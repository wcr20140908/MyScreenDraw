# 测试与验收 / Testing and acceptance

适用基线：**v6.2.0 正式版（2026-10-18）**。本页记录离屏回归、实际原生桌面输入、最终便携包和公开附件回下载等不同层级的验证方式及边界。

离屏回归、实际原生桌面输入、最终便携包和公开附件回下载是不同层级，分别记录各自的验证结果；真实触控及跨设备范围按目标环境核对。[6.0.1 验证记录](release-validation-6.0.1.md)及 [6.1.0 验证记录](release-validation-6.1.0.md)保留历史版本结果。

## 1. 默认离屏回归

在 Windows、仓库根目录和已安装运行依赖的虚拟环境中执行：

```powershell
python -m pip install pytest pytest-subtests
$previousPlatform = $env:QT_QPA_PLATFORM
try {
    $env:QT_QPA_PLATFORM = 'offscreen'
    python -m pytest -q -rs --ignore=tests/test_touch_injection.py --ignore=tests/test_multitouch_injection.py --ignore=tests/test_multitouch.py
    if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed' }
} finally {
    if ($null -eq $previousPlatform) {
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    } else {
        $env:QT_QPA_PLATFORM = $previousPlatform
    }
}
```

该范围与 `build.ps1` 一致；`-rs` 额外列出跳过原因。不要去掉离屏设置后对整个测试目录做默认发现，否则构造画布时可能弹出全屏窗口或争抢输入。

| 领域 | 主要回归文件 |
| --- | --- |
| 笔形、配置隔离与纹理差异 | `test_pen_styles.py`、`test_pen_profiles.py`、`test_speed_width.py` |
| 鼠标穿透与窗口层级 | `test_canvas_passthrough.py`、`test_window_stacking.py`、`test_thumbnail_zorder.py` |
| 白板与生命周期 | `test_whiteboard_pages.py`、`test_lifecycle.py`、`test_lifecycle_regressions.py` |
| 保存与异常文件 | `test_project_roundtrip.py`、`test_persistence_safety.py`、`test_autosave_size.py` |
| 文字、公式、键盘 | `test_text_workflow.py`、`test_formula.py`、`test_touch_keyboard.py` |
| 升级设置恢复与旧共享画笔迁移 | `test_upgrade_settings.py` |
| LOGO 整体边界与按下状态清理 | `test_logo_drag_regressions.py` |
| 更新与发布元数据 | `test_beta6_updater.py`、`test_release_hygiene.py`、`test_release_artifact.py` |
| 后台窗口、主题与调色盘、粉笔集成 | `test_background_windows.py`、`test_pen_defaults.py`、`test_chalk_texture.py`、`test_final_ui_integration.py` |
| 构建无屏保护、DLL 查找与异常清理 | `test_build_smoke.py`、`test_build_dependencies.py` |
| 教学目录、epoch、协议、状态与独立进程 | `test_teaching_catalog.py`、`test_teaching_engine.py`、`test_teaching_protocol.py`、`test_teaching_state.py`、`test_teaching_practice.py`、`test_teaching_complete_process.py` |
| 教学结果与输入、漫游及遮挡 | `test_teaching_business_adapters.py`、`test_teaching_core_input.py`、`test_teaching_page_drag_input.py`、`test_teaching_roam.py`、`test_teaching_example_occlusion.py`、`test_teaching_selection_occlusion.py` |
| 无限白板、自定义配色与完整缩略图 | `test_infinite_whiteboard.py`、`test_whiteboard_ink_pixels.py`、`test_custom_colors.py`、`test_thumbnail_layout.py`、`test_page_management_610.py` |
| 隐藏棱、设置与更新说明 | `test_box_hidden_edges.py`、`test_settings_collapse.py`、`test_settings_feedback.py`、`test_update_notes.py` |
| 递归源码与精确教学资源发布门禁 | `test_release_620_scripts.py`、`test_release_artifact.py`、`test_teaching_packaging.py` |

文件名中的旧 beta 编号表示测试引入背景，不表示该测试已失效。单元测试中的 mock 只能验证本地逻辑，不能证明真实桌面窗口收到输入。6.2.0 正式版已发布；公开附件、校验和及实际覆盖范围以对应 Release 和发布收据为准。

## 1.1 教学分层与判定负对照

