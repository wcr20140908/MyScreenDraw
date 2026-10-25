# SPDX-License-Identifier: GPL-3.0-or-later
"""Startup preferences use only a bounded local JSON read and process environment."""
import json
from pathlib import Path

import pytest

import startup_preferences as preferences


def test_read_three_fields_without_modifying_the_file(tmp_path):
    config = tmp_path / "config.json"
    content = json.dumps({"language": "de", "ui_scale_percent": 150,
                          "never_prompt_autosave_recovery": True, "other": "unchanged"}).encode()
    config.write_bytes(content)
    value = preferences.read_interface_preferences(config)
    assert (value.language, value.ui_scale_percent, value.never_prompt_autosave_recovery) == ("de", 150, True)
    assert config.read_bytes() == content


@pytest.mark.parametrize("content", [b"not json", b"null", b"[]", b'{"language":{}}'])
def test_unreadable_or_invalid_json_defaults(tmp_path, content):
    config = tmp_path / "config.json"
    config.write_bytes(content)
    assert preferences.read_interface_preferences(config) == preferences.InterfacePreferences()
    assert preferences.read_interface_preferences(tmp_path / "missing.json") == preferences.InterfacePreferences()


def test_oversized_startup_config_uses_defaults(tmp_path):
    config = tmp_path / "config.json"
    config.write_bytes(b" " * (preferences.MAX_SETTINGS_BYTES + 1))
    assert preferences.read_interface_preferences(config) == preferences.InterfacePreferences()


def test_scale_preserves_existing_environment_factor_without_compounding_on_restart():
    environment = {"QT_SCALE_FACTOR": "1.25"}
    preferences.apply_scale_environment(150, environment)
    assert float(environment["QT_SCALE_FACTOR"]) == pytest.approx(1.875)
    preferences.apply_scale_environment(150, environment)
    assert float(environment["QT_SCALE_FACTOR"]) == pytest.approx(1.875)
    preferences.apply_scale_environment(100, environment)
    assert float(environment["QT_SCALE_FACTOR"]) == pytest.approx(1.25)
    preferences.apply_scale_environment(200, environment)
    assert float(environment["QT_SCALE_FACTOR"]) == pytest.approx(2.5)


@pytest.mark.parametrize("bad", ["bad", "nan", "inf", "-1", "0"])
def test_invalid_inherited_factor_is_not_used(bad):
    environment = {"QT_SCALE_FACTOR": bad}
    preferences.apply_scale_environment(150, environment)
    assert float(environment["QT_SCALE_FACTOR"]) == 1.5


def test_scale_percent_is_an_integer_and_bounded():
    for bad in (None, True, False, [], {}, "150", 125.5, float("nan"), float("inf")):
        assert preferences.normalize_scale(bad) == 100
    assert preferences.normalize_scale(74) == 75
    assert preferences.normalize_scale(201) == 200
    assert preferences.normalize_scale(125.0) == 125


def test_large_integer_scale_is_clamped_without_float_overflow(tmp_path):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"language": "de", "ui_scale_percent": 10 ** 400}), encoding="utf-8")
    value = preferences.read_interface_preferences(config)
    assert value.language == "de"
    assert value.ui_scale_percent == 200
    assert preferences.normalize_scale(-(10 ** 400)) == 75


def test_deeply_nested_json_defaults_instead_of_crashing_startup(tmp_path):
    config = tmp_path / "config.json"
    config.write_text("[" * 2000 + "0" + "]" * 2000, encoding="utf-8")
    assert preferences.read_interface_preferences(config) == preferences.InterfacePreferences()


def test_large_finite_base_does_not_overflow_intermediate_multiplication():
    environment = {"QT_SCALE_FACTOR": "1e308"}
    assert preferences.apply_scale_environment(100, environment) == 1e308
    assert preferences.apply_scale_environment(200, environment) == 2.0
