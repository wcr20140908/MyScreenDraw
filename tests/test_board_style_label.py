# SPDX-License-Identifier: GPL-3.0-or-later
"""Board switch text reflects its next action in both toolbar presentations."""
import i18n
from test_teaching_application import application_host, practice_request


def test_board_style_label_changes_immediately_and_survives_theme_refresh(application_host):
    host, _ = application_host
    host.context.activate()
    panel = host.panel
    panel.canvas.whiteboard_mode = True
    panel.canvas.board_style = 'WHITE'
    panel.update_whiteboard_ui()
    button = panel.icon_buttons['board_style']
    assert button.text() == i18n.tr('board')
    button.click()
    assert panel.canvas.board_style == 'BLACK'
    assert panel.btn_board_style.text() == i18n.tr('board_white')
    assert button.text() == i18n.tr('board_white')
    assert button.toolTip() == i18n.tr('board_white')
    assert button.accessibleName() == i18n.tr('board_white')
    panel.apply_theme()
    assert button.text() == i18n.tr('board_white')
    button.click()
    assert panel.canvas.board_style == 'WHITE'
    assert button.text() == i18n.tr('board')
