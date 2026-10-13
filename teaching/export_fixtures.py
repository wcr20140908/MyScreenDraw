# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted C10 setup: prepare only the active private export practice."""
from contextlib import nullcontext

EXPORT_FIXTURES = frozenset((
    "export.c10.formats",
    "export.c10.progress_cancel",
    "export.c10.result",
))


def prepare_export_fixture(panel, fixture, paths):
    if fixture not in EXPORT_FIXTURES:
        return
    context = panel.runtime_context
    if not paths.practice or context.paths != paths or not context.ui_active:
        raise ValueError("C10 setup requires this active private practice")
    events = getattr(panel, "teaching_events", None)
    with events.suppress() if events is not None else nullcontext():
        canvas = panel.canvas
        canvas.finish_active_ink()
        canvas.end_text_edit()
        canvas._discard_teaching_laser_operations()
        canvas.laser_trail = []
        canvas.cancel_pending_points()
        canvas.selected_ids.clear()
        panel.close_text_input()
        if getattr(panel, "_open_symbol_group", None) is not None:
            panel._toggle_symbol_group(panel._open_symbol_group)
        panel.pen_defaults_enabled = False
        panel.choose_pen_style("pen")
        panel.set_drawing_mode(True)
        panel.set_tool("PEN", panel.btn_pen)
        canvas.pen_width = 4
        canvas.smart_shapes_enabled = False
        canvas.whiteboard_mode = True
        panel.show_only_sub(None)
        panel.close_thumbnail_panel()
        settings = getattr(panel, "settings_panel", None)
        if settings is not None:
            settings.hide()
        panel._teaching_export_fixture = fixture
        panel.update_whiteboard_ui()
        panel.update_history_ui()
