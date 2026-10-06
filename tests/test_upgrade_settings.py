# SPDX-License-Identifier: GPL-3.0-or-later
"""Upgrade contract: beta.8 JSON must survive a fresh 6.0.0 startup.

Run: python -m pytest tests/test_upgrade_settings.py -q
No packaged app, desktop, listener, tray, telemetry, or update request is used.
The icon-only UI migration and current screen identity are intentional exceptions
when requiring nondefault values. Magnifier is not a persisted TOOL_STATE.

Red-first audit, baseline 354df9a (2026-10-02): 20 failed, 232 passed.
All failures are test_corrupt_single_field_does_not_abort_healthy_siblings:
  {null,string,object} x {eraser_size,marker_alpha_pct,marker_width,
                         laser_width,magnifier_zoom,magnifier_size} (18)
  object-theme, object-draw_state (2).
Unchecked int/float conversions and unhashable dict membership abort the single
outer settings-application try block, leaving healthy later settings at defaults.
No production fix or xfail is included; this record describes the pre-fix baseline.

Updater coverage inspected (not executed: it launches a PowerShell transaction):
test_beta6_updater verifies a sentinel data/config.json survives *failed launch*
rollback, rejects unsafe archives, and tests package data/exports exclusions.
Gaps: successful-install preservation; realistic preference JSON through a new
process; byte preservation of populated exports, autosaves, roster and unrelated
user files; upgrades with existing destination trees and locked user-data files.
These tests cover the in-process persistence boundary, not a packaged updater run.

"""
import copy
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIELDS = tuple("""theme pen_color pen_width pen_profiles pen_style calligraphy_angle
pen_options eraser_type eraser_size marker_color marker_alpha_pct marker_width
laser_color laser_width magnifier_zoom magnifier_size board_style smart_shapes
smart_multitouch speed_width timer_mode timer_target panel_x panel_y panel_screen
logo_x logo_y toolbar_x toolbar_y toolbar_detached orientation draw_state shape_type
text_font_size drawing_mode ruler_calibrations ui_mode ui_radius ui_opacity
update_check_enabled update_channel notice_state whiteboard_auto_pen
pen_defaults_enabled pen_defaults last_annotate_tool autosave_interval_seconds
annotation_screen timer_alarm_volume page_copy_placement""".split())
TOOLS = ("PEN", "MARKER", "LASER", "ERASER", "SELECT", "TEXT", "SHAPE")


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    instance = QApplication.instance() or QApplication([])
    assert instance.platformName() == "offscreen", "Never run this suite on the desktop"
    yield instance


@pytest.fixture
def rig(tmp_path, monkeypatch, app):
    import main
    from PyQt6.QtCore import QCoreApplication, QEvent, QTimer
    from PyQt6.QtWidgets import QApplication

    for name, path in {
        "DATA_DIR": tmp_path, "EXPORT_DIR": tmp_path / "exports",
        "AUTOSAVE_DIR": tmp_path / "autosave", "CONFIG_FILE": tmp_path / "config.json",
        "ROSTER_FILE": tmp_path / "roster.json", "TELEMETRY_FILE": tmp_path / "events.jsonl",
        "LOG_FILE": tmp_path / "app.log",
    }.items():
        monkeypatch.setattr(main, name, str(path))
    monkeypatch.setattr(main, "LOGGER", Mock())
    monkeypatch.setattr(main, "track_event", Mock())
    monkeypatch.setattr(main, "setup_logging", Mock())
    monkeypatch.setattr(main.keyboard, "Listener", Mock())
    monkeypatch.setattr(main.AppLifecycleManager, "_setup_tray", lambda self: None)
    monkeypatch.setattr(main.ControlPanel, "check_for_updates", Mock())
    monkeypatch.setattr(main.urllib.request, "urlopen", Mock(side_effect=AssertionError("network forbidden")))
    monkeypatch.setattr(main, "set_canvas_passthrough", Mock())
    before = set(QApplication.topLevelWidgets())
    quit_on_close = app.quitOnLastWindowClosed()
    pairs = []

    def fresh():
        panel = main.ControlPanel()
        pairs.append((panel, None))  # also clean up if canvas construction fails
        canvas = main.DrawingCanvas(panel)
        pairs[-1] = (panel, canvas)
        panel.canvas = canvas
        for timer in panel.findChildren(QTimer) + canvas.findChildren(QTimer):
            timer.stop()
        return panel, canvas

    def load(payload=None):
        if payload is not None:
            main.atomic_write_json(main.CONFIG_FILE, payload)
        panel, canvas = fresh()
        panel.apply_theme()
        panel.load_settings()
        panel.restore_position()
        return panel, canvas

    yield SimpleNamespace(main=main, fresh=fresh, load=load, path=Path(main.CONFIG_FILE))
    for panel, canvas in pairs:
        panel.listener.stop()
        panel.listener.join(timeout=1)
        panel.stop_update_worker()
        for owner in (panel, canvas):
            if owner is not None:
                for timer in owner.findChildren(QTimer):
                    timer.stop()
    # closeEvent enters background mode; deleteLater is the non-interactive cleanup.
    for window in set(QApplication.topLevelWidgets()) - before:
        window.hide()
        window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.setQuitOnLastWindowClosed(quit_on_close)
    assert not (set(QApplication.topLevelWidgets()) - before), "Leaked offscreen windows"


