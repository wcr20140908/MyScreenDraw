# Architecture and incremental decomposition

MyScreenDraw is a Windows-only PyQt6 application. `main.py` currently contains the
application bootstrap, canvas, control panel, input handling, native window stacking,
imports/exports, and classroom tools. This is deliberate legacy structure: classroom
interaction paths are tightly coupled and large rewrites are difficult to review safely.

## Boundaries

- `persistence.py`: validated project/autosave data and atomic JSON writes.
- `calculator.py`: AST-whitelisted arithmetic evaluation.
- `display_utils.py`: DPI, display selection, calibration, and measurement math.
- `eps_export.py`: dependency-free EPS serialization.
- `i18n.py`: the eight-language UI catalogue.
- `main.py`: Qt widgets, canvas state, native Windows integration, and orchestration.

## Decomposition rules

Future extraction should move one cohesive, testable responsibility at a time. Preserve
serialized page formats and public helper behavior, add regression tests before moving
code, and keep Win32 window-owner/Z-order operations together until they have an explicit
adapter and Windows test coverage. Do not perform a broad rewrite as part of a feature PR.

A safe order is: pure geometry helpers, persistence adapters, export adapters, classroom
utility widgets, then canvas and control-panel orchestration. Each step must retain the
offscreen test suite and a Windows smoke check.
