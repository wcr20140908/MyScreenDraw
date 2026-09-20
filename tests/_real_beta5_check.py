# SPDX-License-Identifier: GPL-3.0-or-later
"""beta.5 实屏检查（手动工具，会占用鼠标和屏幕，运行时不要动鼠标）。

    python tests/_real_beta5_check.py [outdir]

检查项：
  1. 竖版工具栏整栏落在可用屏幕内（不压任务栏），LOGO 与工具栏同宽
  2. 每个按钮都有图标（穿透模式/文件/关闭 以前是空的）
  3. 绘图模式下工具栏/LOGO 在画布之上（z-order），真实鼠标点击画笔按钮能弹出子菜单
  4. LOGO 真实点击折叠/展开
  5. F12（队列信号）进后台 → 恢复：画布、LOGO、工具栏都回来且仍在画布之上
  6. 横版：LOGO 与工具栏同高、不出右边
  7. 收集 Qt 警告（killTimer / requestActivate / UpdateLayeredWindow）
"""
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

from PyQt6.QtCore import QTimer, qInstallMessageHandler  # noqa: E402
from PyQt6.QtGui import QCursor  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from _grab import save_png  # noqa: E402
from zorder_probe import visible_zorder, describe  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "msd_beta5"
OUT.mkdir(parents=True, exist_ok=True)

QT_MESSAGES = []


def _qt_handler(mode, ctx, msg):
    QT_MESSAGES.append(msg)
    print("[QT]", msg, flush=True)


qInstallMessageHandler(_qt_handler)

import main  # noqa: E402

# 不碰用户真实配置：复制一份到临时目录再加载，写回也只写副本。
main.ensure_directories()
_tmp = tempfile.mkdtemp(prefix="msd_beta5_cfg_")
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


RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + ("  -- " + detail if detail else ""), flush=True)
    return ok


def _abs_move(px, py):
    """物理像素 → SendInput 绝对坐标。"""
    cx, cy = u32.GetSystemMetrics(SM_CXSCREEN), u32.GetSystemMetrics(SM_CYSCREEN)
    nx = int(round(px * 65535 / (cx - 1)))
    ny = int(round(py * 65535 / (cy - 1)))
    _send(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, nx, ny)


def move_pointer(lx, ly):
    """逻辑坐标 → 物理 → 0..65535；移动后回读 QCursor.pos()，没落到目标附近就拒绝按下。

    光标贴着屏幕边时，Windows 有时会把第一次绝对移动夹住（实测 wanted (36,120)
    却停在 (0,91)）。先落到屏幕中心再打目标，夹边就不会发生。
    """
    screen = QApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen else 1.0
    cx, cy = u32.GetSystemMetrics(SM_CXSCREEN), u32.GetSystemMetrics(SM_CYSCREEN)
    _abs_move(cx / 2.0, cy / 2.0)
    time.sleep(0.03)
    QApplication.processEvents()
    _abs_move(lx * dpr, ly * dpr)
    time.sleep(0.05)
    QApplication.processEvents()
    got = QCursor.pos()
    if abs(got.x() - lx) > 2 or abs(got.y() - ly) > 2:
        raise RuntimeError(f"pointer missed: wanted ({lx},{ly}) got ({got.x()},{got.y()})")


def click_logical(lx, ly, settle_ms=80):
    """先落到目标再停一会儿再按下：LOGO 的拖动阈值只有 5px，
    如果按下瞬间还夹着上一次绝对移动的残余 MouseMove，会被当成拖动、吞掉 clicked。"""
    move_pointer(lx, ly)
    time.sleep(settle_ms / 1000.0)
    QApplication.processEvents()
    _send(MOUSEEVENTF_LEFTDOWN)
    time.sleep(0.04)
    QApplication.processEvents()
    _send(MOUSEEVENTF_LEFTUP)
    time.sleep(0.03)
    QApplication.processEvents()


def pump(ms):
    end = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < end:
        QApplication.processEvents()
        time.sleep(0.01)


def geom(w):
    g = w.frameGeometry()
    return f"({g.x()},{g.y()} {g.width()}x{g.height()})"


def zorder_index(hwnds):
    order = visible_zorder(0)
    return {h: (order.index(h) if h in order else None) for h in hwnds}


def own_windows_dump():
    pid = os.getpid()
    out = []
    for i, hwnd in enumerate(visible_zorder(0)):
        p = wt.DWORD(0)
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid:
            out.append(f"  {i} {describe(hwnd)}")
    return "\n".join(out)


def visible_subs(pnl):
    return [s for s in pnl.all_subs() if s is not None and s.isVisible()]


