# SPDX-License-Identifier: GPL-3.0-or-later
"""Observe completed measurement actions in the private teaching application."""
from functools import wraps


def measurement_action(name):
    def decorate(function):
        @wraps(function)
        def wrapped(owner, *args, **kwargs):
            panel = owner.panel if hasattr(owner, 'aids') else owner
            bus = getattr(panel, 'teaching_events', None)
            if bus is None:
                return function(owner, *args, **kwargs)
            canvas = panel.canvas
            operation = bus.begin_operation(name)
            before = (len(canvas.aids), dict(canvas.ruler_calibrations))
            try:
                result = function(owner, *args, **kwargs)
                details = None
                if name == 'aid.added' and result is not None and len(canvas.aids) > before[0]:
                    details = {'kind': result['kind']}
                elif name == 'aid.cleared' and before[0] and not canvas.aids:
                    details = {'remaining': 0}
                elif name == 'aid.calibration_changed' and canvas.ruler_calibrations != before[1]:
                    key, ratio, calibrated = canvas.current_screen_calibration()
                    saved = getattr(panel, '_last_settings_write', None)
                    if saved is not None and saved[1]['ruler_calibrations'] == canvas.ruler_calibrations:
                        details = {'calibrated': calibrated, 'px_per_mm': ratio}
                if details is not None:
                    bus.emit_result(operation, name, 'success', details)
                return result
            finally:
                bus.discard_operation(operation)
        return wrapped
    return decorate


def measurement_drag(function):
    @wraps(function)
    def wrapped(canvas, event):
        bus = getattr(canvas.panel, 'teaching_events', None)
        drag = canvas.aid_drag
        if bus is None or drag is None:
            return function(canvas, event)
        aid = next(item for item in canvas.aids if item['id'] == drag['id'])
        def state():
            return (aid['pos'].x(), aid['pos'].y(), aid.get('rotation', 0),
                    aid.get('scale', 1), aid.get('width', 36))
        before = (drag['origin_pos'].x(), drag['origin_pos'].y(), drag['origin_rot'],
                  drag['origin_scale'], drag['origin_width'])
        operation = bus.begin_operation('aid.transformed')
        try:
            result = function(canvas, event)
            if canvas.aid_drag is None and state() != before:
                bus.emit_result(operation, 'aid.transformed', 'success',
                                {'kind': aid['kind'], 'action': drag['mode']})
            return result
        finally:
            bus.discard_operation(operation)
    return wrapped
