# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated Qt view contracts; offscreen is not native-screen acceptance."""
from __future__ import annotations

import gc
import importlib
import os
from pathlib import Path
import subprocess
import sys
import weakref

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, QRect, QSize, Qt
from PyQt6.QtGui import (
    QKeySequence, QNativeGestureEvent, QPointingDevice, QShortcut, QShortcutEvent, QTabletEvent,
    QTouchEvent, QWheelEvent,
)
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication, QLineEdit, QPushButton, QWidget

from teaching.models import (
    END_CHAPTER, TutorialCatalog, TutorialChapter, TutorialCourse, TutorialGroup,
    TutorialStep, WaitClause, WaitSpec,
)
from teaching.state import TutorialStateStore


def widgets():
    # Import in the test body so the initial RED is a test failure, not collection failure.
    return importlib.import_module('teaching.widgets')


def drain(app):
    for _ in range(4):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(scope='session')
def application():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def qt_app(application):
    previous = set(application.topLevelWidgets())
    yield application
    for widget in application.topLevelWidgets():
        if widget not in previous and not sip.isdeleted(widget):
            widget.hide()
            widget.deleteLater()
    drain(application)


@pytest.fixture
def translate():
    calls = []

    def tr(key):
        assert key.startswith('teaching_'), f'Unlocalized teaching text: {key}'
        calls.append(key)
        if key == 'teaching_progress':
            return 'Localized step {current} of {total}'
        if key == 'teaching_course_progress':
            return 'Localized chapters {completed}/{total} completed'
        return f'Localized [{key}]'

    tr.calls = calls
    return tr


def step(kind='information'):
    return TutorialStep(
        id='intro', title_key='teaching_step_title', body_key='teaching_step_body',
        kind=kind, target='toolbar.pen' if kind == 'operation' else None,
        input_policy='target_only' if kind == 'operation' else 'free',
        reveal=(), allowed_targets=(),
        wait=WaitSpec((WaitClause('ink.committed', 'success'),)) if kind == 'operation' else None,
        next=END_CHAPTER,
    )


@pytest.fixture
def catalog():
    chapters = tuple(
        TutorialChapter(f'c01.{name}', f'teaching_chapter_{name}', 'fixture', (step(),))
        for name in ('new', 'complete', 'skip', 'active', 'review')
    )
    return TutorialCatalog(
        courses=(
            TutorialCourse('c01', 2, 2, 'teaching_course_one', chapters),
            TutorialCourse('c02', 1, 1, 'teaching_course_two', (
                TutorialChapter('c02.extra', 'teaching_chapter_extra', 'fixture', (step(),)),
            )),
        ),
        groups=(TutorialGroup('basics', 'teaching_group_basics', ('c01',)),),
    )


@pytest.fixture
def store(tmp_path):
    return TutorialStateStore(tmp_path / 'tutorial-state.json')


def populated_store(store):
    store.record_chapter('c01.complete', 'completed', compat_revision=2)
    store.record_chapter('c01.skip', 'skipped', compat_revision=2)
    store.record_chapter('c01.review', 'completed', compat_revision=1)
    store.sync_catalog({'c01.review': 2})
    store.record_chapter('c01.active', 'in_progress', compat_revision=2)
    return store


def button(parent, x=10, y=10):
    value = QPushButton('Test input', parent)
    value.setGeometry(x, y, 110, 30)
    value.show()
    return value


@pytest.fixture
def host(qt_app):
    value = QWidget()
    value.setGeometry(40, 40, 560, 350)
    value.show()
    drain(qt_app)
    return value


