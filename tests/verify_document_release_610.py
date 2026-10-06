# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in frozen document roundtrip; isolated offscreen package, no input/capture.

Usage: python tests/verify_document_release_610.py PACKAGE.zip EVIDENCE_DIR
Only launches/stops executables from the newly created evidence installation.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import zipfile
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["MYSCREENDRAW_NO_KEYBOARD"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QImage, QColor
import main
from persistence import (make_project_data, atomic_write_project, read_json_maybe_gz,
                         normalize_project_data, PROJECT_KIND, AUTOSAVE_KIND)
from verify_updater_restart import stop_owned, owned_processes, wait_for, sha


def source_document():
    image = QImage(12, 8, QImage.Format.Format_RGB32)
    image.fill(QColor("#2468ac"))
    buffer = QBuffer(); buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    encoded = base64.b64encode(bytes(buffer.data())).decode("ascii")
    pages = []
    for index in range(3):
        pages.append({"page_id": str(uuid.uuid4()), "name": f"Synthetic page {index + 1}",
                      "segments": [{"id": f"ink{index}", "p1": [10, 20], "p2": [40, 60],
                                    "color": "#2255aa", "width": 4, "marker": False}],
                      "texts": [{"id": f"text{index}", "text": f"Page {index + 1}", "pos": [90, 60],
                                 "color": "#ffffff", "size": 24, "width": 1}], "shapes": [],
                      "images": [{"id": f"image{index}", "pos": [40, 50], "size": [12, 8], "data": encoded}]})
    return make_project_data(pages=pages, current_page=1, whiteboard_mode=False,
                             board_style="BLACK", app_version="6.1.0", kind=PROJECT_KIND)


def execute(archive, evidence):
    if main.autostart_enabled():
        raise RuntimeError("Use an isolated Windows profile with autostart disabled")
    main.validate_update_zip(str(archive))
    evidence.mkdir(parents=True, exist_ok=False)
    install = evidence / "portable"
    install.mkdir()
    with zipfile.ZipFile(archive) as package: package.extractall(install)
    data = install / "data"; data.mkdir(exist_ok=True)
    config = data / "config.json"
    config.write_text(json.dumps({"update_check_enabled": False, "timer_alarm_volume": 31,
                                  "autosave_interval_seconds": 5, "page_copy_placement": "before"}), encoding="utf-8")
    system = Path(os.environ["SystemRoot"]) / "System32"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", MYSCREENDRAW_NO_KEYBOARD="1",
               PYINSTALLER_RESET_ENVIRONMENT="1", PYTHONPATH="",
               PATH=os.pathsep.join(map(str, (system, system / "WindowsPowerShell/v1.0"))))
    exe = install / "MyScreenDraw.exe"
    document = source_document()
    wanted_ids = [p["page_id"] for p in document["pages"]]
    rounds = []
    for number in (1, 2):
        recovery = evidence / f"restore-{number}.msd"
        atomic_write_project(str(recovery), document)
        autosaves = data / "autosave"
        before = set(autosaves.glob("autosave_*.json.gz")) if autosaves.exists() else set()
        child = subprocess.Popen([str(exe), "--restore", str(recovery)], cwd=install, env=env,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            wait_for(lambda: not recovery.exists(), timeout=35)
            def new_autosave():
                if child.poll() is not None: raise RuntimeError("Frozen app exited before autosave")
                fresh = set(autosaves.glob("autosave_*.json.gz")) - before
                return max(fresh, key=lambda p: p.stat().st_mtime) if fresh else None
            path = wait_for(new_autosave, timeout=35)
            restored = normalize_project_data(read_json_maybe_gz(str(path)), kind=AUTOSAVE_KIND)
            assert [p["page_id"] for p in restored["pages"]] == wanted_ids
            assert restored["current_page"] == 1 and not restored["whiteboard_mode"]
            assert restored["board_style"] == "BLACK"
            assert [p["name"] for p in restored["pages"]] == [p["name"] for p in document["pages"]]
            assert all(len(p["segments"]) == len(p["texts"]) == len(p["images"]) == 1 for p in restored["pages"])
            settings = json.loads(config.read_text(encoding="utf-8"))
            assert settings["timer_alarm_volume"] == 31
            assert settings["autosave_interval_seconds"] == 5
            assert settings["page_copy_placement"] == "before"
            document = dict(restored, kind=PROJECT_KIND)
            rounds.append({"round": number, "pages": 3, "current_page": 1, "hidden_whiteboard": True,
                           "page_identity_and_content": True, "async_autosave_reopened": True})
        finally:
            if owned_processes(exe): stop_owned(exe)
            child.wait(timeout=20)
    result = {"version": "6.1.0", "offscreen": True, "screenshots": False,
              "zip_sha256": sha(archive), "exe_sha256": sha(exe), "rounds": rounds,
              "persisted_preferences": ["autosave_interval_seconds", "page_copy_placement", "timer_alarm_volume"]}
    (evidence / "document-roundtrip.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    execute(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
