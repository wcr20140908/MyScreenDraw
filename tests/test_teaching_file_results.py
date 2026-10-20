# SPDX-License-Identifier: GPL-3.0-or-later
"""C01 file/recovery/export results use owned offscreen Qt, never desktop input."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
from PyQt6.QtGui import QImageReader, QPixmap, QScreen
from PyQt6.QtWidgets import QDialog

from persistence import AUTOSAVE_KIND, atomic_write_autosave, atomic_write_project, make_project_data
from teaching.application import APPLICATION_EVENTS, APPLICATION_TARGETS
from teaching.models import WaitClause
from test_teaching_application import application_host, practice_request
from test_teaching_business_adapters import attach_wait, draw_ink
from test_export_ui_610 import Progress


def wait_for(panel, event, outcome='success', **equals):
    return attach_wait(panel, event, sequence=(WaitClause(event, outcome, equals),))


def saved_project(host):
    panel = host.panel
    draw_ink(panel.canvas)
    destination = host.request.paths.data_dir / 'saved-practice.msd'
    assert panel.save_project(str(destination))
    return destination


def prepare_export(host, monkeypatch, *, cancel_at=None):
    panel, canvas = host.panel, host.panel.canvas
    canvas.resize(320, 200)
    canvas.enter_whiteboard()
    draw_ink(canvas)
    canvas.new_page()
    draw_ink(canvas)
    progress = Progress(cancel_at)
    monkeypatch.setattr(panel, '_create_document_progress', lambda *args: progress)
    monkeypatch.setattr(panel, '_show_export_result', Mock())
    monkeypatch.setattr(QScreen, 'grabWindow', Mock(side_effect=AssertionError('desktop capture forbidden')))
    return progress


def private_history(host):
    panel = host.panel
    draw_ink(panel.canvas)
    path = host.request.paths.autosave_dir / 'autosave_20261010_120000.json.gz'
    data = make_project_data(pages=panel.canvas.serialized_document_pages(), current_page=0,
                             whiteboard_mode=True, board_style='BLACK', app_version='6.1.0',
                             kind=AUTOSAVE_KIND)
    atomic_write_autosave(str(path), data)
    return path, data


@pytest.mark.parametrize('event', ['project.opened', 'recovery.previewed', 'recovery.applied', 'export.finished'])
def test_application_manifest_accepts_verified_file_results(event):
    assert event in APPLICATION_EVENTS


@pytest.mark.parametrize('target', ['file.recovery', 'file.save_as', 'export.png'])
def test_application_manifest_has_recovery_and_png_targets(target):
    assert target in APPLICATION_TARGETS


def test_reopen_saved_project_reports_applied_document(application_host):
    host, _ = application_host
    path = saved_project(host)
    panel = host.panel
    engine = wait_for(panel, 'project.opened', pages=1, path=path.name)
    assert panel.open_project_from_path(str(path))
    assert panel.project_path == str(path) and not panel.project_dirty
    assert panel.canvas.all_segments and engine.phase == 'completed'
    assert not panel._document_transition_active


def test_open_picker_result_follows_all_ui_and_transition_cleanup(application_host, monkeypatch):
    host, _ = application_host
    panel = host.panel
    path = saved_project(host)
    engine = wait_for(panel, 'project.opened')
    seen = []
    original = panel.update_history_ui
    def update_ui():
        seen.append(engine.phase)
        original()
    engine._on_step = lambda step: seen.append(panel._document_transition_active) if step is None else None
    monkeypatch.setattr(panel, 'update_history_ui', update_ui)
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args: (str(path), ''))
    assert panel.open_project()
    assert len(seen) >= 2 and all(value == 'running' for value in seen[:-1])
    assert seen[-1] is False and engine.phase == 'completed'


@pytest.mark.parametrize('expected', ['success', 'cancelled'])
def test_open_picker_cancellation_is_only_a_cancelled_result(application_host, monkeypatch, expected):
    host, _ = application_host
    panel = host.panel
    engine = wait_for(panel, 'project.opened', expected)
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args: ('', ''))
    assert not panel.open_project()
    assert engine.phase == ('completed' if expected == 'cancelled' else 'running')
    assert not engine._issued


@pytest.mark.parametrize('expected', ['success', 'cancelled'])
def test_unsaved_open_cancel_preserves_live_work(application_host, monkeypatch, expected):
    host, _ = application_host
    path = saved_project(host)
    panel = host.panel
    draw_ink(panel.canvas)
    before = panel.canvas.document_signature()
    engine = wait_for(panel, 'project.opened', expected)
    monkeypatch.setattr(panel, 'confirm_unsaved_changes', lambda _: False)
    assert not panel.open_project_from_path(str(path))
    assert panel.canvas.document_signature() == before
    assert engine.phase == ('completed' if expected == 'cancelled' else 'running')
    assert not engine._issued


@pytest.mark.parametrize('failure', ['invalid', 'outside'])
def test_invalid_or_external_open_does_not_credit_success(application_host, tmp_path, failure):
    host, _ = application_host
    panel = host.panel
    path = (host.request.paths.data_dir if failure == 'invalid' else tmp_path) / 'bad.msd'
    path.write_text('{broken', encoding='utf-8')
    before = panel.canvas.document_signature()
    engine = wait_for(panel, 'project.opened', 'failed')
    assert not panel.open_project_from_path(str(path))
    assert panel.canvas.document_signature() == before
    assert engine.phase == 'completed' and not engine._issued


def test_open_picker_cannot_begin_a_new_epoch_result_after_it_returns(application_host, monkeypatch):
    host, _ = application_host
    panel = host.panel
    path = saved_project(host)
    engine = wait_for(panel, 'project.opened')
    def choose(*args):
        engine.pause(); engine.resume()
        return str(path), ''
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', choose)
    assert panel.open_project()
    assert engine.phase == 'running' and not engine._issued


def test_open_exception_retires_its_token_without_hiding_failure(application_host, monkeypatch):
    host, _ = application_host
    panel = host.panel
    path = saved_project(host)
    engine = wait_for(panel, 'project.opened')
    monkeypatch.setattr(panel, 'update_history_ui', Mock(side_effect=RuntimeError('UI finalization')))
    with pytest.raises(RuntimeError, match='UI finalization'):
        panel.open_project_from_path(str(path))
    assert engine.phase == 'running' and not engine._issued
    assert not panel._document_transition_active


def test_save_missing_canvas_retires_issued_operation(application_host):
    host, _ = application_host
    panel = host.panel
    engine = wait_for(panel, 'project.saved')
    canvas, panel.canvas = panel.canvas, None
    try:
        assert not panel.save_project(str(host.request.paths.data_dir / 'missing.msd'))
    finally:
        panel.canvas = canvas
    assert engine.phase == 'running' and not engine._issued


def test_save_ui_exception_retires_issued_operation(application_host, monkeypatch):
    host, _ = application_host
    panel = host.panel
    draw_ink(panel.canvas)
    engine = wait_for(panel, 'project.saved')
    monkeypatch.setattr(panel, 'setWindowTitle', Mock(side_effect=RuntimeError('save title')))
    with pytest.raises(RuntimeError, match='save title'):
        panel.save_project(str(host.request.paths.data_dir / 'exception.msd'))
    assert engine.phase == 'running' and not engine._issued


def test_save_as_context_predates_destination_chooser(application_host, monkeypatch):
    host, _ = application_host
    panel = host.panel
    draw_ink(panel.canvas)
    path = host.request.paths.data_dir / 'stale-copy.msd'
    engine = wait_for(panel, 'project.saved')
    def choose(*args):
        engine.pause(); engine.resume()
        return str(path), ''
    monkeypatch.setattr(host.module.QFileDialog, 'getSaveFileName', choose)
    assert panel.save_project_as() and path.is_file()
    assert engine.phase == 'running' and not engine._issued


@pytest.mark.parametrize('expected', ['success', 'cancelled'])
def test_save_as_cancel_does_not_replace_project_path(application_host, monkeypatch, expected):
    host, _ = application_host
    panel = host.panel
    path = saved_project(host)
    engine = wait_for(panel, 'project.saved', expected)
    monkeypatch.setattr(host.module.QFileDialog, 'getSaveFileName', lambda *args: ('', ''))
    assert not panel.save_project_as() and panel.project_path == str(path)
    assert engine.phase == ('completed' if expected == 'cancelled' else 'running')
    assert not engine._issued


def test_png_success_uses_committed_private_files_not_a_button(application_host, monkeypatch):
    host, _ = application_host
    prepare_export(host, monkeypatch)
    panel = host.panel
    engine = wait_for(panel, 'export.finished', format='PNG', pages=2, total=2, failed_pages=0)
    result = panel.export_pages('PNG')
    assert result.success and engine.phase == 'completed'
    assert len(result.exported_paths) == 2
    for path in result.exported_paths:
        assert Path(path).is_relative_to(host.request.paths.export_dir)
        assert QImageReader(path).canRead()
    assert not engine._issued and not panel._document_transition_active


@pytest.mark.parametrize('expected', ['success', 'cancelled'])
def test_export_partial_cancel_never_satisfies_success(application_host, monkeypatch, expected):
    host, _ = application_host
    prepare_export(host, monkeypatch, cancel_at=1)
    engine = wait_for(host.panel, 'export.finished', expected)
    result = host.panel.export_pages('PNG')
    assert result.cancelled and not result.success and len(result.exported_paths) == 1
    assert engine.phase == ('completed' if expected == 'cancelled' else 'running')
    assert not engine._issued


@pytest.mark.parametrize('expected', ['success', 'failed'])
def test_export_partial_render_failure_is_not_full_success(application_host, monkeypatch, expected):
    host, _ = application_host
    prepare_export(host, monkeypatch)
    panel, canvas = host.panel, host.panel.canvas
    original = canvas.render_page_pixmap
    calls = []
    def render(page, size):
        calls.append(page)
        return QPixmap() if len(calls) == 1 else original(page, size)
    monkeypatch.setattr(canvas, 'render_page_pixmap', render)
    engine = wait_for(panel, 'export.finished', expected, pages=1, total=2, failed_pages=1)
    result = panel.export_pages('PNG')
    assert not result.success and result.complete and len(result.exported_paths) == 1
    assert engine.phase == ('completed' if expected == 'failed' else 'running')
    assert not engine._issued


def test_export_stale_callback_cannot_complete_new_epoch(application_host, monkeypatch):
    host, _ = application_host
    prepare_export(host, monkeypatch)
    panel, canvas = host.panel, host.panel.canvas
    engine = wait_for(panel, 'export.finished')
    original = canvas.render_page_pixmap
    def render(page, size):
        engine.pause(); engine.resume()
        return original(page, size)
    monkeypatch.setattr(canvas, 'render_page_pixmap', render)
    assert panel.export_pages('PNG').success
    assert engine.phase == 'running' and not engine._issued


def test_export_result_is_delivered_after_final_callbacks(application_host, monkeypatch):
    host, _ = application_host
    prepare_export(host, monkeypatch)
    panel = host.panel
    engine = wait_for(panel, 'export.finished')
    seen = []
    monkeypatch.setattr(panel, '_show_export_result', lambda *args: seen.append(engine.phase))
    monkeypatch.setattr(panel, 'heartbeat_refresh', lambda: seen.append(engine.phase))
    engine._on_step = lambda step: seen.append(panel._document_transition_active) if step is None else None
    assert panel.export_pages('PNG').success
    assert seen == ['running', 'running', False] and engine.phase == 'completed'


def test_export_cleanup_exception_does_not_report_success(application_host, monkeypatch):
    host, _ = application_host
    prepare_export(host, monkeypatch)
    panel = host.panel
    engine = wait_for(panel, 'export.finished')
    monkeypatch.setattr(panel, 'heartbeat_refresh', Mock(side_effect=RuntimeError('export finalization')))
    with pytest.raises(RuntimeError, match='export finalization'):
        panel.export_pages('PNG')
    assert engine.phase == 'running' and not engine._issued


def test_one_export_operation_cannot_complete_two_sequence_clauses(application_host, monkeypatch):
    host, _ = application_host
    prepare_export(host, monkeypatch)
    panel = host.panel
    engine = attach_wait(panel, 'export.finished', sequence=(WaitClause('export.finished', 'success'), WaitClause('export.finished', 'success')))
    assert panel.export_pages('PNG').success
    assert engine.phase == 'running' and engine.sequence_index == 1
    assert panel.export_pages('PNG').success
    assert engine.phase == 'completed'


def test_practice_annotation_png_does_not_capture_desktop(application_host, monkeypatch):
    host, _ = application_host
    prepare_export(host, monkeypatch)
    panel = host.panel
    panel.canvas.exit_whiteboard()
    engine = wait_for(panel, 'export.finished', format='PNG', pages=1)
    result = panel.export_pages('PNG')
    assert result.success and engine.phase == 'completed'
    assert QScreen.grabWindow.call_count == 0


@pytest.mark.parametrize('action,event', [('open_project', 'project.opened'), ('export_pages', 'export.finished')])
def test_busy_document_transition_does_not_sign_a_new_operation(application_host, monkeypatch, action, event):
    host, _ = application_host
    panel = host.panel
    panel._document_transition_active = True
    engine = wait_for(panel, event)
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', Mock(side_effect=AssertionError('busy picker')))
    result = panel.export_pages('PNG') if action == 'export_pages' else panel.open_project()
    assert not result and not engine._issued


def test_private_recovery_opens_only_explicit_manual_entry(application_host, monkeypatch):
    host, _ = application_host
    panel = host.panel
    private_history(host)
    engine = wait_for(panel, 'recovery.previewed')
    monkeypatch.setattr(host.module.RecoveryDialog, '__init__', Mock(side_effect=AssertionError('startup recovery')))
    assert not panel.offer_autosave_restore()
    assert engine.phase == 'running'
    assert callable(getattr(panel, 'open_recovery_from_file_panel', None))


def test_private_recovery_preview_is_real_and_read_only(application_host, monkeypatch):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    path, _ = private_history(host)
    before = panel.canvas.document_signature()
    engine = wait_for(panel, 'recovery.previewed', pages=1, version=path.name)
    observed = []
    def reject(dialog):
        observed.append(dialog.preview_state)
        dialog.reject()
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(host.module.RecoveryDialog, 'exec', reject)
    assert not panel.open_recovery_from_file_panel()
    assert observed[0] == (str(path), 1, 1)
    assert panel.canvas.document_signature() == before
    assert engine.phase == 'completed' and not engine._issued


def test_private_restore_applies_selected_version_before_credit(application_host, monkeypatch):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    _, data = private_history(host)
    engine = wait_for(panel, 'recovery.applied', pages=1)
    monkeypatch.setattr(host.module.RecoveryDialog, 'exec', lambda dialog: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(panel, 'confirm_unsaved_changes', lambda _: True)
    assert panel.open_recovery_from_file_panel()
    assert panel.canvas.board_style == data['board_style'] and panel.canvas.all_segments
    assert panel.project_dirty and panel.project_path is None
    assert engine.phase == 'completed' and not engine._issued
    assert not panel._document_transition_active


@pytest.mark.parametrize('failure', ['cancelled', 'empty_preview', 'unsaved_cancel', 'apply_failure', 'stale'])
def test_private_restore_cannot_credit_cancel_failure_or_old_epoch(application_host, monkeypatch, failure):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    private_history(host)
    engine = wait_for(panel, 'recovery.previewed' if failure == 'empty_preview' else 'recovery.applied')
    monkeypatch.setattr(panel, 'confirm_unsaved_changes', lambda _: failure != 'unsaved_cancel')
    if failure == 'empty_preview':
        monkeypatch.setattr(panel.canvas, 'render_page_pixmap', lambda *args, **kwargs: QPixmap())
    if failure == 'apply_failure':
        monkeypatch.setattr(panel, 'apply_autosave_data', lambda _: False)
    def choose(dialog):
        if failure == 'stale':
            engine.pause(); engine.resume()
        if failure in ('cancelled', 'empty_preview'):
            dialog.reject()
            return QDialog.DialogCode.Rejected
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(host.module.RecoveryDialog, 'exec', choose)
    result = panel.open_recovery_from_file_panel()
    assert bool(result) == (failure == 'stale')
    assert engine.phase == 'running' and not engine._issued


def test_one_recovery_dialog_does_not_credit_preview_then_restore(application_host, monkeypatch):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    private_history(host)
    engine = attach_wait(panel, 'recovery.previewed', sequence=(WaitClause('recovery.previewed', 'success'), WaitClause('recovery.applied', 'success')))
    monkeypatch.setattr(host.module.RecoveryDialog, 'exec', lambda dialog: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(panel, 'confirm_unsaved_changes', lambda _: True)
    assert panel.open_recovery_from_file_panel()
    assert engine.phase == 'running' and engine.sequence_index == 1
    assert panel.open_recovery_from_file_panel()
    assert engine.phase == 'completed'


@pytest.mark.parametrize('target,attribute', [('file.recovery', 'btn_recovery'), ('file.save_as', 'btn_save_project_as'), ('export.png', 'btn_export_png')])
def test_file_targets_point_to_real_private_controls(application_host, target, attribute):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    before = (panel.canvas.document_signature(), panel.canvas.draw_state)
    host._reveal_file()
    assert host.registry.resolve(target) is getattr(panel, attribute)
    assert getattr(panel, attribute).isVisible()
    host._reveal_file()  # Revealing an already-open file panel must not toggle it shut.
    assert host.registry.resolve(target) is getattr(panel, attribute)
    assert (panel.canvas.document_signature(), panel.canvas.draw_state) == before
    assert host.presenter.engine.current_step_id == 'ink'


@pytest.mark.parametrize('event,target', [('project.opened', 'file.open'), ('recovery.previewed', 'file.recovery'),
                                         ('recovery.applied', 'file.recovery'), ('export.finished', 'export.png')])
def test_catalog_can_use_only_the_verified_new_file_contracts(practice_request, event, target):
    import json
    import main
    from teaching.application import application_catalog
    course_path = practice_request.paths.resource_dir / 'assets/tutorials/course.json'
    data = json.loads(course_path.read_text(encoding='utf-8'))
    step = data['chapters'][0]['steps'][0]
    step['target'] = target
    step['wait'] = {'event': event, 'outcome': 'success'}
    step['reveal'] = ['open_file_panel']
    course_path.write_text(json.dumps(data), encoding='utf-8')
    catalog, _ = application_catalog(main, practice_request.paths.resource_dir)
    assert catalog.chapter_by_id('c01.foundation').steps[0].wait.clauses[0].event == event



def install_file_then_width(host, event, target):
    import json
    from teaching.application import application_catalog
    host.presenter.engine.stop()
    course_path = host.request.paths.resource_dir / 'assets/tutorials/course.json'
    data = json.loads(course_path.read_text(encoding='utf-8'))
    data['chapters'][0]['steps'] = [
        {'id': 'file', 'title_key': 'teaching_center_title', 'body_key': 'teaching_resume',
         'target': target, 'input_policy': 'target_only', 'reveal': ['open_file_panel'],
         'wait': {'event': event, 'outcome': 'success'}, 'next': 'width'},
        {'id': 'width', 'title_key': 'teaching_center_title', 'body_key': 'teaching_resume',
         'target': 'pen.width', 'input_policy': 'target_only', 'reveal': ['open_pen_panel'],
         'wait': {'event': 'pen.width_changed', 'outcome': 'success'}, 'next': 'end_chapter'}]
    course_path.write_text(json.dumps(data), encoding='utf-8')
    catalog, _ = application_catalog(host.module, host.request.paths.resource_dir)
    host.presenter.engine.catalog = catalog
    host.presenter.start(host.request.course_id, host.request.chapter_id)
    return host.presenter.engine


@pytest.mark.parametrize('button,event,target', [
    ('btn_save_project', 'project.saved', 'file.save'),
    ('btn_save_project_as', 'project.saved', 'file.save_as'),
    ('btn_open_project', 'project.opened', 'file.open'),
    ('btn_export_png', 'export.finished', 'export.png'),
    ('btn_recovery', 'recovery.previewed', 'file.recovery'),
    ('btn_recovery', 'recovery.applied', 'file.recovery')])
def test_real_presenter_keeps_following_target_after_whole_file_callback(
        application_host, monkeypatch, button, event, target):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    monkeypatch.setattr(panel, 'confirm_unsaved_changes', lambda _: True)
    path = host.request.paths.data_dir / 'menu-practice.msd'
    # Prepare synthetic content before presenting a target-only file lesson.
    # Canvas input legitimately closes menus; doing this during the lesson would
    # hide its target and test a broken setup rather than the file callback.
    with panel.teaching_events.suppress():
        if event == 'export.finished':
            prepare_export(host, monkeypatch)
        elif event.startswith('recovery.'):
            private_history(host)
        else:
            draw_ink(panel.canvas)
        data = make_project_data(pages=panel.canvas.serialized_document_pages(),
                                 current_page=panel.canvas.current_page,
                                 whiteboard_mode=panel.canvas.whiteboard_mode,
                                 board_style=panel.canvas.board_style, app_version='6.1.0')
        fixture = host.request.paths.resource_dir / 'assets/tutorials/fixtures/blank.msd'
        atomic_write_project(str(fixture), data)
        if event == 'project.opened':
            assert panel.save_project(str(path))
    if event.startswith('recovery.'):
        def choose(dialog):
            if event == 'recovery.previewed':
                dialog.reject()
                return QDialog.DialogCode.Rejected
            return QDialog.DialogCode.Accepted
        monkeypatch.setattr(host.module.RecoveryDialog, 'exec', choose)
    else:
        monkeypatch.setattr(host.module.QFileDialog, 'getSaveFileName', lambda *args: (str(path), ''))
        monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args: (str(path), ''))
    engine = install_file_then_width(host, event, target)
    assert engine.current_step_id == 'file' and engine.phase == 'running'
    assert host.registry.resolve(target) is getattr(panel, button)
    assert getattr(panel, button).isVisible()
    getattr(panel, button).click()
    assert engine.current_step_id == 'width' and engine.phase == 'running'
    assert host.presenter._dialog_depth == 0 and not panel._document_transition_active
    assert panel.draw_sub.isVisible()
    assert host.presenter.active_target_id == 'pen.width'
    assert host.registry.resolve('pen.width') is panel.pen_width_row
    panel.pen_slider.setValue(12 if panel.canvas.pen_width != 12 else 13)
    assert engine.phase == 'completed'


def test_private_recovery_rechecks_selected_path_before_applying(application_host, monkeypatch, tmp_path):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    private_history(host)
    outside = tmp_path / 'not-practice.json.gz'
    outside.write_bytes(b'original private data')
    before = panel.canvas.document_signature()
    engine = wait_for(panel, 'recovery.applied')
    monkeypatch.setattr(panel, 'confirm_unsaved_changes', lambda _: True)
    def choose(dialog):
        dialog.selected_path = str(outside)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(host.module.RecoveryDialog, 'exec', choose)
    assert not panel.open_recovery_from_file_panel()
    assert engine.phase == 'running' and not engine._issued
    assert panel.canvas.document_signature() == before
    assert outside.read_bytes() == b'original private data'


def test_cancelled_recovery_retires_only_its_own_operation(application_host, monkeypatch):
    host, _ = application_host
    host.context.activate(); host.activate()
    panel = host.panel
    private_history(host)
    engine = wait_for(panel, 'recovery.applied')
    peer = panel.teaching_events.begin_operation('recovery.applied')
    assert peer is not None
    monkeypatch.setattr(host.module.RecoveryDialog, 'exec', lambda dialog: QDialog.DialogCode.Rejected)
    assert not panel.open_recovery_from_file_panel()
    assert engine.phase == 'running' and engine._issued == {peer.operation_id: peer}
    assert panel.teaching_events.discard_operation(peer)
