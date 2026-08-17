"""Pure-logic coverage for i18n completeness and JSON-safe telemetry helpers."""
import importlib
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class I18nCompletenessTests(unittest.TestCase):
    def test_all_languages_share_the_same_keys(self):
        from i18n import TEXT, _LANGS, tr

        base_keys = set(TEXT["zh"])
        self.assertTrue(base_keys)
        for lang in _LANGS:
            self.assertEqual(set(TEXT[lang]), base_keys, lang)
            for key, value in TEXT[lang].items():
                self.assertIsInstance(value, str)
                self.assertTrue(value.strip(), f"{lang}.{key} empty")

        required = {
            "export_failed",
            "export_done",
            "export_png_summary",
            "export_pdf_summary",
            "save_failed",
            "open_failed",
            "light_theme",
            "dark_theme",
            "no_screen",
            "theme",
            "exit",
        }
        self.assertTrue(required.issubset(base_keys))
        sample = tr("export_failed")
        self.assertNotEqual(sample, "export_failed")
        self.assertIn("{count}", TEXT["en"]["export_png_summary"])
        self.assertIn("{path}", TEXT["en"]["export_pdf_summary"])


class SpdxHeaderTests(unittest.TestCase):
    """GPL 合规：每个源文件都必须在文件头携带 SPDX 标识（见 docs/provenance-audit.md）。"""

    SOURCES = ("main.py", "persistence.py", "calculator.py", "display_utils.py",
               "i18n.py", "version.py", "eps_export.py")

    def test_all_source_files_carry_spdx_headers(self):
        for name in self.SOURCES:
            with self.subTest(file=name):
                head = (ROOT / name).read_text(encoding="utf-8").splitlines()[:3]
                self.assertTrue(
                    any("SPDX-License-Identifier: GPL-3.0-or-later" in line for line in head),
                    f"{name} 缺少 SPDX-License-Identifier 头",
                )


class TelemetryHelperTests(unittest.TestCase):
    def test_json_safe_handles_non_serializable_values(self):
        # Import helpers without starting the GUI.
        with mock.patch.dict(os.environ, {"QT_QPA_PLATFORM": "offscreen"}, clear=False):
            import main as app

        payload = app._json_safe(
            {
                "ok": 1,
                "nan": float("nan"),
                "inf": float("inf"),
                "nested": {"pts": (1, 2), "set": {3, 4}},
                "obj": object(),
            }
        )
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        self.assertIn("ok", encoded)
        self.assertIn("nan", encoded)
        self.assertNotIn("NaN", encoded)

        with tempfile.TemporaryDirectory() as tmp:
            events = os.path.join(tmp, "events.jsonl")
            with mock.patch.object(app, "DATA_DIR", tmp), mock.patch.object(app, "TELEMETRY_FILE", events):
                app.track_event("unit_test", value=float("nan"), nested={"a": object()})
            with open(events, encoding="utf-8") as handle:
                line = handle.readline()
            data = json.loads(line)
            self.assertEqual(data["event"], "unit_test")
            self.assertIn("payload", data)


if __name__ == "__main__":
    unittest.main()
