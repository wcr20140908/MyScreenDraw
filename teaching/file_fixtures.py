# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted C08 drafts: prepare only this active private practice."""
from contextlib import nullcontext
from pathlib import Path
from shutil import copyfile

from persistence import (AUTOSAVE_KIND, PROJECT_KIND, atomic_write_autosave,
                         normalize_project_data, read_json_maybe_gz)

FILE_FIXTURES = frozenset('files.c08.' + chapter for chapter in
                          ('save', 'open_guard', 'recovery', 'interval'))
FILE_OPEN_ASSET = 'fixtures/files-c08-open-sample.msd'
FILE_HISTORY_ASSET = 'fixtures/files-c08-history.msd'
FILE_HISTORY_NAME = 'autosave_teaching_c08_recovery.json.gz'


def _synthetic_project(loader, asset):
    source = loader.asset_path(asset)
    data = normalize_project_data(read_json_maybe_gz(str(source)), kind=PROJECT_KIND)
    if data['metadata'].get('synthetic_teaching') is not True or len(data['pages']) != 2:
        raise ValueError('C08 asset must be a synthetic two-page project')
    return source, data


def prepare_file_fixture(panel, loader, fixture, paths):
    if fixture not in FILE_FIXTURES:
        return
    context = panel.runtime_context
    if not paths.practice or context.paths != paths or not context.ui_active:
        raise ValueError('C08 setup requires this active private practice')
    events = getattr(panel, 'teaching_events', None)
    with events.suppress() if events is not None else nullcontext():
        canvas = panel.canvas
        canvas.finish_active_ink()
        canvas.end_text_edit()
        canvas._discard_teaching_laser_operations()
        canvas.laser_trail = []
        canvas.cancel_pending_points()
        canvas.selected_ids.clear()
        panel.close_text_input()
        if getattr(panel, '_open_symbol_group', None) is not None:
            panel._toggle_symbol_group(panel._open_symbol_group)
        panel.pen_defaults_enabled = False
        panel.choose_pen_style('pen')
        panel.set_drawing_mode(True)
        panel.set_tool('PEN', panel.btn_pen)
        canvas.pen_width = 4
        canvas.smart_shapes_enabled = False
        canvas.reset_history()
        panel.show_only_sub(None)
        panel.close_thumbnail_panel()
        settings = getattr(panel, 'settings_panel', None)
        if settings is not None:
            settings.hide()
        panel._teaching_last_saved_project = None
        panel._teaching_file_open_path = None
        panel._teaching_file_history_path = None
        panel._teaching_unsaved_choice = None
        if fixture == 'files.c08.save':
            panel.project_path = None
        elif fixture == 'files.c08.open_guard':
            source, _data = _synthetic_project(loader, FILE_OPEN_ASSET)
            directory = paths.require_directory_path(paths.data_dir / 'fixtures')
            directory.mkdir(parents=True, exist_ok=True)
            destination = paths.require_write_path(directory / 'files-c08-open-sample.msd')
            copyfile(str(source), str(destination))
            panel._teaching_file_open_path = str(destination)
        elif fixture == 'files.c08.recovery':
            _source, data = _synthetic_project(loader, FILE_HISTORY_ASSET)
            directory = paths.require_directory_path(paths.autosave_dir)
            directory.mkdir(parents=True, exist_ok=True)
            resolved_directory = Path(directory).resolve()
            candidates = set(Path(directory).glob('autosave_*.json'))
            candidates.update(Path(directory).glob('autosave_*.json.gz'))
            # This is the exclusive active practice directory, never ordinary data.
            for candidate in sorted(candidates):
                if not candidate.is_file():
                    continue
                permitted = Path(paths.require_write_path(candidate))
                if permitted.resolve().parent != resolved_directory:
                    raise ValueError('C08 history cleanup escaped its private directory')
                permitted.unlink()
            data['kind'] = AUTOSAVE_KIND
            destination = paths.require_write_path(directory / FILE_HISTORY_NAME)
            atomic_write_autosave(str(destination), data)
            remaining = set(Path(directory).glob('autosave_*.json'))
            remaining.update(Path(directory).glob('autosave_*.json.gz'))
            remaining = {path.resolve() for path in remaining if path.is_file()}
            if remaining != {Path(destination).resolve()}:
                raise ValueError('C08 recovery requires exactly one private candidate')
            panel._teaching_file_history_path = str(destination)
        elif fixture == 'files.c08.interval':
            panel.set_autosave_interval(30, persist=False)
        panel.update_whiteboard_ui()
        panel.update_history_ui()
