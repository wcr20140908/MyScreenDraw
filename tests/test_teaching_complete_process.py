# SPDX-License-Identifier: GPL-3.0-or-later
"""All 48 chapters share a private process, real controls and restored parent work."""
from test_teaching_export_process import (
    BRIDGE as EXPORT_BRIDGE, CHAPTERS as EXPORT_CHAPTERS,
    parent_coordinator, practice_request, run_course_process,
)

CHAPTERS = EXPORT_CHAPTERS + (
    'c11.instruments', 'c11.calibration',
    'c12.calculator', 'c12.scientific_calculator', 'c12.roster', 'c12.timer',
    'c12.magnifier', 'c12.spotlight',
    'c13.layout_theme', 'c13.monitor_audio', 'c13.lifecycle', 'c13.system',
)
BRIDGE = EXPORT_BRIDGE.replace('chapters = ' + repr(EXPORT_CHAPTERS), 'chapters = ' + repr(CHAPTERS))
BRIDGE = BRIDGE.replace("    if engine.phase == 'paused' and current is not None and current.id == 'pause':", """
    if engine.phase == 'paused' and current is not None and current.id == 'pause_resume':
        if not trace.get('c13_resumed'):
            trace['c13_resumed'] = True
            self.presenter.controller.pause_button.click()
    elif engine.phase == 'paused' and current is not None and current.id == 'pause':""")
BRIDGE = BRIDGE.replace("    current = engine.current_step", """    current = engine.current_step
    current_key = [engine.chapter_id, engine.current_step_id, engine.phase]
    if current_key != trace.get('current'):
        trace['current'] = current_key
        trace['step_started'] = time.monotonic()
        record(self, 'step_entered')
    assert time.monotonic() - trace['step_started'] < 10, ('step stalled', current_key,
        panel.toolbar_window.isVisible(), panel.logo_window.isVisible(), str(panel.lifecycle.state),
        self.presenter._missing, panel.btn_theme.isVisible(), panel.btn_theme.isEnabled(),
        panel.settings_panel.isVisible() if panel.settings_panel else None)""")
