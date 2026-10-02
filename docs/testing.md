# 测试与验收 / Testing and acceptance

适用基线：**v6.0.0-beta.8**。离屏回归、真实桌面输入和最终便携包验证是不同层级，不能互相替代。

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
| 更新与发布元数据 | `test_beta6_updater.py`、`test_release_hygiene.py` |

文件名中的旧 beta 编号表示测试引入背景，不表示该测试已失效。单元测试中的 mock 只能验证本地逻辑，不能证明真实桌面窗口收到输入。

## 2. 真实桌面与触控

这些测试会占用屏幕、鼠标或触摸输入。先获得使用者同意、保存工作，并与离屏测试分开运行。不要在用户上课时自动执行。

- `tests/real_screen_acceptance.py`：已有的桌面验收脚本；其覆盖范围不是完整的 beta.8 验收清单。
- `tests/manual_mouse_passthrough.py`：跨进程鼠标穿透人工探针，按脚本说明使用。
- `tests/run_touch_injection.py`：独立进程运行注入自检和多指画布测试：

```powershell
python tests/run_touch_injection.py
```

Windows 注入测试不等于实际触控设备测试。最终候选版还须在目标大屏验证：

- 11 种笔、颜色与参数独立保存，重启后恢复；已有笔迹不随设置改变。
- 鼠标／批注／白板反复切换，底层浏览器或演示程序能收到鼠标和键盘。
- 子菜单、工具栏、文字公式输入、软键盘在亮暗主题和不同缩放下可操作。
- 页面列表定位、首页末页提示、删除取消／确认、唯一页删除、保存与重新打开。
- F12 隐藏、托盘恢复、取消退出、保存失败后不退出，以及最终正常退出。
- 多指绘制、抬指与切笔后笔迹正确，撤销顺序符合实际笔完成顺序。

## 3. 最终便携包与长时间使用

`build.ps1` 会对构建目录和解压后的 EXE 执行 `--smoke-ui`。该选项构造生产窗口后退出，不运行完整交互流程；通过它不能宣称课堂实屏验收完成。

从最终 ZIP 解压出的程序再进行真实操作，记录包哈希、系统版本、显示缩放、显示器/触控设备、步骤和结果。稳定版候选建议至少完成一轮 60–90 分钟使用，包含多页、大量笔迹、纹理笔、图片/PDF、公式、自动保存和撤销重做，观察卡顿、内存增长与退出情况。

## 4. 记录证据而不是只记录通过数

测试报告应注明 commit、命令、环境、通过/失败/跳过数量、子测试数量及跳过原因。实屏证据和发布包验证单独列出。每个跳过项都应说明是平台限制、主动禁用还是尚未覆盖；不能将“未运行”写成“通过”。

当前测试数量会随代码变化，不是永久发布门槛。正式版需满足 [发布清单](releasing.md)，而不仅是达到某个测试数量。截图和日志公开前必须脱敏，不能包含名单、用户名、桌面文件或凭据。
