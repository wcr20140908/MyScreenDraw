# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Native single-instance preflight that runs before importing Qt."""
from __future__ import annotations

from dataclasses import dataclass
import ctypes
import ctypes.wintypes
import getpass
import hashlib
import os
import time
from typing import Literal, Sequence


_APPLICATION_ID = "org.myscreendraw.desktop.v1"
ACTIVATE_MESSAGE = b"activate\n"
_ERROR_ALREADY_EXISTS = 183
_ERROR_INVALID_PARAMETER = 87
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


def _login_session_key() -> str:
    """Return a stable key shared by source and frozen builds in one login session."""
    if os.name == "nt":
        session_id = ctypes.c_ulong()
        if ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session_id)):
            return f"windows-{session_id.value}-{getpass.getuser()}"
    return f"{os.name}-{getattr(os, 'getuid', lambda: 0)()}-{os.environ.get('DISPLAY', '')}"


def application_endpoint() -> str:
    identity = f"{_APPLICATION_ID}:{_login_session_key()}".encode("utf-8", "surrogatepass")
    return f"MyScreenDraw-{hashlib.sha256(identity).hexdigest()[:20]}"


def replacement_pid(arguments: Sequence[object]) -> int | None:
    try:
        values = list(arguments)
        index = values.index("--replace-instance")
        value = int(values[index + 1])
    except (ValueError, TypeError, IndexError):
        return None
    return value if value > 0 and value != os.getpid() else None


def wait_for_process_exit(pid: int, timeout_ms: int = 30000) -> bool:
    """Wait only for the explicitly supplied predecessor PID."""
    if not isinstance(pid, int) or pid <= 0 or pid == os.getpid():
        return False
    if os.name == "nt":
        synchronize = 0x00100000
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL,
                                         ctypes.wintypes.DWORD]
        kernel32.OpenProcess.restype = ctypes.wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = ctypes.wintypes.DWORD
        kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
        kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
        handle = kernel32.OpenProcess(synchronize, False, pid)
        if not handle:
            return ctypes.get_last_error() == _ERROR_INVALID_PARAMETER
        try:
            return kernel32.WaitForSingleObject(handle, max(0, int(timeout_ms))) == 0
        finally:
            kernel32.CloseHandle(handle)

    deadline = time.monotonic() + max(0, timeout_ms) / 1000
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        time.sleep(0.05)
    return False


class NativeInstanceLease:
    """Own the Windows mutex handle until the Qt server takes over."""

    def __init__(self, endpoint: str, handle: int):
        self.endpoint = endpoint
        self._handle = handle

    @property
    def is_open(self) -> bool:
        return self._handle is not None

    def close(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None or os.name != "nt":
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
        kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
        kernel32.CloseHandle(ctypes.wintypes.HANDLE(handle))

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


@dataclass
class StartupDecision:
    role: Literal["primary", "secondary", "bypass"]
    lease: NativeInstanceLease | None = None
    notified: bool = False
    reason: str = ""


def claim_windows_lease(endpoint: str | None = None) -> NativeInstanceLease | None:
    """Claim the per-session mutex, or return None while another process owns it."""
    if os.name != "nt":
        raise RuntimeError("native instance lease is available only on Windows")
    endpoint = endpoint or application_endpoint()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.wintypes.BOOL,
                                      ctypes.wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = ctypes.wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
    kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, False, f"Local\\{endpoint}-owner")
    error = ctypes.get_last_error()
    if not handle:
        raise OSError(error, "CreateMutexW failed")
    if error == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        return None
    return NativeInstanceLease(endpoint, int(handle))


def _notify_windows_pipe(endpoint: str, message: bytes = ACTIVATE_MESSAGE,
                         timeout_ms: int = 250) -> bool:
    """Write directly to the named pipe backing QLocalServer, without importing Qt."""
    if os.name != "nt":
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    pipe_name = rf"\\.\pipe\{endpoint}"
    kernel32.WaitNamedPipeW.argtypes = [ctypes.wintypes.LPCWSTR, ctypes.wintypes.DWORD]
    kernel32.WaitNamedPipeW.restype = ctypes.wintypes.BOOL
    if not kernel32.WaitNamedPipeW(pipe_name, max(0, int(timeout_ms))):
        return False
    kernel32.CreateFileW.argtypes = [ctypes.wintypes.LPCWSTR, ctypes.wintypes.DWORD,
                                     ctypes.wintypes.DWORD, ctypes.c_void_p,
                                     ctypes.wintypes.DWORD, ctypes.wintypes.DWORD,
                                     ctypes.wintypes.HANDLE]
    kernel32.CreateFileW.restype = ctypes.wintypes.HANDLE
    handle = kernel32.CreateFileW(pipe_name, 0x40000000, 0, None, 3, 0x80, None)
    if not handle or int(handle) == _INVALID_HANDLE_VALUE:
        return False
    try:
        kernel32.WriteFile.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_void_p,
                                       ctypes.wintypes.DWORD,
                                       ctypes.POINTER(ctypes.wintypes.DWORD), ctypes.c_void_p]
        kernel32.WriteFile.restype = ctypes.wintypes.BOOL
        written = ctypes.wintypes.DWORD()
        buffer = ctypes.create_string_buffer(message)
        return bool(kernel32.WriteFile(handle, buffer, len(message), ctypes.byref(written), None)
                    and written.value == len(message))
    finally:
        kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
        kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
        kernel32.CloseHandle(handle)


def _bypass_reason(arguments: Sequence[object]) -> str | None:
    names = {value.split("=", 1)[0] for value in arguments if isinstance(value, str)}
    if "--teaching-practice" in names:
        return "teaching-practice"
    if "--smoke" in names or "--smoke-ui" in names:
        return "smoke"
    return None


def preflight_startup(arguments: Sequence[object], *, endpoint: str | None = None,
                      timeout_ms: int = 500) -> StartupDecision:
    """Decide ordinary startup before Qt, pynput or the application module loads."""
    reason = _bypass_reason(arguments)
    if reason is not None:
        return StartupDecision("bypass", reason=reason)
    predecessor = replacement_pid(arguments)
    if predecessor is not None and not wait_for_process_exit(predecessor):
        raise RuntimeError(f"replacement startup timed out waiting for process {predecessor}")
    if os.name != "nt":
        return StartupDecision("bypass", reason="qt-fallback")

    endpoint = endpoint or application_endpoint()
    lease = claim_windows_lease(endpoint)
    if lease is not None:
        return StartupDecision("primary", lease=lease)

    deadline = time.monotonic() + max(0, int(timeout_ms)) / 1000
    while True:
        remaining = max(0, round((deadline - time.monotonic()) * 1000))
        if _notify_windows_pipe(endpoint, timeout_ms=min(250, remaining)):
            return StartupDecision("secondary", notified=True)
        lease = claim_windows_lease(endpoint)
        if lease is not None:
            return StartupDecision("primary", lease=lease)
        if remaining <= 0:
            return StartupDecision("secondary", notified=False)
        time.sleep(min(0.05, remaining / 1000))


__all__ = [
    "ACTIVATE_MESSAGE", "NativeInstanceLease", "StartupDecision",
    "application_endpoint", "claim_windows_lease", "preflight_startup",
    "replacement_pid", "wait_for_process_exit",
]
