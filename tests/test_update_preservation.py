# SPDX-License-Identifier: GPL-3.0-or-later
"""Real PowerShell file transactions, not EXE startup/real-package evidence.

Only tiny temporary fixtures are used. The generated script's single Start-Process
is replaced with a log marker; no application or desktop UI is launched. Faults
wrap native Move-Item, including real FileShare.None locks, rather than mocking
Python's updater result. Run on Windows: python -m pytest tests/test_update_preservation.py -q
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell transaction")


def ps_literal(path):
    return "'" + str(path).replace("'", "''") + "'"


@pytest.fixture
def transaction(tmp_path, monkeypatch, request):
    # Spaces, Unicode, wildcard metacharacters and apostrophes must remain literal.
    install = tmp_path / getattr(request, "param", "install 教室's")
    install.mkdir()
    old = {"MyScreenDraw.exe": b"old executable", "a.dll": b"old library",
           "_internal/shared.dll": b"old dependency"}
    private = {"lesson.txt": b"private root note", "old.dll": b"unmanaged old library",
               "lessons/[1].txt": b"private folder", "_internal/local.txt": b"local add-on",
               "data/config.json": b'{"keep":true}', "data/autosave/page.json": b"ink",
               "data/roster.csv": b"names", "exports/page.png": b"export"}
    payload = {"MyScreenDraw.exe": b"new non-executable fixture", "a.dll": b"new library",
               "_internal/shared.dll": b"new dependency", "z-last.dll": b"new last file",
               "data/config.json": b"DO NOT INSTALL", "exports/page.png": b"DO NOT INSTALL"}
    for name, content in {**old, **private}.items():
        target = install / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    archive = tmp_path / "update.zip"
    def package(wrapped=False):
        with zipfile.ZipFile(archive, "w") as z:
            for name, content in payload.items():
                z.writestr(("MyScreenDraw/" if wrapped else "") + name, content)
    package()
    original_mkdtemp = tempfile.mkdtemp
    with monkeypatch.context() as patch:
        patch.setattr(main.tempfile, "mkdtemp", lambda **kw: original_mkdtemp(dir=tmp_path, **kw))
        script = Path(main.make_update_batch(str(archive), str(install)))
    assert script.resolve().is_relative_to(tmp_path.resolve())
    text = script.read_text(encoding="utf-8-sig")
    calls = re.findall(r"(?m)^    Start-Process -FilePath.*$", text)
    assert len(calls) == 1, "The test must replace exactly one interactive application launch"
    marker = "    Set-Content -LiteralPath (Join-Path $install 'launch-marker.txt') -Value 'transaction-only'"
    text = text.replace(calls[0], marker)

    def run(fault="", setup="", transform=None):
        script.write_text(setup + fault + (transform(text) if transform else text), encoding="utf-8-sig")
        process = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script)],
            capture_output=True, timeout=40,
        )
        result_path = install / "data/update-result.json"
        result = json.loads(result_path.read_text(encoding="utf-8-sig")) if result_path.exists() else None
        return process, result

    return install, archive, old, private, payload, package, run


def assert_files(install, files):
    for name, content in files.items():
        assert (install / name).is_file(), name
        assert (install / name).read_bytes() == content, name


def move_fault(body):
    # CmdletBinding supplies common parameters (including ErrorAction) for forwarding.
    return r"""
function Move-Item {
    [CmdletBinding()] param([string]$LiteralPath, [string]$Destination)
""" + body + r"""
    Microsoft.PowerShell.Management\Move-Item @PSBoundParameters
}
"""


@pytest.mark.parametrize("transaction", ["install 教室's", "install [class] 教室's"], indirect=True)
@pytest.mark.parametrize("wrapped", [False, True])
def test_success_replaces_only_payload_conflicts(transaction, wrapped):
    install, _, old, private, payload, package, run = transaction
    package(wrapped)
    process, result = run()
    assert process.returncode == 0, (result, process.stderr.decode(errors="replace"))
    assert result["status"] == "success"
    assert_files(install, private)
    assert_files(install, {k: v for k, v in payload.items() if k.split("/")[0] not in ("data", "exports")})
    assert (install / "launch-marker.txt").read_text().strip() == "transaction-only"
    assert not list(install.glob(".msd-update-*"))


@pytest.mark.parametrize("phase", ["backup", "incoming", "incoming_locked"])
def test_move_failure_restores_old_and_preserves_user_files(transaction, phase):
    install, _, old, private, _, _, run = transaction
    if phase == "backup":
        fault = move_fault(r"""
    if ($Destination -match '\\backup(?:\\|$)') {
        $script:backupMoves++
        if ($script:backupMoves -eq 2) { throw 'fixture_partial_backup_failure' }
    }