教学 `test_teaching_*_process.py` 和 `test_teaching_complete_process.py` 覆盖实际 QProcess、私有练习目录、进度协议与原工作恢复；在 offscreen 下使用控件/适配器驱动，并非 Windows 原生输入验收。逐章原生驱动则使用独立练习宿主，不能反过来证明正常父子进程 IPC、原工作恢复或冻结包启动。

判定须同时核对真实业务结果与教学状态：操作入口取得 session/run/step epoch/operation ID；迟到、重复、旧 epoch 结果及夹具准备不得推进步骤。取消、失败、部分导出应符合各自结果条件；点击按钮、直接发送事件或赋值为“已完成”都不能代替业务结果。漫游核对平移/缩放、锚点、Fit/Home 和内容/撤销历史不变；排序核对完整页面身份顺序与当前页身份。

每项新增回归还应做 mutation/负对照：临时恢复对应旧缺陷或输入已知错误结果，要求**相关断言**失败，再恢复修复并复跑。图像判定也须有已知坏图，避免“没有画出来”“抓错图”“只看到页码”仍被判为通过。正式结果须注明负对照范围，而非只写全部绿色。

## 1.2 6.0.1 更新器专项验证（历史场景，后续版继续回归）

先运行只读元数据测试（`-B` 禁止生成字节码缓存，不导入应用或启动 EXE）：

```powershell
python -B -m unittest discover -s tests -p test_release_hygiene.py -v
```

此测试只证明版本、文档和既有发布元数据断言满足要求，不能证明下载/安装可用。更新器回归文件和最终命令由维护者按完成后的实现确认，再与上面的完整离屏门禁一并复跑。不能为通过测试而删除或放宽涉及 6.0.0 的有效版本断言。

| 场景 | 应核对的行为与证据 |
| --- | --- |
| 检查与下载并行状态 | 状态独立；重复检查、重复下载和关闭设置不导致并发安装或丢失下载任务 |
| 已知/未知总大小 | 可信总大小时检查百分比及字节数；缺少总大小时仅字节数与不定进度，无伪造百分比 |
| 取消及异常 | 下载中取消、网络中断、归档失败后清理状态与临时文件，不安装、不修改用户数据；记录可再次下载的结果 |
| 源码目录保护 | 从源码运行时拒绝应用内覆盖安装，工作树前后无安装产生的改动 |
| 安装参数和退出等待 | 目标版本和旧 PID 正确传递；安全等待旧进程退出，验证超时/身份异常/退出取消不会继续替换 |
| 版本、重启和回滚 | 目标版本匹配、真实重启可验证；版本不符、启动失败、占用/权限失败时核对回滚和诊断，不能仅断言启动函数被调用 |
| 用户数据保全 | 对合成的 `data/`、`exports/`、配置、名单、自动保存、日志作前后哈希/内容比对，覆盖成功、取消和失败；不使用真实隐私数据 |
| 6.0.0 手动迁移 | 最终包在新目录解压；旧版完全退出后备份并复制 `data/`、`exports/`，不覆盖隐私文件；快捷方式改为新 EXE，核对 6.0.1 版本与再次启动 |

候选版正式附件已发布；迁移和公开附件核验按 6.2.0 Release 执行。

## 2. 真实桌面与触控

这些测试会占用屏幕、鼠标或触摸输入。先获得使用者同意、保存工作，并与离屏测试分开运行。不要在用户上课时自动执行。

- `tests/real_screen_acceptance.py`：较早的桌面验收脚本；不代表完整的 6.0.0 验收清单。
- `tests/real_release_acceptance.py`：6.0.x 时期的 Windows 输入验收脚本，涵盖 LOGO、设置及课堂工具等交互；源码运行结果不能替代最终 EXE 验收。
- `tests/manual_mouse_passthrough.py`：跨进程鼠标穿透人工探针，按脚本说明使用。
- `tests/run_touch_injection.py`：独立进程运行注入自检和多指画布测试：

```powershell
python tests/run_touch_injection.py
```

### 6.2.0 actual native driver（显式选择运行）

