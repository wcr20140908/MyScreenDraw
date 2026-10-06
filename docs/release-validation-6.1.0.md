# 6.1.0 release validation

**Status: RELEASED and publicly re-downloaded/verified on 2026-10-06. All required local and publication gates passed; explicit hardware boundaries below remain.**

The full regression/build suite uses `QT_QPA_PLATFORM=offscreen`. Following the explicit updated instruction on 2026-10-06, separate Windows native-input tests run on screen, serially, with isolated synthetic documents and ownership-checked input. Screenshots and diagnostic logs stay private under ignored `.ccgui/`. Windows injected touch is not a physical-touchscreen hardware test. Real multi-monitor switching, other display/DPI configurations and audible speaker output remain unverified; simulated screens do not replace physical-display acceptance.

## Requirement evidence

| Requirement | Implementation / focused evidence | Acceptance / boundary |
|---|---|---|
| Preserve all pages after leaving whiteboard | `test_document_safety_610.py`, `test_project_roundtrip.py` | passed: full suite and frozen two-round reopen |
| Atomic readable project/autosave files | `test_persistence_610.py`, `test_persistence_safety.py`, actual embedded PNG validation and extension-independent reads | passed: frozen two-round reopen |
| Safe open/update transitions | cancel-default Save/Discard/Cancel, dedicated document tests and updater mutation tests | passed: latest-source full suite |
| Background autosave / no unchanged snapshots | single-flight worker, revision-keyed pages, immutable data, retries/drain; `test_autosave_async_610.py` | passed: latest-source full suite |
| Recovery version selection and preview | collapsed history picker, lazy validation, corrupt skip, preview/cancel tests | passed: full suite, native recovery and bundled QtPdf runtime exercised by frozen PDF export |
| PNG/PDF streaming and explicit failures | `test_export_pipeline_610.py`, `test_export_ui_610.py`; original failed-page indices, progress/cancel, atomic files | passed: full suite, native failure/cancel paths and frozen 3-page PNG/PDF outputs |
| SVG/EPS incomplete export safety | per-page serialized data, atomic writes, validated output and modal outcome | passed: latest-source full suite |
| PDF to separate whiteboard pages | `test_pdf_pages_610.py`; staged transaction, independent identities, bounded bitmap budget, real PDF/project reopen | passed: latest-source full suite |
| Duplicate / rename / drag reorder | placement preference, stable active identity and view-count repair; `test_page_management_610.py`; native edge-autoscroll in both themes | passed: latest-source full suite and native dark/light drag |
| Visible revision-keyed thumbnails | bounded visible-only rendering; page-management regression tests | passed: latest-source full suite |
| Completed stroke geometry / bounds, incremental active path | exact pixels for pen variants, clips, erased gaps/interleaved contacts; `test_stroke_cache_610.py` | passed: mutation regressions, exact-pixel tests and final suite |
| Autosave interval / monitor / timer volume | `test_preferences_610.py`, synthetic screen fallback, volume PCM amplitude/mute; native interval/copy/volume settings controls in both themes | physical multi-monitor and audible output explicitly not tested |
| Teaching features assessment | discussion below; no unrequested extra features | completed; assessment only |

## Test checkpoints (not additive, not a final total)

- Original 6.0.1 baseline: 1387 passed, 11 skipped, 1200 subtests.
- Document/persistence/autosave/updater checkpoint: 86 passed, 8 subtests.
- Page/text/project/lifecycle checkpoint: 250 passed, 142 subtests.
- Preferences/settings/update checkpoint: 116 passed, 13 subtests.
- Export/import/media checkpoint: 71 passed.
- Recovery/cache checkpoint: 40 passed.
- Settings migration audit including all four new preferences: **288 passed** (151.16 s).
- Version/build/angle gate checks: **24 passed, 109 subtests**.
- Final independent sol read-only requirement/drag audit found no concrete critical or important code defect; this does not replace runtime release gates.
- Final post-native-fix build: **1488 passed, 7 skipped, 1208 subtests passed in 921.37 s; build exit 0**. Staging and extracted-EXE smoke, ZIP hygiene and extracted-file equality passed. The build excludes three native-touch suites; the dedicated Windows injected-touch tier is recorded separately below.

## Native Windows acceptance — 2026-10-06

