# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted C10 output names and a bounded real filesystem conflict."""
from pathlib import Path


def teaching_export_destination(panel, fmt):
    context = getattr(panel, 'runtime_context', None)
    fixture = getattr(panel, '_teaching_export_fixture', None)
    names = {name: 'export.c10.'+name for name in ('formats','progress_cancel','result')}
    if context is None or not context.paths.practice or not context.ui_active or fixture not in names.values():
        return None
    engine = getattr(getattr(panel, 'teaching_presenter', None), 'engine', None)
    chapter = fixture.rsplit('.',1)[1]
    if engine is None or engine.phase != 'running' or engine.chapter_id != 'c10.'+chapter:
        return None
    step = engine.current_step
    if step is None or step.kind != 'operation':
        return None
    expected = (step.id.upper() if chapter == 'formats' else
                'PNG' if step.id in ('cancel_png','partial_png','retry_png') else None)
    if str(fmt).upper() != expected:
        return None
    paths = context.paths
    directory = Path(paths.require_directory_path(paths.export_dir))
    directory.mkdir(parents=True,exist_ok=True)
    output = Path(paths.require_write_path(directory/('c10_'+chapter+'.'+str(fmt).lower())))
    if chapter == 'result' and expected == 'PNG':
        blocker = directory/'c10_result_p2.png'
        # Reject links through the current session's path guard before file work.
        if blocker.is_file():
            permitted = Path(paths.require_write_path(blocker))
            if permitted.parent != directory:
                raise ValueError('C10 output escaped its private directory')
            if step.id == 'partial_png':
                permitted.unlink()
        elif blocker.exists():
            permitted = Path(paths.require_directory_path(blocker))
            if permitted.parent != directory:
                raise ValueError('C10 blocker escaped its private directory')
            if step.id == 'retry_png':
                permitted.rmdir()  # Only the known empty demonstration directory.
        if step.id == 'partial_png':
            permitted = Path(paths.require_directory_path(blocker))
            if permitted.parent != directory:
                raise ValueError('C10 blocker escaped its private directory')
            permitted.mkdir(exist_ok=True)
    return output
