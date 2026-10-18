# SPDX-License-Identifier: GPL-3.0-or-later
"""Formal C01 content, offline assets and every chapter using owned Qt methods."""
from __future__ import annotations

import ast
from dataclasses import replace
import json
from pathlib import Path
from string import Formatter
from unittest.mock import Mock

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QPoint, QTimer, Qt
from PyQt6.QtGui import QColor, QScreen
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog

from persistence import normalize_project_data, read_json_maybe_gz, PROJECT_KIND, AUTOSAVE_KIND
from runtime_paths import RuntimeContext, RuntimePaths
from teaching.application import ApplicationTeachingHost, application_catalog
from teaching.packaging import collect_teaching_datas
from teaching.session_view import parent_progress_view
from teaching.state import TutorialStateStore
from test_teaching_application_isolation import drain
from test_teaching_business_adapters import draw_ink, mouse

ROOT = Path(__file__).resolve().parents[1]
CHAPTERS = ('interface', 'ink', 'select', 'pages', 'files', 'finish')
STEP_IDS = (('identity', 'pen', 'stroke', 'mode'), ('color', 'width', 'stroke', 'erase'),
            ('undo', 'redo', 'choose', 'move'), ('enter', 'add', 'previous', 'next'),
            ('save', 'open', 'preview', 'restore'), ('png', 'pause', 'center', 'done'))


def formal_catalog():
    import main
    assert (ROOT / 'assets/tutorials/catalog.json').is_file(), 'Formal C01 catalog is not delivered'
    return application_catalog(main, ROOT)


def test_formal_core_has_six_real_chapters_and_24_steps_with_verified_targets():
    catalog, loader = formal_catalog()
    course = catalog.course_by_id('c01')
    assert tuple(chapter.id for chapter in course.chapters) == tuple('c01.' + name for name in CHAPTERS)
    assert tuple(tuple(step.id for step in chapter.steps) for chapter in course.chapters) == STEP_IDS
    assert sum(len(chapter.steps) for chapter in course.chapters) == 24
    assert all(chapter.fixture in loader.fixtures for chapter in course.chapters)
    assert all(step.kind == 'operation' and step.wait is not None
               for chapter in course.chapters for step in chapter.steps
               if step.id not in ('identity', 'done'))
    files = course.chapters[4]
    assert dict(files.steps[1].wait.clauses[0].equals)['reopened_saved'] is True
    assert dict(files.steps[2].wait.clauses[0].equals)['version'] == 'autosave_teaching_core_files.json.gz'
    assert dict(files.steps[3].wait.clauses[0].equals)['version'] == 'autosave_teaching_core_files.json.gz'


def test_formal_core_copy_is_pure_complete_eight_language_data():
    import i18n
    from teaching.core_copy import CORE_COPY
    assert len(CORE_COPY) == 56
    tree = ast.parse((ROOT / 'teaching/core_copy.py').read_text(encoding='utf-8-sig'))
    assert all(isinstance(node, ast.Assign) for node in tree.body)
    catalog, _ = formal_catalog()
    referenced = {catalog.courses[0].title_key, catalog.groups[0].title_key}
    for chapter in catalog.courses[0].chapters:
        referenced.add(chapter.title_key)
        for step in chapter.steps:
            referenced.update((step.title_key, step.body_key))
    assert referenced == set(CORE_COPY)
    for key, values in CORE_COPY.items():
        assert type(values) is tuple and len(values) == len(i18n._LANGS) == 8
        for language, value in zip(i18n._LANGS, values):
            assert type(value) is str and value.strip() and i18n.TEXT[language][key] == value
            assert not any(field is not None for _, field, _, _ in Formatter().parse(value))
            assert '<' not in value and '>' not in value
    for language in i18n._LANGS:
        for key in ('teaching_c01_interface_identity_body', 'teaching_c01_finish_done_body'):
            assert i18n.TEXT[language]['teaching_next'] in i18n.TEXT[language][key]
            assert i18n.TEXT[language]['teaching_exit'] in i18n.TEXT[language][key]
        assert i18n.TEXT[language]['teaching_pause'] in i18n.TEXT[language]['teaching_c01_finish_pause_body']
        assert i18n.TEXT[language]['teaching_resume'] in i18n.TEXT[language]['teaching_c01_finish_pause_body']


