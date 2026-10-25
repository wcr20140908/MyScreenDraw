# Interface preferences implementation plan

**Goal:** Add a language preference, complete interface scaling, and an option to never offer autosave recovery at ordinary startup.

**Architecture:** Read validated startup preferences before creating QApplication. Use Qt's native scale factor for the entire application so widgets, fonts, icons, spacings, menus, dialogs, and hit areas share one coordinate system. Language and scale apply after restarting and the Settings page says so; pending preferences never change the current document. Preserve existing restart snapshot handling, autosave creation, and explicit File → recovery.

**Tech stack:** Python, PyQt6, pytest.

The user authorized implementation without further confirmation and cancelled package preparation. No packages will be generated for this change. The GitHub CLI is unavailable; issue operations cannot run.

## Tasks

1. Add a stdlib startup-preference module with language validation, bounded integer scale percentages, bounded JSON reads, and scale environment handling that cannot compound on restart. Use it before the normal QApplication construction and inherit the effective UI environment in private teaching processes.
2. Add complete eight-language strings and settings controls for system/native language names, a scale slider with percentage and restart hint, and an explicit never-prompt recovery checkbox.
3. Persist the three preferences, load them independently of other settings, synchronize controls with signals blocked, and suppress only the ordinary startup recovery entry.
4. Test invalid settings, persistence, restart language catalogs, whole-application Qt rendering at multiple ratios in isolated subprocesses, noncompounding restart environments, normal and manual recovery behavior, and existing toolbar/layout regressions.
5. Update source documentation to reflect the unbuilt current source and record actual checks, without publishing or modifying release assets.
