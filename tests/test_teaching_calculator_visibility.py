# SPDX-License-Identifier: GPL-3.0-or-later
"""Opening the calculator must survive its source button becoming hidden."""
import pytest

from test_teaching_toolbox_interface import qt_slot_failures
from test_teaching_writing_courses import writing_host, next_info


@pytest.mark.parametrize('writing_host', ['c12.calculator', 'c12.scientific_calculator'], indirect=True)
def test_calculator_open_result_survives_nested_source_visibility_check(writing_host, monkeypatch):
    host, _ = writing_host
    panel = host.panel
    next_info(host)
    assert host.presenter.engine.current_step_id == 'open'
    button = panel.tool_menu_buttons['open_calculator']
    assert button.isVisible()
    raised = panel.raise_floating
    checks = []
    def nested_visibility(window):
        result = raised(window)
        if window is panel.calc_panel:
            checks.append(button.isVisible())
            host.presenter._targets_changed()
        return result
    monkeypatch.setattr(panel, 'raise_floating', nested_visibility)
    button.click()
    assert checks == [False]
    assert host.presenter.engine.phase == 'running'
    assert host.presenter.engine.current_step_id == (
        'two' if host.request.chapter_id == 'c12.calculator' else 'mode')
    assert not host.presenter._missing and not host.presenter.engine._issued


@pytest.mark.parametrize('writing_host', ['c12.calculator', 'c12.scientific_calculator'], indirect=True)
def test_calculator_chapter_switch_keeps_new_fixture_window_closed(writing_host, tmp_path):
    from teaching.session_view import parent_progress_view
    from teaching.state import TutorialStateStore
    host, _ = writing_host
    panel = host.panel
    next_info(host)
    panel.tool_menu_buttons['open_calculator'].click()
    assert panel.calc_panel.isVisible()
    assert host.request_center()
    host.accept_center(parent_progress_view(host.catalog, TutorialStateStore(tmp_path / 'progress.json')))
    next_chapter = ('c12.scientific_calculator' if host.request.chapter_id == 'c12.calculator'
                    else 'c12.calculator')
    host.prepare_chapter_change()
    host.prepare_chapter('c12', next_chapter)
    assert not panel.calc_panel.isVisible()
    host.commit_chapter()
    assert not panel.calc_panel.isVisible()
    assert host.presenter.engine.current_step_id == 'intro'
    next_info(host)
    panel.tool_menu_buttons['open_calculator'].click()
    assert host.presenter.engine.phase == 'running'
    assert host.presenter.engine.current_step_id == (
        'mode' if next_chapter == 'c12.scientific_calculator' else 'two')


@pytest.mark.parametrize('writing_host', ['c12.calculator', 'c12.scientific_calculator'], indirect=True)
def test_calculator_fixture_clears_both_drafts_and_repeat_equals_state(writing_host):
    from teaching.toolbox_fixtures import prepare_toolbox_fixture
    host, _ = writing_host
    panel = host.panel
    widget = panel.calculator_widget
    for mode, expression in [('scientific', '11+2'), ('basic', '4+5')]:
        widget.set_mode(mode)
        widget._set_expression(expression)
        widget.commit_expression()
        assert widget._just_committed
    widget.history_toggle.setChecked(True)
    widget.history_search.setText('previous private filter')
    widget.history_filter.setCurrentIndex(1)
    fixture = host.catalog.chapter_by_id(host.request.chapter_id).fixture
    prepare_toolbox_fixture(panel, fixture, host.request.paths)
    assert widget.drafts == {'basic': '0', 'scientific': '0'}
    assert widget.engine.ans == widget.engine.memory == 0
    assert not widget.history.entries
    assert not widget.history_toggle.isChecked()
    assert not widget.history_search.text() and widget.history_filter.currentData() is None
    widget.set_mode('scientific')
    assert not widget._just_committed
    widget.commit_expression()
    assert len(widget.history.entries) == 1 and widget.history.entries[0].result == '0'
