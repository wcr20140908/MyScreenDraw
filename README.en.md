# MyScreenDraw

> **中文**: [README.md](README.md)

MyScreenDraw is a fullscreen annotation / whiteboard / math-teaching tool built for **classroom touch screens**:

- **Annotate anything on screen** — 11 permanent pen styles, plus a highlighter and laser pointer
- **Freehand shapes snap to standard shapes**: draw, then hold the pen still at the end — a progress ring fills and the stroke converts; lift to keep it freehand (lifting never converts)
- **Multi-page whiteboard** with white/black board switching; export page by page to PNG / PDF / SVG / EPS
- **Real millimetre-scaled ruler, protractor and set squares** (per-screen calibration) with live readings
- **Random name picker, timer, presentation spotlight, calculator** — a whole lesson without switching apps
- **No account; drawings, rosters and logs are not uploaded**. Automatic update checks are enabled by default and can be disabled in Settings. Downloads and installation each require separate confirmation; neither happens silently

Current version **v6.1.0** (stable release; published and independently re-downloaded for verification). The UI follows the system language in 8 languages: English, 中文, Français, Español, Deutsch, Русский, 한국어, 日本語.

> Product screenshots are not included in the public release yet; the current local captures contain development-environment details and must not be committed to GitHub.

## 6.1.0: document safety, streaming exports and recovery previews (released)

- Preserve the complete document after leaving whiteboard mode; explicit unsaved-work confirmation before destructive open/update operations.
- Background autosave, configurable intervals and a collapsed-by-default older-version picker with page previews.
- Page-by-page PNG/PDF output with progress, cancellation and original failed-page numbers; import PDFs as independent board pages.
- Duplicate, rename and reorder pages; visible thumbnail and stroke geometry caches.
- Annotation monitor selection and timer-alarm volume without changing the Windows primary display or system volume.

**Published and publicly re-downloaded for verification.** The final build passed 1488 tests and 1208 subtests, with 7 skipped. Native dark/light acceptance passed 102 existing-flow and 37 new-feature checks per theme, plus 4 injected-touch tests. Frozen document reopen, updater restart, PNG/PDF output, public ZIP/checksum verification and extracted-EXE startup all passed. Injected touch is not physical-touchscreen acceptance; Windows 11, multi-monitor/mixed-DPI, audible output and long classroom sessions remain unverified. See the [6.1.0 validation record](docs/release-validation-6.1.0.md) and [release notes](release-notes-v6.1.0.md).

## 6.0.1: download progress and verified restart (released)

- Separate checking, downloading, verification, and installation states. Show percentage and received/total size with cancellation; use indeterminate progress when the total is unknown.
- Refuse in-app overwrite installation from source. Portable updates pass the target version and old process PID, wait for exit, and never force-kill an arbitrary Python process.
- Verify the version and EXE SHA-256. Launch literal paths containing Unicode, spaces, and brackets. Delete backups only after the new event loop acknowledges readiness; attempt rollback on early exit and retain backups if a live process is not ready.
- Preserve user data. Rollback does not guarantee recovery from power, permission, or disk failures; back up before upgrading.

Final build regression: **1347 passed, 7 skipped, 1197 subtests passed; build exit code 0**. Isolated real-package restart, manual reopen, new-directory migration, public download hashes, and extracted-EXE offscreen startup were verified. Physical touchscreens, Windows 11, multiple monitors/DPI, and long classroom sessions remain unverified. See the [6.0.1 validation record](docs/release-validation-6.0.1.md) and [release notes](release-notes-v6.0.1.md). The 6.0.0 figures below are historical only.

### Moving from 6.0.0: use a new directory, not its in-app updater

**The running 6.0.0 updater has download/installation defects of its own. A new 6.1.0 package cannot retroactively repair update code executing in the old process. Do not rely on the 6.0.0 in-app updater for this upgrade.**

