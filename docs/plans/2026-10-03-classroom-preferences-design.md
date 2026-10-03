# 6.0.0 classroom preferences: approved design

Approved by the user on 2026-10-03. This expands the pending stable release; it does not authorize a language rewrite or broad main.py refactor.

**Status:** source behaviour reconciled with `main.py`, `pen_defaults.py`, and `release_notice.py` on 2026-10-03. Stable 6.0.0 is still unpublished and not yet packaged. This documentation pass does not run tests, start a GUI, build, commit, push, or publish. Existing validation records are not changed.

## Behaviour

### 1. Dismissible notice at the top of Settings

The first item in Settings is a yellow/amber card explaining that MyScreenDraw is
free and open source and that paid third-party installation/assistance is the
provider's responsibility, not an official project fee. It is not a modal prompt
and does not automatically open Settings. No opt-in switch is required.

Eligibility is the first three normal launches recorded in `data/config.json`,
then the first launch after a change from the preceding launch's version. This
includes downgrades and revisiting an old version, not just never-before-seen
versions. Opening Settings does not increment the counter; a normal launch counts
even if the card is never viewed. Close (×) hides it for the entire current run,
including subsequent Settings openings, but not later eligible launches. Tray
hide/restore does not start a new session. Resetting local configuration resets
the history. Construction and the startup smoke branch do not count normal launches;
isolated tests must not use real user settings.

### 2. First-contact whiteboard pen restoration (default on)

**Settings → Drawing → Restore pen after page turn** arms one automatic return
only after a page transition when currently in a non-annotation tool or mouse mode.
The last annotation tool includes the retained permanent pen style, highlighter,
or laser. The first left-button press or touch start switches and continues the
same event: no extra tap or lost first stroke due to switching. Laser remains a
pointer, not permanent ink. Already-active annotation tools are not forced to switch.

Previous/next navigation, thumbnail jumps, new pages, and deletion of the current
page use the return path; deleting the only page leaves a blank page. Boundary
no-ops, selecting the current thumbnail, and deleting another page do not arm a new
return. A deliberate tool choice (even the same tool), switching mouse/drawing mode,
leaving whiteboard mode, or turning the option off cancels the pending action.
Opening Settings alone does not cancel it. Mouse passthrough outside the whiteboard
is unchanged. Arming is transient, not saved in settings or projects.

### 3. Independent custom pen defaults (one switch, default off)

**Settings → Drawing → Use custom pen defaults** controls all pens; there are no
per-pen enable switches. Off means retain last-used live settings, not delete
presets or undo an earlier application. Below it, **Pen type** selects an independent
preset for each of 11 permanent styles, highlighter, or laser. Permanent pens store
colour, width, speed response, and applicable advanced options; calligraphy adds
nib angle. Highlighter stores colour/width/opacity; laser stores colour/width only.
Missing preset fields use factory values, not an implicit capture of live settings.

The editor remains usable when the switch is off. **Save preset** saves the selected
pen's edited values; invalid colour disables saving. **Capture current** immediately
saves that selected pen type's live configuration and replaces its draft, with no
second Save click required. It does not capture some other active tool. Dropdown
selection neither changes the canvas tool nor saves to configuration. Valid drafts
can survive dropdown changes but must be explicitly saved to persist.

Saving/capturing does not apply a preset. When enabled, startup settings restoration
and returning from another tool or pen style apply it; enabling the switch while
an annotation tool is current also applies immediately after finishing active ink.
Same-tool/same-style clicks only open settings and do not reload; presets are never
applied on each stroke. To try saved values, keep the switch on and switch away and
back. Automatic page restoration through `set_tool()` follows the same policy.
Temporary regular-settings edits do not overwrite saved presets. Only future drawing
uses applied values; existing strokes and their saved style/options remain unchanged.

## Architecture
Qt integration stays in `ControlPanel`/`DrawingCanvas`. `release_notice.py` owns pure
normalization/eligibility and the presentation-only card; the panel starts one normal
session and owns dismissal. `pen_defaults.py` owns independent normalization,
capture/apply helpers, and editor signals; the panel owns persistence, the global
switch, safe application timing, and UI refresh. Neither helper imports `main.py`.

The existing atomic settings writer stores normalized JSON. Preserve the original
41 fields and add `notice_state`, `whiteboard_auto_pen`, `pen_defaults_enabled`,
`pen_defaults`, and `last_annotate_tool` (46 top-level fields in current source).
Missing fields default to fresh notice history, auto-return on, custom defaults off,
factory presets, and PEN respectively. The exact permanent pen style remains in
`pen_style`; legacy shared values still migrate into live `pen_profiles`. Session
dismissal and page-return arming are not persisted. No private runtime data enters
Git or release assets. See [architecture](../architecture.md) for ownership details.

## Verification and release
The intended gates remain focused red/green tests, the full offscreen suite,
mouse and injected-touch coverage, real desktop runs in both themes, locally reviewed
screenshots, frozen-package smoke, and isolated old-install upgrade. These are future
gates, not results asserted by this design or by the current documentation pass.
Physical hardware, multi-machine, and long-soak limitations must be stated separately;
record failures and interruptions as well as successes in the existing validation
workflow when that work is authorized.

This pass is limited to the seven named documentation files in the
[implementation plan](2026-10-03-classroom-preferences.md), with UTF-8, link, and diff
checks only. Keep the beta.8 download entry and stable-release preparation wording.
No code, scripts, tests, or validation reports may change; no GUI, commit, push, or
release is authorized here. Build/publish and the original optional discussion of
modularization versus C/C#/C++ remain separate future work, not a language migration.
