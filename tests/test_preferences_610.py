# SPDX-License-Identifier: GPL-3.0-or-later
import io
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import wave
from array import array
from unittest.mock import Mock, patch
from types import SimpleNamespace
import pytest
from PyQt6.QtCore import QRect
from PyQt6.QtWidgets import QApplication
import main
from alarm_audio import alarm_wave, play_alarm_async
from document_preferences import monitor_key, select_monitor
from test_document_safety_610 import document


def test_defaults_and_live_settings_controls(document):
    panel, canvas = document
    assert panel.autosave_interval_seconds == 30
    assert panel.timer_alarm_volume == 100
    assert panel.page_copy_placement == "after"
    panel.build_settings_panel()
    ui = panel.document_preferences
    ui.interval_combo.setCurrentIndex(ui.interval_combo.findData(120))
    assert panel.autosave_timer.interval() == 120000
    ui.interval_combo.setCurrentIndex(ui.interval_combo.count() - 1)
    ui.interval_custom.setValue(47)
    assert panel.autosave_interval_seconds == 47
    panel.resume_callbacks()
    assert panel.autosave_timer.interval() == 47000
    ui.copy_combo.setCurrentIndex(ui.copy_combo.findData("before"))
    assert panel.page_copy_placement == "before"
    ui.volume_slider.setValue(25)
    assert panel.timer_alarm_volume == 25
    assert "25" in ui.volume_label.text()
    assert ui.interval_hint.text()
    assert ui.monitor_combo.count() >= 2


def test_preferences_roundtrip_and_normalization(document, tmp_path, monkeypatch):
    panel, canvas = document
    monkeypatch.setattr(main, "CONFIG_FILE", str(tmp_path / "settings.json"))
    panel.set_autosave_interval(43)
    panel.set_timer_alarm_volume(17)
    panel.set_page_copy_placement("last")
    panel.set_annotation_screen("unplugged|serial", apply=False)
    saved = panel.collect_settings()
    assert saved["autosave_interval_seconds"] == 43
    assert saved["timer_alarm_volume"] == 17
    panel.autosave_interval_seconds = 30
    panel.timer_alarm_volume = 100
    panel.page_copy_placement = "after"
    panel.annotation_screen = ""
    panel.load_settings()
    assert panel.autosave_interval_seconds == 43
    assert panel.timer_alarm_volume == 17
    assert panel.page_copy_placement == "last"
    assert panel.annotation_screen == "unplugged|serial"
    assert panel.autosave_timer.interval() == 43000
    assert panel.set_autosave_interval(True) == 30
    assert panel.set_timer_alarm_volume(-100) == 0
    assert panel.set_timer_alarm_volume(999) == 100


def screen(name, serial, x):
    return SimpleNamespace(name=lambda: name, serialNumber=lambda: serial,
                           geometry=lambda: QRect(x, 0, 1920, 1080),
                           availableGeometry=lambda: QRect(x, 0, 1920, 1040))


def test_selected_display_and_unplug_fallback_without_changing_windows_primary(document, monkeypatch):
    panel, canvas = document
    primary, secondary = screen("primary", "A", 0), screen("teaching", "B", -1920)
    assert select_monitor([primary, secondary], monitor_key(secondary), primary) is secondary
    assert select_monitor([primary], monitor_key(secondary), primary) is primary
    monkeypatch.setattr(main.QApplication, "screens", lambda: [primary, secondary])
    monkeypatch.setattr(main.QApplication, "primaryScreen", lambda: primary)
    panel.annotation_screen = monitor_key(secondary)
    assert panel.target_screen() is secondary
    fake_canvas = SimpleNamespace(screen=lambda: primary, windowHandle=lambda: None,
        windowState=lambda: main.Qt.WindowState.WindowFullScreen,
        setWindowState=Mock(), setGeometry=Mock(), refresh_speed_scale=Mock(),
        mark_content_changed=Mock(), update=Mock(), isVisible=lambda: False)
    panel.canvas = fake_canvas
    monkeypatch.setattr(panel, "opacity_targets", lambda: [])
    monkeypatch.setattr(panel, "_position_page_rail", Mock())
    monkeypatch.setattr(panel, "close_thumbnail_panel", Mock())
    panel.apply_annotation_screen()
    fake_canvas.setGeometry.assert_called_with(secondary.geometry())
    assert panel.annotation_screen == monitor_key(secondary)
    # Losing a monitor falls back without discarding the saved preference.
    monkeypatch.setattr(main.QApplication, "screens", lambda: [primary])
    panel.apply_annotation_screen()
    fake_canvas.setGeometry.assert_called_with(primary.geometry())
    panel.canvas = canvas


def test_timer_passes_volume_without_touching_system_mixer(document, monkeypatch):
    panel, canvas = document
    panel.timer_alarm_volume = 31
    alarm = Mock()
    monkeypatch.setattr(main, "play_alarm_async", alarm)
    panel._timer_finished()
    alarm.assert_called_once_with(31)
    assert panel.timer_alerting
    panel.timer_flash.stop()


def test_pcm_amplitude_and_mute():
    def samples(volume):
        with wave.open(io.BytesIO(alarm_wave(volume)), "rb") as sound:
            assert sound.getframerate() == 22050
            return array("h", sound.readframes(sound.getnframes()))
    full, quarter, muted = samples(100), samples(25), samples(0)
    assert max(abs(v) for v in quarter) == pytest.approx(max(abs(v) for v in full) / 4, abs=1)
    assert not any(muted)
    with patch("alarm_audio.threading.Thread") as thread:
        assert play_alarm_async(0) is None
        thread.assert_not_called()
