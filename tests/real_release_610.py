# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in Windows 6.1.0 native-input acceptance. Never run in automated pytest.

Usage: python tests/real_release_610.py D:\\private\\.ccgui\\release-610
The named directory must contain a .ccgui component and is exclusively private
widget/evidence output. This program occupies the desktop and pointer.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class NativeMouse:
    """Only press above this process's HWND; release a captured press on failure."""

    LEFTDOWN = 0x0002
    LEFTUP = 0x0004

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    def __init__(self, app):
        from PyQt6.QtGui import QCursor
        self.app = app
        self.cursor = QCursor
        self.user32 = ctypes.windll.user32
        self.user32.GetCursorPos.argtypes = [ctypes.POINTER(self.POINT)]
        self.user32.GetCursorPos.restype = wintypes.BOOL
        self.user32.WindowFromPoint.argtypes = [self.POINT]
        self.user32.WindowFromPoint.restype = wintypes.HWND
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.user32.GetCapture.restype = wintypes.HWND
        self.user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                            wintypes.DWORD, ctypes.c_size_t]
        self.start = QCursor.pos()
        self.down = False
        self.press_point = None

    def pump(self, ms=50):
        from PyQt6.QtWidgets import QApplication
        deadline = time.monotonic() + ms / 1000
        while time.monotonic() < deadline:
            QApplication.processEvents()
            time.sleep(.008)

    def owner(self, hwnd):
        if not hwnd:
            return False
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == os.getpid()

    def point_hwnd(self):
        point = self.POINT()
        if not self.user32.GetCursorPos(ctypes.byref(point)):
            raise RuntimeError("GetCursorPos failed")
        return self.user32.WindowFromPoint(point)

    def move(self, point):
        self.cursor.setPos(point)
        self.pump(45)
        if (self.cursor.pos() - point).manhattanLength() > 3:
            raise RuntimeError(f"Cursor failed to reach widget: {point} / {self.cursor.pos()}")

    def down_at(self, point):
        self.move(point)
        hwnd = self.point_hwnd()  # Windows physical cursor position, not guessed DPI coordinates.
        if not self.owner(hwnd) and not (self.down and self.owner(self.user32.GetCapture())):
            raise RuntimeError(f"Refusing mouse DOWN above foreign HWND {hwnd!r} at {point}")
        self.user32.mouse_event(self.LEFTDOWN, 0, 0, 0, 0)
        self.down = True
        self.press_point = point
        self.pump(55)

    def up(self):
        if self.down:
            # If capture was lost over a foreign window, move back to the owned press.
            if not self.owner(self.user32.GetCapture()) and not self.owner(self.point_hwnd()):
                self.move(self.press_point)
            self.user32.mouse_event(self.LEFTUP, 0, 0, 0, 0)
            self.down = False
            self.pump(90)

    def click_point(self, point):
        self.down_at(point)
        try:
            self.up()
        finally:
            self.up()

    def click(self, widget):
        from PyQt6.QtCore import QRect
        from PyQt6.QtWidgets import QCheckBox, QStyle, QStyleOptionButton
        if not widget.isVisible() or not widget.isEnabled():
            raise RuntimeError(f"Not clickable: {widget!r}")
        if isinstance(widget, QCheckBox):
            option = QStyleOptionButton()
            widget.initStyleOption(option)
            rect = widget.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, widget)
            point = widget.mapToGlobal(rect.center())
        else:
            rect = QRect(widget.mapToGlobal(widget.rect().topLeft()), widget.rect().size())
            visible = rect.intersected(widget.window().frameGeometry())
            if visible.isEmpty():
                raise RuntimeError(f"Widget outside its window: {widget!r}")
            point = visible.center()
        self.click_point(point)

    def drag(self, source, destination, hold_ms=0):
        # Windows OLE's native drag loop can starve Qt timers. Drive ONLY Win32
        # pointer input in a bounded worker; all Qt reads/painting stay here.
        import threading
        self.move(destination)
        end = self.POINT(); self.user32.GetCursorPos(ctypes.byref(end))
        self.down_at(source)
        start = self.POINT(); self.user32.GetCursorPos(ctypes.byref(start))
        done = threading.Event()
        errors = []
        def input_sequence():
            try:
                for index in range(1, 16):
                    x = start.x + (end.x - start.x) * index // 15
                    y = start.y + (end.y - start.y) * index // 15
                    if not self.user32.SetCursorPos(x, y):
                        raise RuntimeError("Native drag cursor move failed")
                    time.sleep(.045)
                # A real steady edge hold lets Qt accelerate its autoscroll;
                # artificial cursor jitter repeatedly resets that acceleration.
                time.sleep(hold_ms / 1000)
            except Exception as exc:
                errors.append(exc)
            finally:
                if not self.owner(self.point_hwnd()):
                    self.user32.SetCursorPos(start.x, start.y)
                self.user32.mouse_event(self.LEFTUP, 0, 0, 0, 0)
                self.down = False
                done.set()
        worker = threading.Thread(target=input_sequence, name="bounded-native-test-drag")
        worker.start()
        try:
            while not done.is_set():
                self.pump(25)
        finally:
            worker.join(timeout=5)
            self.up()
        if errors: raise errors[0]
        self.pump(180)

    def restore(self):
        try:
            self.up()
        finally:
            self.cursor.setPos(self.start)