def rich_settings(rig):
    """Produce the beta.8-format input using the real writer, not the loader."""
    from PyQt6.QtGui import QColor
    p, c = rig.fresh()
    baseline = p.collect_settings()
    p.theme_name = "light"
    p.theme = p.THEMES["light"]
    p.apply_theme()
    p.set_orientation("landscape")
    p.set_ui_radius(21, persist=False)
    p.set_ui_opacity(73, persist=False)
    p.timer_mode, p.timer_target = "UP", 137
    p.update_check_enabled, p.update_channel = False, "preview"
    for i, style in enumerate(rig.main.PEN_STYLES):
        c.pen_profiles[style] = {"color": QColor.fromHsv(i * 23, 180, 190).name(),
                                 "width": i + 11, "speed_width": bool(i % 2)}
    c.pen_style = "calligraphy"
    c.pen_color, c.pen_width, c.speed_width_enabled = QColor("#2468ac"), 19, False
    c.calligraphy_angle = 123
    c.pen_options = {style: {key: low if default != low else high
                            for key, low, high, default in options}
                     for style, options in rig.main.PEN_STYLE_OPTIONS.items()}
    c.eraser_type, c.eraser_size = "STROKE", 81
    c.marker_color, c.marker_width = QColor("#317ca8"), 37
    p.marker_alpha_slider.setValue(61)
    c.laser_color, c.laser_width = QColor("#ab3498"), 29
    c.magnifier_zoom, c.magnifier_size = 3.5, 347
    c.board_style = "BLACK"
    c.smart_shapes_enabled = c.smart_multitouch_enabled = False
    c.draw_state, c.shape_type, c.text_font_size = "SHAPE", "ELLIPSE", 47
    c.is_drawing_mode = False
    c.ruler_calibrations = {
        key: {"screen_key": key, "px_per_mm": scale, "known_length_mm": 150.0,
              "dpr": 1.5, "logical_dpi": 144.0, "geometry": geometry}
        for key, scale, geometry in (("external-A", 5.25, [0, 0, 1920, 1080]),
                                     ("external-B", 7.5, [-2560, 0, 2560, 1440]))
    }
    p._toolbar_detached = True
    # Coordinates deliberately fit the offscreen display and final orientation.
    p.move(13, 17)
    p.logo_window.move(29, 31)
    p.toolbar_window.move(43, 107)
    p._toolbar_saved_pos = (43, 107)
    from pen_defaults import capture_current
    p.whiteboard_auto_pen = False
    p.pen_defaults_enabled = True
    p.notice_state = {"launches": 9, "last_version": "v6.0.0"}
    p.last_annotate_tool = "MARKER"
    p.autosave_interval_seconds = 47
    p.annotation_screen = "synthetic-disconnected-monitor|serial"
    p.timer_alarm_volume = 31
    p.page_copy_placement = "before"
    p.pen_defaults = {key: capture_current(c, key) for key in (*rig.main.PEN_STYLES, "marker", "laser")}
    settings = p.collect_settings()
    assert set(settings) == set(FIELDS), "Update the audit when collect_settings changes"
    for field in FIELDS:
        if field not in ("ui_mode", "panel_screen"):
            assert settings[field] != baseline[field], f"{field} must exercise a nondefault"
    p.save_settings()
    import json
    assert json.loads(rig.path.read_text(encoding="utf-8")) == settings
    return settings