def test_core_resources_are_legal_offline_projects_and_in_bundle_inventory():
    catalog, loader = formal_catalog()
    manifest = collect_teaching_datas(ROOT)
    bundled = {Path(source).resolve() for source, _ in manifest}
    assert len(manifest) == len(bundled)
    for chapter in catalog.courses[0].chapters:
        path = loader.asset_path(loader.fixtures[chapter.fixture])
        data = normalize_project_data(read_json_maybe_gz(str(path)), kind=PROJECT_KIND)
        assert len(data['pages']) == 1 and path in bundled
        assert data['metadata'].get('synthetic_teaching') is True
    history = loader.asset_path('fixtures/core-files-history.msd')
    assert history in bundled
    assert normalize_project_data(read_json_maybe_gz(str(history)), kind=PROJECT_KIND)['board_style'] == 'BLACK'
    assert loader.asset_path('courses/c01.json') in bundled


@pytest.fixture
def core_host(request, tmp_path, monkeypatch):
    import main
    from teaching.bootstrap import PracticeRequest
    chapter = getattr(request, 'param', 'c01.interface')
    paths = RuntimePaths.create_practice(ROOT, ROOT, temp_root=tmp_path / 'owned-temp')
    context = RuntimeContext(paths)
    monkeypatch.setattr(main, 'RUNTIME_CONTEXT', context)
    for name, value in paths.module_aliases().items():
        monkeypatch.setattr(main, name, value)
    main.ensure_directories()
    monkeypatch.setattr(main, 'notify_user', Mock())
    monkeypatch.setattr(QScreen, 'grabWindow', Mock(side_effect=AssertionError('desktop capture forbidden')))
    app = QApplication.instance()
    before = set(app.topLevelWidgets())
    progress = []
    host = ApplicationTeachingHost(main, PracticeRequest(paths, 'offscreen-core', 'c01', chapter),
                                  on_progress=lambda *record: progress.append(record))
    try:
        context.activate()
        host.activate()
        yield host, progress
    finally:
        host.close()
        for window in set(app.topLevelWidgets()) - before:
            if not sip.isdeleted(window):
                for timer in window.findChildren(QTimer):
                    timer.stop()
                window.hide()
                window.deleteLater()
        drain(app)


def step(host, expected):
    assert host.presenter.engine.phase == 'running', host.presenter.engine.last_error
    assert host.presenter.engine.current_step_id == expected


def completed(host, progress, chapter):
    assert host.presenter.engine.phase == 'completed'
    assert progress[-1] == ('c01.' + chapter, 'completed', 1)
    assert host.presenter.controller.chapter_finished and host.presenter.controller.isVisible()
    assert host.presenter._dialog_depth == 0


def assert_core_interface_button_round_trip(host, progress, monkeypatch):
    panel, presenter = host.panel, host.presenter
    canvas, engine = panel.canvas, presenter.engine
    app = QApplication.instance()
    assert app.platformName() == 'offscreen'
    assert host.context.paths.practice

    def click(button):
        assert button.isVisible() and button.isEnabled()
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        drain(app)

    step(host, 'identity')
    assert presenter.controller.practice_label.isVisible()
    assert presenter.controller.practice_label.text() == host.module.tr('teaching_practice_badge')
    assert not canvas.is_drawing_mode
    click(presenter.controller.next_button)
    step(host, 'pen')
    QTest.mouseClick(presenter.controller.next_button, Qt.MouseButton.LeftButton)
    step(host, 'pen')  # An operation cannot be bypassed.
    click(panel.icon_buttons['pen'])
    step(host, 'stroke')
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(50, 70))
    QTest.mouseMove(canvas, QPoint(160, 70))
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(200, 70))
    drain(app)
    step(host, 'mode')
    assert canvas.all_segments and canvas.is_drawing_mode
    assert presenter.active_target_id == 'toolbar.mode' and engine.sequence_index == 0

    modes = []
    emit_result = presenter.events.emit_result

    def record_mode(context, name, outcome, details):
        # Observe real adapter results without issuing or fabricating any event.
        if context is not None and name == 'mode.changed' and outcome == 'success':
            modes.append((details['drawing_mode'], canvas.is_drawing_mode))
        return emit_result(context, name, outcome, details)

    monkeypatch.setattr(presenter.events, 'emit_result', record_mode)
    blocked_clicks = []
    panel.icon_buttons['settings'].clicked.connect(lambda: blocked_clicks.append('settings'))
    panel.icon_buttons['pen'].clicked.connect(lambda: blocked_clicks.append('pen'))
    click(panel.icon_buttons['pen'])  # Return is not allowed before entering mouse mode.
    assert canvas.is_drawing_mode and engine.sequence_index == 0 and not modes

    for stage in (0, 1):
        assert presenter.barrier.installed
        click(panel.icon_buttons['settings'])  # Visible even in the compact mouse toolbar.
        QTest.mouseClick(presenter.controller.next_button, Qt.MouseButton.LeftButton)
        step(host, 'mode')
        assert engine.sequence_index == stage and blocked_clicks == []
        assert not any(record[1] == 'completed' for record in progress)
        if stage == 0:
            click(panel.icon_buttons['mode'])
            step(host, 'mode')
            assert engine.sequence_index == 1 and not canvas.is_drawing_mode
            assert canvas.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            assert modes == [(False, False)]

    return_target = presenter.active_target_id
    return_highlight = presenter.highlight.geometry()
    pen_rect = host.registry.global_rect('toolbar.pen')
    click(panel.icon_buttons['pen'])
    assert canvas.is_drawing_mode, 'Annotate input must return from mouse mode'
    assert not canvas.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert modes == [(False, False), (True, True)] and engine.sequence_index == 2
    assert return_target == 'toolbar.pen' and return_highlight == pen_rect
    assert blocked_clicks == ['pen']
    completed(host, progress, 'interface')
    assert not presenter.barrier.installed


