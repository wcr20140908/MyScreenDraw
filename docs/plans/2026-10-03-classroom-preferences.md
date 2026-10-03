# 6.0.0 Classroom Preferences Implementation Plan

> Original implementation split: at most two authorized workers with disjoint file ownership, plus parent integration. The user permits subagents; this is a work split, not evidence that agents or checks ran. Preserve existing unrelated work.

**Goal:** Prepare the approved three preferences together with settings/LOGO fixes for stable 6.0.0. **Status (updated 2026-10-03): built and published.** The stable ZIP and SHA-256 assets are public and hash-verified; the implementation, documentation and publication tasks below are closed.

**Current pass (2026-10-03): documentation only.** Reconcile the source and
[approved design](2026-10-03-classroom-preferences-design.md), preserving prior edits.
The write allowlist is exactly:

- [README.md](../../README.md)
- [README.en.md](../../README.en.md)
- [CHANGELOG.md](../../CHANGELOG.md)
- [release-notes-v6.0.0.md](../../release-notes-v6.0.0.md)
- [docs/architecture.md](../architecture.md)
- [this implementation plan](2026-10-03-classroom-preferences.md)
- [the design plan](2026-10-03-classroom-preferences-design.md)

Read `main.py`, `pen_defaults.py`, and `release_notice.py` for behaviour. That pass was
documentation-only: code, scripts, tests, and validation reports were not edited, and
only document/link/strict UTF-8 and diff checks ran. The stable assets have since been
published and verified, so the beta.8 download/checksum examples were replaced by 6.0.0
links. The tasks below retain the implementation/release roadmap; file ownership
there is not a claim of completed testing.

### Source alignment checklist

- Notice: top-of-Settings yellow card, first three normal launches and subsequent
  version changes (including downgrade/revisit), once-per-run counting, run-only
  dismissal, no automatic opening of Settings, no counting on merely opening it.
- Page return: default on; only arm after actual whiteboard transitions in a
  non-annotation state; restore exact style/marker/laser before continuing first
  contact; cancel on manual tool/mode choice, exit, or disable; boundary no-ops do
  not arm. Include current-page deletion and the laser's non-permanent output.
- Presets: one default-off switch, 13 independent entries with tool-specific fields,
  factory fallback, editor/save/capture-selected-live actions, and no save on dropdown
  selection. Save/Capture persist but do not apply; enable-current/startup/re-entry
  apply, same-tool clicks and individual strokes do not. Never rewrite stored ink.
- Persistence: retain the prior 41 fields plus five additions (46 in current source);
  default auto-return on/custom defaults off, normalize missing fields, and keep
  live settings separate from presets. Session dismissal/arming remain transient.
- Evidence: describe source behaviour without upgrading earlier results into new
  feature acceptance; pending gates remain pending in this plan.

**Architecture:** Small independently testable notice and preset modules integrate with existing PyQt6 settings and input dispatch. Existing atomic JSON persistence remains the authority; helpers do not import main.

**Tech Stack:** Python 3.11, PyQt6, pytest, Windows SendInput/touch injection, PyInstaller, PowerShell, GitHub REST.

### Task 1: launch notice (worker A)
Files: new release_notice.py and tests/test_release_notice.py only.
1. Test launch counting, same-session close, upgrade/downgrade version changes, malformed state, and UI close/theme/wrapping.
2. Run focused tests red, implement normalized lifecycle helper and self-contained amber card, run green.
3. Parent integrates state loading/saving and starts one session only from normal bootstrap; smoke exits before this step, and card dismissal belongs to the panel rather than persisted state.

### Task 2: pen preset editor (worker B)
Files: new pen_defaults.py and tests/test_pen_defaults.py only.
1. Test independent deep copies, normalization, missing/corrupt fields, unchanged presets after live edits.
2. Implement reusable preset normalization/editor with signals or callbacks for capture/save; no main import. Current integration connects the signals to parent persistence. Capture saves the selected type's live configuration; neither action applies it.
3. Run focused tests; parent integrates tool transitions and settings persistence.

### Task 3: whiteboard return and integration (parent)
Files: main.py, i18n.py, tests/test_classroom_preferences.py, tests/test_upgrade_settings.py.
1. Write failing integrated tests for first-contact return, manual override, page boundaries, mouse/touch paths, settings roundtrip and preset application.
2. Add transient arm/consume/cancel helper using existing set_tool/input hooks. Do not consume the initial contact.
3. Integrate helpers, new settings controls, normalization, and normal-launch initialization. Audit all 46 current top-level fields, including the five new keys; a source count alone does not establish coverage.
4. Run QT_QPA_PLATFORM=offscreen python -m pytest focused suites, then complete suite excluding opt-in touch tiers.

### Task 4: real desktop and release gates (future execution; excluded from this pass)
Files: tests/real_release_acceptance.py, build.ps1, create_release.ps1, release artifact validator/tests if needed.
1. Extend opt-in desktop tests for new settings and page transition behavior in both themes.
2. Run serially on the desktop, inspect cropped screenshots, run independent cross-process input and touch injection.
3. Harden literal paths and candidate promotion; verify manifest/version/hash/receipt before publishing.
4. Build, verify clean ZIP, verify isolated old-install upgrade and preserved data. Never modify real user settings.

### Task 5: documentation alignment (current pass)
Files: only the seven paths in the allowlist above.
1. Explain operation locations, defaults, saving/application timing, and cancellation/compatibility boundaries in both READMEs and stable release notes.
2. Update the changelog, module/state ownership, and both plans without removing prior settings/LOGO fixes or the beta.8 migration notes.
3. Check strict UTF-8, relative links/anchors, and scoped diff/whitespace; confirm files outside the allowlist are unchanged. Do not run metadata tests or rewrite validation reports.
4. Report exactly which documents changed, which checks ran, and the untested/unpublished status.

### Task 6: publication and follow-up (not authorized in this pass)
The original roadmap includes updating testing/releasing guidance and the validation
record from fresh evidence, then committing explicit paths, pushing, and publishing
stable ZIP/SHA-256 assets only after gates pass and execution is authorized. A later
published-asset download/hash/EXE smoke check must record the exact URL and commit.
Those actions, including edits to `docs/testing.md`, `docs/releasing.md`, and
`docs/release-validation-6.0.0.md`, are outside the current allowlist. Discussion of
incremental Python extraction, C# rewrite, C++ Qt port, or native C hot paths remains
optional future analysis, without a language rewrite in this feature.
