# Touchscreen toolbar attachment implementation plan

**Goal:** Repair LOGO/toolbar separation on classroom touch displays, including collapse/expand and saved startup layouts.

**Architecture:** Retain the two topmost tool windows and use the LOGO position as their common anchor. Dragging either window moves the pair. Read legacy configuration by keeping the LOGO position and recomputing the toolbar position for the current orientation and available screen area.

**Tech stack:** Python, PyQt6, pytest, PyInstaller.

The toolbar previously had no drag threshold. Its position callback set and persisted a detached state, which both expansion and startup explicitly preserved. The Qt pointer/mouse path therefore allowed minor touchscreen movement to create a persistent split layout.

Resetting only at expansion would allow the problem to recur. Filtering only touch input would leave legacy configurations and synthesized mouse events unresolved. Keep the pair attached for every input source and apply the Qt drag distance before starting a drag.

The user authorized continuing without confirmation. GitHub Issues remain the requirement tracker; the gh CLI is unavailable in this environment, so issue operations are blocked. This file records implementation steps.

## Implementation

1. Reproduce the defects with production Qt windows and the actual positioning methods. Add edge, orientation, reverse drag, jitter, legacy configuration, expand, and restart regression cases; confirm they fail before changing production code.
2. Update toolbar_windows.py: use QApplication.startDragDistance(), preserve pointer offset through boundary clamping, and clear drag state on release.
3. Update main.py: derive the LOGO anchor from toolbar dragging, always attach during relayout, and migrate legacy split settings. Retain toolbar_detached=false for compatibility with old configuration readers.
4. Update the configuration audit for the existing 6.2.0 custom palettes and infinite whiteboard settings, and require them to survive startup.
5. Run relevant offscreen configuration, UI, lifecycle, theme, and window-layer regressions; build to a separate portable directory; run frozen EXE startup checks and validate the packaged contents.
6. Document the local artifact and checks. Physical touchscreen hardware remains an explicit verification gap.
