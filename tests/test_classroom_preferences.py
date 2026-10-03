# SPDX-License-Identifier: GPL-3.0-or-later
"""Integrated classroom preferences; never takes over the real desktop."""
import copy
import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from test_upgrade_settings import app, rig


def press(canvas, button=Qt.MouseButton.LeftButton):
    event = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(230, 240),
                        QPointF(230, 240), button, button, Qt.KeyboardModifier.NoModifier)
    canvas.mousePressEvent(event)


def release(canvas):
    move = QMouseEvent(QEvent.Type.MouseMove, QPointF(270, 260),
                       QPointF(270, 260), Qt.MouseButton.NoButton,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    canvas.mouseMoveEvent(move)
    event = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(270, 260),
                        QPointF(270, 260), Qt.MouseButton.LeftButton,
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    canvas.mouseReleaseEvent(event)


@pytest.mark.parametrize('tool', ['ERASER', 'SELECT', 'SHAPE', 'TEXT', 'MAGNIFIER', 'SPOTLIGHT'])
def test_page_first_contact_restores_exact_pen_and_draws(rig, tool):
    p, c = rig.fresh()
    p.choose_pen_style('chalk')
    p.set_tool(tool, p.btn_eraser)
    c.new_page()
    assert c._page_return_pending
    assert c.draw_state == tool
    press(c)
    assert c.draw_state == 'PEN' and c.pen_style == 'chalk'
    assert not c._page_return_pending
    assert c.current_stroke_id is not None
    release(c)
    assert c.all_segments


@pytest.mark.parametrize('tool', ['MARKER', 'LASER'])
def test_returns_last_annotation_category(rig, tool):
    p, c = rig.fresh()
    p.set_tool(tool, p.btn_pen)
    p.set_tool('ERASER', p.btn_eraser)
    c.new_page(); press(c)
    assert c.draw_state == tool
    release(c)


def test_manual_selection_after_page_cancels_return(rig):
    p, c = rig.fresh()
    p.set_tool('ERASER', p.btn_eraser)
    c.new_page()
    p.set_tool('ERASER', p.btn_eraser)  # even selecting the same tool is explicit
    assert not c._page_return_pending
    press(c)
    assert c.draw_state == 'ERASER'
    release(c)


def test_disabled_and_boundary_noop_do_not_arm(rig):
    p, c = rig.fresh()
    p.whiteboard_auto_pen = False
    p.set_tool('ERASER', p.btn_eraser)
    c.new_page()
    assert not c._page_return_pending
    p.whiteboard_auto_pen = True
    c.switch_page(1)
    assert not c._page_return_pending
    c.switch_page(-1)
    assert c._page_return_pending


def test_mouse_mode_return_captures_only_after_whiteboard_page(rig):
    p, c = rig.fresh()
    c.new_page()
    p.set_drawing_mode(False)
    assert c._mouse_passthrough
    c.switch_page(-1)
    assert c._page_return_pending
    assert not c._mouse_passthrough
    press(c)
    assert c.is_drawing_mode and c.draw_state == 'PEN'
    release(c)
    p.set_drawing_mode(False)
    assert c._mouse_passthrough


def test_right_click_does_not_consume_pending(rig):
    p, c = rig.fresh()
    p.set_tool('ERASER', p.btn_eraser); c.new_page()
    press(c, Qt.MouseButton.RightButton)
    assert c._page_return_pending
    assert c.draw_state == 'ERASER'


def test_existing_annotation_unchanged_and_page_delete_arms(rig):
    p, c = rig.fresh()
    p.choose_pen_style('rainbow'); c.new_page()
    assert not c._page_return_pending
    p.set_tool('ERASER', p.btn_eraser)
    c.delete_page()
    assert c._page_return_pending


def test_notice_started_once_and_dismissed_for_session(rig):
    p, c = rig.fresh()
    p.begin_usage_session()
    assert p.notice_state['launches'] == 1 and p._notice_visible
    p.begin_usage_session()
    assert p.notice_state['launches'] == 1
    p.build_settings_panel()
    p.dismiss_release_notice()
    p.sync_settings_panel()
    assert p.release_notice.isHidden()
    p2, c2 = rig.load(p.collect_settings())
    p2.begin_usage_session()
    assert p2.notice_state['launches'] == 2 and p2._notice_visible


def test_new_fields_roundtrip_with_defaults_off(rig):
    p, c = rig.fresh()
    p.whiteboard_auto_pen = False
    p.last_annotate_tool = 'MARKER'
    p.notice_state = {'launches': 7, 'last_version': 'v6.0.0'}
    saved = p.collect_settings()
    p2, c2 = rig.load(saved)
    for key in ('whiteboard_auto_pen', 'last_annotate_tool', 'notice_state', 'pen_defaults_enabled', 'pen_defaults'):
        assert p2.collect_settings()[key] == saved[key]

@pytest.mark.parametrize('style', ['pen','fountain','brush','calligraphy','pencil','crayon','chalk','neon','dashed','rainbow','arrow'])
def test_preset_reentry_not_every_click_or_stroke(rig, style):
    from pen_defaults import capture_current
    p, c = rig.fresh()
    p.choose_pen_style(style)
    c.pen_color = '#234567'; c.pen_width = 17; c.speed_width_enabled = False
    if style == 'calligraphy': c.calligraphy_angle = 121
    preset = capture_current(c, style)
    p.save_pen_default(style, preset)
    p.set_pen_defaults_enabled(True)
    original = copy.deepcopy(p.pen_defaults)
    c.pen_width = 28
    p.choose_pen_style(style)  # same selected pen opens its settings, not re-entry
    assert c.pen_width == 28
    press(c); release(c)
    assert c.pen_width == 28
    p.set_tool('ERASER', p.btn_eraser)
    p.choose_pen_style(style)
    assert c.pen_width == 17 and c.pen_color.name() == '#234567'
    assert p.pen_defaults == original
    p.pen_defaults_enabled = False
    c.pen_width = 29
    p.choose_pen_style('arrow' if style != 'arrow' else 'pen')
    p.choose_pen_style(style)
    assert c.pen_width == 29


@pytest.mark.parametrize('key', ['marker','laser'])
def test_other_annotation_presets_apply_and_roundtrip(rig, key):
    p, c = rig.fresh()
    preset = {'color':'#765432','width':23}
    if key == 'marker': preset['alpha_pct'] = 72
    p.save_pen_default(key,preset)
    p.pen_defaults_enabled = True
    p.set_tool(key.upper(),p.btn_pen)
    assert getattr(c,key+'_color').name() == '#765432'
    assert getattr(c,key+'_width') == 23
    if key == 'marker':
        assert p.marker_alpha_slider.value() == 72
    p2,c2=rig.load(p.collect_settings())
    assert p2.pen_defaults_enabled
    assert getattr(c2,key+'_width') == 23
    assert p2.pen_defaults == p.pen_defaults


def test_automatic_return_applies_preset_without_swallowing_contact(rig):
    p,c=rig.fresh()
    p.choose_pen_style('chalk')
    p.pen_defaults['chalk']['width']=18
    p.pen_defaults_enabled=True
    c.pen_width=33
    p.set_tool('ERASER',p.btn_eraser)
    c.new_page(); press(c)
    assert c.pen_width == 18 and c.current_stroke_id is not None
    release(c)
    assert c.all_segments


def test_multitouch_first_contact_returns_and_builds_two_strokes(rig):
    from test_multitouch import FakePoint, FakeTouchEvent
    from PyQt6.QtGui import QEventPoint
    p,c=rig.fresh()
    p.choose_pen_style('pencil')
    p.set_tool('ERASER',p.btn_eraser); c.new_page()
    def event(state,offset):
        return FakeTouchEvent([FakePoint(i,state,220+i*100+offset,220+offset) for i in (1,2)])
    assert c._handle_touch(event(QEventPoint.State.Pressed,0))
    assert c.draw_state == 'PEN' and c.pen_style == 'pencil'
    assert c._handle_touch(event(QEventPoint.State.Updated,40))
    assert c._handle_touch(event(QEventPoint.State.Released,60))
    assert len({s['id'] for s in c.all_segments}) == 2


def test_exit_whiteboard_and_same_tool_button_cancel(rig):
    p,c=rig.fresh()
    p.set_tool('ERASER',p.btn_eraser);c.new_page()
    p.handle_eraser_click()
    assert not c._page_return_pending
    c.switch_page(-1)
    assert c._page_return_pending
    c.exit_whiteboard()
    assert not c._page_return_pending


@pytest.mark.parametrize('bad',[None,[],{},'wrong',123])
def test_malformed_new_settings_preserve_healthy_siblings(rig,bad):
    p,c=rig.load({'whiteboard_auto_pen':bad,'pen_defaults_enabled':bad,
                 'pen_defaults':bad,'notice_state':bad,'last_annotate_tool':bad,
                 'update_check_enabled':False,'ui_opacity':71})
    assert p.whiteboard_auto_pen is True and p.pen_defaults_enabled is False
    assert p.update_check_enabled is False and p.ui_opacity == 71
    assert p.last_annotate_tool == 'PEN'


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_new_checkbox_text_uses_theme_foreground(rig, theme):
    from PyQt6.QtGui import QPalette
    from PyQt6.QtWidgets import QApplication
    p, _ = rig.fresh()
    p.theme_name = theme
    p.theme = p.THEMES[theme]
    p.apply_theme()
    p.open_settings_panel()
    QApplication.processEvents()
    for box in (p.auto_pen_checkbox, p.pen_defaults_checkbox,
                p.pen_defaults_editor.speed_check):
        assert box.palette().color(QPalette.ColorRole.WindowText).name() == p.theme["text"].lower()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_settings_hints_have_readable_small_text_contrast(rig, theme):
    from PyQt6.QtGui import QColor, QPalette
    from PyQt6.QtWidgets import QApplication, QLabel
    p, _ = rig.fresh()
    p.theme_name = theme
    p.theme = p.THEMES[theme]
    p.apply_theme()
    p.open_settings_panel()
    QApplication.processEvents()
    def luminance(color):
        channels = [color.redF(), color.greenF(), color.blueF()]
        values = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in channels]
        return sum(v*w for v,w in zip(values, (.2126,.7152,.0722)))
    for label in p.settings_panel.findChildren(QLabel, "SettingsHint"):
        fg = luminance(label.palette().color(QPalette.ColorRole.WindowText))
        bg = luminance(QColor(p.theme["frame"]))
        assert (max(fg,bg)+.05)/(min(fg,bg)+.05) >= 4.5


@pytest.mark.parametrize("tool,key,width_attr", [("PEN","chalk","pen_width"),
                                                   ("MARKER","marker","marker_width"),
                                                   ("LASER","laser","laser_width")])
@pytest.mark.parametrize("entry", ["page", "tool", "mode", "annotate"])
def test_mouse_mode_reentry_applies_same_annotation_preset(rig, tool, key, width_attr, entry):
    p, c = rig.fresh()
    p.choose_pen_style("chalk")
    p.set_tool(tool, p.btn_pen)
    p.pen_defaults[key]["width"] = 17
    p.set_pen_defaults_enabled(True)
    setattr(c, width_attr, 28)
    p.set_drawing_mode(False)
    assert getattr(c, width_attr) == 28
    if entry == "page":
        c.new_page()
        press(c)
    elif entry == "tool":
        p.set_tool(tool, p.btn_pen)
    elif entry == "mode":
        p.set_drawing_mode(True)
    else:
        p.handle_annotate_click()
    assert c.is_drawing_mode and c.draw_state == tool
    assert getattr(c, width_attr) == 17
    assert p.pen_defaults[key]["width"] == 17
    if entry == "page":
        release(c)
        if tool != "LASER": assert c.all_segments