BRIDGE = BRIDGE.replace("        elif chapter.startswith('c10.'):", r"""        elif chapter == 'c11.instruments':
            kinds = {'ruler': 'ruler', 'protractor': 'protractor',
                     'square_45': 'set_square_45', 'square_30': 'set_square_30'}
            if name in kinds:
                panel.aid_buttons[kinds[name]].click()
            elif name == 'clear':
                panel.btn_aid_clear.click()
                assert not canvas.aids
            else:
                aid = canvas.aids[-1]
                mode = name.split('_', 1)[0]
                if mode == 'move':
                    start = aid['pos']; end = start + QPointF(70, 60)
                else:
                    local = (canvas._aid_width_handle_local(aid) if mode == 'width' else
                        canvas._aid_rotate_handle_local(aid) if mode == 'rotate' else
                        canvas._aid_scale_handle_local(aid))
                    start = canvas.aid_transform(aid).map(local)
                    delta = start - aid['pos']
                    end = aid['pos'] + (QPointF(-delta.y(), delta.x()) if mode == 'rotate' else delta * 1.2)
                    if mode == 'width': end = start + QPointF(0, 20)
                mouse(canvas, 'press', round(start.x()), round(start.y()))
                assert canvas.aid_drag['mode'] == mode
                mouse(canvas, 'move', round(end.x()), round(end.y()))
                mouse(canvas, 'release', round(end.x()), round(end.y()))
        elif chapter == 'c11.calibration':
            if name == 'calibrate':
                original_dialog = self.module.RulerCalibrationDialog
                def create_dialog(*args, **kwargs):
                    dialog = original_dialog(*args, **kwargs)
                    button = next(button for button in dialog.findChildren(QPushButton)
                                  if button.text() == self.module.tr('calibration_apply'))
                    from PyQt6.QtTest import QTest
                    QTimer.singleShot(0, lambda: QTest.mouseClick(button, Qt.MouseButton.LeftButton))
                    return dialog
                self.module.RulerCalibrationDialog = create_dialog
                try: panel.btn_aid_calibrate.click()
                finally: self.module.RulerCalibrationDialog = original_dialog
                assert canvas.ruler_calibrations and self.request.paths.config_file.is_file()
            else:
                panel.btn_aid_reset.click()
                assert not canvas.ruler_calibrations
        elif chapter == 'c12.calculator':
            if name == 'open': panel.tool_menu_buttons['open_calculator'].click()
            else:
                panel.calc_buttons[{'two':'2','plus':'+','three':'3','equals':'='}[name]].click()
                if name == 'equals':
                    assert panel._calc_display.text() == '5'
                    trace['c12_basic_result'] = '5'
        elif chapter == 'c12.scientific_calculator':
            widget = panel.calculator_widget
            if name == 'open': panel.tool_menu_buttons['open_calculator'].click()
            elif name == 'mode': widget.mode_buttons['scientific'].click()
            elif name == 'angle':
                widget.scientific_buttons['angle'].click()
                assert widget.engine.angle_mode == 'deg'
                trace['c12_scientific_angle'] = 'deg'
            elif name == 'expression':
                widget.expression_edit.setText('sin(30)+√16')
                widget.expression_edit.textEdited.emit(widget.expression_edit.text())
            elif name == 'calculate':
                widget.scientific_buttons['equals'].click()
                assert widget.expression_edit.text() == '4.5'
                trace['c12_scientific_result'] = '4.5'
            elif name == 'ans_expression':
                widget.expression_edit.setText('Ans×2')
                widget.expression_edit.textEdited.emit(widget.expression_edit.text())
            elif name == 'ans_calculate':
                widget.scientific_buttons['equals'].click()
                assert widget.expression_edit.text() == '9'
                trace['c12_scientific_ans'] = '9'
            elif name == 'history_open': widget.history_toggle.click()
            elif name == 'history_restore':
                from decimal import Decimal
                from calculator import format_decimal
                entry = next(entry for entry in widget.history.entries
                             if entry.mode == 'scientific' and entry.input == 'sin(30)+√16'
                             and format_decimal(Decimal(entry.result)) == '4.5')
                item = next(widget.history_list.item(i) for i in range(widget.history_list.count())
                            if widget.history_list.item(i).data(Qt.ItemDataRole.UserRole) == entry.id)
                widget.history_list.setCurrentItem(item)
                widget.history_list.itemClicked.emit(item)
                assert widget.expression_edit.text() == 'sin(30)+√16'
                assert [(entry.input, format_decimal(Decimal(entry.result)))
                        for entry in widget.history.entries] == [
                    ('sin(30)+√16', '4.5'), ('Ans*2', '9')]
                trace['c12_scientific_restored'] = 'sin(30)+√16'
            assert widget.history.retention == 'session' and not widget.history.persistent
        elif chapter == 'c12.roster':
            if name == 'open': panel.tool_menu_buttons['open_roster_panel'].click()
            elif name == 'reset': panel.btn_roster_reset.click()
            else: panel.btn_roster_draw.click()
        elif chapter == 'c12.timer':
            if name == 'open': panel.tool_menu_buttons['handle_timer_click'].click()
            elif name == 'up': panel.btn_timer_up.click()
            elif name == 'start_up': panel.btn_timer_start.click()
            elif name == 'pause_up':
                if panel.timer_left > 0: panel.btn_timer_start.click()
            elif name == 'reset_up': panel.btn_timer_reset.click()
            elif name == 'down': panel.btn_timer_down.click()
            elif name == 'finish_down':
                if not panel.timer_running and not panel.timer_alerting: panel.btn_timer_start.click()
        elif chapter == 'c12.magnifier':
            if name == 'open':
                panel.tool_menu_buttons['handle_magnifier_click'].click()
                assert panel._teaching_magnifier_source == 'private_canvas'
                assert canvas.magnifier_pixmap is not None and not canvas.magnifier_pixmap.isNull()
            elif name == 'zoom': panel.btn_mag_zoom_in.click()
            elif name == 'size': panel.mag_size_slider.setValue(320)
            elif name == 'move':
                mouse(canvas, 'move', 220, 210)
                mouse(canvas, 'move', 260, 225)
            else: panel.btn_mag_refresh.click()
        elif chapter == 'c12.spotlight':
            if name == 'move': mouse(canvas, 'move', 210, 160)
            else: panel.tool_menu_buttons['handle_spotlight_click'].click()
        elif chapter == 'c13.layout_theme':
            if name in ('landscape','portrait'): getattr(panel, 'btn_orient_'+name).click()
            elif name in ('collapse','expand'): panel.logo_window.logo_btn.click()
            elif name in ('dark','light'): panel.btn_theme.click()
            elif name == 'opacity': panel.ui_opacity_slider.setValue(65)
            else:
                value = {'graphite':'graphite_teal','slate':'slate_blue','warm':'warm_indigo','classic':'classic'}[name]
                panel.color_scheme_combo.setCurrentIndex(panel.color_scheme_combo.findData(value))
        elif chapter == 'c13.monitor_audio':
            assert name == 'volume', 'This offscreen run must use the single-monitor branch'
            panel.document_preferences.volume_slider.setValue(40)
        elif chapter == 'c13.lifecycle':
            assert name == 'pause_resume'
            if not trace.get('c13_paused'):
                trace['c13_paused'] = True
                self.presenter.controller.pause_button.click()
        elif chapter.startswith('c10.'):""")


def test_all_courses_one_process_restores_parent_and_cleans_private_files(parent_coordinator, tmp_path, monkeypatch):
    proof = run_course_process(parent_coordinator, tmp_path, monkeypatch,
        chapters=CHAPTERS, bridge_source=BRIDGE, expected_steps=411)
    assert proof['c13_paused'] and proof['c13_resumed']
    assert proof['c12_basic_result'] == '5'
    assert proof['c12_scientific_angle'] == 'deg'
    assert proof['c12_scientific_result'] == '4.5'
    assert proof['c12_scientific_ans'] == '9'
    assert proof['c12_scientific_restored'] == 'sin(30)+√16'
