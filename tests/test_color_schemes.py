# SPDX-License-Identifier: GPL-3.0-or-later
"""Four independent UI color schemes; all widget operations are offscreen."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QSize, QTimer, Qt
from PyQt6.QtGui import QColor, QIcon, QPalette, QPixmap
from PyQt6.QtWidgets import QApplication, QStyledItemDelegate

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import i18n
import main

SCHEMES = ("classic", "graphite_teal", "slate_blue", "warm_indigo")
ROLES = ("surface", "panel", "button", "border", "text", "muted", "accent",
         "selected", "on_selected", "hover", "disabled", "focus", "danger", "on_danger")
# Independent transcription of section 4 of the approved 2026-10-09 report.
EXPECTED = {
    ("graphite_teal", "light"): "F5F7FA FFFFFF E8EEF3 647787 17212B 4A5D6B 00746F 00746F FFFFFF DAE6EC 6B7A88 1D4ED8 B42318 FFFFFF",
    ("graphite_teal", "dark"): "20272F 28323D 34414F A3B4C4 F5F7FA C5D0DA 5EEAD4 5EEAD4 102A28 435365 93A4B4 93C5FD FFC1B8 3B0A06",
    ("slate_blue", "light"): "F4F7FB FFFFFF E8EEF7 66788F 17243A 4B5D75 2456A6 2456A6 FFFFFF D7E4F5 6A7A8F 6D28D9 B42318 FFFFFF",
    ("slate_blue", "dark"): "1B2533 253246 31425A A0B2CB F5F8FD C9D5E5 93C5FD 93C5FD 102A4C 405574 A0ACC0 5EEAD4 FFC1B8 3B0A06",
    ("warm_indigo", "light"): "F7F5F0 FFFEFA ECE9E2 746F67 28251F 5D574E 4F46E5 4F46E5 FFFFFF E1DED6 7A746A 006D75 B42318 FFFFFF",
    ("warm_indigo", "dark"): "252420 302E29 3C3933 ABA394 FAF7F0 D0C8BA C4B5FD C4B5FD 241B4B 4B473F A89F90 5EEAD4 FFC1B8 3B0A06",
}


def contrast(fg, bg):
    def luminance(hex_color):
        color = QColor(hex_color)
        channels = [color.redF(), color.greenF(), color.blueF()]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
        return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))
    high, low = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (high + .05) / (low + .05)


@pytest.fixture
def rig(tmp_path, monkeypatch):
    assert os.environ.get("QT_QPA_PLATFORM") == "offscreen"
    assert os.environ.get("MYSCREENDRAW_NO_KEYBOARD") == "1"
    assert os.environ.get("PYNPUT_BACKEND") == "dummy"
    app = QApplication.instance() or QApplication([])
    assert app.platformName() == "offscreen"
    monkeypatch.setattr(main, "CONFIG_FILE", str(tmp_path / "config.json"))
    monkeypatch.setattr(main, "track_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "autostart_enabled", lambda: False)
    monkeypatch.setattr(main.keyboard, "Listener", Mock())
    monkeypatch.setattr(main.AppLifecycleManager, "_setup_tray", lambda self: None)
    monkeypatch.setattr(main.ControlPanel, "check_for_updates", Mock())
    monkeypatch.setattr(main.urllib.request, "urlopen", Mock(side_effect=AssertionError("network forbidden")))
    monkeypatch.setattr(main, "set_canvas_passthrough", Mock())
    initial_windows = set(app.topLevelWidgets())
    panels = []

    def create():
        panel = main.ControlPanel()
        panel.canvas = main.DrawingCanvas(panel)
        panel.update_check_enabled = False
        for timer in panel.findChildren(QTimer):
            timer.stop()
        panels.append(panel)
        return panel

    yield create, app
    for panel in panels:
        panel.stop_update_worker()
        panel.shutdown_autosave()
    from conftest import _dispose_offscreen_widgets
    _dispose_offscreen_widgets(app, set(app.topLevelWidgets()) - initial_windows)


@pytest.mark.parametrize("scheme,mode", EXPECTED)
def test_approved_tokens_and_compatibility_aliases(scheme, mode):
    theme = main.ControlPanel.theme_for(mode, scheme)
    for role, value in zip(ROLES, EXPECTED[scheme, mode].split()):
        assert QColor(theme[role]).name() == "#" + value.lower(), role
    for alias, role in {"frame": "surface", "button_hover": "hover", "label": "accent",
                        "hint": "muted", "active_text": "on_selected", "mode_off": "disabled"}.items():
        assert theme[alias] == theme[role]
    for fg in ("text", "muted"):
        for bg in ("surface", "panel", "button", "hover"):
            assert contrast(theme[fg], theme[bg]) >= 4.5, (fg, bg)
    for fg, bg in (("on_selected", "selected"), ("on_danger", "danger")):
        assert contrast(theme[fg], theme[bg]) >= 4.5
    for bg in ("surface", "panel", "button", "hover"):
        assert contrast(theme["border"], theme[bg]) >= 3
    # Focus is separated from selected fills by the surface-colored isolation band.
    assert contrast(theme["focus"], theme["surface"]) >= 3


@pytest.mark.parametrize("mode", ("light", "dark"))
def test_classic_factory_keeps_legacy_tokens(mode):
    assert main.ControlPanel.theme_for(mode, "classic") == main.ControlPanel.THEMES[mode]


@pytest.mark.parametrize("mode", ("light", "dark"))
@pytest.mark.parametrize("scheme", SCHEMES)
def test_settings_choice_applies_and_reopens_from_disk(rig, scheme, mode):
    create, app = rig
    panel = create()
    if panel.theme_name != mode:
        panel.toggle_theme()
    panel.open_settings_panel()
    combo = panel.color_scheme_combo
    assert [combo.itemData(i) for i in range(combo.count())] == list(SCHEMES)
    combo.setCurrentIndex(combo.findData(scheme))
    if scheme == "classic":
        panel.save_settings()
    app.processEvents()
    assert panel.color_scheme == scheme
    assert panel.theme_name == mode
    assert panel.theme == main.ControlPanel.theme_for(mode, scheme)
    assert isinstance(combo.itemDelegate(), QStyledItemDelegate)
    assert combo.view().palette().color(QPalette.ColorRole.Highlight) == QColor(panel.theme["accent"])
    assert combo.view().palette().color(QPalette.ColorRole.HighlightedText) == QColor(panel.theme["active_text"])
    assert panel.theme["frame"] in panel.styleSheet()
    assert panel.theme["frame"] in panel.toolbar_window.styleSheet()
    stored = json.loads(Path(main.CONFIG_FILE).read_text(encoding="utf-8"))
    assert (stored["theme"], stored["color_scheme"]) == (mode, scheme)
    reopened = create()
    reopened.load_settings()
    reopened.open_settings_panel()
    assert (reopened.theme_name, reopened.color_scheme) == (mode, scheme)
    assert reopened.color_scheme_combo.currentData() == scheme
    assert reopened.theme == main.ControlPanel.theme_for(mode, scheme)
    panel.settings_panel.hide()
    panel.open_settings_panel()
    assert panel.color_scheme_combo is combo
    assert combo.currentData() == scheme


@pytest.mark.parametrize("mode", ("light", "dark"))
@pytest.mark.parametrize("value", ["missing", None, "unknown", "A", 7, True, [], {}])
def test_old_or_invalid_scheme_falls_back_to_classic(rig, mode, value):
    create, _ = rig
    panel = create()
    panel.set_color_scheme("warm_indigo", persist=False)
    old = {"theme": mode, "ui_opacity": 63, "ui_radius": 17,
           "orientation": "landscape", "pen_color": "#aabbcc", "update_check_enabled": False}
    if value != "missing":
        old["color_scheme"] = value
    Path(main.CONFIG_FILE).write_text(json.dumps(old), encoding="utf-8")
    panel.load_settings()
    assert panel.color_scheme == "classic"
    assert panel.theme_name == mode
    assert panel.theme == main.ControlPanel.THEMES[mode]
    assert panel.ui_opacity == 63
    assert panel.ui_radius == 17
    assert panel.orientation == "landscape"
    assert panel.canvas.pen_color.name() == "#aabbcc"
    panel.save_settings()
    assert json.loads(Path(main.CONFIG_FILE).read_text(encoding="utf-8"))["color_scheme"] == "classic"


@pytest.mark.parametrize("mode", ("light", "dark"))
def test_switching_preserves_user_content_preferences_and_button_geometry(rig, mode):
    create, app = rig
    panel = create()
    if panel.theme_name != mode:
        panel.toggle_theme()
    panel.set_ui_opacity(71, persist=False)
    panel.set_ui_radius(19, persist=False)
    panel.set_orientation("landscape")
    panel.canvas.pen_color = QColor("#987654")
    panel.canvas.marker_color = QColor("#369abc")
    panel.marker_alpha_slider.setValue(47)
    panel.canvas.laser_color = QColor("#123456")
    panel.open_settings_panel()
    app.processEvents()
    before = panel.collect_settings()
    identities = {key: (id(btn), btn.size(), btn.pos()) for key, btn in panel.icon_buttons.items()}
    collapsed = panel.toolbar_window.isVisible()
    for scheme in SCHEMES:
        panel.color_scheme_combo.setCurrentIndex(panel.color_scheme_combo.findData(scheme))
        after = panel.collect_settings()
        assert {k: v for k, v in after.items() if k != "color_scheme"} == {k: v for k, v in before.items() if k != "color_scheme"}
        assert panel.toolbar_window.isVisible() == collapsed
        assert {key: (id(btn), btn.size(), btn.pos()) for key, btn in panel.icon_buttons.items()} == identities
        panel.toggle_theme()
        assert panel.color_scheme == scheme
        panel.toggle_theme()
        assert panel.theme_name == mode


@pytest.mark.parametrize("lang", i18n._LANGS)
def test_color_choice_strings_use_all_eight_languages(rig, monkeypatch, lang):
    monkeypatch.setattr(i18n, "CURRENT", lang)
    panel = rig[0]()
    panel.open_settings_panel()
    keys = ("color_scheme_classic", "color_scheme_graphite_teal", "color_scheme_slate_blue", "color_scheme_warm_indigo")
    assert panel.color_scheme_label.text() == i18n.tr("color_scheme")
    assert panel.color_scheme_label.buddy() is panel.color_scheme_combo
    for index, key in enumerate(keys):
        assert panel.color_scheme_combo.itemText(index) == i18n.TEXT[lang][key]
        assert i18n.tr(key) != key
    assert main.ControlPanel.theme_for("light", "classic") == main.ControlPanel.THEMES["light"]


def test_main_keeps_utf8_bom():
    assert (ROOT / "main.py").read_bytes().startswith(b"\xef\xbb\xbf")


def image_contains(image, color):
    expected = QColor(color)
    return any(image.pixelColor(x, y).alpha() >= 250 and image.pixelColor(x, y).rgb() == expected.rgb()
               for y in range(image.height()) for x in range(image.width()))


@pytest.mark.parametrize("scheme,mode", EXPECTED)
def test_icon_modes_mirrored_states_badge_and_cache(rig, monkeypatch, scheme, mode):
    from unittest.mock import Mock
    import ui_icons
    panel = rig[0]()
    if panel.theme_name != mode:
        panel.toggle_theme()
    panel.set_color_scheme(scheme, persist=False)
    button = panel.icon_buttons["eraser"]
    source = panel.btn_eraser
    source.setObjectName("")
    source.setEnabled(True)
    panel.sync_icon_buttons()
    theme = panel.theme
    for qt_mode in (QIcon.Mode.Normal, QIcon.Mode.Active, QIcon.Mode.Selected, QIcon.Mode.Disabled):
        for state in (QIcon.State.Off, QIcon.State.On):
            role = "disabled" if qt_mode == QIcon.Mode.Disabled else (
                "on_selected" if state == QIcon.State.On or qt_mode == QIcon.Mode.Selected else "text")
            image = button.icon().pixmap(QSize(main.ICON_GLYPH, main.ICON_GLYPH), qt_mode, state).toImage()
            assert image_contains(image, theme[role]), (qt_mode, state, role)
    source.setObjectName("ActiveTool")
    panel.sync_icon_buttons()
    assert button.objectName() == "IconBtnActive"
    assert image_contains(button.icon().pixmap(main.ICON_GLYPH).toImage(), theme["on_selected"])
    source.setEnabled(False)
    panel.sync_icon_buttons()
    assert not button.isEnabled()
    assert image_contains(button.icon().pixmap(main.ICON_GLYPH, QIcon.Mode.Disabled).toImage(), theme["disabled"])
    source.setEnabled(True)
    source.setObjectName("")
    panel.sync_icon_buttons()
    button.setDown(True)
    button.pressed.emit()  # Qt signal only; never OS input.
    assert image_contains(button.icon().pixmap(main.ICON_GLYPH).toImage(), theme["on_selected"])
    pixmap = QPixmap(button.size())
    pixmap.fill(Qt.GlobalColor.transparent)
    button.render(pixmap)
    assert pixmap.toImage().pixelColor(2, button.height() // 2) == QColor(theme["selected"])
    button.setDown(False)
    button.released.emit()
    assert image_contains(button.icon().pixmap(main.ICON_GLYPH).toImage(), theme["text"])
    panel.canvas.marker_color = QColor("#13579b")
    panel.canvas.marker_color.setAlpha(70)
    panel.canvas.draw_state = "MARKER"
    panel.refresh_ui()
    badge = panel.icon_buttons["pen"].icon().pixmap(QSize(main.ICON_GLYPH * 2, main.ICON_GLYPH * 2)).toImage()
    assert image_contains(badge, "#13579b")
    assert panel.canvas.marker_color.alpha() == 70
    cached = {key: btn.icon().cacheKey() for key, btn in panel.icon_buttons.items()}
    draw = Mock(wraps=ui_icons.make_ui_pixmap)
    monkeypatch.setattr(ui_icons, "make_ui_pixmap", draw)
    panel.sync_icon_buttons()
    panel.refresh_ui()
    panel.refresh_annotate_badge()
    assert draw.call_count == 0
    assert {key: btn.icon().cacheKey() for key, btn in panel.icon_buttons.items()} == cached
    # Returning through classic must invalidate the cached enhanced icon projection.
    panel.set_color_scheme("classic", persist=False)
    panel.set_color_scheme(scheme, persist=False)
    assert image_contains(panel.icon_buttons["pen"].icon().pixmap(main.ICON_GLYPH).toImage(), theme["on_selected"])


@pytest.mark.parametrize("scheme,mode", EXPECTED)
def test_focus_ring_has_neutral_isolation_and_preserves_hit_area(rig, scheme, mode):
    panel, app = rig[0](), rig[1]
    if panel.theme_name != mode:
        panel.toggle_theme()
    panel.set_color_scheme(scheme, persist=False)
    panel.open_settings_panel()
    button = panel.btn_theme
    geometry = button.geometry()
    panel.settings_panel.activateWindow()
    button.setFocus(Qt.FocusReason.OtherFocusReason)
    app.processEvents()
    ring = button._color_scheme_focus_ring
    assert ring.isVisible()
    assert ring.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert ring.focusPolicy() == Qt.FocusPolicy.NoFocus
    pixmap = QPixmap(ring.size())
    pixmap.fill(Qt.GlobalColor.transparent)
    ring.render(pixmap)
    image = pixmap.toImage()
    assert image_contains(image, panel.theme["surface"])
    assert image_contains(image, panel.theme["focus"])
    assert button.geometry() == geometry
    panel.set_color_scheme("classic", persist=False)
    assert not ring.isVisible()


@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5, 2.0])
@pytest.mark.parametrize("scheme,mode", EXPECTED)
def test_state_icons_keep_logical_size_at_scaling_levels(rig, scheme, mode, dpr):
    panel = rig[0]()
    if panel.theme_name != mode:
        panel.toggle_theme()
    panel.set_color_scheme(scheme, persist=False)
    icon = panel.icon_buttons["eraser"].icon()
    pixmap = icon.pixmap(QSize(main.ICON_GLYPH, main.ICON_GLYPH), dpr,
                         QIcon.Mode.Selected, QIcon.State.On)
    assert pixmap.width() / pixmap.devicePixelRatio() == pytest.approx(main.ICON_GLYPH)
    assert pixmap.height() / pixmap.devicePixelRatio() == pytest.approx(main.ICON_GLYPH)
    assert image_contains(pixmap.toImage(), panel.theme["on_selected"])


@pytest.mark.parametrize("bad", [None, "unknown", True, [], {}])
def test_invalid_live_selection_does_not_change_or_persist(rig, monkeypatch, bad):
    from unittest.mock import Mock
    panel = rig[0]()
    panel.set_color_scheme("slate_blue", persist=False)
    save = Mock()
    monkeypatch.setattr(panel, "save_settings", save)
    panel.set_color_scheme(bad)
    panel.set_color_scheme("slate_blue")
    assert panel.color_scheme == "slate_blue"
    assert save.call_count == 0


@pytest.mark.parametrize("legacy_theme", [None, "unknown", "light_A", 5, True, {}, []])
def test_invalid_old_theme_does_not_override_mode_or_abort_scheme(rig, legacy_theme):
    panel = rig[0]()
    Path(main.CONFIG_FILE).write_text(json.dumps({"theme": legacy_theme,
        "color_scheme": "graphite_teal", "ui_opacity": 58, "update_check_enabled": False}), encoding="utf-8")
    panel.load_settings()
    assert (panel.theme_name, panel.color_scheme) == ("dark", "graphite_teal")
    assert panel.ui_opacity == 58
