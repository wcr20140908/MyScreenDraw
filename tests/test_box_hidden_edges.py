# SPDX-License-Identifier: GPL-3.0-or-later
"""Box visibility regressions: exact edges, real offscreen pixels and isolated exports."""
import math
import os
from collections import Counter

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QEvent, QLineF, QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtSvg import QSvgRenderer

import eps_export
import main
from test_document_safety_610 import document


SIZE = QSize(800, 650)
RECT = (180.0, 190.0, 280.0, 220.0)
# Front/back vertices run TL, TR, BR, BL. Only the far lower-left corner is hidden.
EDGES = ((0, 1), (1, 2), (2, 3), (3, 0),
         (4, 5), (5, 6), (6, 7), (7, 4),
         (0, 4), (1, 5), (2, 6), (3, 7))
HIDDEN = {(6, 7), (7, 4), (3, 7)}


def box(kind, rotation=0):
    return dict(id="box", type=kind, kind="rect", rect=QRectF(*RECT),
                color=QColor("#000000"), width=3, rotation=rotation)


def vertices(item):
    """Independent geometry oracle; never consult production projection/bounds helpers."""
    x, y, w, h = item["rect"].getRect()
    d = min(w, h) * (0.18 if item["type"] == "CUBE" else 0.20)
    if item["type"] == "CUBE":
        front = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        back = [(px + d, py - d) for px, py in front]
    else:
        front = [(x, y + d), (x + w - d, y + d), (x + w - d, y + h), (x, y + h)]
        back = [(x + d, y), (x + w, y), (x + w, y + h - d), (x + d, y + h - d)]
    cx, cy = x + w / 2, y + h / 2
    angle = math.radians(item["rotation"])
    c, s = math.cos(angle), math.sin(angle)
    return [QPointF(cx + (px - cx) * c - (py - cy) * s,
                    cy + (px - cx) * s + (py - cy) * c) for px, py in front + back]


def edge_key(a, b):
    return tuple(sorted(((round(a.x(), 4), round(a.y(), 4)),
                         (round(b.x(), 4), round(b.y(), 4)))))


def assert_edges(records, item):
    points = vertices(item)
    expected = Counter((edge_key(points[a], points[b]), (a, b) in HIDDEN) for a, b in EDGES)
    actual = Counter((edge_key(a, b), dashed) for a, b, dashed in records)
    assert actual == expected, "Exactly three hidden edges and nine solid edges; no solid underpainting"


def eps_edges(text, height):
    """Read stroked EPS geometry, including closed paths (not unrelated setdash strings)."""
    points, records, dashed = [], [], False
    for line in text.splitlines():
        tokens = line.split()
        if not tokens:
            continue
        if tokens[-1] == "setdash":
            dashed = not line.startswith("[]")
        elif tokens[-1] in ("moveto", "lineto"):
            point = QPointF(float(tokens[0]), height - float(tokens[1]))
            if tokens[-1] == "moveto":
                points = [point]
            else:
                points.append(point)
        elif line == "closepath":
            points.append(points[0])
        elif line == "stroke":
            records.extend((a, b, dashed) for a, b in zip(points, points[1:]))
            points = []
        elif line.endswith("fill"):
            points = []
    return records


class RecordingPainter(QPainter):
    """Record geometry while also executing real Qt rasterization."""
    def __init__(self, image):
        super().__init__(image)
        self.edges = []
        self.setRenderHint(QPainter.RenderHint.Antialiasing)

    def record(self, points, closed=False):
        points = [self.worldTransform().map(p) for p in points]
        if closed:
            points.append(points[0])
        dashed = self.pen().style() != Qt.PenStyle.SolidLine
        self.edges.extend((a, b, dashed) for a, b in zip(points, points[1:]))

    def drawLine(self, *args):
        line = QLineF(args[0]) if len(args) == 1 else QLineF(*args)
        self.record([line.p1(), line.p2()])
        super().drawLine(*args)

    def drawLines(self, lines):
        for line in lines:
            self.record([QPointF(line.p1()), QPointF(line.p2())])
        super().drawLines(lines)

    def drawRect(self, rect):
        self.record([rect.topLeft(), rect.topRight(), rect.bottomRight(), rect.bottomLeft()], True)
        super().drawRect(rect)

    def drawPolygon(self, polygon, *args):
        self.record(polygon, True)
        super().drawPolygon(polygon, *args)

    def drawPolyline(self, polygon):
        self.record(polygon)
        super().drawPolyline(polygon)


