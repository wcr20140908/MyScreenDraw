# SPDX-License-Identifier: GPL-3.0-or-later
"""The opt-in restart verifier must not heal a user's autostart entry."""
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def verifier():
    path = Path(__file__).with_name("verify_updater_restart.py")
    spec = importlib.util.spec_from_file_location("restart_verifier", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_autostart_profile_is_rejected_before_creating_evidence(verifier, tmp_path, monkeypatch):
    monkeypatch.setattr(verifier, "autostart_enabled", lambda: True)
    validate = Mock()
    monkeypatch.setattr(verifier, "validate_update_zip", validate)
    evidence = tmp_path / "must-not-be-created"
    with pytest.raises(RuntimeError, match="isolated Windows profile"):
        verifier.execute(tmp_path / "old.zip", tmp_path / "new.zip", "6.0.1", evidence)
    assert not evidence.exists()
    validate.assert_not_called()


def test_clean_profile_reaches_archive_validation(verifier, tmp_path, monkeypatch):
    monkeypatch.setattr(verifier, "autostart_enabled", lambda: False)
    validate = Mock(side_effect=ValueError("archive validation sentinel"))
    monkeypatch.setattr(verifier, "validate_update_zip", validate)
    evidence = tmp_path / "isolated-evidence"
    with pytest.raises(ValueError, match="archive validation sentinel"):
        verifier.execute(tmp_path / "old.zip", tmp_path / "new.zip", "6.0.1", evidence)
    assert evidence.is_dir()
    validate.assert_called_once_with(str(tmp_path / "old.zip"))
