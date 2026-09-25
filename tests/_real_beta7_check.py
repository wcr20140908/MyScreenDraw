# SPDX-License-Identifier: GPL-3.0-or-later
"""beta.7 real-screen checks. Occupies the mouse briefly; do not touch it."""
import ctypes
import ctypes.wintypes as wt
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.pop("QT_QPA_PLATFORM", None)

from PyQt6.QtCore import Qt, QRect, QTimer, qInstallMessageHandler
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication, QMessageBox

from _grab import save_png
from zorder_probe import visible_zorder

import toolbar_windows

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "msd_beta7"
OUT.mkdir(parents=True, exist_ok=True)
QT_MESSAGES = []


def _qt_handler(mode, ctx, msg):
    QT_MESSAGES.append(msg)
    print("[QT]", msg, flush=True)


qInstallMessageHandler(_qt_handler)
import main

main.ensure_directories()
_tmp = tempfile.mkdtemp(prefix="msd_beta7_cfg_")
_cfg_copy = os.path.join(_tmp, "config.json")
if os.path.exists(main.CONFIG_FILE):
    shutil.copy(main.CONFIG_FILE, _cfg_copy)
main.CONFIG_FILE = _cfg_copy

u32 = ctypes.windll.user32
u32.GetSystemMetrics.restype = ctypes.c_int
SM_CXSCREEN, SM_CYSCREEN = 0, 1
MOUSEEVENTF_MOVE, MOUSEEVENTF_ABSOLUTE = 0x0001, 0x8000
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
INPUT_MOUSE = 0
RESULTS = []


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def _send(flags, dx=0, dy=0):
    inp = INPUT(type=INPUT_MOUSE)
    inp.mi = MOUSEINPUT(dx, dy, 0, flags, 0, None)
    if u32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
        raise RuntimeError("SendInput failed")


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + ("  -- " + detail if detail else ""), flush=True)
    return ok


def pump(ms):
    end = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < end:
        QApplication.processEvents()
        time.sleep(0.01)


def _abs_move(px, py):
    cx, cy = u32.GetSystemMetrics(SM_CXSCREEN), u32.GetSystemMetrics(SM_CYSCREEN)
    _send(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
          int(round(px * 65535 / (cx - 1))), int(round(py * 65535 / (cy - 1))))


def click_logical(lx, ly):
    screen = QApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen else 1.0
    cx, cy = u32.GetSystemMetrics(SM_CXSCREEN), u32.GetSystemMetrics(SM_CYSCREEN)
    for _ in range(3):
        _abs_move(lx * dpr, ly * dpr)
        time.sleep(0.08)
        QApplication.processEvents()
        got = QCursor.pos()
        if abs(got.x() - lx) <= 3 and abs(got.y() - ly) <= 3:
            break
    else:
        raise RuntimeError(f"pointer missed: wanted ({lx},{ly}) got ({got.x()},{got.y()})")
    time.sleep(0.05)
    _send(MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.04)
    QApplication.processEvents()
    _send(MOUSEEVENTF_LEFTUP)
    time.sleep(0.03)
    QApplication.processEvents()


def click_button(button):
    # 按钮的样式最小宽度有时比所在窗口还宽，几何中心会落在窗口外、点不到。
    # 取按钮和它顶层窗口的交集，点交集的中心。
    top = button.window().frameGeometry()
    rect = button.rect()
    origin = button.mapToGlobal(rect.topLeft())
    visible = QRect(origin, rect.size()).intersected(top)
    if not visible.isValid():
        visible = QRect(origin, rect.size())
    center = visible.center()
    click_logical(center.x(), center.y())


def grab(path, *widgets):
    xs = [w.frameGeometry().left() for w in widgets]
    ys = [w.frameGeometry().top() for w in widgets]
    rs = [w.frameGeometry().right() for w in widgets]
    bs = [w.frameGeometry().bottom() for w in widgets]
    screen = QApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen else 1.0
    x, y = max(0, min(xs) - 20), max(0, min(ys) - 20)
    w, h = max(rs) - x + 20, max(bs) - y + 20
    save_png(str(path), int(x * dpr), int(y * dpr), int(w * dpr), int(h * dpr))


def taskbar_windows():
    pid = os.getpid()
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def visit(hwnd, _lparam):
        owner_pid = wt.DWORD(0)
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner_pid))
        if owner_pid.value != pid or not u32.IsWindowVisible(hwnd):
            return True
        exstyle = u32.GetWindowLongW(hwnd, -20)
        owner = u32.GetWindow(hwnd, 4)  # GW_OWNER
        if exstyle & 0x00040000 and not owner:  # WS_EX_APPWINDOW, unowned taskbar candidate
            length = u32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            u32.GetWindowTextW(hwnd, buf, length + 1)
            found.append((int(hwnd), buf.value))
        return True

    u32.EnumWindows(visit, 0)
    return found


def rects_overlap(a, b):
    return a.intersects(b)


def hwnd(widget):
    return int(widget.winId())