@pytest.mark.parametrize("field", FIELDS)
def test_every_collected_field_survives_fresh_start(rig, field):
    expected = rich_settings(rig)
    p, _ = rig.load()
    assert p.collect_settings()[field] == expected[field]


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("drawing_mode", [False, True])
def test_tool_and_drawing_mode_are_independent(rig, tool, drawing_mode):
    payload = rich_settings(rig)
    payload.update(draw_state=tool, drawing_mode=drawing_mode)
    p, c = rig.load(payload)
    assert (c.draw_state, c.is_drawing_mode) == (tool, drawing_mode)
    p.save_settings()
    again, canvas = rig.load()
    assert (canvas.draw_state, canvas.is_drawing_mode) == (tool, drawing_mode)


@pytest.mark.parametrize("orientation", ["portrait", "landscape"])
def test_detached_positions_fit_screen_without_drift(rig, orientation):
    payload = rich_settings(rig)
    payload["orientation"] = orientation
    p, _ = rig.load(payload)
    area = p.screen().availableGeometry()
    for window in (p, p.logo_window, p.toolbar_window):
        assert area.contains(window.geometry()), "Fixture must fit; clamping is not data loss"
    p._sync_split_geometry()
    keys = ("panel_x", "panel_y", "logo_x", "logo_y", "toolbar_x", "toolbar_y",
            "toolbar_detached", "orientation")
    assert {k: p.collect_settings()[k] for k in keys} == {k: payload[k] for k in keys}


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("channel", ["stable", "preview"])
def test_update_preferences_and_timer(rig, enabled, channel):
    payload = rich_settings(rig)
    payload.update(update_check_enabled=enabled, update_channel=channel)
    p, _ = rig.load(payload)
    assert (p.update_check_enabled, p.update_channel) == (enabled, channel)
    assert p.update_check_timer.isActive() is enabled
    rig.main.ControlPanel.check_for_updates.assert_not_called()
    rig.main.urllib.request.urlopen.assert_not_called()


@pytest.mark.parametrize("mode", ["UP", "DOWN"])
@pytest.mark.parametrize("seconds", [1, 137, 5999])
def test_timer_configuration_not_running_session_is_restored(rig, mode, seconds):
    payload = rich_settings(rig)
    payload.update(timer_mode=mode, timer_target=seconds)
    p, _ = rig.load(payload)
    assert (p.timer_mode, p.timer_target) == (mode, seconds)
    assert p.timer_left == (float(seconds) if mode == "DOWN" else 0.0)
    assert not p.timer_running


@pytest.mark.parametrize("legacy_style", ["classic", "icon"])
def test_legacy_ui_migrates_to_icon_without_losing_appearance(rig, legacy_style):
    payload = rich_settings(rig)
    payload["ui_mode"] = legacy_style
    p, c = rig.load(payload)
    assert (p.ui_mode, p.theme_name, p.ui_radius, p.ui_opacity) == ("icon", "light", 21, 73)
    assert c.windowOpacity() == 1.0, "UI opacity must not fade ink"


@pytest.mark.parametrize("speed", [False, True])
def test_beta7_shared_pen_migrates_to_independent_profiles(rig, speed):
    payload = rich_settings(rig)
    for key in ("pen_profiles", "pen_style", "pen_options", "calligraphy_angle"):
        payload.pop(key)
    payload.update(pen_color="#456789", pen_width=17, speed_width=speed, pen_defaults_enabled=False)
    p, c = rig.load(payload)
    expected = {"color": "#456789", "width": 17, "speed_width": speed}
    for style in rig.main.PEN_STYLES:
        assert c.pen_profile(style) == expected
    p.save_settings()
    p2, c2 = rig.load()
    assert p2.collect_settings()["pen_profiles"] == p.collect_settings()["pen_profiles"]
    c2.pen_style = "pencil"
    c2.pen_width = 3
    assert c2.pen_profile("chalk") == expected


# Invalid JSON *values*, not an invalid file: healthy sibling settings must load.
# Use a neutral drawing mode to keep corruption isolation separate from tool/mode checks.
@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("bad", [None, "not-a-value", {"corrupt": "invalid"}],
                         ids=["null", "string", "object"])