""")
    else:
        action = "throw 'fixture_incoming_failure'" if phase == "incoming" else """
        $script:heldIncoming = [IO.File]::Open($LiteralPath, 'Open', 'Read', 'None')
"""
        fault = move_fault(r"""
    if ($LiteralPath -match '\\stage\\' -and (Split-Path -Leaf $LiteralPath) -eq 'z-last.dll') {
""" + action + """
    }
""")
    process, result = run(fault)
    assert process.returncode != 0
    assert result["status"] == "failed"
    assert "rollback_failed" not in result["detail"]
    assert_files(install, {**old, **private})
    assert not (install / "z-last.dll").exists()
    assert not (install / "launch-marker.txt").exists()


def test_locked_rollback_retains_backup_and_restores_other_entries(transaction):
    install, _, old, private, _, _, run = transaction
    fault = move_fault(r"""
    if ($LiteralPath -match '\\stage\\' -and (Split-Path -Leaf $LiteralPath) -eq 'z-last.dll') {
        $script:heldInstalled = [IO.File]::Open((Join-Path $install 'MyScreenDraw.exe'), 'Open', 'Read', 'None')
        throw 'fixture_incoming_failure_with_locked_rollback'
    }
""")
    process, result = run(fault)
    assert process.returncode != 0
    assert result["status"] == "failed" and "rollback_failed" in result["detail"]
    assert_files(install, private)
    assert_files(install, {k: v for k, v in old.items() if k != "MyScreenDraw.exe"})
    backup = Path(result["backup"])
    assert backup.resolve().is_relative_to(install.resolve())
    assert (backup / "MyScreenDraw.exe").read_bytes() == old["MyScreenDraw.exe"]
    assert not (install / "launch-marker.txt").exists()


def test_backup_move_that_succeeds_then_throws_is_still_rolled_back(transaction):
    install, _, old, private, _, _, run = transaction
    fault = move_fault(r"""
    if ($Destination -match '\\backup(?:\\|$)' -and -not $script:failedAfterMove) {
        $script:failedAfterMove = $true
        Microsoft.PowerShell.Management\Move-Item @PSBoundParameters
        throw 'fixture_error_after_backup_move'
    }
""")
    process, result = run(fault)
    assert process.returncode != 0 and result["status"] == "failed"
    assert_files(install, {**old, **private})


@pytest.mark.parametrize("location", ["payload_target", "private_directory", "data_directory", "stage"])
def test_reparse_points_are_rejected_without_touching_referent(transaction, tmp_path, location):
    install, _, old, private, _, _, run = transaction
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_bytes(b"outside sentinel")
    if location == "stage":
        setup = r"""
function Expand-Archive {
    [CmdletBinding()] param([string]$LiteralPath, [string]$DestinationPath, [switch]$Force)
    Microsoft.PowerShell.Archive\Expand-Archive @PSBoundParameters
    New-Item -ItemType Junction -Path (Join-Path $DestinationPath 'linked') -Target """ + ps_literal(outside) + """ | Out-Null
}
"""
    else:
        link = install / {"payload_target": "z-last.dll", "private_directory": "linked", "data_directory": "data/link"}[location]
        created = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                                  f"New-Item -ItemType Junction -Path {ps_literal(link)} -Target {ps_literal(outside)} | Out-Null"],
                                 capture_output=True, timeout=15)
        assert created.returncode == 0, created.stderr
        setup = ""
    process, result = run(setup=setup)
    assert process.returncode != 0
    assert (outside / "keep.txt").read_bytes() == b"outside sentinel"
    assert_files(install, {**old, **private})
    assert not (outside / "update-result.json").exists()
    assert not (install / "launch-marker.txt").exists()
    # Remove junctions without traversing them, before pytest removes the fixture tree.
    for link in [*install.rglob("linked"), install / "z-last.dll", install / "data/link"]:
        if link.exists() and (link.lstat().st_file_attributes & 0x400):
            assert link.absolute().is_relative_to(tmp_path.absolute())
            os.rmdir(link)


@pytest.mark.parametrize("fail", [False, True])
def test_file_directory_conflicts_are_replaced_or_restored(transaction, fail):
    install, _, old, private, payload, package, run = transaction
    (install / "folder-replaces-file").write_bytes(b"old file")
    (install / "file-replaces-folder").mkdir()
    (install / "file-replaces-folder/old.txt").write_bytes(b"old nested file")
    payload["folder-replaces-file/new.txt"] = b"new nested file"
    payload["file-replaces-folder"] = b"new file"
    package()
    fault = move_fault(r"""
    if ($LiteralPath -match '\\stage\\' -and (Split-Path -Leaf $LiteralPath) -eq 'z-last.dll') {
        throw 'fixture_incoming_failure'
    }
