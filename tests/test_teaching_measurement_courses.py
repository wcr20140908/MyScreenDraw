# SPDX-License-Identifier: GPL-3.0-or-later
"""Two direct private Qt flows cover the C11 measurement course."""
from PyQt6.QtCore import QPointF, QTimer, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QPushButton
import pytest
from test_teaching_writing_courses import writing_host, next_info, assert_step, finished
from test_teaching_business_adapters import mouse


@pytest.mark.parametrize('writing_host', ['c11.instruments'], indirect=True)
def test_measurement_instruments_use_real_controls_and_drag_handles(writing_host):
    host, progress = writing_host
    panel, canvas = host.panel, host.panel.canvas
    next_info(host)
    def drag(aid, mode):
        if mode == 'move':
            start = aid['pos']; end = start + QPointF(70, 60)
        else:
            local = canvas._aid_width_handle_local(aid) if mode == 'width' else (
                canvas._aid_rotate_handle_local(aid) if mode == 'rotate' else canvas._aid_scale_handle_local(aid))
            start = canvas.aid_transform(aid).map(local)
            delta = start - aid['pos']
            end = aid['pos'] + (QPointF(-delta.y(), delta.x()) if mode == 'rotate' else delta * 1.2)
            if mode == 'width': end = start + QPointF(0, 20)
        point = lambda p: (round(p.x()), round(p.y()))
        mouse(canvas, 'press', point(start))
        assert canvas.aid_drag['mode'] == mode
        mouse(canvas, 'move', point(end))
        mouse(canvas, 'release', point(end))
    for kind, modes in [('ruler', ('move', 'width')), ('protractor', ('rotate',)),
                        ('set_square_45', ('scale',)), ('set_square_30', ('scale',))]:
        panel.aid_buttons[kind].click()
        aid = canvas.aids[-1]
        assert aid['kind'] == kind
        for mode in modes: drag(aid, mode)
    assert_step(host, 'clear')
    panel.btn_aid_clear.click()
    assert not canvas.aids
    assert_step(host, 'done'); next_info(host); finished(host, progress)


@pytest.mark.parametrize('writing_host', ['c11.calibration'], indirect=True)
def test_calibration_is_saved_to_private_config_then_reset(writing_host, monkeypatch):
    host, progress = writing_host
    panel, canvas = host.panel, host.panel.canvas
    next_info(host)
    import sys
    callback_errors = []
    monkeypatch.setattr(sys, 'excepthook', lambda *error: callback_errors.append(error))
    dialog_type = host.module.RulerCalibrationDialog
    dialogs = []
    def calibration_dialog(*args, **kwargs):
        dialog = dialog_type(*args, **kwargs)
        dialogs.append(dialog)
        apply_button = next(button for button in dialog.findChildren(QPushButton)
                            if button.text() == host.module.tr('calibration_apply'))
        QTimer.singleShot(0, lambda: QTest.mouseClick(apply_button, Qt.MouseButton.LeftButton))
        return dialog
    monkeypatch.setattr(host.module, 'RulerCalibrationDialog', calibration_dialog)
    panel.btn_aid_calibrate.click()
    assert not callback_errors, [(str(error), tb.tb_lineno) for _, error, tb in callback_errors]
    assert canvas.ruler_calibrations and host.request.paths.config_file.is_file()
    assert_step(host, 'reset')
    panel.btn_aid_reset.click()
    assert not canvas.ruler_calibrations
    assert_step(host, 'done'); next_info(host); finished(host, progress)
