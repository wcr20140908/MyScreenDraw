# SPDX-License-Identifier: GPL-3.0-or-later
"""Validated interface preferences read before QApplication is constructed."""
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path

LANGUAGE_NAMES = {
    "zh": "中文", "en": "English", "fr": "Français", "es": "Español",
    "de": "Deutsch", "ru": "Русский", "ko": "한국어", "ja": "日本語",
}
SCALE_MIN = 75
SCALE_MAX = 200
MAX_SETTINGS_BYTES = 4 * 1024 * 1024
# Qt's global factor is inherited by restart/teaching children. Remember the
# external base so a restart replaces our factor instead of multiplying it again.
_BASE_SCALE_ENV = "MYSCREENDRAW_BASE_QT_SCALE_FACTOR"
ACTIVE_LANGUAGE_ENV = "MYSCREENDRAW_ACTIVE_LANGUAGE"


def normalize_language(value):
    return value if isinstance(value, str) and value in ("auto", *LANGUAGE_NAMES) else "auto"


def normalize_scale(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 100
    if isinstance(value, float) and (not math.isfinite(value) or not value.is_integer()):
        return 100
    return max(SCALE_MIN, min(SCALE_MAX, int(value)))


@dataclass(frozen=True)
class InterfacePreferences:
    language: str = "auto"
    ui_scale_percent: int = 100
    never_prompt_autosave_recovery: bool = False

    @classmethod
    def from_settings(cls, settings):
        if not isinstance(settings, dict):
            return cls()
        return cls(normalize_language(settings.get("language")),
                   normalize_scale(settings.get("ui_scale_percent")),
                   settings.get("never_prompt_autosave_recovery") is True)


def read_interface_preferences(config_file):
    try:
        with Path(config_file).open("rb") as stream:
            content = stream.read(MAX_SETTINGS_BYTES + 1)
        if len(content) > MAX_SETTINGS_BYTES:
            return InterfacePreferences()
        return InterfacePreferences.from_settings(json.loads(content.decode("utf-8-sig")))
    except (OSError, ValueError, UnicodeError, RecursionError):
        return InterfacePreferences()


def apply_scale_environment(percent, environment=None):
    environment = os.environ if environment is None else environment
    inherited = environment.get(_BASE_SCALE_ENV, environment.get("QT_SCALE_FACTOR", "1"))
    try:
        base = float(inherited)
        if not math.isfinite(base) or base <= 0:
            base = 1.0
    except (TypeError, ValueError):
        base = 1.0
    factor = base * (normalize_scale(percent) / 100)
    if not math.isfinite(factor):
        base, factor = 1.0, normalize_scale(percent) / 100
    environment[_BASE_SCALE_ENV] = format(base, ".12g")
    environment["QT_SCALE_FACTOR"] = format(factor, ".12g")
    return factor
