# SPDX-License-Identifier: GPL-3.0-or-later
"""Startup checks and persistent, clickable Settings update notification."""
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QToolButton

import main
from test_upgrade_settings import app, rig

CHECK_FOR_UPDATES = main.ControlPanel.check_for_updates


@pytest.fixture
def panel(rig, monkeypatch):
    value, _ = rig.fresh()
    monkeypatch.setattr(main, 'notify_user', Mock())
    return value


def test_startup_check_is_deferred_to_ui_loop_once_and_keeps_manual_check(panel, monkeypatch):
    assert panel.update_check_enabled is True
    calls = []
    monkeypatch.setattr(panel, 'check_for_updates', lambda: calls.append('check'))
    panel.schedule_startup_update_check()
    panel.schedule_startup_update_check()
    assert calls == []
    QTest.qWait(5)
    assert calls == ['check']
    assert panel.update_check_timer.isActive()
    panel.open_settings_panel()
    assert panel.btn_check_update.isEnabled()
    panel.btn_check_update.click()
    assert calls == ['check', 'check']


@pytest.mark.parametrize('disabled,private,stopping', [(True,False,False),(False,True,False),(False,False,True)])
def test_startup_no_check_for_disabled_private_or_stopping_runtime(panel, monkeypatch, disabled, private, stopping):
    panel.update_check_enabled = not disabled
    panel._updates_stopping = stopping
    monkeypatch.setattr(type(panel.runtime_context), 'updates', property(lambda self: not private))
    check = Mock()
    monkeypatch.setattr(panel, 'check_for_updates', check)
    panel.schedule_startup_update_check()
    QTest.qWait(5)
    check.assert_not_called()
    assert not panel.update_check_timer.isActive()


def test_available_update_has_neon_sticker_and_settings_click_does_not_dismiss(panel):
    panel.apply_theme()
    panel.set_ui_mode('icon', persist=False)
    panel._on_update_result({'tag':'v99.0.0'}, None)
    button = panel.icon_buttons['settings']
    indicator = button._update_indicator
    assert indicator.available and not indicator.isHidden()
    assert indicator.parentWidget() is button
    assert not indicator.isWindow()
    assert indicator.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert indicator.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert indicator.badge_text == 'NEW！'
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    assert panel.settings_panel.isVisible()
    panel.settings_panel.hide()
    assert indicator.available
    panel.toggle_theme()
    assert indicator.available
    panel.update_check_enabled = False
    panel.sync_settings_panel()
    assert indicator.available


@pytest.mark.parametrize('release,error', [(None,'timed out'),(None,'rate_limited'),(None,None),('invalid',None)])
def test_transient_failure_does_not_erase_known_update_or_indicator(panel, release, error):
    known = {'tag':'v99.0.0'}
    panel._on_update_result(known, None)
    panel._on_update_result(release, error)
    assert panel._pending_update_release == known
    assert panel.icon_buttons['settings']._update_indicator.available


@pytest.mark.parametrize('release', ['v99.0.0', {'tag':'v99.0.0'}])
def test_successful_current_check_clears_indicator(panel, release):
    panel._on_update_result(release, None)
    assert panel.icon_buttons['settings']._update_indicator.available
    panel._on_update_result({'tag': main.APP_VERSION}, None)
    assert panel._pending_update_release is None
    assert not panel.icon_buttons['settings']._update_indicator.available


def test_shutdown_result_cannot_turn_on_indicator(panel):
    panel._updates_stopping = True
    panel._on_update_result({'tag':'v99.0.0'}, None)
    assert panel._pending_update_release is None
    assert not panel.icon_buttons['settings']._update_indicator.available


def test_indicator_tracks_geometry_hides_and_resumes_without_extra_windows(app):
    from update_indicator import UpdateIndicator
    button = QToolButton()
    button.resize(80,56)
    indicator = UpdateIndicator(button)
    button.show()
    indicator.set_available(True)
    QTest.qWait(5)
    assert indicator.geometry() == button.rect()
    assert indicator.timer.isActive()
    before = set(app.topLevelWidgets())
    button.resize(120,80)
    QTest.qWait(5)
    assert indicator.geometry() == button.rect()
    assert set(app.topLevelWidgets()) == before
    button.hide()
    QTest.qWait(5)
    assert not indicator.timer.isActive()
    button.show()
    QTest.qWait(5)
    assert indicator.timer.isActive() and indicator.available
    indicator.set_available(False)
    assert not indicator.timer.isActive() and indicator.isHidden()
    button.hide(); button.deleteLater()


def test_old_disabled_preference_still_blocks_startup_request(rig, monkeypatch):
    panel, _ = rig.load({'update_check_enabled': False})
    check = Mock()
    monkeypatch.setattr(panel, 'check_for_updates', check)
    panel.schedule_startup_update_check()
    QTest.qWait(5)
    check.assert_not_called()
    assert not panel.update_check_timer.isActive()


def test_startup_and_manual_requests_share_one_running_worker(panel, monkeypatch):
    starts = []
    original = main.UpdateCheckWorker
    class HoldingWorker(original):
        def start(self):
            self.running = True
            starts.append(self)
        def isRunning(self):
            return getattr(self, 'running', False)
        def requestInterruption(self):
            self.running = False
        def wait(self, *args):
            self.running = False
            return True
    monkeypatch.setattr(main, 'UpdateCheckWorker', HoldingWorker)
    monkeypatch.setattr(panel, 'check_for_updates', lambda: CHECK_FOR_UPDATES(panel))
    panel.schedule_startup_update_check()
    QTest.qWait(5)
    panel.check_for_updates()
    panel.check_for_updates()
    assert len(starts) == 1
    starts[0].running = False
    starts[0].finished_check.emit({'tag':'v99.0.0'}, None)
    assert panel.icon_buttons['settings']._update_indicator.available


def test_update_indicator_survives_background_restore_and_collapse(panel):
    panel.set_ui_mode('icon', persist=False)
    panel._on_update_result({'tag':'v99.0.0'}, None)
    indicator = panel.icon_buttons['settings']._update_indicator
    panel.lifecycle.hide_to_background()
    QTest.qWait(5)
    assert not indicator.isVisible() and not indicator.timer.isActive()
    panel.lifecycle.restore_from_background()
    QTest.qWait(5)
    assert indicator.isVisible() and indicator.timer.isActive()
    panel.toggle_toolbar_collapsed()
    assert not indicator.isVisible() and indicator.available
    panel.toggle_toolbar_collapsed()
    assert indicator.isVisible() and indicator.available


def test_changing_release_channel_clears_candidate_and_both_indicators_together(panel):
    panel.open_settings_panel()
    panel._on_update_result({'tag':'v99.0.0'}, None)
    panel.update_channel_combo.setCurrentIndex(1)
    assert panel.update_channel == 'preview'
    assert panel._pending_update_release is None
    assert not panel.btn_download_update.isEnabled()
    for button in (panel.btn_settings, panel.icon_buttons['settings']):
        assert not button._update_indicator.available
        assert button.accessibleDescription() == ''
    panel._on_update_result(None, 'timed out')
    assert not panel.icon_buttons['settings']._update_indicator.available
