# SPDX-License-Identifier: GPL-3.0-or-later
"""Document/classroom preferences, independent of the large main UI module."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QSpinBox, QSlider, QApplication
from i18n import tr, trf

AUTOSAVE_PRESETS = (15, 30, 60, 120, 300)
COPY_PLACEMENTS = ("after", "before", "first", "last")


def bounded_int(value, default, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(minimum, min(maximum, value))


def monitor_key(screen):
    serial = screen.serialNumber() or ""
    return f"{screen.name()}|{serial}"


def select_monitor(screens, preference, fallback=None):
    for screen in screens:
        if monitor_key(screen) == preference:
            return screen
    return fallback if fallback in screens else (screens[0] if screens else None)


class DocumentPreferences(QWidget):
    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self.interval_label = QLabel(tr("autosave_interval"))
        layout.addWidget(self.interval_label)
        self.interval_combo = QComboBox()
        for seconds in AUTOSAVE_PRESETS:
            self.interval_combo.addItem(trf("seconds_value", value=seconds), seconds)
        self.interval_combo.addItem(tr("custom_interval"), -1)
        layout.addWidget(self.interval_combo)
        self.interval_custom = QSpinBox()
        self.interval_custom.setRange(5, 86400)
        self.interval_custom.setSuffix(tr("seconds_suffix"))
        layout.addWidget(self.interval_custom)
        self.interval_hint = QLabel(tr("autosave_interval_hint"))
        self.interval_hint.setWordWrap(True)
        layout.addWidget(self.interval_hint)
        layout.addWidget(QLabel(tr("page_copy_placement")))
        self.copy_combo = QComboBox()
        for placement in COPY_PLACEMENTS:
            self.copy_combo.addItem(tr("copy_" + placement), placement)
        layout.addWidget(self.copy_combo)
        layout.addWidget(QLabel(tr("annotation_monitor")))
        self.monitor_combo = QComboBox()
        layout.addWidget(self.monitor_combo)
        monitor_hint = QLabel(tr("annotation_monitor_hint"))
        monitor_hint.setWordWrap(True)
        layout.addWidget(monitor_hint)
        self.volume_label = QLabel()
        layout.addWidget(self.volume_label)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        layout.addWidget(self.volume_slider)
        self.volume_hint = QLabel(tr("timer_volume_hint"))
        self.volume_hint.setWordWrap(True)
        layout.addWidget(self.volume_hint)
        self.sync_from_panel()
        self.interval_combo.currentIndexChanged.connect(self._interval_selected)
        self.interval_custom.valueChanged.connect(self._custom_changed)
        self.copy_combo.currentIndexChanged.connect(lambda _: panel.set_page_copy_placement(self.copy_combo.currentData()))
        self.monitor_combo.currentIndexChanged.connect(lambda _: panel.set_annotation_screen(self.monitor_combo.currentData()))
        self.volume_slider.valueChanged.connect(panel.set_timer_alarm_volume)
        QApplication.instance().screenAdded.connect(self.refresh_screens)
        QApplication.instance().screenRemoved.connect(self.refresh_screens)

    def _interval_selected(self, _):
        seconds = self.interval_combo.currentData()
        custom = seconds == -1
        self.interval_custom.setVisible(custom)
        self.panel.set_autosave_interval(self.interval_custom.value() if custom else seconds, sync=not custom)

    def _custom_changed(self, value):
        if self.interval_combo.currentData() == -1:
            self.panel.set_autosave_interval(value, sync=False)

    def refresh_screens(self, *_):
        self.monitor_combo.blockSignals(True)
        try:
            self.monitor_combo.clear()
            self.monitor_combo.addItem(tr("monitor_auto"), "")
            for index, screen in enumerate(QApplication.screens()):
                geometry = screen.geometry()
                label = trf("monitor_label", index=index + 1, name=screen.name(),
                            width=geometry.width(), height=geometry.height())
                self.monitor_combo.addItem(label, monitor_key(screen))
            selected = self.monitor_combo.findData(self.panel.annotation_screen)
            if selected < 0 and self.panel.annotation_screen:
                self.monitor_combo.addItem(tr("monitor_unavailable"), self.panel.annotation_screen)
                selected = self.monitor_combo.count() - 1
            self.monitor_combo.setCurrentIndex(max(0, selected))
        finally:
            self.monitor_combo.blockSignals(False)

    def sync_from_panel(self):
        for widget in (self.interval_combo, self.interval_custom, self.copy_combo, self.volume_slider):
            widget.blockSignals(True)
        try:
            seconds = self.panel.autosave_interval_seconds
            index = self.interval_combo.findData(seconds)
            self.interval_combo.setCurrentIndex(index if index >= 0 else self.interval_combo.count() - 1)
            self.interval_custom.setValue(seconds)
            self.interval_custom.setVisible(index < 0)
            self.copy_combo.setCurrentIndex(max(0, self.copy_combo.findData(self.panel.page_copy_placement)))
            self.volume_slider.setValue(self.panel.timer_alarm_volume)
            self.volume_label.setText(trf("timer_alarm_volume", value=self.panel.timer_alarm_volume))
        finally:
            for widget in (self.interval_combo, self.interval_custom, self.copy_combo, self.volume_slider):
                widget.blockSignals(False)
        self.refresh_screens()