def grab_around(path, *widgets, pad=20):
    xs = [w.frameGeometry().left() for w in widgets]
    ys = [w.frameGeometry().top() for w in widgets]
    rs = [w.frameGeometry().right() for w in widgets]
    bs = [w.frameGeometry().bottom() for w in widgets]
    screen = QApplication.primaryScreen()
    dpr = screen.devicePixelRatio() if screen else 1.0
    x, y = max(0, min(xs) - pad), max(0, min(ys) - pad)
    w, h = max(rs) - x + pad, max(bs) - y + pad
    try:
        save_png(str(path), int(x * dpr), int(y * dpr), int(w * dpr), int(h * dpr))
        print("  grabbed", path, flush=True)
    except Exception as exc:
        print("  grab failed:", exc, flush=True)


def run(app, pnl, cvs):
    tb, logo = pnl.toolbar_window, pnl.logo_window
    screen = pnl.screen() or QApplication.primaryScreen()
    avail = screen.availableGeometry()
    print("screen avail:", avail, "dpr", screen.devicePixelRatio(), "orientation", pnl.orientation)

    # ---- 1. 竖版几何 ----
    pnl.set_orientation("portrait")
    pump(800)
    print("toolbar", geom(tb), "logo", geom(logo), "panel", geom(pnl))
    print("button size", tb._button_width, "x", tb._button_height, "wb cols", tb._wb_columns)
    tg, lg = tb.frameGeometry(), logo.frameGeometry()
    check("portrait: toolbar inside available screen",
          avail.contains(tg), f"toolbar {geom(tb)} avail {avail}")
    check("portrait: logo inside available screen", avail.contains(lg), geom(logo))
    check("portrait: logo width == toolbar width", lg.width() == tg.width(),
          f"logo {lg.width()} toolbar {tg.width()}")
    check("portrait: toolbar directly below logo", tg.x() == lg.x() and abs(tg.y() - (lg.bottom() + 1)) <= 4,
          f"logo bottom {lg.bottom()} toolbar top {tg.y()}")
    check("buttons not square-ish (w>=h)", tb._button_width >= tb._button_height,
          f"{tb._button_width}x{tb._button_height}")
    check("buttons no taller than 44", tb._button_height <= 44, str(tb._button_height))
    bad_icons = [k for k, b in tb.icon_buttons.items() if b.icon().isNull() or b.icon().pixmap(20, 20).isNull()]
    check("every toolbar button has an icon", not bad_icons, str(bad_icons))
    off = []
    for k, b in tb.icon_buttons.items():
        if not b.isVisible():
            continue
        r = b.geometry()
        # 样式表 min/max 是内容盒，外面还有 padding: 1px
        if r.width() != tb._button_width + 2 or r.height() != tb._button_height + 2:
            off.append((k, r.width(), r.height()))
    check("visible buttons have target size", not off, str(off))
    grab_around(OUT / "01_portrait.png", tb, logo)

    # ---- 2. 绘图模式 z-order + 真实点击 ----
    pnl.set_drawing_mode(True)
    pump(1200)
    print(own_windows_dump())
    zi = zorder_index([int(tb.winId()), int(logo.winId()), int(cvs.winId())])
    tb_i, lg_i, cv_i = zi[int(tb.winId())], zi[int(logo.winId())], zi[int(cvs.winId())]
    check("drawing: toolbar above canvas", tb_i is not None and cv_i is not None and tb_i < cv_i,
          f"toolbar idx {tb_i} canvas idx {cv_i}")
    check("drawing: logo above canvas", lg_i is not None and cv_i is not None and lg_i < cv_i,
          f"logo idx {lg_i} canvas idx {cv_i}")

    pen = tb.icon_buttons["pen"]
    c = pen.mapToGlobal(pen.rect().center())
    pnl.show_only_sub(None)
    pump(200)
    click_logical(c.x(), c.y())
    pump(600)
    subs = visible_subs(pnl)
    check("drawing: real click on pen opens a submenu", bool(subs), str([s.__class__.__name__ for s in subs]))
    grab_around(OUT / "02_pen_menu.png", tb, logo, *([pnl.menu_panel] if subs else []))
    if subs:
        # all_subs() 里是 menu_panel 的子 QFrame，坐标相对父窗口；真正的顶层窗口是 menu_panel
        mg = pnl.menu_panel.frameGeometry()
        check("submenu fully on screen", avail.contains(mg), str(mg))
        check("submenu does not overlap toolbar", not mg.intersects(tb.frameGeometry()),
              f"menu {mg} toolbar {tb.frameGeometry()}")

    # 点击画布空白处（远离所有窗口）→ 子菜单关闭
    click_logical(avail.right() - 200, avail.bottom() - 200)
    pump(500)
    still = visible_subs(pnl)
    check("click on canvas dismisses submenu", not still, str([s.__class__.__name__ for s in still]))

    # 真实点击「穿透模式」按钮 → 退出绘图模式
    mode = tb.icon_buttons["mode"]
    c = mode.mapToGlobal(mode.rect().center())
    click_logical(c.x(), c.y())
    pump(800)
    check("real click on mode button leaves drawing mode", not cvs.is_drawing_mode,
          f"is_drawing_mode={cvs.is_drawing_mode}")

    # ---- 3. LOGO 真实点击折叠/展开 ----
    c = logo.mapToGlobal(logo.rect().center())
    print("logo click at", c.x(), c.y(), "dragging-before", logo._dragging, "visible", tb.isVisible())
    click_logical(c.x(), c.y(), settle_ms=150)
    pump(600)
    print("after collapse click: tb.visible", tb.isVisible(), "dragging", logo._dragging, "logo", geom(logo))
    check("logo click collapses toolbar", not tb.isVisible(),
          f"visible={tb.isVisible()} dragging={logo._dragging} pos={geom(logo)}")
    c = logo.mapToGlobal(logo.rect().center())
    click_logical(c.x(), c.y(), settle_ms=150)
    pump(800)
    print("after expand click: tb.visible", tb.isVisible(), "dragging", logo._dragging)
    check("logo click expands toolbar", tb.isVisible(),
          f"visible={tb.isVisible()} dragging={logo._dragging}")
    tg, lg = tb.frameGeometry(), logo.frameGeometry()
    check("after expand: toolbar below logo & same width",
          tg.x() == lg.x() and abs(tg.y() - (lg.bottom() + 1)) <= 4 and tg.width() == lg.width(),
          f"logo {lg} toolbar {tg}")
    pnl.set_drawing_mode(True)
    pump(1000)
    zi = zorder_index([int(tb.winId()), int(cvs.winId())])
    check("after expand + drawing: toolbar above canvas",
          zi[int(tb.winId())] is not None and zi[int(cvs.winId())] is not None
          and zi[int(tb.winId())] < zi[int(cvs.winId())], str(zi))
    eraser = tb.icon_buttons["eraser"]
    c = eraser.mapToGlobal(eraser.rect().center())
    click_logical(c.x(), c.y())
    pump(600)
    check("real click on eraser activates eraser", pnl.btn_eraser.objectName() == "ActiveTool",
          pnl.btn_eraser.objectName())
    pnl.show_only_sub(None)
    pnl.set_drawing_mode(False)
    pump(400)

    # ---- 4. F12 队列信号进后台 → 恢复 ----
    n_before = len(QT_MESSAGES)
    pnl.background_requested.emit()
    pump(800)
    lc = pnl.lifecycle
    check("F12: hidden state", lc.state == "hidden", lc.state)
    vis = [n for n, w in (("panel", pnl), ("toolbar", tb), ("logo", logo), ("canvas", cvs)) if w.isVisible()]
    check("F12: all windows hidden", not vis, "still visible: " + str(vis) + "\n" + own_windows_dump())
    lbl = lc._menu_labels.get(lc.action_toggle_ui)
    check("F12: tray widget label says show", lbl is not None and lbl.text() == main.tr("show_main_ui"),
          lbl.text() if lbl else "no label")
    lc.restore_from_background()
    pump(1200)
    check("restore: showing state", lc.state == "showing", lc.state)
    check("restore: canvas + logo + toolbar visible", cvs.isVisible() and logo.isVisible() and tb.isVisible())
    check("restore: tray widget label says hide", lbl is not None and lbl.text() == main.tr("hide_main_ui"),
          lbl.text() if lbl else "no label")
    tg, lg = tb.frameGeometry(), logo.frameGeometry()
    check("restore: geometry intact", tg.width() == lg.width() and avail.contains(tg), f"logo {lg} toolbar {tg}")
    pnl.set_drawing_mode(True)
    pump(1000)
    zi = zorder_index([int(tb.winId()), int(logo.winId()), int(cvs.winId())])
    check("restore + drawing: toolbar/logo above canvas",
          all(v is not None for v in zi.values()) and zi[int(tb.winId())] < zi[int(cvs.winId())]
          and zi[int(logo.winId())] < zi[int(cvs.winId())], str(zi))
    pnl.set_drawing_mode(False)
    pump(400)
    kt = [m for m in QT_MESSAGES[n_before:] if "killTimer" in m or "startTimer" in m]
    check("F12 path: no cross-thread timer warnings", not kt, str(kt))

    # ---- 5. 横版 ----
    pnl.set_orientation("landscape")
    pump(800)
    tg, lg = tb.frameGeometry(), logo.frameGeometry()
    print("landscape toolbar", geom(tb), "logo", geom(logo))
    check("landscape: toolbar inside available screen", avail.contains(tg), str(tg))
    check("landscape: logo height == toolbar height", lg.height() == tg.height(),
          f"logo {lg.height()} toolbar {tg.height()}")
    check("landscape: toolbar right of logo", tg.y() == lg.y() and abs(tg.x() - (lg.right() + 1)) <= 4,
          f"logo {lg} toolbar {tg}")
    grab_around(OUT / "03_landscape.png", tb, logo)
    pnl.set_orientation("portrait")
    pump(800)
    tg, lg = tb.frameGeometry(), logo.frameGeometry()
    check("back to portrait: same width & inside screen", lg.width() == tg.width() and avail.contains(tg),
          f"logo {lg} toolbar {tg}")

    # ---- 6. 白板模式：控制区显示后仍在屏幕内 ----
    pnl.toggle_whiteboard()
    pump(1000)
    tg, lg = tb.frameGeometry(), logo.frameGeometry()
    print("whiteboard toolbar", geom(tb), "wb visible", tb.icon_wb_box.isVisible(), "cols", tb._wb_columns,
          "btn h", tb._button_height)
    check("whiteboard: wb box visible", tb.icon_wb_box.isVisible())
    check("whiteboard: toolbar inside available screen", avail.contains(tg), str(tg))
    check("whiteboard: logo width == toolbar width", lg.width() == tg.width(), f"{lg.width()} vs {tg.width()}")
    grab_around(OUT / "04_whiteboard.png", tb, logo)
    pnl.toggle_whiteboard()
    pump(800)
    tg = tb.frameGeometry()
    check("leave whiteboard: wb box hidden and toolbar shrinks back",
          not tb.icon_wb_box.isVisible() and tg.height() < 700, str(tg))

    # ---- 7. LOGO 拖到屏幕底部：工具栏翻到上面 ----
    logo.move(logo.x(), avail.bottom() - logo.height() - 10)
    pnl._on_logo_dragged(logo.pos())
    pump(500)
    tg, lg = tb.frameGeometry(), logo.frameGeometry()
    check("logo near bottom: toolbar flips above and stays on screen",
          avail.contains(tg) and tg.bottom() < lg.top(), f"logo {lg} toolbar {tg}")
    grab_around(OUT / "05_flip.png", tb, logo)
    logo.move(20, 20)
    pnl._on_logo_dragged(logo.pos())
    pump(300)