def image():
    result = QImage(SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    result.fill(QColor("white"))
    return result


def assert_edge_pixels(rendered, points):
    """Sampling actual edge centers catches both absent ink and dashed-over-solid cheats."""
    for edge in EDGES:
        a, b = (points[i] for i in edge)
        length = QLineF(a, b).length()
        trim = min(12.0, length * 0.20)
        samples = max(20, math.ceil(length - 2 * trim))
        values = []
        for i in range(samples):
            t = (trim + (length - 2 * trim) * (i + 0.5) / samples) / length
            p = a + (b - a) * t
            assert rendered.rect().contains(round(p.x()), round(p.y())), (edge, p)
            values.append(rendered.pixelColor(round(p.x()), round(p.y())).lightness())
        dark = sum(v < 150 for v in values) / samples
        gaps = sum(v > 235 for v in values) / samples
        assert dark > 0.30, ("missing edge ink", edge, dark)
        if edge in HIDDEN:
            assert gaps > 0.05, ("hidden edge has no real gaps", edge, gaps)
        else:
            assert gaps < 0.02, ("visible edge must stay continuous", edge, gaps)


@pytest.mark.parametrize("kind", ["CUBE", "CUBOID"])
@pytest.mark.parametrize("rotation", [0, 37, -28])
def test_eps_exact_hidden_edges_without_solid_underpaint(tmp_path, kind, rotation):
    item = box(kind, rotation)
    page = main.serialize_page(dict(segments=[], texts=[], shapes=[item], images=[]))
    destination = tmp_path / "only-box.eps"
    eps_export.write_eps(str(destination), page, SIZE.width(), SIZE.height())
    assert_edges(eps_edges(destination.read_text("latin-1"), SIZE.height()), item)


@pytest.mark.parametrize("kind", ["CUBE", "CUBOID"])
def test_eps_wide_hidden_dashes_leave_gaps_between_round_caps(kind):
    item = box(kind)
    item["width"] = 12
    serialized = main.serialize_page(dict(segments=[], texts=[], shapes=[item], images=[]))["shapes"][0]
    lines = []
    eps_export._emit_shape(lines, serialized, SIZE.height(), "WHITE")
    width, cap, pattern, hidden_count = None, None, [], 0
    for line in lines:
        if line.endswith(" setlinewidth"):
            width = float(line.split()[0])
        elif line.endswith(" setlinecap"):
            cap = int(line.split()[0])
        elif line.endswith(" setdash"):
            pattern = [float(value) for value in line.split("]")[0][1:].split()]
        elif line == "stroke" and pattern:
            hidden_count += 1
            # Round caps protrude half a pen width from BOTH ends of every gap.
            assert cap == 1
            assert pattern[1] > width, "EPS dash gaps must survive the round caps at wide pen widths"
    assert hidden_count == 3


@pytest.mark.parametrize("kind", ["CUBE", "CUBOID"])
@pytest.mark.parametrize("rotation", [0, 37, -28])
def test_qt_exact_hidden_edges_and_real_pixel_gaps(document, kind, rotation):
    _, canvas = document
    item, rendered = box(kind, rotation), image()
    painter = RecordingPainter(rendered)
    try:
        canvas.draw_shape_item(painter, item)
    finally:
        painter.end()
    # Pixel assertion first: old solid rectangles must be observably wrong, not just a spy mismatch.
    assert_edge_pixels(rendered, vertices(item))
    assert_edges(painter.edges, item)


@pytest.mark.parametrize("kind", ["CUBE", "CUBOID"])
@pytest.mark.parametrize("rotation", [0, 37, 90])
def test_bounds_include_all_rotated_vertices_and_pen_radius(document, kind, rotation):
    _, canvas = document
    item = box(kind, rotation)
    bounds = canvas.shape_bounds(item)
    radius = item["width"] / 2
    for point in vertices(item):
        footprint = QRectF(point.x() - radius, point.y() - radius, 2 * radius, 2 * radius)
        assert bounds.contains(footprint), (kind, rotation, bounds, footprint)


@pytest.mark.parametrize("rotation", [0, 90])
def test_partial_repaint_does_not_cull_projected_cube_back_face(document, rotation):
    _, canvas = document
    item = box("CUBE", rotation)
    points = vertices(item)
    midpoint = (points[4] + points[5]) / 2
    clip = QRectF(midpoint.x() - 5, midpoint.y() - 5, 10, 10)
    rendered = image()
    painter = QPainter(rendered)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(clip)
        canvas.draw_content(painter, segments=[], texts=[], images=[], shapes=[item], clip=clip)
    finally:
        painter.end()
    assert rendered.pixelColor(round(midpoint.x()), round(midpoint.y())).lightness() < 150


def mouse(canvas, kind, point):
    event = QMouseEvent(kind, point, point,
        Qt.MouseButton.NoButton if kind == QEvent.Type.MouseMove else Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier)
    {QEvent.Type.MouseButtonPress: canvas.mousePressEvent,
     QEvent.Type.MouseMove: canvas.mouseMoveEvent,
     QEvent.Type.MouseButtonRelease: canvas.mouseReleaseEvent}[kind](event)


@pytest.mark.parametrize("kind", ["CUBE", "CUBOID"])
def test_drag_preview_commit_and_saved_reopen_share_hidden_edges(document, tmp_path, monkeypatch, kind):
    panel, canvas = document
    canvas.resize(SIZE)
    canvas.enter_whiteboard()
    panel.set_drawing_mode(True)
    canvas.draw_state, canvas.shape_type = "SHAPE", kind
    canvas.pen_color, canvas.pen_width = QColor("black"), 3
    observed = []
    original = canvas.draw_shape_item

    def draw(painter, item):
        observed.append(item["type"])
        return original(painter, item)

    monkeypatch.setattr(canvas, "draw_shape_item", draw)
    rect = QRectF(*RECT)
    mouse(canvas, QEvent.Type.MouseButtonPress, rect.topLeft())
    mouse(canvas, QEvent.Type.MouseMove, rect.bottomRight())
    assert canvas.preview_shape and not canvas.shape_items
    preview = image()
    canvas.render(preview)
    assert observed == [kind]
    assert_edge_pixels(preview, vertices(canvas.preview_shape))
    mouse(canvas, QEvent.Type.MouseButtonRelease, rect.bottomRight())
    assert canvas.preview_shape is None and len(canvas.shape_items) == 1
    canvas.selected_ids.clear()
    observed.clear()
    committed = image()
    canvas.render(committed)
    assert observed == [kind]
    assert_edge_pixels(committed, vertices(canvas.shape_items[0]))
    assert preview == committed

    canvas.shape_items[0]["rotation"] = 37
    canvas.mark_content_changed()
    destination = str(tmp_path / "boxes.msd")
    assert panel.save_project(destination)
    assert panel.open_project_from_path(destination)
    restored = canvas.shape_items[0]
    assert restored["type"] == kind and restored["rotation"] == 37
    reopened = image()
    painter = QPainter(reopened)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        canvas.draw_shape_item(painter, restored)
    finally:
        painter.end()
    assert_edge_pixels(reopened, vertices(restored))


@pytest.mark.parametrize("kind", ["CUBE", "CUBOID"])
@pytest.mark.parametrize("rotation", [0, 37])
def test_box_export_png_pdf_svg_pixels_and_eps_topology(document, tmp_path, kind, rotation):
    panel, canvas = document
    canvas.enter_whiteboard()
    item = box(kind, rotation)
    canvas.shape_items = [item]
    canvas.mark_content_changed()
    page = canvas.capture_page()
    scale, dx, dy = canvas.page_export_transform(page, SIZE.width(), SIZE.height())
    points = [QPointF(p.x() * scale + dx, p.y() * scale + dy) for p in vertices(item)]
    assert_edge_pixels(canvas.render_page_pixmap(page, SIZE).toImage(), points)
    for fmt in ("PNG", "PDF", "SVG", "EPS"):
        destination = str(tmp_path / ("only-box." + fmt.lower()))
        if fmt in ("PNG", "PDF"):
            result = main.export_document(fmt, destination, [page],
                lambda p, i, total: canvas.render_page_pixmap(p, SIZE))
        else:
            result = panel._export_vector_pages(fmt, destination, [page], SIZE,
                                               lambda *args: None, lambda: False)
        assert result.success, result
        if fmt == "EPS":
            text = (tmp_path / "only-box.eps").read_text("latin-1")
            assert_edges(eps_edges(text, SIZE.height()), item)
            assert f"{eps_export._fmt(scale)} {eps_export._fmt(scale)} scale" in text
            continue
        if fmt == "PNG":
            rendered = QImage(destination)
        elif fmt == "PDF":
            pdf = QPdfDocument(None)
            assert pdf.load(destination) == QPdfDocument.Error.None_
            rendered = pdf.render(0, SIZE)
            pdf.close()
        else:
            rendered = image()
            painter = QPainter(rendered)
            try:
                QSvgRenderer(destination).render(painter)
            finally:
                painter.end()
        assert_edge_pixels(rendered, points)