""") if fail else ""
    process, result = run(fault)
    assert_files(install, private)
    if fail:
        assert process.returncode != 0 and result["status"] == "failed"
        assert_files(install, old)
        assert (install / "folder-replaces-file").read_bytes() == b"old file"
        assert (install / "file-replaces-folder/old.txt").read_bytes() == b"old nested file"
    else:
        assert process.returncode == 0 and result["status"] == "success"
        assert (install / "folder-replaces-file/new.txt").read_bytes() == b"new nested file"
        assert (install / "file-replaces-folder").read_bytes() == b"new file"


def test_incoming_move_that_succeeds_then_throws_is_still_rolled_back(transaction):
    install, _, old, private, _, _, run = transaction
    fault = move_fault(r"""
    if ($LiteralPath -match '\\stage\\' -and -not $script:failedAfterMove) {
        $script:failedAfterMove = $true
        Microsoft.PowerShell.Management\Move-Item @PSBoundParameters
        throw 'fixture_error_after_incoming_move'
    }
""")
    process, result = run(fault)
    assert process.returncode != 0 and result["status"] == "failed"
    assert_files(install, {**old, **private})


def test_success_does_not_move_locked_unrelated_file(transaction):
    install, _, _, private, _, _, run = transaction
    setup = "$heldPrivate = [IO.File]::Open(" + ps_literal(install / "lesson.txt") + ", 'Open', 'Read', 'None')\n"
    process, result = run(setup=setup)
    assert process.returncode == 0 and result["status"] == "success"
    assert_files(install, private)


@pytest.mark.parametrize("operation", ["remove_sibling", "remove_owner", "move_source", "move_destination"])
def test_containment_rejects_escape_before_file_operations(transaction, operation):
    install, _, old, private, _, _, run = transaction
    sibling = install.with_name(install.name + "-outside")
    sibling.mkdir()
    sentinel = sibling / "keep.txt"
    sentinel.write_bytes(b"outside fixture file")
    # Keep every attempted target inside the explicit test workspace even if a guard regresses.
    assert sibling.resolve().is_relative_to(install.parent.resolve())
    commands = {
        "remove_sibling": "Remove-Checked " + ps_literal(install / ".." / sibling.name) + " $install",
        "remove_owner": "Remove-Checked $install $install",
        "move_source": "Move-Checked " + ps_literal(sentinel) + " (Join-Path $install 'unexpected.txt') $install $install",
        "move_destination": "Move-Checked (Join-Path $install 'lesson.txt') " + ps_literal(sibling / "unexpected.txt") + " $install $install",
    }
    def only_guard(text):
        helpers, _ = text.split("try {\n    $install = Assert-Path", 1)
        return helpers + "\ntry {\n" + commands[operation] + "\n} catch { if ($_.Exception.Message -eq 'path_outside_owner') { exit 7 }; throw }\nexit 0\n"
    process, _ = run(transform=only_guard)
    assert process.returncode == 7, process.stderr.decode(errors="replace")
    assert_files(install, {**old, **private})
    assert sentinel.read_bytes() == b"outside fixture file"
    assert not (sibling / "unexpected.txt").exists()


def test_install_root_junction_is_rejected(transaction):
    install, _, old, private, _, _, run = transaction
    alias = install.with_name("install-alias")
    setup = "New-Item -ItemType Junction -Path " + ps_literal(alias) + " -Target " + ps_literal(install) + " | Out-Null\n"
    def alias_install(text):
        return re.sub(r"(?m)^\$install = .*", lambda _: "$install = " + ps_literal(alias), text, count=1)
    try:
        process, _ = run(setup=setup, transform=alias_install)
        assert process.returncode != 0
        assert_files(install, {**old, **private})
        assert not (install / "launch-marker.txt").exists()
        assert not (install / "data/update-result.json").exists()
    finally:
        if alias.exists():
            assert alias.absolute().is_relative_to(install.parent.absolute())
            os.rmdir(alias)  # Remove only the junction, never the referenced tree.
