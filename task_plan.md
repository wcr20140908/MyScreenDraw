# 6.1.0 implementation and verification plan

## Objective / acceptance
Preserve the complete requested scope. Keep extensive offscreen verification. Latest explicit user instruction (2026-10-06) now authorizes and requests extensive real-screen testing, superseding the earlier offscreen-only restriction. Real tests must use isolated synthetic data and operate only owned application windows. At most one child agent is active at a time. Never write credentials into tracked files or logs.

## Design / decisions
Use incremental changes around the existing PyQt6 application rather than a rewrite. Keep the complete document independent of visible whiteboard mode; desktop annotation edits its active page; revision-keyed caches and immutable serialization snapshots feed background persistence. Keep Qt painting on its owning thread and stream one export page at a time. Modal unsaved-content and partial-export dialogs are required. Retain compatibility with existing projects. New controls follow the current page rail/settings patterns. PDF import creates one board page per PDF page. Page copy placement defaults after source, with before/front/back choices. Teaching-feature discussion is an assessment, not an unrequested feature build.

## Phases
- [complete] 1. Inspect and reproduce data-loss/open failures; run full offscreen baseline.
- [complete] 2. Fix document state, readable atomic writes, unsaved guards (open/update/exit).
- [complete] 3. Revision-aware background autosave, recovery history preview, interval settings.
- [complete] 4. Streaming PNG/PDF exports, cancellation/progress/failed-page dialogs; PDF page import.
- [complete] 5. Page duplicate/rename/drag reorder; revision/visible-first thumbnails.
- [complete] 6. Baseline stroke rendering benchmark then completed-path/bounds and incremental stroke caches.
- [complete] 7. Monitor settings and timer-end volume default 100; teaching feature assessment.
- [complete] 8. Full offscreen regressions, package smoke/reopen verification, 6.1.0 release evidence and publish.

## Requirement evidence matrix
Each phase must record relevant tests and commands in progress.md, with explicit release acceptance in docs/release-validation-6.1.0.md. A green test unrelated to a requirement is not evidence for it. Native Windows testing is explicitly authorized by the latest instruction. Keep native-input runs serial, synthetic and isolated; monitor selection is checked by code and synthetic screens without changing the OS primary monitor.

## Errors
Custom autosave selector resynchronized itself to its preceding preset; fixed and verified. Legacy update tests needed separate install-confirmation and Save/Discard/Cancel dialog results. Compression-by-suffix prevented reopening renamed files; regression reproduced, magic-byte reader implemented.

## Final acceptance
All implementation and local/public release phases are complete. Version 6.1.0 is published at release commit bfd172c5d15546b7a8c4b0181d7821f55fe71646. Public assets match the accepted ZIP/EXE hashes and extracted smoke exited 0. Hardware limits are explicit in docs/release-validation-6.1.0.md. Final documentation follow-up and clean remote status are checked before closing the goal.
