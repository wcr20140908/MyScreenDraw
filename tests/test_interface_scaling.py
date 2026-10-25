# SPDX-License-Identifier: GPL-3.0-or-later
"""Whole-interface Qt scaling on an isolated 1920x1080 virtual screen."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCALE_PERCENTAGES = (75, 100, 125, 150, 175, 200)
PHYSICAL_SCREEN = (1920, 1080)


PROBE = r'''
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
config = root / "config.json"

import main
import i18n
import toolbar_windows

for name, path in {
    "DATA_DIR": root / "data",
    "EXPORT_DIR": root / "exports",
    "AUTOSAVE_DIR": root / "data" / "autosave",
    "CONFIG_FILE": config,
    "ROSTER_FILE": root / "data" / "roster.json",
    "TELEMETRY_FILE": root / "data" / "events.jsonl",
    "LOG_FILE": root / "data" / "app.log",
}.items():
    setattr(main, name, str(path))
for path in (Path(main.DATA_DIR), Path(main.EXPORT_DIR), Path(main.AUTOSAVE_DIR)):
    path.mkdir(parents=True, exist_ok=True)

# A normal restart inherits our environment. Applying startup preferences twice
# before QApplication emulates that inheritance and must replace, not multiply,
# the application's factor.
main.initialize_interface_preferences()
first_factor = main.os.environ["QT_SCALE_FACTOR"]
main.initialize_interface_preferences()
second_factor = main.os.environ["QT_SCALE_FACTOR"]

from PyQt6.QtCore import QRect, QTimer
from PyQt6.QtWidgets import QApplication, QStyleOptionToolButton

app = QApplication([])
app.setQuitOnLastWindowClosed(False)
scale = float(second_factor)
screen = QRect(0, 0, round(1920 / scale), round(1080 / scale))

# Qt's offscreen plugin exposes a fixed 800x800 screen. Substitute only the
# platform screen boundary; every widget, layout, font, icon, and grab below is
# a real production Qt object rendered with the real process scale factor.
toolbar_windows._available_rect = lambda _widget=None: QRect(screen)
main.ControlPanel.screen_geometry = lambda _self, *_widgets: QRect(screen)
main.track_event = lambda *_args, **_kwargs: None
main.setup_logging = lambda: None
main.AppLifecycleManager._setup_tray = lambda _self: None
main.ControlPanel.check_for_updates = lambda _self: None
main.set_canvas_passthrough = lambda *_args, **_kwargs: None

panel = main.ControlPanel()
canvas = main.DrawingCanvas(panel)
panel.canvas = canvas
for owner in (panel, canvas):
    for timer in owner.findChildren(QTimer):
        timer.stop()


def settle():
    for _ in range(5):
        app.processEvents()


def rendered(widget):
    settle()
    pixmap = widget.grab()
    return {
        "logical": [widget.width(), widget.height()],
        "pixels": [pixmap.width(), pixmap.height()],
        "dpr": pixmap.devicePixelRatio(),
    }


def contained(widget):
    return screen.contains(widget.frameGeometry())


panel.apply_theme()
panel.load_settings()
panel.logo_window.move(40, 40)
panel.logo_window.show()
panel.toolbar_window.show()
settle()

orientations = {}
for orientation in ("portrait", "landscape"):
    panel.set_orientation(orientation)
    panel.logo_window.move(40, 40)
    panel.toolbar_window.show()
    panel.logo_window.show()
    panel._sync_split_geometry()
    settle()

    logo = panel.logo_window
    toolbar = panel.toolbar_window
    gap = toolbar_windows.LOGO_GAP
    close = lambda actual, expected: abs(actual - expected) <= 1
    if orientation == "portrait":
        attached = (close(logo.width(), toolbar.width()) and close(toolbar.x(), logo.x()) and
                    close(toolbar.y(), logo.y() + logo.height() + gap))
    else:
        attached = (close(logo.height(), toolbar.height()) and close(toolbar.y(), logo.y()) and
                    close(toolbar.x(), logo.x() + logo.width() + gap))

    panel.show_only_sub(panel.file_sub)
    settle()
    menu_record = rendered(panel.menu_panel)
    menu_contained = contained(panel.menu_panel)

    panel.open_settings_panel()
    settle()
    settings_button = panel.icon_buttons["settings"]
    button_option = QStyleOptionToolButton()
    settings_button.initStyleOption(button_option)
    hint = panel.interface_restart_hint
    settings_record = rendered(panel.settings_panel)
    horizontal_overflow = panel.settings_scroll.horizontalScrollBar().maximum()

    orientations[orientation] = {
        "attached": attached,
        "contained": {
            "logo": contained(logo),
            "toolbar": contained(toolbar),
            "menu": menu_contained,
            "settings": contained(panel.settings_panel),
        },
        "logo": rendered(logo),
        "toolbar": rendered(toolbar),
        "menu": menu_record,
        "settings": settings_record,
        "settings_button": rendered(settings_button),
        "settings_hint": rendered(hint),
        "settings_horizontal_overflow": horizontal_overflow,
        "button_font_height": settings_button.fontMetrics().height(),
        "hint_font_height": hint.fontMetrics().height(),
        "button_icon_size": [settings_button.iconSize().width(), settings_button.iconSize().height()],
        "button_icon_is_null": settings_button.icon().isNull(),
        "button_text": settings_button.text(),
        "button_text_advance": button_option.fontMetrics.horizontalAdvance(settings_button.text()),
        "button_contents_width": settings_button.contentsRect().width(),
        "button_text_fits": (button_option.fontMetrics.horizontalAdvance(settings_button.text())
                             <= settings_button.contentsRect().width()),
        "hint_text": hint.text(),
        "hint_word_wrap": hint.wordWrap(),
    }
    panel.settings_panel.hide()

result = {
    "platform": app.platformName(),
    "actual_offscreen_geometry": list(app.primaryScreen().geometry().getRect()),
    "virtual_physical_screen": [1920, 1080],
    "virtual_logical_screen": [screen.width(), screen.height()],
    "dpr": app.primaryScreen().devicePixelRatio(),
    "first_factor": first_factor,
    "second_factor": second_factor,
    "language": i18n.CURRENT,
    "module_language": main.CURRENT,
    "orientations": orientations,
}

# Full widget trees need deterministic main-thread teardown on Windows. Letting
# SIP and Qt race during interpreter shutdown can end an otherwise successful
# probe with 0xC0000005, which tests process teardown rather than scaling.
panel.stop_update_worker()
panel.shutdown_autosave()
listener = getattr(panel, "listener", None)
if listener is not None:
    listener.stop()
    try:
        listener.join(timeout=1)
    except RuntimeError:
        pass
from PyQt6.QtCore import QCoreApplication, QEvent
for window in list(app.topLevelWidgets()):
    for timer in window.findChildren(QTimer):
        timer.stop()
    window.hide()
    window.deleteLater()
QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
app.processEvents()
print(json.dumps(result, ensure_ascii=False), flush=True)
'''


def _run_probe(folder, percentage):
    folder.mkdir(parents=True)
    (folder / "config.json").write_text(
        json.dumps({"language": "de", "ui_scale_percent": percentage}), encoding="utf-8")
    env = dict(os.environ)
    env.update({
        "QT_QPA_PLATFORM": "offscreen",
        "QT_SCALE_FACTOR": "1",
        "MYSCREENDRAW_NO_KEYBOARD": "1",
        "PYNPUT_BACKEND": "dummy",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    })
    env.pop("MYSCREENDRAW_BASE_QT_SCALE_FACTOR", None)
    env.pop("MYSCREENDRAW_ACTIVE_LANGUAGE", None)
    completed = subprocess.run(
        [sys.executable, "-c", PROBE, str(folder)], cwd=ROOT, env=env,
        capture_output=True, text=True, encoding="utf-8", timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert completed.returncode == 0, completed.stderr
    line = next(line for line in reversed(completed.stdout.splitlines()) if line.strip())
    return json.loads(line)


@pytest.fixture(scope="module")
def scale_probes(tmp_path_factory):
    root = tmp_path_factory.mktemp("interface-scaling")
    return {percentage: _run_probe(root / str(percentage), percentage)
            for percentage in SCALE_PERCENTAGES}


def _assert_native_render(record, factor):
    assert record["dpr"] == pytest.approx(factor)
    for logical, pixels in zip(record["logical"], record["pixels"]):
        assert pixels == pytest.approx(logical * factor, abs=1)


def test_saved_scale_and_language_apply_at_restart_without_compounding(scale_probes):
    for percentage, data in scale_probes.items():
        factor = percentage / 100
        assert data["platform"] == "offscreen"
        assert float(data["first_factor"]) == pytest.approx(factor)
        assert float(data["second_factor"]) == pytest.approx(factor)
        assert data["dpr"] == pytest.approx(factor)
        assert data["language"] == data["module_language"] == "de"
        assert data["virtual_physical_screen"] == list(PHYSICAL_SCREEN)
        assert data["virtual_logical_screen"] == [round(1920 / factor), round(1080 / factor)]


def test_toolbar_logo_settings_and_submenu_fit_both_orientations(scale_probes):
    for data in scale_probes.values():
        for orientation in ("portrait", "landscape"):
            result = data["orientations"][orientation]
            assert result["attached"]
            assert all(result["contained"].values()), result["contained"]
            assert result["settings_horizontal_overflow"] == 0
            assert result["settings"]["logical"][0] >= 300


def test_text_icons_and_complete_widgets_use_the_native_qt_factor(scale_probes):
    baseline = scale_probes[100]["orientations"]
    for percentage, data in scale_probes.items():
        factor = percentage / 100
        for orientation in ("portrait", "landscape"):
            result = data["orientations"][orientation]
            for name in ("logo", "toolbar", "menu", "settings", "settings_button", "settings_hint"):
                _assert_native_render(result[name], factor)
            assert not result["button_icon_is_null"]
            assert result["button_icon_size"] == [20, 20]
            assert result["button_text"]
            assert result["button_text_fits"]
            assert result["hint_text"]
            assert result["hint_word_wrap"]
            assert result["button_font_height"] == baseline[orientation]["button_font_height"]
            assert result["hint_font_height"] == baseline[orientation]["hint_font_height"]