def test_import_does_not_load_main_or_install_global_hooks():
    code = '''
import importlib.abc, sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'main', 'keyboard', 'pynput'}:
            raise AssertionError('view module loaded runtime or global hooks: ' + fullname)
sys.meta_path.insert(0, Guard())
import teaching.widgets
from PyQt6.QtWidgets import QApplication
assert QApplication.instance() is None
'''
    result = subprocess.run(
        [sys.executable, '-B', '-c', code], cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_center_shows_groups_courses_chapters_and_distinct_statuses(qt_app, catalog, store, translate):
    center = widgets().TeachingCenter(catalog, populated_store(store), translate)
    assert center.tree.topLevelItemCount() == 2  # group and ungrouped course
    group = center.tree.topLevelItem(0)
    assert group.text(0) == translate('teaching_group_basics')
    course = group.child(0)
    assert course.text(0) == translate('teaching_course_one')
    assert course.childCount() == 5
    expected = {
        'new': 'not_started', 'complete': 'completed', 'skip': 'skipped',
        'active': 'in_progress', 'review': 'not_started',
    }
    for name, status in expected.items():
        assert center.select_chapter('c01', f'c01.{name}')
        item = center.tree.currentItem()
        assert item.text(0) == translate(f'teaching_chapter_{name}')
        assert translate(f'teaching_status_{status}') in item.text(1)
        assert (translate('teaching_status_needs_review') in item.text(1)) == (name == 'review')
    assert center.select_chapter('c02', 'c02.extra')


def test_center_start_replay_resume_are_signals_only(qt_app, catalog, store, translate):
    populated_store(store)
    before = store.snapshot()
    before_bytes = store.path.read_bytes()
    center = widgets().TeachingCenter(catalog, store, translate)
    requests = QSignalSpy(center.start_requested)
    center.show()
    drain(qt_app)
    assert center.selected_chapter == ('c01', 'c01.active')
    assert center.resume_button.isEnabled()
    center.select_chapter('c01', 'c01.skip')
    QTest.mouseClick(center.start_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(center.replay_button, Qt.MouseButton.LeftButton)
    QTest.mouseClick(center.resume_button, Qt.MouseButton.LeftButton)
    assert list(requests) == [
        ['c01', 'c01.skip'], ['c01', 'c01.skip'], ['c01', 'c01.active'],
    ]
    assert store.snapshot() == before
    assert store.path.read_bytes() == before_bytes
    assert center.close_button.isEnabled()
    QTest.mouseClick(center.close_button, Qt.MouseButton.LeftButton)
    drain(qt_app)
    assert sip.isdeleted(center)
    assert store.snapshot() == before


def test_center_does_not_create_progress_on_open_selection_hide_or_close(qt_app, catalog, store, translate):
    center = widgets().TeachingCenter(catalog, store, translate)
    assert not center.resume_button.isEnabled()
    assert not center.start_button.isEnabled()
    center.show()
    center.select_chapter('c01', 'c01.new')
    center.hide()
    center.close()
    drain(qt_app)
    assert not store.path.exists()
    assert not store.snapshot()['chapters']


def test_center_rejects_stale_resume_and_non_chapter_selection(qt_app, catalog, store, translate):
    store.record_chapter('c99.removed', 'in_progress', compat_revision=1)
    center = widgets().TeachingCenter(catalog, store, translate)
    requests = QSignalSpy(center.start_requested)
    assert not center.resume_button.isEnabled()
    assert not center.select_chapter('c02', 'c01.complete')
    center.tree.setCurrentItem(center.tree.topLevelItem(0))
    assert center.selected_chapter is None
    assert not center.start_button.isEnabled()
    assert not center.replay_button.isEnabled()
    assert len(requests) == 0


def test_center_refresh_preserves_selection_without_writes(qt_app, catalog, store, translate):
    center = widgets().TeachingCenter(catalog, store, translate)
    center.select_chapter('c01', 'c01.new')
    store.record_chapter('c01.new', 'skipped', compat_revision=2)
    before = store.path.read_bytes()
    center.refresh()
    assert center.selected_chapter == ('c01', 'c01.new')
    assert center.tree.currentItem().text(1) == translate('teaching_status_skipped')
    assert store.path.read_bytes() == before



C01_CHAPTERS = (
    ('c01', 'c01.new'), ('c01', 'c01.complete'), ('c01', 'c01.skip'),
    ('c01', 'c01.active'), ('c01', 'c01.review'),
)
ALL_CHAPTERS = C01_CHAPTERS + (('c02', 'c02.extra'),)
UNFINISHED_CHAPTERS = (
    ('c01', 'c01.new'), ('c01', 'c01.skip'), ('c01', 'c01.active'),
    ('c01', 'c01.review'), ('c02', 'c02.extra'),
)


def visible_chapters(center):
    result = []

    def visit(item):
        if item.isHidden():
            return
        pair = item.data(0, Qt.ItemDataRole.UserRole)
        if pair is not None:
            result.append(tuple(pair))
        for index in range(item.childCount()):
            visit(item.child(index))

    for index in range(center.tree.topLevelItemCount()):
        visit(center.tree.topLevelItem(index))
    return tuple(result)


def set_center_filter(center, status):
    assert hasattr(center, 'filter_combo'), 'TeachingCenter needs a status filter'
    index = center.filter_combo.findData(status)
    assert index >= 0, f'Missing stable filter value: {status}'
    center.filter_combo.setCurrentIndex(index)


@pytest.fixture
def localized_titles(translate):
    titles = {
        'teaching_course_one': 'Écriture · Straße',
        'teaching_course_two': 'Files and tools',
        'teaching_chapter_new': 'First strokes',
        'teaching_chapter_complete': 'Finished shapes',
        'teaching_chapter_skip': 'Pressure practice',
        'teaching_chapter_active': 'Active pen',
        'teaching_chapter_review': 'Review brush',
        'teaching_chapter_extra': '保存文件',
    }

    def tr(key):
        return titles[key] if key in titles else translate(key)

    return tr


def test_center_filter_controls_are_localized(qt_app, catalog, store, translate):
    center = widgets().TeachingCenter(catalog, store, translate)
    assert hasattr(center, 'search_edit'), 'TeachingCenter needs a keyword search'
    assert center.search_edit.placeholderText() == translate('teaching_search')
    assert hasattr(center, 'filter_combo'), 'TeachingCenter needs a status filter'
    assert center.filter_combo.count() == 3
    for index, status in enumerate(('all', 'completed', 'unfinished')):
        assert center.filter_combo.itemData(index) == status
        assert center.filter_combo.itemText(index) == translate(f'teaching_filter_{status}')
    assert center.filter_combo.currentData() == 'all'
    assert not center.search_edit.text()


@pytest.mark.parametrize('query,expected', [
    ('', ALL_CHAPTERS), ('   ', ALL_CHAPTERS),
    ('éCRITURE', C01_CHAPTERS), ('STRASSE', C01_CHAPTERS),
    ('  c01  ', C01_CHAPTERS), ('stROKes', (('c01', 'c01.new'),)),
    ('C01.SKIP', (('c01', 'c01.skip'),)),
    ('FILES AND TOOLS', (('c02', 'c02.extra'),)),
    ('C02.EXTRA', (('c02', 'c02.extra'),)), ('保存', (('c02', 'c02.extra'),)),
    ('no such chapter', ()), ('teaching_chapter_new', ()),
])
def test_center_search_matches_localized_titles_and_stable_ids(
        qt_app, catalog, store, localized_titles, query, expected):
    center = widgets().TeachingCenter(catalog, store, localized_titles)
    assert hasattr(center, 'search_edit'), 'TeachingCenter needs a keyword search'
    center.search_edit.setText(query)
    assert visible_chapters(center) == expected


@pytest.mark.parametrize('status,expected', [
    ('all', ALL_CHAPTERS), ('completed', (('c01', 'c01.complete'),)),
    ('unfinished', UNFINISHED_CHAPTERS),
])
@pytest.mark.parametrize('replay_status', [None, 'skipped', 'in_progress'])
def test_center_filters_use_current_completion_not_last_attempt(
        qt_app, catalog, store, translate, status, expected, replay_status):
    populated_store(store)
    if replay_status is not None:
        assert store.record_chapter('c01.complete', replay_status, compat_revision=2)
    center = widgets().TeachingCenter(catalog, store, translate)
    set_center_filter(center, status)
    assert visible_chapters(center) == expected


def test_center_combines_search_and_filter_and_hides_empty_parents(
        qt_app, catalog, store, localized_titles):
    center = widgets().TeachingCenter(catalog, populated_store(store), localized_titles)
    assert hasattr(center, 'search_edit'), 'TeachingCenter needs a keyword search'
    group = center.tree.topLevelItem(0)
    course = group.child(0)
    ungrouped = center.tree.topLevelItem(1)
    center.search_edit.setText('Écriture')
    set_center_filter(center, 'completed')
    assert visible_chapters(center) == (('c01', 'c01.complete'),)
    assert not group.isHidden() and not course.isHidden() and ungrouped.isHidden()
    center.search_edit.setText('C02')
    assert visible_chapters(center) == ()
    assert group.isHidden() and course.isHidden() and ungrouped.isHidden()
    set_center_filter(center, 'unfinished')
    assert visible_chapters(center) == (('c02', 'c02.extra'),)
    assert group.isHidden() and course.isHidden() and not ungrouped.isHidden()
    center.search_edit.clear()
    set_center_filter(center, 'all')
    assert visible_chapters(center) == ALL_CHAPTERS
    assert not group.isHidden() and not course.isHidden() and not ungrouped.isHidden()


def test_center_group_stays_visible_when_any_member_course_matches(
        qt_app, catalog, store, translate):
    grouped = TutorialCatalog(catalog.courses, (
        TutorialGroup('basics', 'teaching_group_basics', ('c01', 'c02')),
    ))
    center = widgets().TeachingCenter(grouped, store, translate)
    assert hasattr(center, 'search_edit'), 'TeachingCenter needs a keyword search'
    center.search_edit.setText('C02')
    group = center.tree.topLevelItem(0)
    assert not group.isHidden()
    assert group.child(0).isHidden() and not group.child(1).isHidden()
    assert visible_chapters(center) == (('c02', 'c02.extra'),)


def test_center_course_progress_counts_entire_course_not_visible_subset(
        qt_app, catalog, store, translate):
    center = widgets().TeachingCenter(catalog, populated_store(store), translate)
    course = center.tree.topLevelItem(0).child(0)
    assert course.text(1) == 'Localized chapters 1/5 completed'
    assert center.tree.topLevelItem(1).text(1) == 'Localized chapters 0/1 completed'
    center.search_edit.setText('C01.NEW')
    set_center_filter(center, 'unfinished')
    assert visible_chapters(center) == (('c01', 'c01.new'),)
    assert course.text(1) == 'Localized chapters 1/5 completed'


@pytest.mark.parametrize('status,expected', [
    ('completed', ()), ('unfinished', ALL_CHAPTERS),
])
def test_center_outdated_completion_is_unfinished_without_syncing_store(
        qt_app, catalog, store, translate, status, expected):
    assert store.record_chapter('c01.complete', 'completed', compat_revision=1)
    before = store.snapshot()
    before_bytes = store.path.read_bytes()
    center = widgets().TeachingCenter(catalog, store, translate)
    course = center.tree.topLevelItem(0).child(0)
    assert course.text(1) == 'Localized chapters 0/5 completed'
    assert translate('teaching_status_needs_review') in course.child(1).text(1)
    set_center_filter(center, status)
    assert visible_chapters(center) == expected
    assert store.snapshot() == before and store.path.read_bytes() == before_bytes


def test_center_hidden_and_stale_activations_cannot_launch_another_selection(
        qt_app, catalog, store, translate):
    center = widgets().TeachingCenter(catalog, store, translate)
    requests = QSignalSpy(center.start_requested)
    assert center.select_chapter('c01', 'c01.new')
    hidden = center.tree.currentItem()
    assert hasattr(center, 'search_edit'), 'TeachingCenter needs a keyword search'
    center.search_edit.setText('C02')
    assert center.selected_chapter is None and center.tree.currentItem() is None
    assert not center.start_button.isEnabled() and not center.replay_button.isEnabled()
    assert not center.select_chapter('c01', 'c01.new')
    center.tree.setCurrentItem(hidden)  # A programmatic/stale selection bypasses the view.
    assert center.selected_chapter is None
    assert not center.start_button.isEnabled() and not center.replay_button.isEnabled()
    center.start_button.click()
    center.replay_button.click()
    center.tree.itemActivated.emit(hidden, 0)
    assert not requests
    assert center.select_chapter('c02', 'c02.extra')
    center.tree.itemActivated.emit(hidden, 0)
    center.tree.itemActivated.emit(center.tree.topLevelItem(0), 0)
    assert not requests
    center.tree.itemActivated.emit(center.tree.currentItem(), 0)
    assert list(requests) == [['c02', 'c02.extra']]


@pytest.mark.parametrize('hidden_parent', ['course', 'group'])
def test_center_chapter_under_hidden_parent_cannot_be_selected_or_started(
        qt_app, catalog, store, translate, hidden_parent):
    center = widgets().TeachingCenter(catalog, store, translate)
    requests = QSignalSpy(center.start_requested)
    assert center.select_chapter('c01', 'c01.new')
    chapter = center.tree.currentItem()
    parent = chapter.parent() if hidden_parent == 'course' else chapter.parent().parent()
    parent.setHidden(True)
    assert not chapter.isHidden()  # Visibility must include ancestors, not only this item's flag.
    assert center.selected_chapter is None
    center.tree.itemActivated.emit(chapter, 0)
    assert not center.select_chapter('c01', 'c01.new')
    assert not center.start_button.isEnabled() and not center.replay_button.isEnabled()
    center.start_button.click()
    center.replay_button.click()
    assert not requests


def test_center_refresh_reapplies_search_to_current_localized_titles(
        qt_app, catalog, store, translate):
    titles = {'teaching_chapter_new': 'First strokes'}

    def tr(key):
        return titles[key] if key in titles else translate(key)

    center = widgets().TeachingCenter(catalog, store, tr)
    assert hasattr(center, 'search_edit'), 'TeachingCenter needs a keyword search'
    center.search_edit.setText('STROKES')
    set_center_filter(center, 'unfinished')
    assert center.select_chapter('c01', 'c01.new')
    titles['teaching_chapter_new'] = '初次绘图'
    center.refresh()
    assert center.search_edit.text() == 'STROKES'
    assert center.filter_combo.currentData() == 'unfinished'
    assert not visible_chapters(center) and center.selected_chapter is None
    center.search_edit.setText('绘图')
    assert visible_chapters(center) == (('c01', 'c01.new'),)
    assert center.select_chapter('c01', 'c01.new')
    assert center.tree.currentItem().text(0) == '初次绘图'
    assert not store.path.exists()


def test_center_filter_changes_preserve_only_still_visible_selection(
        qt_app, catalog, store, translate):
    center = widgets().TeachingCenter(catalog, populated_store(store), translate)
    assert hasattr(center, 'search_edit'), 'TeachingCenter needs a keyword search'
    center.search_edit.setText('C01')
    set_center_filter(center, 'unfinished')
    assert center.selected_chapter == ('c01', 'c01.active')
    set_center_filter(center, 'completed')
    assert center.selected_chapter is None
    assert not center.start_button.isEnabled() and not center.replay_button.isEnabled()
    set_center_filter(center, 'all')
    assert center.selected_chapter is None  # Clearing a filter must not start/select a different chapter.
    assert not center.select_chapter('c99', 'c99.unknown')


@pytest.mark.parametrize('hidden', [True, False])
def test_center_resume_displays_the_requested_chapter_before_emitting(
        qt_app, catalog, store, translate, hidden):
    center = widgets().TeachingCenter(catalog, populated_store(store), translate)
    assert hasattr(center, 'search_edit'), 'TeachingCenter needs a keyword search'
    query, status = ('C02', 'completed') if hidden else ('C01.ACTIVE', 'unfinished')
    center.search_edit.setText(query)
    set_center_filter(center, status)
    requests = QSignalSpy(center.start_requested)
    presented = []
    center.start_requested.connect(
        lambda *_: presented.append((center.selected_chapter, visible_chapters(center))))
    assert center.resume_button.isEnabled()
    group = center.tree.topLevelItem(0)
    group.child(0).setExpanded(False)
    group.setExpanded(False)
    center.resume_button.click()
    assert list(requests) == [['c01', 'c01.active']]
    assert presented[0][0] == ('c01', 'c01.active')
    assert ('c01', 'c01.active') in presented[0][1]
    item = center.tree.currentItem()
    assert item.parent().isExpanded() and item.parent().parent().isExpanded()
    assert center.search_edit.text() == ('' if hidden else query)
    assert center.filter_combo.currentData() == ('all' if hidden else status)


def test_center_refresh_retains_filter_query_and_visible_selection(
        qt_app, catalog, store, translate):
    center = widgets().TeachingCenter(catalog, populated_store(store), translate)
    assert hasattr(center, 'search_edit'), 'TeachingCenter needs a keyword search'
    center.search_edit.setText(' c01 ')
    set_center_filter(center, 'unfinished')
    assert store.record_chapter('c01.new', 'completed', compat_revision=2)
    assert store.record_chapter('c01.active', 'skipped', compat_revision=2)
    before = store.snapshot()
    before_bytes = store.path.read_bytes()
    center.refresh()
    assert center.search_edit.text() == ' c01 '
    assert center.filter_combo.currentData() == 'unfinished'
    assert center.selected_chapter == ('c01', 'c01.active')
    assert center.tree.currentItem().text(1) == translate('teaching_status_skipped')
    assert visible_chapters(center) == (
        ('c01', 'c01.skip'), ('c01', 'c01.active'), ('c01', 'c01.review'),
    )
    assert center.tree.topLevelItem(0).child(0).text(1) == 'Localized chapters 2/5 completed'
    assert store.snapshot() == before and store.path.read_bytes() == before_bytes


def test_center_refresh_clears_selection_that_no_longer_matches(
        qt_app, catalog, store, translate):
    center = widgets().TeachingCenter(catalog, store, translate)
    assert center.select_chapter('c01', 'c01.new')
    assert hasattr(center, 'search_edit'), 'TeachingCenter needs a keyword search'
    center.search_edit.setText('C01.NEW')
    set_center_filter(center, 'unfinished')
    assert store.record_chapter('c01.new', 'completed', compat_revision=2)
    center.refresh()
    requests = QSignalSpy(center.start_requested)
    assert center.search_edit.text() == 'C01.NEW'
    assert center.filter_combo.currentData() == 'unfinished'
    assert not visible_chapters(center)
    assert center.tree.topLevelItem(0).isHidden()
    assert center.selected_chapter is None and center.tree.currentItem() is None
    assert not center.start_button.isEnabled() and not center.replay_button.isEnabled()
    center.start_button.click()
    center.tree.itemActivated.emit(center.tree.topLevelItem(0).child(0).child(0), 0)
    assert not requests


def test_center_refresh_keeps_explicitly_cleared_selection(qt_app, catalog, store, translate):
    center = widgets().TeachingCenter(catalog, populated_store(store), translate)
    assert not center.select_chapter('c99', 'c99.unknown')
    center.refresh()
    assert center.selected_chapter is None
    assert not center.start_button.isEnabled() and not center.replay_button.isEnabled()


@pytest.mark.parametrize('language', ('zh', 'en', 'fr', 'es', 'de', 'ru', 'ko', 'ja'))
def test_center_fixed_controls_and_course_placeholders_use_real_locale(
        qt_app, catalog, store, monkeypatch, language):
    import i18n

    monkeypatch.setattr(i18n, 'CURRENT', language)
    center = widgets().TeachingCenter(catalog, populated_store(store), i18n.tr)
    progress = center.tree.topLevelItem(0).child(0).text(1)
    assert '1/5' in progress and '{' not in progress
    assert progress == i18n.trf('teaching_course_progress', completed=1, total=5)
    assert hasattr(center, 'search_edit'), 'TeachingCenter needs a keyword search'
    assert center.search_edit.placeholderText() == i18n.tr('teaching_search')
    for index, status in enumerate(('all', 'completed', 'unfinished')):
        assert center.filter_combo.itemText(index) == i18n.tr(f'teaching_filter_{status}')


@pytest.mark.parametrize('persisted', [False, True])
def test_center_filtering_refresh_and_requests_never_write_or_spawn(
        qt_app, catalog, store, translate, monkeypatch, persisted):
    if persisted:
        populated_store(store)
    before = store.snapshot()
    before_bytes = store.path.read_bytes() if store.path.exists() else None
    before_files = set(store.path.parent.iterdir())

    def forbidden(*_args, **_kwargs):
        pytest.fail('TeachingCenter must not write progress or start a process')

    monkeypatch.setattr(store, '_persist', forbidden)
    monkeypatch.setattr(store, 'sync_catalog', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    if hasattr(os, 'startfile'):
        monkeypatch.setattr(os, 'startfile', forbidden)
    center = widgets().TeachingCenter(catalog, store, translate)
    requests = QSignalSpy(center.start_requested)
    assert hasattr(center, 'search_edit'), 'TeachingCenter needs a keyword search'
    center.search_edit.setText('C02')
    set_center_filter(center, 'completed')
    center.refresh()
    center.resume_button.click()
    center.search_edit.clear()
    set_center_filter(center, 'all')
    assert center.select_chapter('c01', 'c01.new')
    center.start_button.click()
    center.replay_button.click()
    center.refresh()
    center.hide()
    center.close()
    drain(qt_app)
    expected = [['c01', 'c01.active']] if persisted else []
    assert list(requests) == expected + [['c01', 'c01.new'], ['c01', 'c01.new']]
    assert store.snapshot() == before
    assert (store.path.read_bytes() if store.path.exists() else None) == before_bytes
    assert set(store.path.parent.iterdir()) == before_files


@pytest.mark.parametrize('kind', ['information', 'operation'])
@pytest.mark.parametrize('previous,next_', [(False, False), (False, True), (True, False), (True, True)])
def test_controller_navigation_never_completes_operations(qt_app, translate, kind, previous, next_):
    controller = widgets().TutorialController(translate)
    controller.present(step(kind), 1, 4, previous, next_)
    requests = QSignalSpy(controller.next_requested)
    controller.show()
    drain(qt_app)
    assert controller.windowType() == Qt.WindowType.Tool
    assert controller.title_label.text() == translate('teaching_step_title')
    assert controller.body_label.text() == translate('teaching_step_body')
    assert controller.progress_label.text() == 'Localized step 2 of 4'
    assert controller.previous_button.isEnabled() == previous
    assert controller.next_button.isEnabled() == (next_ and kind == 'information')
    assert controller.exit_button.isVisible() and controller.exit_button.isEnabled()
    QTest.mouseClick(controller.next_button, Qt.MouseButton.LeftButton)
    assert len(requests) == int(next_ and kind == 'information')
    if kind == 'operation':
        assert controller.status_label.text() == translate('teaching_waiting_operation')


def test_controller_actions_emit_requests_without_changing_presentation(qt_app, translate):
    controller = widgets().TutorialController(translate)
    controller.present(step(), 1, 3, True, True)
    names = ('previous', 'next', 'pause', 'skip')
    requests = {name: QSignalSpy(getattr(controller, f'{name}_requested')) for name in names}
    controller.show()
    drain(qt_app)
    before = (controller.title_label.text(), controller.body_label.text(), controller.progress_label.text())
    for name in names:
        QTest.mouseClick(getattr(controller, f'{name}_button'), Qt.MouseButton.LeftButton)
        assert len(requests[name]) == 1
    assert (controller.title_label.text(), controller.body_label.text(), controller.progress_label.text()) == before


def test_controller_paused_and_missing_states_keep_exit_and_recovery(qt_app, translate):
    controller = widgets().TutorialController(translate)
    controller.present(step(), 0, 2, True, True)
    retry = QSignalSpy(controller.retry_requested)
    controller.set_target_missing(True)
    assert controller.status_label.text() == translate('teaching_target_missing')
    assert not controller.previous_button.isEnabled() and not controller.next_button.isEnabled()
    assert controller.retry_button.isEnabled() and controller.skip_button.isEnabled()
    controller.show()
    drain(qt_app)
    QTest.mouseClick(controller.retry_button, Qt.MouseButton.LeftButton)
    assert len(retry) == 1
    controller.set_paused(True)
    assert controller.status_label.text() == translate('teaching_paused')
    assert controller.pause_button.text() == translate('teaching_resume')
    assert not controller.next_button.isEnabled()
    assert controller.skip_button.isEnabled()  # Skip remains reachable during pause.
    assert controller.exit_button.isEnabled()
    controller.present(step(), 1, 2, True, True)
    assert not controller.next_button.isEnabled()  # present cannot silently resume
    controller.set_paused(False)
    assert controller.status_label.text() == translate('teaching_target_missing')
    controller.set_target_missing(False)
    assert controller.next_button.isEnabled()
    assert not controller.retry_button.isEnabled()


def test_controller_hide_is_not_exit_and_close_emits_once(qt_app, translate):
    controller = widgets().TutorialController(translate)
    controller.present(step(), 0, 1, False, False)
    exits = QSignalSpy(controller.exit_requested)
    controller.show()
    controller.hide()
    assert len(exits) == 0
    assert controller.progress_label.text() == 'Localized step 1 of 1'
    controller.show()
    # A host may synchronously close in response; avoid recursive exit emission.
    controller.exit_requested.connect(controller.close)
    QTest.mouseClick(controller.exit_button, Qt.MouseButton.LeftButton)
    drain(qt_app)
    assert len(exits) == 1
    assert sip.isdeleted(controller)


@pytest.mark.parametrize('index,total', [(-1, 2), (2, 2), (0, 0), (False, 1)])
def test_controller_rejects_invalid_progress_without_corrupting_view(qt_app, translate, index, total):
    controller = widgets().TutorialController(translate)
    controller.present(step(), 0, 1, False, True)
    with pytest.raises(ValueError):
        controller.present(step(), index, total, False, True)
    assert controller.progress_label.text() == 'Localized step 1 of 1'
    assert controller.exit_button.isEnabled()


def test_controller_localized_text_is_plain_not_html(qt_app, translate):
    def tr(key):
        return '<b>not markup</b>' if key == 'teaching_step_body' else translate(key)
    controller = widgets().TutorialController(tr)
    controller.present(step(), 0, 1, False, True)
    assert controller.body_label.textFormat() == Qt.TextFormat.PlainText
    assert controller.body_label.text() == '<b>not markup</b>'
    assert controller.body_label.wordWrap()


@pytest.mark.parametrize('anchor,size,available', [
    (QRect(-1300, -700, 80, 30), QSize(400, 240), QRect(-1600, -900, 1000, 800)),
    (QRect(-40, 100, 30, 50), QSize(360, 260), QRect(-1000, 20, 1000, 700)),
    (QRect(4000, 4000, 10, 10), QSize(2000, 2000), QRect(-900, -700, 640, 480)),
    (QRect(-9000, -9000, 10, 10), QSize(300, 200), QRect(120, 80, 1024, 700)),
])
def test_geometry_is_bounded_by_explicit_screen_including_negative_origins(anchor, size, available):
    geometry = widgets().controller_geometry(anchor, size, available)
    assert available.contains(geometry)
    assert geometry.width() == min(size.width(), available.width())
    assert geometry.height() == min(size.height(), available.height())


def test_controller_place_uses_explicit_work_area(qt_app, translate):
    controller = widgets().TutorialController(translate)
    available = QRect(-1200, -700, 600, 400)
    result = controller.place(QRect(-650, -400, 30, 40), available)
    assert available.contains(controller.geometry())
    assert controller.geometry() == result
    with pytest.raises(ValueError):
        widgets().controller_geometry(QRect(), QSize(10, 10), QRect())


def test_overlay_is_independent_border_only_input_transparent_and_nonactivating(qt_app, host):
    overlay = widgets().HighlightOverlay()
    before = host.grab().toImage()
    rect = QRect(-450, -230, 220, 90)
    overlay.highlight(rect)
    drain(qt_app)
    assert overlay.isWindow() and overlay.windowType() == Qt.WindowType.Tool
    assert overlay.geometry() == rect
    for attribute in (Qt.WidgetAttribute.WA_TranslucentBackground,
                      Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                      Qt.WidgetAttribute.WA_ShowWithoutActivating):
        assert overlay.testAttribute(attribute)
    assert overlay.windowFlags() & Qt.WindowType.WindowTransparentForInput
    assert overlay.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus
    assert overlay.focusPolicy() == Qt.FocusPolicy.NoFocus
    image = overlay.grab().toImage()
    assert image.pixelColor(image.width() // 2, image.height() // 2).alpha() == 0
    assert any(image.pixelColor(x, 1).alpha() for x in range(image.width()))
    assert host.grab().toImage() == before
    overlay.highlight(QRect())
    assert not overlay.isVisible()
    overlay.highlight(None)
    overlay.close()
    drain(qt_app)
    assert sip.isdeleted(overlay)


def test_barrier_only_blocks_owned_window_and_allows_target_children_and_controller(qt_app, host, translate):
    module = widgets()
    allowed = QWidget(host)
    allowed.setGeometry(10, 10, 140, 80)
    allowed.show()
    child = button(allowed)
    forbidden = button(host, 190, 10)
    foreign = QWidget()
    foreign.show()
    other = button(foreign)
    controller = module.TutorialController(translate)
    controller.present(step(), 0, 1, False, True)
    controller.show()
    owned = {host, controller}
    barrier = module.InputBarrier(lambda window: window in owned)
    spies = [QSignalSpy(value.clicked) for value in (child, forbidden, other)]
    pause = QSignalSpy(controller.pause_requested)
    barrier.activate('target_only', targets=(allowed,), controller=controller)
    try:
        drain(qt_app)
        for value in (child, forbidden, other):
            QTest.mouseClick(value, Qt.MouseButton.LeftButton)
        QTest.mouseClick(controller.pause_button, Qt.MouseButton.LeftButton)
        assert [len(spy) for spy in spies] == [1, 0, 1]
        assert len(pause) == 1
    finally:
        barrier.close()


def test_barrier_blocks_keys_and_shortcuts_only_in_owned_windows(qt_app, host):
    allowed = QLineEdit(host)
    allowed.setGeometry(10, 10, 120, 30)
    forbidden = QLineEdit(host)
    forbidden.setGeometry(150, 10, 120, 30)
    foreign = QLineEdit()
    for value in (allowed, forbidden, foreign):
        value.show()
    delivered_shortcuts = []

    class ShortcutProbe(QShortcut):
        def event(self, event):
            if event.type() == QEvent.Type.Shortcut:
                delivered_shortcuts.append(event.type())
            return super().event(event)

    shortcut = ShortcutProbe(QKeySequence('Ctrl+K'), forbidden)
    shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
    QCoreApplication.sendEvent(shortcut, QShortcutEvent(QKeySequence('Ctrl+K'), 0))
    assert delivered_shortcuts == [QEvent.Type.Shortcut]
    delivered_shortcuts.clear()
    activated = QSignalSpy(shortcut.activated)
    barrier = widgets().InputBarrier(lambda window: window is host)
    barrier.activate('target_only', targets=(allowed,))
    try:
        QTest.keyClicks(allowed, 'yes')
        QTest.keyClicks(forbidden, 'no')
        QTest.keyClicks(foreign, 'other app')
        QTest.keyClick(forbidden, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
        assert allowed.text() == 'yes'
        assert forbidden.text() == ''
        assert foreign.text() == 'other app'
        QCoreApplication.sendEvent(shortcut, QShortcutEvent(QKeySequence('Ctrl+K'), 0))
        assert len(activated) == 0
        assert delivered_shortcuts == []
    finally:
        barrier.close()


def test_barrier_suspend_is_nested_and_free_policy_uninstalls_filter(qt_app, host):
    forbidden = button(host)
    clicks = QSignalSpy(forbidden.clicked)
    barrier = widgets().InputBarrier(lambda window: window is host)
    assert not barrier.active and not barrier.installed
    barrier.activate('target_only')
    try:
        assert barrier.active and barrier.installed
        QTest.mouseClick(forbidden, Qt.MouseButton.LeftButton)
        assert len(clicks) == 0
        barrier.suspend()
        barrier.suspend()
        assert barrier.active and not barrier.installed
        QTest.mouseClick(forbidden, Qt.MouseButton.LeftButton)
        barrier.resume()
        QTest.mouseClick(forbidden, Qt.MouseButton.LeftButton)
        assert len(clicks) == 2
        barrier.resume()
        assert barrier.installed
        QTest.mouseClick(forbidden, Qt.MouseButton.LeftButton)
        assert len(clicks) == 2
        barrier.activate('free')
        assert barrier.active and not barrier.installed
        QTest.mouseClick(forbidden, Qt.MouseButton.LeftButton)
        assert len(clicks) == 3
        barrier.deactivate()
        assert not barrier.active and not barrier.installed
    finally:
        barrier.close()
    with pytest.raises(RuntimeError, match='closed'):
        barrier.activate('free')


GESTURE_TYPES = (
    QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease,
    QEvent.Type.MouseButtonDblClick, QEvent.Type.KeyPress, QEvent.Type.KeyRelease,
    QEvent.Type.Wheel, QEvent.Type.TabletPress, QEvent.Type.TabletMove, QEvent.Type.TabletRelease,
    QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd, QEvent.Type.TouchCancel,
    QEvent.Type.Gesture, QEvent.Type.GestureOverride, QEvent.Type.NativeGesture,
    QEvent.Type.ContextMenu, QEvent.Type.InputMethod, QEvent.Type.ShortcutOverride,
    QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop,
)


class InputProbe(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.received = []

    def event(self, event):
        if event.type() in GESTURE_TYPES:
            self.received.append(event.type())
            event.accept()
            return True
        return super().event(event)


def test_canvas_policy_passes_every_canvas_gesture_and_no_unrelated_inputs(qt_app, host):
    canvas = InputProbe(host)
    child = InputProbe(canvas)
    forbidden = InputProbe(host)
    barrier = widgets().InputBarrier(lambda window: window is host)
    barrier.activate('canvas', canvas=canvas)
    try:
        for receiver in (canvas, child, forbidden):
            for event_type in GESTURE_TYPES:
                # Policy coverage only. QApplication casts input events before
                # QWidget.event(), so never dispatch a bare QEvent as typed input.
                event = QEvent(event_type)
                assert barrier.eventFilter(receiver, event) == (receiver is forbidden)
                if receiver is forbidden:
                    assert event.isAccepted()
        QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(3, 3))
        QTest.mouseMove(canvas, QPoint(15, 15))
        QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(15, 15))
        wheel = QWheelEvent(QPointF(4, 4), QPointF(44, 44), QPoint(), QPoint(0, 120),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.NoScrollPhase, False)
        QCoreApplication.sendEvent(canvas, wheel)
        QCoreApplication.sendEvent(canvas, QTouchEvent(QEvent.Type.TouchBegin))
        device = QPointingDevice.primaryPointingDevice()
        tablet = QTabletEvent(QEvent.Type.TabletPress, device, QPointF(4, 4), QPointF(44, 44),
                              0.5, 0, 0, 0, 0, 0, Qt.KeyboardModifier.NoModifier,
                              Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
        QCoreApplication.sendEvent(canvas, tablet)
        gesture = QNativeGestureEvent(Qt.NativeGestureType.ZoomNativeGesture, device, 2,
                                     QPointF(4, 4), QPointF(4, 4), QPointF(44, 44),
                                     0.2, QPointF())
        QCoreApplication.sendEvent(canvas, gesture)
        assert QEvent.Type.TabletPress in canvas.received
        assert QEvent.Type.NativeGesture in canvas.received
        assert QEvent.Type.MouseButtonPress in canvas.received
        assert QEvent.Type.MouseButtonRelease in canvas.received
        assert QEvent.Type.Wheel in canvas.received
        assert QEvent.Type.TouchBegin in canvas.received
    finally:
        barrier.close()


def test_target_only_does_not_whitelist_canvas_unless_explicit(qt_app, host):
    canvas = button(host)
    allowed = button(host, 150, 10)
    clicks = QSignalSpy(canvas.clicked)
    barrier = widgets().InputBarrier(lambda window: window is host)
    barrier.activate('target_only', targets=(allowed,), canvas=canvas)
    try:
        QTest.mouseClick(canvas, Qt.MouseButton.LeftButton)
        assert len(clicks) == 0
    finally:
        barrier.close()


@pytest.mark.parametrize('root_kind', ['target', 'canvas', 'controller'])
def test_barrier_uses_weak_roots_and_ignores_deleted_widgets(qt_app, host, root_kind):
    allowed = button(host)
    target_ref = weakref.ref(allowed)
    barrier = widgets().InputBarrier(lambda window: window is host)
    configuration = {'targets': (allowed,)} if root_kind == 'target' else {root_kind: allowed}
    barrier.activate('canvas' if root_kind == 'canvas' else 'target_only', **configuration)
    del configuration
    try:
        allowed.deleteLater()
        drain(qt_app)
        assert sip.isdeleted(allowed)
        del allowed
        gc.collect()
        assert target_ref() is None
        forbidden = button(host)
        clicks = QSignalSpy(forbidden.clicked)
        QTest.mouseClick(forbidden, Qt.MouseButton.LeftButton)
        assert len(clicks) == 0
    finally:
        barrier.close()


def test_barrier_rejects_invalid_policy_without_changing_live_policy(qt_app, host):
    forbidden = button(host)
    barrier = widgets().InputBarrier(lambda window: window is host)
    barrier.activate('target_only')
    try:
        with pytest.raises(ValueError, match='policy'):
            barrier.activate('desktop')
        clicks = QSignalSpy(forbidden.clicked)
        QTest.mouseClick(forbidden, Qt.MouseButton.LeftButton)
        assert len(clicks) == 0
    finally:
        barrier.close()


def test_one_hundred_close_cycles_leave_no_windows_filters_or_weak_references(qt_app, host, catalog, store, translate):
    module = widgets()
    filter_calls = []

    class TrackedBarrier(module.InputBarrier):
        def eventFilter(self, receiver, event):
            filter_calls.append(event.type())
            return super().eventFilter(receiver, event)

    forbidden = button(host)
    previous = set(qt_app.topLevelWidgets())
    references = []
    for _ in range(100):
        center = module.TeachingCenter(catalog, store, translate)
        controller = module.TutorialController(translate)
        overlay = module.HighlightOverlay()
        barrier = TrackedBarrier(lambda window: window is host)
        references.extend(weakref.ref(value) for value in (center, controller, overlay, barrier))
        controller.present(step('operation'), 0, 1, False, True)
        center.show()
        controller.show()
        overlay.highlight(QRect(40, 40, 100, 50))
        barrier.activate('target_only', controller=controller)
        barrier.suspend()
        barrier.resume()
        controller.hide()
        barrier.close()
        assert not barrier.installed and not barrier.active
        center.close()
        controller.close()
        overlay.close()
        barrier.deleteLater()
        drain(qt_app)
        assert all(sip.isdeleted(value) for value in (center, controller, overlay, barrier))
        filter_calls.clear()
        QTest.mouseClick(forbidden, Qt.MouseButton.LeftButton)
        drain(qt_app)
        assert filter_calls == []
        assert set(qt_app.topLevelWidgets()) == previous
        del center, controller, overlay, barrier
    gc.collect()
    assert all(reference() is None for reference in references)
    assert not store.path.exists()



def test_center_displays_readonly_progress_warning_without_a_modal(qt_app, catalog, store, translate):
    store.read_only, store.last_error = True, 'unsupported_schema'
    before = store.snapshot()
    center = widgets().TeachingCenter(catalog, store, translate)
    center.show()
    assert center.warning_label.isVisible()
    assert center.warning_label.text() == translate('teaching_progress_save_failed')
    assert center.warning_label.textFormat() == Qt.TextFormat.PlainText
    assert not center.isModal()
    assert store.snapshot() == before and not store.path.exists()


def test_controller_persistence_warning_survives_step_pause_and_finish(qt_app, translate):
    controller = widgets().TutorialController(translate)
    controller.present(step(), 0, 1, False, True)
    controller.show()
    controller.set_persistence_warning()
    controller.set_paused(True)
    controller.set_paused(False)
    controller.present(step('operation'), 0, 1, False, False)
    controller.set_finished('completed')
    assert controller.warning_label.isVisible()
    assert controller.warning_label.text() == translate('teaching_progress_save_failed')
    assert controller.status_label.text() == translate('teaching_status_completed')
    assert controller.exit_button.isEnabled() and not controller.next_button.isEnabled()
