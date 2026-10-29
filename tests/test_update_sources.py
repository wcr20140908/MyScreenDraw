# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline dual-source and signed-content regressions with synthetic packages."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
import base64
import hashlib
import io
import json
import threading
import time
from unittest.mock import Mock
import zipfile
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import main
import update_sources as sources
import update_notes as notes
from test_update_notes import panel, no_external_effects, settle


class Response(io.BytesIO):
    def __init__(self, value, length=None):
        super().__init__(json.dumps(value).encode() if isinstance(value, (dict, list)) else value)
        self.headers = {"Content-Length": str(length)} if length is not None else {}
    def geturl(self):
        return "https://file-cdn.gitcode.com/synthetic"


@pytest.fixture
def signed(monkeypatch):
    key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(sources, "PUBLIC_KEY", base64.b64encode(key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode())
    def sign(tag="v6.3.0", **changes):
        manifest = dict(schema=1, tag=tag, version=tag[1:], asset_name=f"MyScreenDraw-{tag}-windows-x64.zip",
                        size=123, sha256="a" * 64, exe_sha256="b" * 64, commit="c" * 40)
        manifest.update(changes)
        return manifest, json.dumps(dict(manifest=manifest, signature=base64.b64encode(
            key.sign(sources.canonical_manifest(manifest))).decode())).encode()
    return sign


def release(source, tag="v6.3.0", size=123):
    names = [f"MyScreenDraw-{tag}-windows-x64.zip", sources.descriptor_name(tag)]
    return dict(tag_name=tag, prerelease=bool("-" in tag), body="notes", assets=[dict(name=name,
        type="attach", size=size, browser_download_url=f"https://{source}.com/wcr20140908/MyScreenDraw/releases/download/{tag}/{name}")
        for name in names])


@pytest.mark.parametrize("source", ["github", "gitcode"])
@pytest.mark.parametrize("channel,tag", [("stable", "v6.3.0"), ("preview", "v6.3.1-beta.1")])
def test_signed_source_check_uses_anonymous_correct_api(monkeypatch, signed, source, channel, tag):
    manifest, raw = signed(tag)
    calls = []
    def open_url(request, **kwargs):
        calls.append(request)
        assert not request.has_header("Authorization")
        return Response([release(source, tag)]) if len(calls) == 1 else Response(raw)
    monkeypatch.setattr(main.urllib.request, "urlopen", open_url)
    result, error = main.fetch_release(channel, source=source)
    assert error is None and result["integrity"] == manifest and result["source"] == source
    assert calls[0].full_url == sources.releases_url(source)
    assert calls[1].full_url == sources.download_url(source, tag, sources.descriptor_name(tag))
    assert result["download_url"] == sources.download_url(source, tag, result["asset_name"])


@pytest.mark.parametrize("source", ["github", "gitcode"])
def test_new_release_without_signed_descriptor_fails_closed(monkeypatch, source):
    value = release(source)
    value["assets"].pop()
    monkeypatch.setattr(main.urllib.request, "urlopen", lambda *a, **k: Response([value]))
    assert main.fetch_release(source=source) == (None, "missing_update_signature")


def test_gitcode_source_archive_cannot_become_update(monkeypatch):
    value = release("gitcode")
    value["assets"][0]["type"] = "source"
    monkeypatch.setattr(main.urllib.request, "urlopen", lambda *a, **k: Response([value]))
    assert main.fetch_release(source="gitcode") == (None, "no_release")


@pytest.mark.parametrize("field,value", [("tag", "v6.3.1"), ("version", "9.0.0"),
    ("asset_name", "source.zip"), ("size", 0), ("size", True), ("size", sources.MAX_ARCHIVE_BYTES+1),
    ("sha256", "INVALID"), ("exe_sha256", "INVALID"), ("commit", "INVALID")])
def test_signed_but_wrong_descriptor_rejected(signed, field, value):
    _, raw = signed(**{field: value}) if field != "tag" else signed(value)
    with pytest.raises(ValueError, match="invalid_update_descriptor"):
        sources.verify_descriptor(raw, "v6.3.0", "MyScreenDraw-v6.3.0-windows-x64.zip")


def test_descriptor_tamper_and_untrusted_key_rejected(signed):
    _, raw = signed()
    modified = json.loads(raw)
    modified["manifest"]["sha256"] = "d" * 64
    with pytest.raises(ValueError, match="signature"):
        sources.verify_descriptor(json.dumps(modified).encode(), "v6.3.0", "MyScreenDraw-v6.3.0-windows-x64.zip")
    with pytest.raises(ValueError, match="descriptor_too_large"):
        sources.verify_descriptor(b" " * (sources.MAX_DESCRIPTOR_BYTES + 1), "v6.3.0", "x")


@pytest.mark.parametrize("url", ["https://gitcode.com.evil/wcr20140908/MyScreenDraw/releases/download/v6.3.0/a.zip",
    "http://gitcode.com/wcr20140908/MyScreenDraw/releases/download/v6.3.0/a.zip",
    "https://gitcode.com:443/wcr20140908/MyScreenDraw/releases/download/v6.3.0/a.zip",
    "https://gitcode.com/wcr20140908/MyScreenDraw/releases/download/v6.3.0/a.zip?token=bad",
    "https://gitcode.com/wcr20140908/MyScreenDraw/releases/download/v6.3.1/a.zip",
    "https://u@gitcode.com/wcr20140908/MyScreenDraw/releases/download/v6.3.0/a.zip"])
def test_asset_origin_is_exact(url):
    assert not sources.official_asset_url(url, "v6.3.0", "a.zip", "gitcode")


@pytest.mark.parametrize("mutation", ["valid", "hash", "truncated", "oversized", "header"])
def test_streaming_download_checks_signed_bytes_and_cleans_failure(monkeypatch, tmp_path, mutation):
    payload = b"synthetic-update-bytes"
    expected = dict(size=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    actual = payload if mutation in ("valid", "header") else payload[:-1] if mutation == "truncated" else payload+b"!" if mutation == "oversized" else b"x"*len(payload)
    monkeypatch.setattr(main.tempfile, "mkdtemp", lambda **kwargs: str(tmp_path / "download"))
    (tmp_path / "download").mkdir()
    monkeypatch.setattr(main.urllib.request, "urlopen", lambda *a, **k: Response(actual, len(payload)+1 if mutation == "header" else None))
    worker = main.UpdateDownloadWorker("https://example.invalid/test", integrity=expected)
    results = []
    worker.finished_download.connect(lambda path, error: results.append((path, error)))
    worker.run()
    if mutation == "valid":
        assert results[0][1] is None and (tmp_path / "download/update.zip").read_bytes() == payload
    else:
        assert results[0][0] is None and results[0][1] and not (tmp_path / "download").exists()


def test_source_preference_invalidates_candidate_and_old_response(panel, monkeypatch):
    panel.build_settings_panel()
    panel._on_update_result(dict(tag="v99.0.0", source="github", body="foreign notes"), None)
    monkeypatch.setattr(panel, "save_settings", Mock())
    old = main.UpdateCheckWorker("stable", panel, source="github")
    panel.set_update_source(panel.update_source_combo.findData("gitcode"))
    assert panel.update_source == "gitcode"
    assert panel._pending_update_release is None and panel.update_notes_section.isHidden()
    assert not panel.icon_buttons["settings"]._update_indicator.available
    monkeypatch.setattr(panel, "sender", lambda: old)
    panel._on_update_result(dict(tag="v99.0.1", source="github", body="stale"), None)
    assert panel._pending_update_release is None


def test_source_cannot_change_during_download(panel, monkeypatch):
    panel.build_settings_panel()
    panel._update_download_active = True
    panel.update_source_combo.setCurrentIndex(panel.update_source_combo.findData("gitcode"))
    assert panel.update_source == "github" and panel.update_source_combo.currentData() == "github"
    panel._update_download_active = False


def test_notes_cache_source_scope_and_late_reply(tmp_path):
    first = threading.Event()
    controller = notes.NotesController(tmp_path / "history.json", lambda tag: (first.wait(3) and "foreign", None), lambda: True)
    controller.history.record_running("6.3.0")
    try:
        controller.request("v6.3.0")
        controller.set_source("gitcode", lambda tag: ("domestic", None))
        first.set()
        settle(controller, timeout=5)
        assert controller.state("v6.3.0") == ("domestic", None)
        assert controller.history.notes["v6.3.0"] == "foreign"
        assert controller.history.notes["gitcode:v6.3.0"] == "domestic"
        loaded = notes.UpdateHistory(tmp_path / "history.json")
        loaded.load()
        assert loaded.notes == controller.history.notes and len(loaded.installed) == 1
    finally:
        first.set()
        controller.stop()


def test_notes_source_switch_waits_for_both_delayed_workers(tmp_path, monkeypatch):
    original_run = notes.NotesWorker.run

    def delayed_run(worker):
        time.sleep(1.6)
        original_run(worker)

    monkeypatch.setattr(notes.NotesWorker, "run", delayed_run)
    test_notes_cache_source_scope_and_late_reply(tmp_path)


@pytest.mark.parametrize("mutation", ["valid", "version", "hash", "exe"])
def test_local_package_manifest_bound_to_descriptor(tmp_path, mutation):
    exe = b"synthetic exe"
    exe_hash = hashlib.sha256(exe).hexdigest()
    integrity = dict(version="6.3.0", exe_sha256=exe_hash)
    path = tmp_path / "package.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("RELEASE-MANIFEST.json", json.dumps(dict(app_version="9.0.0" if mutation=="version" else "6.3.0",
            sha256="a"*64 if mutation=="hash" else exe_hash)))
        archive.writestr("MyScreenDraw.exe", b"changed exe" if mutation=="exe" else exe)
    if mutation=="valid":
        sources.verify_downloaded_manifest(path, integrity)
    else:
        with pytest.raises(ValueError, match="package_(manifest|exe)_mismatch"):
            sources.verify_downloaded_manifest(path, integrity)


