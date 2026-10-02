# Architecture and maintenance boundaries

This document describes **v6.0.0-beta.8**, checked against the implementation on
2026-10-02. MyScreenDraw is a Windows desktop application built with Python and
PyQt6. The published package is a PyInstaller onedir Windows x64 build.

## Modules

| Module | Responsibility |
| --- | --- |
| `main.py` | Application bootstrap, `DrawingCanvas`, `ControlPanel`, shape recognition, input routing, page state, imports/exports, updates, and classroom-tool orchestration |
| `app_lifecycle.py` | Tray, hide/restore, exit confirmation, restart, and lifecycle state |
| `toolbar_windows.py` | Separate `LogoWindow` and `ToolbarWindow`, screen-bound positioning |
| `persistence.py` | Project/autosave validation, size limits, JSON/gzip I/O, and atomic writes |
| `display_utils.py` | Display selection, DPI, calibration, and measurement math |
| `formula.py` | Structured formula layout and painting |
| `touch_keyboard.py` | Windows touch-keyboard integration and cleanup |
| `eps_export.py` | EPS serialization without an additional export dependency |
| `calculator.py` | AST-whitelisted arithmetic evaluation |
| `i18n.py` / `ui_icons.py` | Eight-language UI catalogue and generated tool icons |
| `version.py` | Application version; Windows version resources and build guard must be synchronized |

`main.py` still owns tightly coupled classroom interaction paths. This is not a
web application, and it does not use a remote model for shape recognition.

## Pen settings and stored ink

The permanent styles are pen, fountain, brush, calligraphy, pencil, crayon, chalk,
neon, dashed, rainbow, and arrow. Highlighter and laser are separate tools.

- `PEN_STYLES` and `PEN_STYLE_OPTIONS` define styles and advanced option ranges.
- `DrawingCanvas.pen_profile()` supplies each style's colour, width, and
  speed-to-width settings. `collect_settings()` writes `pen_profiles`;
  `load_settings()` migrates legacy shared values into independent profiles.
- Advanced options are normalized before use. A stroke retains its own settings;
  changing the active tool must not retroactively change existing ink.
- `clone_segment()`, serialization, undo/redo, copying, and transforms must preserve
  style/options, fractional widths, and nib orientation. Rotating calligraphy also
  rotates the nib.
- Textured, dashed, and neon styles are grouped to avoid seams from per-segment
  composition. Texture generation is deterministic and cached.
- PNG/PDF retain texture effects. SVG textures and EPS texture/glow output have
  documented fallbacks; see the [README](../README.en.md).

## Input and window lifecycle

Drawing mode captures input on the canvas. Mouse mode uses native Windows window
styles for passthrough; Qt-only flags are not sufficient evidence of correct
cross-process mouse and keyboard delivery. Native owner/Z-order management keeps
floating tool windows above the canvas without hiding menus behind it.

F12 and the toolbar close action hide to the tray; they do not quit the process.
The tray restores the interface or starts the exit/restart flow. Keep callbacks,
timers, keyboard cleanup, and pending update threads consistent across those paths.

Whiteboard pages are owned by the canvas. The compact page list follows the page
navigation bar, not the main toolbar. Boundary arrows remain clickable for hints;
deleting a page requires confirmation, and deleting the only page leaves a blank page.

## Persistence and updates

Projects contain page data and embedded media. `persistence.py` currently uses
schema version 1 with bounded sizes/counts and atomic JSON writes. Autosave may
use gzip; compressed input also needs a decompressed-size bound. Runtime data
belongs in `data/` and exports in `exports/`, never in release assets.

Updates use background workers and GitHub release metadata. Stable/preview channel
selection and automatic-check preferences are persisted. Download and installation
require separate confirmation. ZIP validation and user-data preservation are not a
substitute for publisher authentication; see [SECURITY](../SECURITY.md).

## Rules for incremental decomposition

Extract one cohesive, testable responsibility at a time. Preserve serialized page
formats and public helper behaviour. Add regression coverage before moving code.
Keep Win32 window-owner/Z-order operations together until there is an explicit
adapter with Windows acceptance coverage. Do not combine a feature fix with a
large rewrite of `main.py`.

Prefer pure geometry helpers, persistence/export adapters, and classroom utility
widgets before moving canvas/control-panel orchestration. Every extraction retains
the [offscreen suite and relevant desktop acceptance checks](testing.md).
