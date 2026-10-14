# SPDX-License-Identifier: GPL-3.0-or-later
"""Custom UI palettes use the existing isolated offscreen panel rig."""
from copy import deepcopy
import json
from pathlib import Path

from test_color_schemes import rig

import main
from custom_colors import ALIASES, ROLES, palette_from_theme


def custom_palette():
    colors = {
        mode: palette_from_theme(main.ControlPanel.theme_for(mode, "classic"))
        for mode in ("light", "dark")
    }
    colors["light"].update(surface="#f2e7d3", panel="#fcf1dd", selected="#205a84")
    colors["dark"].update(surface="#16252e", panel="#20313e", selected="#8bc2dd")
    return colors


def test_custom_scheme_save_edit_and_reopen(rig):
    create, app = rig
    panel = create()
    colors = custom_palette()
    scheme_id = panel.save_custom_color_scheme("Workshop", colors)
    assert scheme_id.startswith("custom_")
    assert panel.color_scheme == scheme_id

    edited = deepcopy(colors)
    edited["light"]["button"] = "#d4e6f1"
    edited["dark"]["button"] = "#304957"
    assert panel.save_custom_color_scheme("Workshop edited", edited, scheme_id) == scheme_id
    expected = {scheme_id: {"name": "Workshop edited", "colors": edited}}
    assert panel.custom_color_schemes == expected
    stored = json.loads(Path(main.CONFIG_FILE).read_text(encoding="utf-8"))
    assert stored["custom_color_schemes"] == expected
    assert stored["color_scheme"] == scheme_id

    reopened = create()
    reopened.load_settings()
    reopened.open_settings_panel()
    app.processEvents()
    assert reopened.custom_color_schemes == expected
    assert reopened.color_scheme == scheme_id
    assert reopened.color_scheme_combo.currentData() == scheme_id
    assert reopened.color_scheme_combo.currentText() == "Workshop edited"
    assert reopened.theme["button"] == edited[reopened.theme_name]["button"]
    assert reopened.theme["button"] in reopened.styleSheet()


def test_custom_scheme_applies_both_theme_modes(rig):
    create, app = rig
    panel = create()
    colors = custom_palette()
    scheme_id = panel.save_custom_color_scheme("Workshop", colors)
    panel.open_settings_panel()

    for mode in ("light", "dark"):
        if panel.theme_name != mode:
            panel.toggle_theme()
        app.processEvents()
        assert panel.color_scheme == scheme_id
        assert panel.color_scheme_combo.currentData() == scheme_id
        assert {role: panel.theme[role] for role in ROLES} == colors[mode]
        assert panel.theme == main.ControlPanel.theme_for(mode, scheme_id, panel.custom_color_schemes)
        for alias, role in ALIASES.items():
            assert panel.theme[alias] == colors[mode][role]
        assert colors[mode]["surface"] in panel.styleSheet()
        assert colors[mode]["surface"] in panel.toolbar_window.styleSheet()
        stored = json.loads(Path(main.CONFIG_FILE).read_text(encoding="utf-8"))
        assert (stored["theme"], stored["color_scheme"]) == (mode, scheme_id)


def test_delete_selected_custom_scheme_persists_classic_fallback(rig):
    create, app = rig
    panel = create()
    scheme_id = panel.save_custom_color_scheme("Workshop", custom_palette())
    panel.open_settings_panel()
    panel.delete_custom_color_scheme(scheme_id)
    app.processEvents()

    assert panel.custom_color_schemes == {}
    assert panel.color_scheme == "classic"
    assert panel.theme == main.ControlPanel.theme_for(panel.theme_name, "classic")
    assert panel.color_scheme_combo.currentData() == "classic"
    assert panel.color_scheme_combo.findData(scheme_id) == -1
    stored = json.loads(Path(main.CONFIG_FILE).read_text(encoding="utf-8"))
    assert stored["custom_color_schemes"] == {}
    assert stored["color_scheme"] == "classic"

    reopened = create()
    reopened.load_settings()
    assert reopened.custom_color_schemes == {}
    assert reopened.color_scheme == "classic"
    assert reopened.theme == main.ControlPanel.theme_for(reopened.theme_name, "classic")
