# SPDX-License-Identifier: GPL-3.0-or-later
"""Collapsing the toolbar closes settings without reopening it on heartbeat."""
import inspect
import textwrap

import pytest
from PyQt6.QtWidgets import QApplication

import main
from app_lifecycle import LifecycleState


@pytest.fixture
def panel():
    assert QApplication.instance().platformName() == "offscreen"
    value = main.ControlPanel()
    value.canvas = main.DrawingCanvas(value)
    value.update_check_timer.stop()
    value.timer.stop()
    value.autosave_timer.stop()
    value.apply_theme()
    value.show()
    value.logo_window.show()
    value.toolbar_window.show()
    value.canvas.show()
    yield value
    from conftest import _dispose_offscreen_widgets
    _dispose_offscreen_widgets(QApplication.instance(), [value.canvas, value])


def collapse_contract(panel):
    panel.open_settings_panel()
    settings = panel.settings_panel
    assert settings is not None and settings.isVisible()
    assert panel.toolbar_window.isVisible()
    before = panel.canvas.document_signature()
    panel.toggle_toolbar_collapsed()
    assert settings.isHidden(), "Collapsing the main toolbar must close settings"
    assert panel.toolbar_window.isHidden()
    assert panel.lifecycle.state == LifecycleState.COLLAPSED
    for _ in range(3):
        panel.heartbeat_refresh()
        QApplication.instance().processEvents()
    assert settings.isHidden() and panel.toolbar_window.isHidden()
    assert panel.logo_window.isVisible() and panel.canvas.isVisible()
    panel.toggle_collapsed()
    assert panel.toolbar_window.isVisible()
    assert panel.lifecycle.state == LifecycleState.SHOWING
    panel.heartbeat_refresh()
    assert settings.isHidden(), "Expanding the toolbar must not reopen settings"
    panel.open_settings_panel()
    assert panel.settings_panel is settings and settings.isVisible()
    assert panel.canvas.document_signature() == before


@pytest.mark.parametrize("orientation", ["portrait", "landscape"])
@pytest.mark.parametrize("whiteboard", [False, True])
def test_collapse_closes_settings_until_explicitly_reopened(panel, orientation, whiteboard):
    panel.set_orientation(orientation)
    if whiteboard:
        panel.toggle_whiteboard()
    collapse_contract(panel)


def test_collapse_does_not_construct_unopened_settings(panel):
    assert panel.settings_panel is None
    panel.toggle_toolbar_collapsed()
    assert panel.settings_panel is None
    assert panel.lifecycle.state == LifecycleState.COLLAPSED
    panel.toggle_toolbar_collapsed()
    assert panel.settings_panel is None
    assert panel.lifecycle.state == LifecycleState.SHOWING


def test_collapse_regression_rejects_original_settings_left_open(panel, monkeypatch):
    source = textwrap.dedent(inspect.getsource(main.ControlPanel.toggle_toolbar_collapsed))
    removal = '        if self.settings_panel is not None:\n            self.settings_panel.hide()\n'
    assert source.count(removal) == 1
    namespace = dict(vars(main))
    exec(compile(source.replace(removal, ""), "<original-collapse>", "exec"), namespace)
    monkeypatch.setattr(main.ControlPanel, "toggle_toolbar_collapsed", namespace["toggle_toolbar_collapsed"])
    with pytest.raises(AssertionError, match="Collapsing the main toolbar must close settings"):
        collapse_contract(panel)
