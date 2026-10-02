"""Native passthrough style checks; real cross-process input is tested by the opt-in probe."""
import os
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import main


class NativePassthroughTests(unittest.TestCase):
    def fake_user32(self, initial):
        state = {"style": initial}
        api = Mock()
        api.GetWindowLongPtrW.side_effect = lambda *_: state["style"]
        def set_style(_hwnd, _index, value):
            old = state["style"]
            state["style"] = value
            return old
        api.SetWindowLongPtrW.side_effect = set_style
        return api, state

    def test_toggle_preserves_other_styles_and_keeps_layered(self):
        initial = main.WS_EX_TOOLWINDOW | 0x08000000
        api, state = self.fake_user32(initial)
        with patch.object(main.QApplication, "platformName", return_value="windows"), patch.object(main.ctypes.windll, "user32", api):
            main.set_canvas_passthrough(123, True)
            self.assertEqual(state["style"], initial | main.WS_EX_LAYERED | main.WS_EX_TRANSPARENT)
            main.set_canvas_passthrough(123, False)
            self.assertEqual(state["style"], initial | main.WS_EX_LAYERED)

    def test_heartbeat_does_not_rewrite_unchanged_native_style(self):
        api, state = self.fake_user32(main.WS_EX_LAYERED | main.WS_EX_TRANSPARENT)
        with patch.object(main.QApplication, "platformName", return_value="windows"), patch.object(main.ctypes.windll, "user32", api):
            for _ in range(3):
                main.set_canvas_passthrough(123, True)
        api.SetWindowLongPtrW.assert_not_called()

    def test_failed_native_change_is_not_reported_as_success(self):
        api, state = self.fake_user32(main.WS_EX_LAYERED)
        api.SetWindowLongPtrW.side_effect = None
        with patch.object(main.QApplication, "platformName", return_value="windows"), patch.object(main.ctypes.windll, "user32", api):
            with self.assertRaises(OSError):
                main.set_canvas_passthrough(123, True)


if __name__ == "__main__":
    unittest.main()
