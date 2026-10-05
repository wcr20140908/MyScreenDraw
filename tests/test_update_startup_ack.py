# SPDX-License-Identifier: GPL-3.0-or-later
"""Startup-ready acknowledgement contracts without windows or subprocesses.

All candidate destinations, including rejected external paths and link targets,
are temporary fixtures. The real helper is called directly like its timer callback.
"""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main


READY_ENV = "MYSCREENDRAW_UPDATE_READY"
TRANSACTION = ".msd-update-" + "a1" * 16


@pytest.fixture
def startup(tmp_path, monkeypatch):
    install = tmp_path / "portable 教室's"
    install.mkdir()
    executable = install / "MyScreenDraw.exe"
    executable.write_bytes(b"fixture only: never executed")
    folder = install / TRANSACTION
    folder.mkdir()
    monkeypatch.setattr(main, "APP_DIR", str(install))
    monkeypatch.setattr(main.sys, "executable", str(executable))
    monkeypatch.setattr(main.sys, "frozen", True, raising=False)
    monkeypatch.delenv(READY_ENV, raising=False)
    return SimpleNamespace(install=install, executable=executable, folder=folder,
                           ready=folder / "ready.json", root=tmp_path)


def acknowledge():
    helper = getattr(main, "acknowledge_update_startup", None)
    assert callable(helper), "The first-event-loop startup acknowledgement helper is required"
    return helper()


def test_no_environment_does_not_write_ready(startup):
    acknowledge()
    assert not startup.ready.exists()
    assert list(startup.folder.iterdir()) == []
    assert startup.executable.read_bytes() == b"fixture only: never executed"


def test_frozen_startup_writes_identity_and_consumes_environment(startup, monkeypatch):
    monkeypatch.setenv(READY_ENV, str(startup.ready))
    callback = lambda: acknowledge()
    callback()  # Exercise callback semantics, without a Qt event loop or window.
    assert READY_ENV not in os.environ
    data = json.loads(startup.ready.read_text(encoding="utf-8"))
    assert data["version"] == main.APP_VERSION
    assert data["executable"] == str(startup.executable)
    assert data["pid"] == os.getpid()
    assert isinstance(data["pid"], int)
    assert set(startup.folder.iterdir()) == {startup.ready}, "Atomic-write temporary files must not leak"

    startup.ready.write_bytes(b"already acknowledged; do not overwrite on a later callback")
    callback()
    assert startup.ready.read_bytes() == b"already acknowledged; do not overwrite on a later callback"


@pytest.mark.parametrize("frozen", [False, None], ids=["not-frozen", "no-frozen-attribute"])
def test_source_process_does_not_acknowledge_portable_startup(startup, monkeypatch, frozen):
    monkeypatch.setenv(READY_ENV, str(startup.ready))
    if frozen is None:
        monkeypatch.delattr(main.sys, "frozen")
    else:
        monkeypatch.setattr(main.sys, "frozen", frozen)
    acknowledge()
    assert not startup.ready.exists()
    assert list(startup.folder.iterdir()) == []
    assert READY_ENV not in os.environ


@pytest.mark.parametrize("location", [
    "outside-install", "sibling-prefix", "wrong-filename", "not-transaction",
    "malformed-transaction", "nested-transaction",
])
def test_rejected_path_does_not_modify_existing_files(startup, monkeypatch, location):
    if location == "outside-install":
        ready = startup.root / "outside" / TRANSACTION / "ready.json"
    elif location == "sibling-prefix":
        ready = startup.install.with_name(startup.install.name + "-other") / TRANSACTION / "ready.json"
    elif location == "wrong-filename":
        ready = startup.folder / "something-else.json"
    elif location == "not-transaction":
        ready = startup.install / "data" / "ready.json"
    elif location == "malformed-transaction":
        ready = startup.install / ".msd-update-not-a-guid" / "ready.json"
    else:
        ready = startup.install / "nested" / TRANSACTION / "ready.json"
    ready.parent.mkdir(parents=True, exist_ok=True)
    sentinel = ready.parent / "keep.txt"
    sentinel.write_bytes(b"unrelated content")
    ready.write_bytes(b"existing destination must not be overwritten")
    before = {path.name: path.read_bytes() for path in ready.parent.iterdir()}
    monkeypatch.setenv(READY_ENV, str(ready))

    acknowledge()

    assert {path.name: path.read_bytes() for path in ready.parent.iterdir()} == before
    assert READY_ENV not in os.environ
    assert not startup.ready.exists()


def test_nonexistent_transaction_directory_is_not_created(startup, monkeypatch):
    ready = startup.install / (".msd-update-" + "b2" * 16) / "ready.json"
    monkeypatch.setenv(READY_ENV, str(ready))
    acknowledge()
    assert not ready.parent.exists()
    assert READY_ENV not in os.environ


@pytest.fixture
def directory_links(tmp_path):
    """Use real Windows junctions without elevation, a shell, or a child process."""
    links = []

    def create(link, target):
        assert link.absolute().is_relative_to(tmp_path.absolute())
        assert target.resolve().is_relative_to(tmp_path.resolve())
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
        else:
            link.symlink_to(target, target_is_directory=True)
        links.append(link)
        return link

    yield create
    for link in reversed(links):
        assert link.absolute().is_relative_to(tmp_path.absolute())
        if os.name == "nt":
            os.rmdir(link)  # Remove the junction itself; never recursively traverse its target.
        else:
            link.unlink()


@pytest.mark.parametrize("location", ["transaction", "install-root", "ready-entry"])
def test_reparse_paths_are_rejected_without_touching_target(startup, monkeypatch, directory_links, location):
    outside = startup.root / "outside-link-target"
    outside.mkdir()
    (outside / "keep.txt").write_bytes(b"outside sentinel")
    (outside / "ready.json").write_bytes(b"outside ready sentinel")
    before = {path.name: path.read_bytes() for path in outside.iterdir()}

    if location == "transaction":
        link = startup.install / (".msd-update-" + "c3" * 16)
        directory_links(link, outside)
        ready = link / "ready.json"
    elif location == "install-root":
        alias = directory_links(startup.root / "install-alias", startup.install)
        monkeypatch.setattr(main, "APP_DIR", str(alias))
        monkeypatch.setattr(main.sys, "executable", str(alias / "MyScreenDraw.exe"))
        ready = alias / TRANSACTION / "ready.json"
    else:
        ready = directory_links(startup.ready, outside)
    monkeypatch.setenv(READY_ENV, str(ready))

    acknowledge()

    assert {path.name: path.read_bytes() for path in outside.iterdir()} == before
    assert not list(startup.folder.glob(".ready-*"))
    if location != "ready-entry":
        assert not startup.ready.exists()
    assert READY_ENV not in os.environ


def test_ready_callback_registered_before_optional_recovery_dialog():
    source = Path(main.__file__).read_text(encoding="utf-8")
    startup = source[source.rfind('if __name__ == "__main__":'):]
    assert startup.index("QTimer.singleShot(0, acknowledge_update_startup)") < startup.index("pnl.offer_autosave_restore()")
