# SPDX-License-Identifier: GPL-3.0-or-later
"""Native lesson driver checks with fake input only; never touch the desktop."""
import ast
import importlib.util
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QListWidget, QListWidgetItem

ROOT = Path(__file__).resolve().parents[1]


def native_driver():
    path = ROOT / 'tests/real_teaching_620.py'
    spec = importlib.util.spec_from_file_location('calculator_native_driver', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_catalog_counts_and_native_science_plan():
    module = native_driver()
    rows = module.catalog_rows()
    assert len(rows) == 48
    assert sum(len(chapter['steps']) for chapter in rows.values()) == 412
    science = rows['c12.scientific_calculator']
    assert len(science['steps']) == 11
    assert [module.classify(science['id'], step) for step in science['steps']] == [
        'next', *(['toolbox'] * 9), 'next']
    with pytest.raises(ValueError, match='unmapped scientific'):
        module.classify(science['id'], {'id': 'future_science', 'target': 'calculator.expression'})


def test_native_self_check_runs_without_gui_or_input():
    checked = subprocess.run([sys.executable, '-B', str(ROOT / 'tests/real_teaching_620.py'),
                              '--self-check'], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert checked.returncode == 0, checked.stderr
    assert '48 chapters / 412 catalog steps classified' in checked.stdout
    assert 'No native chapter, screenshot, or business acceptance has been run.' in checked.stdout


def test_science_driver_has_no_direct_business_or_synthetic_qt_actions():
    tree = ast.parse((ROOT / 'tests/real_teaching_620.py').read_text('utf-8'))
    driver = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                  and node.name == 'ChapterDriver')
    science = next(node for node in driver.body if isinstance(node, ast.FunctionDef)
                   and node.name == 'execute_scientific_calculator')
    attributes = {node.func.attr for node in ast.walk(science) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute)}
    assert not attributes & {'setText', 'setValue', 'setCurrentItem', 'setCurrentRow', 'emit',
                             'sendEvent', 'calculate', 'submit', 'restore_selected_history', 'set_mode'}
    assert {'text', 'chord', 'click_point'} <= attributes


@pytest.mark.parametrize('name,expression,preview', [
    ('expression', 'sin(30)+√16', '4.5'), ('ans_expression', 'Ans×2', '9')])
def test_science_expressions_use_owned_native_keyboard(name, expression, preview):
    module = native_driver()
    calls = []
    window = object()
    edit = SimpleNamespace(window=lambda: window, text=lambda: expression)
    mouse = SimpleNamespace(click=lambda target: calls.append(('click', target)),
        chord=lambda *keys, **kw: calls.append(('chord', keys, kw)),
        text=lambda value, **kw: calls.append(('text', value, kw)))
    widget = SimpleNamespace(preview_label=SimpleNamespace(text=lambda: preview),
        history=SimpleNamespace(retention='session', persistent=False))
    def require(label, condition, *details):
        assert condition, (label, details)
    driver = module.ChapterDriver.__new__(module.ChapterDriver)
    driver.panel = SimpleNamespace(calculator_widget=widget)
    driver.h = SimpleNamespace(mouse=mouse, require=require)
    driver.target = lambda: edit
    driver.pump = lambda ms: None
    driver.execute_toolbox('c12.scientific_calculator', name)
    assert calls == [('click', edit), ('chord', (0x11, 0x41), {'expected': window}),
                     ('text', expression, {'expected': window})]


def test_science_history_clicks_record_id_and_not_similar_result():
    module = native_driver()
    listing = QListWidget()
    listing.resize(600, 200)
    entries = [SimpleNamespace(id='first', mode='scientific', input='sin(30)+√16', result='4.49999999999999994'),
               SimpleNamespace(id='second', mode='scientific', input='Ans×2', result='9')]
    # A distracting row also contains 4.5: result substring matching would pick it.
    for entry_id, text in [('wrong', '45 / 10 = 4.5'), ('first', 'sin(30)+√16 = 4.49999999999999994'),
                           ('second', 'Ans×2 = 9')]:
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, entry_id)
        listing.addItem(item)
    listing.show()
    QApplication.instance().processEvents()
    clicked = []
    def require(label, condition, *details):
        assert condition, (label, details)
    widget = SimpleNamespace(history=SimpleNamespace(entries=entries, retention='session', persistent=False),
        expression_edit=SimpleNamespace(text=lambda: 'sin(30)+√16'), mode='scientific',
        engine=SimpleNamespace(angle_mode='deg'))
    driver = module.ChapterDriver.__new__(module.ChapterDriver)
    driver.panel = SimpleNamespace(calculator_widget=widget)
    driver.h = SimpleNamespace(require=require, mouse=SimpleNamespace(click_point=clicked.append))
    driver.target = lambda: listing
    driver.pump = lambda ms: None
    try:
        driver.execute_toolbox('c12.scientific_calculator', 'history_restore')
        assert clicked == [listing.viewport().mapToGlobal(listing.visualItemRect(listing.item(1)).center())]
    finally:
        listing.hide()
        listing.deleteLater()


@pytest.mark.parametrize('name,canonical,full_result,display', [
    ('calculate', 'sin(30)+√16', '4.49999999999999994', '4.5'),
    ('ans_calculate', 'Ans*2', '8.99999999999999988', '9')])
def test_native_science_submission_accepts_canonical_full_precision_history(
        name, canonical, full_result, display):
    module = native_driver()
    entry = SimpleNamespace(mode='scientific', input=canonical, result=full_result)
    widget = SimpleNamespace(expression_edit=SimpleNamespace(text=lambda: display),
        history=SimpleNamespace(entries=[entry], retention='session', persistent=False))
    def require(label, condition, *details):
        assert condition, (label, details)
    driver = module.ChapterDriver.__new__(module.ChapterDriver)
    driver.panel = SimpleNamespace(calculator_widget=widget)
    driver.h = SimpleNamespace(require=require)
    driver.click_target = lambda: None
    driver.execute_toolbox('c12.scientific_calculator', name)
