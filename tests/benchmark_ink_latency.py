# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated input/paint CPU benchmark. Not a hardware pen-to-photon measurement."""
import argparse
import json
import math
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['MYSCREENDRAW_NO_KEYBOARD'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QEvent, QLine, QPointF, Qt
from PyQt6.QtGui import QColor, QMouseEvent, QPen
from PyQt6.QtWidgets import QApplication
import main


class TimedCanvas(main.DrawingCanvas):
    def __init__(self):
        self.paint_samples = []
        super().__init__(None)

    def paintEvent(self, event):
        start = time.perf_counter()
        super().paintEvent(event)
        self.paint_samples.append({'ms': (time.perf_counter()-start)*1000,
                                   'width': event.rect().width(), 'height': event.rect().height()})


def make_ink(count):
    pen = QPen(QColor(28, 80, 180), 4, Qt.PenStyle.SolidLine,
               Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    result = []
    for part in range(count):
        stroke, index = divmod(part, 100)
        x, y = 10 + (stroke % 20)*60 + index//2, 15 + (stroke//20 % 30)*27
        result.append({'id': str(stroke), 'line': QLine(x, y, x+2, y+round(math.sin(index/5)*3)),
                       'pen': pen, 'marker': False})
    return result


def send(canvas, kind, x, y, button, buttons):
    point = QPointF(x, y)
    event = QMouseEvent(kind, point, point, button, buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(canvas, event)


def run(counts):
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix='myscreendraw-ink-bench-') as temporary:
        root = Path(temporary)
        # The real telemetry call is timed too, but it only writes this owned root.
        for name, path in {'DATA_DIR':root/'data', 'EXPORT_DIR':root/'exports',
            'AUTOSAVE_DIR':root/'data'/'autosave', 'CONFIG_FILE':root/'data'/'config.json',
            'ROSTER_FILE':root/'data'/'roster.json', 'TELEMETRY_FILE':root/'data'/'events.jsonl',
            'LOG_FILE':root/'data'/'app.log'}.items():
            setattr(main, name, str(path))
        results=[]
        for count in counts:
            canvas=TimedCanvas()
            canvas.resize(800,800)
            canvas.whiteboard_mode=True
            canvas.smart_shapes_enabled=False
            canvas.draw_state='PEN'
            canvas.all_segments=make_ink(count)
            canvas.mark_content_changed()
            canvas.pages=[canvas.capture_page()]
            canvas.show();app.processEvents();app.processEvents()
            canvas.paint_samples.clear()
            begin=time.perf_counter()
            send(canvas,QEvent.Type.MouseButtonPress,550,700,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton)
            press=(time.perf_counter()-begin)*1000
            callbacks=[];frames=[]
            for i in range(6):
                begin=time.perf_counter()
                send(canvas,QEvent.Type.MouseMove,555+i*4,702+i,Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton)
                callbacks.append((time.perf_counter()-begin)*1000)
                app.processEvents();app.processEvents()
                frames.append((time.perf_counter()-begin)*1000)
            begin=time.perf_counter()
            send(canvas,QEvent.Type.MouseButtonRelease,575,707,Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)
            release=(time.perf_counter()-begin)*1000
            app.processEvents();app.processEvents()
            paints=canvas.paint_samples
            results.append({'segments_before':count, 'press_callback_ms':round(press,3),
                'move_callback_median_ms':round(statistics.median(callbacks),3),
                'move_through_paint_median_ms':round(statistics.median(frames),3),
                'move_through_paint_max_ms':round(max(frames),3),
                'release_callback_ms':round(release,3),
                'paint_median_ms':round(statistics.median([p['ms'] for p in paints]),3),
                'paint_max_ms':round(max(p['ms'] for p in paints),3),
                'paint_rects':[[p['width'],p['height']] for p in paints]})
            canvas.hide();canvas.deleteLater()
            from PyQt6.QtCore import QCoreApplication
            QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    return {'platform':os.environ.get('QT_QPA_PLATFORM'), 'canvas_size':[800,800],
            'kind':'ordinary pen, synthetic offscreen CPU event-to-paint', 'results':results}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path)
    parser.add_argument('--counts',type=int,nargs='+',default=[0,20000,100000])
    args=parser.parse_args()
    result=run(args.counts)
    text=json.dumps(result,indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text+'\n',encoding='utf-8')
    print(text)
