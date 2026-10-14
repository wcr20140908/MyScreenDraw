# C12 工具箱课程资源与接线

2026-10-13。独立交付 5 章 33 步：calculator 7、roster 6、timer 9、magnifier 6、spotlight 5。正文与六个明确虚构的名字共 36 键，静态八语言顺序 zh/en/fr/es/de/ru/ko/ja。

## 宿主接入

- i18n 合并 TOOLBOX_COPY，catalog 加入 courses/c12.json。
- fixture IDs：toolbox.c12.calculator、toolbox.c12.roster、toolbox.c12.timer、toolbox.c12.magnifier、toolbox.c12.spotlight。各对应 fixtures/<ID>.msd，均为一页合成白板数据。
- 私有素材加载后调用 prepare_toolbox_fixture(panel, fixture, paths)；准备过程抑制事件，名单经真实 save_roster 写私有 roster.json，计时器预设2秒并静音。
- APPLICATION_EVENTS / APPLICATION_TARGETS 分别合入 TOOLBOX_EVENTS、TOOLBOX_TARGETS。绑定使用 toolbox_bindings(panel)，reveal 可用 reveal_toolbox_target(panel, target)；现有 canvas.ink 保持原绑定。
- 零参数装饰方法仍暴露零参数 Qt slot，clicked(bool) 不转发给无参数业务方法。无 bus 直接执行原业务函数。

## main 方法与事件

| 真实方法 | 装饰器/事件 | 结果判断 |
|---|---|---|
| open_calculator | toolbox_action('calculator.opened') | 实际窗口从隐藏到显示 |
| _calc_input | toolbox_action('calculator.input') | 输入观察 expression/display；按=用 calculator.calculated，记录原式与真实结果 |
| open_roster_panel | toolbox_action('roster.opened') | 实际窗口显示 |
| draw_random_name | toolbox_action('roster.drawn') | 集合新增一个、unique、drawn、total、displayed、fictional、私有 saved |
| reset_drawn_names | toolbox_action('roster.reset') | 已点集合从非空变空，名单仍为6人，私有 saved |
| handle_timer_click | toolbox_action('timer.panel_opened') | 子面板实际显示 |
| set_timer_mode | toolbox_action('timer.mode_changed') | mode/target/seconds 真实变化 |
| toggle_timer_running | teaching_timer_toggle | timer.running_changed；DOWN开始时保存 timer.finished 原操作上下文 |
| reset_timer | toolbox_action('timer.reset') | 秒数归零、running=false、真实时钟停止 |
| _timer_finished | teaching_timer_finished | 原上下文、原目标时长、实际DOWN归零/停钟/alerting后才提交 timer.finished |
| handle_magnifier_click | toolbox_action('magnifier.opened') | 真实工具状态、非空私有图像 |
| Canvas.step_magnifier_zoom | toolbox_action('magnifier.zoom_changed') | 实际zoom变化和increased |
| on_magnifier_size_changed | toolbox_action('magnifier.size_changed') | 实际size变化 |
| refresh_magnifier | toolbox_action('magnifier.refreshed') | 新非空pixmap cacheKey、source=private_canvas |
| set_tool | toolbox_action('spotlight.changed') | 真实SPOTLIGHT开启/退出 |
| handle_spotlight_click | toolbox_action('spotlight.changed') | 在工具动作抑制范围外观察实际开/关，覆盖再次点击退出 |
| Canvas.mouseMoveEvent | teaching_spotlight_move | SPOTLIGHT中实际mouse_pos变化，提交x/y/moved |

TOOLBOX_METHODS 列出常规映射；handle_spotlight_click 需额外使用同一个 toolbox_action 装饰器，三个专用装饰器另接。切章/停止时调用 discard_timer_completion(panel)，取消旧异步上下文；引擎的epoch门禁保留。DOWN不直接调用完成函数、不改计时值来制造结束。

## 控件引用和targets

