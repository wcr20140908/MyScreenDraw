# SPDX-License-Identifier: GPL-3.0-or-later
"""Cross-process ownership and activation for ordinary application startup."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _environment():
    environment = dict(os.environ)
    environment.update({
        "QT_QPA_PLATFORM": "offscreen",
        "MYSCREENDRAW_NO_KEYBOARD": "1",
        "PYNPUT_BACKEND": "dummy",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    })
    return environment


def _run(script, *arguments, timeout=15):
    return subprocess.run(
        [sys.executable, "-c", script, *map(str, arguments)], cwd=ROOT,
        env=_environment(), capture_output=True, text=True, encoding="utf-8",
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def test_second_process_notifies_primary_and_does_not_claim_endpoint(tmp_path):
    endpoint = f"myscreendraw-test-{uuid.uuid4().hex}"
    activated = tmp_path / "activated.json"
    server_script = r'''
import json, sys
from pathlib import Path
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from single_instance import SingleInstanceGuard
app = QApplication([])
guard = SingleInstanceGuard(sys.argv[1])
assert guard.acquire_or_notify()
def activated():
    Path(sys.argv[2]).write_text(json.dumps({"activated": True}), encoding="utf-8")
    app.quit()
guard.activation_requested.connect(activated)
print("READY", flush=True)
QTimer.singleShot(10000, app.quit)
raise SystemExit(app.exec())
'''
    client_script = r'''
import json, sys
from PyQt6.QtWidgets import QApplication
from single_instance import SingleInstanceGuard
app = QApplication([])
guard = SingleInstanceGuard(sys.argv[1])
print(json.dumps({"primary": guard.acquire_or_notify()}), flush=True)
'''
    server = subprocess.Popen(
        [sys.executable, "-c", server_script, endpoint, str(activated)], cwd=ROOT,
        env=_environment(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        assert server.stdout.readline().strip() == "READY"
        client = _run(client_script, endpoint)
        assert client.returncode == 0, client.stderr
        assert json.loads(client.stdout.strip())["primary"] is False
        server.wait(timeout=10)
        assert json.loads(activated.read_text(encoding="utf-8")) == {"activated": True}
    finally:
        if server.poll() is None:
            server.terminate()
            server.wait(timeout=5)


def test_endpoint_can_be_reclaimed_after_primary_exits():
    endpoint = f"myscreendraw-test-{uuid.uuid4().hex}"
    script = r'''
import json, sys
from PyQt6.QtWidgets import QApplication
from single_instance import SingleInstanceGuard
app = QApplication([])
guard = SingleInstanceGuard(sys.argv[1])
print(json.dumps({"primary": guard.acquire_or_notify()}), flush=True)
'''
    first = _run(script, endpoint)
    second = _run(script, endpoint)
    assert first.returncode == second.returncode == 0
    assert json.loads(first.stdout.strip())["primary"] is True
    assert json.loads(second.stdout.strip())["primary"] is True


def test_replacement_waits_for_owned_process_to_exit():
    holder = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(0.6)"], cwd=ROOT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        script = r'''
import json, sys, time
from single_instance import wait_for_process_exit
started = time.monotonic()
result = wait_for_process_exit(int(sys.argv[1]), timeout_ms=5000)
print(json.dumps({"result": result, "elapsed": time.monotonic() - started}), flush=True)
'''
        completed = _run(script, holder.pid)
        assert completed.returncode == 0, completed.stderr
        report = json.loads(completed.stdout.strip())
        assert report["result"] is True
        assert report["elapsed"] >= 0.2
    finally:
        if holder.poll() is None:
            holder.terminate()
        holder.wait(timeout=5)


def test_replacement_accepts_predecessor_that_already_exited():
    holder = subprocess.Popen(
        [sys.executable, "-c", "pass"], cwd=ROOT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    holder.wait(timeout=5)
    script = r'''
import json, sys
from single_instance import wait_for_process_exit
print(json.dumps({"result": wait_for_process_exit(int(sys.argv[1]), timeout_ms=100)}), flush=True)
'''
    completed = _run(script, holder.pid)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout.strip())["result"] is True


def test_normal_endpoint_is_stable_across_source_and_frozen_identity(monkeypatch):
    import single_instance_bootstrap as bootstrap

    monkeypatch.setattr(bootstrap, "_login_session_key", lambda: "session-42")
    assert bootstrap.application_endpoint() == bootstrap.application_endpoint()
    assert "MyScreenDraw" in bootstrap.application_endpoint()


def test_bootstrap_module_does_not_import_qt_or_main():
    script = r'''
import json, sys
import single_instance_bootstrap
print(json.dumps({
    "pyqt": any(name == "PyQt6" or name.startswith("PyQt6.") for name in sys.modules),
    "pynput": any(name == "pynput" or name.startswith("pynput.") for name in sys.modules),
    "main": "main" in sys.modules,
}))
'''
    completed = _run(script)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout.strip()) == {"pyqt": False, "pynput": False, "main": False}


@pytest.mark.skipif(os.name != "nt", reason="native named mutex and pipe are Windows startup behavior")
def test_native_secondary_exits_without_qt_when_server_is_not_ready():
    endpoint = f"myscreendraw-test-{uuid.uuid4().hex}"
    holder_script = r'''
import sys, time
from single_instance_bootstrap import claim_windows_lease
lease = claim_windows_lease(sys.argv[1])
assert lease is not None
print("READY", flush=True)
time.sleep(10)
'''
    client_script = r'''
import json, sys
from single_instance_bootstrap import preflight_startup
decision = preflight_startup([], endpoint=sys.argv[1], timeout_ms=150)
print(json.dumps({
    "role": decision.role,
    "notified": decision.notified,
    "pyqt": any(name == "PyQt6" or name.startswith("PyQt6.") for name in sys.modules),
    "pynput": any(name == "pynput" or name.startswith("pynput.") for name in sys.modules),
    "main": "main" in sys.modules,
}), flush=True)
'''
    holder = subprocess.Popen(
        [sys.executable, "-c", holder_script, endpoint], cwd=ROOT, env=_environment(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        assert holder.stdout.readline().strip() == "READY"
        completed = _run(client_script, endpoint)
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout.strip()) == {
            "role": "secondary", "notified": False,
            "pyqt": False, "pynput": False, "main": False,
        }
    finally:
        if holder.poll() is None:
            holder.terminate()
        holder.wait(timeout=5)


@pytest.mark.skipif(os.name != "nt", reason="native named mutex and pipe are Windows startup behavior")
def test_native_secondary_notifies_existing_qt_server(tmp_path):
    endpoint = f"myscreendraw-test-{uuid.uuid4().hex}"
    activated = tmp_path / "native-activated.json"
    server_script = r'''
import json, sys
from pathlib import Path
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from single_instance import SingleInstanceGuard
app = QApplication([])
guard = SingleInstanceGuard(sys.argv[1])
assert guard.acquire_or_notify()
guard.activation_requested.connect(
    lambda: (Path(sys.argv[2]).write_text(json.dumps({"activated": True}), encoding="utf-8"), app.quit()))
print("READY", flush=True)
QTimer.singleShot(10000, app.quit)
raise SystemExit(app.exec())
'''
    client_script = r'''
import json, sys
from single_instance_bootstrap import preflight_startup
decision = preflight_startup([], endpoint=sys.argv[1], timeout_ms=1500)
print(json.dumps({"role": decision.role, "notified": decision.notified}), flush=True)
'''
    server = subprocess.Popen(
        [sys.executable, "-c", server_script, endpoint, str(activated)], cwd=ROOT,
        env=_environment(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        assert server.stdout.readline().strip() == "READY"
        completed = _run(client_script, endpoint)
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout.strip()) == {"role": "secondary", "notified": True}
        server.wait(timeout=10)
        assert json.loads(activated.read_text(encoding="utf-8")) == {"activated": True}
    finally:
        if server.poll() is None:
            server.terminate()
            server.wait(timeout=5)


@pytest.mark.skipif(os.name != "nt", reason="native named mutex is Windows startup behavior")
def test_native_preflight_reclaims_mutex_when_owner_exits_during_retry():
    endpoint = f"myscreendraw-test-{uuid.uuid4().hex}"
    holder_script = r'''
import sys, time
from single_instance_bootstrap import claim_windows_lease
lease = claim_windows_lease(sys.argv[1])
assert lease is not None
print("READY", flush=True)
time.sleep(0.25)
lease.close()
'''
    client_script = r'''
import json, sys
from single_instance_bootstrap import preflight_startup
decision = preflight_startup([], endpoint=sys.argv[1], timeout_ms=2000)
print(json.dumps({"role": decision.role, "notified": decision.notified}), flush=True)
if decision.lease is not None:
    decision.lease.close()
'''
    holder = subprocess.Popen(
        [sys.executable, "-c", holder_script, endpoint], cwd=ROOT, env=_environment(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        assert holder.stdout.readline().strip() == "READY"
        completed = _run(client_script, endpoint, timeout=10)
        assert completed.returncode == 0, completed.stderr
        assert json.loads(completed.stdout.strip()) == {"role": "primary", "notified": False}
    finally:
        if holder.poll() is None:
            holder.terminate()
        holder.wait(timeout=5)


def test_smoke_and_practice_startups_bypass_ordinary_instance_lock():
    from single_instance_bootstrap import preflight_startup

    for arguments in (["--smoke"], ["--smoke-ui"], ["--teaching-practice"]):
        decision = preflight_startup(arguments)
        assert decision.role == "bypass"
        assert decision.lease is None


def test_main_runs_preflight_before_qt_and_pynput_imports():
    source = (ROOT / "main.py").read_text(encoding="utf-8-sig")
    preflight = source.index("preflight_startup(")
    assert preflight < source.index("from PyQt6.QtWidgets import")
    assert preflight < source.index("from pynput import keyboard")
    assert source.index("parse_practice_request(") < preflight
