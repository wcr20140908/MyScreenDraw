# SPDX-License-Identifier: GPL-3.0-or-later
"""Fixed, trusted C01 setup; course JSON cannot supply executable actions."""
from __future__ import annotations

from persistence import (PROJECT_KIND, AUTOSAVE_KIND, atomic_write_autosave,
                         normalize_project_data, read_json_maybe_gz)

CORE_FIXTURES = frozenset('core.' + name for name in
                         ('interface', 'ink', 'select', 'pages', 'files', 'finish'))
CORE_HISTORY_NAME = 'autosave_teaching_core_files.json.gz'


def prepare_core_fixture(panel, loader, fixture, paths):
    if fixture not in CORE_FIXTURES:
        return
    context = panel.runtime_context
    if not paths.practice or context.paths != paths or not context.ui_active:
        raise ValueError('core setup requires this active private practice')
    canvas = panel.canvas
    panel.set_tool('PEN', panel.btn_pen)
    panel.set_drawing_mode(fixture != 'core.interface')
    panel.show_only_sub(None)
    panel._teaching_last_saved_project = None
    if fixture == 'core.select':
        previous = canvas.capture_page()
        previous['segments'] = []
        canvas.undo_stack = [previous]
        canvas.redo_stack = []
        canvas.last_undo_key = None
        panel.update_history_ui()
    elif fixture == 'core.files':
        source = loader.asset_path('fixtures/core-files-history.msd')
        data = normalize_project_data(read_json_maybe_gz(str(source)), kind=PROJECT_KIND)
        data['kind'] = AUTOSAVE_KIND
        paths.require_directory_path(paths.autosave_dir).mkdir(parents=True, exist_ok=True)
        destination = paths.require_write_path(paths.autosave_dir / CORE_HISTORY_NAME)
        atomic_write_autosave(str(destination), data)
