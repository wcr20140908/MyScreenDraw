# SPDX-License-Identifier: GPL-3.0-or-later
"""Optional runtime-path capability in existing lifecycle adapters."""
import pytest
from PyQt6.QtCore import QEvent

from test_teaching_application_lifecycle import rig


def test_suspended_minimal_lifecycle_context_stays_hidden_without_qt_callback_error(rig):
    rig.panel._teaching_suspended = True
    event = QEvent(QEvent.Type.Show)
    assert rig.manager._window_guard.eventFilter(rig.panel, event) is False
    assert not rig.panel.isVisible()


def test_minimal_lifecycle_context_cannot_claim_practice_window_exemption(rig):
    with pytest.raises(ValueError, match='active owned practice teaching window'):
        rig.manager.allow_practice_teaching_window(rig.registered)