def run(app, panel, canvas):
    toolbar = panel.toolbar_window
    panel.set_orientation("portrait")
    panel.set_drawing_mode(False)
    pump(900)
    mode = toolbar.icon_buttons["mode"]
    pen = toolbar.icon_buttons["pen"]
    whiteboard = toolbar.icon_buttons["whiteboard"]
    close = toolbar.icon_buttons["close"]
    check("mouse mode highlights mouse", mode.objectName() == "IconBtnActive", mode.objectName())
    check("mouse mode does not highlight annotation", pen.objectName() != "IconBtnActive", pen.objectName())
    check("mouse button text", mode.text() == main.tr("mouse"), mode.text())
    check("logo and toolbar do not overlap",
          not rects_overlap(panel.logo_window.frameGeometry(), toolbar.frameGeometry()),
          f"logo={panel.logo_window.frameGeometry()} toolbar={toolbar.frameGeometry()}")
    grab(OUT / "01_mouse_highlight.png", toolbar, panel.logo_window)

    before = toolbar.width()
    canvas_hwnd_before = hwnd(canvas)
    panel.set_drawing_mode(True)
    pump(500)
    click_button(whiteboard)
    pump(900)
    panel._sync_split_geometry()
    pump(300)
    check("whiteboard button says exit", whiteboard.text() == main.tr("exit_whiteboard"), whiteboard.text())
    check("only board toggle stays in the toolbar",
          toolbar.icon_wb_box.isVisible() and set(toolbar.WB_KEYS) == {"board_style"})
    check("whiteboard width unchanged", toolbar.width() == before, f"{before} -> {toolbar.width()}")
    board = toolbar.icon_buttons["board_style"]
    entry_bottom = whiteboard.mapToGlobal(whiteboard.rect().bottomRight()).y()
    board_top = board.mapToGlobal(board.rect().topLeft()).y()
    close_top = close.mapToGlobal(close.rect().topLeft()).y()
    board_bottom = board.mapToGlobal(board.rect().bottomRight()).y()
    check("board toggle sits below the whiteboard entry", board_top > entry_bottom,
          f"{board_top} > {entry_bottom}")
    check("close stays at the bottom", close_top > board_bottom, f"{close_top} > {board_bottom}")
    check("board toggle keeps the normal button size",
          board.width() == toolbar.icon_buttons["mode"].width(),
          f"board={board.width()} mode={toolbar.icon_buttons['mode'].width()}")
    rail = panel.page_rail
    check("page rail is visible at the bottom right", rail.isVisible())
    check("page rail shows the page count", panel.rail_count.text() == "1/1", panel.rail_count.text())
    check("page rail sits in the bottom right",
          rail.frameGeometry().right() > toolbar.frameGeometry().right()
          and rail.frameGeometry().bottom() > toolbar.frameGeometry().bottom())
    check("whiteboard entry does not rebuild canvas", hwnd(canvas) == canvas_hwnd_before,
          f"before={canvas_hwnd_before} after={hwnd(canvas)}")
    check("whiteboard logo and toolbar do not overlap",
          not rects_overlap(panel.logo_window.frameGeometry(), toolbar.frameGeometry()),
          f"logo={panel.logo_window.frameGeometry()} toolbar={toolbar.frameGeometry()}")
    grab(OUT / "02_whiteboard_layout.png", toolbar, panel.logo_window, rail)

    updates = []
    original = canvas.paintEvent
    def counted(event):
        updates.append(1)
        return original(event)
    canvas.paintEvent = counted
    click_button(mode)
    pump(700)
    mouse_updates = len(updates)
    updates.clear()
    click_button(pen)
    pump(700)
    annotation_updates = len(updates)
    canvas.paintEvent = original
    check("mode toggles do not repaint the canvas repeatedly",
          mouse_updates <= 3 and annotation_updates <= 3,
          f"mouse={mouse_updates} annotation={annotation_updates}")

    stroke = []
    canvas.last_point = None
    canvas.current_stroke_id = 1
    canvas.current_stroke_widths = []
    for i in range(30):
        canvas.add_smooth_segments(main.QPoint(100 + i * 12, 200 + (i % 3)))
    check("strokes are sampled densely", len(canvas.all_segments) >= 60, str(len(canvas.all_segments)))
    canvas.all_segments.clear()

    panel.show_only_sub(None)
    pump(200)
    click_button(close)
    pump(700)
    check("close hides the main windows",
          not panel.logo_window.isVisible() and not toolbar.isVisible())
    check("close leaves the app running", panel.lifecycle.state == "hidden", panel.lifecycle.state)
    check("close keeps the tray icon",
          panel.lifecycle.tray_icon is not None and panel.lifecycle.tray_icon.isVisible())
    check("only one taskbar button", len(taskbar_windows()) <= 1, str(taskbar_windows()))
    relevant = [msg for msg in QT_MESSAGES if any(token in msg for token in ("killTimer", "requestActivate", "UpdateLayeredWindow"))]
    check("no relevant Qt warnings", not relevant, str(relevant))


def main_():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    panel = main.ControlPanel()
    canvas = main.DrawingCanvas(panel)
    panel.canvas = canvas
    panel.apply_theme()
    panel.load_settings()
    panel.update_whiteboard_ui()
    panel.update_history_ui()
    panel.show()
    canvas.show()
    panel.bind_topmost_stack()
    rc = [0]

    def go():
        try:
            run(app, panel, canvas)
        except Exception:
            traceback.print_exc()
            RESULTS.append(("harness exception", False, traceback.format_exc().splitlines()[-1]))
        finally:
            failed = [item for item in RESULTS if not item[1]]
            print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed", flush=True)
            for name, ok, detail in failed:
                print("  FAIL", name, "--", detail, flush=True)
            rc[0] = 1 if failed else 0
            try:
                panel.listener.stop()
            except Exception:
                pass
            for name in ("timer", "autosave_timer"):
                try:
                    getattr(panel, name).stop()
                except Exception:
                    pass
            try:
                panel.lifecycle.tray_icon.hide()
            except Exception:
                pass
            app.quit()

    QTimer.singleShot(1500, go)
    app.exec()
    shutil.rmtree(_tmp, ignore_errors=True)
    return rc[0]


if __name__ == "__main__":
    raise SystemExit(main_())