def main_():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    pnl = main.ControlPanel()
    cvs = main.DrawingCanvas(pnl)
    pnl.canvas = cvs
    pnl.apply_theme()
    pnl.load_settings()
    pnl.update_whiteboard_ui()
    pnl.update_history_ui()
    pnl.show()
    if not pnl.restore_position():
        pnl.move(0, 300)
    pnl.bind_topmost_stack()
    QTimer.singleShot(0, pnl.bind_topmost_stack)
    QTimer.singleShot(200, pnl.bind_topmost_stack)

    rc = [0]

    def go():
        try:
            run(app, pnl, cvs)
        except Exception:
            traceback.print_exc()
            RESULTS.append(("harness exception", False, traceback.format_exc().splitlines()[-1]))
        finally:
            fails = [r for r in RESULTS if not r[1]]
            print("\n==== SUMMARY: %d checks, %d failed ====" % (len(RESULTS), len(fails)))
            for name, ok, detail in fails:
                print("  FAIL", name, "--", detail)
            interesting = [m for m in QT_MESSAGES if any(k in m for k in
                           ("killTimer", "requestActivate", "UpdateLayeredWindow", "QObject", "QWidget"))]
            print("Qt messages of interest (%d):" % len(interesting))
            for m in interesting:
                print("  ", m)
            rc[0] = 1 if fails else 0
            try:
                pnl.listener.stop()
            except Exception:
                pass
            for t in ("timer", "autosave_timer"):
                try:
                    getattr(pnl, t).stop()
                except Exception:
                    pass
            try:
                pnl.lifecycle.tray_icon.hide()
            except Exception:
                pass
            app.quit()

    QTimer.singleShot(1500, go)
    app.exec()
    shutil.rmtree(_tmp, ignore_errors=True)
    return rc[0]


if __name__ == "__main__":
    sys.exit(main_())
