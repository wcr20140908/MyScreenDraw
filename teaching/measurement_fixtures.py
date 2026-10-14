# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare C11 using only the already isolated teaching runtime."""

def prepare_measurement_fixture(panel, fixture, paths):
    if fixture not in {'measurement.c11.instruments', 'measurement.c11.calibration'}:
        return
    if not paths.practice or paths != panel.runtime_context.paths:
        raise ValueError('measurement preparation requires the private practice')
    with panel.teaching_events.suppress():
        canvas = panel.canvas
        canvas.finish_active_ink()
        canvas.end_text_edit()
        canvas.clear_aids()
        canvas.cancel_pending_points()
        canvas.selected_ids.clear()
        panel.set_drawing_mode(True)
        panel.set_tool('PEN', panel.btn_pen)
        canvas.smart_shapes_enabled = False
        canvas.ruler_calibrations = {}
        canvas.ruler_calibration = None
        panel.close_thumbnail_panel()
        panel.show_only_sub(panel.aid_sub)
        settings = getattr(panel, 'settings_panel', None)
        if settings is not None:
            settings.hide()
        panel.update_ruler_calibration_label()