def test_core_interface_uses_actual_marker_tool_ink_and_two_mode_changes(core_host, monkeypatch):
    assert_core_interface_button_round_trip(*core_host, monkeypatch)


def test_core_interface_button_regression_rejects_old_mode_allowlist(core_host, monkeypatch):
    host, progress = core_host
    chapter = host.catalog.chapter_by_id('c01.interface')
    # Reintroduce only the old course-data defect in memory; never roll back files
    # or bypass the real presenter, InputBarrier, buttons, or action adapters.
    old_chapter = replace(chapter, steps=tuple(
        replace(item, allowed_targets=('toolbar.mode', 'toolbar.mode'))
        if item.id == 'mode' else item for item in chapter.steps))
    monkeypatch.setattr(host.presenter.engine, '_chapter', old_chapter)
    monkeypatch.setattr(host.presenter, '_chapter', old_chapter)
    with pytest.raises(AssertionError, match='Annotate input must return from mouse mode'):
        assert_core_interface_button_round_trip(host, progress, monkeypatch)
    step(host, 'mode')
    assert host.presenter.engine.sequence_index == 1
    assert host.presenter.active_target_id == 'toolbar.mode'
    assert host.presenter.barrier.installed and not host.panel.canvas.is_drawing_mode
    assert not any(record[1] == 'completed' for record in progress)


@pytest.mark.parametrize('core_host', ['c01.ink'], indirect=True)
def test_core_ink_changes_color_width_and_really_erases_a_stroke(core_host):
    host, progress = core_host
    panel, canvas = host.panel, host.panel.canvas
    step(host, 'color')
    button = next(button for button in panel.color_buttons
                  if button.property('color_val') and QColor(button.property('color_val')) != canvas.pen_color)
    button.click()
    step(host, 'width')
    panel.pen_slider.setValue(12 if canvas.pen_width != 12 else 13)
    step(host, 'stroke')
    draw_ink(canvas)
    step(host, 'erase')
    panel.handle_eraser_click()
    assert host.presenter.engine.sequence_index == 1
    before = len(canvas.all_segments)
    mouse(canvas, 'press', (170, 150))
    mouse(canvas, 'move', (220, 180))
    mouse(canvas, 'release', (220, 180))
    assert len(canvas.all_segments) < before
    completed(host, progress, 'ink')


@pytest.mark.parametrize('core_host', ['c01.select'], indirect=True)
def test_core_select_has_meaningful_undo_redo_then_real_selection_and_move(core_host):
    host, progress = core_host
    panel, canvas = host.panel, host.panel.canvas
    step(host, 'undo')
    signature = canvas.document_signature()
    assert canvas.undo_stack and canvas.all_segments and not canvas.redo_stack
    assert canvas.undo()
    assert canvas.document_signature() != signature
    step(host, 'redo')
    assert canvas.redo()
    step(host, 'choose')
    panel.handle_select_click()
    assert host.presenter.engine.sequence_index == 1
    mouse(canvas, 'press', (170, 150))
    mouse(canvas, 'release', (170, 150))
    assert canvas.selected_ids
    step(host, 'move')
    before = canvas.document_signature()
    mouse(canvas, 'press', (170, 150))
    mouse(canvas, 'move', (230, 210))
    mouse(canvas, 'release', (230, 210))
    assert canvas.document_signature() != before
    completed(host, progress, 'select')


