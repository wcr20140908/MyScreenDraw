# SPDX-License-Identifier: GPL-3.0-or-later
"""C07's original text stays clickable; only owned, offscreen Qt events are used."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('MYSCREENDRAW_NO_KEYBOARD', '1')
os.environ.setdefault('PYNPUT_BACKEND', 'dummy')

import pytest
from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QScreen
from PyQt6.QtWidgets import QApplication

from test_teaching_application_isolation import drain
from test_teaching_selection_occlusion import global_box
from test_teaching_text_courses import click_text, fixture_text_item, symbol_button
from test_teaching_writing_courses import writing_host, next_info, assert_step


@pytest.fixture(autouse=True)
def only_offscreen(monkeypatch):
    assert QApplication.instance().platformName() == 'offscreen'

    def forbidden(*args, **kwargs):
        pytest.fail('Text placement tests must not capture the native desktop')

    monkeypatch.setattr(QScreen, 'grabWindow', forbidden)
    import main
    monkeypatch.setattr(main.touch_keyboard, 'keyboard_rect', lambda: None)


def layout_scene(host, monkeypatch, origin, dpr):
    """Both placement paths use the same logical work area, not offscreen's 800x800."""
    area = QRect(origin[0], origin[1], 1463, 820)
    panel, presenter = host.panel, host.presenter
    import toolbar_windows
    # Split-toolbar heartbeat also clamps its owned windows; give it the same
    # work area or it silently drags a negative-origin scene back onto 800x800.
    monkeypatch.setattr(toolbar_windows, '_available_rect', lambda widget: QRect(area))
    monkeypatch.setattr(panel, 'screen_geometry', lambda *widgets: QRect(area))
    monkeypatch.setattr(presenter, '_available_geometry', lambda target: QRect(area))
    monkeypatch.setattr(panel.canvas, 'devicePixelRatioF', lambda: dpr)
    monkeypatch.setattr(panel, 'devicePixelRatioF', lambda: dpr)
    panel.canvas.setWindowState(Qt.WindowState.WindowNoState)
    panel.canvas.setGeometry(area)
    panel.show_only_sub(None)
    panel.toolbar_window.setFixedSize(128, area.height())
    panel.toolbar_window.move(area.topLeft())
    panel.logo_window.move(area.topLeft())
    presenter.controller.resize(736, 525)
    drain(QApplication.instance())
    panel.page_rail.move(area.right() + 1 - panel.page_rail.width(), area.top() + 400)
    presenter.refresh_layout()
    return area


def protected_samples(canvas, originals):
    # Measure the real fixture objects, not the production protection callback.
    # global_box independently maps camera/document coordinates into Qt logical
    # coordinates and adds 20 logical pixels, including on negative/DPR=2 screens.
    region = QRect()
    for item in originals:
        region = region.united(global_box(canvas, canvas.text_bounds(item), margin=20))
    assert not region.isEmpty()
    return region


def assert_samples_clear(host, area, originals):
    panel, controller = host.panel, host.presenter.controller
    protected = protected_samples(panel.canvas, originals)
    windows = [('controller', controller)]
    if getattr(panel, 'text_panel', None) is not None and panel.text_panel.isVisible():
        windows.append(('text_panel', panel.text_panel))
    for name, window in windows:
        rect = window.frameGeometry()
        assert area.contains(rect), (name, rect, area)
        assert not rect.intersects(protected), (name, rect, protected)
    if len(windows) == 2:
        assert not controller.frameGeometry().intersects(panel.text_panel.frameGeometry())
    return protected


def assert_layout_only(host, progress, area, originals):
    presenter, canvas = host.presenter, host.panel.canvas
    snapshot, records, document = presenter._snapshot(), list(progress), canvas.document_signature()
    # Real controller Resize events and a refresh must re-fit around both the
    # original objects and the input panel without completing/restarting a step.
    presenter.controller.resize(820, 560)
    presenter.refresh_layout()
    drain(QApplication.instance())
    assert_samples_clear(host, area, originals)
    assert presenter._snapshot() == snapshot
    assert progress == records
    assert canvas.document_signature() == document
    assert presenter.barrier.installed


