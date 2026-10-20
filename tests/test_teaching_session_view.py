# SPDX-License-Identifier: GPL-3.0-or-later
"""A child receives only bounded parent learning records, never a writable store."""
import copy
import importlib
from dataclasses import replace

import pytest
from teaching.state import TutorialStateStore
from test_teaching_engine import make_catalog


def api():
    try:
        return importlib.import_module('teaching.session_view')
    except ModuleNotFoundError:
        pytest.fail('parent progress view and read-only practice mirror are not implemented')


def test_parent_view_is_catalog_scoped_and_does_not_write(tmp_path):
    store=TutorialStateStore(tmp_path/'progress.json')
    store.record_chapter('c01.save','completed',compat_revision=1)
    store.record_chapter('old.removed','completed',compat_revision=1)
    store.mark_context_seen('private.context')
    before=store.path.read_bytes()
    module=api()
    data=module.parent_progress_view(make_catalog(),store)
    assert set(data)=={'records','last_started','read_only','context_hints_enabled'}
    assert set(data['records'])=={'c01.save','c01.other'}
    assert data['last_started'] is None
    assert 'private.context' not in repr(data)
    assert store.path.read_bytes()==before


def test_practice_view_copies_records_and_has_no_writer(tmp_path):
    module=api(); catalog=make_catalog()
    store=TutorialStateStore(tmp_path/'progress.json')
    store.record_chapter('c01.save','completed',compat_revision=1)
    data=module.parent_progress_view(catalog,store)
    view=module.PracticeProgressView(catalog)
    view.replace(data)
    assert view.chapter_record('c01.save')['status']=='completed'
    assert view.last_started=={'course_id':'c01','chapter_id':'c01.save'}
    data['records']['c01.save']['status']='skipped'
    result=view.chapter_record('c01.save');result['status']='skipped'
    assert view.chapter_record('c01.save')['status']=='completed'
    assert not hasattr(view,'record_chapter') and not hasattr(view,'reset') and not hasattr(view,'path')


@pytest.mark.parametrize('corruption',['extra','unknown','missing','bool_revision','invalid_status','wrong_last','bool_read_only'])
def test_bad_parent_view_is_rejected_without_partial_replacement(tmp_path,corruption):
    module=api(); catalog=make_catalog(); store=TutorialStateStore(tmp_path/'progress.json')
    good=module.parent_progress_view(catalog,store); view=module.PracticeProgressView(catalog);view.replace(good)
    data=copy.deepcopy(good)
    if corruption=='extra': data['private_path']='not allowed'
    elif corruption=='unknown': data['records']['wrong.chapter']=data['records']['c01.other']
    elif corruption=='missing': del data['records']['c01.other']
    elif corruption=='bool_revision': data['records']['c01.save']['compat_revision']=True
    elif corruption=='invalid_status': data['records']['c01.save']['status']='pretend_complete'
    elif corruption=='wrong_last': data['last_started']={'course_id':'c01','chapter_id':'c01.removed'}
    else: data['read_only']=1
    with pytest.raises((ValueError,KeyError)):
        view.replace(data)
    assert view.chapter_record('c01.save')==good['records']['c01.save']


def test_view_preserves_parent_review_and_readonly_flags(tmp_path):
    module=api(); catalog=make_catalog(); store=TutorialStateStore(tmp_path/'progress.json')
    store.record_chapter('c01.save','completed',compat_revision=1)
    changed=replace(catalog,courses=(replace(catalog.courses[0],compat_revision=2),))
    store.sync_catalog(changed.chapter_revisions())
    store.read_only=True
    view=module.PracticeProgressView(changed)
    view.replace(module.parent_progress_view(changed,store))
    assert view.read_only and view.chapter_record('c01.save')['needs_review']
    assert view.chapter_record('c01.save')['completed_revision']==1
