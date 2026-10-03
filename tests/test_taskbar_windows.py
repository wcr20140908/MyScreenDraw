# SPDX-License-Identifier: GPL-3.0-or-later
"""Taskbar native-call regressions using fake COM/user32; never touch Explorer."""
import ast
import ctypes
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLSID = uuid.UUID("56FDF344-FD6D-11D0-958A-006097C9A090").bytes_le
IID = uuid.UUID("56FDF342-FD6D-11D0-958A-006097C9A090").bytes_le
E_FAIL = -2147467259
RPC_E_CHANGED_MODE = -2147417850


def load_helpers(**namespace):
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8-sig"))
    names = {"_delete_from_taskbar", "mark_tool_window"}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    panel = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ControlPanel")
    nodes += [n for n in panel.body if isinstance(n, ast.FunctionDef) and n.name == "raise_floating"]
    assert len(nodes) == 3
    namespace.update(uuid=uuid, LOGGER=Mock(spec=logging.Logger),
                     GWL_EXSTYLE=-20, WS_EX_TOOLWINDOW=0x80, WS_EX_APPWINDOW=0x40000)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / "main.py"), "exec"), namespace)
    return namespace


class NativeCalls:
    def __init__(self, *, apartment=0, create=0, hrinit=0, delete=0):
        self.guids = None
        self.prototypes = {}
        self.release = Mock(return_value=0)
        self.hrinit = Mock(return_value=hrinit)
        self.delete = Mock(return_value=delete)
        self.functions = {102: self.release, 103: self.hrinit, 105: self.delete}
        self.vtable = (ctypes.c_void_p * 6)(0, 0, 102, 103, 0, 105)
        self.instance = (ctypes.POINTER(ctypes.c_void_p) * 1)(
            ctypes.cast(self.vtable, ctypes.POINTER(ctypes.c_void_p)))
        self.address = ctypes.addressof(self.instance)
        self.ole32 = SimpleNamespace(
            CoInitializeEx=Mock(return_value=apartment), CoUninitialize=Mock(),
            CoCreateInstance=Mock(side_effect=self.create),
        )
        self.create_result = create
        self.user32 = SimpleNamespace(GetWindowLongPtrW=Mock(return_value=0x80020),
                                      SetWindowLongPtrW=Mock())
        harness = self

        class Types:
            windll = SimpleNamespace(ole32=harness.ole32, user32=harness.user32)

            def __getattr__(self, name):
                return getattr(ctypes, name)

            @staticmethod
            def WINFUNCTYPE(result, *arguments):
                def bind(address):
                    harness.prototypes[address] = (result, arguments)
                    return harness.functions[address]
                return bind

        self.ns = load_helpers(ctypes=Types(),
                               QApplication=SimpleNamespace(platformName=lambda: "windows"))

    def create(self, clsid, outer, context, iid, output):
        self.guids = (ctypes.string_at(clsid, 16), ctypes.string_at(iid, 16))
        if self.guids != (CLSID, IID):
            return -2147221164  # REGDB_E_CLASSNOTREG, the original failure.
        if self.create_result < 0:
            return self.create_result
        ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = self.address
        return self.create_result

    def remove(self, hwnd=0x123456789ABC):
        return self.ns["_delete_from_taskbar"](hwnd)


def test_registered_guid_bytes_reach_cocreateinstance():
    native = NativeCalls()
    native.remove()
    assert native.guids == (CLSID, IID)


def test_success_preserves_64_bit_hwnd_and_types_com_arguments():
    native = NativeCalls()
    assert native.remove() is True
    assert native.delete.call_args.args[1].value == 0x123456789ABC
    assert native.ole32.CoCreateInstance.argtypes[-1] == ctypes.POINTER(ctypes.c_void_p)
    assert native.ole32.CoInitializeEx.argtypes == [ctypes.c_void_p, ctypes.c_ulong]
    assert native.ole32.CoInitializeEx.restype == ctypes.c_long
    assert native.ole32.CoCreateInstance.restype == ctypes.c_long
    assert native.ole32.CoUninitialize.argtypes == []
    assert native.ole32.CoUninitialize.restype is None
    assert native.prototypes == {
        102: (ctypes.c_ulong, (ctypes.c_void_p,)),
        103: (ctypes.c_long, (ctypes.c_void_p,)),
        105: (ctypes.c_long, (ctypes.c_void_p, ctypes.c_void_p)),
    }
    native.hrinit.assert_called_once()
    native.release.assert_called_once()


