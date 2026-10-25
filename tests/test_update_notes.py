# SPDX-License-Identifier: GPL-3.0-or-later
"""Release notes use isolated storage, fake HTTP, and real offscreen Qt widgets."""
import inspect
import io
import json
import textwrap
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock
import urllib.error

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent, QThread, QUrl
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

import main
import update_notes as notes


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Release notes tests must not use real HTTP or child processes")
    monkeypatch.setattr(main.urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(main.subprocess, "Popen", forbidden)
    monkeypatch.setattr(main, "track_event", Mock())


@pytest.fixture
def controller(tmp_path):
    value = notes.NotesController(tmp_path / "history.json", Mock(return_value=("fetched", None)), lambda: True)
    yield value
    value.stop()
    QApplication.instance().processEvents()
    value.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def settle(controller):
    deadline = time.monotonic() + 3
    while controller._worker is not None and time.monotonic() < deadline:
        QTest.qWait(5)
    assert controller._worker is None, "Notes worker did not drain"


class Response(io.BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode("utf-8") if not isinstance(payload, bytes) else payload)

    def geturl(self):
        return "https://api.github.com/repos/wcr20140908/MyScreenDraw/releases/tags/v6.1.0"


def release(tag="v6.2.0", **extra):
    name = f"MyScreenDraw-{tag}-windows-x64.zip"
    return {"tag_name": tag, "draft": False, "prerelease": False, "body": "# Exact release\n\n- Change",
            "assets": [{"name": name, "browser_download_url":
                        f"https://github.com/wcr20140908/MyScreenDraw/releases/download/{tag}/{name}"}], **extra}


def test_selected_release_keeps_its_own_body_and_notes_failure_does_not_hide_update(monkeypatch):
    for body, error in [("# right release", None), (None, None), (42, "bad_release_notes")]:
        monkeypatch.setattr(main.urllib.request, "urlopen", Mock(return_value=Response([
            release("v6.1.0", body="wrong release"), release(body=body)])))
        found, failure = main.fetch_release()
        assert failure is None
        assert found["tag"] == "v6.2.0"
        assert found["notes_error"] == error
        assert found["body"] == ("" if body is None else None if error else body)


def test_historical_fetch_uses_exact_tag_without_an_asset(monkeypatch):
    http = Mock(return_value=Response({"tag_name": "v6.1.0", "body": "older notes"}))
    monkeypatch.setattr(main.urllib.request, "urlopen", http)
    assert main.fetch_release_notes("6.1.0") == ("older notes", None)
    assert http.call_args.args[0].full_url.endswith("/releases/tags/v6.1.0")
    assert http.call_args.kwargs["timeout"] == main.UPDATE_TIMEOUT_S


@pytest.mark.parametrize("payload,error", [
    ({"tag_name": "v6.2.0", "body": "wrong version"}, "bad_release_notes"),
    ({"tag_name": "v6.1.0", "body": "hidden", "draft": True}, "bad_release_notes"),
    ({"tag_name": "v6.1.0"}, "bad_release_notes"),
    ({"tag_name": "v6.1.0", "body": []}, "bad_release_notes"),
    ({"tag_name": "v6.1.0", "body": "x" * (notes.MAX_NOTES_BYTES + 1)}, "notes_too_large"),
    (b"not json", "bad_json"),
    (b"x" * (1024 * 1024 + 1), "notes_too_large"),
], ids=["wrong-tag", "draft", "missing-body", "bad-body", "large-body", "bad-json", "large-response"])
def test_fetch_rejects_wrong_version_and_malformed_notes(monkeypatch, payload, error):
    monkeypatch.setattr(main.urllib.request, "urlopen", Mock(return_value=Response(payload)))
    assert main.fetch_release_notes("v6.1.0") == (None, error)


@pytest.mark.parametrize("code,remaining,error", [(404, None, "http_404"), (429, None, "rate_limited"),
                                                  (403, "0", "rate_limited"), (403, "5", "http_403")])
def test_http_errors_remain_explicit(monkeypatch, code, remaining, error):
    headers = {} if remaining is None else {"X-RateLimit-Remaining": remaining}
    monkeypatch.setattr(main.urllib.request, "urlopen", Mock(side_effect=urllib.error.HTTPError(
        "https://example.invalid", code, "error", headers, None)))
    assert main.fetch_release_notes("v6.1.0") == (None, error)
    assert notes.notes_error_text(error)


def test_timeout_and_invalid_tag_never_fall_back_to_latest(monkeypatch):
    http = Mock(side_effect=urllib.error.URLError("timed out"))
    monkeypatch.setattr(main.urllib.request, "urlopen", http)
    body, error = main.fetch_release_notes("v6.1.0")
    assert body is None and error.startswith("net_")
    assert notes.notes_error_text(error) == main.trf("update_notes_failed", detail=main.tr("update_notes_network"))
    http.reset_mock()
    assert main.fetch_release_notes("../../latest") == (None, "bad_release_notes")
    http.assert_not_called()


def history_contract(path):
    history = notes.UpdateHistory(path)
    assert not path.exists()
    history.record_running("6.1.0")
    first_seen = history.installed[0]["first_seen"]
    history.remember_notes("v6.1.0", "installed notes")
    history.remember_notes("v6.2.0", "candidate notes")
    history.record_running("v6.1.0")
    reopened = notes.UpdateHistory(path)
    reopened.load()
    assert reopened.installed == [{"tag": "v6.1.0", "first_seen": first_seen}]
    assert reopened.notes["v6.2.0"] == "candidate notes"
    reopened.record_running("6.2.0")
    assert [entry["tag"] for entry in reopened.installed] == ["v6.2.0", "v6.1.0"]
    assert reopened.notes["v6.2.0"] == "candidate notes"


def test_history_records_running_versions_not_candidates_and_survives_restart(tmp_path):
    history_contract(tmp_path / "history.json")


def test_corrupt_history_is_visible_and_never_overwritten(tmp_path, controller):
    path = controller.history.path
    path.write_bytes(b"{broken original")
    controller.history.record_running("6.1.0")
    controller.prime("v6.1.0", "notes", None)
    assert path.read_bytes() == b"{broken original"
    dialog = notes.UpdateHistoryDialog(controller, "6.1.0")
    try:
        assert not dialog.storage_status.isHidden()
        assert main.trf("update_history_read_failed", detail=controller.history.read_error) == dialog.storage_status.text()
    finally:
        dialog.deleteLater()


def test_write_failure_visible_and_same_version_can_retry(monkeypatch, controller):
    original = notes.atomic_write_json
    monkeypatch.setattr(notes, "atomic_write_json", Mock(side_effect=PermissionError("read-only")))
    controller.history.record_running("6.1.0")
    controller.prime("6.1.0", "cached", None)
    dialog = notes.UpdateHistoryDialog(controller, "6.1.0")
    try:
        assert "read-only" in dialog.storage_status.text()
        assert not controller.history.path.exists()
        monkeypatch.setattr(notes, "atomic_write_json", original)
        controller.history.record_running("6.1.0")
        assert controller.history.write_error is None
        assert controller.history.path.exists()
    finally:
        dialog.deleteLater()


def test_bounded_history_keeps_only_installed_and_latest_candidate(tmp_path):
    history = notes.UpdateHistory(tmp_path / "history.json")
    for index in range(notes.MAX_VERSIONS + 3):
        history.record_running(f"1.0.{index}")
    history.remember_notes("v2.0.0", "old candidate")
    history.remember_notes("v2.1.0", "latest candidate")
    assert len(history.installed) == notes.MAX_VERSIONS
    assert "v2.0.0" not in history.notes
    assert history.notes["v2.1.0"] == "latest candidate"


def test_cache_budget_counts_json_escaping_and_keeps_file_readable(controller, monkeypatch):
    monkeypatch.setattr(notes, "MAX_HISTORY_BYTES", 200 * 1024)
    for tag in ("v1.0.0", "v2.0.0", "v3.0.0"):
        controller.history.record_running(tag)
        controller.history.remember_notes(tag, "\u0000" * (20 * 1024))
    assert controller.history.path.stat().st_size <= notes.MAX_HISTORY_BYTES
    reopened = notes.UpdateHistory(controller.history.path)
    reopened.load()
    assert reopened.read_error is None
    assert "v3.0.0" in reopened.notes and "v1.0.0" not in reopened.notes
    assert len(reopened.installed) == 3


def test_fold_is_lazy_error_empty_and_retry_are_distinct(controller):
    section = notes.ReleaseNotesSection(controller)
    try:
        section.set_tag("v6.1.0")
        assert not section.toggle.isChecked() and section.view.isHidden()
        controller.fetch.assert_not_called()
        controller.prime("v6.1.0", None, "http_404")
        section.toggle.click()
        assert "404" in section.view.status.text() and not section.view.retry.isHidden()
        controller.fetch.assert_not_called()
        section.view.retry.click()
        settle(controller)
        assert section.view.browser.toPlainText() == "fetched"
        controller.prime("v6.1.0", "", None)
        assert section.view.status.text() == main.tr("update_notes_empty")
        section.set_tag("v6.2.0")
        assert not section.toggle.isChecked() and section.view.isHidden()
        section.set_tag(None)
        assert section.isHidden()
    finally:
        section.deleteLater()


def test_offline_cache_reads_without_network_but_missing_version_is_explicit(controller):
    controller.history.record_running("6.1.0")
    controller.history.remember_notes("v6.1.0", "offline notes")
    controller.allowed = lambda: False
    dialog = notes.UpdateHistoryDialog(controller, "6.2.0")
    try:
        assert main.tr("update_notes_unavailable") in dialog.view.status.text()
        assert dialog.versions.count() == 2
        dialog.versions.setCurrentIndex(1)
        assert dialog.view.browser.toPlainText() == "offline notes"
        controller.fetch.assert_not_called()
        assert [item["tag"] for item in controller.history.installed] == ["v6.1.0"]
    finally:
        dialog.deleteLater()


def test_worker_is_background_and_late_response_never_replaces_selected_version(controller):
    entered, release_first = threading.Event(), threading.Event()
    calls = []
    def fetch(tag):
        calls.append((tag, QThread.currentThread()))
        if tag == "v1.0.0":
            entered.set()
            assert release_first.wait(3)
        return "notes for " + tag, None
    controller.fetch = fetch
    view = notes.NotesView(controller)
    try:
        view.select("v1.0.0")
        assert entered.wait(1)
        view.select("v2.0.0")
        view.select("v3.0.0")
        assert controller._worker.tag == "v1.0.0"
        release_first.set()
        settle(controller)
        assert [tag for tag, _ in calls] == ["v1.0.0", "v3.0.0"]
        assert all(thread is not QThread.currentThread() for _, thread in calls)
        assert view.browser.toPlainText() == "notes for v3.0.0"
        assert controller.state("v1.0.0") == ("notes for v1.0.0", None)
    finally:
        release_first.set()
        controller.stop()
        view.deleteLater()


def test_closing_dialog_does_not_destroy_worker_and_shutdown_discards_queued_result(controller):
    controller.fetch = lambda tag: ("late result", None)
    dialog = notes.UpdateHistoryDialog(controller, "1.0.0")
    worker = controller._worker
    assert worker is not None
    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    controller.stop()
    assert not worker.isRunning()
    QApplication.instance().processEvents()
    assert not controller.history.path.exists()


def test_markdown_blocks_html_and_resource_loading_and_unsafe_links(controller, monkeypatch):
    opened = Mock()
    monkeypatch.setattr(notes.QDesktopServices, "openUrl", opened)
    controller.prime("v1.0.0", '**safe** <b>RAW</b> ![image](file:///secret.png)', None)
    view = notes.NotesView(controller)
    try:
        view.select("v1.0.0")
        assert "<b>RAW</b>" in view.browser.toPlainText()
        assert not view.browser.openLinks() and not view.browser.openExternalLinks()
        assert not view.browser.loadResource(2, QUrl("file:///secret.png"))
        for url in ("file:///secret", "javascript:alert(1)", "ms-settings:privacy", "https:relative"):
            view.browser.anchorClicked.emit(QUrl(url))
        opened.assert_not_called()
        view.browser.anchorClicked.emit(QUrl("https://example.invalid/notes"))
        opened.assert_called_once()
    finally:
        view.deleteLater()


@pytest.fixture
def panel():
    panel = main.ControlPanel()
    panel.update_check_timer.stop()
    panel.timer.stop()
    panel.autosave_timer.stop()
    panel.apply_theme()
    yield panel
    from conftest import _dispose_offscreen_widgets
    _dispose_offscreen_widgets(QApplication.instance(), [panel])


def test_real_settings_keeps_known_release_on_error_and_clears_when_current(panel):
    panel.build_settings_panel()
    assert panel.btn_update_history.text() == main.tr("update_history")
    panel._on_update_result({"tag": "v99.0.0", "body": "# Specific notes"}, None)
    section = panel.update_notes_section
    assert section.tag == "v99.0.0" and not section.isHidden()
    assert not section.toggle.isChecked()
    section.toggle.click()
    assert section.view.browser.toPlainText() == "Specific notes"
    assert panel._release_notes.history.notes["v99.0.0"] == "# Specific notes"
    assert not panel._release_notes.history.installed
    panel._on_update_result(None, "network failure")
    assert not section.isHidden() and panel._pending_update_release['tag'] == 'v99.0.0'
    assert panel.btn_download_update.isEnabled()
    assert section.toggle.isChecked() and section.view.browser.toPlainText() == 'Specific notes'
    panel._on_update_result({"tag": "v99.0.0"}, None)
    assert main.tr("update_notes_bad_response") in section.view.status.text()
    panel._on_update_result({"tag": "v0.0.1", "body": "old"}, None)
    assert section.isHidden()


def test_history_button_opens_dialog_without_requiring_canvas(panel, monkeypatch):
    opened = []
    def execute(dialog):
        opened.append(dialog.windowTitle())
        assert not panel._release_notes_allowed() or panel.update_check_enabled
        return 0
    panel.update_check_enabled = False
    monkeypatch.setattr(notes.UpdateHistoryDialog, "exec", execute)
    panel.build_settings_panel()
    panel.btn_update_history.click()
    assert opened == [main.tr("update_history")]
    assert panel._release_notes._worker is None


def test_history_session_excludes_source_practice_and_duplicate_startup(tmp_path, monkeypatch):
    history = notes.UpdateHistory(tmp_path / "startup.json")
    panel = SimpleNamespace(runtime_context=SimpleNamespace(updates=True),
                            _release_notes=SimpleNamespace(history=history))
    monkeypatch.delattr(main.sys, "frozen", raising=False)
    main.ControlPanel.begin_update_history_session(panel)
    assert not history.path.exists()
    monkeypatch.setattr(main.sys, "frozen", True, raising=False)
    panel.runtime_context.updates = False
    main.ControlPanel.begin_update_history_session(panel)
    assert not history.path.exists()
    panel.runtime_context.updates = True
    main.ControlPanel.begin_update_history_session(panel)
    main.ControlPanel.begin_update_history_session(panel)
    assert [item["tag"] for item in history.installed] == [notes.version_tag(main.APP_VERSION)]
    startup = inspect.getsource(main)
    assert startup.index("QTimer.singleShot(0, acknowledge_update_startup)") < startup.index(
        "QTimer.singleShot(0, pnl.begin_update_history_session)")


def test_selected_cached_version_cancels_obsolete_waiting_request(controller):
    entered, release_first = threading.Event(), threading.Event()
    calls = []
    def fetch(tag):
        calls.append(tag)
        entered.set()
        assert release_first.wait(3)
        return tag, None
    controller.fetch = fetch
    controller.prime("v3.0.0", "cached third", None)
    try:
        controller.request("v1.0.0")
        assert entered.wait(1)
        controller.request("v2.0.0")
        controller.request("v3.0.0")
        release_first.set()
        settle(controller)
        assert calls == ["v1.0.0"]
    finally:
        release_first.set()
        controller.stop()


def test_runtime_guard_rechecked_when_notes_worker_finishes(controller):
    controller.fetch = lambda tag: ("must not cache", None)
    controller.request("v1.0.0")
    controller.allowed = lambda: False
    settle(controller)
    assert controller.state("v1.0.0") == (None, "notes_unavailable")
    assert not controller.history.path.exists()


def test_channel_change_hides_candidate_and_rejects_late_old_channel_result(panel, monkeypatch):
    panel.build_settings_panel()
    panel._on_update_result({"tag": "v99.0.0", "body": "old channel"}, None)
    old_channel = panel.update_channel
    index = panel.update_channel_combo.findData("preview" if old_channel == "stable" else "stable")
    monkeypatch.setattr(panel, "save_settings", Mock())
    panel.set_update_channel(index)
    assert panel._pending_update_release is None and panel.update_notes_section.isHidden()
    assert not panel.icon_buttons['settings']._update_indicator.available
    assert not panel.icon_buttons['settings'].accessibleDescription()
    worker = main.UpdateCheckWorker(old_channel, panel)
    monkeypatch.setattr(panel, "sender", lambda: worker)
    panel._on_update_result({"tag": "v99.0.1", "body": "obsolete reply"}, None)
    assert panel._pending_update_release is None and panel.update_notes_section.isHidden()
    assert not panel.icon_buttons['settings']._update_indicator.available


def test_opening_settings_preserves_already_detected_preview(panel, monkeypatch):
    panel.update_channel = "preview"
    panel._on_update_result({"tag": "v99.0.0-rc.1", "body": "preview notes"}, None)
    monkeypatch.setattr(panel, "save_settings", Mock())
    panel.build_settings_panel()
    panel.sync_settings_panel()
    assert panel._pending_update_release["tag"] == "v99.0.0-rc.1"
    assert panel.update_notes_section.tag == "v99.0.0-rc.1"
    assert panel.btn_download_update.isEnabled()


def test_malformed_unicode_is_a_notes_error_not_a_lost_update(monkeypatch, controller):
    http = Mock(return_value=Response([release(body="\ud800")]))
    monkeypatch.setattr(main.urllib.request, "urlopen", http)
    found, error = main.fetch_release()
    assert error is None and found["tag"] == "v6.2.0"
    assert found["notes_error"] == "bad_release_notes"
    controller.prime("v1.0.0", [], None)
    assert controller.state("v1.0.0") == (None, "bad_release_notes")


def mutated_method(method, old, new, namespace):
    source = textwrap.dedent(inspect.getsource(method))
    assert source.count(old) == 1
    source = source.replace(old, new)
    scope = dict(namespace)
    exec(compile(source, "<known-bad-notes>", "exec"), scope)
    return scope[method.__name__]


@pytest.mark.parametrize("case", ["wrong-tag", "oversize", "unsafe-html", "missing-fold-reset", "missing-runtime-guard"])
def test_notes_assertions_kill_known_bad_behaviors(case, controller, monkeypatch):
    if case == "wrong-tag":
        broken = mutated_method(main.fetch_release_notes,
            'or release.get("tag_name") != tag', 'or False', vars(main))
        monkeypatch.setattr(main, "fetch_release_notes", broken)
        with pytest.raises(AssertionError):
            test_fetch_rejects_wrong_version_and_malformed_notes(monkeypatch,
                {"tag_name": "v9.0.0", "body": "wrong"}, "bad_release_notes")
    elif case == "oversize":
        broken = mutated_method(notes.release_body, 'if size > MAX_NOTES_BYTES:', 'if False:', vars(notes))
        monkeypatch.setattr(main, "release_body", broken)
        with pytest.raises(AssertionError):
            test_fetch_rejects_wrong_version_and_malformed_notes(monkeypatch,
                {"tag_name": "v6.1.0", "body": "x" * (notes.MAX_NOTES_BYTES + 1)}, "notes_too_large")
    elif case == "unsafe-html":
        broken = mutated_method(notes.NotesView._refresh,
            'QTextDocument.MarkdownFeature.MarkdownNoHTML',
            'QTextDocument.MarkdownFeature.MarkdownDialectGitHub', vars(notes))
        monkeypatch.setattr(notes.NotesView, "_refresh", broken)
        with pytest.raises(AssertionError):
            test_markdown_blocks_html_and_resource_loading_and_unsafe_links(controller, monkeypatch)
    elif case == "missing-fold-reset":
        broken = mutated_method(notes.ReleaseNotesSection.set_tag,
            'self.toggle.setChecked(False)', 'pass', vars(notes))
        monkeypatch.setattr(notes.ReleaseNotesSection, "set_tag", broken)
        with pytest.raises(AssertionError):
            test_fold_is_lazy_error_empty_and_retry_are_distinct(controller)
    else:
        broken = mutated_method(notes.NotesController._received,
            'if not self.allowed():', 'if False:', vars(notes))
        monkeypatch.setattr(notes.NotesController, "_received", broken)
        with pytest.raises(AssertionError):
            test_runtime_guard_rechecked_when_notes_worker_finishes(controller)


def test_history_assertions_reject_missing_persistence(tmp_path, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(notes.UpdateHistory, "_save", lambda self: None)
        with pytest.raises(AssertionError):
            history_contract(tmp_path / "missing.json")


def test_version_selection_assertion_rejects_late_response_mutation(controller, monkeypatch):
    controller.prime("v1.0.0", "first", None)
    controller.prime("v2.0.0", "second", None)
    view = notes.NotesView(controller)
    try:
        view.select("v2.0.0")
        broken = mutated_method(notes.NotesView._refresh, 'if tag != self.tag or not tag:',
                                'if not tag:', vars(notes))
        with monkeypatch.context() as patch:
            patch.setattr(notes.NotesView, "_refresh", broken)
            with pytest.raises(AssertionError):
                view._refresh("v1.0.0")
                assert view.browser.toPlainText() == "second"
    finally:
        view.deleteLater()


def test_integration_assertion_rejects_old_result_without_notes(panel, monkeypatch):
    panel.build_settings_panel()
    broken = mutated_method(main.ControlPanel._on_update_result,
        'self._release_notes.prime(tag, body, release.get("notes_error") or notes_error)',
        'pass', vars(main))
    with monkeypatch.context() as patch:
        patch.setattr(main.ControlPanel, "_on_update_result", broken)
        with pytest.raises(AssertionError):
            panel._on_update_result({"tag": "v98.0.1", "body": "must cache"}, None)
            assert panel._release_notes.state("v98.0.1") == ("must cache", None)
