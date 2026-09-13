# MyScreenDraw v6.0.0-beta.2 — Second Beta Release

This is the second beta release of MyScreenDraw v6, with refinements to the lifecycle system and callback management.

## 🔧 What's Fixed

### Lifecycle & Background Mode
- **Timer management**: All callbacks (heartbeat, autosave, thumbnail updates, laser fade, keyboard watch) now properly pause when hiding to background
- **Restoration**: Timers correctly resume when returning from background mode
- **System tray**: Background mode lifecycle fully stable with no unwanted window reappearance

### Test Suite
- Fixed whiteboard layout test to use correct attribute (`wb_grid` instead of non-existent `wb_layout`)
- All 713 automated tests passing (10 skipped in offscreen mode where system tray is unavailable)

## 🎨 Features from v6.0.0-beta.1

### Unified Icon Interface
- **Single icon-based UI**: Removed the text/icon mode toggle — now uses a consistent icon+label layout optimized for touch
- **Original visual system**: All functional icons and the 'screen+ink' logo drawn from scratch, supporting 16/24/32/48/256px
- **Horizontal and vertical layouts**: Single-row horizontal or strict single-column vertical; scrollable tool area when space is tight
- **LOGO interaction**: Click to fold/unfold the toolbar (fold leaves only the logo visible); press and drag to move the panel

### Click Canvas to Close Menus
- Any temporary sub-menu (pen types, shapes, tools, files) closes when you click the canvas
- Does not consume the drawing/selection event — the same click continues your current tool action
- Does not interfere with text editing, tool selection, or independent windows (calculator, name picker, timer)

### System Tray & Background Mode
- **Background mode**: Close button and F12 now hide to the system tray instead of exiting
- **Tray menu**: Left-click restores the main UI; right-click shows Show/Hide, Settings, Restart (blue), Exit (bold red)
- **Safe exit dialog**: Three buttons — Cancel (show main UI), Exit without saving, Save then exit
- **Restart preserves work**: Unsaved content is recovered via temporary state handshake

### True Constant Pen Width
- Removed the artificial taper at stroke start
- With speed-to-width **off**: every segment uses the user-set pen width directly
- With speed-to-width **on**: preserves real speed measurement and genuine input pressure behavior

## 🗑️ Removed
- All rotation buttons from the main panel
- UI mode selection (old configs migrate to unified icon mode)
- Smart shape recognition toggle from pen sub-menu (feature remains)

## ⚠️ Known Limitations
- This is a **beta test version** — features and UI may change in the stable release
- Tray restore returns to pre-background state, stays in click-through until you select a tool
- During restart, if new process fails, old process keeps your content

## 📦 Installation
1. Download MyScreenDraw-v6.0.0-beta.2-windows-x64.zip
2. Extract to Desktop/drive/USB
3. Run MyScreenDraw.exe

**SHA-256**: 9a148e386f4a9f9ca9ff6fed6fb88ddc56739d37bb1fb93354a8247df799e287

## 🐛 Feedback
Report issues at: https://github.com/wcr20140908/MyScreenDraw/issues
