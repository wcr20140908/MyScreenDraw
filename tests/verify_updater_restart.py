# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in frozen restart check; isolated data, offscreen Qt, no screenshots.

Usage: python tests/verify_updater_restart.py OLD.zip NEW.zip NEW_VERSION EVIDENCE_DIR
Runs the *current* updater against a copy of the old package. It does not prove
that the old release's embedded updater has been retroactively repaired.
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['MYSCREENDRAW_NO_KEYBOARD'] = '1'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import make_update_batch, validate_update_zip, autostart_enabled


def sha(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def wait_for(check, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.2)
    raise TimeoutError('Frozen updater verification timed out')


def powershell(code):
    return subprocess.check_output(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', code],
                                   creationflags=subprocess.CREATE_NO_WINDOW, timeout=20).decode('utf-8-sig').strip()


def owned_processes(exe):
    literal = "'" + str(exe).replace("'", "''") + "'"
    text = powershell("$ErrorActionPreference='Stop'; @(Get-Process -Name MyScreenDraw -ErrorAction SilentlyContinue | "
                      "Where-Object { $_.Path -eq " + literal + " } | ForEach-Object { "
                      "@{ id=$_.Id; threads=@($_.Threads | ForEach-Object {$_.Id}) } }) | ConvertTo-Json -Compress")
    if not text:
        return []
    result = json.loads(text)
    return result if isinstance(result, list) else [result]


def stop_owned(exe):
    # Only processes whose executable path is the exact isolated installation.
    processes = owned_processes(exe)
    for process in processes:
        for thread in process['threads']:
            ctypes.windll.user32.PostThreadMessageW(int(thread), 0x0012, 0, 0)
    wait_for(lambda: not owned_processes(exe), timeout=20)


def execute(old_zip, new_zip, version, evidence):
    # Normal startup heals enabled autostart paths; never touch a user's entry.
    if autostart_enabled():
        raise RuntimeError("Use an isolated Windows profile without a MyScreenDraw autostart entry")
    evidence = evidence.resolve()
    if evidence.exists():
        raise ValueError('Evidence directory must be new; never overwrite an installation')
    evidence.mkdir(parents=True)
    install = evidence / "portable 升级 [6] with spaces"
    validate_update_zip(str(old_zip)); validate_update_zip(str(new_zip))
    with zipfile.ZipFile(old_zip) as archive:
        archive.extractall(install)
    (install / 'data').mkdir(exist_ok=True)
    (install / 'exports').mkdir(exist_ok=True)
    config = install / 'data/config.json'
    preferences = {'theme': 'light', 'ui_radius': 19, 'ui_opacity': 83,
                   'update_check_enabled': False, 'update_channel': 'stable',
                   'notice_state': {'launches': 7, 'last_version': 'v6.0.0'}}
    config.write_text(json.dumps(preferences), encoding='utf-8')
    sentinels = {'data/lesson.msd': b'synthetic lesson', 'data/roster.json': b'[]',
                 'exports/lesson.svg': b'<svg/>', 'teacher-notes.txt': b'private root file'}
    for relative, data in sentinels.items():
        (install / relative).write_bytes(data)
    before = {relative: sha(install / relative) for relative in sentinels}
    exe = install / 'MyScreenDraw.exe'
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', MYSCREENDRAW_NO_KEYBOARD='1',
               PYINSTALLER_RESET_ENVIRONMENT='1')
    system = Path(os.environ['SystemRoot']) / 'System32'
    env['PATH'] = os.pathsep.join(map(str, (system, system / 'WindowsPowerShell/v1.0')))
    env['PYTHONPATH'] = ''
    old_hash = sha(exe)
    # Verify the old package can start and close without ever displaying a window.
    smoke = subprocess.run([str(exe), '--smoke-ui'], cwd=install, env=env, timeout=60,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    assert smoke.returncode == 0, 'Old package smoke failed'
    copy = evidence / 'update.zip'
    shutil.copyfile(new_zip, copy)
    script = make_update_batch(str(copy), str(install), version='v' + version, owner_pid=None)
    started = time.monotonic()
    try:
        # File handles, not PIPE: the intentionally long-lived restarted process
        # can inherit stdout/stderr, so communicate() must not wait for its EOF.
        with (evidence / 'transaction.stdout').open('wb') as stdout, (evidence / 'transaction.stderr').open('wb') as stderr:
            run = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden',
                                  '-ExecutionPolicy', 'Bypass', '-File', script], env=env,
                                 stdout=stdout, stderr=stderr, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
        assert run.returncode == 0, (evidence / 'transaction.stderr').read_text(errors='replace')
        def started_new_version():
            try:
                data = json.loads(config.read_text(encoding='utf-8'))
                return data if data.get('notice_state', {}).get('last_version') == 'v' + version else None
            except (OSError, ValueError):
                return None
        saved = wait_for(started_new_version)
        assert owned_processes(exe), 'New EXE did not remain running'
        assert sha(exe) != old_hash, 'Executable did not change'
        manifest = json.loads((install / 'RELEASE-MANIFEST.json').read_text(encoding='utf-8-sig'))
        assert manifest['app_version'] == version
        assert sha(exe) == manifest['sha256']
        assert all(sha(install / p) == h for p, h in before.items())
        for key in ('theme', 'ui_radius', 'ui_opacity', 'update_check_enabled', 'update_channel'):
            assert saved[key] == preferences[key], key
        duration = round(time.monotonic() - started, 2)
        stop_owned(exe)
        # Manual reopen is verified too, using the exact installed executable.
        reopened = subprocess.run([str(exe), '--smoke-ui'], cwd=install, env=env, timeout=60,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
        assert reopened.returncode == 0
        result = {'result': 'passed', 'version': version, 'old_zip_sha256': sha(old_zip),
                  'new_zip_sha256': sha(new_zip), 'installed_exe_sha256': sha(exe),
                  'transaction_and_startup_seconds': duration, 'preserved_private_files': len(before),
                  'preserved_preferences': 5, 'automatic_restart': True, 'manual_reopen_smoke': True,
                  'offscreen': True, 'screenshots': False, 'current_updater_not_old_embedded_updater': True}
        (evidence / 'restart-verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result, indent=2))
    finally:
        if owned_processes(exe):
            stop_owned(exe)


if __name__ == '__main__':
    execute(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3], Path(sys.argv[4]))