**The stable 6.1.0 assets have been published and verified by downloading them again.** Follow these migration steps:

1. Download the **6.1.0 Windows x64 portable ZIP** and matching `.zip.sha256` from the official repository's stable Release. Verify SHA-256; do not choose Source code archives.
2. Extract the entire ZIP into a new, empty directory, such as `D:\Apps\MyScreenDraw-6.1.0`. Do not overwrite the old installation or a source checkout, and do not launch the new EXE yet.
3. Save your work, exit the old app through its tray menu, handle any save confirmation, and confirm the old `MyScreenDraw.exe` process has ended. F12 or hiding to the tray is not an exit.
4. Back up the old `data/`, `exports/`, and projects saved elsewhere. Then copy `data/` and `exports/` into the new directory. Never overwrite private settings, rosters, autosaves, or logs with package defaults or sample files. If the destination already contains user files, back up both sets and resolve conflicts individually, not by overwriting whole folders. Keep the old directory and backups for recovery.
5. Point desktop, Start menu, and taskbar shortcuts to the new `MyScreenDraw.exe`. If Start with Windows is enabled, check and update that path too so it does not launch the old app.
6. Launch only the new EXE, confirm **v6.1.0**, check settings, projects, and exports, then fully exit and restart to verify. Never run both versions against the same data.

## Historical features and fixes in 6.0.0 (released)

These changes are included in the stable 6.0.0 portable release. The older beta.8 assets do not include these new features or fixes.

- Added a free/open-source notice at the top of Settings, default-on pen restoration after whiteboard page turns, and default-off custom pen defaults. See “New classroom preferences in 6.0.0” below for controls, saving steps, and limits.

- Dragging the LOGO bounds it together with the attached, expanded toolbar in the available screen area, with the LOGO above in portrait mode or to the left in landscape mode. If the group is larger than that area, relative placement takes priority; full visibility is not guaranteed.
- Entering and releasing a drag clears the LOGO pressed highlight. Ordinary clicks still collapse/expand the toolbar, and normal hover feedback remains.
- Invalid theme/current-tool types and certain numeric fields no longer interrupt loading later valid settings, including disabled update checks. This field-level recovery cannot recover an unparseable configuration file; back up before upgrading.
- Hiding the main UI also hides persistent tools such as Calculator; restore keeps their content and positions. Opening Settings from the tray while hidden does not wake the other windows.
- Settings dropdowns follow the light/dark theme. Click a preset color swatch for an alpha-aware color picker; the color code is read-only/copyable, and Cancel leaves the draft unchanged. Chalk uses a longer-period deterministic grain texture; visual acceptance remains with the user.
- Pre-release offscreen regression: 1296 passed, 7 skipped, and 1184 subtests passed; the actual configuration stayed byte-identical. The release owner reported their checks complete. Automated EXE smoke remains offscreen and the build is unsigned; see the [validation record](docs/release-validation-6.0.0.md) for coverage and limits.

## Quick start

These links and checksum examples refer to the published and verified **6.1.0 stable release**.

