# 6.0.0 Classroom Preferences Implementation Plan

> Execution: subagent-driven in this session, at most two workers, disjoint file ownership. Existing unrelated work is preserved.

**Goal:** Ship the approved three preferences together with settings/LOGO fixes as stable 6.0.0.

**Architecture:** Small independently testable notice and preset modules integrate with existing PyQt6 settings and input dispatch. Existing atomic JSON persistence remains the authority; helpers do not import main.

**Tech Stack:** Python 3.11, PyQt6, pytest, Windows SendInput/touch injection, PyInstaller, PowerShell, GitHub REST.

### Task 1: launch notice (worker A)
Files: new release_notice.py and tests/test_release_notice.py only.
1. Test launch counting, same-session close, upgrade/downgrade version changes, malformed state, and UI close/theme/wrapping.
2. Run focused tests red, implement normalized lifecycle helper and self-contained amber card, run green.
3. Parent integrates state loading/saving and starts one session only from normal bootstrap.

### Task 2: pen preset editor (worker B)
Files: new pen_defaults.py and tests/test_pen_defaults.py only.
1. Test independent deep copies, normalization, missing/corrupt fields, unchanged presets after live edits.
2. Implement reusable preset normalization/editor with callback-based capture and save; no main import.
3. Run focused tests; parent integrates tool transitions and settings persistence.

### Task 3: whiteboard return and integration (parent)
Files: main.py, i18n.py, tests/test_classroom_preferences.py, tests/test_upgrade_settings.py.
1. Write failing integrated tests for first-contact return, manual override, page boundaries, mouse/touch paths, settings roundtrip and preset application.
2. Add transient arm/consume/cancel helper using existing set_tool/input hooks. Do not consume the initial contact.
3. Integrate helpers, new settings controls, normalization, and normal-launch initialization. Update exhaustive field audit.
4. Run QT_QPA_PLATFORM=offscreen python -m pytest focused suites, then complete suite excluding opt-in touch tiers.

### Task 4: real desktop and release gates
Files: tests/real_release_acceptance.py, build.ps1, create_release.ps1, release artifact validator/tests if needed.
1. Extend opt-in desktop tests for new settings and page transition behavior in both themes.
2. Run serially on the desktop, inspect cropped screenshots, run independent cross-process input and touch injection.
3. Harden literal paths and candidate promotion; verify manifest/version/hash/receipt before publishing.
4. Build, verify clean ZIP, verify isolated old-install upgrade and preserved data. Never modify real user settings.

### Task 5: publish and report
Files: README.md, README.en.md, CHANGELOG.md, docs/testing.md, docs/releasing.md, docs/release-validation-6.0.0.md, release-notes-v6.0.0.md.
1. Update docs to actual functionality and evidence; run git diff --check and metadata tests.
2. Commit explicit source/test/docs paths, push main, publish stable v6.0.0 with ZIP and SHA-256.
3. Download published asset, verify hash and extracted EXE smoke; record exact published URL/commit.
4. Discuss incremental Python extraction, C# rewrite, C++ Qt port and native C hot paths, without code changes.
