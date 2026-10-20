# SPDX-License-Identifier: GPL-3.0-or-later
"""Real application entrypoints under private paths, only Qt offscreen input."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.QtGui import QImage, QColor
from PyQt6.QtWidgets import QApplication

from runtime_paths import RuntimeContext, RuntimePaths
from teaching.bootstrap import practice_arguments


def drain(app):
    for _ in range(5):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture
def private_runtime(tmp_path, monkeypatch):
    import main
    root = Path(__file__).resolve().parents[1]
    paths = RuntimePaths.create_practice(root, root, temp_root=tmp_path / 'owned-temp')
    context = RuntimeContext(paths)
    monkeypatch.setattr(main, 'RUNTIME_CONTEXT', context, raising=False)
    for name, value in paths.module_aliases().items():
        monkeypatch.setattr(main, name, value)
    for folder in (paths.data_dir, paths.export_dir, paths.autosave_dir):
        folder.mkdir(parents=True, exist_ok=True)
    notices = []
    monkeypatch.setattr(main, 'notify_user', lambda *args, **kwargs: notices.append((args, kwargs)))
    return main, paths, context, notices


@pytest.fixture
def panel(private_runtime, monkeypatch):
    main, paths, context, notices = private_runtime
    listener = Mock()
    monkeypatch.setattr(main.keyboard, 'Listener', listener)
    app = QApplication.instance() or QApplication([])
    prior = set(app.topLevelWidgets())
    value = main.ControlPanel()
    canvas = main.DrawingCanvas(value)
    value.canvas = canvas
    value._test_listener_factory = listener
    yield value
    value.stop_update_worker()
    value.shutdown_autosave()
    if getattr(value, 'listener', None) is not None:
        value.listener.stop()
    for widget in app.topLevelWidgets():
        if widget not in prior and not sip.isdeleted(widget):
            for timer in widget.findChildren(main.QTimer):
                timer.stop()
            widget.hide()
            widget.deleteLater()
    drain(app)


def test_real_construction_does_not_create_keyboard_hook_or_start_ui(private_runtime, panel):
    main, paths, context, notices = private_runtime
    assert panel._test_listener_factory.call_count == 0
    assert panel.listener is None
    assert not panel.canvas.isVisible()
    assert not panel.logo_window.isVisible() and not panel.toolbar_window.isVisible()
    assert not panel.timer.isActive() and not panel.autosave_timer.isActive()
    assert panel.lifecycle.tray_icon is None


def test_load_settings_mode_and_deferred_refresh_stay_hidden_until_activation(private_runtime, panel):
    main, paths, context, notices = private_runtime
    paths.config_file.write_text(json.dumps({'ui_mode': 'icon', 'update_check_enabled': True}), encoding='utf-8')
    panel.load_settings()
    panel.set_ui_mode('icon', persist=False)
    panel.resume_callbacks()
    panel.heartbeat_refresh()
    drain(QApplication.instance())
    assert not panel.canvas.isVisible() and not panel.logo_window.isVisible()
    assert not panel.toolbar_window.isVisible()
    assert not panel.timer.isActive() and not panel.autosave_timer.isActive()
    assert not panel.update_check_timer.isActive()


def test_practice_usage_and_telemetry_never_count_as_normal_sessions(private_runtime, panel):
    main, paths, context, notices = private_runtime
    main.track_event('app_started', secret='must-not-be-written')
    before = paths.config_file.read_bytes() if paths.config_file.exists() else None
    panel.begin_usage_session()
    assert not paths.telemetry_file.exists()
    assert panel._notice_session_started is False
    assert (paths.config_file.read_bytes() if paths.config_file.exists() else None) == before


def test_direct_update_entry_cannot_create_network_worker(private_runtime, panel, monkeypatch):
    main, paths, context, notices = private_runtime
    worker = Mock()
    worker.return_value.download_path = None
    worker.return_value.isRunning.return_value = False
    monkeypatch.setattr(main, 'UpdateCheckWorker', worker)
    panel.update_check_enabled = True
    panel.check_for_updates()
    assert worker.call_count == 0 and not panel.update_check_timer.isActive()


@pytest.mark.parametrize('method,args', [('autostart_enabled', ()), ('set_autostart', (True,)),
                                         ('heal_autostart', ())])
def test_practice_autostart_never_reads_or_writes_real_registry(private_runtime, monkeypatch, method, args):
    main, paths, context, notices = private_runtime
    touch = Mock(side_effect=OSError('registry probe must not be reached'))
    fake = SimpleNamespace(HKEY_CURRENT_USER=1, KEY_SET_VALUE=2, REG_SZ=3, OpenKey=touch, CreateKeyEx=touch)
    monkeypatch.setitem(sys.modules, 'winreg', fake)
    assert not getattr(main, method)(*args)
    assert touch.call_count == 0


def test_save_project_rejects_external_path_before_touching_document_or_file(private_runtime, panel, tmp_path):
    main, paths, context, notices = private_runtime
    outside = tmp_path / 'real-document.msd'
    outside.write_bytes(b'original user file')
    signature = panel.canvas.document_signature()
    assert panel.save_project(str(outside)) is False
    assert outside.read_bytes() == b'original user file'
    assert panel.canvas.document_signature() == signature and panel.project_path is None


def test_open_project_rejects_external_file_before_parse_or_document_change(private_runtime, panel, tmp_path, monkeypatch):
    main, paths, context, notices = private_runtime
    outside = tmp_path / 'real-document.msd'
    outside.write_text('{}', encoding='utf-8')
    reader = Mock(side_effect=ValueError('must not parse the external document'))
    monkeypatch.setattr(main, 'read_json_maybe_gz', reader)
    assert panel.open_project_from_path(str(outside)) is False
    assert reader.call_count == 0 and not panel._document_transition_active


def test_actual_private_save_and_open_round_trip_is_still_usable(private_runtime, panel):
    main, paths, context, notices = private_runtime
    destination = paths.data_dir / 'practice.msd'
    assert panel.save_project(str(destination))
    assert destination.is_file() and panel.project_path == str(destination)
    assert panel.open_project_from_path(str(destination))
    assert not panel.project_dirty


def test_import_image_rejects_external_input_before_decode(private_runtime, panel, tmp_path, monkeypatch):
    main, paths, context, notices = private_runtime
    outside = tmp_path / 'personal.png'
    outside.write_bytes(b'not even a valid image')
    reader = Mock(side_effect=AssertionError('must reject before QImageReader'))
    monkeypatch.setattr(main, 'QImageReader', reader)
    assert panel.import_image_file(str(outside)) is None
    assert reader.call_count == 0


def test_private_image_can_be_decoded_and_inserted(private_runtime, panel):
    main, paths, context, notices = private_runtime
    source = paths.data_dir / 'sample.png'
    image = QImage(24, 24, QImage.Format.Format_ARGB32)
    image.fill(QColor('blue'))
    assert image.save(str(source))
    assert panel.import_image_file(str(source)) is not None


@pytest.mark.parametrize('method,alias', [('save_settings', 'CONFIG_FILE'), ('save_roster', 'ROSTER_FILE')])
def test_alias_rebinding_cannot_bypass_actual_write_boundary(private_runtime, panel, tmp_path, monkeypatch, method, alias):
    main, paths, context, notices = private_runtime
    outside = tmp_path / 'parent-data.json'
    outside.write_bytes(b'keep exact original bytes')
    monkeypatch.setattr(main, alias, str(outside))
    getattr(panel, method)()
    assert outside.read_bytes() == b'keep exact original bytes'


def test_roster_read_rejects_external_alias_without_loading_real_names(private_runtime, panel, tmp_path, monkeypatch):
    main, paths, context, notices = private_runtime
    outside = tmp_path / 'real-roster.json'
    outside.write_text('["private name"]', encoding='utf-8')
    monkeypatch.setattr(main, 'ROSTER_FILE', str(outside))
    panel.load_roster()
    assert panel.roster == []


def test_practice_never_offers_normal_recovery_or_consumes_restart_file(private_runtime, panel, tmp_path, monkeypatch):
    main, paths, context, notices = private_runtime
    chooser = Mock(side_effect=AssertionError('normal recovery must not be offered'))
    monkeypatch.setattr(main.RecoveryDialog, '__init__', chooser)
    restart = tmp_path / 'original-restart.json'
    restart.write_bytes(b'keep restart data')
    reader = Mock(side_effect=AssertionError('practice must not read ordinary recovery data'))
    monkeypatch.setattr(main, 'read_json_maybe_gz', reader)
    monkeypatch.setattr(panel, '_list_autosave_files', reader)
    assert not panel.offer_autosave_restore()
    assert not panel.restore_from_restart(str(restart))
    assert chooser.call_count == 0 and reader.call_count == 0
    assert restart.read_bytes() == b'keep restart data'


def test_practice_screen_export_renders_private_page_without_desktop_capture(private_runtime, panel, monkeypatch):
    main, paths, context, notices = private_runtime
    screen = Mock(side_effect=AssertionError('practice must never capture the desktop'))
    monkeypatch.setattr(main.QApplication, 'primaryScreen', screen)
    panel.canvas.whiteboard_mode = False
    pixmap = panel.grab_screen()
    assert pixmap is not None and not pixmap.isNull()
    assert screen.call_count == 0


@pytest.mark.parametrize('argument', ['--teaching-practice', '--teaching-practice=bad', '--session-root', '--channel=bad'])
def test_bad_private_startup_arguments_fail_before_qt_import_or_normal_fallback(tmp_path, argument):
    source = """import sys