class Harness:
    def __init__(self, app, output):
        self.app, self.output = app, output
        self.mouse = NativeMouse(app)
        self.checks = []

    def check(self, name, condition, detail=""):
        row = {"name": name, "passed": bool(condition), "detail": str(detail)}
        self.checks.append(row)
        print(("PASS " if condition else "FAIL ") + name + (f" -- {detail}" if detail else ""), flush=True)
        return bool(condition)

    def run_check(self, name, fn):
        try:
            fn()
        except Exception as exc:
            self.check(name, False, f"{type(exc).__name__}: {exc}")
            traceback.print_exc()
            # A failed native step must not leave a modal dialog obstructing later checks.
            from PyQt6.QtWidgets import QApplication, QDialog
            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, QDialog) and widget.isVisible():
                    widget.reject()
            self.mouse.up()

    def capture(self, name, widget):
        # QWidget.grab, never QScreen.grabWindow or desktop pixels.
        self.mouse.pump(100)
        image = widget.grab()
        if image.isNull() or not image.save(str(self.output / name), "PNG"):
            raise RuntimeError(f"Widget capture failed: {name}")

    def scroll_to(self, panel, widget):
        self.mouse.pump(250)
        viewport = panel.settings_scroll.viewport()
        bar = panel.settings_scroll.verticalScrollBar()
        for _ in range(5):
            center = widget.mapTo(viewport, widget.rect().center())
            bar.setValue(bar.value() + center.y() - viewport.rect().center().y())
            self.mouse.pump(150)
            point = widget.mapToGlobal(widget.rect().center())
            from PyQt6.QtWidgets import QApplication
            hit = QApplication.widgetAt(point)
            if viewport.rect().contains(widget.mapTo(viewport, widget.rect().center())) and (hit is widget or widget.isAncestorOf(hit) if hit else False):
                return
        raise RuntimeError("Preference control is not actually hit-testable in its scroll viewport")

    def combo(self, combo, data):
        """Native click to open and choose a Qt popup row (not setCurrentIndex)."""
        index = combo.findData(data)
        if index < 0:
            raise RuntimeError(f"Missing combo choice {data!r}")
        self.mouse.click(combo)
        view = combo.view()
        deadline = time.monotonic() + 1.5
        while not view.isVisible() and time.monotonic() < deadline:
            self.mouse.pump(30)
        if not view.isVisible():
            raise RuntimeError("Native combo popup did not become visible")
        self.mouse.pump(300)  # finish Windows popup rollout before aiming at a row
        rect = view.visualRect(view.model().index(index, 0))
        if rect.isEmpty():
            view.scrollTo(view.model().index(index, 0))
            self.mouse.pump(60)
            rect = view.visualRect(view.model().index(index, 0))
        self.mouse.click_point(view.viewport().mapToGlobal(rect.center()))
        self.mouse.pump(80)
        self.check(f"native combo {data}", combo.currentData() == data)

    def modal(self, dialog_type, action, inspect, button):
        """Poll for a synchronously exec()-ed dialog; native-click its response."""
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication, QDialog
        seen = []
        active = [True]
        deadline = time.monotonic() + 30

        def respond():
            if not active[0]:
                return
            dialogs = [w for w in QApplication.topLevelWidgets()
                       if isinstance(w, dialog_type) and w.isVisible()]
            if not dialogs:
                if time.monotonic() < deadline:
                    QTimer.singleShot(80, respond)
                    return
                self.check(f"{dialog_type.__name__} native response", False, "dialog did not appear in 30s")
                for widget in QApplication.topLevelWidgets():
                    if isinstance(widget, QDialog) and widget.isVisible():
                        widget.reject()
                return
            try:
                if len(dialogs) != 1:
                    raise RuntimeError(f"Expected one {dialog_type.__name__}, found {len(dialogs)}")
                dialog = dialogs[0]
                inspect(dialog)
                self.mouse.click(button(dialog))
                seen.append(True)
            except Exception as exc:
                self.check(f"{dialog_type.__name__} native response", False, repr(exc))
                for dialog in dialogs:
                    dialog.reject()

        QTimer.singleShot(80, respond)
        try:
            action()
        finally:
            active[0] = False
        self.check(f"{dialog_type.__name__} native response", bool(seen))


