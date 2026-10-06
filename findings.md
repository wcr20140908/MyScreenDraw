# Findings — 6.1.0

- Initial checkout clean, HEAD 7c270d7; version 6.0.1, origin wcr20140908/MyScreenDraw.
- main.py ~14,449 lines; persistence.py owns atomic JSON/gzip writers and project limits.
- Qt tests already isolate runtime outside checkout when QT_QPA_PLATFORM=offscreen; preserve this isolation.
- Reader enforces 64 MiB physical and decompressed limit; existing generic atomic writers have no symmetric size validation (investigation underway).
- No AGENTS.md found in checkout or D: root.
- Confirmed page loss root cause: save_project/auto_save serialize only capture_page in annotate mode; open_project_from_path/apply_autosave_data clear pages in that mode. Preserve existing semantics (annotate continues editing active board page), not a separate new document.
- Dirty flag was only set in a few UI paths; update handoff relied on this incomplete flag. Added actual content revision detection and explicit modal user choice.
- Serialization cache now exists, but mutation-path audit remains essential (text editing outside whiteboard uses direct content_revision and needs central mark_content_changed).
- persistence.py new atomic_write_project/atomic_write_autosave require integration at main project/autosave call sites; generic writers remain for config/legacy tests.

## Additional confirmed findings
- Custom autosave interval selection had setter/UI feedback: selecting Custom with a preset numeric value immediately reset the combo. Suppressing that sync for the Custom action fixes it.
- File-extension-only compression detection broke successful plain project saves named .gz and compressed snapshots renamed otherwise. Reader now checks gzip magic while retaining physical/decompressed byte limits.
- All-page export raster lists caused avoidable memory pressure; silent exception/null skipping made requested and exported page counts diverge without an explicit failure. Streaming engine retains original indices and validates output.
- PDF insertion previously put all page images onto one active page. New import stages an entire bounded batch and appends independent pages only on success.
- Text-only serialized pages were not recognized by the renderer's serialized-data probe; fixed while adding recovery previews.
- Coalesced angle adjustments changed geometry without incrementing document revision after the first edit. Regression demonstrates stale saved angle; fixed with post-mutation revision invalidation.
- Many heavy function-scoped widgets were only hidden between tests. Native Qt teardown could then occur during a later constructor; explicit owned-tree cleanup resolved two reproduced access violations and subsequent focused runs pass.
- Current-page stroke cache drastically reduces warm clipped redraw/selection work but has a measured cold-build cost. Raw before/after numbers are retained and the tradeoff is documented.
- Full tests that use inspect.getsource are invalidated if main.py is edited while the same pytest process is running; final build freezes source inputs and rejects changed source at sealing.

- Native page drag exposed QListWidget.startDrag performing source-row deletion after custom document reorder/rebuild. Owned QDrag prevents double deletion; refresh also repairs row-count mismatch. QListView IconMode dragMove filtering prevented edge autoscroll until replaced with generic QAbstractItemView housekeeping and explicit own-source MoveAction acceptance.
- Native Windows drag loops can starve Qt timers: deterministic test input now uses a bounded Win32-only worker, steady edge hold, ownership-checked press and guaranteed release.
