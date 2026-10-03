# 6.0.0 classroom preferences: approved design

Approved by the user on 2026-10-03. This expands the pending stable release; it does not authorize a language rewrite or broad main.py refactor.

## Behaviour
- Settings starts with a dismissible amber open-source notice. Eligibility is the first three normal application launches and the first launch of each later version. Opening settings does not increment the counter. Dismissal lasts for the current launch. Smoke/tests do not consume normal launches.
- Whiteboard page changes arm one automatic return to the last annotation tool (including the exact pen style, marker or laser) if currently using a non-annotation tool. The first canvas contact both switches and draws. A deliberate tool selection after paging cancels the pending action. Actual page changes include new-page and thumbnail navigation; boundary no-ops do not arm. Default enabled. Mouse passthrough outside whiteboard remains unchanged.
- One default-off switch controls custom defaults for all annotation pens. Each pen has an independent preset: colour, width, speed response and applicable advanced parameters, including marker/laser settings. Applying a preset happens on re-entry to the tool or startup, never on each stroke. Editing temporary settings never overwrites presets. Settings provides an editor and capture-current action.

## Architecture
Keep Qt integration in ControlPanel/DrawingCanvas. Add small independent preference/UI helper modules with no main.py import, and persist normalized JSON through the existing atomic settings writer. Preserve all pre-existing 41 fields and migrate missing new fields safely. Input arming is transient, not persisted. No private runtime data enters Git or release assets.

## Verification and release
Red/green focused tests, complete offscreen suite, mouse and injected-touch coverage, real desktop runs in light/dark themes, screenshots reviewed locally, frozen package smoke and isolated old-install upgrade. Build and publish v6.0.0 only after gates pass. Record failures/interruptions as well as successes, and explicitly identify untested physical hardware/multi-machine/long-soak conditions. Commit/push/release as authorized, then discuss modularization versus C/C#/C++ without implementing a migration.
