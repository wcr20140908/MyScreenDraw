# SPDX-License-Identifier: GPL-3.0-or-later
"""Welcome UI is nonmodal and emits choices, never persistence or practice."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QCoreApplication, QEvent, Qt
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication

import i18n


@pytest.fixture
def qt_app():
    app = QApplication.instance() or QApplication([])
    before = set(app.topLevelWidgets())
    yield app
    for widget in app.topLevelWidgets():
        if widget not in before and not sip.isdeleted(widget):
            widget.hide()
            widget.deleteLater()
    for _ in range(4):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def make_dialog(language='zh'):
    from teaching.welcome import TeachingWelcome
    return TeachingWelcome(lambda key: i18n.TEXT[language][key])


def test_welcome_does_not_force_modality_focus_or_automatic_start(qt_app):
    value = make_dialog()
    decisions = QSignalSpy(value.decision_made)
    value.show()
    qt_app.processEvents()
    assert value.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert not value.isModal()
    assert value.windowModality() == Qt.WindowModality.NonModal
    assert not value.start_button.isDefault() and not value.later_button.isDefault()
    assert len(decisions) == 0


@pytest.mark.parametrize('action,decision', [('start', 'accepted'), ('later', 'skipped'),
                                             ('close', 'dismissed'), ('escape', 'dismissed')])
def test_explicit_choice_emits_once_and_closes_without_starting_any_program(qt_app, action, decision):
    value = make_dialog()
    decisions = QSignalSpy(value.decision_made)
    value.show()
    qt_app.processEvents()
    if action in ('start', 'later'):
        getattr(value, f'{action}_button').click()
    elif action == 'escape':
        QTest.keyClick(value, Qt.Key.Key_Escape)
    else:
        value.close()
    assert len(decisions) == 1 and decisions[0] == [decision]
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert sip.isdeleted(value)


def test_choice_signal_can_synchronously_close_dialog_without_duplicate_decision(qt_app):
    value = make_dialog()
    decisions = QSignalSpy(value.decision_made)
    value.decision_made.connect(value.close)
    value.show()
    value.start_button.click()
    assert len(decisions) == 1 and decisions[0] == ['accepted']


@pytest.mark.parametrize('language', ['zh', 'en', 'fr', 'es', 'de', 'ru', 'ko', 'ja'])
def test_all_eight_languages_render_actual_fixed_strings_without_markup(qt_app, language):
    value = make_dialog(language)
    value.resize(480, 280)
    value.show()
    qt_app.processEvents()
    assert value.windowTitle() == i18n.TEXT[language]['teaching_welcome_title']
    assert value.body_label.text() == i18n.TEXT[language]['teaching_welcome_body']
    assert value.body_label.textFormat() == Qt.TextFormat.PlainText
    assert value.start_button.text() == i18n.TEXT[language]['teaching_welcome_start']
    assert value.later_button.text() == i18n.TEXT[language]['teaching_welcome_later']
    assert value.body_label.wordWrap() and value.body_label.isVisible()
    assert value.rect().contains(value.start_button.geometry())
    assert value.rect().contains(value.later_button.geometry())


def readiness():
    from teaching.onboarding import TeachingReadiness
    return TeachingReadiness(lifecycle_ready=True, restore_finished=True, layout_ready=True,
                             foreground=True, application_visible=True)


def coordinator(tmp_path, start_core):
    from teaching.onboarding import WelcomePolicy
    from teaching.state import TutorialStateStore
    from teaching.welcome import WelcomeCoordinator
    store = TutorialStateStore(tmp_path / 'tutorial-state.json')
    policy = WelcomePolicy(store)
    bridge = WelcomeCoordinator(policy, translate=lambda key: i18n.TEXT['zh'][key], start_core=start_core)
    return store, bridge


def test_coordinator_checks_readiness_before_creating_any_welcome(qt_app, tmp_path):
    from dataclasses import replace
    store, bridge = coordinator(tmp_path, lambda: pytest.fail('No explicit choice'))
    assert not bridge.maybe_show(replace(readiness(), text_edit_active=True))
    assert bridge.dialog is None and not store.path.exists()
    assert bridge.maybe_show(readiness())
    assert bridge.dialog.isVisible() and store.welcome == 'unseen'
    assert not bridge.maybe_show(readiness())
    bridge.close()
    assert store.welcome == 'dismissed'


def test_real_welcome_signal_records_accepted_before_requesting_practice(qt_app, tmp_path):
    starts = []
    store, bridge = coordinator(tmp_path, lambda: starts.append(store.welcome))
    assert bridge.maybe_show(readiness())
    bridge.dialog.start_button.click()
    assert starts == ['accepted'] and store.welcome == 'accepted'
    assert store.completed_count() == 0
    bridge.close()
    assert not bridge.maybe_show(readiness()) and starts == ['accepted']


def test_failed_launch_from_qt_signal_does_not_escape_or_repeat_welcome(qt_app, tmp_path):
    def fail():
        raise OSError('simulated child launch failure')
    store, bridge = coordinator(tmp_path, fail)
    failures = QSignalSpy(bridge.failed)
    assert bridge.maybe_show(readiness())
    bridge.dialog.start_button.click()
    assert len(failures) == 1 and failures[0] == ['teaching_session_start_failed']
    assert store.welcome == 'accepted'
    assert not bridge.maybe_show(readiness())
    bridge.close()


def test_start_callback_can_synchronously_close_coordinator_without_double_decision(qt_app, tmp_path):
    starts = []
    def start():
        starts.append(True)
        bridge.close()
    store, bridge = coordinator(tmp_path, start)
    assert bridge.maybe_show(readiness())
    bridge.dialog.start_button.click()
    assert starts == [True] and store.welcome == 'accepted'
    assert not bridge.maybe_show(readiness())


def test_readonly_state_has_no_automatic_dialog_but_does_not_mutate_file(qt_app, tmp_path):
    path = tmp_path / 'tutorial-state.json'
    data = b'{"schema_version":999}'
    path.write_bytes(data)
    store, bridge = coordinator(tmp_path, lambda: pytest.fail('must not launch'))
    assert not bridge.maybe_show(readiness())
    assert bridge.dialog is None and path.read_bytes() == data
    bridge.close()
