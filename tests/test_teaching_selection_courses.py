# SPDX-License-Identifier: GPL-3.0-or-later
"""Formal C04 chapters use actual selection handles and edit buttons."""
from string import Formatter

import pytest
from PyQt6.QtCore import QPoint

from teaching.application import application_catalog
from test_teaching_business_adapters import mouse
from test_teaching_writing_courses import ROOT, writing_host, next_info, assert_step, finished


def click_sample(panel):
    mouse(panel.canvas, 'press', (170, 150))
    mouse(panel.canvas, 'release', (170, 150))


def transform_handle(canvas, action):
    point = canvas.selection_handles()[action].center().toPoint()
    destination = point + (QPoint(70, 30) if action == 'scale' else QPoint(60, 40))
    mouse(canvas, 'press', (point.x(), point.y()))
    mouse(canvas, 'move', (destination.x(), destination.y()))
    mouse(canvas, 'release', (destination.x(), destination.y()))


def test_selection_catalog_and_eight_language_copy_are_complete():
    import main, i18n
    from teaching.selection_copy import SELECTION_COPY
    catalog, _ = application_catalog(main, ROOT)
    course = catalog.course_by_id('c04')
    assert [chapter.id for chapter in course.chapters] == [
        'c04.select_move', 'c04.transform', 'c04.copy_delete']
    assert [len(chapter.steps) for chapter in course.chapters] == [5, 7, 7]
    assert len(SELECTION_COPY) == 43
    for key, values in SELECTION_COPY.items():
        assert len(values) == 8
        for language, value in zip(i18n._LANGS, values):
            assert i18n.TEXT[language][key] == value and value.strip()
            assert not any(field is not None for _, field, _, _ in Formatter().parse(value))


@pytest.mark.parametrize('writing_host', ['c04.select_move'], indirect=True)
def test_select_move_requires_real_click_then_a_committed_drag(writing_host):
    host, progress = writing_host
    panel = host.panel
    next_info(host)
    panel.handle_select_click()
    assert_step(host, 'select')
    click_sample(panel)
    assert_step(host, 'move')
    before = host.module.serialize_page(panel.canvas.capture_page())
    mouse(panel.canvas, 'press', (170, 150))
    mouse(panel.canvas, 'move', (210, 190))
    mouse(panel.canvas, 'release', (210, 190))
    assert host.module.serialize_page(panel.canvas.capture_page()) != before
    assert_step(host, 'done')
    next_info(host)
    finished(host, progress)


@pytest.mark.parametrize('writing_host', ['c04.transform'], indirect=True)
def test_scaling_and_rotation_require_two_real_handle_gestures(writing_host):
    host, progress = writing_host
    panel = host.panel
    next_info(host)
    panel.handle_select_click()
    click_sample(panel)
    assert_step(host, 'handles')
    next_info(host)
    assert_step(host, 'scale')
    before = host.module.serialize_page(panel.canvas.capture_page())
    transform_handle(panel.canvas, 'scale')
    assert host.module.serialize_page(panel.canvas.capture_page()) != before
    assert_step(host, 'rotate')
    before = host.module.serialize_page(panel.canvas.capture_page())
    transform_handle(panel.canvas, 'rotate')
    assert host.module.serialize_page(panel.canvas.capture_page()) != before
    assert_step(host, 'done')
    next_info(host)
    finished(host, progress)


@pytest.mark.parametrize('writing_host', ['c04.copy_delete'], indirect=True)
def test_box_copy_delete_and_undo_preserve_originals_and_restore_copies(writing_host):
    host, progress = writing_host
    panel, canvas = host.panel, host.panel.canvas
    next_info(host)
    panel.handle_select_click()
    assert_step(host, 'box')
    originals = {item['id'] for item in canvas.shape_items}
    assert len(originals) == 2
    mouse(canvas, 'press', (90, 100))
    mouse(canvas, 'move', (460, 450))
    mouse(canvas, 'release', (460, 450))
    assert canvas.selected_ids == originals
    assert_step(host, 'copy')
    panel.btn_dup.click()
    copies = set(canvas.selected_ids)
    assert len(copies) == 2 and copies.isdisjoint(originals)
    assert {item['id'] for item in canvas.shape_items} == originals | copies
    assert_step(host, 'delete')
    panel.btn_del.click()
    assert {item['id'] for item in canvas.shape_items} == originals
    assert_step(host, 'undo')
    assert canvas.undo()
    assert {item['id'] for item in canvas.shape_items} == originals | copies
    assert_step(host, 'done')
    next_info(host)
    finished(host, progress)


@pytest.mark.parametrize('writing_host', ['c04.copy_delete'], indirect=True)
def test_deleting_originals_does_not_complete_the_delete_copies_step(writing_host):
    host, _ = writing_host
    panel, canvas = host.panel, host.panel.canvas
    next_info(host)
    panel.handle_select_click()
    originals = {item['id'] for item in canvas.shape_items}
    mouse(canvas, 'press', (90, 100))
    mouse(canvas, 'move', (460, 450))
    mouse(canvas, 'release', (460, 450))
    panel.btn_dup.click()
    copies = set(canvas.selected_ids)
    assert_step(host, 'delete')

    canvas.selected_ids = originals
    canvas.delete_selection()

    assert {item['id'] for item in canvas.shape_items} == copies
    assert_step(host, 'delete')
    assert not host.presenter.engine._issued