@pytest.mark.parametrize('core_host', ['c01.pages'], indirect=True)
def test_core_pages_starts_outside_whiteboard_and_keeps_actual_page_sequence(core_host):
    host, progress = core_host
    panel, canvas = host.panel, host.panel.canvas
    assert not canvas.whiteboard_mode
    step(host, 'enter')
    panel.toggle_whiteboard()
    step(host, 'add')
    panel.new_whiteboard_page()
    assert len(canvas.pages) == 2 and canvas.current_page == 1
    step(host, 'previous')
    panel.switch_whiteboard_page(-1)
    assert canvas.current_page == 0
    step(host, 'next')
    panel.switch_whiteboard_page(1)
    assert canvas.current_page == 1
    completed(host, progress, 'pages')


def save_and_reopen(host, monkeypatch):
    panel = host.panel
    path = host.request.paths.data_dir / '1.msd'
    monkeypatch.setattr(host.module.QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
    assert panel.save_project_from_file_panel() and path.is_file()
    step(host, 'open')
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args: (str(path), ''))
    assert panel.open_project_from_file_panel()
    step(host, 'preview')
    return path


@pytest.mark.parametrize('core_host', ['c01.files'], indirect=True)
def test_core_files_reopens_own_saved_project_previews_then_restores_seeded_history(core_host, monkeypatch):
    host, progress = core_host
    panel = host.panel
    path = host.request.paths.autosave_dir / 'autosave_teaching_core_files.json.gz'
    history = normalize_project_data(read_json_maybe_gz(str(path)), kind=AUTOSAVE_KIND)
    assert history['board_style'] == 'BLACK' and len(panel._list_autosave_files()) == 1
    save_and_reopen(host, monkeypatch)
    before = panel.canvas.document_signature()
    monkeypatch.setattr(host.module.RecoveryDialog, 'exec', lambda dialog: QDialog.DialogCode.Rejected)
    assert not panel.open_recovery_from_file_panel()
    assert panel.canvas.document_signature() == before
    step(host, 'restore')
    monkeypatch.setattr(host.module.RecoveryDialog, 'exec', lambda dialog: QDialog.DialogCode.Accepted)
    assert panel.open_recovery_from_file_panel()
    assert panel.canvas.board_style == 'BLACK' and panel.project_dirty and panel.project_path is None
    completed(host, progress, 'files')


@pytest.mark.parametrize('core_host', ['c01.files'], indirect=True)
def test_core_file_cancel_and_another_fixture_cannot_credit_expected_save_or_reopen(core_host, monkeypatch):
    host, progress = core_host
    panel = host.panel
    monkeypatch.setattr(host.module.QFileDialog, 'getSaveFileName', lambda *args: ('', ''))
    assert not panel.save_project_from_file_panel()
    step(host, 'save')
    wrong = host.request.paths.data_dir / 'wrong-name.msd'
    assert panel.save_project(str(wrong))
    step(host, 'save')
    expected = host.request.paths.data_dir / '1.msd'
    assert panel.save_project(str(expected))
    step(host, 'open')
    other = host.request.paths.data_dir / 'fixtures/core.files.msd'
    assert panel.open_project_from_path(str(other))
    step(host, 'open')
    assert panel.open_project_from_path(str(expected))
    step(host, 'preview')
    assert not any(record[1] == 'completed' for record in progress)


@pytest.mark.parametrize('core_host', ['c01.finish'], indirect=True)
def test_core_finish_needs_png_explicit_resume_center_return_and_explicit_exit(core_host, tmp_path, monkeypatch):
    host, progress = core_host
    panel = host.panel
    exits = []
    host.exit_requested.connect(lambda: exits.append('exit'))
    monkeypatch.setattr(panel, '_show_export_result', Mock())
    result = panel.do_export('PNG')
    assert result.success and result.total == 1
    assert list(host.request.paths.export_dir.glob('*.png'))
    step(host, 'pause')
    host.resume()  # Already running is not a completed pause/resume.
    drain(QApplication.instance())
    step(host, 'pause')
    host.pause()
    assert host.presenter.engine.phase == 'paused'
    host.resume()
    drain(QApplication.instance())
    step(host, 'center')
    assert host.panel.open_teaching_center()
    store = TutorialStateStore(tmp_path / 'parent-progress.json')
    host.accept_center(parent_progress_view(host.catalog, store))
    step(host, 'center')
    host.center_closed.connect(lambda: host.finish_center(resume=True))
    host.center.close()
    step(host, 'done')
    assert not exits
    host.presenter.controller.next_button.click()
    completed(host, progress, 'finish')
    assert not exits  # Chapter completion does not automatically exit.
    host.presenter.controller.exit_button.click()
    assert exits == ['exit']
