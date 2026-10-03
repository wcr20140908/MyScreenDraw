# SPDX-License-Identifier: GPL-3.0-or-later
"""Final UI fixes through the actual host, without desktop or user data."""
from unittest.mock import patch
from PyQt6.QtGui import QColor, QPalette
from test_upgrade_settings import app, rig


def test_settings_both_dropdowns_follow_repeated_theme_changes(rig, app):
    p, c = rig.fresh()
    p.open_settings_panel()
    editor = p.pen_defaults_editor
    editor.width_spin.setValue(19)
    before = editor.presets()
    for name in ("dark", "light", "dark"):
        p.theme_name = name
        p.theme = p.THEMES[name]
        p.apply_theme()
        for combo in (p.update_channel_combo, editor.pen_combo):
            combo.showPopup()
            app.processEvents()
            view = combo.view()
            assert view.isVisible()
            assert view.palette().color(QPalette.ColorRole.Base) == QColor(p.theme["panel"])
            assert view.palette().color(QPalette.ColorRole.Text) == QColor(p.theme["text"])
            assert view.palette().color(QPalette.ColorRole.Highlight) == QColor(p.theme["accent"])
            combo.hidePopup()
        assert editor.width_spin.value() == 19
        assert editor.presets() == before


def test_chalk_renderer_uses_new_texture_and_existing_cache(rig):
    import main
    from chalk_texture import make_chalk_texture
    main._TEXTURE_CACHE.clear()
    color = QColor("#aacc5533")
    options = {"density": 68, "opacity": 83}
    image = main.style_texture("chalk", color, options)
    assert image == make_chalk_texture(color, **options)
    with patch.object(main, "make_chalk_texture", side_effect=AssertionError("cache missed")):
        assert main.style_texture("chalk", color, dict(options)) is image
    assert main.style_texture("pencil", color).width() == 48
    assert main.style_texture("crayon", color).width() == 48