| Tier | Result | Private evidence directory |
|---|---:|---|
| Existing drawing/toolbar/page/settings flows, dark | 102/102 | `.ccgui/real610-dark-20261006` |
| Existing drawing/toolbar/page/settings flows, light | 102/102 | `.ccgui/real610-light-20261006` |
| New 6.1.0 flows after final drag fix, dark | 37/37 | `.ccgui/real610-features-final-dark-20261006` |
| New 6.1.0 flows after final drag fix, light | 37/37 | `.ccgui/real610-features-final-light-20261006` |
| Windows native touch injection through Qt | 4/4, zero skipped | `.ccgui/real610-touch-rerun-20261006` |

These are separate suites, not extra unique unit tests. Reproduction commands (use a **new** `.ccgui` directory for each run; never run real-input suites concurrently):

```powershell
python tests/run_real_acceptance_isolated.py .ccgui/acceptance-dark dark
python tests/run_real_acceptance_isolated.py .ccgui/acceptance-light light
python tests/real_release_610.py .ccgui/features-dark --theme dark
python tests/real_release_610.py .ccgui/features-light --theme light
python tests/run_touch_isolated_610.py .ccgui/touch
```

The 102-check suites cover all 11 permanent pen styles, portrait/landscape toolbar drag/collapse, page add/delete/cancel, settings/presets, first-contact pen return and tray/hide/layout. The 37-check suites cover rename/copy, real page drag with edge-autoscroll, settings controls, collapsed/expanded recovery and older preview, unsaved-open Cancel/Discard, PDF success, injected render-failure modal, native progress cancellation and independent imported pages. File-picker paths and fixture text are injected; the exercised mouse actions and modal responses are native. Settings-volume testing does not play sound or change the Windows mixer/primary display.

**Defect found by native testing:** inherited `QListWidget.startDrag` deleted a source row after custom drop code had already reordered/rebuilt the document view. `PageListWidget` now owns `QDrag`, resolves source identity stably and uses generic `QAbstractItemView` drag housekeeping to preserve insertion/autoscroll in IconMode. Thumbnail refresh also repairs row-count mismatch even if the identity sequence is unchanged. Four focused regressions cover these issues; both final native runs scroll 0→379, reorder and retain the expected rows.

The driver uses a bounded Win32-only input worker because a native OLE drag loop can starve Qt timers. Qt reads/painting remain on the GUI thread; button press checks window ownership and release/cursor restoration run in cleanup. Touch fixtures now account for physical client geometry and drain asynchronous input frames. Initial failed test attempts are not counted as passes. Qt external-WM_DESTROY warnings were observed after successful checks during owned-window teardown, not as runtime application failures.

Visual inspection of recovery, settings, page order and export warnings found no blocked controls in the tested configuration. The incomplete-export dialog explicitly showed 3/4 written pages, original missing page 2 and a separate partial-PDF name. Physical touchscreen hardware, Windows 11, multi-monitor/mixed-DPI setups and long classroom sessions are outside this acceptance.

## Stroke benchmark

Reproduce with `QT_QPA_PLATFORM=offscreen python tests/benchmark_strokes_610.py <output.json>`.
Same synthetic input: 120 grouped marker strokes / 21,600 segments, 1280×900 image. Warm numbers are medians; cold is one initial frame. Raw results are in `stroke-benchmark-610-before.json` and `stroke-benchmark-610-after.json`.

| Measurement | Before (ms) | After (ms) |
|---|---:|---:|
| First full draw / cache construction | 232.020 | 346.883 |
| Warm full draw | 219.486 | 131.205 |
| Warm clipped draw | 95.778 | 0.426 |
| Query all stroke bounds | 386.955 | 0.423 |
| Active append plus clipped draw | 97.616 | 0.313 |

The cache trades a slower first construction for much cheaper repeated partial repaints and hit bounds. These synthetic results do not establish actual touchscreen latency, every pen's speed, or performance on other machines. Exact-image tests establish equivalence independently of timings; no timing threshold is used as a flaky correctness assertion.

## Teaching feature assessment (not implemented in this change)

The next useful teaching improvement would be a compact, opt-in classroom preset rather than another always-visible panel: larger controls, a clear document-save/recovery indicator, and a quiet timer profile. A temporary presentation lock could reduce accidental page deletion or opening during lectures. Session recording, cloud sync and attendance analytics add permissions, storage and privacy work; they should remain separate proposals until the document-safety release is verified. No such extra features are claimed as delivered in 6.1.0.

## Frozen package acceptance

