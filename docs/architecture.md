# Architecture and maintenance boundaries

This document describes the **v6.0.0 source under release preparation**, reviewed
on 2026-10-03; it does not establish final-package acceptance. MyScreenDraw is a
Windows desktop application built with Python and PyQt6. Packaging targets a
PyInstaller onedir Windows x64 build; 6.0.0 has not yet been packaged or published.

## Modules

| Module | Responsibility |
| --- | --- |
| `main.py` | Application bootstrap, `DrawingCanvas`, `ControlPanel`, shape recognition, input routing, page state, imports/exports, updates, and classroom-tool orchestration |
| `release_notice.py` | Normalized launch/version notice policy and presentation-only dismissible settings card |
| `pen_defaults.py` | Independent preset normalization, capture/apply helpers, and embeddable preset editor; no main import or persistence ownership |
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

## Classroom preferences (6.0.0 source)

The controls live in **Settings**: the notice is first in the scrollable content;
**Drawing** contains **Restore pen after page turn**, followed by the custom-defaults
switch and editor. See the [user instructions](../README.en.md) and
[approved design](plans/2026-10-03-classroom-preferences-design.md). These are source
contracts, not evidence of runtime or final-package acceptance.

### Notice policy and session ownership

`release_notice.py` normalizes `notice_state = {launches, last_version}` and returns
an updated state plus eligibility from `begin_notice_session()`. Eligibility is the
first three normal launches OR a version change relative to the preceding launch,
including downgrades and returns to a previously used version. It is not a history
of every version ever seen. Invalid counts become zero; integer counts are clamped
to 0–2,147,483,647; non-string saved versions become an empty string.

`ControlPanel.begin_usage_session()` is guarded to run once and is called after
normal startup loads settings. It persists the advanced state even if Settings is
never opened. The smoke branch exits before this call; constructing a panel or
opening Settings alone does not advance the count. The helper itself has no I/O
or session deduplication. Tests that explicitly call it still advance their supplied
state; test isolation remains the caller's responsibility.

`ReleaseNoticeCard` renders localized plain text in light/dark amber styling; it
neither opens Settings nor interprets the project URL as an active link. Closing
hides the card and emits `dismissed`; the panel owns `_notice_visible` for this run.
Reopening Settings does not redisplay a dismissed card. Dismissal is not persisted;
resetting the saved configuration resets launch history. Paid third-party services
are identified as the provider's responsibility, not official project fees.

### One-shot return after whiteboard page changes

`DrawingCanvas.arm_page_pen_return()` sets transient `_page_return_pending` only
in whiteboard mode, with `whiteboard_auto_pen` enabled, and when drawing mode is off
or `draw_state` is not PEN/MARKER/LASER. New-page creation, actual `switch_page()`
navigation (including thumbnails), and deletion of the current page invoke it.
Boundary no-ops, the current thumbnail, and deleting another page do not arm it.
Deletion of the only page leaves a blank page and follows the current-page path.

`sync_canvas_input_mode()` keeps input available while the return is pending.
A non-synthesized left mouse press or a nonempty TouchBegin calls
`consume_page_pen_return()` before normal input dispatch. It selects
`last_annotate_tool` through `set_tool()` and continues the same event instead of
requiring a second contact. PEN uses the retained `pen_style`; MARKER and LASER
remain distinct, and LASER still leaves no permanent ink. Existing touch ownership
and mouse-synthesis handling remain in place; this path is not proof of compatibility
with every physical touch device.

Deliberate tool selection (including same-tool clicks), mouse/drawing mode changes,
leaving the whiteboard, or disabling the option cancels the pending return. Opening
Settings alone does not. The flag is neither stored in settings nor attached to a
page/project. Mouse passthrough outside the whiteboard is unchanged.

### Presets are separate from live pen profiles

`pen_defaults_enabled` is one global, default-off switch. `pen_defaults` contains
13 independent entries: the 11 `PEN_STYLES`, `marker`, and `laser`. Permanent pens
store `color`, `width`, `speed_width`, and applicable `options`; calligraphy adds
`calligraphy_angle`. Marker stores `color`, `width`, and `alpha_pct`; laser stores
only `color` and `width`. `PEN_STYLES`/`PEN_STYLE_OPTIONS` are passed from the host.
Missing/corrupt fields use factory values, unknown fields are dropped, dimensions
are clamped, and out-of-range style options use their declared defaults. Copies
prevent live edits from mutating saved presets or another style.

`PenDefaultsEditor` edits the selected key, not necessarily the active tool. Its
Save action emits `preset_saved`; Capture reads that key's live settings and emits
`current_captured`, replacing its draft. Both connect to `save_pen_default()` for
persistence, not live application. Dropdown changes do not switch the canvas tool
or save settings. Valid drafts survive dropdown changes, but are not persistent;
invalid colours disable Save. The editor remains usable with the global switch off.

`apply_current_pen_default()` is called after settings restoration and actual tool
or pen-style re-entry when enabled. Turning the switch on also finishes active ink
and applies the current annotation tool's preset. Same-tool/same-style clicks do
not reload it, and no per-stroke application occurs. Automatic page return uses the
same `set_tool()` path; it does not bypass the preset switch. Saving or capturing
alone does not apply; temporary regular-settings edits do not overwrite presets.
Turning the switch off keeps the current live values and saved presets. The helper
`apply_preset()` only changes the selected live configuration: the host owns stroke
completion, tool selection, UI refresh, and persistence. Existing ink is untouched.

## Input and window lifecycle

Dragging the LOGO positions it and an attached, visible toolbar as one bounded
rectangle: LOGO above in portrait mode, to the left in landscape mode. Detached
toolbars are bounded separately; a collapsed toolbar does not move with the LOGO.
Each oversized dimension anchors at the available area's left or top edge
rather than flipping or overlapping; not every control will necessarily fit onscreen.
The LOGO button clears its pressed state on drag activation and release; hover
feedback and ordinary click-to-collapse/expand remain separate behaviours.

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

`ControlPanel.collect_settings()` currently emits 46 top-level fields: the prior
41 plus the following additions, saved in `data/config.json` through the existing
atomic settings writer. This source inventory is not a coverage result.

| Key | Missing/invalid value behaviour | Owner |
| --- | --- | --- |
| `notice_state` | Normalize to launch count 0 and empty last version as needed | Notice helper; panel starts the session |
| `whiteboard_auto_pen` | `true` unless a valid boolean was saved | Panel preference; canvas transient return flag |
| `pen_defaults_enabled` | `false` unless a valid boolean was saved | Panel application policy |
| `pen_defaults` | Independent factory presets for missing/corrupt fields | Preset helper; panel persists edits |
| `last_annotate_tool` | `PEN` unless `PEN`, `MARKER`, or `LASER` was saved | Panel; exact PEN style remains in `pen_style` |

Legacy shared pen settings still migrate to live `pen_profiles`. New presets are
not automatically captured from those profiles; with the default-off switch they
do not overwrite them. Session dismissal and page-return arming are not serialized.


Settings loading checks theme/current-tool types and bounds numeric eraser,
highlighter, laser, and magnifier values before applying them. These fixes prevent
the affected fields from aborting later valid preferences, including disabled
update checks. This is not recovery of an unparseable JSON file or proof that a
packaged update preserves every user file; that requires separate validation.

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
