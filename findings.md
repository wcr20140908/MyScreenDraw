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


---

# 6.3.0 核实记录

- 当前origin为GitHub，分支main，源码元数据6.2.0；工作树有前序功能及历史说明删除，尚未提交。
- GitCode仓库由用户提供；官方文档给出 api.gitcode.com/api/v5/repos/{owner}/{repo}/releases 及按tag取得附件上传地址。网页需要客户端渲染，须以真实HTTP验证匿名接口，不依赖搜索摘要。
- 客户端现有更新实现位于main.py，支持稳定／预览；release_artifact.py、build.ps1、create_release.ps1有严格源码／收据／ZIP／教学资源门禁。
- 国内分发既有调研提出第二来源需独立校验的元数据；核实匿名访问后决定确实可用的签名／哈希分发方案。
- cryptography在本机可用，尚未决定新增运行时依赖。
- 本地agent.md已写入，root .gitignore与.git/info/exclude均排除，git ls-files确认未跟踪。

规划文件已存在，原6.1.0记录已保留并追加当前任务；旧记录说明实际屏幕测试须串行、隔离合成数据，不操作其他应用窗口。

真实HTTP核实：GitCode仓库公开且token可读；仓库基本信息匿名返回401，但/releases列表匿名200且目前为空。/releases/latest匿名400，不能照搬GitHub latest路径。GitHub匿名/releases正常，当前最高正式发布v6.2.0。国内客户端可使用公开/releases列表，仍须验证附件URL、上传字段与真正匿名下载。

Git ls-remote 实测两平台 main/HEAD 均为170e3cfeab6e66861ef71c1dc9f8ddcd3142e206，无分歧，v6.3.0标签尚不存在。Git认证使用临时askpass，不修改或保存用户凭据助手。决定新增签名更新清单（两平台同一份）以绑定ZIP大小/SHA-256/版本/EXE哈希；Windows EXE代码签名状态仍如实标明未签名。

GitCode真实创建release_status=pre成功，prerelease=true。通过返回的file.gitcode.com地址PUT合成附件成功；公开assets中附件type=attach，含id/size/digest，browser_download_url与GitHub同路径结构但域名gitcode.com。匿名API附件下载返回200，重定向到file-cdn.gitcode.com，回下载69字节与合成内容SHA-256一致。DELETE release本身返回405；正在按官方附件删除接口及自己创建的标签清理。GitCode不能把draft/prerelease布尔参数照搬GitHub，应使用release_status=pre/latest。
