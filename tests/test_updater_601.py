# SPDX-License-Identifier: GPL-3.0-or-later
"""6.0.1 updater contracts: no network, event loop, desktop, or child process.

The actual worker runs synchronously. ControlPanel methods are compiled without
rewriting their bodies and receive inert collaborators instead of a real window.
"""
import ast
import inspect
import io
import os
from pathlib import Path
import sys
import textwrap
from types import SimpleNamespace
from unittest.mock import Mock
import urllib.request
import zipfile

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main


URL = "https://example.invalid/MyScreenDraw-v6.0.1.zip"
RELEASE = {"tag": "v6.0.1", "download_url": URL, "asset_name": "MyScreenDraw-v6.0.1.zip"}
CHUNK = 64 * 1024


@pytest.fixture(autouse=True)
def no_external_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Updater regression tests must not access network or spawn processes")
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(main.subprocess, "Popen", forbidden)
    monkeypatch.setattr(main, "track_event", Mock())


class Response:
    """Finite, cursor-based stream, unlike mocks that return one chunk forever."""

    def __init__(self, payload, length=None, fail_after=None):
        self.stream = io.BytesIO(payload)
        self.headers = {} if length is None else {"Content-Length": str(length)}
        self.fail_after = fail_after
        self.read_sizes = []
        self.eof = False
        self.closed = False

    def geturl(self):
        return URL

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True
        self.stream.close()
        return False

    def read(self, size=-1):
        self.read_sizes.append(size)
        if len(self.read_sizes) > 16:
            raise AssertionError("Download must terminate on EOF")
        if self.fail_after is not None and self.stream.tell() >= self.fail_after:
            raise OSError("simulated interrupted transport")
        chunk = self.stream.read(size)
        self.eof = not chunk
        return chunk


def prepare_worker(monkeypatch, tmp_path, response, cancelled=lambda: False):
    original_mkdtemp = main.tempfile.mkdtemp
    roots = []

    def mkdtemp(*args, **kwargs):
        kwargs["dir"] = str(tmp_path)
        root = original_mkdtemp(*args, **kwargs)
        roots.append(Path(root))
        return root

    monkeypatch.setattr(main.tempfile, "mkdtemp", mkdtemp)
    monkeypatch.setattr(urllib.request, "urlopen", Mock(return_value=response))
    worker = main.UpdateDownloadWorker(URL)
    monkeypatch.setattr(worker, "isInterruptionRequested", cancelled)
    outcomes = []
    worker.finished_download.connect(
        lambda path, error: outcomes.append((path, error, [r.exists() for r in roots]))
    )
    return worker, roots, outcomes


@pytest.mark.parametrize("known_size", [True, False], ids=["content-length", "unknown-size"])
def test_download_progress_tracks_received_bytes_through_final_chunk(monkeypatch, tmp_path, known_size):
    payload = b"x" * (2 * CHUNK + 19)
    response = Response(payload, len(payload) if known_size else None)
    worker, roots, outcomes = prepare_worker(monkeypatch, tmp_path, response)
    progress = getattr(worker, "progress", None)
    assert progress is not None, "UpdateDownloadWorker needs a two-argument Qt progress signal"
    assert callable(getattr(progress, "connect", None)), "progress must be a bound Qt signal"
    events = []
    progress.connect(lambda received, total: events.append((received, total)))
    worker.run()

    assert len(outcomes) == 1
    path, error, existed_at_finish = outcomes[0]
    assert error is None
    assert Path(path).read_bytes() == payload
    assert Path(path).parent == roots[0]
    assert worker.download_path == path
    assert existed_at_finish == [True], "Successful download ownership passes to ControlPanel"
    assert response.closed
    assert response.read_sizes == [CHUNK] * 4
    assert events, "At least final byte count must be delivered"
    assert events[-1] == (len(payload), len(payload) if known_size else 0)
    assert all(isinstance(n, int) and isinstance(t, int) for n, t in events)
    assert all(0 <= n <= len(payload) for n, _ in events)
    assert [n for n, _ in events] == sorted(n for n, _ in events)
    assert all(t == (len(payload) if known_size else 0) for _, t in events)
    assert any(0 < n < len(payload) for n, _ in events), "Progress must stream, not only finish"