- `tests/real_teaching_620.py`：按章节或课程串行运行 C01–C13 原生操作；包含 c05.roam 的平移、滚轮缩放和 Fit/Home。每章是新的源码练习进程；暂停/教学中心使用本地桥接，不声称覆盖正常 IPC/父窗口恢复。系统、自启、更新、托盘相关信息步骤不执行对应系统改动。
- `tests/real_features_620.py`：独立覆盖 13 页极端笔迹的完整缩略图、多列跨行 OLE 排序/边缘滚动/关闭、CUBE/CUBOID 四方向绘制及三虚九实棱线像素、c05.reorder 直接/中间态/错误顺序路径。
- 两者共用 `tests/native_input_620.py`。Qt 提供几何换算、状态读取和事件循环（光标定位经 QCursor 做 DPI 换算后由 Win32 回读核对）；按钮/按键/滚轮通过 Win32 注入，文字使用 Unicode `SendInput`，拖放进入真实 OLE 循环。不用 QTest、直接业务调用、替换拖放循环或伪造对话框结果取得完成分。初始宿主/夹具构造与收尾不算用户操作。

驱动在按下前核对光标回读、目标 HWND/PID 与预期根窗口，键盘核对前台归属；透明教学高亮的 Qt 命中歧义须由原生命中交叉确认，不能临时隐藏真实遮挡。物理 Escape 为紧急中止。不要与其他原生驱动并行或在运行时操作桌面。超时仅处理所拥有的子进程；强制终止前按输入日志尝试在仍属子进程的目标释放按下状态，无法确认清理时必须记为未确认，不能向其他程序盲发 UP。

以下是**静态检查命令**，不导入应用/Qt、不调用 Win32、不截图，不代表已运行实屏：

```powershell
python -B tests/real_teaching_620.py --self-check
python -B tests/real_teaching_620.py --all --plan
python -B tests/real_features_620.py --self-check
python -B tests/real_features_620.py --all --plan
```

`--self-check` 校准未知章节/动作的拒绝与 fake-Win32 清理路径；feature 校准还包含空白、实线覆盖隐藏虚线、可见棱误画虚线、缩略图单侧缺失/左右互换/页码干扰和错误排序。它们检查判定器能拒绝指定坏输入，不证明产品已画出正确画面。获得单独实屏授权后，才选择如 `--chapter c05.roam`、`--chapter c05.reorder` 或 `--case thumbnails` 并传入全新、私有、位于 `.ccgui` 下的 `--output` 目录；`--all` 也是实屏运行，不因带有自动化驱动就默认获准。

截图由 `SRCCOPY|CAPTUREBLT` 抓取实际合成屏幕，包含分层窗口，不是 `QWidget.grab()` 或生产渲染函数的替代图。截图、输入日志、逐步 report 和失败现场只保留于本地私有证据目录，不上传/发布或放入便携包；画面仍可能含桌面个人信息。公开记录只摘录脱敏的步骤、命令、退出码、结果/未覆盖项和包哈希，不伪造不存在的截图或报告链接。

Windows 注入测试是原生窗口输入回归的一部分；物理触控设备仍按目标环境记录。正式版在目标大屏继续核对：

- LOGO 横竖布局边缘拖动、继续/反向拖动、分离/折叠，以及释放后按下高亮清理；区分正常悬停反馈。
- 用旧配置恢复有效偏好；用单字段损坏样本确认后续设置仍恢复，尤其是关闭更新检查的偏好。单元测试不替代打包升级保留用户文件的验证。
- 11 种笔、颜色与参数独立保存，重启后恢复；已有笔迹不随设置改变。
- 鼠标／批注／白板反复切换，底层浏览器或演示程序能收到鼠标和键盘。
- 子菜单、工具栏、文字公式输入、软键盘在亮暗主题和不同缩放下可操作。
- 页面列表定位、首页末页提示、删除取消／确认、唯一页删除、保存与重新打开。
- 无限白板的鼠标/单指平移、滚轮/双指缩放、锚点保持、Fit/Home、切回笔输入；逐页视图保存/复制/重开及负坐标和屏外笔迹的缩略图/四格式导出。
- 多列缩略图完整显示（含首末笔迹与页码）、跨行排序、边缘滚动与关闭；正确中间排序不提前通过，最终完整顺序正确才推进教学。
- 教学控制器/提示/示例不遮挡真实操作，完成、跳过、暂停/恢复及退出后原工作和设置保留。
- F12 隐藏、托盘恢复、取消退出、保存失败后不退出，以及最终正常退出。
- 多指绘制、抬指与切笔后笔迹正确，撤销顺序符合实际笔完成顺序。

