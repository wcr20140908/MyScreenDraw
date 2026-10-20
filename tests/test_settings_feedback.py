# SPDX-License-Identifier: GPL-3.0-or-later
"""Settings feedback opens only the requested form, never during construction."""
import inspect
import textwrap
from unittest.mock import Mock

import pytest
from PyQt6.QtWidgets import QApplication

import i18n
import main


FORM_URL = "https://forms.cloud.microsoft/r/5i4Sj4wuH2"


@pytest.fixture
def panel(monkeypatch):
    assert QApplication.instance().platformName() == "offscreen"
    monkeypatch.setattr(main.QDesktopServices, "openUrl", Mock(return_value=True))
    value = main.ControlPanel()
    value.update_check_timer.stop()
    value.timer.stop()
    value.autosave_timer.stop()
    value.apply_theme()
    yield value
    from conftest import _dispose_offscreen_widgets
    _dispose_offscreen_widgets(QApplication.instance(), [value])


def feedback_contract(panel):
    panel.build_settings_panel()
    opened = main.QDesktopServices.openUrl
    opened.assert_not_called()
    button = getattr(panel, "btn_feedback", None)
    assert button is not None, "Settings must include the feedback button"
    assert button.text() == main.tr("feedback")
    assert panel.settings_scroll.widget().layout().itemAt(0).widget() is button
    button.click()
    opened.assert_called_once()
    assert opened.call_args.args[0].toString() == FORM_URL


def test_feedback_is_first_and_opens_exact_form_only_when_clicked(panel):
    feedback_contract(panel)


def test_feedback_label_is_translated_in_every_language():
    labels = i18n._BASE["feedback"]
    assert labels[0] == "反馈"
    assert len(labels) == len(i18n._LANGS)
    assert all(label.strip() for label in labels)


@pytest.mark.parametrize("mutation", ["missing-button", "wrong-url", "disconnected"])
def test_feedback_assertions_reject_known_bad_behaviors(panel, monkeypatch, mutation):
    source = textwrap.dedent(inspect.getsource(main.ControlPanel.build_settings_panel))
    if mutation == "missing-button":
        old = ('    self.btn_feedback = QPushButton(tr("feedback"))\n'
               '    self.btn_feedback.clicked.connect(\n'
               f'        lambda: QDesktopServices.openUrl(QUrl("{FORM_URL}")))\n'
               '    form.addWidget(self.btn_feedback)\n')
        new = ""
    elif mutation == "wrong-url":
        old, new = FORM_URL, "https://example.invalid/wrong-form"
    else:
        old = f'lambda: QDesktopServices.openUrl(QUrl("{FORM_URL}"))'
        new = 'lambda: None'
    assert source.count(old) == 1
    namespace = dict(vars(main))
    exec(compile(source.replace(old, new), "<known-bad-feedback>", "exec"), namespace)
    monkeypatch.setattr(main.ControlPanel, "build_settings_panel", namespace["build_settings_panel"])
    with pytest.raises(AssertionError):
        feedback_contract(panel)
