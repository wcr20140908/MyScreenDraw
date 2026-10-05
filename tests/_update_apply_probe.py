"""Probe the detached update transaction against a throwaway install dir.

Not part of the suite: run manually to observe what make_update_batch's
PowerShell transaction actually does on this machine.

    QT_QPA_PLATFORM=offscreen python tests/_update_apply_probe.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from main import make_update_batch  # noqa: E402


def build_fixture():
    root = tempfile.mkdtemp(prefix="msd_probe_")
    install = os.path.join(root, "install")
    os.makedirs(os.path.join(install, "_internal"))
    os.makedirs(os.path.join(install, "data"))
    os.makedirs(os.path.join(install, "exports"))
    # A real PE so Start-Process can launch something; where.exe exits on its own.
    shutil.copyfile(r"C:\Windows\System32\where.exe",
                    os.path.join(install, "MyScreenDraw.exe"))
    with open(os.path.join(install, "_internal", "old.txt"), "w", encoding="utf-8") as handle:
        handle.write("old payload")
    with open(os.path.join(install, "data", "config.json"), "w", encoding="utf-8") as handle:
        handle.write('{"keep": true}')
    with open(os.path.join(install, "exports", "note.txt"), "w", encoding="utf-8") as handle:
        handle.write("user export")

    download = tempfile.mkdtemp(prefix="msd_probe_zip_")
    zip_path = os.path.join(download, "update.zip")
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("MyScreenDraw.exe", b"MZ new payload")
        archive.writestr("_internal/old.txt", "new payload")
        archive.writestr("_internal/new.txt", "added")
        archive.writestr("extra.txt", "top level")
    return root, install, zip_path


def main():
    root, install, zip_path = build_fixture()
    script = make_update_batch(zip_path, install)
    print("install:", install)
    print("script :", script)
    proc = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive",
                           "-ExecutionPolicy", "Bypass", "-File", script],
                          capture_output=True, text=True)
    print("exit   :", proc.returncode)
    print("stdout :", proc.stdout.strip())
    print("stderr :", proc.stderr.strip())
    result = os.path.join(install, "data", "update-result.json")
    if os.path.isfile(result):
        with open(result, encoding="utf-8-sig") as handle:
            print("result :", handle.read())
    else:
        print("result : MISSING")
    for path, _, names in os.walk(install):
        for name in names:
            full = os.path.join(path, name)
            print("  ", os.path.relpath(full, install), os.path.getsize(full))
    leftovers = [n for n in os.listdir(install) if n.startswith(".msd-update-")]
    print("leftover update dirs:", leftovers)
    print("root:", root)


if __name__ == "__main__":
    main()
