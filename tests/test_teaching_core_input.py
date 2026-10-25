# SPDX-License-Identifier: GPL-3.0-or-later
"""C01 selection and file actions through the real Qt input barrier, offscreen."""
import inspect
import textwrap
from pathlib import Path
from unittest.mock import Mock

import pytest
from PyQt6.QtCore import QPoint, QPointF, QRectF, QSizeF, QTimer, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialogButtonBox, QFileDialog

from test_teaching_core_course import core_host, step
from test_teaching_application_isolation import drain


def click(host, target, window_input=False):
    widget = host.registry.resolve(target)
    assert widget is not None and widget.isEnabled(), target
    if window_input:
        surface = widget.window().windowHandle()
        point = widget.mapTo(widget.window(), widget.rect().center())
        QTest.mousePress(surface, Qt.MouseButton.LeftButton, pos=point)
        QTest.qWait(200)
        QTest.mouseRelease(surface, Qt.MouseButton.LeftButton, pos=point)
    else:
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
    drain(QApplication.instance())


def select_contract(host, method):
    canvas = host.panel.canvas
    assert QApplication.instance().platformName() == 'offscreen'
    drain(QApplication.instance())
    click(host, 'toolbar.undo')
    step(host, 'redo')
    click(host, 'toolbar.redo')
    step(host, 'choose')
    click(host, 'toolbar.select')
    assert host.presenter.engine.sequence_index == 1
    assert host.presenter.active_target_id == 'canvas.ink'
    # Empty input cannot count as selecting an object.
    QTest.mouseClick(canvas.windowHandle(), Qt.MouseButton.LeftButton, pos=QPoint(700, 80))
    drain(QApplication.instance())
    step(host, 'choose')
    assert not canvas.selected_ids
    if method == 'click':
        start = end = QPoint(170, 150)
    else:
        bounds = canvas.page_content_bounds(canvas.live_page()).adjusted(-30, -30, 30, 30)
        start, end = bounds.topLeft().toPoint(), bounds.bottomRight().toPoint()
        if method == 'reverse':
            start, end = end, start
    surface = canvas.windowHandle()
    QTest.mousePress(surface, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(surface, end)
    drain(QApplication.instance())
    step(host, 'choose')
    if method != 'click':
        assert canvas.selection_rect is not None and abs(canvas.selection_rect.width()) > 100
    QTest.mouseRelease(surface, Qt.MouseButton.LeftButton, pos=end)
    drain(QApplication.instance())
    assert canvas.selected_ids, 'Real input must select an existing object'
    step(host, 'move')


@pytest.mark.parametrize('core_host', ['c01.select'], indirect=True)
@pytest.mark.parametrize('method', ['click', 'rectangle', 'reverse'])
def test_core_selection_input_advances_after_release(core_host, method):
    select_contract(core_host[0], method)


def original_rectangle_selection(monkeypatch, module):
    source = textwrap.dedent(inspect.getsource(module.DrawingCanvas.select_objects_in_rect))
    added = ('    for stroke_id in {segment["id"] for segment in self.all_segments}:\n'
             '        if normalized.intersects(self.object_bounds(stroke_id)):\n'
             '            self.selected_ids.add(stroke_id)\n'
             '    for item in self.text_items:\n'
             '        if normalized.intersects(self.text_bounds(item)):\n'
             '            self.selected_ids.add(item["id"])\n')
    assert source.count(added) == 1
    namespace = dict(vars(module))
    exec(compile(source.replace(added, ''), '<old-rectangle-selection>', 'exec'), namespace)
    monkeypatch.setattr(module.DrawingCanvas, 'select_objects_in_rect', namespace['select_objects_in_rect'])


@pytest.mark.parametrize('core_host', ['c01.select'], indirect=True)
def test_selection_regression_rejects_original_ink_omission(core_host, monkeypatch):
    host, _ = core_host
    original_rectangle_selection(monkeypatch, host.module)
    with pytest.raises(AssertionError, match='Real input must select an existing object'):
        select_contract(host, 'rectangle')
    step(host, 'choose')


@pytest.mark.parametrize('core_host', ['c01.select'], indirect=True)
def test_reverse_selection_rejects_original_empty_rectangle_check(core_host, monkeypatch):
    host, _ = core_host
    source = textwrap.dedent(inspect.getsource(host.module.DrawingCanvas.mouseReleaseEvent))
    old = 'if self.draw_state == "SELECT" and self.selection_rect is not None:'
    assert source.count(old) == 1
    namespace = dict(vars(host.module))
    exec(compile(source.replace(old, 'if self.draw_state == "SELECT" and self.selection_rect:'),
                 '<old-reverse-selection>', 'exec'), namespace)
    monkeypatch.setattr(host.module.DrawingCanvas, 'mouseReleaseEvent', namespace['mouseReleaseEvent'])
    with pytest.raises(AssertionError, match='Real input must select an existing object'):
        select_contract(host, 'reverse')


def all_objects_contract(host):
    # This legacy contract deliberately includes editable images.
    host.panel.set_preserve_original_images(False, persist=False)
    canvas = host.panel.canvas
    canvas.create_text_item(QPointF(500, 100), text='Private example')
    shape = canvas.make_shape_item(QRectF(520, 250, 80, 70))
    canvas.shape_items.append(shape)
    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.GlobalColor.blue)
    canvas.image_items.append({'id': 992, 'pos': QPointF(520, 350), 'size': QSizeF(80, 50),
                               'rotation': 30, 'pixmap': pixmap})
    ids = {item['id'] for items in (canvas.all_segments, canvas.text_items,
                                   canvas.shape_items, canvas.image_items) for item in items}
    assert len(ids) >= 4
    signature = canvas.document_signature()
    area = canvas.page_content_bounds(canvas.live_page()).adjusted(-20, -20, 20, 20)
    canvas.select_objects_in_rect(QRectF(area.bottomRight(), area.topLeft()))
    assert canvas.selected_ids == ids, 'Rectangle selection must include every object type'
    assert canvas.document_signature() == signature
    canvas.select_objects_in_rect(QRectF(10000, 10000, 30, 30))
    assert not canvas.selected_ids


