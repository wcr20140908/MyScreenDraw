# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic offscreen CPU paint benchmark; never grabs the desktop."""
import json
import math
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import statistics
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QLine, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen
from PyQt6.QtWidgets import QApplication
import main


def build_segments(strokes=120, parts=180):
    result = []
    for stroke in range(strokes):
        pen = QPen(QColor(20, 110, 200, 90), 9, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        x, y = (stroke % 10) * 110, (stroke // 10) * 60
        previous = (x, y)
        for step in range(1, parts + 1):
            point = (x + step // 2, y + round(math.sin(step / 12) * 18))
            result.append({"id": str(stroke), "line": QLine(*previous, *point), "pen": pen, "marker": True})
            previous = point
    return result


def run():
    app = QApplication.instance() or QApplication([])
    canvas = main.DrawingCanvas(None)
    canvas.all_segments = build_segments()
    image = QImage(1280, 900, QImage.Format.Format_ARGB32_Premultiplied)
    def frame(clip=None):
        image.fill(QColor("white"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if clip is not None: painter.setClipRect(clip)
        canvas.draw_segments(painter, canvas.all_segments, clip=clip)
        painter.end()
    def measure(fn, repeats=7):
        times = []
        for _ in range(repeats):
            start = time.perf_counter(); fn(); times.append((time.perf_counter()-start)*1000)
        return round(statistics.median(times), 3)
    cold = measure(lambda: frame(), 1)
    full = measure(lambda: frame())
    clip = QRectF(1190, 810, 25, 35)
    clipped = measure(lambda: frame(clip))
    bounds = measure(lambda: [canvas.object_bounds(str(i)) for i in range(120)])
    active = []
    for index in range(35):
        canvas.all_segments.append({"id": "active", "line": QLine(index*2, 820, index*2+2, 820),
                                    "pen": canvas.all_segments[0]["pen"], "marker": True})
        start = time.perf_counter(); frame(QRectF(0, 790, 100, 70)); active.append((time.perf_counter()-start)*1000)
    result = {"segments": 21600, "strokes": 120, "cold_ms": cold, "warm_full_ms": full,
              "warm_clipped_ms": clipped, "all_bounds_ms": bounds,
              "active_append_frame_ms": round(statistics.median(active), 3), "platform": "offscreen"}
    canvas.close()
    return result


if __name__ == "__main__":
    result = run()
    text = json.dumps(result, indent=2)
    if len(sys.argv) > 1: Path(sys.argv[1]).write_text(text + "\n", encoding="utf-8")
    print(text)