**[Download Windows x64 portable v6.1.0 (stable; includes EXE, no installation)](https://github.com/wcr20140908/MyScreenDraw/releases/download/v6.1.0/MyScreenDraw-v6.1.0-windows-x64.zip)**

[Release page and notes](https://github.com/wcr20140908/MyScreenDraw/releases/tag/v6.1.0) · [SHA-256 checksum](https://github.com/wcr20140908/MyScreenDraw/releases/download/v6.1.0/MyScreenDraw-v6.1.0-windows-x64.zip.sha256). The public assets were downloaded again and hash-verified; the extracted EXE passed an offscreen startup check.

> Do not download GitHub's automatic **Source code (zip)** / **Source code (tar.gz)** assets or **Code → Download ZIP**. Those contain source code, not the runnable application.

1. **Get the app**: download the portable ZIP above and extract **all its contents** into a new folder on your Desktop, another drive, or a USB stick. Do not run inside the ZIP or extract only the EXE: keep `MyScreenDraw.exe` beside the `_internal` folder. No installation or Python required; the only registry write happens if you turn on "Start with Windows" in Settings — see below.
2. **Launch**: double-click `MyScreenDraw.exe`. It creates `data/` (settings & autosave) and `exports/` (exports) beside itself on first run.
3. **Hide or exit**: press **F12** or the toolbar close button to hide to the system tray; the process keeps running. Click the tray icon to restore the interface. To quit, use the tray exit command and respond to the save confirmation.

> ⚠️ Put the app somewhere **you can write to** (Desktop, another drive, USB). Inside `C:\Program Files` it cannot save settings or data due to permissions.

## Features

### Annotation & drawing
- Eleven permanent pen styles: pen, fountain pen, brush, calligraphy, pencil, crayon, chalk, neon, dashed, rainbow and arrow, plus highlighter and laser pointer.
- Selecting a pen opens its settings immediately. Per-style options include taper/pressure response, nib angle/width, grain coverage/opacity, glow width/strength, dash length/gap, hue speed/saturation, and arrowhead size/angle. Each permanent style saves its own colour, width, speed-to-width setting, and advanced options; these can be reset. Changes affect new strokes, not existing ink.
- Colour dots inside the annotation and pen icons show the current colour without enlarging the main toolbar. Rainbow uses a multicolour dot.
- Hold-to-recognize shapes applies only to the plain pen. Highlighter offers colour/width/opacity; laser is a pointer and leaves no ink.
- Export limits: PNG/PDF preserve texture. SVG renders pencil/crayon/chalk as same-colour translucent solid strokes. EPS has no alpha compositing: textures become solid and neon retains its centre line; calligraphy keeps its flat-nib outline and dashes retain their length/gap.
- Eraser (area / stroke)
- Shapes: line, dashed line, triangle, rectangle, parallelogram, trapezoid, rhombus, circle, ellipse, angle
- 3-D shapes: cube, cuboid, cylinder, cone
- Box / click selection; duplicate, delete, move, scale, rotate; undo / redo

### Smart features
- **Hold-to-convert**: hold the pen still at the end of a stroke (~0.6 s) and it becomes a standard shape (a progress ring shows at the pen tip); lift immediately to keep it freehand — never triggered by accident
- 3 short collinear strokes merge into a dashed line
- Line endpoint snapping
- Geometry construction: circumcircle, incircle, medians, altitudes, diagonals, angle bisector, etc.

### Whiteboard
- The compact page list is anchored to the page navigation bar.
- First/last-page arrows appear grey but show a boundary hint when clicked.
- Select a page and use the red **Delete** button below the list. Confirmation defaults to cancel; deleting the only page leaves one blank page.
- Multi-page management with thumbnail navigation; use **Copy** / **Rename** below the list and drag thumbnails to reorder. Copies default to after the source; Settings can choose before, first or last
- White / black board switching
- Page-by-page export to PNG / PDF / SVG / EPS (page numbers on multi-page exports; SVG/EPS are vector and stay editable)

### Classroom tools
- **Drawing aids**: real millimetre/centimetre ruler, 45°/30° set squares, live-reading protractor (move, rotate, adjust range)
- **Random name picker**: import a txt/csv list; the drawn name is projected fullscreen in large type
- **Timer**: count up / count down; beeps and flashes red when finished
- **Magnifier**, **presentation spotlight** (dims the screen, bright region follows the mouse)
- Calculator
- Text and formulas: drag out a box, type multiple lines, change colour/width/rotation; the structured formula editor covers fractions, super/subscripts, roots, sums and integrals — tap a slot to type into it. Letters and digits come from the Windows touch keyboard; a symbol panel folds by category above it

### Import / export
- Import images or PDFs (embedded into the project file as base64 — **single self-contained file**, easy to share and back up)
- Export PNG / PDF / SVG / EPS
- Drag a `.msd` / `.json` project file onto the main panel to open it

### Settings & appearance
The Settings button opens five sections — appearance, interface, drawing, system, and about:

- The toolbar uses one icon-based layout; the mode button is labeled **Mouse**
- In mouse mode, annotation tools and whiteboard controls are hidden; only mouse, annotation, settings, and close remain. Click **Annotation** to return to drawing mode and reveal the full annotation menu
- **UI opacity** 35%–100%, applied to the control panels only. **The canvas and your ink are never faded**
- **Corner radius** 0–24px, applied consistently across panels and controls
- Light/dark theme, toolbar orientation, shape recognition, multi-touch drawing, and speed-to-width remain in Settings
- **Start with Windows** is off by default and writes only the current user's Run entry when enabled
- **Update channel** lets you choose stable or preview releases
- **In-app updates** ask before downloading and before installing, and preserve `data/`, `exports/`, settings, autosaves, roster data, and logs

### Document and annotation preferences in 6.1.0

**Settings** includes autosave interval, page-copy placement, annotation monitor and timer-alarm volume. Selecting an annotation monitor does not change the Windows primary display; a disconnected target falls back to an available display. Alarm volume defaults to **100** and can be set to **0** for silence; Windows volume and mute still apply.

Each imported PDF page becomes an independent whiteboard page. PNG/PDF export shows progress and supports cancellation. If a page fails, a modal lists the original missing page numbers; a usable partial PDF receives a separate filename and is never reported as complete success.

### New classroom preferences in 6.0.0

All three features are in **Settings** on the main toolbar. Introduced in 6.0.0, they are also included in the 6.1.0 download above.

#### Top of Settings: free/open-source and third-party service notice

- A dismissible yellow card explains that MyScreenDraw is free and open source. Paid third-party installation or assistance is not an official project fee; contact that provider about its services. This is not a modal prompt and does not open Settings automatically.
- No switch is needed: using the record in local `data/config.json`, the card is eligible on the first **three normal launches**, then on a launch whose version differs from the previous launch. This includes upgrades, downgrades, and returning to a previously used version. Launches count even if you never open Settings; reopening Settings does not increment the count.
- Click **×** at the card's top right to dismiss it for this run only. Reopening Settings keeps it hidden; a later eligible launch can show it again. Hiding to the tray with F12 and restoring is not a new launch. Resetting the local configuration restarts the count.

#### Settings → Drawing: Restore pen after page turn

- **Restore pen after page turn** is **on by default**. After an actual whiteboard page change, if you are using a non-annotation tool such as eraser, selection, or shapes (or are in mouse mode), the next left-button press or touch start restores your last annotation tool and continues handling that same contact. **No second tap is needed; the automatic switch does not discard the first stroke.**
- The restored tool includes the exact permanent pen style, highlighter, or laser. A restored laser still only points and leaves no permanent ink. An already-active annotation pen is not forcibly switched.
- Previous/next page, thumbnail navigation, a new page, and deleting the current page to show a surviving page all use this logic; deleting the only page leaves a blank page. Boundary-arrow clicks, choosing the current thumbnail, and deleting another page do not arm a new return.
- Deliberately selecting a tool after paging (including reselecting the current tool), switching mouse/drawing mode, leaving the whiteboard, or turning this option off cancels the pending return. Opening Settings alone does not cancel it. Mouse passthrough outside the whiteboard is unchanged.

#### Settings → Drawing: Use custom pen defaults

- **Use custom pen defaults** is one global switch, **off by default**, not a switch per pen. When off, the app keeps last-used settings. Turning it off neither deletes presets nor rolls back values already applied to live settings.
- Use **Pen type** below the switch to select a target. Each of the 11 permanent styles has independent colour, width, speed-to-width, and applicable advanced options, plus nib angle for calligraphy. Highlighter has colour, width, and opacity; laser has colour and width. You can edit and save even while the switch is off.
- **Edit a preset:** select a pen type, click its colour swatch to open the alpha-aware picker, confirm the colour, then click **Save preset**. The colour code is read-only/copyable; cancelling the picker leaves the draft unchanged. Editing fields or changing the dropdown alone neither saves to configuration nor switches the canvas tool. Missing presets use built-in defaults; they do not automatically capture last-used settings.
- **Save live settings:** adjust the target pen through its regular settings, select that same type in this editor, and click **Capture current**. This immediately saves the selected type's live settings as its preset and replaces that type's editor draft. It does not capture whichever unrelated tool is active, and no extra Save click is needed.
- When enabled, presets load during startup settings restoration and when returning from a different tool or pen style. Turning the global switch on also applies the preset immediately if the current tool is an annotation pen. An automatic page-turn return to a different annotation tool follows the same rule. Clicking the already-selected pen again only opens its settings; it does not reload the preset. Presets are not reset on every stroke.
- **Save preset** and **Capture current** do not themselves apply a preset. To try the saved values, leave the switch on, select another tool/style, and switch back. Temporary edits in regular pen settings never overwrite presets; those live values are replaced only when a preset is applied again. These operations affect future drawing, **not existing ink**.

If an older configuration lacks the new fields, page-turn restoration defaults to on, custom defaults to off, and notice counting starts with the first normal launch. Existing independent pen settings remain. The release passed the automated headless gates documented above, and the release owner reported their checks complete. No additional per-device or packaged-upgrade matrix is claimed; see the validation record.

## Usage

### Calibrating the ruler (important)
Before first use, calibrate: Tools → Drawing aids → **Calibrate this screen**, lining the two endpoints up with a physical ruler. Calibration is saved per display; until calibrated, a system-DPI estimate is used.

- Ruler: small tick = 1 mm, major tick = 1 cm; hover the body for a live mm/cm readout
- Mouse wheel or the orange circular handle changes the ruler **length** (mm spacing stays real); drag the purple square or use Ctrl + wheel to change body **width**
- Protractor: align its centre with the angle vertex and its baseline with one side; hover inside the semicircle for a live angle, hold Shift to snap to whole degrees
- Aids can be dragged to move, rotated with the teal handle, and **removed with a right-click**

### Mouse and annotation modes
Click **Mouse** to let mouse/touch input pass through the canvas to the application underneath; the toolbar contracts to its basic controls. Click **Annotation** to resume drawing and reveal the full annotation menu. Existing annotations are preserved.

### Project files & autosave
- Tools → Open / Save manages `.msd` project files (all whiteboard pages included)
- Autosave checks every 30 s by default and only writes changed content. Settings offers 15/30/60/120/300 s presets or a custom 5–86400 s interval. Very short intervals increase snapshot/compression/disk work and consume the retained-version count faster.
- The startup recovery prompt previews the selected version. Expand the older-version options to choose another valid autosave; selection only changes the preview, and Restore applies it
- Rely on explicit saves; autosave is only for recovery

### Verify a portable ZIP and upgrade manually
Download the ZIP and `.zip.sha256` from the same Release, then run in PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 .\MyScreenDraw-v6.1.0-windows-x64.zip
```

Compare the hash with the value in the `.sha256` file. Quit the old application through the tray, back up `data/`, `exports/`, and projects saved elsewhere, and extract the entire new ZIP into a new directory. Copy the backed-up data as needed. Do not run two versions against the same data. Autosave is not a version backup.

Since beta.8, old shared pen colour, width, and speed-to-width settings migrate into independent per-style profiles. 6.0.0 retains this migration. Changing one style no longer changes the others. Older versions may not preserve new pen effects; keep the original projects and data before downgrading.

## FAQ

**Q: Windows says "Windows protected your PC" / antivirus flags the app?**
A: The release is not code-signed and may trigger Windows reputation warnings. A warning is not proof of malware, but being open-source is not proof of safety either. Verify the download source and SHA-256 checksum and check with security software rather than ignoring the warning. Automatic update checks are enabled by default; drawings, rosters and logs are not uploaded. For offline use, disable update checks and do not download updates. Strictly isolated environments should block network access before the first launch.

Signing helps identify the publisher, but does not guarantee that SmartScreen or antivirus warnings disappear. SHA-256 checks integrity; it is not a digital signature. You can also [build from source](CONTRIBUTING.md). See the [code-signing notes](docs/code-signing.md) for the trust boundaries.

**Q: Where is my data?**
A: In the app folder: `data/` (settings, autosave, name list, local log) and `exports/`. Back up `data/` together with your projects.

**Q: Multiple monitors?**
A: The drawing canvas stays on the primary screen; the toolbar can travel across screens; ruler calibration is saved per display; capture/export can target a chosen screen.

**Q: CJK text missing in EPS export?**
A: EPS is vector PostScript using standard fonts; viewers without a CJK font may miss non-Latin glyphs. Use SVG when you need vector output with CJK text.

**Q: Can two people draw at once?**
A: Yes, since v5.2.0. The pen and highlighter accept several contacts at once — each finger draws its own stroke and dwells on its own clock, and undo removes the last stroke to *finish*. Both fingers share the current tool and colour (no pen-in-one-hand, eraser-in-the-other); select, shapes, text and eraser remain single-point.

## Privacy & data safety

- **Drawings, rosters and logs are not uploaded**. Update checks retrieve public release metadata.
- **Update checks**: The current version enables them for new installations (since beta.7) and respects an existing disabled setting. Choose stable or preview releases. A 24-hour timer starts when settings load; the first automatic check is about 24 hours later, not immediately at startup. You can also click **Check now**. Checks contact GitHub's release API (`api.github.com/repos/wcr20140908/MyScreenDraw/releases?per_page=30`). Automatic results only notify you; they never start a download or installation.
  - The existing design downloads in a background thread; see the known 6.0.0 download/installation defects and manual migration steps above, rather than assuming its updater works
  - The app asks before downloading and asks again before installing
  - ZIP validation rejects path traversal, symlinks, duplicate entries, oversized archives, excessive member counts, and archives missing `MyScreenDraw.exe`
  - Installation must preserve `data/`, `exports/`, settings, roster data, logs, and autosaves; synthetic-data preservation and failure paths in 6.0.1 passed automated checks, and backups remain necessary
  - For offline use, disable update checks and do not download updates; strictly isolated environments should block network access before the first launch
- **Start with Windows** (new in v5.5.0, off by default): when enabled, the app writes one value named `MyScreenDraw` under `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`, holding the path used to launch it. Turning the switch off deletes that value. Current user only — it never touches `HKEY_LOCAL_MACHINE`, needs no administrator rights, and this switch does not modify other registry entries.
- The local log (`data/events.jsonl`) may include file names — check it before sharing
- The name list (`data/roster.json`) contains student names; treat it as personal data and never ship it with the program

## Developers

- Build, test, coding rules and contribution flow: see [CONTRIBUTING.md](CONTRIBUTING.md)
- Full changelog: see [CHANGELOG.md](CHANGELOG.md)
- Architecture and maintenance boundaries: [architecture](docs/architecture.md)
- Offscreen regression and desktop acceptance: [testing guide](docs/testing.md)
- Packaging, verification, and stable-release gates: [release guide](docs/releasing.md)
- Code-origin and license review scope: [provenance notes](docs/provenance-audit.md)
- Security reporting: see [SECURITY.md](SECURITY.md)

## License

**GPL-3.0-or-later** — see [LICENSE](LICENSE). Third-party components are listed in [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt).

> Tech stack: Python · PyQt6 · pynput · PyInstaller (build-time only)
