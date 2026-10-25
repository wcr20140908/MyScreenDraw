# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted C09 setup: copy only synthetic media into the active private practice."""
from contextlib import nullcontext
from pathlib import Path
from shutil import copyfile

MEDIA_FIXTURES = frozenset(("media.c09.image", "media.c09.pdf_pages"))
MEDIA_ASSETS = {
    "media.c09.image": "fixtures/media-c09-sample.png",
    "media.c09.pdf_pages": "fixtures/media-c09-sample.pdf",
}


def prepare_media_fixture(panel, loader, fixture, paths):
    if fixture not in MEDIA_FIXTURES:
        return
    context = panel.runtime_context
    if not paths.practice or context.paths != paths or not context.ui_active:
        raise ValueError("C09 setup requires this active private practice")
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
        # C09 teaches image editing in the already verified private practice.
        panel.set_preserve_original_images(False, persist=False)
        panel.pen_defaults_enabled = False
        panel.choose_pen_style("pen")
        panel.set_drawing_mode(True)
        panel.set_tool("PEN", panel.btn_pen)
        canvas.pen_width = 4
        canvas.smart_shapes_enabled = False
        panel.show_only_sub(None)
        panel.close_thumbnail_panel()
        settings = getattr(panel, "settings_panel", None)
        if settings is not None:
            settings.hide()
        panel._teaching_media_source_path = None
        asset = MEDIA_ASSETS[fixture]
        source = loader.asset_path(asset)
        directory = paths.require_directory_path(paths.data_dir / "media-fixtures")
        directory.mkdir(parents=True, exist_ok=True)
        destination = paths.require_write_path(directory / Path(asset).name)
        copyfile(str(source), str(destination))
        panel._teaching_media_source_path = str(destination)
        panel.update_whiteboard_ui()
        panel.update_history_ui()
