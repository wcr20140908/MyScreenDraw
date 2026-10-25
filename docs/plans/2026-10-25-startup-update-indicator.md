# Startup update indicator implementation plan

**Goal:** Check for updates immediately on normal startup by default; show a non-dismissible neon ring and red/white `NEW！` sticker around Settings when a newer release is available; retain the manual settings-page check.

**Architecture:** Keep the existing update worker and version comparison. Schedule one zero-delay startup callback after restoring the normal UI and existing preferences. Paint the indication as a transparent child of each Settings button, with no new top-level window, input handling or dismissal control. A known update survives transient check errors and closing Settings or disabling checks; a successful check confirming no newer version clears it. Selecting a different release channel invalidates the old channel candidate and its decoration together. Existing fully-disabled update preferences and private/smoke runtime restrictions remain authoritative.

**Tech stack:** Python, existing PyQt6, pytest; no new runtime dependency.

The user's request specifies the visual design and behavior. Implement in the existing checkout, preserving preceding uncommitted calculator/toolbar work; no commit, push or release is requested. Requirements and verification are recorded in GitHub Issues per project instructions.

## Tasks

1. Record the requirement in GitHub and add failing focused tests for startup once/default/disabled/private behavior, update state transitions, and Settings click/resize/theme/lifecycle behavior.
2. Add `update_indicator.py`: transparent child overlay, slow neon pulse, high-contrast red sticker; timer runs only while visible and enabled, no close/dismiss control.
3. Update `main.py`: attach indicators to Settings buttons; start normal startup checks immediately; synchronize indicators when updates are found/confirmed current; preserve known update state on transient failures and ignore results after shutdown/channel changes.
4. Run focused updater, settings, lifecycle, toolbar and isolation regressions; inspect a simulated update in an isolated real desktop runtime without querying or modifying user data.
5. Update docs/testing and the GitHub Issue with results and visual evidence. Leave source edits in the existing checkout.

**Validation commands:**

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest -q tests/test_update_indicator.py tests/test_settings_and_ui_modes.py tests/test_update_notes.py tests/test_beta6_updater.py tests/test_background_windows.py tests/test_logo_drag_regressions.py tests/test_i18n_and_telemetry.py --tb=short
```

The new focused tests use fake update workers, not a real release request. Real desktop evidence uses synthetic available-release metadata and the existing owned-window native capture helper. Download/install behavior is unchanged.
