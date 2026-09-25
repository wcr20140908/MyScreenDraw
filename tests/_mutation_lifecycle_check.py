"""In-memory mutations: do not modify production files during verification."""
import inspect
import io
import os
import sys
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app_lifecycle
import test_lifecycle_regressions as regressions


def mutated(cls, method, old, new):
    original = getattr(cls, method)
    source = textwrap.dedent(inspect.getsource(original))
    assert old in source, (method, old)
    namespace = {}
    exec(compile(source.replace(old, new, 1), "<mutation>", "exec"), original.__globals__, namespace)
    return namespace[method]


cases = [
    ("cancel restores hidden UI", "_quit_app", "self.state = state_before_quit",
     "self.state = state_before_quit\n        self.restore_from_background()",
     "test_close_escape_cancel_and_save_failure_preserve_each_state"),
    ("quit twice", "_do_quit", 'if getattr(self, "_quit_done", False):', 'if False:',
     "test_quitting_is_idempotent_and_cannot_restore_or_hide"),
    ("save failure exits", "_quit_app", 'if success:', 'if True:',
     "test_close_escape_cancel_and_save_failure_preserve_each_state"),
    ("tray skips confirmation", "_quit_app", 'self._quit_dialog_showing = True',
     'self._do_quit(False)\n    return\n    self._quit_dialog_showing = True',
     "test_repeated_close_requires_another_confirmation"),
]
cases.append(("restart save failure starts new process", "_restart_app",
              'if not success:', 'if False:',
              "test_restart_save_failure_never_starts_or_quits"))
cases.extend([
    ("tray confirmation runs inside mouse event", "_apply_menu_colors",
     'QTimer.singleShot(0, fn)', 'fn()',
     "test_tray_label_defers_confirmation_until_menu_hidden"),
    ("tray menu stays open during confirmation", "_apply_menu_colors",
     'self.tray_menu.hide()', 'pass',
     "test_tray_label_defers_confirmation_until_menu_hidden"),
])
failed = []
for label, method, old, new, test in cases:
    replacement = mutated(app_lifecycle.AppLifecycleManager, method, old, new)
    with patch.object(app_lifecycle.AppLifecycleManager, method, replacement):
        result = unittest.TextTestRunner(stream=io.StringIO()).run(
            unittest.TestSuite([regressions.QuitRegressionTests(test)]))
    killed = bool(result.failures) and not result.errors
    print(("PASS " if killed else "FAIL ") + label + " mutation detected", flush=True)
    if not killed:
        failed.append(label)
assert not failed, failed

import main
import persistence
from test_persistence_safety import FileSizeLimitTests
extra = [
    (main.ControlPanel, "restore_from_restart", 'if not ok:', 'if False:',
     regressions.QuitRegressionTests("test_failed_restart_restore_keeps_recovery_file")),
    (main.ControlPanel, "_sync_split_geometry",
     'if follow and self.orientation == "portrait" and not getattr(self, "_toolbar_detached", False) and toolbar.isVisible():',
     'if False:', regressions.FloatingLifecycleTests("test_portrait_group_near_bottom_does_not_cover_logo")),
    (app_lifecycle.AppLifecycleManager, "hide_to_background", 'self.panel.close_thumbnail_panel()',
     'pass', regressions.FloatingLifecycleTests("test_preview_hide_stops_timer_and_restore_does_not_reopen")),
    (main.ControlPanel, "resume_callbacks",
     "if hasattr(self, 'lifecycle') and self.lifecycle.state in (LifecycleState.HIDDEN, LifecycleState.QUITTING):",
     'if False:', regressions.FloatingLifecycleTests("test_preview_hide_stops_timer_and_restore_does_not_reopen")),
]
for cls, method, old, new, test in extra:
    with patch.object(cls, method, mutated(cls, method, old, new)):
        result = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestSuite([test]))
    assert result.failures and not result.errors, (method, result.errors)
    print("PASS " + method + " mutation detected", flush=True)
with patch.object(persistence, "read_json_maybe_gz", mutated(persistence, "read_json_maybe_gz",
                  'if len(payload) > MAX_PROJECT_BYTES:', 'if False:')):
    result = unittest.TextTestRunner(stream=io.StringIO()).run(unittest.TestSuite([
        FileSizeLimitTests("test_compressed_autosave_has_decompressed_limit")]))
assert result.failures and not result.errors
print("PASS decompressed size mutation detected", flush=True)
