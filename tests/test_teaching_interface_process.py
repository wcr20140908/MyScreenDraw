# SPDX-License-Identifier: GPL-3.0-or-later
"""Real offscreen child startup and C13 chapter switches, with parent restoration."""
import pytest
from test_teaching_complete_process import (
    BRIDGE, CHAPTERS, parent_coordinator, practice_request, run_course_process,
)
from teaching.application import application_catalog
from pathlib import Path


@pytest.mark.parametrize('include_layout', [False, True])
def test_last_three_courses_start_via_private_process_and_center(
        parent_coordinator, tmp_path, monkeypatch, include_layout):
    catalog, _ = application_catalog(None, Path(__file__).resolve().parents[1])
    course = catalog.course_by_id('c13')
    chapters = tuple(ch.id for ch in course.chapters)[0 if include_layout else 1:]
    bridge = BRIDGE.replace('chapters = ' + repr(CHAPTERS), 'chapters = ' + repr(chapters))
    steps = sum(len(catalog.chapter_by_id(ch).steps) for ch in chapters) - 1
    proof = run_course_process(parent_coordinator, tmp_path, monkeypatch,
        chapters=chapters, bridge_source=bridge, expected_steps=steps)
    assert proof['c13_paused'] and proof['c13_resumed']
    assert proof['parent_restored'] and proof['private_root_removed']
