# SPDX-License-Identifier: GPL-3.0-or-later
"""Legacy style test ownership cannot leak config writers into following tests."""
from PyQt6 import sip


def test_style_fixture_disposes_pending_split_save_and_owned_windows():
    from test_pen_styles import PenStyleTestCase

    probe = type("StyleCleanupProbe", (PenStyleTestCase,), {})
    probe.setUpClass()
    panel = probe.panel
    panel.choose_pen_style("fountain")
    assert panel._split_save_timer.isActive()
    owned_windows = set(probe.app.topLevelWidgets()) - probe._initial_windows
    assert panel in owned_windows

    probe.tearDownClass()

    assert all(sip.isdeleted(window) for window in owned_windows)
    assert set(probe.app.topLevelWidgets()) == probe._initial_windows