sys.argv=['main.py', sys.argv[1]]
import main
raise AssertionError('invalid teaching request fell back to ordinary app')
"""
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', MYSCREENDRAW_NO_KEYBOARD='1', PYNPUT_BACKEND='dummy')
    result = subprocess.run([sys.executable, '-B', '-c', source, argument], cwd=Path(__file__).resolve().parents[1],
                            env=environment, capture_output=True, timeout=30)
    assert result.returncode == 2, result.stderr.decode('utf-8', errors='replace')
    assert b'invalid teaching request fell back' not in result.stderr


def test_valid_practice_bootstrap_binds_private_paths_before_any_logging(tmp_path):
    root = Path(__file__).resolve().parents[1]
    paths = RuntimePaths.create_practice(root, root, temp_root=tmp_path / 'owned-temp')
    arguments = practice_arguments(paths, 'myscreendraw-teaching-' + 'a' * 32, 'c01', 'c01.intro')
    source = """import sys
sys.argv=['main.py']+sys.argv[1:]
import main
from pathlib import Path
root=main.PRACTICE_REQUEST.paths.runtime_root
assert main.RUNTIME_CONTEXT.paths.practice and not main.RUNTIME_CONTEXT.ui_active
for key in ('DATA_DIR','EXPORT_DIR','AUTOSAVE_DIR','CONFIG_FILE','ROSTER_FILE','TELEMETRY_FILE','LOG_FILE'):
    assert Path(getattr(main,key)).resolve().is_relative_to(root), key