def text_autosave(path, label, main):
    from persistence import atomic_write_autosave, make_project_data, AUTOSAVE_KIND
    page = {"segments": [], "shapes": [], "texts": [{
        "id": label, "text": label, "pos": [80, 60], "color": "#ff0000",
        "width": 1, "size": 24, "scale": 1, "rotation": 0}]}
    data = make_project_data(pages=[page], current_page=0, whiteboard_mode=False,
                             board_style="WHITE", app_version=main.APP_VERSION, kind=AUTOSAVE_KIND)
    atomic_write_autosave(str(path), data)


def exercise(h, main, panel, canvas, private):
    from PyQt6.QtCore import Qt, QPoint
    from PyQt6.QtGui import QColor, QPen, QPixmap
    from PyQt6.QtWidgets import QApplication, QDialogButtonBox, QInputDialog, QMessageBox
    from recovery_dialog import RecoveryDialog
    from export_pipeline import export_document

    h.check("release version 6.1.0", main.APP_VERSION == "v6.1.0")
    canvas.enter_whiteboard()
    canvas.all_segments.append({"line": main.QLine(1, 2, 30, 40), "pen": QPen(), "id": "first"})
    canvas.mark_content_changed()
    canvas.new_page()
    canvas.all_segments.append({"line": main.QLine(2, 3, 40, 50), "pen": QPen(), "id": "second"})
    canvas.mark_content_changed()
    panel.update_whiteboard_ui()
    panel.toggle_thumbnail_panel()
    h.mouse.pump(150)
    h.check("two synthetic starter pages", panel.thumbnail_list.count() == 2)
    h.capture("pages-before.png", panel.thumbnail_panel)

    def rename():
        def inspect(dialog):
            dialog.findChild(main.QLineEdit).setText("Native 6.1.0")
        h.modal(QInputDialog, lambda: h.mouse.click(panel.btn_rename_page), inspect,
                lambda dialog: dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok))
        h.check("native rename persists", canvas._page_name == "Native 6.1.0")
    h.run_check("rename page", rename)

    def copy():
        before = len(canvas.pages)
        h.mouse.click(panel.btn_copy_page)
        h.check("native copy creates independent page", len(canvas.pages) == before + 1
                and len({p["page_id"] for p in canvas.document_pages()}) == before + 1)
    h.run_check("copy page", copy)

    def reorder():
        listing = panel.thumbnail_list
        panel.refresh_page_thumbnails(force=True)
        listing.setCurrentRow(0)  # Fixture selection only; drag is native.
        listing.doItemsLayout()
        a = listing.viewport().mapToGlobal(listing.visualItemRect(listing.item(0)).center())
        # The compact rail deliberately shows roughly one page at a time.
        # Hold a genuine native drag at the bottom edge to exercise autoscroll.
        visible = listing.viewport().rect()
        b = listing.viewport().mapToGlobal(QPoint(visible.center().x(), visible.bottom() - 4))
        first = canvas.document_pages()[0]["page_id"]
        before_scroll = listing.verticalScrollBar().value()
        h.mouse.drag(a, b, hold_ms=2200)
        h.check("native drag autoscroll advances", listing.verticalScrollBar().value() > before_scroll)
        h.check("native page drag changes order", canvas.document_pages()[-1]["page_id"] == first,
                f"scroll={listing.verticalScrollBar().value()}/{listing.verticalScrollBar().maximum()}")
        h.capture("pages-reordered.png", panel.thumbnail_panel)
    h.run_check("page reorder", reorder)
    panel.close_thumbnail_panel()

    def preferences():
        panel.open_settings_panel()
        ui = panel.document_preferences
        h.scroll_to(panel, ui.copy_combo)
        h.combo(ui.copy_combo, "last")
        h.check("copy placement persisted", panel.page_copy_placement == "last")
        h.scroll_to(panel, ui.interval_combo)
        h.combo(ui.interval_combo, 120)
        h.check("autosave preset and timer", panel.autosave_interval_seconds == 120
                and panel.autosave_timer.interval() == 120000)
        h.scroll_to(panel, ui.interval_combo)
        h.combo(ui.interval_combo, -1)
        h.check("custom interval visible", ui.interval_custom.isVisible())
        h.scroll_to(panel, ui.interval_custom)
        # Keyboard editing is setup; clicking the native spinbox arrow exercises the change.
        ui.interval_custom.setValue(42)
        from PyQt6.QtWidgets import QStyle, QStyleOptionSpinBox
        spin = QStyleOptionSpinBox()
        ui.interval_custom.initStyleOption(spin)
        up = ui.interval_custom.style().subControlRect(
            QStyle.ComplexControl.CC_SpinBox, spin,
            QStyle.SubControl.SC_SpinBoxUp, ui.interval_custom)
        h.mouse.click_point(ui.interval_custom.mapToGlobal(up.center()))
        h.check("custom autosave changed by native arrow", panel.autosave_interval_seconds == 43
                and panel.autosave_timer.interval() == 43000)
        h.scroll_to(panel, ui.volume_slider)
        ui.volume_slider.setValue(0)
        from PyQt6.QtWidgets import QStyle, QStyleOptionSlider
        option = QStyleOptionSlider()
        ui.volume_slider.initStyleOption(option)
        groove = ui.volume_slider.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderGroove, ui.volume_slider)
        handle = ui.volume_slider.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, option, QStyle.SubControl.SC_SliderHandle, ui.volume_slider)
        h.mouse.drag(ui.volume_slider.mapToGlobal(handle.center()), ui.volume_slider.mapToGlobal(
            QPoint(groove.left() + groove.width() * 3 // 4, groove.center().y())))
        h.check("native volume slider drag (no playback)", 50 <= panel.timer_alarm_volume <= 95
                and str(panel.timer_alarm_volume) in ui.volume_label.text())
        h.capture("preferences.png", panel.settings_panel)
        panel.autosave_timer.stop()  # Deterministic recovery fixtures, no background save.
        panel.settings_panel.hide()
        # Copy placement applied to actual button, not only the combo model.
        before = len(canvas.pages)
        panel.toggle_thumbnail_panel()
        h.mouse.pump(100)
        h.mouse.click(panel.btn_copy_page)
        h.check("last placement drives native copy", len(canvas.pages) == before + 1
                and canvas.current_page == len(canvas.pages) - 1)
        panel.close_thumbnail_panel()
    h.run_check("document preferences", preferences)

    def recovery():
        latest = private / "autosave" / "autosave_20261006_130000.json.gz"
        older = private / "autosave" / "autosave_20261006_120000.json.gz"
        text_autosave(latest, "latest", main)
        text_autosave(older, "older", main)
        before = canvas.document_signature()
        def inspect(dialog):
            h.check("recovery starts collapsed with bounded preview",
                    not dialog.advanced_options.isVisible() and dialog.selected_path == str(latest)
                    and dialog.preview.pixmap() is not None
                    and dialog.preview.pixmap().width() <= 360)
            h.capture("recovery-collapsed.png", dialog)
            h.mouse.click(dialog.advanced_toggle)
            h.check("native recovery expand", dialog.advanced_options.isVisible())
            item = dialog.version_list.item(1)
            rect = dialog.version_list.visualItemRect(item)
            h.mouse.click_point(dialog.version_list.viewport().mapToGlobal(rect.center()))
            h.check("native older selection previews only", dialog.selected_path == str(older)
                    and dialog.preview.pixmap() is not None
                    and canvas.document_signature() == before)
            h.capture("recovery-expanded.png", dialog)
        h.modal(RecoveryDialog, panel.offer_autosave_restore, inspect,
                lambda dialog: dialog.not_now_button)
        h.check("recovery decline leaves document intact", canvas.document_signature() == before
                and latest.exists() and older.exists())
    h.run_check("recovery preview", recovery)

    def unsaved_open():
        fixture = private / "fixture.msd"
        if not panel.save_project(str(fixture)):
            raise RuntimeError("Could not write isolated project fixture")
        # Make content dirty without changing the real project file.
        canvas.new_page()
        panel.update_whiteboard_ui()
        before = canvas.document_signature()
        fixture_pages = len(canvas.pages) - 1
        def invoke():
            with patch.object(main.QFileDialog, "getOpenFileName", return_value=(str(fixture), "")):
                h.mouse.click(panel.btn_open_project)
        panel.show_only_sub(panel.file_sub)
        def inspect(box):
            h.check("unsaved open modal defaults Cancel", box.defaultButton() ==
                    box.button(QMessageBox.StandardButton.Cancel)
                    and box.escapeButton() == box.button(QMessageBox.StandardButton.Cancel))
            h.capture("unsaved-cancel.png", box)
        h.modal(QMessageBox, invoke, inspect,
                lambda box: box.button(QMessageBox.StandardButton.Cancel))
        h.check("native Cancel retains dirty pages", canvas.document_signature() == before
                and panel.has_unsaved_changes())
        panel.show_only_sub(panel.file_sub)
        h.modal(QMessageBox, invoke, lambda box: None,
                lambda box: box.button(QMessageBox.StandardButton.Discard))
        h.check("native Discard loads fixture", canvas.document_signature() != before
                and len(canvas.pages) == fixture_pages and not panel.has_unsaved_changes()
                and panel.project_path == str(fixture))
    h.run_check("unsaved open", unsaved_open)

    def export_flow():
        panel.show_only_sub(panel.file_sub)
        def dismiss(box):
            h.check("export success information modal", box.icon() == QMessageBox.Icon.Information)
            h.capture("export-result.png", box)
        # Success notification is a native QMessageBox; no desktop capture.
        h.modal(QMessageBox, lambda: h.mouse.click(panel.btn_export_pdf), dismiss,
                lambda box: box.button(QMessageBox.StandardButton.Ok))
        outputs = list((private / "exports").glob("*.pdf"))
        h.check("native PDF export succeeds", len(outputs) == 1 and outputs[0].stat().st_size > 0)
        panel.show_only_sub(panel.file_sub)
        original = canvas.render_page_pixmap
        calls = [0]
        def faulty(page, size, *args, **kwargs):
            calls[0] += 1
            if calls[0] == 2:
                raise RuntimeError("injected page render failure")
            return original(page, size, *args, **kwargs)
        with patch.object(canvas, "render_page_pixmap", side_effect=faulty):
            def inspect(box):
                h.check("incomplete export is warning modal", box.icon() == QMessageBox.Icon.Warning
                        and bool(box.detailedText()) and "2" in box.informativeText())
                h.capture("export-incomplete.png", box)
            h.modal(QMessageBox, lambda: h.mouse.click(panel.btn_export_pdf), inspect,
                    lambda box: box.button(QMessageBox.StandardButton.Ok))
        h.check("injected render failure reached second page", calls[0] >= 2)

        # A separate progress-dialog cancellation must report cancellation, not success.
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QProgressDialog, QPushButton
        panel.show_only_sub(panel.file_sub)
        cancelled = []
        def cancel_progress():
            dialogs = [w for w in QApplication.topLevelWidgets()
                       if isinstance(w, QProgressDialog) and w.isVisible()]
            if len(dialogs) != 1:
                h.check("export cancellation progress visible", False, len(dialogs))
                return
            h.mouse.click(dialogs[0].findChild(QPushButton))
            cancelled.append(dialogs[0].wasCanceled())
        def queue_cancel(page, size, *args, **kwargs):
            image = original(page, size, *args, **kwargs)
            if not cancelled:
                QTimer.singleShot(0, cancel_progress)
            return image
        with patch.object(canvas, "render_page_pixmap", side_effect=queue_cancel):
            def inspect_cancel(box):
                h.check("cancelled export uses warning modal", box.icon() == QMessageBox.Icon.Warning
                        and bool(box.informativeText()))
                h.capture("export-cancelled.png", box)
            h.modal(QMessageBox, lambda: h.mouse.click(panel.btn_export_pdf), inspect_cancel,
                    lambda box: box.button(QMessageBox.StandardButton.Ok))
        h.check("export Cancel was native progress click", cancelled == [True])
    h.run_check("export success/incomplete/cancel", export_flow)

    def pdf_import():
        fixture = private / "two-colors.pdf"
        def render(color):
            pix = QPixmap(90, 60)
            pix.fill(QColor(color))
            return pix
        result = export_document("PDF", fixture, ["red", "blue"], lambda c, *_: render(c))
        if not result.success:
            raise RuntimeError(f"Could not create real PDF fixture: {result.failures}")
        before = len(canvas.pages)
        panel.show_only_sub(panel.file_sub)
        with patch.object(main.QFileDialog, "getOpenFileName", return_value=(str(fixture), "")):
            h.modal(QMessageBox, lambda: h.mouse.click(panel.btn_import_media), lambda box: None,
                    lambda box: box.button(QMessageBox.StandardButton.Ok))
        pages = canvas.document_pages()
        h.check("native PDF import creates independent pages", len(pages) == before + 2
                and len({p["page_id"] for p in pages[-2:]}) == 2
                and all(len(p["images"]) == 1 for p in pages[-2:]))
        h.capture("pdf-imported-canvas.png", canvas)
    h.run_check("PDF import", pdf_import)


def main_():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="private .ccgui evidence directory")
    parser.add_argument("--theme", choices=("dark", "light"), default="dark")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("real native acceptance requires Windows")
    if ".ccgui" not in args.output.resolve().parts:
        parser.error("output must be inside a private .ccgui directory")
    if os.environ.get("QT_QPA_PLATFORM") not in (None, "windows"):
        parser.error("unset QT_QPA_PLATFORM; native Windows platform is required")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ["MYSCREENDRAW_NO_KEYBOARD"] = "1"
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    import main
    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    h = Harness(app, output)
    panel = canvas = None
    status = [1]
    with tempfile.TemporaryDirectory(prefix="msd-610-native-") as directory:
        private = Path(directory)
        for folder in (private / "autosave", private / "exports"):
            folder.mkdir()
        # All production paths are redirected before any widgets or logging are made.
        for name, value in {
            "DATA_DIR": private, "CONFIG_FILE": private / "config.json",
            "ROSTER_FILE": private / "roster.json", "AUTOSAVE_DIR": private / "autosave",
            "EXPORT_DIR": private / "exports", "TELEMETRY_FILE": private / "events.jsonl",
            "LOG_FILE": private / "app.log",
        }.items():
            setattr(main, name, str(value))
        main.setup_logging()
        main.ControlPanel.check_for_updates = lambda self, *args, **kwargs: None
        try:
            panel = main.ControlPanel()
            canvas = main.DrawingCanvas(panel)
            panel.canvas = canvas
            panel.apply_theme()
            panel.load_settings()
            panel.theme_name = args.theme
            panel.theme = panel.THEMES[args.theme]
            panel.apply_theme()
            panel.update_whiteboard_ui()
            panel.update_history_ui()
            panel.show()
            canvas.show()
            panel.bind_topmost_stack()
            panel.autosave_timer.stop()
            # The outer loop makes QTimer modal callbacks and native Windows HWNDs live.
            def go():
                try:
                    h.mouse.pump(150)
                    exercise(h, main, panel, canvas, private)
                except Exception as exc:
                    h.check("harness exception", False, repr(exc))
                    traceback.print_exc()
                finally:
                    failed = [item for item in h.checks if not item["passed"]]
                    report = {"version": main.APP_VERSION, "checks": h.checks,
                              "passed": len(h.checks) - len(failed), "failed": len(failed)}
                    (output / "real-release-610.json").write_text(
                        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
                    print(f"REAL 6.1.0: {report['passed']}/{len(h.checks)} passed", flush=True)
                    status[0] = bool(failed)
                    h.mouse.restore()
                    panel.shutdown_autosave()
                    for name in ("listener", "timer", "autosave_timer", "update_check_timer",
                                 "_split_save_timer", "_thumbnail_live_timer", "_laser_fade",
                                 "_keyboard_watch", "_autosave_poll_timer"):
                        obj = getattr(panel, name, None)
                        if obj is not None:
                            try:
                                obj.stop()
                            except (AttributeError, RuntimeError):
                                pass
                    try:
                        panel.stop_update_worker()
                        if getattr(panel, "lifecycle", None) and panel.lifecycle.tray_icon:
                            panel.lifecycle.tray_icon.hide()
                    finally:
                        for widget in QApplication.topLevelWidgets():
                            widget.hide()  # Destroy only after the outer cleanup has drained workers.
                        app.quit()
            def deadline():
                h.check("four-minute native deadline", False, "Timed out")
                from PyQt6.QtWidgets import QDialog
                for widget in QApplication.topLevelWidgets():
                    if isinstance(widget, QDialog) and widget.isVisible():
                        widget.reject()
                app.quit()
            watchdog = QTimer()
            watchdog.setSingleShot(True)
            watchdog.timeout.connect(deadline)
            watchdog.start(240000)
            QTimer.singleShot(900, go)
            app.exec()
            watchdog.stop()
        except Exception as exc:
            h.check("native setup", False, f"{type(exc).__name__}: {exc}")
            traceback.print_exc()
        finally:
            h.mouse.restore()
            if panel is not None:
                panel.shutdown_autosave()
                for name in ("listener", "timer", "autosave_timer", "update_check_timer",
                             "_split_save_timer", "_thumbnail_live_timer", "_laser_fade",
                                 "_keyboard_watch", "_autosave_poll_timer"):
                    obj = getattr(panel, name, None)
                    if obj is not None:
                        try:
                            obj.stop()
                        except (AttributeError, RuntimeError):
                            pass
            if app is not None:
                sys.path.insert(0, str(ROOT / "tests"))
                from conftest import _dispose_offscreen_widgets
                _dispose_offscreen_widgets(app)
            # FileHandler must release the private log before TemporaryDirectory
            # attempts cleanup on Windows.
            for handler in list(main.LOGGER.handlers):
                handler.flush()
                handler.close()
                main.LOGGER.removeHandler(handler)
            if not (output / "real-release-610.json").exists():
                failures = [row for row in h.checks if not row["passed"]]
                (output / "real-release-610.json").write_text(json.dumps({
                    "version": main.APP_VERSION, "checks": h.checks,
                    "passed": len(h.checks) - len(failures), "failed": len(failures),
                }, indent=2, ensure_ascii=False), encoding="utf-8")
    return int(status[0])


if __name__ == "__main__":
    raise SystemExit(main_())
