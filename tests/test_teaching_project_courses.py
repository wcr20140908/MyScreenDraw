# SPDX-License-Identifier: GPL-3.0-or-later
"""C08 formal file courses through owned offscreen controls and private files."""
import json
from pathlib import Path
from string import Formatter

import pytest
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from persistence import PROJECT_KIND, AUTOSAVE_KIND, normalize_project_data, read_json_maybe_gz
from teaching.application import application_catalog
from teaching.packaging import collect_teaching_datas
from test_teaching_business_adapters import draw_ink
from test_teaching_writing_courses import ROOT, writing_host, next_info, assert_step, finished


def test_c08_catalog_copy_and_private_assets_are_complete():
    import main, i18n
    from teaching.file_copy import FILE_COPY
    catalog, loader = application_catalog(main, ROOT)
    course = catalog.course_by_id('c08')
    assert [chapter.id for chapter in course.chapters] == ['c08.save', 'c08.open_guard', 'c08.recovery', 'c08.interval']
    assert [len(chapter.steps) for chapter in course.chapters] == [7, 8, 6, 7]
    assert len(FILE_COPY) == 62 and sum(len(values) for values in FILE_COPY.values()) == 496
    for key, values in FILE_COPY.items():
        assert len(values) == 8
        for language, value in zip(i18n._LANGS, values):
            assert i18n.TEXT[language][key] == value and value.strip()
            assert not any(field is not None for _, field, _, _ in Formatter().parse(value))
    bundle = {Path(source) for source, _ in collect_teaching_datas(ROOT)}
    for chapter in course.chapters:
        source = loader.asset_path(loader.fixtures[chapter.fixture])
        data = normalize_project_data(read_json_maybe_gz(str(source)), kind=PROJECT_KIND)
        assert data['metadata']['synthetic_teaching'] is True and len(data['pages']) == 2
        assert source in bundle


@pytest.mark.parametrize('writing_host', ['c08.save'], indirect=True)
def test_save_course_writes_updates_copies_and_reopens_current_private_project(writing_host, monkeypatch):
    host, progress = writing_host
    panel = host.panel
    primary = host.request.paths.data_dir / 'practice-first.msd'
    copied = host.request.paths.data_dir / 'practice-copy.msd'
    destinations = iter([primary, copied])
    monkeypatch.setattr(host.module.QFileDialog, 'getSaveFileName', lambda *args: (str(next(destinations)), ''))
    next_info(host)
    assert_step(host, 'save_first'); panel.btn_save_project.click()
    assert primary.is_file() and panel.project_path == str(primary)
    assert_step(host, 'edit'); draw_ink(panel.canvas)
    expected = panel.canvas.serialized_document_pages()
    assert_step(host, 'save_again'); panel.btn_save_project.click()
    assert not panel.has_unsaved_changes()
    assert_step(host, 'save_as'); panel.btn_save_project_as.click()
    assert copied.is_file() and panel.project_path == str(copied)
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args: (str(copied), ''))
    assert_step(host, 'reopen'); panel.btn_open_project.click()
    assert panel.canvas.serialized_document_pages() == expected
    assert_step(host, 'done'); next_info(host); finished(host, progress)


@pytest.mark.parametrize('writing_host', ['c08.open_guard'], indirect=True)
def test_open_guard_course_preserves_cancels_discards_then_saves_real_work(writing_host, monkeypatch):
    host, progress = writing_host
    panel = host.panel
    sample = Path(panel._teaching_file_open_path)
    defaults = []
    def choose_sample(owner, title, default, file_filter):
        defaults.append(default)
        return str(sample), file_filter
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', choose_sample)
    assert sample.is_file() and sample.is_relative_to(host.request.paths.data_dir)
    next_info(host)
    assert_step(host, 'make_dirty'); draw_ink(panel.canvas)
    original = panel.canvas.document_signature()
    assert_step(host, 'cancel_open')
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: QMessageBox.StandardButton.Cancel)
    panel.btn_open_project.click()
    assert panel.canvas.document_signature() == original
    assert_step(host, 'discard_open')
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: QMessageBox.StandardButton.Discard)
    panel.btn_open_project.click()
    assert panel.project_path == str(sample) and panel.canvas.document_signature() != original
    assert_step(host, 'make_dirty_again'); draw_ink(panel.canvas)
    expected = panel.canvas.serialized_document_pages()
    assert_step(host, 'save_then_open')
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: QMessageBox.StandardButton.Save)
    panel.btn_open_project.click()
    assert panel.canvas.serialized_document_pages() == expected and not panel.has_unsaved_changes()
    assert list(map(Path, defaults)) == [sample] * 3, 'Every Open must suggest the chapter sample'
    assert_step(host, 'guard_info'); next_info(host)
    assert_step(host, 'done'); next_info(host); finished(host, progress)


