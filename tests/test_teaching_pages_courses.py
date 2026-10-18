# SPDX-License-Identifier: GPL-3.0-or-later
"""All 49 formal C05 steps through real owned offscreen controls (roam in test_teaching_roam)."""
from pathlib import Path
from string import Formatter

import pytest
from PyQt6.QtCore import QPoint,QRect
from PyQt6.QtWidgets import QApplication,QMessageBox

from persistence import normalize_project_data,read_json_maybe_gz,PROJECT_KIND
from teaching.application import application_catalog
from test_teaching_page_adapters import drag_to_front
from test_teaching_writing_courses import ROOT,writing_host,next_info,assert_step,finished


def test_pages_catalog_and_eight_language_resources_are_complete():
    import main,i18n
    from teaching.pages_copy import PAGES_COPY
    catalog,loader=application_catalog(main,ROOT)
    course=catalog.course_by_id('c05')
    assert [chapter.id for chapter in course.chapters]==[
        'c05.board','c05.add_switch','c05.rename_delete','c05.copy_position','c05.reorder','c05.roam']
    assert [len(chapter.steps) for chapter in course.chapters]==[7,6,7,12,7,10]
    assert len(PAGES_COPY)==105
    for key,values in PAGES_COPY.items():
        assert len(values)==8
        for language,value in zip(i18n._LANGS,values):
            assert i18n.TEXT[language][key]==value and value.strip()
            assert not any(field is not None for _,field,_,_ in Formatter().parse(value))
    for chapter in course.chapters:
        data=normalize_project_data(read_json_maybe_gz(str(loader.asset_path(loader.fixtures[chapter.fixture]))),kind=PROJECT_KIND)
        assert data['metadata']['synthetic_teaching'] is True


@pytest.mark.parametrize('writing_host',['c05.board'],indirect=True)
def test_board_switches_white_black_white_then_returns_to_annotation(writing_host,monkeypatch):
    from PyQt6.QtGui import QScreen
    host,progress=writing_host
    monkeypatch.setattr(QScreen,'grabWindow',lambda *args:pytest.fail('desktop capture forbidden'))
    panel=host.panel
    assert not panel.canvas.whiteboard_mode
    next_info(host)
    panel.icon_buttons['whiteboard'].click()
    assert_step(host,'black')
    panel.icon_buttons['board_style'].click()
    assert panel.canvas.board_style=='BLACK'
    assert_step(host,'white')
    panel.icon_buttons['board_style'].click()
    assert panel.canvas.board_style=='WHITE'
    assert_step(host,'exit')
    panel.icon_buttons['whiteboard'].click()
    assert not panel.canvas.whiteboard_mode
    assert_step(host,'boundaries')
    next_info(host);next_info(host)
    finished(host,progress)


@pytest.mark.parametrize('writing_host',['c05.add_switch'],indirect=True)
def test_add_and_turn_pages_requires_three_real_page_results(writing_host):
    host,progress=writing_host
    panel,canvas=host.panel,host.panel.canvas
    original=canvas._page_id
    next_info(host)
    panel.rail_new.click()
    added=canvas._page_id
    assert original!=added and len(canvas.pages)==2
    assert_step(host,'previous');panel.rail_prev.click()
    assert canvas._page_id==original
    assert_step(host,'next');panel.rail_next.click()
    assert canvas._page_id==added
    assert_step(host,'pen_return_info');next_info(host);next_info(host)
    finished(host,progress)


@pytest.mark.parametrize('writing_host',['c05.rename_delete'],indirect=True)
def test_rename_then_explicit_cancel_delete_and_confirm_delete(writing_host,monkeypatch):
    host,progress=writing_host
    panel,canvas=host.panel,host.panel.canvas
    original,survivor=[page['page_id'] for page in canvas.pages]
    next_info(host)
    panel.rail_count.click()
    assert_step(host,'rename')
    monkeypatch.setattr(host.module.QInputDialog,'getText',lambda *args,**kwargs:('Practice',True))
    panel.btn_rename_page.click()
    assert canvas._page_id==original and canvas._page_name=='Practice'
    assert_step(host,'cancel_delete')
    monkeypatch.setattr(QMessageBox,'exec',lambda box:QMessageBox.StandardButton.Cancel)
    panel.btn_delete_page.click()
    assert [page['page_id'] for page in canvas.pages]==[original,survivor]
    assert_step(host,'delete')
    monkeypatch.setattr(QMessageBox,'exec',lambda box:QMessageBox.StandardButton.Yes)
    panel.btn_delete_page.click()
    assert [page['page_id'] for page in canvas.pages]==[survivor]
    assert_step(host,'limits');next_info(host);next_info(host)
    finished(host,progress)