@pytest.mark.parametrize('writing_host', ['c07.formula'], indirect=True)
@pytest.mark.parametrize('origin,dpr', [((0, 0), 1.0), ((-1800, -280), 2.0)])
def test_formula_originals_stay_clear_through_symbol_groups_and_open_formula(
        writing_host, monkeypatch, origin, dpr):
    host, progress = writing_host
    panel, canvas = host.panel, host.panel.canvas
    symbols = fixture_text_item(canvas, 'Symbols: ')
    formula_item = fixture_text_item(canvas, 'F = ')
    originals = (symbols, formula_item)
    original_ids = {item['id'] for item in originals}
    area = layout_scene(host, monkeypatch, origin, dpr)

    next_info(host)
    assert_step(host, 'choose_text')
    panel.btn_text.click()
    assert_step(host, 'open_symbols')
    assert_samples_clear(host, area, originals)
    click_text(panel, symbols)
    assert_step(host, 'greek')
    drain(QApplication.instance())
    # Negative control: the old toolbar-only anchor really covers the live F
    # target on this scene. A trivially clear fixture cannot pass this regression.
    old_x, old_y = panel._floating_anchor(panel.text_panel.width(), panel.text_panel.height(), gap=6)
    old_panel = QRect(old_x, old_y, panel.text_panel.width(), panel.text_panel.height())
    assert old_panel.intersects(global_box(canvas, canvas.text_bounds(formula_item))), old_panel

    sizes = set()
    for step, group, entry in (
            ('greek', 'greek', 'α'), ('operator', 'operator', '±'),
            ('relation', 'relation', '∈'), ('calculus', 'calculus', '∫')):
        drain(QApplication.instance())
        assert_step(host, step)
        assert panel._open_symbol_group == group
        sizes.add((panel.text_panel.width(), panel.text_panel.height()))
        assert_samples_clear(host, area, originals)
        assert_layout_only(host, progress, area, originals)
        symbol_button(panel, entry).click()

    drain(QApplication.instance())
    assert_step(host, 'open_formula')
    assert_samples_clear(host, area, originals)
    assert len(sizes) > 1, 'Exercise real symbol-grid resizing, not a fixed fake panel'
    assert all(symbol in symbols['text'] for symbol in ('α', '±', '∈', '∫'))
    assert formula_item['text'] == 'F = '
    # Never send a synthetic click through an occluding top-level window: the
    # geometry assertions above must pass before clicking the actual F object.
    click_text(panel, formula_item)
    assert canvas.editing_text_id == formula_item['id']
    assert_step(host, 'structure')
    panel._symbol_group_buttons['structure'].click()
    drain(QApplication.instance())
    assert_step(host, 'frac')
    assert_samples_clear(host, area, originals)
    assert_layout_only(host, progress, area, originals)
    assert {item['id'] for item in canvas.text_items} == original_ids


@pytest.mark.parametrize('writing_host', ['c07.formula'], indirect=True)
def test_dynamic_symbol_press_survives_input_refocus(writing_host, monkeypatch):
    from PyQt6.QtTest import QTest
    host, _ = writing_host
    panel, canvas = host.panel, host.panel.canvas
    formula_item = fixture_text_item(canvas, 'F = ')
    layout_scene(host, monkeypatch, (0, 0), 1.0)
    next_info(host); panel.btn_text.click()
    click_text(panel, fixture_text_item(canvas, 'Symbols: '))
    for step, entry, following in (
            ('greek', 'α', 'operator'), ('operator', '±', 'relation'),
            ('relation', '∈', 'calculus'), ('calculus', '∫', 'open_formula'),
            ('frac', 'frac', 'frac_num')):
        if step == 'frac':
            click_text(panel, formula_item)
            panel._symbol_group_buttons['structure'].click()
        drain(QApplication.instance())
        assert_step(host, step)
        panel.text_panel.activateWindow()
        panel.text_input.setFocus()
        drain(QApplication.instance())
        button = symbol_button(panel, entry)
        QTest.mousePress(button, Qt.MouseButton.LeftButton)
        try:
            assert button.isDown()
            # This is the heartbeat's production focus-repair path, deliberately
            # between DOWN and UP instead of a timing-dependent timer race.
            panel._refocus_input()
            assert button.isDown(), 'Input refocus cancelled the pending symbol click'
        finally:
            QTest.mouseRelease(button, Qt.MouseButton.LeftButton)
        assert_step(host, following)
    assert formula_item.get('formula') is not None
    assert canvas.editing_slot[-1] == 'num'


@pytest.mark.parametrize('writing_host', ['c07.formula'], indirect=True)
def test_non_teaching_text_panel_keeps_ordinary_anchor_and_user_position(writing_host, monkeypatch):
    host, _ = writing_host
    panel = host.panel
    area = layout_scene(host, monkeypatch, (0, 0), 1.0)
    host.presenter.engine.stop()
    monkeypatch.setattr(panel, 'teaching_presenter', None)
    panel._build_text_panel()
    panel._position_text_panel(force=True)
    expected = QPoint(*panel._floating_anchor(panel.text_panel.width(), panel.text_panel.height(), gap=6))
    assert panel.text_panel.pos() == expected
    panel.text_panel.show()
    # A user-moved ordinary panel remains where it was on non-forced refresh;
    # tutorial-specific avoidance must not leak into normal editor placement.
    spot = area.topLeft() + QPoint(760, 30)
    panel.text_panel.move(spot)
    document = panel.canvas.document_signature()
    for group in ('greek', 'operator', 'calculus'):
        panel._symbol_group_buttons[group].click()
        drain(QApplication.instance())
        assert area.contains(panel.text_panel.frameGeometry())
        assert panel.text_panel.pos() == spot
    assert panel.canvas.document_signature() == document
