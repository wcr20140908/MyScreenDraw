# SPDX-License-Identifier: GPL-3.0-or-later
"""Observe real C12 tool results; no bus means the original application path."""
from functools import wraps
from inspect import signature
import json

TOOLBOX_EVENTS = frozenset({
    'calculator.opened', 'calculator.input', 'calculator.calculated',
    'roster.opened', 'roster.drawn', 'roster.reset', 'timer.panel_opened',
    'timer.mode_changed', 'timer.running_changed', 'timer.reset', 'timer.finished',
    'magnifier.opened', 'magnifier.zoom_changed', 'magnifier.size_changed',
    'magnifier.refreshed', 'spotlight.changed', 'spotlight.moved',
})
TOOLBOX_METHODS = {
    'open_calculator': 'calculator.opened', '_calc_input': 'calculator.input',
    'open_roster_panel': 'roster.opened', 'draw_random_name': 'roster.drawn',
    'reset_drawn_names': 'roster.reset', 'handle_timer_click': 'timer.panel_opened',
    'set_timer_mode': 'timer.mode_changed', 'reset_timer': 'timer.reset',
    'handle_magnifier_click': 'magnifier.opened',
    'on_magnifier_size_changed': 'magnifier.size_changed',
    'refresh_magnifier': 'magnifier.refreshed', 'set_tool': 'spotlight.changed',
}


def _qt_slot(function, wrapped):
    # Keep a zero-argument Qt slot zero-argument after decoration: clicked(bool)
    # is otherwise forwarded by a *args wrapper to a method that cannot take it.
    if len(signature(function).parameters) == 1:
        @wraps(function)
        def slot(owner):
            return wrapped(owner)
        return slot
    return wraps(function)(wrapped)


def _panel(owner):
    return owner.panel if hasattr(owner, 'draw_state') else owner


def _frame_key(canvas):
    frame = canvas.magnifier_pixmap
    return frame.cacheKey() if frame is not None and not frame.isNull() else None


def _snapshot(panel, name):
    canvas = panel.canvas
    if name == 'calculator.opened':
        return panel.calc_panel is not None and panel.calc_panel.isVisible()
    if name in ('calculator.input', 'calculator.calculated'):
        return (panel._calc_expr, panel._calc_display.text())
    if name == 'roster.opened':
        return panel.roster_panel is not None and panel.roster_panel.isVisible()
    if name in ('roster.drawn', 'roster.reset'):
        return frozenset(panel.roster_drawn)
    if name == 'timer.panel_opened':
        return panel.timer_sub.isVisible()
    if name == 'timer.mode_changed':
        return panel.timer_mode
    if name == 'timer.reset':
        return (panel.timer_running, panel.timer_alerting, panel.timer_left)
    if name in ('magnifier.opened', 'spotlight.changed'):
        return canvas.draw_state
    if name == 'magnifier.zoom_changed':
        return canvas.magnifier_zoom
    if name == 'magnifier.size_changed':
        return canvas.magnifier_size
    if name == 'magnifier.refreshed':
        return _frame_key(canvas)


