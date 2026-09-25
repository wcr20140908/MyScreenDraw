# MyScreenDraw

> **中文**: [README.md](README.md)

MyScreenDraw is a fullscreen annotation / whiteboard / math-teaching tool built for **classroom touch screens**:

- **Annotate anything on screen** — pen, highlighter, laser pointer
- **Freehand shapes snap to standard shapes**: draw, then hold the pen still at the end — a progress ring fills and the stroke converts; lift to keep it freehand (lifting never converts)
- **Multi-page whiteboard** with white/black board switching; export page by page to PNG / PDF / SVG / EPS
- **Real millimetre-scaled ruler, protractor and set squares** (per-screen calibration) with live readings
- **Random name picker, timer, presentation spotlight, calculator** — a whole lesson without switching apps
- **No account; drawings, rosters and logs are not uploaded**. Automatic update checks are enabled by default and can be disabled in Settings. Downloads and installation each require separate confirmation; neither happens silently

Current version **v6.0.0-beta.7**. The UI follows the system language in 8 languages: English, 中文, Français, Español, Deutsch, Русский, 한국어, 日本語.

> Product screenshots are not included in the public release yet; the current local captures contain development-environment details and must not be committed to GitHub.

## Quick start

1. **Get the app**: extract the portable `MyScreenDraw` folder to your Desktop, another drive, or a USB stick (no installation; the only registry write happens if you turn on "Start with Windows" in Settings — see below).
2. **Launch**: double-click `MyScreenDraw.exe`. It creates `data/` (settings & autosave) and `exports/` (exports) beside itself on first run.
3. **Exit**: press **F12** (global hotkey, works even on the fullscreen canvas).

> ⚠️ Put the app somewhere **you can write to** (Desktop, another drive, USB). Inside `C:\Program Files` it cannot save settings or data due to permissions.

## Features

### Annotation & drawing
- Pen / highlighter / laser pointer (adjustable color, width, opacity; laser only indicates, leaves no ink)
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
- Multi-page management with thumbnail navigation
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

### Settings & appearance (beta.6)
The Settings button opens five sections — appearance, interface, drawing, system, and about:

- The toolbar uses one icon-based layout; the mode button is labeled **Mouse**
- In mouse mode, annotation tools and whiteboard controls are hidden; only mouse, annotation, settings, and close remain. Click **Annotation** to return to drawing mode and reveal the full annotation menu
- **UI opacity** 35%–100%, applied to the control panels only. **The canvas and your ink are never faded**
- **Corner radius** 0–24px, applied consistently across panels and controls
- Light/dark theme, toolbar orientation, shape recognition, multi-touch drawing, and speed-to-width remain in Settings
- **Start with Windows** is off by default and writes only the current user's Run entry when enabled
- **Update channel** lets you choose stable or preview releases
- **In-app updates** ask before downloading and before installing, and preserve `data/`, `exports/`, settings, autosaves, roster data, and logs

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
- Autosave runs every 30 s; after an abnormal exit the next launch asks whether to restore
- Rely on explicit saves; autosave is only for recovery

## FAQ

**Q: Windows says "Windows protected your PC" / antivirus flags the app?**
A: The release is not code-signed and may trigger Windows reputation warnings. A warning is not proof of malware, but being open-source is not proof of safety either. Verify the download source and SHA-256 checksum and check with security software rather than ignoring the warning. Automatic update checks are enabled by default; drawings, rosters and logs are not uploaded. For offline use, disable update checks and do not download updates. Strictly isolated environments should block network access before the first launch.

Why does it appear? The distributed exe is not yet code-signed. Fully removing the prompt requires the **publisher (developer)** to purchase a code-signing certificate and sign the release — that is a distribution-trust matter, not a program-security one, and virtually every free/open-source desktop app shows the same prompt on first run. If you are unsure, you can also build it yourself from source (see [CONTRIBUTING.md](CONTRIBUTING.md)).

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
- **Update checks**: beta.7 enables them for new installations and respects an existing disabled setting. Choose stable or preview releases. A 24-hour timer starts when settings load; the first automatic check is about 24 hours later, not immediately at startup. You can also click **Check now**. Checks contact GitHub's release API (`api.github.com/repos/wcr20140908/MyScreenDraw/releases?per_page=30`). Automatic results only notify you; they never start a download or installation.
  - Downloads stay inside the application and run in a background thread
  - The app asks before downloading and asks again before installing
  - ZIP validation rejects path traversal, symlinks, duplicate entries, oversized archives, excessive member counts, and archives missing `MyScreenDraw.exe`
  - Installation skips `data/`, `exports/`, settings, roster data, logs, and autosaves
  - For offline use, disable update checks and do not download updates; strictly isolated environments should block network access before the first launch
- **Start with Windows** (new in v5.5.0, off by default): when enabled, the app writes one value named `MyScreenDraw` under `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run`, holding the path used to launch it. Turning the switch off deletes that value. Current user only — it never touches `HKEY_LOCAL_MACHINE`, needs no administrator rights, and changes nothing else in the system.
- The local log (`data/events.jsonl`) may include file names — check it before sharing
- The name list (`data/roster.json`) contains student names; treat it as personal data and never ship it with the program

## Developers

- Build, test, coding rules and contribution flow: see [CONTRIBUTING.md](CONTRIBUTING.md)
- Full changelog: see [CHANGELOG.md](CHANGELOG.md)
- Code-origin audit: see [docs/provenance-audit.md](docs/provenance-audit.md)
- Security reporting: see [SECURITY.md](SECURITY.md)

## License

**GPL-3.0-or-later** — see [LICENSE](LICENSE). Third-party components are listed in [THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt).

> Tech stack: Python · PyQt6 · pynput · PyInstaller (build-time only)