@pytest.mark.parametrize('writing_host', ['c08.recovery'], indirect=True)
def test_recovery_course_previews_without_replacement_then_applies_history_and_saves(writing_host, monkeypatch):
    host, progress = writing_host
    panel = host.panel
    candidates = panel._list_autosave_files()
    assert len(candidates) == 1
    history = normalize_project_data(read_json_maybe_gz(candidates[0][1]), kind=AUTOSAVE_KIND)
    assert len(history['pages']) == 2
    original = panel.canvas.document_signature()
    next_info(host)
    assert_step(host, 'preview')
    monkeypatch.setattr(host.module.RecoveryDialog, 'exec', lambda dialog: QDialog.DialogCode.Rejected)
    panel.btn_recovery.click()
    assert panel.canvas.document_signature() == original
    assert_step(host, 'restore')
    monkeypatch.setattr(host.module.RecoveryDialog, 'exec', lambda dialog: QDialog.DialogCode.Accepted)
    panel.btn_recovery.click()
    assert panel.project_dirty and panel.project_path is None and len(panel.canvas.pages) == 2
    assert panel.canvas.document_signature() != original
    assert_step(host, 'inspect_info'); next_info(host)
    saved = host.request.paths.data_dir / 'restored.msd'
    monkeypatch.setattr(host.module.QFileDialog, 'getSaveFileName', lambda *args: (str(saved), ''))
    assert_step(host, 'save_restored'); panel.btn_save_project.click()
    assert saved.is_file() and not panel.has_unsaved_changes()
    assert_step(host, 'done'); next_info(host); finished(host, progress)


@pytest.mark.parametrize('writing_host', ['c08.interval'], indirect=True)
def test_interval_course_keeps_custom_control_visible_and_persists_real_values(writing_host):
    host, progress = writing_host
    panel = host.panel
    assert panel.autosave_interval_seconds == 30
    next_info(host)
    assert_step(host, 'preset_60')
    preferences = panel.document_preferences
    preferences.interval_combo.setCurrentIndex(preferences.interval_combo.findData(60))
    assert_step(host, 'custom')
    preferences.interval_combo.setCurrentIndex(preferences.interval_combo.findData(-1))
    assert_step(host, 'custom_75')
    assert preferences.interval_custom.isVisible()
    QApplication.instance().processEvents()
    viewport = panel.settings_scroll.viewport()
    clip = QRect(viewport.mapToGlobal(QPoint()), viewport.size())
    assert clip.contains(host.registry.global_rect('settings.autosave_custom'))
    preferences.interval_custom.setValue(75)
    assert_step(host, 'preset_30')
    preferences.interval_combo.setCurrentIndex(preferences.interval_combo.findData(30))
    config = json.loads(host.request.paths.config_file.read_text(encoding='utf-8'))
    assert config['autosave_interval_seconds'] == 30 and panel.autosave_timer.interval() == 30000
    assert_step(host, 'cost_info'); next_info(host)
    assert_step(host, 'done'); next_info(host); finished(host, progress)


@pytest.mark.parametrize('writing_host', ['c08.open_guard'], indirect=True)
def test_open_picker_cancel_cannot_impersonate_unsaved_dialog_cancel(writing_host, monkeypatch):
    host, _ = writing_host
    panel = host.panel
    next_info(host); draw_ink(panel.canvas)
    assert_step(host, 'cancel_open')
    monkeypatch.setattr(host.module.QFileDialog, 'getOpenFileName', lambda *args: ('', ''))
    monkeypatch.setattr(QMessageBox, 'exec', lambda self: pytest.fail('no unsaved dialog without a file'))
    panel.btn_open_project.click()
    assert_step(host, 'cancel_open')


@pytest.mark.parametrize('writing_host', ['c08.open_guard'], indirect=True)
@pytest.mark.parametrize('cancel_picker', [False, True])
def test_open_guard_picker_shows_and_preselects_its_private_sample(writing_host, monkeypatch, cancel_picker):
    from PyQt6.QtCore import QTimer, Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QFileDialog, QDialogButtonBox
    host, _ = writing_host
    panel, app = host.panel, QApplication.instance()
    assert app.platformName() == 'offscreen'
    sample = Path(panel._teaching_file_open_path)
    next_info(host); draw_ink(panel.canvas)
    original = panel.canvas.document_signature()
    seen, errors, prompts = [], [], []

    def respond():
        dialog = app.activeModalWidget()
        try:
            assert isinstance(dialog, QFileDialog)
            seen.append(True)
            assert Path(dialog.directory().absolutePath()) == sample.parent, 'Chooser must display the sample folder'
            assert list(map(Path, dialog.selectedFiles())) == [sample], 'Chooser must preselect the existing .msd sample'
            assert sample.is_file()
            normalize_project_data(read_json_maybe_gz(str(sample)), kind=PROJECT_KIND)
            buttons = dialog.findChild(QDialogButtonBox)
            button = buttons.button(QDialogButtonBox.StandardButton.Cancel if cancel_picker
                                    else QDialogButtonBox.StandardButton.Open)
            assert button.isEnabled()
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        except BaseException as exc:
            errors.append(exc)
            if isinstance(dialog, QFileDialog):
                dialog.reject()

    def unsaved_prompt(box):
        prompts.append(True)
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, 'exec', unsaved_prompt)
    QTimer.singleShot(100, respond)
    panel.btn_open_project.click()
    if errors:
        raise errors[0]
    assert seen == [True]
    assert prompts == ([] if cancel_picker else [True])
    assert panel.canvas.document_signature() == original
    assert_step(host, 'cancel_open' if cancel_picker else 'discard_open')


@pytest.mark.parametrize('writing_host', ['c08.save'], indirect=True)
def test_save_as_same_destination_cannot_complete_the_new_destination_lesson(writing_host, monkeypatch):
    host, _ = writing_host
    panel = host.panel
    saved = host.request.paths.data_dir / 'original.msd'
    monkeypatch.setattr(host.module.QFileDialog, 'getSaveFileName', lambda *args: (str(saved), ''))
    next_info(host); panel.btn_save_project.click(); draw_ink(panel.canvas); panel.btn_save_project.click()
    assert_step(host, 'save_as'); panel.btn_save_project_as.click()
    assert_step(host, 'save_as')