def _roster_saved(panel):
    paths = panel.runtime_context.paths
    if not paths.practice:
        return False
    try:
        saved = json.loads(paths.roster_file.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    return saved == {'names': panel.roster, 'drawn': sorted(panel.roster_drawn)}


def _result(panel, name, before, args):
    canvas = panel.canvas
    after = _snapshot(panel, name)
    if name in ('calculator.opened', 'roster.opened', 'timer.panel_opened'):
        return {'visible': True} if not before and after else None
    if name == 'calculator.input' and after != before:
        return {'key': str(args[0]), 'expression': panel._calc_expr,
                'display': panel._calc_display.text()}
    if name == 'calculator.calculated' and panel._calc_just_evaluated and after != before:
        return {'expression': before[0], 'result': panel._calc_expr,
                'display': panel._calc_display.text()}
    if name == 'roster.drawn' and len(after - before) == 1 and before < after:
        name_drawn = next(iter(after - before))
        return {'drawn': len(after), 'total': len(panel.roster), 'unique': True,
                'displayed': panel.roster_result.text() == name_drawn,
                'fictional': tuple(panel.roster) == getattr(panel, '_teaching_fictional_roster', None),
                'saved': _roster_saved(panel)}
    if name == 'roster.reset' and before and not after:
        return {'drawn': 0, 'total': len(panel.roster), 'saved': _roster_saved(panel)}
    if name == 'timer.mode_changed' and after != before:
        return {'mode': after, 'target': panel.timer_target, 'seconds': panel.timer_left}
    if name == 'timer.reset' and after != before and not panel.timer_running and not panel.timer_alerting:
        return {'mode': panel.timer_mode, 'seconds': panel.timer_left,
                'running': False, 'clock_stopped': not panel.timer_clock.isActive()}
    if name == 'magnifier.opened' and before != after and after == 'MAGNIFIER':
        return {'active': True, 'source': getattr(panel, '_teaching_magnifier_source', None),
                'frame': _frame_key(canvas) is not None}
    if name == 'magnifier.zoom_changed' and after != before:
        return {'zoom': after, 'increased': after > before}
    if name == 'magnifier.size_changed' and after != before:
        return {'size': after, 'changed': True}
    if name == 'magnifier.refreshed' and after is not None and after != before:
        return {'source': getattr(panel, '_teaching_magnifier_source', None), 'frame': True,
                'width': canvas.magnifier_pixmap.width(), 'height': canvas.magnifier_pixmap.height()}
    if name == 'spotlight.changed' and (before == 'SPOTLIGHT') != (after == 'SPOTLIGHT'):
        return {'active': after == 'SPOTLIGHT', 'tool': after}
    return None


def discard_timer_completion(panel):
    pending = getattr(panel, '_teaching_timer_completion', None)
    panel._teaching_timer_completion = None
    if pending is not None:
        pending[0].discard_operation(pending[1])


def toolbox_action(name):
    def decorate(function):
        def wrapped(owner, *args, **kwargs):
            panel = _panel(owner)
            bus = getattr(panel, 'teaching_events', None)
            if bus is None:
                return function(owner, *args, **kwargs)
            event = ('calculator.calculated' if name == 'calculator.input'
                     and args and args[0] == '=' else name)
            operation = bus.begin_operation(event)
            before = _snapshot(panel, event)
            if event in ('timer.mode_changed', 'timer.reset'):
                discard_timer_completion(panel)
            try:
                result = function(owner, *args, **kwargs)
                details = _result(panel, event, before, args)
                if details is not None:
                    outcome = ('failed' if event.startswith('roster.') and details.get('saved') is False
                               else 'success')
                    bus.emit_result(operation, event, outcome, details)
                return result
            finally:
                bus.discard_operation(operation)
        return _qt_slot(function, wrapped)
    return decorate


def teaching_timer_toggle(function):
    def wrapped(panel, *args, **kwargs):
        bus = getattr(panel, 'teaching_events', None)
        if bus is None:
            return function(panel, *args, **kwargs)
        discard_timer_completion(panel)
        before = panel.timer_running
        changed = bus.begin_operation('timer.running_changed')
        completion = (bus.begin_operation('timer.finished')
                      if not before and panel.timer_mode == 'DOWN' else None)
        retained = False
        try:
            result = function(panel, *args, **kwargs)
            if not before and panel.timer_running and panel.timer_mode == 'DOWN' and completion is not None:
                panel._teaching_timer_completion = (bus, completion, panel.timer_target)
                retained = True
            if before != panel.timer_running:
                bus.emit_result(changed, 'timer.running_changed', 'success', {
                    'mode': panel.timer_mode, 'running': panel.timer_running,
                    'seconds': panel.timer_left, 'clock_active': panel.timer_clock.isActive()})
            return result
        finally:
            bus.discard_operation(changed)
            if not retained:
                bus.discard_operation(completion)
    return _qt_slot(function, wrapped)


def teaching_timer_finished(function):
    def wrapped(panel, *args, **kwargs):
        bus = getattr(panel, 'teaching_events', None)
        if bus is None:
            return function(panel, *args, **kwargs)
        pending = getattr(panel, '_teaching_timer_completion', None)
        panel._teaching_timer_completion = None
        was_running = panel.timer_running
        try:
            result = function(panel, *args, **kwargs)
            if (pending is not None and was_running and panel.timer_mode == 'DOWN'
                    and panel.timer_target == pending[2] and panel.timer_left == 0
                    and not panel.timer_running and panel.timer_alerting and not panel.timer_clock.isActive()):
                pending[0].emit_result(pending[1], 'timer.finished', 'success', {
                    'mode': 'DOWN', 'target': pending[2], 'seconds': 0,
                    'running': False, 'alerting': True})
            return result
        finally:
            if pending is not None:
                pending[0].discard_operation(pending[1])
    return _qt_slot(function, wrapped)


def teaching_spotlight_move(function):
    @wraps(function)
    def wrapped(canvas, event):
        bus = getattr(canvas.panel, 'teaching_events', None)
        if bus is None or canvas.draw_state != 'SPOTLIGHT':
            return function(canvas, event)
        operation = bus.begin_operation('spotlight.moved')
        before = (canvas.mouse_pos.x(), canvas.mouse_pos.y())
        try:
            result = function(canvas, event)
            after = (canvas.mouse_pos.x(), canvas.mouse_pos.y())
            if canvas.draw_state == 'SPOTLIGHT' and after != before:
                bus.emit_result(operation, 'spotlight.moved', 'success', {
                    'moved': True, 'x': after[0], 'y': after[1]})
            return result
        finally:
            bus.discard_operation(operation)
    return wrapped


def toolbox_bindings(panel):
    """Lazy real-control resolvers; host supplies Tools/subpanel reveal callbacks."""
    bindings = {f'tools.{tool}': (lambda method=method: panel.tool_menu_buttons.get(method))
                for tool, method in (
                    ('calculator', 'open_calculator'), ('roster', 'open_roster_panel'),
                    ('timer', 'handle_timer_click'), ('magnifier', 'handle_magnifier_click'),
                    ('spotlight', 'handle_spotlight_click'))}
    for target, code in (('two', '2'), ('plus', '+'), ('three', '3'), ('equals', '=')):
        bindings['calculator.' + target] = lambda code=code: getattr(panel, 'calc_buttons', {}).get(code)
    for target, attribute in {
        'roster.draw': 'btn_roster_draw', 'roster.reset': 'btn_roster_reset',
        'timer.up': 'btn_timer_up', 'timer.down': 'btn_timer_down',
        'timer.start_pause': 'btn_timer_start', 'timer.reset': 'btn_timer_reset',
        'magnifier.zoom_in': 'btn_mag_zoom_in', 'magnifier.size': 'mag_size_slider',
        'magnifier.refresh': 'btn_mag_refresh',
    }.items():
        bindings[target] = lambda attribute=attribute: getattr(panel, attribute, None)
    return bindings


TOOLBOX_TARGETS = frozenset({
    'tools.calculator', 'tools.roster', 'tools.timer', 'tools.magnifier', 'tools.spotlight',
    'calculator.two', 'calculator.plus', 'calculator.three', 'calculator.equals',
    'roster.draw', 'roster.reset', 'timer.up', 'timer.down', 'timer.start_pause', 'timer.reset',
    'magnifier.zoom_in', 'magnifier.size', 'magnifier.refresh',
})


def reveal_toolbox_target(panel, target):
    """Open the target's existing panel under setup suppression."""
    from contextlib import nullcontext
    bus = getattr(panel, 'teaching_events', None)
    with bus.suppress() if bus is not None else nullcontext():
        settings = getattr(panel, 'settings_panel', None)
        if settings is not None:
            settings.hide()
        if target.startswith('tools.'):
            panel.show_only_sub(panel.tools_sub)
        elif target.startswith('calculator.'):
            if panel.calc_panel is None or not panel.calc_panel.isVisible():
                panel.open_calculator()
        elif target.startswith('roster.'):
            if panel.roster_panel is None or not panel.roster_panel.isVisible():
                panel.open_roster_panel()
        elif target.startswith('timer.'):
            panel.show_only_sub(panel.timer_sub)
        elif target.startswith('magnifier.'):
            panel.show_only_sub(panel.magnifier_sub)