@pytest.mark.parametrize("failure", ["transport", "cancel-before-read", "cancel-midstream", "cancel-after-eof"])
def test_worker_failure_cleans_temp_before_finished_signal(monkeypatch, tmp_path, failure):
    response = Response(b"x" * (CHUNK + 1), fail_after=CHUNK if failure == "transport" else None)
    def cancelled():
        return (failure == "cancel-before-read"
                or failure == "cancel-midstream" and bool(response.read_sizes)
                or failure == "cancel-after-eof" and response.eof)
    worker, roots, outcomes = prepare_worker(monkeypatch, tmp_path, response, cancelled)
    worker.run()
    assert len(outcomes) == 1
    path, error, existed_at_finish = outcomes[0]
    assert path is None and error
    assert roots and not any(existed_at_finish), "Cleanup must precede failure notification"
    assert all(not root.exists() for root in roots)
    assert worker.download_path is None
    assert response.closed
    if failure.startswith("cancel-"):
        assert error == "download_cancelled"
    if failure == "cancel-before-read":
        assert response.read_sizes == []
    elif failure == "cancel-after-eof":
        assert response.eof


def isolated_method(name, **overrides):
    """Inject globals, not implementation substitutions or exact source matches."""
    method = getattr(main.ControlPanel, name)
    source = textwrap.dedent(inspect.getsource(method))
    namespace = dict(main.__dict__)
    namespace.update(overrides)
    exec(compile(source, str(ROOT / "main.py"), "exec"), namespace)
    return namespace[name]


def panel_stub():
    return SimpleNamespace(
        update_check_enabled=True, update_channel="stable",
        _update_worker=None, _update_download_worker=None,
        _update_flow_busy=False, _updates_stopping=False, _update_install_handoff=False,
        _pending_update_release=dict(RELEASE),
        _set_update_status=Mock(), _set_update_check_enabled=Mock(),
        _on_update_result=Mock(), _on_update_downloaded=Mock(),
        _on_update_progress=Mock(), _set_update_progress=Mock(),
        update_progress_bar=Mock(), btn_download_update=Mock(), btn_cancel_update=Mock(),
        pause_callbacks=Mock(), resume_callbacks=Mock(), styleSheet=lambda: "",
        save_settings=Mock(), save_project=Mock(return_value=True), project_dirty=False,
        confirm_unsaved_changes=Mock(return_value=True),
        lifecycle=SimpleNamespace(is_exiting=lambda: False, _quit_dialog_showing=False, _do_quit=Mock()),
    )


def message_boxes(answer):
    dialog = Mock()
    dialog.exec.return_value = answer
    constructor = Mock(return_value=dialog)
    constructor.StandardButton = main.QMessageBox.StandardButton
    return constructor


def panel_globals(boxes, **extra):
    return dict(QMessageBox=boxes, tr=lambda key: key,
                trf=lambda key, **values: (key, values), track_event=Mock(), **extra)


def test_checking_and_downloading_have_distinct_status_and_wire_progress():
    panel = panel_stub()
    check_worker = Mock()
    isolated_method("check_for_updates", **panel_globals(
        message_boxes(main.QMessageBox.StandardButton.Yes),
        UpdateCheckWorker=Mock(return_value=check_worker),
    ))(panel)
    checking = panel._set_update_status.call_args.args[0]
    check_worker.start.assert_called_once()
    check_worker.isRunning.return_value = False

    progress_handler = isolated_method("_on_update_progress", **panel_globals(
        message_boxes(main.QMessageBox.StandardButton.Yes),
    ))
    panel._on_update_progress.side_effect = lambda received, total: progress_handler(panel, received, total)
    download_worker = Mock()
    isolated_method("_offer_update_page", **panel_globals(
        message_boxes(main.QMessageBox.StandardButton.Yes),
        UpdateDownloadWorker=Mock(return_value=download_worker),
    ))(panel, dict(RELEASE))
    downloading = panel._set_update_status.call_args.args[0]
    download_worker.start.assert_called_once()
    assert checking != downloading, "Download must not continue displaying the checking state"
    download_worker.progress.connect.assert_called_once()
    callback = download_worker.progress.connect.call_args.args[0]
    assert callable(callback)
    callback(CHUNK, 2 * CHUNK)
    panel._on_update_progress.assert_called_with(CHUNK, 2 * CHUNK)


