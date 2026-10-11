# 四种界面配色交付（2026-10-11）

基线：b8a301ea52c1e427cba606d1996c17b5d1b82bc5。隔离检出：C:/Users/WIN10/.codex/worktrees/four-color-schemes/MyScreenDraw。managed create_worktree 返回 Git is unavailable，attach_worktree 未接受登记；已使用 Git CLI 创建同基线的独立 worktree，主工作树文件没有写入，也没有在主树测试。

设置 → 外观 → 界面配色提供经典、A 石墨青绿、B 冷灰钢蓝、C 暖灰靛蓝。theme 仍只存 light/dark；新增 color_scheme 分别存 classic、graphite_teal、slate_blue、warm_indigo。旧配置缺键或键值损坏时回退经典，初始明暗模式仍为 dark。选择与明暗切换即时应用并沿用原子设置写入，重开恢复两个独立选项。

A/B/C 的六套 14-role token 按原报告逐项实现；旧角色别名兼容现有模块。浮窗、组合框 popup palette/delegate、工具栏 selected/pressed/disabled 图标与焦点隔离环同步；图标按状态缓存，纯颜色切换不重排工具栏。八语言标签走 tr。经典原始色值、用户笔/荧光笔/激光笔颜色、透明度、圆角、方向、折叠状态和按钮对象/尺寸保持兼容。main.py 保留 UTF-8 BOM。

写集：main.py、i18n.py、tests/test_color_schemes.py、tests/test_upgrade_settings.py、本说明。升级审计仅补充新 color_scheme 字段及非默认色系输入，新增正常重开与三种坏值隔离用例；没有削弱既有断言。教学模块/数据、AGENTS 和原配色研究报告未修改。

测试均在上述隔离树、冻结源码下执行，环境为：

~~~powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:MYSCREENDRAW_NO_KEYBOARD = '1'
$env:PYNPUT_BACKEND = 'dummy'
$env:PYTHONIOENCODING = 'utf-8'
python -B -m compileall -q main.py i18n.py tests/test_color_schemes.py
python -B -m pytest -q tests/test_color_schemes.py tests/test_theme_contrast.py tests/test_settings_and_ui_modes.py tests/test_i18n_and_telemetry.py tests/test_qt_dialog_i18n.py tests/test_ui_icons.py tests/test_upgrade_settings.py tests/test_pen_defaults.py tests/test_touch_layout.py --maxfail=5
~~~

语法检查 exit 0；最终组合回归 **526 passed, 431 subtests passed in 620.76s**。定向套件单独执行为 **91 passed in 27.59s**（命令：python -B -m pytest -q tests/test_color_schemes.py --maxfail=3）。覆盖四方案 × 明暗、设置选择和落盘重开、旧配置/损坏配置、用户内容与几何不变、Qt 图标四模式 × On/Off、缓存、焦点中性隔离和 1/1.25/1.5/2 倍 DPR。运行数据由离屏夹具放入临时目录。git diff --check 通过。

限制：验证基于 b8a301e，未复制正在修改的教学源码；未进行实屏/桌面捕获、原生输入、可见原生程序或物理 DPI/Windows 原生 popup 验收。经典保留旧配色；整窗透明度叠加任意真实桌面的对比度不作保证。未执行 PyInstaller build、安装、发布、push、main 合并或 cherry-pick。只交付一个本地提交，供提交级集成。
