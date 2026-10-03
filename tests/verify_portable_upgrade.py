# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in real EXE upgrade check. All data is synthetic, beneath an explicit evidence directory.

Usage: python tests/verify_portable_upgrade.py OLD.zip NEW.zip PRIVATE_DIR
Uses real update transaction and native window-loop exit (WM_QUIT), not a mock EXE.
Does not test physical touch hardware or a Windows installation without Python.
"""
import ctypes
from ctypes import wintypes as wt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from main import make_update_batch, validate_update_zip, autostart_enabled
from persistence import make_project_data

u = ctypes.windll.user32
k = ctypes.windll.kernel32
u.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
u.GetWindowThreadProcessId.restype = wt.DWORD
u.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]
k.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k.OpenProcess.restype = wt.HANDLE
k.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
k.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
k.CloseHandle.argtypes = [wt.HANDLE]
CALLBACK = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
u.EnumWindows.argtypes = [CALLBACK, wt.LPARAM]
u.IsWindowVisible.argtypes = [wt.HWND]
u.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def windows(pid):
    result = []
    @CALLBACK
    def collect(hwnd, _):
        owner = wt.DWORD()
        tid = u.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            result.append((hwnd, tid, bool(u.IsWindowVisible(hwnd))))
        return True
    u.EnumWindows(collect, 0)
    return result


def bounded_wait(predicate, timeout=25):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(.2)
    raise AssertionError('Timed out waiting for test application')


def quit_app(pid):
    handle = k.OpenProcess(0x100000 | 0x1000, False, pid)
    assert handle, 'Cannot open owned test process'
    try:
        threads = {tid for _, tid, _ in windows(pid)}
        assert threads, 'No application event-loop thread'
        for tid in threads:
            assert u.PostThreadMessageW(tid, 0x12, 0, 0)  # WM_QUIT -> Qt aboutToQuit
        assert k.WaitForSingleObject(handle, 15000) == 0, 'EXE did not exit normally'
        code = wt.DWORD()
        assert k.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value == 0, code.value
    finally:
        k.CloseHandle(handle)


def inspect_and_quit(pid, evidence, label):
    owned = bounded_wait(lambda: [w for w in windows(pid) if w[2]])
    time.sleep(3)
    # Capture only the smallest visible owned window (typically the LOGO).
    from _grab import save_png
    rects = []
    for hwnd, _, _ in owned:
        r = wt.RECT()
        if u.GetWindowRect(hwnd, ctypes.byref(r)) and r.right > r.left and r.bottom > r.top:
            rects.append((r.right-r.left, r.bottom-r.top, r.left, r.top))
    if rects:
        choose = max if label == "restarted-exe" else min
        width, height, x, y = choose(rects, key=lambda r:r[0]*r[1])
        save_png(str(evidence / (label+'.png')), x, y, width, height)
    quit_app(pid)


def execute(old_zip, new_zip, evidence):
    assert not autostart_enabled(), "Use a test profile without an existing app autostart entry"
    evidence.mkdir(parents=True, exist_ok=True)
    install = evidence / 'portable \u5347\u7ea7 [6] with spaces'
    assert not install.exists(), 'Use a fresh evidence directory; never overwrite an installation'
    validate_update_zip(old_zip); validate_update_zip(new_zip)
    with zipfile.ZipFile(old_zip) as z:
        z.extractall(install)
    (install/'data').mkdir(exist_ok=True)
    (install/'exports').mkdir(exist_ok=True)
    config = install/'data/config.json'
    preferences = {'theme':'light','orientation':'landscape','ui_radius':19,
                   'ui_opacity':83,'update_check_enabled':False,'update_channel':'stable',
                   'pen_style':'calligraphy','pen_color':'#2468ac','pen_width':19,
                   'speed_width':False,'calligraphy_angle':123,
                   'eraser_size':81,'marker_width':37,'marker_alpha_pct':61,
                   'laser_width':29,'smart_shapes':False,
                   'smart_multitouch':False}
    config.write_text(json.dumps(preferences), encoding='utf-8')
    env = dict(os.environ)
    env.pop('QT_QPA_PLATFORM', None)
    system32 = Path(os.environ['SystemRoot'])/'System32'
    env['PATH'] = os.pathsep.join(map(str, (system32, system32/'WindowsPowerShell/v1.0')))
    env['PYTHONPATH'] = ''
    exe = install/'MyScreenDraw.exe'
    old = subprocess.Popen([str(exe)], cwd=install, env=env)
    inspect_and_quit(old.pid, evidence, 'old-exe')
    assert old.wait(timeout=2) == 0
    before = json.loads(config.read_text(encoding='utf-8'))
    protected = {'data/roster.json':'["Synthetic Student A"]',
                 'data/autosave/private-note.txt':'Synthetic autosave directory sentinel',
                 'data/lesson.msd':'{"fixture":"synthetic classroom project"}',
                 'data/old-classroom.log':'Synthetic old log',
                 'exports/lesson.svg':'<svg xmlns="http://www.w3.org/2000/svg"/>',
                 'teacher-notes.txt':'Synthetic unrelated root file',
                 'lessons/keep.txt':'Synthetic unrelated root directory'}
    page = {"segments": [{"p1":[200,200], "p2":[600,350], "color":"#2468ac", "width":8}],
            "texts":[], "shapes":[], "images":[]}
    project = make_project_data(pages=[page,page],current_page=1,whiteboard_mode=True,
                                board_style="WHITE",app_version="v6.0.0-beta.8")
    protected['data/lesson.msd'] = json.dumps(project)
    for relative, text in protected.items():
        path = install/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    hashes = {p:digest(install/p) for p in protected}
    archive = evidence/'update-copy.zip'
    shutil.copy2(new_zip, archive)
    script = make_update_batch(str(archive), str(install))
    run = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',script],
                         env=env, capture_output=True, timeout=600, creationflags=subprocess.CREATE_NO_WINDOW)
    (evidence/'update-transaction.stdout').write_bytes(run.stdout)
    (evidence/'update-transaction.stderr').write_bytes(run.stderr)
    assert run.returncode == 0, run.stderr.decode(errors='replace')
    def find_pid():
        out = subprocess.check_output(['powershell.exe','-NoProfile','-Command',
            "[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); Get-CimInstance Win32_Process -Filter \"Name='MyScreenDraw.exe'\" | Select-Object ProcessId,ExecutablePath | ConvertTo-Json -Compress"],
            creationflags=subprocess.CREATE_NO_WINDOW)
        items = json.loads(out.decode('utf-8-sig') or '[]')
        if isinstance(items, dict): items = [items]
        return next((x['ProcessId'] for x in items if x.get('ExecutablePath','').casefold()==str(exe).casefold()),None)
    pid = bounded_wait(find_pid)
    inspect_and_quit(pid, evidence, 'new-exe')
    after = json.loads(config.read_text(encoding='utf-8'))
    preserved = [key for key in preferences if after[key] == before[key]]
    assert len(preserved)==len(preferences), [(key,before.get(key),after.get(key)) for key in preferences if before.get(key)!=after.get(key)]
    assert after['whiteboard_auto_pen'] is True and after['pen_defaults_enabled'] is False
    assert after['notice_state']['launches'] == 1, after.get('notice_state')
    assert all(digest(install/p)==h for p,h in hashes.items())
    manifest=json.loads((install/'RELEASE-MANIFEST.json').read_text(encoding='utf-8-sig'))
    assert manifest['app_version']=='6.0.0'
    with zipfile.ZipFile(new_zip) as z:
        assert digest(exe)==hashlib.sha256(z.read('MyScreenDraw.exe')).hexdigest()
    # A second independent normal process must preserve new preferences and notice count.
    restore=evidence/'restore-fixture.msd'
    shutil.copy2(install/'data/lesson.msd', restore)
    again=subprocess.Popen([str(exe),'--restore',str(restore)],cwd=install,env=env)
    inspect_and_quit(again.pid,evidence,'restarted-exe')
    assert again.wait(timeout=2)==0
    restarted=json.loads(config.read_text(encoding='utf-8'))
    assert restarted['notice_state']['launches']==2
    assert not restore.exists(), 'Frozen app did not restore the prior-version project'
    events=[json.loads(line) for line in (install/'data/events.jsonl').read_text(encoding='utf-8').splitlines()]
    assert any(event['event']=='restart_restored' for event in events)
    assert all(digest(install/p)==h for p,h in hashes.items())
    log=(install/'data/app.log').read_text(encoding='utf-8')
    assert 'Traceback' not in log and 'ERROR' not in log
    result={'old_zip_sha256':digest(old_zip),'new_zip_sha256':digest(new_zip),
            'exe_sha256':digest(exe),'version':manifest['app_version'],
            'preserved_preference_count':len(preserved),'preserved_sentinel_count':len(hashes),
            'normal_process_launches':3,'prior_version_project_restored':True,'python_removed_from_child_path':True,
            'non_ascii_space_bracket_path':True,'result':'passed'}
    (evidence/'portable-upgrade.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    execute(*(Path(arg).resolve() for arg in sys.argv[1:4]))
