# MyScreenDraw

> **中文**: [README.md](README.md)

MyScreenDraw is a fullscreen annotation / whiteboard / math-teaching tool built for **classroom touch screens**:

- **Annotate anything on screen** — pen, highlighter, laser pointer
- **Freehand shapes snap to standard shapes**: draw, then hold the pen still at the end — a progress ring fills and the stroke converts; lift to keep it freehand (lifting never converts)
- **Multi-page whiteboard** with white/black board switching; export page by page to PNG / PDF / SVG / EPS
- **Real millimetre-scaled ruler, protractor and set squares** (per-screen calibration) with live readings
- **Random name picker, timer, presentation spotlight, calculator** — a whole lesson without switching apps
- **Fully offline**: no network, no uploads, no account — suitable for classrooms and restricted environments

Current version **v5.3.2**. The UI follows the system language in 8 languages: English, 中文, Français, Español, Deutsch, Русский, 한국어, 日本語.

> Product screenshots are not included in the public release yet; the current local captures contain development-environment details and must not be committed to GitHub.

## Quick start

1. **Get the app**: extract the portable `MyScreenDraw` folder to your Desktop, another drive, or a USB stick (no installation, no registry changes).
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

## Usage

### Calibrating the ruler (important)
Before first use, calibrate: Tools → Drawing aids → **Calibrate this screen**, lining the two endpoints up with a physical ruler. Calibration is saved per display; until calibrated, a system-DPI estimate is used.

- Ruler: small tick = 1 mm, major tick = 1 cm; hover the body for a live mm/cm readout
- Mouse wheel or the orange circular handle changes the ruler **length** (mm spacing stays real); drag the purple square or use Ctrl + wheel to change body **width**
- Protractor: align its centre with the angle vertex and its baseline with one side; hover inside the semicircle for a live angle, hold Shift to snap to whole degrees
- Aids can be dragged to move, rotated with the teal handle, and **removed with a right-click**

### Click-through mode
Tap "Click-through" so the mouse/touch passes through to the app underneath; tap "Drawing mode" to resume annotating. Existing annotations are never lost.

### Project files & autosave
- Tools → Open / Save manages `.msd` project files (all whiteboard pages included)
- Autosave runs every 30 s; after an abnormal exit the next launch asks whether to restore
- Rely on explicit saves; autosave is only for recovery

## FAQ

**Q: Windows says "Windows protected your PC" / antivirus flags the app?**
A: This is Windows' normal warning for **unsigned programs** — it does **not** mean your PC is infected. Click "More info → Run anyway" to use it, or run an antivirus scan to confirm — the app is **open-source and fully offline** (no network, no uploads).

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

- **Fully offline**: no network, no uploads, no update service
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