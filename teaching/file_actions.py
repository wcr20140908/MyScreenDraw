# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage persisted C08 setting results until real UI cleanup succeeds."""
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

from .events import TeachingOperationBatch


@contextmanager
def file_setting_action(panel):
    active = getattr(panel, '_teaching_document_batch', None)
    if active is not None:
        yield active
        return
    bus = getattr(panel, 'teaching_events', None)
    if bus is None:
        yield None
        return
    batch = TeachingOperationBatch(bus, ('settings.autosave_changed', 'settings.autosave_custom_opened'))
    panel._teaching_document_batch = batch
    try:
        yield batch
        batch.flush()
    finally:
        panel._teaching_document_batch = None
        batch.close()


def teaching_autosave_setting(function):
    @wraps(function)
    def wrapped(panel, seconds, persist=True, sync=True):
        if getattr(panel, 'teaching_events', None) is None:
            return function(panel, seconds, persist=persist, sync=sync)
        with file_setting_action(panel) as batch:
            operation = batch.operation('settings.autosave_changed')
            before = panel.autosave_interval_seconds
            result = function(panel, seconds, persist=persist, sync=sync)
            if operation is not None and persist and before != result and type(seconds) is int:
                marker = getattr(panel, '_last_settings_write', None)
                paths = panel.runtime_context.paths
                saved = (isinstance(marker, tuple) and len(marker) == 2
                         and Path(marker[0]) == paths.config_file and paths.config_file.is_file()
                         and isinstance(marker[1], dict)
                         and marker[1].get('autosave_interval_seconds') == result)
                batch.emit_result(operation, 'settings.autosave_changed',
                                  'success' if saved else 'failed', {'seconds': result})
            return result
    return wrapped


def teaching_interval_choice(function):
    @wraps(function)
    def wrapped(preferences, *args, **kwargs):
        panel = preferences.panel
        if getattr(panel, 'teaching_events', None) is None:
            return function(preferences, *args, **kwargs)
        with file_setting_action(panel) as batch:
            operation = batch.operation('settings.autosave_custom_opened')
            before = not preferences.interval_custom.isHidden()
            result = function(preferences, *args, **kwargs)
            if (operation is not None and not before and preferences.interval_combo.currentData() == -1
                    and not preferences.interval_custom.isHidden()):
                batch.emit_result(operation, 'settings.autosave_custom_opened', 'success', {'custom': True})
            return result
    return wrapped