## 3. 最终便携包与长时间使用

`build.ps1` 会对构建目录和解压后的 EXE 执行 `--smoke-ui`。每次启动都单独强制 `QT_QPA_PLATFORM=offscreen`、`MYSCREENDRAW_NO_KEYBOARD=1`，并在 `finally` 中恢复调用方环境；仅传递 Hidden 不足以保证 Qt 不显示窗口。该选项以离屏平台构造生产窗口后退出，不运行完整交互流程；通过它不能宣称课堂实屏验收完成。

6.0.0 的历史收尾记录注明未查看图片或视频、未截图、未进行桌面操作；这不是 6.0.1 或 6.2.0 的执行结果。`test_build_smoke.py` 仅抽取 PowerShell 冒烟函数并模拟进程，覆盖启动失败、非零退出、超时、句柄清理失败与环境恢复；不启动真实 EXE。实际本地构建结果及跳过原因见 [6.0.0 验证记录](release-validation-6.0.0.md)。

整包升级使用显式运行的隔离验收脚本（不会由 pytest 自动收集）。旧预览包已从 GitHub Release 删除，请从保留的正式版 Release 下载旧包。以下保留 v5.5.1 升级到 v6.0.0 的历史执行示例，不表示该版本组合已经通过验收，也不是 6.0.0 → 6.0.1 的推荐用户升级路径：

```powershell
python tests/verify_portable_upgrade.py MyScreenDraw-v5.5.1-windows-x64.zip MyScreenDraw-v6.0.0-windows-x64.zip .git/release-validation/portable-upgrade
```

最后一个参数必须指向尚未使用的证据目录。脚本会启动实际旧、新 EXE，使用带中文、空格、方括号的隔离安装目录，执行真实更新事务，检查偏好、合成用户文件及重启计数。退出使用定向到测试进程的 Windows 消息；这不替代托盘退出交互验收。子进程 PATH 移除 Python，只证明随包运行库可用，不等于已在另一台未安装 Python 的机器验收。截图和原始日志保留在 `.git/`，不提交。

稳定版使用建议至少完成一轮 60–90 分钟使用，包含多页、大量笔迹、纹理笔、图片/PDF、公式、自动保存和撤销重做，观察卡顿、内存增长与退出情况；该建议用于后续环境复查。

## 4. 记录证据而不是只记录通过数

测试报告记录 commit、命令、环境、通过/失败/跳过数量、子测试数量及跳过原因。实屏证据和发布包验证单独列出；正式版发布记录已随收据归档。

本说明记录 6.2.0 正式版的分层验证方法、输入保护和复查边界；正式版持续沿用这些门禁。

当前测试数量会随代码变化，不是永久发布门槛。正式版需满足 [发布清单](releasing.md)，而不仅是达到某个测试数量。截图和日志公开前必须脱敏，不能包含名单、用户名、桌面文件或凭据。

## 离屏测试的数据隔离

`tests/conftest.py` 的会话级 fixture 仅在 Qt offscreen 模式下生效，将配置、名单、自动保存、导出和日志重定向到仓库外的临时目录，不复制真实用户配置。现有用例可继续覆盖各自的临时路径；实屏验收脚本不由此自动启动。`tests/test_runtime_isolation.py` 覆盖路径边界和真实设置写入函数。发布前完整回归还需独立核对真实配置的前后哈希；测试成功不能替代数据保全检查。


### 6.0.1 隔离 EXE 重启检查（保留历史命令）

6.0.1 当时的候选包使用以下不显示桌面窗口、不截图的隔离检查；保留原版本组合，不作为 6.2.0 的运行记录：

```powershell
python tests/verify_updater_restart.py MyScreenDraw-v6.0.0-windows-x64.zip MyScreenDraw-v6.0.1-windows-x64.zip 6.0.1 .git/release-validation/601-restart
```

证据目录必须是新目录。该脚本使用当前源码的更新事务替换旧包副本，验证新进程正常启动、版本、EXE 哈希、配置与合成用户文件，并检查手动再次打开。它不证明旧版内嵌更新器已经修好，也不覆盖真实触控交互。源码回归还覆盖新进程早退回滚、存活但未就绪时保留备份，不能以“进程未退出”代替启动就绪确认。