@pytest.mark.parametrize("status", [0, 1])
def test_own_com_initialization_is_balanced(status):
    native = NativeCalls(apartment=status)
    assert native.remove() is True
    native.ole32.CoInitializeEx.assert_called_once()
    native.ole32.CoUninitialize.assert_called_once()


def test_existing_different_apartment_is_not_uninitialized():
    native = NativeCalls(apartment=RPC_E_CHANGED_MODE)
    assert native.remove() is True
    native.ole32.CoUninitialize.assert_not_called()
    native.release.assert_called_once()


def test_com_initialization_failure_never_creates_interface():
    native = NativeCalls(apartment=E_FAIL)
    assert native.remove() is False
    native.ole32.CoCreateInstance.assert_not_called()
    native.ole32.CoUninitialize.assert_not_called()
    native.ns["LOGGER"].warning.assert_called()


def test_create_failure_balances_com_and_reports_failure():
    native = NativeCalls(create=E_FAIL)
    assert native.remove() is False
    native.release.assert_not_called()
    native.ole32.CoUninitialize.assert_called_once()
    native.ns["LOGGER"].warning.assert_called()


def test_hrinit_failure_releases_interface_without_deleting_tab():
    native = NativeCalls(hrinit=E_FAIL)
    assert native.remove() is False
    native.delete.assert_not_called()
    native.release.assert_called_once()
    native.ole32.CoUninitialize.assert_called_once()


@pytest.mark.parametrize("raises", [False, True])
def test_delete_failure_still_releases_interface_and_com(raises):
    native = NativeCalls(delete=E_FAIL)
    if raises:
        native.delete.side_effect = OSError("fake native failure")
    assert native.remove() is False
    native.release.assert_called_once()
    native.ole32.CoUninitialize.assert_called_once()
    native.ns["LOGGER"].warning.assert_called()


def test_release_exception_does_not_skip_com_cleanup():
    native = NativeCalls()
    native.release.side_effect = OSError("fake release failure")
    assert native.remove() is True
    native.ole32.CoUninitialize.assert_called_once()
    native.ns["LOGGER"].warning.assert_called()


@pytest.mark.parametrize("hwnd", [0, None])
def test_empty_handle_never_enters_com(hwnd):
    native = NativeCalls()
    assert native.remove(hwnd) is False
    native.ole32.CoInitializeEx.assert_not_called()
    native.ole32.CoCreateInstance.assert_not_called()


def test_offscreen_mark_does_not_call_any_windows_api():
    native = NativeCalls()
    native.ns["QApplication"].platformName = lambda: "offscreen"
    native.ns["_delete_from_taskbar"] = Mock()
    native.ns["mark_tool_window"](123)
    native.user32.GetWindowLongPtrW.assert_not_called()
    native.user32.SetWindowLongPtrW.assert_not_called()
    native.ns["_delete_from_taskbar"].assert_not_called()


@pytest.mark.parametrize("initial", [0x80020 | 0x40000, 0x80020 | 0x80])
def test_native_style_preserves_flags_and_removes_existing_taskbar_button(initial):
    native = NativeCalls()
    native.user32.GetWindowLongPtrW.return_value = initial
    native.ns["_delete_from_taskbar"] = Mock(return_value=True)
    native.ns["mark_tool_window"](123)
    wanted = (initial | 0x80) & ~0x40000
    if wanted != initial:
        assert native.user32.SetWindowLongPtrW.call_args.args[-1] == wanted
    else:
        native.user32.SetWindowLongPtrW.assert_not_called()
    native.ns["_delete_from_taskbar"].assert_called_once_with(123)


