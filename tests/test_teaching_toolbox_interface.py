# SPDX-License-Identifier: GPL-3.0-or-later
"""Small C12/C13 check: real private Qt methods, no screen/input/system effects."""
import json
from pathlib import Path
import shutil
import sys
import traceback

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

from persistence import PROJECT_KIND, normalize_project_data
from teaching.catalog import CatalogLoader
from teaching.application import APPLICATION_EVENTS, APPLICATION_TARGETS
from teaching.engine import TutorialEngine
from teaching.events import TeachingEventBus
from teaching.models import TutorialCatalog
from teaching.toolbox_copy import TOOLBOX_COPY
from teaching.toolbox_fixtures import TOOLBOX_FIXTURES, prepare_toolbox_fixture
from teaching.interface_copy import INTERFACE_COPY
from teaching.interface_fixtures import INTERFACE_FIXTURES, prepare_interface_fixture
from test_teaching_application import application_host, practice_request

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def qt_slot_failures(monkeypatch):
    errors = []
    def capture(exc_type, exception, tb):
        details = ''.join(traceback.format_exception(exc_type, exception, tb))
        errors.append(details)
        sys.__stderr__.write(details)
    monkeypatch.setattr(sys, 'excepthook', capture)
    yield
    if errors:
        pytest.fail('Unhandled Qt slot exception(s):\n' + '\n'.join(errors), pytrace=False)


def courses():
    import i18n
    loader = CatalogLoader(ROOT / 'assets/tutorials',
        string_keys=set(i18n.TEXT['zh']),
        target_ids=set(APPLICATION_TARGETS),
        event_names=set(APPLICATION_EVENTS),
        fixtures={fixture: 'fixtures/' + fixture + '.msd'
                  for fixture in TOOLBOX_FIXTURES | INTERFACE_FIXTURES})
    return tuple(loader.validate(json.loads((loader.root / 'courses' / (key + '.json')).read_text(
        encoding='utf-8'))) for key in ('c12', 'c13'))


def test_resource_graphs_private_fixtures_and_all_eight_languages():
    import i18n
    catalog = courses()
    assert [len(c.chapters) for c in catalog] == [5, 4]
    assert [sum(len(ch.steps) for ch in c.chapters) for c in catalog] == [33, 27]
    assert len(TOOLBOX_COPY) == 36 and len(INTERFACE_COPY) == 29
    for key, row in (TOOLBOX_COPY | INTERFACE_COPY).items():
        assert len(row) == 8 and all(isinstance(s, str) and s.strip() for s in row)
        assert all('{' not in s and '}' not in s for s in row)
        for language, value in zip(i18n._LANGS, row):
            assert i18n.TEXT[language][key] == value
    for fixture in TOOLBOX_FIXTURES | INTERFACE_FIXTURES:
        raw = json.loads((ROOT / 'assets/tutorials/fixtures' / (fixture + '.msd')).read_text(encoding='utf-8'))
        data = normalize_project_data(raw, kind=PROJECT_KIND)
        assert data['metadata']['synthetic_teaching'] is True
        assert data['metadata']['fixture_id'] == fixture
        assert data['whiteboard_mode'] and len(data['pages']) == 1
        assert len(data['pages'][0]['segments']) == 1 and len(data['pages'][0]['shapes']) == 1
    system = catalog[1].chapters[-1]
    assert all(step.kind == 'information' and step.target is None for step in system.steps)


@pytest.fixture
def tool_panel(application_host, monkeypatch):
    # Production methods and signal connections are installed by main itself.
    # Do not redecorate methods or replace refresh_magnifier in this test.
    host, _ = application_host
    host.context.activate()
    panel = host.panel
    def capture_forbidden(*args, **kwargs):
        raise AssertionError('desktop capture is forbidden in this check')
    monkeypatch.setattr(panel, 'grab_screen', capture_forbidden)
    panel.set_ui_mode('icon', persist=False)
    return panel


def start(panel, chapter_id):
    catalog = TutorialCatalog(courses())
    chapter = catalog.chapter_by_id(chapter_id)
    paths = panel.runtime_context.paths
    destination = paths.data_dir / (chapter.fixture + '.msd')
    shutil.copyfile(ROOT / 'assets/tutorials/fixtures' / (chapter.fixture + '.msd'), destination)
    panel.teaching_events = TeachingEventBus()
    assert panel.load_teaching_fixture(str(destination))
    setup = prepare_toolbox_fixture if chapter_id.startswith('c12.') else prepare_interface_fixture
    setup(panel, chapter.fixture, paths)
    engine = TutorialEngine(catalog, session_id='toolbox-interface-direct',
        condition_reader=lambda name, argument: len(QApplication.screens()) > 1 if name == 'multiple_monitors' else False)
    panel.teaching_events = TeachingEventBus(engine)
    engine.start(chapter_id.split('.')[0], chapter_id)
    assert engine.next()
    return engine


def button(window, label):
    return next(control for control in window.findChildren(QPushButton) if control.text() == label)


def done(engine):
    assert engine.current_step_id == 'done'
    assert engine.next() and engine.phase == 'completed'
    assert not engine._issued


