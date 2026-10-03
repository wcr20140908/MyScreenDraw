# SPDX-License-Identifier: GPL-3.0-or-later
"""Exercise real show/restore entry points offscreen with native calls replaced."""
from unittest.mock import Mock
import pytest
from test_upgrade_settings import app, rig


def observe_taskbar(rig, monkeypatch, panel):
    mark = Mock()
    monkeypatch.setattr(rig.main, "mark_tool_window", mark)
    monkeypatch.setattr(rig.main, "set_window_owner", Mock())
    monkeypatch.setattr(rig.main, "enforce_topmost_order", Mock(return_value=(False, None, set())))
    monkeypatch.setattr(panel, "heartbeat_refresh", Mock())
    return mark


@pytest.mark.parametrize("opener,attribute", [
    ("open_calculator", "calc_panel"), ("open_settings_panel", "settings_panel"),
    ("open_roster_panel", "roster_panel"),
])
def test_reopened_tools_reapply_taskbar_rule_without_waiting_for_heartbeat(rig, monkeypatch, opener, attribute):
    panel, canvas = rig.fresh()
    mark = observe_taskbar(rig, monkeypatch, panel)
    for _ in range(2):
        mark.reset_mock()
        getattr(panel, opener)()
        window = getattr(panel, attribute)
        assert window.parent() is None  # Do not regress native-owner/text-focus contract.
        assert window.isVisible()
        mark.assert_any_call(int(window.winId()))
        window.hide()


def test_toolbar_expansion_reapplies_taskbar_rule(rig, monkeypatch):
    panel, canvas = rig.fresh()
    mark = observe_taskbar(rig, monkeypatch, panel)
    panel.toolbar_window.hide()
    panel.toggle_toolbar_collapsed()
    assert panel.toolbar_window.isVisible()
    mark.assert_any_call(int(panel.toolbar_window.winId()))


def test_background_tray_settings_is_marked_without_waking_canvas(rig, monkeypatch):
    panel, canvas = rig.fresh()
    mark = observe_taskbar(rig, monkeypatch, panel)
    panel.lifecycle.hide_to_background()
    mark.reset_mock()
    panel.lifecycle._open_settings_from_tray()
    assert panel.settings_panel.isVisible()
    assert not canvas.isVisible()
    mark.assert_any_call(int(panel.settings_panel.winId()))


def test_full_restore_rechecks_existing_window_handles(rig, monkeypatch):
    panel, canvas = rig.fresh()
    mark = observe_taskbar(rig, monkeypatch, panel)
    panel.show()
    canvas.show()
    panel.open_calculator()
    handles = [int(w.winId()) for w in (panel, canvas, panel.calc_panel, panel.logo_window)]
    panel.lifecycle.hide_to_background()
    mark.reset_mock()
    panel.lifecycle.restore_from_background()
    for hwnd in handles:
        mark.assert_any_call(hwnd)
    assert not canvas.is_drawing_mode
