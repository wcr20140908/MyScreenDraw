# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings use a single readable text style across embedded preference panels."""
import pytest
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QLabel, QCheckBox
from PyQt6.QtTest import QTest

from test_upgrade_settings import app, rig


@pytest.mark.parametrize('theme_name', ['dark', 'light'])
@pytest.mark.parametrize('scheme', ['classic', 'warm_indigo'])
def test_settings_labels_hints_and_fields_share_font_and_text_color(rig, theme_name, scheme):
    panel, _ = rig.fresh()
    panel.theme_name = theme_name
    panel.color_scheme = scheme
    panel.theme = panel.theme_for(theme_name, scheme, panel.custom_color_schemes)
    panel.apply_theme()
    panel.open_settings_panel()
    QTest.qWait(5)
    content = panel.settings_scroll.widget()
    combo = panel.document_preferences.interval_combo
    assert combo.font().pixelSize() == 12
    for label in panel.settings_panel.findChildren(QLabel):
        if label.objectName().startswith('releaseNotice'):
            continue
        assert label.font().pixelSize() == combo.font().pixelSize(), (label.text(), label.font().pixelSize())
        assert label.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText) == QColor(panel.theme['text']), label.text()
    for checkbox in content.findChildren(QCheckBox):
        assert checkbox.font().pixelSize() == combo.font().pixelSize()
        assert checkbox.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.WindowText) == QColor(panel.theme['text'])
    for label in content.findChildren(QLabel):
        if label.objectName() == 'SettingsSection':
            assert label.font().bold()


def test_document_help_is_brief_and_uses_shared_hint_role(rig):
    panel, _ = rig.fresh()
    panel.open_settings_panel()
    preferences = panel.document_preferences
    for label in (preferences.preserve_images_hint, preferences.interval_hint, preferences.volume_hint):
        assert label.objectName() == 'SettingsHint'
        assert label.wordWrap()
        assert len(label.text()) < 45
