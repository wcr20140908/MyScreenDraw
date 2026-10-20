# C13 界面与设置课程资源与接线

2026-10-13。独立交付 4 章 27 步：layout_theme 13、monitor_audio 5（实际按分支走4步）、lifecycle 5、system 4。29个静态八语言键，顺序 zh/en/fr/es/de/ru/ko/ja。

## 宿主接入

- i18n 合并 INTERFACE_COPY，catalog 加入 courses/c13.json。
- fixture IDs：interface.c13.layout_theme、interface.c13.monitor_audio、interface.c13.lifecycle、interface.c13.system；各对应 fixtures/<ID>.msd，为一页合成白板。
- 私有素材加载后调用 prepare_interface_fixture(panel, fixture, paths)。基线为icon、竖向、浅色、经典、界面不透明度100、显示器自动、计时音量0，写入私有config.json。
- APPLICATION_EVENTS / APPLICATION_TARGETS 合入 INTERFACE_EVENTS / INTERFACE_TARGETS。使用 interface_bindings(panel)，配套 reveal_interface_target(panel, target)；logo目标不要自动展开工具栏。
- multiple_monitors 条件需读当前 QApplication.screens() 数量>1。intro的默认路径single_screen解释单屏，多屏分支select_monitor要求选择真实已连接的具体显示器。两个分支均汇合到volume。

## main 方法与事件

常规装饰器为 interface_action，方法到事件的映射在 INTERFACE_METHODS。

| 方法 | 事件 | 结果details |
|---|---|---|
| _set_orientation_from_settings | settings.orientation_changed | orientation、saved |
| toggle_toolbar_collapsed | toolbar.visibility_changed | visible、logo_visible |
| toggle_theme | settings.theme_changed | theme、applied、saved |
| set_color_scheme | settings.color_scheme_changed | scheme、applied、saved |
| set_ui_opacity | settings.opacity_changed | percent、changed、applied、ink_unchanged、saved |
| set_annotation_screen | settings.monitor_changed | configured、applied、saved |
| set_timer_alarm_volume | settings.timer_volume_changed | volume、changed、saved |

结果只在前后实际变化后提交。主题/配色观察真实样式表变化；透明度读取各操作窗口实际windowOpacity并确认canvas不受影响；显示器只接受当前已连接项且canvas在目标屏；持久化读取本练习config.json，不凭方法被调用就声称保存成功。无bus直接原方法。零参数theme/collapse保持真实Qt slot签名，不传clicked(bool)。

## targets 与真实控件

| target | 引用 |
|---|---|
| settings.orientation.landscape/portrait | btn_orient_landscape / btn_orient_portrait |
| toolbar.logo | logo_window |
| settings.theme | btn_theme |
| settings.color_scheme | color_scheme_combo |
| settings.opacity | ui_opacity_slider |
| settings.monitor | document_preferences.monitor_combo |
| settings.timer_volume | document_preferences.volume_slider |

layout_theme实际执行横/竖、收起/展开、深/浅、graphite_teal/slate_blue/warm_indigo/classic四个配色及不透明度改变。未重新启用旧classic文字栏模式。

## 生命周期与系统说明

lifecycle.pause_resume复用当前宿主的 practice.resumed：真实pause将引擎暂停，宿主resume确认原先paused且仍在同一步后发恢复事件。当前引擎在paused阶段拒收结果；因此没有新增或伪造practice.paused事件来绕过门禁。控制条的暂停/继续始终可用，该步input_policy=free。

托盘/F12隐藏、托盘显示、真正退出均分开说明；不点击会终止当前练习的退出路径。停止教学仍由既有控制条结束练习并恢复父工作。system章更新通道、检查/下载/安装、自启动均为information，无wait、无可操作系统按钮target，不联网或写注册表。

## 验证记录（2026-10-14，直接验收完成）

使用正式共享接线，仅运行 tests/test_teaching_toolbox_interface.py 的5项；环境为 QT_QPA_PLATFORM=offscreen、MYSCREENDRAW_NO_KEYBOARD=1、PYNPUT_BACKEND=dummy、PYTHONIOENCODING=utf-8。

```powershell
python -B -m pytest -q -p no:cacheprovider --tb=short tests/test_teaching_toolbox_interface.py
```

最终整组结果：**5 passed in 5.84s，退出码0，无失败或teardown error**。资源/八语言、计算器/私有名单、UP/DOWN计时、私有放大镜/聚光灯，以及C13实际设置用例全部通过。

C13的 test_real_layout_four_schemes_opacity_and_private_audio 实际覆盖横竖、收起/展开、深/浅、四套配色、不透明度实际改变且画布不受影响、单屏说明分支和计时音量保存到私有config.json。资源测试验证全部八语言文本、四份C13合成白板及system章所有步骤均为information且没有可操作系统target。

唯一测试文件复用正式main的Qt连接，没有业务方法重新装饰、i18n注入或refresh_magnifier替代函数。grab_screen失败钩子确保私有练习不抓桌面；sys.excepthook输出完整Qt异常并在teardown报告失败，不吞错误。此前C12名单两处日志参数冲突与聚光灯退出事件问题已由主线程修复，本次整组运行验证通过。

状态：C12/C13独立资源、适配模块、直接测试与接线文档已收尾，本组无剩余失败。本轮只更新两份交付文档，不改共享文件，也不追加测试。

验证边界：当前离屏环境只有一个显示器；没有实际验证多显示器切换、宿主生命周期pause/resume、父现场恢复或最终全课程同QProcess串联，由主线程负责。没有执行更新、自启、退出或托盘路径。本次未运行C11、46章串联或导出一致性审查，也未跑冻结矩阵/全仓回归；没有构建、打包或发布。