| targets | 控件引用 |
|---|---|
| tools.calculator/roster/timer/magnifier/spotlight | tool_menu_buttons[原handler.__name__] |
| calculator.two/plus/three/equals | calc_buttons['2'/'+'/'3'/'='] |
| roster.draw/reset | btn_roster_draw / btn_roster_reset |
| timer.up/down/start_pause/reset | btn_timer_up / btn_timer_down / btn_timer_start / btn_timer_reset |
| magnifier.zoom_in/size/refresh | btn_mag_zoom_in / mag_size_slider / btn_mag_refresh |
| 聚光灯移动 | 复用canvas.ink |

工具菜单用原handler.__name__字典，不覆盖现有 tool_buttons() 方法。

## 私有图像和边界

练习 refresh_magnifier 应执行 canvas.magnifier_pixmap = render_private_magnifier_frame(self)，然后沿用 canvas.update 与业务记录；正常模式沿用 grab_screen。合成函数只用 QPixmap/QPainter 和 canvas.draw_content，绘制本练习白板笔迹、形状、文字、图像，不使用 QWidget.grab 或桌面捕获。练习窗口尚未activate时不得调用普通抓屏分支。

课程不使用系统剪贴板、真实名单、系统音量、注册表或更新功能。声明完成、文件持久化、计时自然结束都由真实状态验证；不发虚假成功。

## 验证记录（2026-10-14，直接验收完成）

范围仅 tests/test_teaching_toolbox_interface.py 的5项直接测试。使用正式 main 装饰器、Qt信号、APPLICATION_EVENTS / APPLICATION_TARGETS 和八语言文案，没有测试内重新装饰、i18n注入或私有放大镜替代实现。保留 grab_screen 失败钩子；sys.excepthook 完整输出Qt槽异常，并在teardown使测试失败。

```powershell
$env:QT_QPA_PLATFORM='offscreen'
$env:MYSCREENDRAW_NO_KEYBOARD='1'
$env:PYNPUT_BACKEND='dummy'
$env:PYTHONIOENCODING='utf-8'
python -B -m pytest -q -p no:cacheprovider --tb=short tests/test_teaching_toolbox_interface.py
```

最终整组结果：**5 passed in 5.84s，退出码0，无失败或teardown error**。

| 用例 | 最终实际结果 |
|---|---|
| test_resource_graphs_private_fixtures_and_all_eight_languages | 通过：课程图、65个八语言键、9份合成白板 |
| test_real_calculator_keys_and_private_nonrepeating_roster | 通过：真实按键2+3=5、无bus计算、6人虚构名单连续两次不重复抽选、重置与私有roster.json保存 |
| test_real_up_timer_and_natural_down_completion | 通过：UP开始/暂停/重置、DOWN取消旧上下文及重新启动后自然结束 |
| test_private_board_magnifier_and_real_spotlight_motion | 通过：私有放大镜倍率/尺寸/刷新，聚光灯开启/移动/退出，课程正常结束 |
| test_real_layout_four_schemes_opacity_and_private_audio | 通过：横竖、折叠、明暗、四配色、透明度、单屏分支及私有计时音量 |

计时测试等待两个真实timer_clock tick；DOWN通过真实时钟自然到零、停钟和alerting，不直接调用完成函数或改计时值制造结束。

主线程已将 name_projection_shown、roster_draw 两处业务记录字段改为selected_name，并为 handle_spotlight_click 添加外层 toolbox_action('spotlight.changed')。此前名单Qt参数冲突和聚光灯退出事件被抑制的问题均在本次完整5项运行中验证通过。本线程没有修改共享main或更改课程事件、targets、fixture IDs及引擎门禁。

状态：C12/C13独立资源、适配模块、直接测试与接线文档已收尾，本组无剩余失败。此次修复后只复跑上述5项一次，命令已结束；未运行C11、46章串联或导出一致性审查。

验证边界：多屏实际切换、真实宿主暂停/恢复、父现场恢复及全课程同一QProcess串联未在这5项中验证，由主线程负责。本次没有冻结矩阵、全仓回归、构建、打包或发布。
