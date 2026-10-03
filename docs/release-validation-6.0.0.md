# 6.0.0 release validation / 发布验证记录

Record updated: 2026-10-03. **The release owner reported their checks complete and authorized publication. The test-runtime isolation repair passed a new full offscreen regression with current configuration bytes preserved. Binary/source verification is current; the earlier configuration mismatch remains documented as historical evidence, not rewritten as a pass.**

This closeout used source, text logs, in-memory automated assertions and offscreen Qt only. No images or videos were opened, no screenshots were taken, and no real desktop/input/upgrade scripts were run. The build remains unsigned. All pre-existing working-tree changes were retained and included in the reviewed release commit. Publication details follow; earlier no-publication statements below describe historical runs only.

## Published artifact verification — 2026-10-03

- Release: [MyScreenDraw v6.0.0](https://github.com/wcr20140908/MyScreenDraw/releases/tag/v6.0.0), public, not a draft or prerelease.
- Release/tag commit: `d08db57ae6951ee69dcc2bc4d071c77bade7cd41`.
- ZIP: `MyScreenDraw-v6.0.0-windows-x64.zip`, 42261368 bytes.
- Public ZIP SHA-256: `6ec2008cc89e7213f31d206e939191f71016872f339c8cde13b777f8e013210b`.
- Public EXE SHA-256: `35422b32bb00923ca4142a3aeadd6155638f626ede5c09d7c6967a817371302b`.
- Both draft assets were uploaded and downloaded again before publication; hashes matched the accepted local files. The two public assets were then downloaded without authentication and verified again.
- All extracted files matched the public ZIP. Its EXE completed `--smoke-ui` with `QT_QPA_PLATFORM=offscreen` and keyboard launch disabled; exit 0, unchanged EXE hash. This was not a real-desktop test.
- The first ZIP upload encountered a TLS EOF and left a partial asset in the draft. Only that incomplete, newly created asset was removed; retry succeeded before publication. The later public download was resumed after a timeout and accepted only after full SHA-256 verification.
- Source changes after the tag are documentation-only download/status updates; the published EXE was not rebuilt or replaced.

## Publication authorization and test-runtime repair — 2026-10-03

The release owner reported that their checks were complete and authorized fixing
the outstanding issue and publishing 6.0.0. This is user-reported acceptance, not
AI-observed desktop evidence. No per-device or per-scenario report was supplied;
Windows 11, physical-touch vendors, DPI matrices, clean/no-Python environments,
packaged-upgrade permutations and long classroom soaks are not newly claimed.

The configuration concern was addressed at the test boundary, not by changing
production behavior or overwriting user settings. Some legacy offscreen tests
could call the real settings writer using the checkout's runtime paths. A new
session fixture in `tests/conftest.py` redirects data, exports, autosave, config,
roster and log paths to temporary directories outside the checkout. It applies
only to offscreen runs. Per-test fixtures can still override these paths.

- RED: **2 failed, 1 passed; 0.42 s**. Assertions failed before any real-data write.
- GREEN subset: **95 passed, 13 subtests passed; 17.48 s; exit 0**.
- Post-repair complete regression: **1296 passed, 7 skipped, 1184 subtests passed; 785.86 s; exit 0**.
- Current configuration was backed up at the start of the publish request and
  remained byte-identical across the subset and full rerun:
  `4a8f90e532ab… (full value retained in local evidence)`.
- The earlier expected hash `f1853d0d...` still does not match. That historical
  failure is retained below and was not rewritten as a pass. Its exact original
  writer/content was not recovered; this repair proves subsequent isolation and
  preservation, not retroactive preservation of the earlier state.
- Production inputs, EXE, ZIP and build receipt were unchanged. The existing
  candidate was reverified instead of rebuilding an identical source merely to
  replace evidence. The new files are tests; release documentation is outside
  the binary source fingerprint by design.

Local-only evidence: `runtime-isolation-red.log`, `runtime-isolation-green.log`,
`full-offscreen.log` and the corresponding configuration-check JSON records,
plus final artifact/source and public-download verification records. No raw
configuration, private log, image, or screenshot is included in Git or the ZIP.

## Earlier taskbar closeout — before test-runtime isolation repair

Environment remains Windows 10 x64 (19045), Python 3.11.9, PyQt / Qt 6.11.0,
pytest 9.1.1 and PyInstaller 6.21.0. Version remains 6.0.0.

Production changes are limited to `main.py` functions `_delete_from_taskbar`,
`mark_tool_window` and `ControlPanel.raise_floating`: correct little-endian COM
GUIDs, pointer-width-safe signatures, paired initialization/release and diagnostic
logging, offscreen guards, and immediate tool-window marking after owner rebinding.
Qt parent, focus, menus, single-instance, pinned-shortcut and AppUserModelID policies
were not changed. These defects do not identify whether the reported duplicate
icons belong to one process or multiple processes; Explorer behavior is untested.

- Artifact: `MyScreenDraw-v6.0.0-windows-x64.zip`, **42261368 bytes**.
- ZIP SHA-256: `6ec2008cc89e7213f31d206e939191f71016872f339c8cde13b777f8e013210b`.
- EXE SHA-256: `35422b32bb00923ca4142a3aeadd6155638f626ede5c09d7c6967a817371302b`.
- Production-source fingerprint: `7196612bf2d44ac64b3d4de466784178a266df33cfc7af93061728d4c7f40fe8`.
- Current local receipt: `build/release-receipts/MyScreenDraw-v6.0.0-windows-x64.zip.json`.
- Current text evidence: `exports/taskbar-fix-validation/` (local only).

| Check | Actual result | Evidence / limits |
| --- | --- | --- |
| Pre-fix taskbar RED rerun | **21 failed, 4 passed; 6.69 s** | `resume-red.log`; mocked native interfaces. |
| Initial taskbar/window/settings regression | **313 passed; 158.17 s** | `taskbar-green.log`; not real input/focus. |
| Expanded taskbar suite | **33 passed; 8.18 s** | `taskbar-final-focused.log`; COM ABI, cleanup/failures, styles and offscreen lifecycle. |
| Complete build regression | **1293 passed, 7 skipped, 1184 subtests passed; 1197.27 s; exit 0** | `build-taskbar.log`; ends `BUILD_EXIT=0`. |
| Staging and ZIP-extracted EXE smoke | **Passed in build** | Forced offscreen, soft keyboard disabled; recorded by new receipt. |
| Independent binary/source checks | **Passed** | ZIP checksum/CRC/PE/manifest/receipt/source fingerprint, frozen function code/constants, versions 6.0.0.0 / v6.0.0, unchanged unrelated checkpoint files. |
| Bundled modules/dependencies | **Passed** | `app_lifecycle`, `themed_controls`, `pen_defaults`, `chalk_texture`, `release_notice`, `qoffscreen.dll`; no foreign `icuuc.dll`. |
| Continuation taskbar/release/build/documentation subset | **114 passed, 220 subtests passed; 38.67 s; exit 0** | `closeout-focused.log`; offscreen fixtures and mocked native/process calls. |
| Configuration preservation | **FAILED in this earlier run** | Current `data/config.json` differs from the taskbar pre-build hash. |
| Earlier independent closeout | **FAILED** | `artifact-verification.json`: `status: failed`; `artifact-audit.log`: `AUDIT_EXIT=1`. Build receipt does not prove configuration preservation. |
| Real taskbar/focus/visual/touch acceptance | **Not run, user-owned** | No image/video inspection, screenshots, real input or Explorer operation. |

### Historical configuration preservation failure

The original verifier failed its configuration assertion and was not modified.
A separate diagnostic audit retained the failure and exit code 1 while recording
the other completed checks. The pre-build hash record was not changed.

- Expected taskbar pre-build hash (record created 17:24:21 local):
  `f1853d0db8fc… (full value retained in local evidence)`.
- Actual current hash:
  `4a8f90e532ab… (full value retained in local evidence)`.
- Current bytes match `data/config.json` in the earlier
  `prebuild-runtime-backup.zip` (created 15:03:12 local). This does **not** prove
  preservation of the 17:24 configuration. LF/CRLF/BOM variants do not explain it.
- Current file modification time is 17:31:21 local; the build log began at 17:29:50.
  Timing alone does not identify the writer. Some legacy tests save settings or
  temporarily replace the real config path; that risk is not a proven cause.
- No configuration was restored or overwritten during continuation. The precise
  pre-build content is unavailable in the handoff's hash-only record, so no guessed
  restoration or baseline substitution is acceptable. The subsequent publish-request snapshot and isolated rerun are recorded above;
  they do not reconstruct this earlier state.

The build used the pytest command and seven skip reasons in the historical
reproduction section below, with three real-touch files excluded. The taskbar
wrapper also set `MYSCREENDRAW_NO_KEYBOARD=1` and disabled real keyboard tests.
Runtime logs are not claimed to remain unchanged.

## Historical local evidence — not final acceptance

The following logs are local-only records under `.git/release-validation/`.
Filenames identify evidence for maintainers, not downloadable public artifacts.
They do not consistently establish the tested revision, dirty working-tree state,
full environment, or process exit code. Do not attribute them to the final package.

| Scope | Historical record | Limits and follow-up |
| --- | --- | --- |
| Settings matrix | `upgrade-settings.log`: 252 passed in 138.94 s | Source-level, in-process settings tests, not an installed/package upgrade. The current test file covers 41 collected fields and legacy shared-pen migration. Its pre-fix note reports 20 failures; that note is not a fresh execution log. Rerun against the frozen candidate. |
| Full offscreen regression | `full-regression.log`: 4 failed, 1032 passed, 7 skipped, 708 subtests passed | Three documentation-link failures and one stale beta.8 version assertion. Later file changes do not prove these failures resolved; the current full suite must be rerun, with skip reasons recorded. |
| Earlier Windows desktop acceptance | `real-first.log`: 56/57; `real-fixed.log`: 57/57 | The first run failed the page-rail position check. The later run reports LOGO dragging/highlight, 11 pen styles, settings reload, whiteboard, mode, tray, and native-window checks. It is historical source-run evidence, not final EXE acceptance. Cleanup-time `WM_DESTROY` warnings are present; do not describe the logs as warning-free. |
| Subsequent light-theme attempts | `real-stable-light.log`: 9/10; `real-stable-light-retry.log`: 9/10; `real-stable-light-final.log`: 20/21 | All stopped with pointer-position/movement exceptions in the harness. These are incomplete/failed runs, despite the last filename containing “final”. They do not establish a full light-theme pass; a controlled rerun and explanation are required. |
| Cross-process input probe | `mouse-passthrough.log`: `REAL_INPUT_OK` and `KNOWN_BAD_REPRODUCED` | The log reports mouse/keyboard delivery, heartbeat, repeated mode switches, unchanged HWND, and reproduction of the old Qt-only failure. This is not evidence for every environment or final EXE. |
| Windows touch injection | `touch-injection.log`: 4 tests, `OK` | Injected contacts only, not physical classroom touch hardware. |

`tests/test_logo_drag_regressions.py` contains checks for group bounds,
continued/reversed dragging, portrait/landscape layout, detached/collapsed state,
oversized groups, ordinary clicks, and pressed-state cleanup. Listing this
coverage is not a claim that those tests passed on the current candidate.

## Repair scope and upgrade boundaries

- With an attached, expanded toolbar, dragging the LOGO bounds the pair as one
  rectangle, LOGO above in portrait mode or to the left in landscape mode.
  Detached toolbars remain independent; a collapsed toolbar does not follow the
  LOGO. Oversized groups retain relative placement but may not fit fully onscreen.
- Drag activation and release clear the LOGO button's pressed state. Ordinary
  click-to-collapse/expand and normal hover feedback remain; not every highlight
  is a stuck pressed state.
- Settings fixes validate theme/current-tool types and numeric eraser size,
  highlighter opacity/width, laser width, and magnifier zoom/size. The affected
  fields no longer abort loading later valid preferences, including disabled
  update checks. This does not recover an unparseable configuration file.
- Legacy shared-pen migration remains. Legacy classic UI settings migrate to the
  icon UI, and unavailable/offscreen positions may be adjusted; pixel-identical
  placement is not promised. Restoring settings in-process is not proof of a
  successful packaged upgrade or byte preservation of all user files.

## Previous local candidate, before taskbar repair — 2026-10-03

**Historical only:** the package/receipt/source-snapshot paths below were reused
by the taskbar build. Their current contents do not prove this older result; use
the preserved prior-package checkpoint and historical logs.

Environment: Windows 10 x64, build 19045; Python 3.11.9, PyQt 6.11.0 /
Qt 6.11.0, pytest 9.1.1, PyInstaller 6.21.0. This is the development machine,
not a separate clean machine or Windows 11 validation.

- Base Git HEAD: `aafce1f0565e340aa54435391bf0016d4d9a8ad2`, **with pre-existing and closeout uncommitted changes**.
- Accepted production-source fingerprint: `0c425dd1892d9e1c38286c546eb5f899c69a81b370ee1f0ef230bb18586635cf`.
- Artifact: `MyScreenDraw-v6.0.0-windows-x64.zip`, 42257906 bytes.
- ZIP SHA-256: `66e580b6e40f2615aeada0974183d6827ff01e8004de540f2ec0297a65a157a2`.
- EXE SHA-256: `b4cbc07bfc45888b25ab9cbbea9722eaee4ed2a2cf9b064ccedd10517fbeb61c`.
- Local receipt: `build/release-receipts/MyScreenDraw-v6.0.0-windows-x64.zip.json`.
- Source-input hashes: `build/release-source.json`.
- Text evidence directory: `exports/final-headless-validation/` (local-only).

| Check | Actual result | Evidence / limits |
| --- | --- | --- |
| Build's complete offscreen regression | **1260 passed, 7 skipped, 1182 subtests passed; 796.57 seconds; exit 0** | `build-final.log`; includes lifecycle, presets, chalk, upgrade/settings/rollback tests and LOGO cases. Skip/exclusion details below. |
| Closeout focused regression | **130 passed, 334 subtests passed; 26.96 seconds; exit 0** | `focused-final.log`; keyboard shutdown wiring, headless build guard, background windows, integration, pen defaults and chalk. |
| Post-documentation release checks | **56 passed, 151 subtests; 29.72 seconds; exit 0** | `post-doc-release-checks.log`; metadata, links, archive gates, smoke environment and dependency isolation. Final artifact/source receipt was verified again after documentation edits. |
| Headless smoke guard red/green | **10 failed before fix; 10 passed after fix** | `build-smoke-red.log` / `build-smoke-green.log`. PowerShell AST loads only the smoke function; fake processes test unset/windows inheritance, start failure, nonzero exit, timeout, disposal failure and environment restoration. No EXEs launched by these tests. |
| Dependency search red/green | **4 failed before fix; corrected dependency/release subset: 56 passed, 149 subtests** | `build-dependencies-red.log` / `build-dependencies-green.log`; System32 precedence and PATH restoration, without running PyInstaller in the unit tests. |
| PyInstaller onedir and portable ZIP | **Passed; build exit 0** | `build-final.log`; fresh static imports include lifecycle, themed controls, pen defaults and chalk. Candidate replaces the old ZIP only after all sealing gates pass. |
| Staging and extracted EXE smoke | **Both passed, forced offscreen** | Receipt checks `staging_smoke` and `extracted_smoke`; `--smoke-ui` constructs production windows without displaying them. Not a real-window/focus/input test. |
| Archive integrity and extracted files | **Passed** | Version/PE/manifest/EXE hash, ZIP hash, required Qt dependencies and licenses, privacy exclusions, and full extracted-file comparison. Data/exports are not shipped. |
| Real Windows light/dark acceptance | **Not run, user-owned** | No image inspection, screenshots, pointer automation or native desktop acceptance. Historical visual runs above do not validate this EXE. |
| Real packaged upgrade / failure recovery | **Not run, user-owned** | Automated synthetic settings, preservation and rollback tests passed in the full suite. This does not prove a complete old-EXE-to-new-EXE upgrade with real user data or permissions. |
| Physical touch, Windows 11, DPI/multi-monitor, no-Python machine, offline startup and classroom soak | **Not run** | Offscreen/software assertions on this Windows 10 machine do not establish these environments. |
| Published downloadable artifact | **Not published** | No remote attachment hash or download validation exists for this candidate. |

### Reproduction and skip scope

The closeout wrapper selected Python 3.11.9, set
`QT_QPA_PLATFORM=offscreen`, `MYSCREENDRAW_REAL_KEYBOARD=0`, and
`PYTEST_ADDOPTS='-ra --durations=15'`, then ran `build.ps1`.
The build itself ran:

```powershell
python -m pytest -q --ignore=tests/test_touch_injection.py --ignore=tests/test_multitouch_injection.py --ignore=tests/test_multitouch.py
```

Seven intentional skips: one tray-label check in `test_beta5_verification.py`
(no tray on the offscreen platform); four real keyboard/focus tests in
`test_keyboard_delivery.py` (explicit opt-in disabled); two tray tests in
`test_lifecycle.py` (no system tray on the offscreen platform). The three ignored
touch-related files are **excluded**, not counted among these seven skips.

`Invoke-Smoke` separately forces offscreen and
`MYSCREENDRAW_NO_KEYBOARD=1` for each frozen EXE, restoring both environment
variables in `finally`, including startup or handle-cleanup failure. A hidden
process window alone is not treated as a guarantee that Qt cannot show a window.

### Failures found and resolved in this closeout

The initial full run completed with **1 failed, 1245 passed, 7 skipped,
1182 subtests passed** (811.91 seconds; exit 1; `full-regression.log`).
`ExitWiringTests.test_shutdown_is_wired_to_about_to_quit` decoded `main.py`
using `utf-8` before calling `ast.parse`, leaving its UTF-8 BOM as U+FEFF.
The test now uses `utf-8-sig`, like the existing AST-based tests. Product
shutdown wiring and the assertion were not weakened. The build's full rerun
above is the post-fix result, including the ten newly added smoke-guard cases.

A subsequent full run passed **1256 tests, 7 skipped and 1182 subtests**
(761.55 seconds), but that build's staging EXE smoke timed out. There was no
application log: QtCore failed before application startup. A separate console
build under the local work directory captured an import failure/0xc0000139
without desktop inspection. PyInstaller had collected an unrelated Poppler
`icuuc.dll` from the inherited tool PATH. It lacked all 20 unversioned exports
imported by Qt6Core; Windows System32 ICU provided all 20. Removing only that
foreign DLL from the diagnostic copy made the same offscreen EXE exit 0.

The production spec now puts System32 first during Analysis, then restores
PATH even on error. Four focused spec tests failed before this fix and passed
after it; dependency/release checks passed as a 56-test subset. The final
build result above is a fresh post-fix build, not promotion of the failed
candidate. Logs: `build-full-pass-smoke-timeout.log`,
`frozen-startup-diagnostic.log`, `frozen-startup-with-system-icu.log`.

An initial test launcher and an initial build launcher could not resolve
`python` in Windows PowerShell. Diagnosis found inherited `PATHEXT=.CPL`;
only the child build environment was corrected to include executable extensions.
Those starts did not execute tests or create a new package, and are not successes.
No permanent user/system environment setting was changed.

Source and prior artifact checkpoints were saved outside `build/` before
modification/cleanup. No production source was changed during the accepted build.
A comparison with the pre-build local runtime backup found nine of eleven files
unchanged; only `data/app.log` and `data/events.jsonl` changed due to test logging.
This is not a claim of byte-identical logs or a real packaged-upgrade test.
A generated shell-cache directory was preserved in ignored local evidence, not
added to the source tree or portable ZIP.

Documentation and test files are outside the binary source fingerprint; final
publication still requires the entire worktree to be reviewed and clean.

## Not established by the historical runs

- Physical classroom touch-screen compatibility across vendors.
- A separate Windows 11 machine or a full multi-monitor / DPI matrix.
- A 60–90 minute classroom soak; short automated runs do not establish long-term stability.
- Publisher signature or a complete third-party license audit.

Known SVG/EPS texture/glow fallbacks remain documented in the README. Private
screenshots, configuration fixtures, and raw desktop logs must not be committed
or included in the release ZIP. Review and sanitize any public evidence summary.
See [Testing and acceptance](testing.md) and [Building and releasing](releasing.md)
for the separate validation tiers and release checklist.