The final package was built **after** the native drag fixes. The obsolete earlier package was not published.

- `tests/verify_document_release_610.py`: two actual frozen restore → background-autosave → reopen rounds preserved three pages, stable IDs/names, ink/text/embedded images, active page 2 and hidden-whiteboard state. The three new serializable preferences used by this fixture also persisted.
- `tests/verify_updater_restart.py`: current updater installed the accepted 6.1.0 package over an isolated old-package copy, automatically restarted, and passed manual reopen. Four synthetic private files and five preferences were preserved; transaction/startup took 21.75 s. This does **not** establish a retroactive repair of the old embedded updater.
- Direct external operation of the accepted frozen EXE through ownership-checked Windows UI Automation: restored the synthetic document, entered whiteboard, invoked PDF/PNG buttons and dismissed success modals. The resulting PDF has **3 readable/renderable pages**, and **3 PNGs** decode successfully. Desktop-annotation export separately produced one screen-capture PDF, matching the file-panel hint; saving a project remains whole-document in either mode. Private UIA traces/output: `.ccgui/frozen-exports-final-20261006/frozen-exports.json`. The process was shut down; no existing user project, roster or application configuration was loaded. Desktop-capture output remains private and is excluded from commits/releases.
- Native QtPdf binaries are present in the package, and the frozen PDF output validation ran against the packaged runtime. All other package startup/reopen/update checks were offscreen.

```powershell
python tests/verify_document_release_610.py MyScreenDraw-v6.1.0-windows-x64.zip build/document-reopen-610
python tests/verify_updater_restart.py MyScreenDraw-v6.0.1-windows-x64.zip MyScreenDraw-v6.1.0-windows-x64.zip 6.1.0 build/restart-verify-610
```

Each verification destination must be new. Startup checks refuse to run when the current Windows profile has the application's autostart enabled.

## Accepted artifact

| Item | SHA-256 |
|---|---|
| `MyScreenDraw-v6.1.0-windows-x64.zip` | `8c6c3b2fa048cb40884283b3d78ac1620c73af3d6842f01b46d6e15cc40ac81e` |
| `MyScreenDraw.exe` | `058477b3c7bd755c5fcce26a8d8c9bf2f3a6be7c65e98e42d18a263c0c6299e5` |
| Accepted production/build source snapshot | `e6f2711be79114f7c478c1ea8a8e15531ee31bb9e5beee5fdc22d9bddf7f5a27` |

The release receipt binds source, ZIP and EXE hashes to unit tests, staging smoke, extracted-file verification and extracted smoke. Publication requires a clean committed worktree matching that receipt. Credentials, synthetic runtime data, private screenshots/logs, build directories and ZIPs are not committed. The executable is unsigned.

## Publication and public artifact verification

- Release/tag: `v6.1.0`, stable (not draft/pre-release), published on 2026-10-06 at `wcr20140908/MyScreenDraw`.
- Immutable release commit: `bfd172c5d15546b7a8c4b0181d7821f55fe71646`. The later README/evidence follow-up changes documentation only; production/build inputs remain the accepted snapshot above.
- Published attachments: `MyScreenDraw-v6.1.0-windows-x64.zip` (**39,900,831 bytes**) and `MyScreenDraw-v6.1.0-windows-x64.zip.sha256`.
- A fresh process with **no Authorization header, credential lookup or cookies** opened the public release page and downloaded both attachments. ZIP/checksum and executable hashes match the accepted values; archive CRC/hygiene, all extracted-file comparisons and public extracted EXE `--smoke-ui` passed (**exit 0**).
- Local public evidence: `build/public-release-610/public-verification.json`; sanitized publication trace: `.ccgui/release610-publication.log`. These runtime artifacts are not committed.
- Publication tooling note: GitHub returned HTTP 422 for an as-yet nonexistent commit/tag reference, while the release script's absent-tag branch expects 404. The first attempt stopped before creating a release. A state audit confirmed no draft; an annotated tag was explicitly created/pushed at the accepted commit, verified, and the unchanged guarded script then published successfully. No tag/release was overwritten and no force push was used.
- A transient Git TLS handshake read failure and a diagnostic wrapper encoding issue were resolved without weakening package/source/commit gates. Credentials stayed in memory and were redacted from captured child output.

The final requirement matrix, native tiers, frozen tests and public artifact evidence together establish this release's acceptance; they do not promise bug-free behavior on untested hardware.