assert not main.LOGGER.handlers
main.ensure_directories()
main.setup_logging()
assert Path(main.LOG_FILE).is_file()
print('private bootstrap verified')
"""
    environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', MYSCREENDRAW_NO_KEYBOARD='1', PYNPUT_BACKEND='dummy',
                       MYSCREENDRAW_PRACTICE_NONCE=paths.nonce,
                       MYSCREENDRAW_PRACTICE_TEMP_ROOT=str(paths.temp_root))
    result = subprocess.run([sys.executable, '-B', '-c', source, *arguments], cwd=root,
                            env=environment, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
    assert b'private bootstrap verified' in result.stdout


def test_private_directory_boundary_rejects_files_and_external_directories(private_runtime, tmp_path):
    main, paths, context, notices = private_runtime
    assert paths.require_directory_path(paths.export_dir / 'lesson') == paths.export_dir / 'lesson'
    with pytest.raises(ValueError):
        paths.require_directory_path(tmp_path)
    file = paths.data_dir / 'not-directory'
    file.write_bytes(b'owned')
    with pytest.raises(ValueError):
        paths.require_directory_path(file)


def test_live_io_rechecks_owned_marker(private_runtime, panel):
    main, paths, context, notices = private_runtime
    paths.marker_file.write_text('{}', encoding='utf-8')
    destination = paths.data_dir / 'lost-ownership.msd'
    assert panel.save_project(str(destination)) is False
    assert not destination.exists()


def test_external_config_is_not_loaded(private_runtime, panel, tmp_path, monkeypatch):
    main, paths, context, notices = private_runtime
    outside = tmp_path / 'parent-config.json'
    outside.write_text(json.dumps({'pen_width': 123, 'theme': 'not-practice'}), encoding='utf-8')
    monkeypatch.setattr(main, 'CONFIG_FILE', str(outside))
    before = panel.collect_settings()
    panel.load_settings()
    assert panel.collect_settings().get('pen_width') == before.get('pen_width')


def test_external_export_alias_cannot_create_output(private_runtime, panel, tmp_path, monkeypatch):
    main, paths, context, notices = private_runtime
    outside = tmp_path / 'parent-exports'
    pipeline = Mock(side_effect=AssertionError('must reject before export pipeline'))
    monkeypatch.setattr(main, 'EXPORT_DIR', str(outside))
    monkeypatch.setattr(main, 'export_document', pipeline)
    monkeypatch.setattr(panel, '_show_export_result', lambda *args: None)
    result = panel.export_pages('PNG')
    assert not result.success and not outside.exists()
    assert pipeline.call_count == 0


def test_external_pdf_is_rejected_before_pdf_loader(private_runtime, panel, tmp_path, monkeypatch):
    main, paths, context, notices = private_runtime
    from PyQt6 import QtPdf
    outside = tmp_path / 'parent.pdf'
    outside.write_bytes(b'%PDF private file')
    loader = Mock(side_effect=AssertionError('must reject before QPdfDocument'))
    monkeypatch.setattr(QtPdf, 'QPdfDocument', loader)
    assert panel.import_pdf(str(outside)) == 0
    assert loader.call_count == 0


def test_external_roster_import_does_not_load_names(private_runtime, panel, tmp_path, monkeypatch):
    main, paths, context, notices = private_runtime
    outside = tmp_path / 'parent-names.txt'
    outside.write_text('real private name', encoding='utf-8')
    monkeypatch.setattr(main.QFileDialog, 'getOpenFileName', lambda *args: (str(outside), ''))
    before = list(panel.roster)
    panel.import_roster()
    assert panel.roster == before


def test_external_autosave_alias_cannot_queue_writer(private_runtime, panel, tmp_path, monkeypatch):
    main, paths, context, notices = private_runtime
    from test_document_safety_610 import ink
    outside = tmp_path / 'parent-autosaves'
    outside.mkdir()
    sentinel = outside / 'autosave_20000101_000000.json'
    sentinel.write_bytes(b'user recovery data')
    ink(panel.canvas, 'private-practice-ink')
    writer = Mock(side_effect=AssertionError('must reject before autosave worker'))
    monkeypatch.setattr(main, 'AUTOSAVE_DIR', str(outside))
    monkeypatch.setattr(main, 'atomic_write_autosave', writer)
    panel.auto_save()
    assert not panel.wait_for_autosave(3)
    assert writer.call_count == 0 and panel._autosave_executor is None
    assert sentinel.read_bytes() == b'user recovery data'
    panel._cleanup_autosave_files(keep_hours=0, keep_max=0)
    assert sentinel.read_bytes() == b'user recovery data'


def test_global_callback_does_not_route_parent_hotkey_while_teaching_suspended(private_runtime, panel):
    main, paths, context, notices = private_runtime
    requests = []
    panel.background_requested.connect(lambda: requests.append(True))
    panel._teaching_suspended = True
    assert panel.on_global_key_press(main.keyboard.Key.f12) is None
    assert requests == []


def test_explicit_no_keyboard_flag_never_constructs_hook_in_normal_process(private_runtime, monkeypatch):
    main, paths, context, notices = private_runtime
    monkeypatch.setattr(main, 'RUNTIME_CONTEXT', RuntimeContext(RuntimePaths.for_normal(paths.app_dir)))
    monkeypatch.setenv('MYSCREENDRAW_NO_KEYBOARD', '1')
    listener = Mock()
    monkeypatch.setattr(main.keyboard, 'Listener', listener)
    app = QApplication.instance()
    prior = set(app.topLevelWidgets())
    panel = main.ControlPanel()
    try:
        assert panel.listener is None and listener.call_count == 0
    finally:
        if panel.listener is not None:
            panel.listener.stop()
        for widget in set(app.topLevelWidgets()) - prior:
            for timer in widget.findChildren(main.QTimer):
                timer.stop()
            widget.hide()
            widget.deleteLater()
        drain(app)


def test_direct_practice_install_callback_never_reads_or_deletes_external_download(private_runtime, panel, tmp_path, monkeypatch):
    main, paths, context, notices = private_runtime
    source = tmp_path / 'parent-download.zip'
    source.write_bytes(b'user-owned download')
    validate = Mock(side_effect=AssertionError('practice cannot validate installation'))
    remove = Mock(side_effect=AssertionError('practice cannot remove installer directories'))
    monkeypatch.setattr(main, 'validate_update_zip', validate)
    monkeypatch.setattr(main.shutil, 'rmtree', remove)
    panel._on_update_downloaded(str(source), None)
    assert validate.call_count == 0 and remove.call_count == 0
    assert source.read_bytes() == b'user-owned download'


def test_constructor_cannot_make_private_capabilities_with_normal_process_paths(private_runtime, monkeypatch):
    main, paths, context, notices = private_runtime
    monkeypatch.setattr(main, 'RUNTIME_CONTEXT', RuntimeContext(RuntimePaths.for_normal(paths.app_dir)))
    with pytest.raises(ValueError):
        main.ControlPanel(runtime=context)
    with pytest.raises(ValueError):
        main.DrawingCanvas(runtime=context)


def test_private_file_rejection_has_localized_explanation(private_runtime, panel, tmp_path):
    main, paths, context, notices = private_runtime
    outside = tmp_path / 'outside.png'
    outside.write_bytes(b'test-owned bytes')
    assert panel.import_image_file(str(outside)) is None
    assert notices and main.tr('teaching_private_path_rejected') in notices[-1][0]
