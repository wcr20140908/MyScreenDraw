# Final UI fixes implementation plan — closeout

**Goal:** Finish the user-approved v6.0.0 fixes without discarding existing work.

**Architecture:** Keep visibility ownership in AppLifecycleManager, shared theme controls in themed_controls.py, independent presets in pen_defaults.py, and deterministic chalk texture generation in chalk_texture.py. Keep tool windows parentless: native stacking owns them; a weak registry tracks lifecycle ownership.

## Completed implementation and automated checks

- [x] Persistent independent windows hide with the main UI and restore only if still valid and not closed; transient tools stay closed, collapsed toolbar state and safe mouse mode remain. The application event guard uses a weak manager reference and tolerates teardown.
- [x] Pen-type/update-channel dropdowns and non-native alpha-aware color dialogs follow light/dark theme. Color codes are read-only; cancel leaves the draft unchanged; 13 tool presets remain independent.
- [x] Connect cached deterministic 192×192 chalk texture to the real renderer; preserve RGB, alpha/opacity, density, independent return images and other pen styles. No visual-taste changes were made during this text-only closeout.
- [x] Fix build smoke's environment scope: force offscreen and suppress soft-keyboard launch for both staging/extracted EXEs, restore caller state even on failure. Ten mock-process regressions went red then green.
- [x] Fix frozen QtCore startup failure caused by a foreign ICU DLL on the build PATH. Prefer System32 during spec dependency analysis and restore PATH on success/failure; four isolated spec regressions went red then green. A console diagnostic proved that the foreign ICU lacked all 20 required symbols while Windows ICU supplied them.
- [x] Fix the existing keyboard-exit AST test to decode UTF-8 BOM correctly; keep its shutdown-wiring assertion.
- [x] Focused verification: 130 passed / 334 subtests. Final build regression: 1260 passed / 7 skipped / 1182 subtests. Build, ZIP sealing and both headless EXE smokes passed.
- [x] Refresh release notes, README/CHANGELOG and validation records with exact current package hashes and explicit scope limits.

## Deliberately deferred to the user

- [ ] Visual quality, light/dark layout and chalk thin-stroke continuity.
- [ ] Real Windows window stacking/focus, physical touch, and real packaged upgrade.
- [ ] Windows 11, mixed DPI/multi-display and long classroom stability.
- [ ] Review/commit/push/publish and remote attachment verification, only when authorized.

This closeout used no subagents, images/videos, screenshots, rendering inspection or desktop automation. Prior Worker A/B wording was planning text, not evidence of delegation. No automatic commit, push or publication. See [the validation record](../release-validation-6.0.0.md) for evidence and historical failures.