@pytest.mark.parametrize("handles", [(123, 123), (123, 456)])
def test_post_show_suppression_handles_reused_and_recreated_hwnds(handles):
    native = NativeCalls()
    ns = native.ns
    ns.update(mark_tool_window=Mock(), set_window_owner=Mock(),
              enforce_topmost_order=Mock(return_value=(False, None, set())),
              place_under_ceiling=Mock())
    panel = SimpleNamespace(canvas=SimpleNamespace(winId=lambda: 999),
                            _unreachable_topmost=set(), floating_stack=lambda: [],
                            _bound_key=(999, 123))
    widget = SimpleNamespace(isVisible=lambda: True, winId=lambda: handles[0])
    for hwnd in handles:
        widget.winId = lambda: hwnd
        ns["raise_floating"](panel, widget)
    assert [c.args[0] for c in ns["mark_tool_window"].call_args_list] == list(handles)


def test_qt_popup_without_owner_rebind_keeps_its_taskbar_policy():
    native = NativeCalls()
    ns = native.ns
    ns.update(mark_tool_window=Mock(), set_window_owner=Mock(),
              enforce_topmost_order=Mock(return_value=(False, None, set())),
              place_under_ceiling=Mock())
    panel = SimpleNamespace(canvas=SimpleNamespace(winId=lambda: 999),
                            _unreachable_topmost=set(), floating_stack=lambda: [])
    widget = SimpleNamespace(isVisible=lambda: True, winId=lambda: 123)
    ns["raise_floating"](panel, widget, bind_owner=False)
    ns["mark_tool_window"].assert_not_called()
    ns["set_window_owner"].assert_not_called()


@pytest.mark.parametrize("stage", ["initialize", "create", "hrinit"])
def test_native_exception_balances_only_acquired_resources(stage):
    native = NativeCalls()
    function = {"initialize": native.ole32.CoInitializeEx,
                "create": native.ole32.CoCreateInstance,
                "hrinit": native.hrinit}[stage]
    function.side_effect = OSError("fake native exception")
    assert native.remove() is False
    assert native.release.call_count == (1 if stage == "hrinit" else 0)
    assert native.ole32.CoUninitialize.call_count == (0 if stage == "initialize" else 1)
    native.delete.assert_not_called()
    native.ns["LOGGER"].warning.assert_called()


def test_null_interface_after_success_is_reported_and_com_balanced():
    native = NativeCalls()
    native.ole32.CoCreateInstance.side_effect = None
    native.ole32.CoCreateInstance.return_value = 0
    assert native.remove() is False
    native.release.assert_not_called()
    native.ole32.CoUninitialize.assert_called_once()
    native.ns["LOGGER"].warning.assert_called()


def test_offscreen_direct_removal_does_not_enter_com():
    native = NativeCalls()
    native.ns["QApplication"].platformName = lambda: "offscreen"
    assert native.remove() is False
    native.ole32.CoInitializeEx.assert_not_called()
    native.ole32.CoCreateInstance.assert_not_called()


def test_com_cleanup_exception_does_not_escape_to_ui():
    native = NativeCalls()
    native.ole32.CoUninitialize.side_effect = OSError("fake cleanup failure")
    assert native.remove() is True
    native.release.assert_called_once()
    native.ns["LOGGER"].warning.assert_called()


def test_style_exception_is_reported_without_escaping_to_ui():
    native = NativeCalls()
    native.user32.GetWindowLongPtrW.side_effect = OSError("fake style failure")
    native.ns["mark_tool_window"](123)
    native.ns["LOGGER"].warning.assert_called()


def test_existing_apartment_create_failure_never_uninitializes_caller():
    native = NativeCalls(apartment=RPC_E_CHANGED_MODE, create=E_FAIL)
    assert native.remove() is False
    native.release.assert_not_called()
    native.ole32.CoUninitialize.assert_not_called()
