# SPDX-License-Identifier: GPL-3.0-or-later
"""Preserve imported originals without changing annotation or project behavior."""
import copy
import json
import uuid

import pytest
from PyQt6.QtCore import QLineF, QPoint, QPointF, QRectF, QSizeF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt6.QtTest import QTest
from test_upgrade_settings import app, rig


def original(canvas):
    pixmap = QPixmap(400, 220)
    pixmap.fill(QColor('white'))
    image = {'id': uuid.uuid4(), 'pos': QPointF(300, 220),
             'size': QSizeF(400, 220), 'rotation': 0.0, 'pixmap': pixmap}
    canvas.image_items.append(image)
    return image


def annotation(canvas):
    stroke = {'id': uuid.uuid4(), 'line': QLineF(180, 220, 260, 220),
              'pen': QPen(QColor('#ff0000'), 8)}
    canvas.all_segments.append(stroke)
    return stroke


@pytest.mark.parametrize('value', [None, 0, 1, 'false', [], {}, True, False])
def test_preferences_default_and_strict_boolean_loading(rig, value):
    p, c = rig.load({} if value is None else {'preserve_original_images': value})
    expected = value if isinstance(value, bool) else True
    assert p.preserve_original_images is expected
    assert c.preserve_original_images is expected
    p.open_settings_panel()
    assert p.document_preferences.preserve_images_checkbox.isChecked() is expected


def test_missing_old_field_resets_to_enabled_even_after_disabling(rig):
    p, c = rig.fresh()
    p.set_preserve_original_images(False, persist=False)
    rig.main.atomic_write_json(rig.main.CONFIG_FILE, {})
    p.load_settings()
    assert p.preserve_original_images and c.preserve_original_images