def test_corrupt_single_field_does_not_abort_healthy_siblings(rig, field, bad):
    payload = rich_settings(rig)
    payload["drawing_mode"] = True
    expected = copy.deepcopy(payload)
    payload[field] = copy.deepcopy(bad)
    # Profile maps accept arbitrary keys and ignore them; malformed containers
    # exercise their defensive path instead.
    if field in ("pen_profiles", "pen_options", "ruler_calibrations") and isinstance(bad, dict):
        payload[field] = ["invalid container"]
    p, _ = rig.load(payload)
    excluded = {field}
    dependencies = (
        {"pen_profiles", "pen_color", "pen_width", "speed_width", "pen_style"},
        {"panel_x", "panel_y"},
        {"logo_x", "logo_y", "toolbar_x", "toolbar_y", "toolbar_detached", "orientation"},
    )
    for group in dependencies:
        if field in group:
            excluded.update(group)
    actual = p.collect_settings()
    differences = {key: {"expected": expected[key], "actual": actual[key]}
                   for key in FIELDS if key not in excluded and actual[key] != expected[key]}
    assert not differences, f"Corrupt {field} blocked healthy siblings: {differences}"


PEN_STYLES = ("pen", "fountain", "brush", "calligraphy", "pencil", "crayon",
              "chalk", "neon", "dashed", "rainbow", "arrow")


@pytest.mark.parametrize("style", PEN_STYLES)
def test_each_active_pen_keeps_its_profile_and_options(rig, style):
    payload = rich_settings(rig)
    payload["pen_style"] = style
    profile = payload["pen_profiles"][style]
    payload.update(pen_color=profile["color"], pen_width=profile["width"],
                   speed_width=profile["speed_width"])
    p, c = rig.load(payload)
    assert c.pen_style == style
    assert c.pen_profile(style) == profile
    for field in ("pen_profiles", "pen_options", "pen_color", "pen_width", "speed_width"):
        assert p.collect_settings()[field] == payload[field]


@pytest.mark.parametrize("style", PEN_STYLES)
@pytest.mark.parametrize("member", ["color", "width", "speed_width"])
def test_one_corrupt_profile_member_preserves_other_profiles(rig, style, member):
    payload = rich_settings(rig)
    expected = copy.deepcopy(payload["pen_profiles"])
    payload["pen_profiles"][style][member] = {"invalid": True}
    p, c = rig.load(payload)
    for other in PEN_STYLES:
        if other != style:
            assert c.pen_profile(other) == expected[other]
    for key in ("color", "width", "speed_width"):
        if key != member:
            assert c.pen_profile(style)[key] == expected[style][key]
    assert p.collect_settings()["update_check_enabled"] is False
    assert p.collect_settings()["ruler_calibrations"] == payload["ruler_calibrations"]


@pytest.mark.parametrize("style", PEN_STYLES[1:])
def test_corrupt_style_options_do_not_reset_other_styles(rig, style):
    payload = rich_settings(rig)
    expected = copy.deepcopy(payload["pen_options"])
    payload["pen_options"][style] = ["invalid"]
    p, _ = rig.load(payload)
    actual = p.collect_settings()
    for other in expected:
        if other != style:
            assert actual["pen_options"][other] == expected[other]
    assert actual["update_channel"] == "preview"


@pytest.mark.parametrize("bad_record", [None, {"px_per_mm": "bad"}, {"px_per_mm": 0}])
def test_corrupt_calibration_does_not_erase_other_monitors(rig, bad_record):
    payload = rich_settings(rig)
    expected = copy.deepcopy(payload["ruler_calibrations"])
    payload["ruler_calibrations"]["broken-monitor"] = bad_record
    p, _ = rig.load(payload)
    assert p.collect_settings()["ruler_calibrations"] == expected


def test_legacy_single_screen_calibration_migrates(rig):
    payload = rich_settings(rig)
    payload.pop("ruler_calibrations")
    payload["ruler_calibration"] = {"px_per_mm": 6.25, "known_length_mm": 175.0}
    p, c = rig.load(payload)
    key, _, _ = c.current_screen_calibration()
    assert c.ruler_calibrations[key]["px_per_mm"] == 6.25
    assert c.ruler_calibrations[key]["known_length_mm"] == 175.0
    p.save_settings()
    again, _ = rig.load()
    assert again.collect_settings()["ruler_calibrations"] == p.collect_settings()["ruler_calibrations"]
