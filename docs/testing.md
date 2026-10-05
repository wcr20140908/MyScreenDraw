# 测试与验收 / Testing and acceptance

适用基线：**v6.0.1 源码修复候选，待发布与验收**。更新器实现仍在修改，本页列出应执行的验证，不声明已经通过。6.0.0 的已发布包及历史结果不作为本候选证据。离屏回归、真实桌面输入和最终便携包验证是不同层级，不能互相替代。

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

文件名中的旧 beta 编号表示测试引入背景，不表示该测试已失效。单元测试中的 mock 只能验证本地逻辑，不能证明真实桌面窗口收到输入。

## 6.0.1 更新器专项验证（结果待填）

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

**6.0.0 自带更新器存在下载/安装缺陷，6.0.1 新包不能追溯修复旧代码。** 用修复后的源码调用安装器或模拟旧目录的测试，不能标为“已发布 6.0.0 应用内升级通过”。手动迁移、新安装器事务、最终便携包和真实交互证据必须分别记录到 [6.0.1 验证记录](release-validation-6.0.1.md)。正式附件尚未发布时，只能标记本地候选演练；公开附件迁移验证需在发布后补齐。

## 2. 真实桌面与触控

这些测试会占用屏幕、鼠标或触摸输入。先获得使用者同意、保存工作，并与离屏测试分开运行。不要在用户上课时自动执行。

- `tests/real_screen_acceptance.py`：较早的桌面验收脚本；不代表完整的 6.0.0 验收清单。
- `tests/real_release_acceptance.py`：本轮新增的 Windows 输入验收脚本，涵盖 LOGO、设置及课堂工具等交互；源码运行结果不能替代最终 EXE 验收。
- `tests/manual_mouse_passthrough.py`：跨进程鼠标穿透人工探针，按脚本说明使用。
- `tests/run_touch_injection.py`：独立进程运行注入自检和多指画布测试：

```powershell
python tests/run_touch_injection.py
```

Windows 注入测试不等于实际触控设备测试。最终候选版还须在目标大屏验证：

- LOGO 横竖布局边缘拖动、继续/反向拖动、分离/折叠，以及释放后按下高亮清理；区分正常悬停反馈。
- 用旧配置恢复有效偏好；用单字段损坏样本确认后续设置仍恢复，尤其是关闭更新检查的偏好。单元测试不替代打包升级保留用户文件的验证。
- 11 种笔、颜色与参数独立保存，重启后恢复；已有笔迹不随设置改变。
- 鼠标／批注／白板反复切换，底层浏览器或演示程序能收到鼠标和键盘。
- 子菜单、工具栏、文字公式输入、软键盘在亮暗主题和不同缩放下可操作。
- 页面列表定位、首页末页提示、删除取消／确认、唯一页删除、保存与重新打开。
- F12 隐藏、托盘恢复、取消退出、保存失败后不退出，以及最终正常退出。
- 多指绘制、抬指与切笔后笔迹正确，撤销顺序符合实际笔完成顺序。

## 3. 最终便携包与长时间使用

`build.ps1` 会对构建目录和解压后的 EXE 执行 `--smoke-ui`。每次启动都单独强制 `QT_QPA_PLATFORM=offscreen`、`MYSCREENDRAW_NO_KEYBOARD=1`，并在 `finally` 中恢复调用方环境；仅传递 Hidden 不足以保证 Qt 不显示窗口。该选项以离屏平台构造生产窗口后退出，不运行完整交互流程；通过它不能宣称课堂实屏验收完成。

6.0.0 的历史收尾记录注明未查看图片或视频、未截图、未进行桌面操作；这不是 6.0.1 的执行结果。`test_build_smoke.py` 仅抽取 PowerShell 冒烟函数并模拟进程，覆盖启动失败、非零退出、超时、句柄清理失败与环境恢复；不启动真实 EXE。实际本地构建结果及跳过原因见 [6.0.0 验证记录](release-validation-6.0.0.md)。

整包升级使用显式运行的隔离验收脚本（不会由 pytest 自动收集）。旧预览包已从 GitHub Release 删除，请从保留的正式版 Release 下载旧包。以下保留 v5.5.1 升级到 v6.0.0 的历史执行示例，不表示该版本组合已经通过验收，也不是 6.0.0 → 6.0.1 的推荐用户升级路径：

```powershell
python tests/verify_portable_upgrade.py MyScreenDraw-v5.5.1-windows-x64.zip MyScreenDraw-v6.0.0-windows-x64.zip .git/release-validation/portable-upgrade
```

最后一个参数必须指向尚未使用的证据目录。脚本会启动实际旧、新 EXE，使用带中文、空格、方括号的隔离安装目录，执行真实更新事务，检查偏好、合成用户文件及重启计数。退出使用定向到测试进程的 Windows 消息；这不替代托盘退出交互验收。子进程 PATH 移除 Python，只证明随包运行库可用，不等于已在另一台未安装 Python 的机器验收。截图和原始日志保留在 `.git/`，不提交。

从最终 ZIP 解压出的程序再进行真实操作，记录包哈希、系统版本、显示缩放、显示器/触控设备、步骤和结果。稳定版候选建议至少完成一轮 60–90 分钟使用，包含多页、大量笔迹、纹理笔、图片/PDF、公式、自动保存和撤销重做，观察卡顿、内存增长与退出情况。

## 4. 记录证据而不是只记录通过数

测试报告应注明 commit、命令、环境、通过/失败/跳过数量、子测试数量及跳过原因。实屏证据和发布包验证单独列出。每个跳过项都应说明是平台限制、主动禁用还是尚未覆盖；不能将“未运行”写成“通过”。

6.0.1 的命令、结果和未覆盖项请填入 [当前验证记录（待填）](release-validation-6.0.1.md)；6.0.0 的历史结果与待补证据见 [历史验证记录](release-validation-6.0.0.md)。中断或失败的运行必须保留并解释，不能用较早成功结果代替当前候选版复跑。

当前测试数量会随代码变化，不是永久发布门槛。正式版需满足 [发布清单](releasing.md)，而不仅是达到某个测试数量。截图和日志公开前必须脱敏，不能包含名单、用户名、桌面文件或凭据。

## 离屏测试的数据隔离

`tests/conftest.py` 的会话级 fixture 仅在 Qt offscreen 模式下生效，将配置、名单、自动保存、导出和日志重定向到仓库外的临时目录，不复制真实用户配置。现有用例可继续覆盖各自的临时路径；实屏验收脚本不由此自动启动。`tests/test_runtime_isolation.py` 覆盖路径边界和真实设置写入函数。发布前完整回归还需独立核对真实配置的前后哈希；测试成功不能替代数据保全检查。


### 6.0.1 隔离 EXE 重启检查

构建候选包后，可运行不显示桌面窗口、不截图的隔离检查：

```powershell
python tests/verify_updater_restart.py MyScreenDraw-v6.0.0-windows-x64.zip MyScreenDraw-v6.0.1-windows-x64.zip 6.0.1 .git/release-validation/601-restart
```

证据目录必须是新目录。该脚本使用当前源码的更新事务替换旧包副本，验证新进程正常启动、版本、EXE 哈希、配置与合成用户文件，并检查手动再次打开。它不证明旧版内嵌更新器已经修好，也不覆盖真实触控交互。源码回归还覆盖新进程早退回滚、存活但未就绪时保留备份，不能以“进程未退出”代替启动就绪确认。
