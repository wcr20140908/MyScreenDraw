# SPDX-License-Identifier: GPL-3.0-or-later
"""Bundled C13 startup and copy through the private, offscreen application host."""
import json
from pathlib import Path
import sys
import traceback
import uuid

import pytest
from PyQt6 import sip
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QScreen
from PyQt6.QtWidgets import QApplication

from runtime_paths import RuntimePaths
from teaching.application import ApplicationTeachingHost, PracticeChild, application_catalog
from teaching.bootstrap import bind_practice_paths, parse_practice_request, practice_arguments
from test_teaching_application import Peer
from test_teaching_application_isolation import drain

ROOT = Path(__file__).resolve().parents[1]


def final_chapters():
    catalog, _ = application_catalog(None, ROOT)
    return tuple(chapter.id for course in catalog.courses for chapter in course.chapters)[-3:]


@pytest.fixture
def interface_child(request, tmp_path, monkeypatch):
    import main
    app = QApplication.instance()
    assert app is not None and app.platformName() == 'offscreen'
    chapter_id = getattr(request, 'param', 'c13.layout_theme')
    paths = RuntimePaths.create_practice(ROOT, ROOT, temp_root=tmp_path / 'owned-temp')
    channel = 'myscreendraw-teaching-' + uuid.uuid4().hex
    parsed = parse_practice_request(
        practice_arguments(paths, channel, 'c13', chapter_id), app_dir=ROOT, resource_dir=ROOT,
        environ={'MYSCREENDRAW_PRACTICE_NONCE': paths.nonce,
                 'MYSCREENDRAW_PRACTICE_TEMP_ROOT': str(paths.temp_root)})
    # Track the real bootstrap's global bindings for teardown, not a fake host.
    for name in ('RUNTIME_CONTEXT', *paths.module_aliases()):
        monkeypatch.setattr(main, name, getattr(main, name))
    monkeypatch.setattr(main, 'LOGGER', None)
    context = bind_practice_paths(main, parsed)
    main.ensure_directories()
    failures = []

    def exception(exc_type, value, tb):
        failures.append(''.join(traceback.format_exception(exc_type, value, tb)))
    monkeypatch.setattr(sys, 'excepthook', exception)

    def forbidden(*args, **kwargs):
        raise AssertionError('desktop, updater and system startup effects are forbidden')
    monkeypatch.setattr(QScreen, 'grabWindow', forbidden)
    for name in ('grab_screen', 'check_for_updates', 'download_pending_update', 'toggle_autostart'):
        monkeypatch.setattr(main.ControlPanel, name, forbidden)
    for name in ('set_autostart', 'heal_autostart'):
        monkeypatch.setattr(main, name, forbidden)
    monkeypatch.setattr(main.keyboard, 'Listener', forbidden)
    monkeypatch.setattr(main, 'notify_user', lambda *args, **kwargs: None)
    prior = set(app.topLevelWidgets())
    peer = Peer()
    child = PracticeChild(parsed, peer, context=context,
        host_factory=lambda progress: ApplicationTeachingHost(main, parsed, on_progress=progress))
    try:
        child.start()
        yield child, peer
    finally:
        child.stop()
        for widget in set(app.topLevelWidgets()) - prior:
            if not sip.isdeleted(widget):
                for timer in widget.findChildren(QTimer):
                    timer.stop()
                widget.hide()
                widget.deleteLater()
        drain(app)
        assert not failures, '\n'.join(failures)


def activate(child, peer):
    assert child.phase == 'ready', peer.messages
    host = child.host
    assert not host.panel.canvas.isVisible()
    assert not host.panel.toolbar_window.isVisible()
    assert host.panel.listener is None and host.panel.lifecycle.tray_icon is None
    peer.control('activate')
    drain(QApplication.instance())
    assert child.phase == 'running', peer.messages
    assert host.presenter.engine.phase == 'running'
    assert host.presenter.engine.current_step_id == 'intro'
    assert host.presenter.controller.isVisible()
    return host


def click_next(host):
    controller = host.presenter.controller
    assert controller.next_button.isEnabled()
    controller.next_button.click()
    drain(QApplication.instance())


@pytest.mark.parametrize('interface_child', final_chapters(), indirect=True)
def test_catalog_final_three_start_and_finish_in_private_host(interface_child):
    child, peer = interface_child
    assert final_chapters() == ('c13.monitor_audio', 'c13.lifecycle', 'c13.system')
    host = activate(child, peer)
    engine = host.presenter.engine
    chapter_id = child.request.chapter_id
    assert engine.chapter_id == chapter_id
    click_next(host)
    if chapter_id == 'c13.monitor_audio':
        assert len(QApplication.screens()) == 1
        assert engine.current_step_id == 'single_screen'
        click_next(host)
        assert engine.current_step_id == 'volume'
        slider = host.panel.document_preferences.volume_slider
        assert slider.isVisible() and slider.isEnabled()
        slider.setValue(40)
        drain(QApplication.instance())
        saved = json.loads(child.request.paths.config_file.read_text(encoding='utf-8'))
        assert saved['timer_alarm_volume'] == host.panel.timer_alarm_volume == 40
    elif chapter_id == 'c13.lifecycle':
        assert engine.current_step_id == 'pause_resume'
        assert not host.presenter.controller.next_button.isEnabled()
        for action, phase in (('pause', 'paused'), ('resume', 'running')):
            host.presenter.controller.pause_button.click()
            assert peer.messages[-1][:2] == ('control', {'action': action})
            peer.control(action)
            drain(QApplication.instance())
            assert child.phase == phase
        assert engine.current_step_id == 'tray'
        click_next(host)
        assert engine.current_step_id == 'exit'
        click_next(host)
    else:
        assert engine.current_step_id == 'update'
        click_next(host)
        assert engine.current_step_id == 'autostart'
        click_next(host)
    assert engine.current_step_id == 'done'
    click_next(host)
    assert engine.phase == 'completed'
    assert any(kind == 'chapter_state' and payload['chapter_id'] == chapter_id
               and payload['status'] == 'completed' for kind, payload, _ in peer.messages)
    assert not engine._issued


@pytest.mark.parametrize('language', ('zh', 'en', 'fr', 'es', 'de', 'ru', 'ko', 'ja'))
def test_palette_instruction_uses_exact_translated_display_name(language, monkeypatch):
    import i18n
    monkeypatch.setattr(i18n, 'CURRENT', language)
    catalog, _ = application_catalog(None, ROOT)
    chapter = catalog.chapter_by_id('c13.layout_theme')
    steps = [step for step in chapter.steps if step.target == 'settings.color_scheme']
    assert len(steps) == 4
    for step in steps:
        palette_name = i18n.tr(step.title_key)
        assert palette_name in i18n.tr(step.body_key), (language, step.id, palette_name, i18n.tr(step.body_key))
        # Detect copied labels that happen to agree today but drift on translation updates.
        monkeypatch.setitem(i18n.TEXT[language], step.title_key, 'Palette display sentinel')
        assert 'Palette display sentinel' in i18n.tr(step.body_key)