@pytest.mark.parametrize('core_host', ['c01.select'], indirect=True)
def test_rectangle_selects_ink_text_shapes_and_images_without_editing(core_host):
    all_objects_contract(core_host[0])


@pytest.mark.parametrize('core_host', ['c01.select'], indirect=True)
def test_object_type_assertions_reject_old_selection(core_host, monkeypatch):
    host, _ = core_host
    original_rectangle_selection(monkeypatch, host.module)
    with pytest.raises(AssertionError, match='Rectangle selection must include every object type'):
        all_objects_contract(host)


@pytest.mark.parametrize('core_host', ['c01.files'], indirect=True)
@pytest.mark.parametrize('window_input', [False, True])
def test_core_save_button_opens_chooser_and_advances(core_host, monkeypatch, window_input):
    host, _ = core_host
    assert QApplication.instance().platformName() == 'offscreen'
    path = host.request.paths.data_dir / '1.msd'
    choose = Mock(return_value=(str(path), ''))
    monkeypatch.setattr(host.module.QFileDialog, 'getSaveFileName', choose)
    drain(QApplication.instance())
    click(host, 'file.save', window_input)
    choose.assert_called_once()
    assert choose.call_args.args[0] is host.panel.canvas
    assert Path(choose.call_args.args[2]) == path
    assert path.is_file()
    step(host, 'open')


def retry_wrong_filename_contract(host, monkeypatch, cancel=False):
    wrong = host.request.paths.data_dir / 'wrong-name.msd'
    expected = host.request.paths.data_dir / '1.msd'
    choose = Mock(side_effect=[(str(wrong), ''), ('' if cancel else str(expected), '')])
    monkeypatch.setattr(host.module.QFileDialog, 'getSaveFileName', choose)
    click(host, 'file.save')
    assert wrong.is_file() and not expected.exists()
    step(host, 'save')
    click(host, 'file.save')
    assert choose.call_count == 2, 'Save must reopen the chooser to correct a wrong tutorial filename'
    assert expected.is_file() is not cancel
    assert wrong.is_file()
    assert Path(host.panel.project_path) == (wrong if cancel else expected)
    step(host, 'save' if cancel else 'open')


@pytest.mark.parametrize('core_host', ['c01.files'], indirect=True)
@pytest.mark.parametrize('cancel', [False, True])
def test_save_retries_chooser_after_wrong_filename(core_host, monkeypatch, cancel):
    retry_wrong_filename_contract(core_host[0], monkeypatch, cancel)


