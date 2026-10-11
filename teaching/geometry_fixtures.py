# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted C06 preparation uses this active private practice only."""
GEOMETRY_FIXTURES=frozenset('geometry.c06.'+name for name in
                           ('plane','solid','points','recognition_snap'))


def prepare_geometry_fixture(panel,fixture,paths):
    if fixture not in GEOMETRY_FIXTURES:return
    context=panel.runtime_context
    if not paths.practice or context.paths!=paths or not context.ui_active:
        raise ValueError('geometry setup requires this active private practice')
    canvas=panel.canvas
    canvas._discard_teaching_laser_operations()
    canvas.laser_trail=[]
    canvas.cancel_pending_points()
    canvas.selected_ids.clear()
    panel.pen_defaults_enabled=False
    panel.choose_pen_style('fountain' if fixture.endswith('recognition_snap') else 'pen')
    panel.set_drawing_mode(True)
    panel.set_tool('SHAPE',panel.btn_shape)
    canvas.shape_type='ELLIPSE' if fixture.endswith('plane') else 'LINE'
    canvas.smart_shapes_enabled=False
    panel.update_shape_buttons()
    panel.show_only_sub(None)
    panel.close_thumbnail_panel()
    settings=getattr(panel,'settings_panel',None)
    if settings is not None:settings.hide()
    panel.update_whiteboard_ui()
