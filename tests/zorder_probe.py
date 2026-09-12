# SPDX-License-Identifier: GPL-3.0-or-later
"""Real-screen z-order probe for the topmost heartbeat.

Runs the real ControlPanel + DrawingCanvas on the real desktop while a background
thread walks the Win32 z-order every millisecond and logs every change in the
ordering of visible windows above (and including) the canvas. This catches the
transient states a screenshot never would: a heartbeat that briefly lifts the
opaque whiteboard canvas over the panel, a foreign floater winning the band, or
ClassIsland slipping below us.

Manual tool, kept out of `unittest discover`. It shows real windows.

Usage:  python tests/zorder_probe.py [--seconds 6] [--no-whiteboard]
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.pop("QT_QPA_PLATFORM", None)

u32 = ctypes.windll.user32
dwm = ctypes.windll.dwmapi
u32.GetTopWindow.restype = ctypes.c_void_p
u32.GetTopWindow.argtypes = [ctypes.c_void_p]
u32.GetWindow.restype = ctypes.c_void_p
u32.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
u32.IsWindowVisible.argtypes = [ctypes.c_void_p]
u32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
u32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
u32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.DWORD)]
u32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.RECT)]
u32.GetWindowLongPtrW.restype = ctypes.c_void_p
u32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
GW_HWNDNEXT = 2
GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x8
DWMWA_CLOAKED = 14


def cloaked(hwnd):
    val = wt.DWORD(0)
    dwm.DwmGetWindowAttribute(ctypes.c_void_p(hwnd), DWMWA_CLOAKED, ctypes.byref(val), 4)
    return val.value != 0


def window_pid(hwnd):
    pid = wt.DWORD(0)
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def describe(hwnd):
    buf = ctypes.create_unicode_buffer(128)
    u32.GetWindowTextW(hwnd, buf, 128)
    title = buf.value
    u32.GetClassNameW(hwnd, buf, 128)
    cls = buf.value
    pid = wt.DWORD(0)
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    r = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    ex = int(u32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE) or 0)
    return f"{hwnd:#x} pid={pid.value} {'T' if ex & WS_EX_TOPMOST else '-'} [{cls[:24]}] '{title[:24]}' {r.left},{r.top}-{r.right},{r.bottom}"


def visible_zorder(stop_at):
    """Visible, uncloaked, non-empty windows from the very top down to stop_at inclusive."""
    out = []
    hwnd = u32.GetTopWindow(None)
    while hwnd:
        if u32.IsWindowVisible(hwnd) and not cloaked(hwnd):
            r = wt.RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(r))
            if r.right > r.left and r.bottom > r.top:
                out.append(hwnd)
        if hwnd == stop_at:
            break
        hwnd = u32.GetWindow(hwnd, GW_HWNDNEXT)
    return out


class Poller(threading.Thread):
    def __init__(self, names):
        super().__init__(daemon=True)
        self.names = names            # hwnd -> label for our own windows
        self.seen = {}                # stranger hwnd -> (description, pid) at first sight
        self.events = []              # (t, tuple_of_hwnds)
        self.canvas = None
        self.stop = threading.Event()
        self.samples = 0
        self.t0 = time.perf_counter()
        self.shutdown_at = None       # relative time the app was told to quit

    def run(self):
        last = None
        t0 = self.t0
        while not self.stop.is_set():
            if self.canvas:
                order = tuple(visible_zorder(self.canvas))
                self.samples += 1
                if order != last:
                    self.events.append((time.perf_counter() - t0, order))
                    last = order
                    # Describe strangers while they still exist: transient windows are
                    # often gone (pid 0, no class) by the time the report is printed.
                    for hwnd in order:
                        if hwnd not in self.names and hwnd not in self.seen:
                            self.seen[hwnd] = (describe(hwnd), window_pid(hwnd))
            time.sleep(0.0005)

    def label(self, hwnd):
        return self.names.get(hwnd) or (self.seen.get(hwnd) or (describe(hwnd),))[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=6.0, help="dwell per phase")
    parser.add_argument("--no-whiteboard", action="store_true")
    args = parser.parse_args()

    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    import main

    app = QApplication(sys.argv[:1])
    pnl = main.ControlPanel()
    cvs = main.DrawingCanvas(pnl)
    pnl.canvas = cvs
    pnl.apply_theme()
    pnl.update_whiteboard_ui()
    pnl.update_history_ui()
    pnl.show()
    screen = app.primaryScreen().geometry()
    pnl.move(0, max(8, (screen.height() - pnl.frameGeometry().height()) // 2))
    pnl.bind_topmost_stack()

    names = {}

    def register():
        names[int(cvs.winId())] = "CANVAS"
        names[int(pnl.winId())] = "PANEL"
        for attr in ("menu_panel", "select_panel", "mini_timer", "thumbnail_panel",
                     "calc_panel", "roster_panel", "text_panel", "settings_panel"):
            w = getattr(pnl, attr, None)
            if w is not None:
                names[int(w.winId())] = attr.upper()

    poller = Poller(names)
    poller.start()
    phases = []
    rewrites = []                          # (t, phase) for every real SetWindowPos batch

    original_apply = main.apply_topmost_order

    def counting_apply(chain, ceiling):
        rewrites.append((time.perf_counter(), phases[-1][1] if phases else "startup"))
        return original_apply(chain, ceiling)

    main.apply_topmost_order = counting_apply

    def mark(label):
        register()
        poller.canvas = int(cvs.winId())
        phases.append((time.perf_counter(), label))
        print(f"--- phase: {label}", flush=True)

    def quit_app():
        poller.shutdown_at = time.perf_counter() - poller.t0
        app.quit()

    dwell = int(args.seconds * 1000)
    QTimer.singleShot(300, lambda: mark("annotate"))
    if not args.no_whiteboard:
        QTimer.singleShot(300 + dwell, lambda: (pnl.toggle_whiteboard(), mark("whiteboard")))
        QTimer.singleShot(300 + 2 * dwell, lambda: (pnl.toggle_whiteboard(), mark("annotate-again")))
        QTimer.singleShot(300 + 3 * dwell, quit_app)
    else:
        QTimer.singleShot(300 + dwell, quit_app)
    app.exec()
    poller.stop.set()
    poller.join(1)

    print(f"\n{poller.samples} samples, {len(poller.events)} distinct orderings\n")
    for t, order in poller.events:
        print(f"t={t:8.3f}s" + ("  (shutting down)" if poller.shutdown_at and t >= poller.shutdown_at else ""))
        for hwnd in order:
            print("   ", poller.label(hwnd))

    # --- verdicts -------------------------------------------------------------
    # Use the handles recorded while the app ran: after exec() returns, winId() may
    # hand back a freshly created native window that never appears in the samples.
    # States sampled after quit() are teardown (panel destroyed before canvas) and
    # say nothing about the heartbeat, so they are left out of every verdict.
    canvas_hwnd = poller.canvas
    panel_hwnd = next(h for h, label in names.items() if label == "PANEL")
    own_pid = os.getpid()
    live_events = [(t, order) for t, order in poller.events
                   if poller.shutdown_at is None or t < poller.shutdown_at]

    def is_island(hwnd):
        pid = poller.seen.get(hwnd, (None, None))[1]
        if pid is None:
            return main.is_privileged_window(hwnd)
        return main.process_image_name(pid).startswith(main.PRIVILEGED_PROCESS_PREFIXES)

    def is_ours(hwnd):
        return hwnd in names or poller.seen.get(hwnd, (None, None))[1] == own_pid

    bad_panel = [t for t, order in live_events
                 if order and order[-1] == canvas_hwnd and panel_hwnd not in order]
    # ClassIsland must never sit below the canvas or the main panel.
    bad_island = []
    island_seen = False
    for t, order in live_events:
        if canvas_hwnd not in order:
            continue                      # app already shutting down; nothing of ours left
        islands = [h for h in order if is_island(h)]
        if islands:
            island_seen = True
        lowest_ours = max((order.index(h) for h in (panel_hwnd, canvas_hwnd) if h in order), default=-1)
        if any(order.index(h) > lowest_ours for h in islands):
            bad_island.append(t)
    # Foreign windows between ClassIsland's lowest window and the canvas must not persist:
    # count states where one is there, and how long the *last* such state lasted.
    foreign_states = []
    for i, (t, order) in enumerate(live_events):
        islands = [h for h in order if is_island(h)]
        start = order.index(islands[-1]) + 1 if islands else 0
        zone = order[start:]
        if canvas_hwnd not in zone:
            continue
        above = zone[:zone.index(canvas_hwnd)]
        foreign = [h for h in above if not is_ours(h)]
        if foreign:
            end = live_events[i + 1][0] if i + 1 < len(live_events) else (poller.shutdown_at or t)
            foreign_states.append((t, end - t, [poller.label(h) for h in foreign]))
    print(f"\n{len(live_events)} live states ({len(poller.events) - len(live_events)} teardown states ignored)")
    print(f"states with PANEL missing above CANVAS: {len(bad_panel)}")
    print(f"ClassIsland seen: {island_seen}; states with ClassIsland below panel/canvas: {len(bad_island)}")
    print(f"states with a foreign window between ceiling and canvas: {len(foreign_states)}")
    for t, dur, who in foreign_states:
        print(f"    t={t:8.3f}s lasted {dur * 1000:7.1f}ms  {who}")
    per_phase = {}
    for _, label in rewrites:
        per_phase[label] = per_phase.get(label, 0) + 1
    print(f"z-order rewrites by phase: {per_phase or 'none'}")


if __name__ == "__main__":
    main()