def test_real_checkbox_is_immediate_persistent_and_clears_image_selection(rig, app):
    p, c = rig.fresh()
    p.open_settings_panel()
    checkbox = p.document_preferences.preserve_images_checkbox
    assert checkbox.isChecked()
    p.settings_scroll.ensureWidgetVisible(checkbox)
    app.processEvents()
    QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton, pos=QPoint(8, checkbox.height() // 2))
    assert not p.preserve_original_images and not c.preserve_original_images
    image = original(c)
    c.selected_ids = {image['id']}
    QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton, pos=QPoint(8, checkbox.height() // 2))
    assert p.preserve_original_images and not c.selected_ids
    assert len(c.image_items) == 1
    assert not c.undo_stack
    QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton, pos=QPoint(8, checkbox.height() // 2))
    assert json.loads(rig.path.read_text('utf-8'))['preserve_original_images'] is False
    restored, restored_canvas = rig.load()
    assert not restored.preserve_original_images and not restored_canvas.preserve_original_images


@pytest.mark.parametrize('enabled', [True, False])
@pytest.mark.parametrize('eraser_type', ['CIRCLE', 'STROKE'])
def test_eraser_removes_annotation_and_conditionally_preserves_original(rig, enabled, eraser_type):
    p, c = rig.fresh()
    p.set_preserve_original_images(enabled, persist=False)
    image = original(c)
    annotation(c)
    c.eraser_type = eraser_type
    c.execute_erase(QPointF(220, 220))
    assert not c.all_segments
    assert [item['id'] for item in c.image_items] == ([image['id']] if enabled else [])


@pytest.mark.parametrize('enabled', [True, False])
def test_clear_and_undo_redo_preserve_original_according_to_setting(rig, enabled):
    p, c = rig.fresh()
    p.set_preserve_original_images(enabled, persist=False)
    image = original(c)
    annotation(c)
    p.clear()
    assert not c.all_segments
    assert len(c.image_items) == int(enabled)
    c.undo()
    assert len(c.all_segments) == 1 and c.image_items[0]['id'] == image['id']
    c.redo()
    assert not c.all_segments and len(c.image_items) == int(enabled)


def test_clear_original_only_is_noop(rig):
    p, c = rig.fresh()
    original(c)
    revision = c.content_revision
    p.clear()
    assert len(c.image_items) == 1 and not c.undo_stack
    assert c.content_revision == revision


@pytest.mark.parametrize('enabled', [True, False])
def test_point_and_marquee_selection_match_visible_layer_order(rig, enabled):
    p, c = rig.fresh()
    p.set_preserve_original_images(enabled, persist=False)
    image = original(c)
    stroke = annotation(c)
    assert c.hit_object_at(QPointF(220, 220)) == stroke['id']
    assert c.hit_object_at(QPointF(300, 270)) == (None if enabled else image['id'])
    c.select_objects_in_rect(QRectF(90, 100, 450, 280))
    assert c.selected_ids == ({stroke['id']} if enabled else {stroke['id'], image['id']})


@pytest.mark.parametrize('action', ['move', 'scale', 'rotate', 'delete', 'duplicate'])
def test_stale_selected_image_cannot_bypass_protection(rig, action):
    p, c = rig.fresh()
    image = original(c)
    before = (QPointF(image['pos']), QSizeF(image['size']), image['rotation'])
    c.selected_ids = {image['id']}
    if action == 'move':
        c.move_selection(QPointF(45, 30))
    elif action == 'scale':
        c.scale_selection(1.5)
    elif action == 'rotate':
        c.rotate_selection(90)
    elif action == 'delete':
        c.delete_selection()
    else:
        c.duplicate_selection()
    assert c.image_items == [image]
    assert (image['pos'], image['size'], image['rotation']) == before
    assert not c.selected_ids and not c.undo_stack


def test_disabled_allows_image_transform_duplicate_and_delete(rig):
    p, c = rig.fresh()
    p.set_preserve_original_images(False, persist=False)
    image = original(c)
    c.selected_ids = {image['id']}
    c.move_selection(QPointF(20, 10))
    c.scale_selection(1.5)
    c.rotate_selection(45)
    assert image['pos'] == QPointF(320, 230)
    assert image['size'] == QSizeF(600, 330) and image['rotation'] == 45
    c.duplicate_selection()
    assert len(c.image_items) == 2
    c.delete_selection()
    assert c.image_items == [image]


@pytest.mark.parametrize('enabled', [True, False])
def test_imported_image_auto_selection_respects_preference(rig, enabled):
    p, c = rig.fresh()
    p.set_preserve_original_images(enabled, persist=False)
    pixmap = QPixmap(120, 80)
    pixmap.fill(QColor('white'))
    image = p.insert_image_pixmap(pixmap)
    assert c.selected_ids == (set() if enabled else {image['id']})
    assert c.image_items == [image]


@pytest.mark.parametrize('enabled', [True, False])
def test_opaque_original_is_below_ink_in_display_and_raster_export(rig, enabled):
    p, c = rig.fresh()
    p.set_preserve_original_images(enabled, persist=False)
    original(c)
    annotation(c)
    output = QImage(600, 440, QImage.Format.Format_ARGB32)
    output.fill(QColor('white'))
    painter = QPainter(output)
    c.draw_content(painter)
    painter.end()
    assert output.pixelColor(220, 220) == QColor('#ff0000')
    assert output.pixelColor(300, 270) == QColor('white')


def test_eps_original_is_below_ink_and_shapes(rig):
    from eps_export import _eps_lines
    page = {'segments': [{'id': 'ink', 'p1': [180, 220], 'p2': [260, 220],
                          'color': '#ff0000', 'width': 8}],
            'images': [{'id': 'image', 'pos': [300, 220], 'size': [400, 220], 'rotation': 0}]}
    lines = _eps_lines(page, 600, 440, 'WHITE', {'image': (1, 1, bytes([255, 255, 255]))})
    image_line = next(i for i, line in enumerate(lines) if 'colorimage' in line)
    red_line = next(i for i, line in enumerate(lines) if line == '1 0 0 setrgbcolor')
    assert image_line < red_line


@pytest.mark.parametrize('eraser_type', ['CIRCLE', 'STROKE'])
def test_erase_undo_redo_keeps_original_and_restores_only_annotation(rig, eraser_type):
    p, c = rig.fresh()
    image = original(c)
    annotation(c)
    c.eraser_type = eraser_type
    c.push_undo()
    c.execute_erase(QPointF(220, 220))
    assert c.image_items == [image] and not c.all_segments
    c.undo()
    assert c.image_items[0]['id'] == image['id'] and len(c.all_segments) == 1
    c.redo()
    assert c.image_items[0]['id'] == image['id'] and not c.all_segments


def test_real_pdf_pages_remain_protected_after_project_reopen(rig, tmp_path, monkeypatch):
    from pathlib import Path
    from test_export_ui_610 import Progress
    p, c = rig.fresh()
    c.resize(900, 600)
    monkeypatch.setattr(p, '_create_document_progress', lambda *_: Progress())
    sample = Path(rig.main.__file__).parent / 'assets/tutorials/fixtures/media-c09-sample.pdf'
    assert p.import_pdf(str(sample)) == 2
    assert len(c.image_items) == 1
    image = c.image_items[0]
    center = QPointF(image['pos'])
    assert c.hit_object_at(center) is None
    c.all_segments.append({'id': uuid.uuid4(),
                           'line': QLineF(center.x()-30, center.y(), center.x()+30, center.y()),
                           'pen': QPen(QColor('#ff0000'), 8)})
    project = tmp_path / '课堂原图.msd'
    assert p.save_project(str(project))
    assert p.open_project_from_path(str(project))
    assert len(c.image_items) == 1 and len(c.all_segments) == 1
    c.execute_erase(center)
    assert len(c.image_items) == 1 and not c.all_segments
    p.clear()
    assert len(c.image_items) == 1
    p.set_preserve_original_images(False, persist=False)
    assert c.hit_object_at(center) == c.image_items[0]['id']


def test_project_roundtrip_keeps_images_and_global_preference(rig, tmp_path):
    p, c = rig.fresh()
    original(c)
    annotation(c)
    c.whiteboard_mode = True
    project = tmp_path / 'images.msd'
    assert p.save_project(str(project))
    p.set_preserve_original_images(False, persist=False)
    assert p.open_project_from_path(str(project))
    assert not c.preserve_original_images
    assert len(c.image_items) == 1 and len(c.all_segments) == 1
    p.set_preserve_original_images(True, persist=False)
    p.clear()
    assert p.save_project(str(project))
    assert p.open_project_from_path(str(project))
    assert c.preserve_original_images and len(c.image_items) == 1 and not c.all_segments


def test_translations_are_complete_and_use_plain_chinese(rig):
    import i18n
    for key in ('preserve_original_images', 'preserve_original_images_hint'):
        assert len(i18n._BASE[key]) == len(i18n._LANGS)
        assert all(value.strip() for value in i18n._BASE[key])
    assert i18n._BASE['preserve_original_images'][0] == '保留原图'