@pytest.mark.parametrize('core_host', ['c01.files'], indirect=True)
def test_wrong_filename_regression_rejects_original_silent_reuse(core_host, monkeypatch):
    host, _ = core_host

    def old_save(panel):
        with host.module.teaching_document_action(panel, ('project.saved',)):
            panel.show_only_sub(None)
            return panel.save_project()

    monkeypatch.setattr(host.module.ControlPanel, 'save_project_from_file_panel', old_save)
    # Existing button signals still hold the original bound method; reconnect
    # only that callback to the exact old menu action, retaining the input barrier.
    host.panel.btn_save_project.clicked.disconnect()
    host.panel.btn_save_project.clicked.connect(host.panel.save_project_from_file_panel)
    with pytest.raises(AssertionError, match='Save must reopen the chooser'):
        retry_wrong_filename_contract(host, monkeypatch)


def file_dialog_contract(host, cancel):
    app = QApplication.instance()
    assert app.platformName() == 'offscreen'
    path = host.request.paths.data_dir / '1.msd'
    seen, failures = [], []

    def respond():
        dialog = app.activeModalWidget()
        try:
            assert isinstance(dialog, QFileDialog), 'A real file chooser must open'
            assert dialog.parentWidget() is host.panel.canvas, 'Chooser must use the visible canvas owner'
            assert host.presenter._dialog_depth and not host.presenter.barrier.installed
            assert not host.presenter.controller.isVisible()
            assert Path(dialog.selectedFiles()[0]) == path, 'Chooser must suggest 1.msd'
            seen.append(dialog.acceptMode())
            box = dialog.findChild(QDialogButtonBox)
            role = (QDialogButtonBox.StandardButton.Cancel if cancel else
                    QDialogButtonBox.StandardButton.Save if dialog.acceptMode() == QFileDialog.AcceptMode.AcceptSave
                    else QDialogButtonBox.StandardButton.Open)
            button = box.button(role)
            assert button is not None and button.isEnabled()
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        except BaseException as exc:
            failures.append(exc)
            if isinstance(dialog, QFileDialog):
                dialog.reject()

    # Drive the actual non-native offscreen chooser, not a mocked successful return.
    for target in (('file.save',) if cancel else ('file.save', 'file.open')):
        QTimer.singleShot(100, respond)
        click(host, target)
        if failures:
            raise failures[0]
    assert seen == ([QFileDialog.AcceptMode.AcceptSave] if cancel else
                    [QFileDialog.AcceptMode.AcceptSave, QFileDialog.AcceptMode.AcceptOpen])
    assert path.is_file() is not cancel
    step(host, 'save' if cancel else 'preview')
    assert host.presenter._dialog_depth == 0 and host.presenter.barrier.installed
    assert host.presenter.controller.isVisible()


@pytest.mark.parametrize('core_host', ['c01.files'], indirect=True)
@pytest.mark.parametrize('cancel', [False, True])
def test_real_save_and_reopen_dialogs_are_usable(core_host, cancel):
    file_dialog_contract(core_host[0], cancel)


@pytest.mark.parametrize('core_host', ['c01.files'], indirect=True)
@pytest.mark.parametrize('mutation', ['owner', 'filename'])
def test_real_chooser_contract_rejects_old_owner_and_blank_name(core_host, monkeypatch, mutation):
    host, _ = core_host
    method = host.module.ControlPanel._save_project_operation
    source = textwrap.dedent(inspect.getsource(method))
    old, new = (('owner = self.canvas if practice else self', 'owner = self') if mutation == 'owner' else
                ('self.runtime_context.paths.data_dir / "1.msd"', 'self.runtime_context.paths.data_dir'))
    assert source.count(old) == 1
    namespace = dict(vars(host.module))
    exec(compile(source.replace(old, new), '<old-save-dialog>', 'exec'), namespace)
    monkeypatch.setattr(host.module.ControlPanel, '_save_project_operation', namespace['_save_project_operation'])
    with pytest.raises(AssertionError, match='Chooser must'):
        file_dialog_contract(host, False)


def test_core_file_copy_and_waits_agree_on_short_filename():
    from teaching.core_copy import CORE_COPY
    from test_teaching_core_course import formal_catalog
    for key in ('teaching_c01_files_save_body', 'teaching_c01_files_open_body'):
        assert all('1.msd' in text and 'practice.msd' not in text for text in CORE_COPY[key])
    catalog, _ = formal_catalog()
    for item in catalog.chapter_by_id('c01.files').steps[:2]:
        assert dict(item.wait.clauses[0].equals)['path'] == '1.msd'