def test_settings_constructs_and_adds_progress_bar():
    """Structural contract: actual QProgressBar construction and layout membership."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(main.ControlPanel.build_settings_panel)))
    progress_fields = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        constructor = node.value.func
        if getattr(constructor, "id", getattr(constructor, "attr", None)) != "QProgressBar":
            continue
        for target in node.targets:
            if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                progress_fields.add(target.attr)
    assert progress_fields, "Settings must create a persistent QProgressBar for downloads"
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and node.func.attr == "addWidget"
               and any(isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name)
                       and arg.value.id == "self" and arg.attr in progress_fields for arg in node.args)
               for node in ast.walk(tree)), "Progress control must be present in a layout"


@pytest.fixture
def install_case(tmp_path, monkeypatch):
    monkeypatch.setenv("MSD_TEST_INHERITED_ENV", "keep-parent-value")
    install = tmp_path / "install"
    install.mkdir()
    (install / "MyScreenDraw.exe").write_bytes(b"old non-executable fixture")
    download = tmp_path / "download"
    download.mkdir()
    archive = download / "update.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("MyScreenDraw.exe", b"new non-executable fixture")
    scripts = tmp_path / "script"
    scripts.mkdir()
    script = scripts / "apply.ps1"
    script.write_text("# Never executed", encoding="utf-8")
    panel = panel_stub()
    make_batch = Mock(return_value=str(script))
    popen = Mock()
    boxes = message_boxes(main.QMessageBox.StandardButton.Yes)
    method = isolated_method("_on_update_downloaded", **panel_globals(
        boxes, APP_DIR=str(install), make_update_batch=make_batch, sys=SimpleNamespace(frozen=True),
        subprocess=SimpleNamespace(**{**vars(main.subprocess), "Popen": popen}),
    ))
    return SimpleNamespace(panel=panel, install=install, archive=archive, script=script,
                           make_batch=make_batch, popen=popen, boxes=boxes, method=method)


def test_source_layout_rejected_before_handoff_without_quitting(install_case):
    case = install_case
    (case.install / "MyScreenDraw.exe").unlink()
    (case.install / "main.py").write_text("# source checkout", encoding="utf-8")
    case.method(case.panel, str(case.archive), None)
    case.make_batch.assert_not_called()
    case.popen.assert_not_called()
    case.panel.lifecycle._do_quit.assert_not_called()
    assert not case.panel._update_install_handoff
    assert not case.archive.parent.exists()
    assert any(call.args[0] == "update_source_install_unsupported"
               for call in case.panel._set_update_status.call_args_list)
    assert not case.panel._update_flow_busy


def test_install_passes_target_version_and_owner_pid(install_case):
    case = install_case
    case.method(case.panel, str(case.archive), None)
    case.make_batch.assert_called_once()
    bound = inspect.signature(main.make_update_batch).bind(*case.make_batch.call_args.args,
                                                         **case.make_batch.call_args.kwargs)
    bound.apply_defaults()
    assert bound.arguments["zip_path"] == str(case.archive)
    assert bound.arguments["install_dir"] == str(case.install)
    assert main.parse_version(bound.arguments["version"]) == main.parse_version("6.0.1")
    assert bound.arguments["owner_pid"] == os.getpid()
    case.popen.assert_called_once()
    case.panel.lifecycle._do_quit.assert_called_once_with(save=True)
    assert case.panel._update_install_handoff
    assert case.archive.exists() and case.script.exists(), "Detached installer owns these paths"


@pytest.mark.parametrize("failure", ["cancel", "worker-error", "download-cancelled", "bad-zip", "launch-error", "save-cancel", "stopping"])
def test_download_completion_failure_or_cancel_keeps_app_running_and_cleans(install_case, failure):
    case = install_case
    if failure == "cancel":
        case.boxes.return_value.exec.return_value = main.QMessageBox.StandardButton.Cancel
    elif failure == "bad-zip":
        case.archive.write_bytes(b"not a zip")
    elif failure == "launch-error":
        case.popen.side_effect = OSError("simulated launch failure")
    elif failure == "save-cancel":
        case.panel.project_dirty = True
        case.panel.save_project.return_value = False
        case.panel.confirm_unsaved_changes.return_value = False
    elif failure == "stopping":
        case.panel._updates_stopping = True
    error = {"worker-error": "error_OSError", "download-cancelled": "download_cancelled"}.get(failure)
    case.method(case.panel, str(case.archive), error)
    if failure == "download-cancelled":
        case.panel._set_update_status.assert_any_call("update_download_cancelled")
    case.panel.lifecycle._do_quit.assert_not_called()
    assert not case.panel._update_install_handoff
    assert not case.archive.parent.exists()
    assert not case.panel._update_flow_busy
    case.panel.resume_callbacks.assert_called_once()
    if failure == "launch-error":
        case.popen.assert_called_once()
        assert not case.script.parent.exists()
    else:
        case.popen.assert_not_called()
        case.make_batch.assert_not_called()


@pytest.mark.parametrize("layout", ["source", "exe-is-directory", "portable"])
def test_install_layout_requires_executable_file(tmp_path, layout):
    check_layout = getattr(main, "install_layout_supported", None)
    assert callable(check_layout), "An explicit portable-install preflight is required"
    (tmp_path / "main.py").write_text("# source checkout", encoding="utf-8")
    if layout == "exe-is-directory":
        (tmp_path / "MyScreenDraw.exe").mkdir()
    elif layout == "portable":
        (tmp_path / "MyScreenDraw.exe").write_bytes(b"fixture")
    assert bool(check_layout(str(tmp_path))) == (layout == "portable")


def test_installer_handoff_resets_pyinstaller_env_and_hides_powershell(install_case):
    case = install_case
    original_reset = os.environ.get("PYINSTALLER_RESET_ENVIRONMENT")
    case.method(case.panel, str(case.archive), None)
    case.popen.assert_called_once()
    args, kwargs = case.popen.call_args
    assert Path(args[0][0]).name.lower() == "powershell.exe"
    assert str(case.script) in args[0]
    assert kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
    assert kwargs["env"]["MSD_TEST_INHERITED_ENV"] == "keep-parent-value"
    assert os.environ.get("PYINSTALLER_RESET_ENVIRONMENT") == original_reset
    hidden_flag = getattr(main.subprocess, "CREATE_NO_WINDOW", 0x08000000)
    startup = kwargs.get("startupinfo")
    hidden_startup = (startup is not None
                      and startup.dwFlags & getattr(main.subprocess, "STARTF_USESHOWWINDOW", 1)
                      and startup.wShowWindow == getattr(main.subprocess, "SW_HIDE", 0))
    assert kwargs.get("creationflags", 0) & hidden_flag or hidden_startup
    assert not kwargs.get("shell", False)


@pytest.mark.parametrize("running", [False, True])
def test_cancel_download_is_cooperative_and_does_not_quit(running):
    method = getattr(main.ControlPanel, "cancel_update_download", None)
    assert callable(method), "A user-visible download cancellation handler is required"
    panel = panel_stub()
    worker = Mock()
    worker.isRunning.return_value = running
    panel._update_download_worker = worker
    isolated_method("cancel_update_download", **panel_globals(
        message_boxes(main.QMessageBox.StandardButton.Cancel),
    ))(panel)
    if running:
        worker.requestInterruption.assert_called_once()
    else:
        worker.requestInterruption.assert_not_called()
    worker.terminate.assert_not_called()
    worker.wait.assert_not_called()
    panel.lifecycle._do_quit.assert_not_called()


def test_progress_callback_updates_offscreen_bar_for_known_and_unknown_size():
    method = getattr(main.ControlPanel, "_on_update_progress", None)
    assert callable(method), "Download progress must reach a ControlPanel handler"
    from PyQt6.QtWidgets import QApplication, QProgressBar
    app = QApplication.instance() or QApplication([])
    assert app.platformName() == "offscreen"
    bar = QProgressBar()  # Never shown; no ControlPanel or application runtime is started.
    panel = panel_stub()
    panel.update_progress_bar = bar
    callback = isolated_method("_on_update_progress", **panel_globals(
        message_boxes(main.QMessageBox.StandardButton.Cancel),
    ))
    try:
        callback(panel, CHUNK, 2 * CHUNK)
        assert bar.maximum() > bar.minimum()
        fraction = (bar.value() - bar.minimum()) / (bar.maximum() - bar.minimum())
        assert fraction == pytest.approx(0.5, abs=0.01)
        callback(panel, CHUNK, 0)
        assert bar.minimum() == bar.maximum() == 0
        callback(panel, 2 * CHUNK, 2 * CHUNK)
        assert bar.maximum() > bar.minimum()
        assert bar.value() == bar.maximum()
    finally:
        bar.close()


def test_source_runtime_refuses_install_even_if_an_exe_is_present(install_case):
    case = install_case
    case.method.__globals__["sys"] = SimpleNamespace(frozen=False)
    case.method(case.panel, str(case.archive), None)
    case.make_batch.assert_not_called()
    case.popen.assert_not_called()
    case.panel.lifecycle._do_quit.assert_not_called()
    case.panel._set_update_status.assert_any_call("update_source_install_unsupported")


def test_queued_completion_blocks_reentry_after_download_thread_exits():
    panel = panel_stub()
    panel._update_download_active = True
    panel._update_download_worker = Mock()
    panel._update_download_worker.isRunning.return_value = False
    boxes = message_boxes(main.QMessageBox.StandardButton.Yes)
    method = isolated_method("_offer_update_page", **panel_globals(boxes))
    method(panel, RELEASE)
    boxes.assert_not_called()
    panel.pause_callbacks.assert_not_called()