def test_real_calculator_keys_and_private_nonrepeating_roster(tool_panel):
    panel = tool_panel
    engine = start(panel, 'c12.calculator')
    open_button = QPushButton()
    open_button.clicked.connect(panel.open_calculator)
    open_button.click()  # Exercises the zero-argument decorated Qt slot.
    assert engine.current_step_id == 'two'
    for code in ('2', '+', '3', '='):
        button(panel.calc_panel, code).click()
    assert panel._calc_expr == panel._calc_display.text() == '5'
    done(engine)
    panel.teaching_events = None  # Ordinary no-bus path still calculates.
    for code in ('C', '2', '+', '3', '='):
        panel._calc_input(code)
    assert panel._calc_display.text() == '5'
    engine = start(panel, 'c12.roster')
    panel.open_roster_panel()
    import i18n
    button(panel.roster_panel, i18n.tr('roster_draw')).click()
    first = set(panel.roster_drawn)
    button(panel.roster_panel, i18n.tr('roster_draw')).click()
    assert len(panel.roster_drawn) == 2 and first < panel.roster_drawn
    button(panel.roster_panel, i18n.tr('roster_reset')).click()
    assert not panel.roster_drawn and len(panel.roster) == 6
    saved = json.loads(panel.runtime_context.paths.roster_file.read_text(encoding='utf-8'))
    assert saved == {'names': panel.roster, 'drawn': []}
    done(engine)


def test_real_up_timer_and_natural_down_completion(tool_panel):
    panel = tool_panel
    engine = start(panel, 'c12.timer')
    panel.handle_timer_click()
    panel.btn_timer_up.click()
    panel.btn_timer_start.click()
    QTest.qWait(panel.timer_clock.interval() * 2)
    panel.btn_timer_start.click()
    assert panel.timer_left > 0 and not panel.timer_clock.isActive()
    panel.btn_timer_reset.click()
    assert panel.timer_left == 0
    panel.btn_timer_down.click()
    panel.btn_timer_start.click()
    pending = panel._teaching_timer_completion
    assert pending is not None and engine.current_step_id == 'finish_down'
    panel.reset_timer()  # Cancels the real timer and its outstanding operation.
    assert panel._teaching_timer_completion is None and not engine._issued
    assert engine.current_step_id == 'finish_down'
    panel.btn_timer_start.click()
    QTest.qWait(2300)
    assert panel.timer_left == 0 and panel.timer_alerting and not panel.timer_clock.isActive()
    done(engine)


def test_private_board_magnifier_and_real_spotlight_motion(tool_panel):
    panel = tool_panel
    engine = start(panel, 'c12.magnifier')
    panel.handle_magnifier_click()
    assert panel._teaching_magnifier_source == 'private_canvas'
    panel.canvas.step_magnifier_zoom(1)
    panel.mag_size_slider.setValue(320)
    before = panel.canvas.magnifier_pixmap.cacheKey()
    panel.refresh_magnifier()
    assert panel.canvas.magnifier_pixmap.cacheKey() != before
    done(engine)
    engine = start(panel, 'c12.spotlight')
    panel.handle_spotlight_click()
    event = QMouseEvent(QEvent.Type.MouseMove, QPointF(210, 160), QPointF(210, 160),
                       Qt.MouseButton.NoButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    panel.canvas.mouseMoveEvent(event)
    assert (panel.canvas.mouse_pos.x(), panel.canvas.mouse_pos.y()) == (210, 160)
    panel.handle_spotlight_click()
    assert panel.canvas.draw_state == 'PEN'
    done(engine)


def test_real_layout_four_schemes_opacity_and_private_audio(tool_panel):
    panel = tool_panel
    engine = start(panel, 'c13.layout_theme')
    panel.open_settings_panel()
    panel.btn_orient_landscape.click()
    panel.btn_orient_portrait.click()
    panel.toggle_toolbar_collapsed()
    assert not panel.toolbar_window.isVisible() and panel.logo_window.isVisible()
    panel.toggle_toolbar_collapsed()
    panel.btn_theme.click()
    panel.btn_theme.click()
    for scheme in ('graphite_teal', 'slate_blue', 'warm_indigo', 'classic'):
        panel.color_scheme_combo.setCurrentIndex(panel.color_scheme_combo.findData(scheme))
    ink_opacity = panel.canvas.windowOpacity()
    panel.ui_opacity_slider.setValue(65)
    assert panel.ui_opacity == 65 and panel.canvas.windowOpacity() == ink_opacity
    done(engine)
    engine = start(panel, 'c13.monitor_audio')
    assert engine.current_step_id == 'single_screen'  # Actual offscreen environment has one display.
    assert engine.next() and engine.current_step_id == 'volume'
    if panel.settings_panel is None or not panel.settings_panel.isVisible():
        panel.open_settings_panel()
    panel.document_preferences.volume_slider.setValue(40)
    saved = json.loads(panel.runtime_context.paths.config_file.read_text(encoding='utf-8'))
    assert saved['timer_alarm_volume'] == panel.timer_alarm_volume == 40
    done(engine)
