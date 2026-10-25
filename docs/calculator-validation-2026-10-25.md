# 课堂综合计算器验证记录 — 2026-10-25

本记录针对基于 `170e3cfeab6e66861ef71c1dc9f8ddcd3142e206` 的未提交工作区，覆盖课堂综合计算器升级及后续反馈。GitHub 工单为 [#13](https://github.com/wcr20140908/MyScreenDraw/issues/13)。本次没有创建发行包。

## 实屏高度问题

在 Windows 实屏、设备缩放 175% 下，通过项目现有、带 PID/HWND 校验的原生输入驱动点击模式和历史按钮。使用隔离的临时运行目录；截图来自桌面合成像素。

| 场景 | 修复前窗口高度 | 修复后窗口尺寸（Qt 逻辑单位） |
| --- | ---: | --- |
| 进制模式 | 548 | 400 × 254 |
| 基础模式收起历史 | 625 | 400 × 384 |
| 科学模式 | — | 422 × 396 |
| 基础模式展开历史 | — | 760 × 560 |

根因是堆叠控件把隐藏页面的高度算入当前页面、宿主窗口在模式/历史变化后未收缩，以及历史栏的尺寸策略影响宽度分配。修复后使用当前页面尺寸提示、重新计算并约束窗口尺寸，历史栏按可见空间选择右侧或底部布局；历史更高时键盘保持自身高度并靠上排列。

缩放矩阵另外复现了俄语单位换算在窄屏下出现横向滚动的问题。右侧历史的条件现在同时考虑当前页面最小宽度；长文案的单位操作按钮在窄屏排列成两行。布局选择使用滚动区域可见宽度，避免沿用控件此前的较大宽度。

最终原生复测退出码 0，记录为 `passed`；真实键盘输入 `sin(30)+√16` 和 `Ans×2`，界面分别显示 `4.5` 和 `9`。历史显示使用 12 位有效数字，复制仍取完整结果。

私有证据保存在忽略目录 `.superpowers/sdd/calculator-upgrade/native-final/`，包含原生截图、输入记录和 `native-result.json`；原问题截图保存在相邻 `native-before/`。这些证据没有纳入发行资源。

## 自动化验证

使用 `QT_QPA_PLATFORM=offscreen`，测试运行路径由隔离 fixture 接管。

计算器、历史、面板、宿主、缩放矩阵、黑白板文案、相关教学接口和原生驱动静态校验：**99 passed in 37.94s**。

```powershell
python -m pytest -q tests/test_board_style_label.py tests/test_calculator_advanced.py tests/test_calculator_history.py tests/test_calculator_panel.py tests/test_calculator_main_integration.py tests/test_calculator_scaling.py tests/test_teaching_toolbox_interface.py tests/test_teaching_calculator_native_driver.py --tb=short
```

矩阵覆盖八语言 × 两个屏幕方向 × 五模式 × 历史开/关 × 六档缩放，共 960 个布局状态。检查窗口在屏内、历史不与页面重叠、没有横向滚动、收起后的键盘高度及触控按钮高度。它使用模拟屏幕尺寸，不代表实际多屏硬件验收。

教学完整流程、私有状态、生命周期、界面偏好/缩放、配置升级、单实例、构建 smoke 与翻译/遥测：**558 passed、2 skipped、19 subtests passed in 710.15s**。两个跳过是离屏模式没有系统托盘。

```powershell
python -m pytest -q tests/test_teaching_toolbox_interface.py tests/test_teaching_toolbox_courses.py tests/test_teaching_calculator_native_driver.py tests/test_teaching_calculator_private_state.py tests/test_teaching_calculator_visibility.py tests/test_release_620_scripts.py tests/test_teaching_complete_process.py tests/test_teaching_private_center.py tests/test_lifecycle.py tests/test_lifecycle_regressions.py tests/test_taskbar_windows.py tests/test_interface_preferences.py tests/test_interface_scaling.py tests/test_upgrade_settings.py tests/test_single_instance.py tests/test_build_smoke.py tests/test_i18n_and_telemetry.py --disable-warnings --tb=short
```

`python -B tests/real_teaching_620.py --self-check` 通过：48 章节、412 个目录步骤完成静态分类、负例校准与 29 个 Win32 清理模拟检查；该命令没有运行真实教学章节。源码编译与 `git diff --check` 通过（仅有原有换行格式提示）。

后台窗口、构建依赖、项目往返、导出、运行路径隔离及发布资料检查：**75 passed、178 subtests passed、5 failed in 10.50s**。五个失败均属于同一个文档链接检查的子场景：工作区原先删除了 `release-notes-v6.0.1.md` 和 `release-notes-v6.1.0.md`，README/CHANGELOG 中仍有相关链接。本次保留这些已有删除，没有把这组结果描述为全仓通过。

```powershell
python -m pytest -q tests/test_background_windows.py tests/test_build_dependencies.py tests/test_project_roundtrip.py tests/test_export_ui_610.py tests/test_export_pipeline_610.py tests/test_runtime_isolation.py tests/test_release_hygiene.py --disable-warnings --tb=short
```

## 黑白板切换文字

对应工单 [#14](https://github.com/wcr20140908/MyScreenDraw/issues/14)；本记录两项工单已补充验证结果并关闭。

图标按钮只同步了原按钮的提示和无障碍名称，没有同步 `board_style` 的可见文字；白板状态刷新也在更新原按钮文字之前执行同步。现在原按钮文字更新后再同步，并让图标文字同步该操作。

当前黑板显示“白板”，当前白板显示“黑板”，表示点击后的目标。回归通过真实 Qt 按钮点击覆盖连续切换、主题刷新、提示和无障碍名称；复用现有八语言翻译。

## 验证边界

本次完成源码实屏计算器复测与相关离屏回归。未运行实际多显示器移动/拔插、另一台硬件或最终 EXE 便携包；未重跑此前耗时约 35 分钟的全仓测试。构建 smoke 用例验证脚本行为，不表示已构建并交互验收发行包。
