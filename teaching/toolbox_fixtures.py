# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded C12 setup in the host's already isolated practice runtime."""
from contextlib import nullcontext
from decimal import Decimal

TOOLBOX_FIXTURES = frozenset('toolbox.c12.' + chapter for chapter in
                             ('calculator', 'scientific_calculator', 'roster', 'timer',
                              'magnifier', 'spotlight'))


def prepare_toolbox_fixture(panel, fixture, paths):
    if fixture not in TOOLBOX_FIXTURES:
        return
    if not paths.practice or paths != panel.runtime_context.paths or not panel.runtime_context.ui_active:
        raise ValueError('toolbox preparation requires this active private practice')
    from i18n import tr
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
        panel.set_timer_alarm_volume(0, persist=False)
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
        canvas.smart_shapes_enabled = False
        panel.show_only_sub(None)
        panel._teaching_toolbox_fixture = fixture
        panel._teaching_magnifier_source = None
        panel._teaching_magnifier_frame_key = None
        canvas._teaching_magnifier_origin = None
        if fixture.endswith('.calculator'):
            _prepare_calculator(panel, 'deg')
        elif fixture.endswith('.scientific_calculator'):
            _prepare_calculator(panel, 'rad')
        elif fixture.endswith('.roster'):
            names = tuple(tr('teaching_roster_fiction_' + str(i)) for i in range(1, 7))
            panel._teaching_fictional_roster = names
            panel.roster = list(names)
            panel.roster_drawn = set()
            panel.save_roster()
            if panel.roster_panel is not None:
                panel.refresh_roster_ui()
        elif fixture.endswith('.timer'):
            panel.set_timer_preset(2)
            panel.reset_timer()
        elif fixture.endswith('.magnifier'):
            canvas.magnifier_zoom = 2.0
            canvas.magnifier_size = 260
            canvas.magnifier_pixmap = None
            panel.mag_size_slider.blockSignals(True)
            panel.mag_size_slider.setValue(260)
            panel.mag_size_slider.blockSignals(False)
            panel.update_magnifier_ui()
        panel.update_whiteboard_ui()
        canvas.update()


def _prepare_calculator(panel, angle):
    panel.open_calculator()
    widget = panel.calculator_widget
    widget.history.clear()
    widget.engine.ans = Decimal(0)
    widget.engine.memory_clear()
    widget.engine.set_angle_mode(angle)
    panel.calculator_angle_mode = angle
    widget.scientific_buttons['angle'].setText(angle.upper())
    # Clear each retained draft through the normal clear action, including its
    # repeat-equals guard, before returning to the initial basic page.
    for mode in ('scientific', 'basic'):
        widget.set_mode(mode)
        panel._calc_input('C')
    widget.history_toggle.setChecked(False)
    widget.history_search.clear()
    widget.history_filter.setCurrentIndex(0)
    panel.calc_panel.hide()


def render_private_magnifier_frame(panel):
    """Draw app-owned board data; never capture the desktop or a QWidget."""
    if not panel.runtime_context.paths.practice or not panel.runtime_context.ui_active:
        raise ValueError('synthetic magnifier frame requires active private practice')
    from math import ceil
    from PyQt6.QtGui import QPainter, QPixmap
    canvas = panel.canvas
    dpr = canvas.devicePixelRatioF() or 1.0
    frame = QPixmap(ceil(canvas.width() * dpr), ceil(canvas.height() * dpr))
    frame.setDevicePixelRatio(dpr)
    background = canvas.board_background()
    frame.fill(background)
    painter = QPainter(frame)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if canvas.board_view_active:
            painter.setWorldTransform(canvas.board_view.transform())
        canvas.draw_content(painter)
    finally:
        painter.end()
    panel._teaching_magnifier_source = 'private_canvas'
    panel._teaching_magnifier_frame_key = frame.cacheKey()
    panel._teaching_magnifier_background = background
    return frame
