# SPDX-License-Identifier: GPL-3.0-or-later
"""C13 observes actual UI changes and the private settings written by the app."""
from functools import wraps
from inspect import signature
import json

INTERFACE_EVENTS = frozenset({
    'settings.orientation_changed', 'toolbar.visibility_changed',
    'settings.theme_changed', 'settings.color_scheme_changed',
    'settings.opacity_changed', 'settings.monitor_changed', 'settings.timer_volume_changed',
})
INTERFACE_METHODS = {
    '_set_orientation_from_settings': 'settings.orientation_changed',
    'toggle_toolbar_collapsed': 'toolbar.visibility_changed',
    'toggle_theme': 'settings.theme_changed', 'set_color_scheme': 'settings.color_scheme_changed',
    'set_ui_opacity': 'settings.opacity_changed', 'set_annotation_screen': 'settings.monitor_changed',
    'set_timer_alarm_volume': 'settings.timer_volume_changed',
}
INTERFACE_TARGETS = frozenset({
    'settings.orientation.landscape', 'settings.orientation.portrait', 'toolbar.logo',
    'settings.theme', 'settings.color_scheme', 'settings.opacity',
    'settings.monitor', 'settings.timer_volume',
})


def _private_saved(panel, key, value):
    paths = panel.runtime_context.paths
    if not paths.practice:
        return False
    try:
        saved = json.loads(paths.config_file.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    return saved.get(key) == value


def _snapshot(panel, name):
    if name == 'settings.orientation_changed':
        return panel.orientation
    if name == 'toolbar.visibility_changed':
        return panel.toolbar_window.isVisible()
    if name == 'settings.theme_changed':
        return (panel.theme_name, panel.styleSheet())
    if name == 'settings.color_scheme_changed':
        return (panel.color_scheme, panel.styleSheet())
    if name == 'settings.opacity_changed':
        return (panel.ui_opacity, panel.canvas.windowOpacity())
    if name == 'settings.monitor_changed':
        return panel.annotation_screen
    if name == 'settings.timer_volume_changed':
        return panel.timer_alarm_volume


def _details(panel, name, before):
    after = _snapshot(panel, name)
    if after == before:
        return None
    if name == 'toolbar.visibility_changed':
        return {'visible': after, 'logo_visible': panel.logo_window.isVisible()}
    if name == 'settings.orientation_changed':
        return {'orientation': after, 'saved': _private_saved(panel, 'orientation', after)}
    if name == 'settings.theme_changed':
        return {'theme': after[0], 'applied': after[1] != before[1],
                'saved': _private_saved(panel, 'theme', after[0])}
    if name == 'settings.color_scheme_changed':
        return {'scheme': after[0], 'applied': after[1] != before[1],
                'saved': _private_saved(panel, 'color_scheme', after[0])}
    if name == 'settings.opacity_changed' and after[0] != before[0]:
        expected = after[0] / 100.0
        return {'percent': after[0], 'changed': True,
                'applied': all(abs(window.windowOpacity() - expected) < 0.01
                               for window in panel.opacity_targets()),
                'ink_unchanged': after[1] == before[1],
                'saved': _private_saved(panel, 'ui_opacity', after[0])}
    if name == 'settings.monitor_changed':
        from PyQt6.QtWidgets import QApplication
        from document_preferences import monitor_key
        target = panel.target_screen()
        available = bool(after) and any(monitor_key(screen) == after for screen in QApplication.screens())
        return {'configured': available, 'applied': available and panel.canvas.screen() == target,
                'saved': _private_saved(panel, 'annotation_screen', after)}
    if name == 'settings.timer_volume_changed':
        return {'volume': after, 'changed': True,
                'saved': _private_saved(panel, 'timer_alarm_volume', after)}
    return None


def interface_action(name):
    def decorate(function):
        def wrapped(panel, *args, **kwargs):
            bus = getattr(panel, 'teaching_events', None)
            if bus is None:
                return function(panel, *args, **kwargs)
            operation = bus.begin_operation(name)
            before = _snapshot(panel, name)
            try:
                result = function(panel, *args, **kwargs)
                details = _details(panel, name, before)
                if details is not None:
                    failed = any(details.get(key) is False for key in
                                 ('saved', 'applied', 'configured', 'ink_unchanged', 'logo_visible'))
                    bus.emit_result(operation, name, 'failed' if failed else 'success', details)
                return result
            finally:
                bus.discard_operation(operation)
        if len(signature(function).parameters) == 1:
            @wraps(function)
            def slot(panel):
                return wrapped(panel)
            return slot
        return wraps(function)(wrapped)
    return decorate


def interface_bindings(panel):
    bindings = {}
    for target, attribute in {
        'settings.orientation.landscape': 'btn_orient_landscape',
        'settings.orientation.portrait': 'btn_orient_portrait', 'toolbar.logo': 'logo_window',
        'settings.theme': 'btn_theme', 'settings.color_scheme': 'color_scheme_combo',
        'settings.opacity': 'ui_opacity_slider',
    }.items():
        bindings[target] = lambda attribute=attribute: getattr(panel, attribute, None)
    for target, attribute in {'settings.monitor': 'monitor_combo',
                              'settings.timer_volume': 'volume_slider'}.items():
        bindings[target] = lambda attribute=attribute: getattr(
            getattr(panel, 'document_preferences', None), attribute, None)
    return bindings


def reveal_interface_target(panel, target):
    """Reveal a real settings widget without auto-expanding the logo step."""
    if target == 'toolbar.logo':
        return
    from contextlib import nullcontext
    bus = getattr(panel, 'teaching_events', None)
    with bus.suppress() if bus is not None else nullcontext():
        settings = getattr(panel, 'settings_panel', None)
        if settings is None or not settings.isVisible():
            panel.open_settings_panel()
        widget = interface_bindings(panel)[target]()
        if widget is not None:
            panel.settings_scroll.ensureWidgetVisible(widget)
