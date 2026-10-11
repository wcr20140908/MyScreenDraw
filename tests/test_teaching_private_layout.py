# SPDX-License-Identifier: GPL-3.0-or-later
"""Private chapter layouts may change size; original-work tokens stay exact."""
import pytest
from PyQt6.QtCore import QRect

from app_lifecycle import AppLifecycleManager
from test_teaching_core_course import core_host
from test_teaching_private_center import accepted_center
from test_teaching_application_lifecycle import rig


@pytest.mark.parametrize('core_host', ['c01.interface'], indirect=True)
def test_switch_to_whiteboard_fixture_can_restore_new_toolbar_size(core_host, tmp_path):
    host, _ = core_host
    # Finish this chapter honestly through the already validated business path.
    from test_teaching_business_adapters import draw_ink
    host.presenter.controller.next_button.click()
    host.panel.handle_pen_click()
    draw_ink(host.panel.canvas)
    host.panel.toggle_mode()
    host.panel.toggle_mode()
    assert host.presenter.engine.phase == 'completed'
    accepted_center(host, tmp_path)
    token = host._center_token
    toolbar = host.panel.toolbar_window
    original_height = toolbar.height()
    host.prepare_chapter_change()
    host.prepare_chapter('c01', 'c01.ink')
    assert toolbar.height() != original_height
    host.commit_chapter()
    assert token.restored and not host.panel._teaching_suspended
    assert host.presenter.engine.phase == 'running'
    assert host.presenter.engine.current_step_id == 'color'
    assert toolbar.isVisible() and host.panel.draw_sub.isVisible()


def test_normal_context_cannot_relax_original_window_geometry(rig):
    token = rig.manager.suspend_for_teaching()
    before = token.windows
    with pytest.raises(ValueError, match='active private practice'):
        rig.manager.restore_practice_after_chapter_change(token)
    assert token.windows is before and rig.panel._teaching_suspended
    rig.manager.restore_after_teaching(token)
    assert token.restored
