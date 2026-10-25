# SPDX-License-Identifier: GPL-3.0-or-later
"""Real Qt behavior for the five-mode calculator panel."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QBoxLayout
import pytest

from calculator_history import CalculatorHistoryStore
import calculator_panel


@pytest.fixture
def panel(tmp_path):
    app = QApplication.instance() or QApplication([])
    events = []
    history = CalculatorHistoryStore(tmp_path / "history.json", retention="session")
    value = calculator_panel.CalculatorPanel(
        history,
        translate=lambda key: key,
        event_callback=lambda name, **payload: events.append((name, payload)),
    )
    value.show()
    QTest.qWait(10)
    yield value, history, events
    value.hide()
    value.deleteLater()
    app.processEvents()


def test_basic_page_preserves_legacy_button_codes_and_commits_once(panel):
    value, history, events = panel
    assert tuple(value.basic_buttons) == (
        "C", "B", "%", "/", "7", "8", "9", "*", "4", "5", "6", "-",
        "1", "2", "3", "+", "N", "0", ".", "=",
    )

    for code in ("2", "+", "3"):
        value.basic_buttons[code].click()
    assert value.expression_edit.text() == "2+3"
    assert value.preview_label.text() == "5"
    assert history.entries == []

    value.basic_buttons["="].click()
    assert value.expression_edit.text() == "5"
    assert [entry.result for entry in history.entries] == ["5"]
    assert all("expression" not in payload and "result" not in payload for _, payload in events)


def test_scientific_preview_commit_ans_and_second_functions(panel):
    value, history, _ = panel
    value.set_mode("scientific")
    value.expression_edit.setText("sin(30)+√16")
    assert value.preview_label.text() == "4.5"
    assert history.entries == []

    value.commit_expression()
    assert value.expression_edit.text() == "4.5"
    value.expression_edit.setText("Ans×2")
    value.commit_expression()
    assert value.expression_edit.text() == "9"
    assert [entry.mode for entry in history.entries] == ["scientific", "scientific"]

    assert value.scientific_buttons["trig1"].text() == "sin"
    value.scientific_buttons["second"].click()
    assert value.scientific_buttons["trig1"].text() == "asin"


def test_unit_statistics_and_base_require_explicit_history_commit(panel):
    value, history, _ = panel
    value.set_mode("unit")
    value.unit_value.setText("1000")
    value.unit_category.setCurrentIndex(value.unit_category.findData("length"))
    value.unit_source.setCurrentText("mm")
    value.refresh_unit_results()
    assert history.entries == []
    meter = next(index for index in range(value.unit_results.count())
                 if value.unit_results.item(index).data(Qt.ItemDataRole.UserRole)[0] == "m")
    value.unit_results.setCurrentRow(meter)
    value.save_unit_result()
    assert history.entries[-1].mode == "unit" and history.entries[-1].result == "1 m"

    value.set_mode("statistics")
    value.statistics_input.setPlainText("1,2,3,4,5")
    value.calculate_statistics()
    assert history.entries[-1].mode == "statistics"
    assert history.entries[-1].payload["summary"]["mean"] == "3"

    value.set_mode("base")
    value.base_source.setCurrentIndex(value.base_source.findData(16))
    value.base_target.setCurrentIndex(value.base_target.findData(10))
    value.base_input.setText("0xff")
    assert value.base_result.text() == "255"
    before = len(history.entries)
    value.save_base_result()
    assert len(history.entries) == before + 1
    assert history.entries[-1].mode == "base"


def test_history_search_restore_and_responsive_layout(panel):
    value, history, _ = panel
    history.add("basic", "2+3", "5")
    history.add("scientific", "sin(30)", "0.5")
    value.refresh_history()
    value.history_search.setText("sin")
    assert value.history_list.count() == 1
    value.history_list.setCurrentRow(0)
    value.restore_selected_history()
    assert value.mode == "scientific"
    assert value.expression_edit.text() == "sin(30)"

    value.history_toggle.setChecked(True)
    value.resize(900, 500)
    value.update_responsive_layout()
    assert value.body_layout.direction() == QBoxLayout.Direction.LeftToRight
    value.resize(500, 700)
    value.update_responsive_layout()
    assert value.body_layout.direction() == QBoxLayout.Direction.TopToBottom


def test_stack_size_hint_tracks_active_page_instead_of_tallest_hidden_page(panel):
    value, _, _ = panel
    value.set_mode('statistics')
    tall_hint = value.stack.sizeHint().height()
    value.set_mode('base')
    assert value.stack.sizeHint().height() < tall_hint
    assert value.stack.sizeHint().height() == value.pages['base'].sizeHint().height()


def test_keyboard_after_commit_starts_new_number_and_repeated_enter_is_idempotent(panel):
    value, history, _ = panel
    value.expression_edit.setText('2+3')
    QTest.keyClick(value.expression_edit, Qt.Key.Key_Return)
    QTest.keyClick(value.expression_edit, Qt.Key.Key_Return)
    assert len(history.entries) == 1
    QTest.keyClicks(value.expression_edit, '7')
    assert value.expression_edit.text() == '7'


def test_keypad_respects_selection_and_caret_and_scientific_starts_without_zero(panel):
    value, _, _ = panel
    value.expression_edit.setText('1234')
    value.expression_edit.setCursorPosition(2)
    value.basic_buttons['B'].click()
    assert value.expression_edit.text() == '134'
    value.expression_edit.setSelection(1, 1)
    value.basic_buttons['8'].click()
    assert value.expression_edit.text() == '184'
    value.set_mode('scientific')
    value.scientific_buttons['trig1'].click()
    assert value.expression_edit.text() == 'sin('


def test_copy_retains_original_expression_and_full_result_after_commit(panel):
    value, _, _ = panel
    value.expression_edit.setText('1/7')
    full = value.engine.calculate('1/7').full_text
    value.commit_expression()
    value.copy_result()
    assert QApplication.clipboard().text() == full
    value.copy_input()
    assert QApplication.clipboard().text() == '1/7'
    value.copy_equation()
    assert QApplication.clipboard().text() == f'1/7 = {full}'


def test_large_result_continuation_is_independent_of_other_modes_ans(panel):
    value, history, _ = panel
    value.expression_edit.setText('2^2000')
    value.commit_expression()
    value.set_mode('scientific')
    value.expression_edit.setText('7')
    value.commit_expression()
    value.set_mode('basic')
    value.input_code('+')
    value.input_code('1')
    assert value.engine.ans == 7  # Preview does not commit an answer.
    value.commit_expression()
    assert value.engine.ans == 2**2000 + 1
    entry = history.entries[-1]
    value.refresh_history()
    value.history_list.setCurrentRow(0)
    value.restore_selected_history()
    assert value._last_preview.value == 2**2000 + 1


def test_large_exponents_in_statistics_stay_compact_in_history(panel):
    value, history, _ = panel
    value.set_mode('statistics')
    value.statistics_input.setPlainText(';'.join(['1e9000'] * 60))
    value.calculate_statistics()
    assert len(history.entries) == 1
    assert len(history.entries[0].input) < 1000
    assert not value.storage_status.text()


def test_statistics_locale_history_snapshot_and_invalid_item_position(panel):
    value, history, events = panel
    from i18n import TEXT
    value.t = lambda key: TEXT['en'].get(key, key)
    value.decimal_separator = ','
    value.set_mode('statistics')
    value.statistics_input.setPlainText('1,5; 2,5')
    value.calculate_statistics()
    assert history.entries[-1].input == '1.5; 2.5'
    assert history.entries[-1].result == '2'
    assert all('count' not in payload for _, payload in events)
    value.decimal_separator = '.'
    value.refresh_history()
    value.history_list.setCurrentRow(0)
    value.restore_selected_history()
    assert value.statistics_input.toPlainText() == '1.5; 2.5'
    assert value.statistics_results.count() == 9
    value.statistics_input.setPlainText('1;bad;3')
    value.calculate_statistics()
    assert '2' in value.statistics_error.text()
    assert len(history.entries) == 1



def test_unit_locale_history_restores_selected_pair_and_can_promote_target(panel):
    value, history, _ = panel
    value.decimal_separator = ','
    value.set_mode('unit')
    value.unit_category.setCurrentIndex(value.unit_category.findData('length'))
    value.unit_source.setCurrentText('mm')
    value.unit_value.setText('1,5')
    target = next(index for index in range(value.unit_results.count())
                  if value.unit_results.item(index).data(Qt.ItemDataRole.UserRole)[0] == 'm')
    value.unit_results.setCurrentRow(target)
    value.save_unit_result()
    entry = history.entries[-1]
    assert entry.input == '1.5 mm' and entry.result == '0.0015 m'
    value.decimal_separator = '.'
    value.refresh_history()
    value.history_list.setCurrentRow(0)
    value.restore_selected_history()
    assert value.unit_value.text() == '1.5'
    assert value.unit_source.currentText() == 'mm'
    assert value.unit_results.currentItem().data(Qt.ItemDataRole.UserRole)[0] == 'm'
    value.copy_result()
    assert QApplication.clipboard().text() == '0.0015'
    value.unit_promote.click()
    assert value.unit_value.text() == '0.0015'
    assert value.unit_source.currentText() == 'm'
    assert history.entries == [entry]


def test_five_modes_keep_unsubmitted_drafts_without_writing_history(panel):
    value, history, _ = panel
    value.expression_edit.setText('2+3')
    value.set_mode('scientific')
    value.expression_edit.setText('sin(30)')
    value.set_mode('unit')
    value.unit_value.setText('12.5')
    value.set_mode('statistics')
    value.statistics_input.setPlainText('4; 5; 6')
    value.set_mode('base')
    value.base_source.setCurrentIndex(value.base_source.findData(16))
    value.base_input.setText('ff')
    for mode in ('basic', 'scientific', 'unit', 'statistics', 'base'):
        value.set_mode(mode)
        if mode == 'basic': assert value.expression_edit.text() == '2+3'
        elif mode == 'scientific': assert value.expression_edit.text() == 'sin(30)'
        elif mode == 'unit': assert value.unit_value.text() == '12.5'
        elif mode == 'statistics': assert value.statistics_input.toPlainText() == '4; 5; 6'
        else: assert value.base_input.text() == 'ff'
    assert history.entries == []
    assert not history.path.exists()


def test_history_uses_compact_display_but_copies_full_precision(panel):
    value, history, _ = panel
    value.set_mode('scientific')
    value.expression_edit.setText('sin(30)+√16')
    value.commit_expression()
    entry = history.entries[-1]
    assert value.history_list.item(0).text().endswith('= 4.5')
    value.history_list.setCurrentRow(0)
    value.copy_selected_history()
    assert QApplication.clipboard().text() == entry.result
    assert entry.result != '4.5'
