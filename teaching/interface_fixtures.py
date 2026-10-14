# SPDX-License-Identifier: GPL-3.0-or-later
"""C13 baseline settings belong only to the active private practice."""
from contextlib import nullcontext

INTERFACE_FIXTURES = frozenset('interface.c13.' + chapter for chapter in
                              ('layout_theme', 'monitor_audio', 'lifecycle', 'system'))


def prepare_interface_fixture(panel, fixture, paths):
    if fixture not in INTERFACE_FIXTURES:
        return
    if not paths.practice or paths != panel.runtime_context.paths or not panel.runtime_context.ui_active:
        raise ValueError('interface preparation requires this active private practice')
    from .toolbox_actions import discard_timer_completion
    bus = getattr(panel, 'teaching_events', None)
    with bus.suppress() if bus is not None else nullcontext():
        canvas = panel.canvas
        canvas.finish_active_ink()
        canvas.end_text_edit()
        canvas._discard_teaching_laser_operations()
        canvas.laser_trail = []
        canvas.cancel_pending_points()
        canvas.selected_ids.clear()
        discard_timer_completion(panel)
        panel.reset_timer()
        panel.close_text_input()
        panel.close_thumbnail_panel()
        panel._close_name_projection()
        for name in ('calc_panel', 'roster_panel', 'settings_panel'):
            window = getattr(panel, name, None)
            if window is not None:
                window.hide()
        panel.pen_defaults_enabled = False
        panel.set_drawing_mode(True)
        panel.set_tool('PEN', panel.btn_pen)
        canvas.whiteboard_mode = True
        panel.show_only_sub(None)
        panel.set_ui_mode('icon', persist=False)
        panel.set_orientation('portrait')
        if panel.theme_name != 'light':
            panel.toggle_theme()
        panel.set_color_scheme('classic', persist=False)
        panel.set_ui_opacity(100, persist=False)
        panel.set_annotation_screen('', persist=False, apply=False)
        panel.set_timer_alarm_volume(0, persist=False)
        panel._teaching_interface_fixture = fixture
        panel.save_settings()
        panel.update_whiteboard_ui()
        canvas.update()
