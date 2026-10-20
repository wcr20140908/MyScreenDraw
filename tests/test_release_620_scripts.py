# SPDX-License-Identifier: GPL-3.0-or-later
"""6.2 release gates using synthetic files only: no build, EXE, network or real data."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

import pytest

import release_artifact as artifact
from test_release_artifact import fake_pe
from version import VERSION

ROOT = Path(__file__).resolve().parents[1]
TUTORIAL = "_internal/assets/tutorials/"


@pytest.fixture
def release_tree(tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()
    for name in artifact.SOURCE_REQUIRED:
        (root / name).write_text("synthetic release input\n", encoding="utf-8")
    (root / "build").mkdir()
    files = {
        "teaching/__init__.py": b"# synthetic package\n",
        "teaching/nested/worker.py": b"VALUE = 1\n",
        "assets/tutorials/catalog.json": b'{"schema_version":1,"courses":["courses/c01.json"]}',
        "assets/tutorials/courses/c01.json": b'{"id":"c01"}',
        "assets/tutorials/fixtures/media-c09-sample.png": b"synthetic bundled image",
        "assets/tutorials/fixtures/media-c09-sample.pdf": b"%PDF-synthetic fixture",
        "assets/tutorials/fixtures/core.interface.msd": b'{"synthetic":true}',
    }
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


def archive(root, *, extras=None, omit=(), version="6.2.0"):
    exe = fake_pe()
    files = {name: b"synthetic dependency" for name in artifact.REQUIRED_FILES}
    files["MyScreenDraw.exe"] = exe
    files["_internal/python311.dll"] = b"synthetic runtime"
    files["RELEASE-MANIFEST.json"] = json.dumps({
        "app_version": version, "executable": "MyScreenDraw.exe",
        "hash_algorithm": "SHA-256", "sha256": hashlib.sha256(exe).hexdigest(),
    }).encode()
    for path in (root / "assets/tutorials").rglob("*"):
        if path.is_file():
            files["_internal/" + path.relative_to(root).as_posix()] = path.read_bytes()
    files.update(extras or {})
    destination = root / artifact.artifact_name(version)
    with zipfile.ZipFile(destination, "w") as output:
        for name, data in files.items():
            if name not in omit:
                output.writestr(name, data)
    return destination


@pytest.mark.parametrize("script", ["build.ps1", "create_release.ps1"])
def test_release_scripts_guard_current_source_version(script):
    text = (ROOT / script).read_text("utf-8-sig")
    assert re.search(r'\$version -ne [\"\']' + re.escape(VERSION) + r'[\"\']', text)
    assert "6.1.0" not in text


@pytest.mark.parametrize("relative", ["teaching/nested/worker.py", "assets/tutorials/courses/c01.json",
    "assets/tutorials/fixtures/media-c09-sample.png", "assets/tutorials/fixtures/media-c09-sample.pdf"])
def test_source_snapshot_binds_nested_code_and_exact_teaching_bytes(release_tree, relative):
    before = artifact.source_snapshot(release_tree)
    path = release_tree / relative
    path.write_bytes(path.read_bytes() + b"modified after acceptance")
    after = artifact.source_snapshot(release_tree)
    assert artifact.source_hash(before) != artifact.source_hash(after)
    assert after["files"][relative] == artifact.sha256(path)


def test_new_nested_source_is_detected_but_runtime_and_docs_are_not(release_tree):
    before = artifact.source_snapshot(release_tree)
    for name in ("data/private.json", "exports/private.png", ".ccgui/private.py",
                 "build/generated.py", "tests/test_later.py", "docs/later.md"):
        path = release_tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"must not be read as application source")
    assert artifact.source_snapshot(release_tree) == before
    extra = release_tree / "teaching/nested/new.py"
    extra.write_text("NEW = True\n", encoding="utf-8")
    assert artifact.source_snapshot(release_tree) != before


def test_exact_source_teaching_inventory_survives_archive_validation(release_tree):
    path = archive(release_tree)
    assert artifact.validate_release_zip(path, VERSION, root=release_tree)["version"] == VERSION


@pytest.mark.parametrize("member", ["catalog.json", "courses/c01.json",
    "fixtures/media-c09-sample.png", "fixtures/media-c09-sample.pdf", "fixtures/core.interface.msd"])
def test_missing_teaching_resource_blocks_release(release_tree, member):
    path = archive(release_tree, omit=[TUTORIAL + member])
    with pytest.raises(ValueError, match="teaching|required"):
        artifact.validate_release_zip(path, VERSION, root=release_tree)


@pytest.mark.parametrize("member", ["courses/c01.json", "fixtures/media-c09-sample.png",
                                     "fixtures/core.interface.msd"])
def test_tampered_known_resource_blocks_release(release_tree, member):
    path = archive(release_tree, extras={TUTORIAL + member: b"different bytes"})
    with pytest.raises(ValueError, match="teaching.*(hash|content|mismatch)"):
        artifact.validate_release_zip(path, VERSION, root=release_tree)


@pytest.mark.parametrize("member", ["private.png", "_internal/private.jpg",
    TUTORIAL + "fixtures/unlisted.png", TUTORIAL + "fixtures/unlisted.pdf",
    TUTORIAL + "courses/unlisted.json", TUTORIAL + "fixtures/config.json",
    "data/config.json", "exports/report.pdf", "_internal/leak.py"])
def test_teaching_allowlist_cannot_bless_private_or_unlisted_files(release_tree, member):
    path = archive(release_tree, extras={member: b"must never ship"})
    with pytest.raises(ValueError):
        artifact.validate_release_zip(path, VERSION, root=release_tree)


def test_620_requires_source_inventory_and_teaching_tree(release_tree):
    path = archive(release_tree)
    with pytest.raises(ValueError, match="root|source|teaching"):
        artifact.validate_release_zip(path, VERSION)
    # An absent source catalog cannot quietly disable teaching in a stable release.
    (release_tree / "assets/tutorials/catalog.json").unlink()
    with pytest.raises(ValueError, match="catalog|teaching"):
        artifact.validate_release_zip(path, VERSION, root=release_tree)


def test_package_hygiene_allows_only_byte_identical_bundled_resources(release_tree, tmp_path):
    package = tmp_path / "package"
    package.mkdir()
    with zipfile.ZipFile(archive(release_tree)) as source:
        source.extractall(package)
    artifact.check_package(package, VERSION, release_tree)
    private = package / "private.png"
    private.write_bytes(b"not a teaching resource")
    with pytest.raises(ValueError):
        artifact.check_package(package, VERSION, release_tree)
    private.unlink()
    bundled = package / TUTORIAL / "fixtures/media-c09-sample.png"
    bundled.write_bytes(b"replaced after smoke")
    with pytest.raises(ValueError, match="teaching.*(hash|content|mismatch)"):
        artifact.check_package(package, VERSION, release_tree)


def test_seal_and_verify_reject_changed_teaching_source(release_tree):
    path = archive(release_tree)
    snapshot = release_tree / "build/source.json"
    artifact.write_source_snapshot(release_tree, snapshot)
    checksum = Path(str(path) + ".sha256")
    receipt = release_tree / "build/receipt.json"
    validated = artifact.validate_release_zip(path, VERSION, root=release_tree)
    acceptance = dict(validated, schema=1, checks={check: True for check in artifact.CHECKS})
    artifact.seal_candidate(path, VERSION, release_tree, snapshot, checksum, receipt, acceptance=acceptance)
    artifact.verify_release(path, VERSION, release_tree, checksum, receipt)
    module = release_tree / "teaching/nested/worker.py"
    module.write_bytes(b"changed after acceptance")
    with pytest.raises(ValueError, match="source"):
        artifact.verify_release(path, VERSION, release_tree, checksum, receipt)


@pytest.mark.parametrize("command", ["validate", "check-extracted", "check-package"])
def test_release_cli_uses_source_bound_resources_without_building(release_tree, tmp_path, command):
    path = archive(release_tree)
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(path) as source:
        source.extractall(extracted)
    args = [sys.executable, "-B", str(ROOT / "release_artifact.py"), command,
            "--root", str(release_tree), "--version", VERSION]
    if command != "check-package":
        args.extend(["--zip", str(path)])
    if command != "validate":
        args.extend(["--directory", str(extracted)])
    good = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert good.returncode == 0, good.stderr
    # Even a known fixture at the correct path cannot be replaced after acceptance.
    (release_tree / "assets/tutorials/fixtures/media-c09-sample.png").write_bytes(b"new source bytes")
    bad = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert bad.returncode == 1 and "teaching content hash mismatch" in bad.stderr
    assert "Traceback" not in bad.stderr


def test_both_package_hygiene_checks_and_zip_gates_use_source_root():
    text = (ROOT / "build.ps1").read_text("utf-8-sig")
    checks = re.findall(r"^.*release_artifact\.py check-package.*$", text, re.MULTILINE)
    assert len(checks) == 2
    assert all("--root $root" in line and "--version $version" in line for line in checks)
    for command in ("validate", "check-extracted"):
        line = next(line for line in text.splitlines() if "release_artifact.py " + command in line)
        assert "--root $root" in line
    assert text.index(checks[0]) < text.index("Invoke-Smoke $exe") < text.rindex(checks[1])
    assert "--ignore=tests/test_touch_injection.py" in text
    assert "--ignore=tests/test_multitouch_injection.py" in text
    assert "release_artifact.py snapshot" in text and "release_artifact.py seal" in text
