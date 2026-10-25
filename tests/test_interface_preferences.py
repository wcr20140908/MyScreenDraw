# SPDX-License-Identifier: GPL-3.0-or-later
"""Interface settings and startup behavior, with isolated runtime data."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest
from PyQt6.QtWidgets import QApplication

import i18n
import main
from test_document_safety_610 import document

ROOT = Path(__file__).resolve().parents[1]


def test_settings_controls_save_language_scale_and_never_prompt(document):
    panel, canvas = document
    panel.open_settings_panel()
    language = panel.language_combo
    assert language.count() == 9
    assert [language.itemData(i) for i in range(language.count())] == ["auto", *i18n._LANGS]
    assert language.itemText(language.findData("de")) == "Deutsch"
    assert language.itemText(language.findData("ja")) == "日本語"
    before = canvas.document_signature()
    active_language = i18n.CURRENT
    language.setCurrentIndex(language.findData("de"))
    panel.ui_scale_slider.setValue(150)
    panel.never_prompt_recovery_checkbox.setChecked(True)
    stored = json.loads(Path(main.CONFIG_FILE).read_text(encoding="utf-8"))
    assert (stored["language"], stored["ui_scale_percent"], stored["never_prompt_autosave_recovery"]) == ("de", 150, True)
    assert i18n.CURRENT == active_language, "Pending settings apply only after restart"
    assert canvas.document_signature() == before
    assert panel.ui_scale_value_label.text() == main.trf("ui_scale_value", value=150)
    assert panel.interface_restart_hint.text() == main.tr("interface_restart_hint")
    assert panel.interface_restart_hint.wordWrap()


def test_reloading_controls_has_no_settings_write_or_language_side_effect(document, monkeypatch):
    panel, canvas = document
    panel.open_settings_panel()
    main.atomic_write_json(main.CONFIG_FILE, {"language": "ja", "ui_scale_percent": 175,
                           "never_prompt_autosave_recovery": True, "update_check_enabled": False})
    writer = Mock()
    monkeypatch.setattr(panel, "save_settings", writer)
    language = i18n.CURRENT
    panel.load_settings()
    assert panel.language_combo.currentData() == "ja"
    assert panel.ui_scale_slider.value() == 175
    assert panel.never_prompt_recovery_checkbox.isChecked()
    assert i18n.CURRENT == language
    writer.assert_not_called()


@pytest.mark.parametrize("bad", [None, True, [], {}, "unsupported"])
def test_invalid_language_setting_keeps_other_preferences(document, bad):
    panel, _ = document
    main.atomic_write_json(main.CONFIG_FILE, {"language": bad, "ui_scale_percent": 150,
                           "never_prompt_autosave_recovery": True, "update_check_enabled": False})
    panel.load_settings()
    assert panel.language == "auto"
    assert panel.ui_scale_percent == 150
    assert panel.never_prompt_autosave_recovery is True
    assert panel.update_check_enabled is False


@pytest.mark.parametrize("bad", [None, True, [], {}, "150", float("inf"), float("nan")])
def test_invalid_scale_uses_default_without_blocking_other_settings(document, bad):
    panel, _ = document
    # Exercise normalization through the public setter for non-JSON finite values.
    panel.set_ui_scale(bad, persist=False)
    assert panel.ui_scale_percent == 100
    panel.set_language_preference("fr", persist=False)
    panel.set_never_prompt_autosave_recovery(True, persist=False)
    panel.save_settings()
    assert panel.collect_settings()["language"] == "fr"
    assert panel.collect_settings()["never_prompt_autosave_recovery"] is True


@pytest.mark.parametrize("value,expected", [(25, 75), (250, 200), (125.0, 125)])
def test_scale_bounds_and_integral_json_numbers(document, value, expected):
    panel, _ = document
    panel.set_ui_scale(value, persist=False)
    assert panel.ui_scale_percent == expected


def test_never_prompt_skips_startup_but_manual_recovery_and_autosave_remain(document, monkeypatch):
    panel, canvas = document
    recover = Mock(return_value=True)
    monkeypatch.setattr(panel, "_restore_history_operation", recover)
    interval = panel.autosave_timer.interval()
    panel.set_never_prompt_autosave_recovery(True)
    assert panel.offer_autosave_restore() is False
    recover.assert_not_called()
    assert panel.autosave_timer.interval() == interval
    assert panel.open_recovery_from_file_panel() is True
    recover.assert_called_once_with(allow_private=True)
    recover.reset_mock()
    panel.set_never_prompt_autosave_recovery(False)
    assert panel.offer_autosave_restore() is True
    recover.assert_called_once_with()


@pytest.mark.parametrize("bad", [None, "true", 1, [], {}])
def test_never_prompt_requires_boolean_and_defaults_to_prompting(document, bad):
    panel, _ = document
    main.atomic_write_json(main.CONFIG_FILE, {"never_prompt_autosave_recovery": bad})
    panel.load_settings()
    assert panel.never_prompt_autosave_recovery is False


def test_startup_preferences_precede_application_and_translator_construction():
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8-sig"))
    entry = next(node for node in tree.body if isinstance(node, ast.If)
                 and isinstance(node.test, ast.Compare)
                 and ast.unparse(node.test) == "__name__ == '__main__'")
    source = ast.unparse(entry)
    assert source.index("initialize_interface_preferences()") < source.index("QApplication(sys.argv)")
    assert source.index("initialize_interface_preferences()") < source.index("install_qt_translations(app)")


def test_new_setting_strings_are_complete_in_every_language():
    for key in ("interface_language", "language_system", "ui_scale_value", "interface_restart_hint",
                "never_prompt_autosave_recovery", "never_prompt_autosave_recovery_hint",
                "submenu_animations", "submenu_animations_hint"):
        assert key in i18n._BASE
        assert len(i18n._BASE[key]) == 8
        assert all(value.strip() for value in i18n._BASE[key])


@pytest.mark.parametrize("language", ["zh", "en", "fr", "es", "de", "ru", "ko", "ja"])
def test_language_startup_uses_saved_choice_and_qt_dialog_translation(tmp_path, language):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"language": language}), encoding="utf-8")
    script = r'''
import json, sys
from pathlib import Path
import main, i18n
main.CONFIG_FILE = sys.argv[1]
main.initialize_interface_preferences()
from PyQt6.QtWidgets import QApplication, QFileDialog, QPushButton
app = QApplication([])
main.install_qt_translations(app)
dialog = QFileDialog()
dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
print(json.dumps({"language": i18n.CURRENT, "module_language": main.CURRENT,
                  "settings": main.tr("settings"), "buttons": [b.text() for b in dialog.findChildren(QPushButton)]}))
'''
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", MYSCREENDRAW_NO_KEYBOARD="1", PYNPUT_BACKEND="dummy")
    result = subprocess.run([sys.executable, "-c", script, str(config)], cwd=ROOT, env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["language"] == data["module_language"] == language
    assert data["settings"] == i18n.TEXT[language]["settings"]
    expected = {"zh": "打开(&O)", "en": "&Open", "fr": "&Ouvrir", "es": "&Abrir", "de": "&Öffnen",
                "ru": "&Открыть", "ko": "열기(&O)", "ja": "開く(&O)"}
    assert expected[language] in data["buttons"]


@pytest.mark.parametrize("language", ["auto", "fr"])
def test_normal_restart_uses_saved_choice_instead_of_inherited_language(tmp_path, language):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"language": language, "ui_scale_percent": 125}), encoding="utf-8")
    script = r'''
import json, sys
import main, i18n
main.CONFIG_FILE = sys.argv[1]
main.initialize_interface_preferences()
from PyQt6.QtWidgets import QApplication
app = QApplication([])
print(json.dumps({"language": i18n.CURRENT, "system": i18n.system_language(),
                  "dpr": app.primaryScreen().devicePixelRatio()}))
'''
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", MYSCREENDRAW_NO_KEYBOARD="1",
               PYNPUT_BACKEND="dummy", QT_SCALE_FACTOR="1.5",
               MYSCREENDRAW_BASE_QT_SCALE_FACTOR="1", MYSCREENDRAW_ACTIVE_LANGUAGE="de")
    result = subprocess.run([sys.executable, "-c", script, str(config)], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["language"] == (data["system"] if language == "auto" else language)
    assert data["dpr"] == pytest.approx(1.25)


def test_practice_startup_inherits_active_language_and_scale_without_reading_settings(tmp_path):
    script = r'''
import json, sys
from pathlib import Path
from unittest.mock import Mock
import main, i18n
from runtime_paths import RuntimeContext, RuntimePaths
root = Path.cwd()
paths = RuntimePaths.create_practice(root, root, temp_root=Path(sys.argv[1]))
main.RUNTIME_CONTEXT = RuntimeContext(paths)
main.read_interface_preferences = Mock(side_effect=AssertionError("Practice read ordinary settings"))
main.initialize_interface_preferences()
from PyQt6.QtWidgets import QApplication
app = QApplication([])
print(json.dumps({"language": i18n.CURRENT, "module_language": main.CURRENT,
                  "dpr": app.primaryScreen().devicePixelRatio()}))
'''
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", MYSCREENDRAW_NO_KEYBOARD="1",
               PYNPUT_BACKEND="dummy", QT_SCALE_FACTOR="1.5",
               MYSCREENDRAW_BASE_QT_SCALE_FACTOR="1", MYSCREENDRAW_ACTIVE_LANGUAGE="de")
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["language"] == data["module_language"] == "de"
    assert data["dpr"] == pytest.approx(1.5)


def test_utf8_bom_settings_have_consistent_startup_and_panel_preferences(document):
    panel, _ = document
    Path(main.CONFIG_FILE).write_text(json.dumps({"language": "ja", "ui_scale_percent": 125,
                                    "never_prompt_autosave_recovery": True}), encoding="utf-8-sig")
    startup = main.read_interface_preferences(main.CONFIG_FILE)
    panel.load_settings()
    assert (panel.language, panel.ui_scale_percent, panel.never_prompt_autosave_recovery) == (
        startup.language, startup.ui_scale_percent, startup.never_prompt_autosave_recovery)