@pytest.mark.parametrize('writing_host',['c05.copy_position'],indirect=True)
def test_all_four_saved_copy_positions_create_private_matching_pages(writing_host):
    host,progress=writing_host
    panel,canvas=host.panel,host.panel.canvas
    next_info(host);next_info(host)
    for placement in ('before','after','first','last'):
        assert_step(host,placement)
        combo=panel.document_preferences.copy_combo
        QApplication.instance().processEvents()
        viewport=panel.settings_scroll.viewport()
        clip=QRect(viewport.mapToGlobal(QPoint()),viewport.size())
        assert clip.contains(host.registry.global_rect('pages.copy_position'))
        before=[page['page_id'] for page in canvas.pages]
        source=canvas._page_id
        source_position=canvas.current_page
        combo.setCurrentIndex(combo.findData(placement))
        assert_step(host,'copy_'+placement)
        assert not panel.settings_panel.isVisible() and panel.thumbnail_panel.isVisible()
        panel.btn_copy_page.click()
        expected={'before':source_position,'after':source_position+1,'first':0,'last':len(before)}[placement]
        assert canvas.current_page==expected and canvas._page_id not in before
        assert source in [page['page_id'] for page in canvas.pages]
        assert [page['page_id'] for page in canvas.pages if page['page_id'] in before]==before
    assert len(canvas.pages)==7
    assert_step(host,'limits');next_info(host);next_info(host)
    finished(host,progress)


@pytest.mark.parametrize('writing_host',['c05.reorder'],indirect=True)
def test_real_thumbnail_selection_and_owned_drag_keep_active_page_identity(writing_host,monkeypatch):
    host,progress=writing_host
    panel,canvas=host.panel,host.panel.canvas
    before=[page['page_id'] for page in canvas.pages]
    next_info(host)
    panel.rail_count.click()
    assert_step(host,'select_last')
    panel.thumbnail_list.setCurrentRow(2)
    assert canvas._page_id==before[2]
    assert_step(host,'identity_info');next_info(host)
    assert_step(host,'reorder')
    drag_to_front(panel,monkeypatch)
    assert [page['page_id'] for page in canvas.pages]==[before[2],before[0],before[1]]
    assert canvas._page_id==before[2] and canvas.current_page==0
    assert panel.thumbnail_list.currentRow()==0
    assert_step(host,'verify_info');next_info(host);next_info(host)
    finished(host,progress)


@pytest.mark.parametrize('writing_host',['c05.board'],indirect=True)
def test_chapter_change_from_annotation_rebuilds_the_whiteboard_page_rail(writing_host,tmp_path):
    from test_teaching_private_center import accepted_center
    host,_=writing_host
    panel=host.panel
    next_info(host)
    panel.icon_buttons['whiteboard'].click()
    panel.icon_buttons['board_style'].click()
    panel.icon_buttons['board_style'].click()
    panel.icon_buttons['whiteboard'].click()
    next_info(host);next_info(host)
    assert host.presenter.engine.phase=='completed'
    assert not panel.canvas.whiteboard_mode and not panel.page_rail.isVisible()
    accepted_center(host,tmp_path)
    host.prepare_chapter_change()
    host.prepare_chapter('c05','c05.add_switch')
    host.commit_chapter()
    assert panel.canvas.whiteboard_mode
    assert panel.page_rail.isVisible()
    next_info(host)
    assert_step(host,'add')
    panel.rail_new.click()
    assert_step(host,'previous')


@pytest.mark.parametrize('writing_host',['c05.board'],indirect=True)
@pytest.mark.parametrize('hidden',[False,True])
def test_paused_or_hidden_chapter_change_resumes_with_usable_page_controls(writing_host,tmp_path,monkeypatch,hidden):
    from test_teaching_private_center import accepted_center
    host,_=writing_host
    panel=host.panel
    assert not panel.canvas.whiteboard_mode
    accepted_center(host,tmp_path)
    host.prepare_chapter_change()
    host.prepare_chapter('c05','c05.add_switch')
    restore=panel.lifecycle.restore_practice_after_chapter_change
    def interrupt(token):
        restore(token)
        host.pause(hidden=hidden)
    monkeypatch.setattr(panel.lifecycle,'restore_practice_after_chapter_change',interrupt)
    host.commit_chapter()
    assert host.presenter.engine.phase=='paused'
    host.resume()
    next_info(host)
    assert_step(host,'add')
    assert panel.page_rail.isVisible()
    panel.rail_new.click()
    assert_step(host,'previous')


@pytest.mark.parametrize('writing_host',['c05.copy_position'],indirect=True)
def test_chapter_change_closes_old_thumbnail_panel_and_next_open_is_one_click(writing_host,tmp_path):
    from test_teaching_private_center import accepted_center
    host,_=writing_host
    panel=host.panel
    panel.toggle_thumbnail_panel()
    assert panel.thumbnail_panel.isVisible()
    accepted_center(host,tmp_path)
    host.prepare_chapter_change()
    host.prepare_chapter('c05','c05.reorder')
    host.commit_chapter()
    assert not panel.thumbnail_panel.isVisible()
    next_info(host)
    assert_step(host,'thumbnails')
    panel.rail_count.click()
    assert_step(host,'select_last')