def test_gitcode_release_upload_preserves_provider_signed_headers(monkeypatch, tmp_path):
    import publish_release as publisher
    path = tmp_path / "test.zip"
    path.write_bytes(b"accepted synthetic bytes")
    calls = []
    monkeypatch.setattr(publisher, "api", lambda *a, **k: dict(url="https://file.gitcode.com/synthetic-upload",
        headers={"Content-Type":"application/octet-stream", "x-obs-acl":"public-read"}))
    def upload(url, **kwargs):
        calls.append((url, kwargs["headers"], kwargs["data"].read()))
    monkeypatch.setattr(publisher,"request",upload)
    publisher.upload("gitcode", {"assets":[]}, "v6.3.0", path)
    assert calls[0][1]["Content-Type"]=="application/octet-stream"
    assert int(calls[0][1]["Content-Length"])==path.stat().st_size
    assert calls[0][2]==path.read_bytes()


@pytest.mark.parametrize("source,channel", [("github", "preview"), ("gitcode", "stable")])
def test_obsolete_worker_is_rejected_before_teaching_deferral(panel, monkeypatch, source, channel):
    panel.build_settings_panel()
    worker = main.UpdateCheckWorker(channel, panel, source=source)
    monkeypatch.setattr(panel, "sender", lambda: worker)
    monkeypatch.setattr(main, "update_work_is_blocked", lambda panel: True)
    panel._on_update_result({"tag":"v99.0.0-beta.1", "source":source}, None)
    assert getattr(panel, "_teaching_deferred_update_result", None) is None


@pytest.mark.parametrize("selection", ["source", "channel"])
def test_scheduled_teaching_reply_does_not_restore_after_selection_change(panel, monkeypatch, selection):
    from PyQt6.QtTest import QTest
    panel.build_settings_panel()
    monkeypatch.setattr(panel, "save_settings", Mock())
    monkeypatch.setattr(main, "teaching_blocks_updates", lambda panel: False)
    monkeypatch.setattr(main, "update_work_is_blocked", lambda panel: False)
    panel._teaching_deferred_update_result = (None, "obsolete_route_error")
    panel._resume_teaching_updates()
    if selection=="source":
        panel.set_update_source(panel.update_source_combo.findData("gitcode"))
    else:
        panel.set_update_channel(panel.update_channel_combo.findData("preview"))
    QTest.qWait(10)
    assert panel._update_status_text == ""
    assert panel._pending_update_release is None
