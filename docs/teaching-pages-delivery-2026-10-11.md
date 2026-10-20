# C05 白板与页面教学交付与验收（2026-10-11）

基线：`cb31c9d`；分支：`codex/software-teaching-system`；关联GitHub Issue #9。范围取自已批准T7，五章为board、add_switch、rename_delete、copy_position、reorder。完整39步中文正文及精确成功条件见`docs/teaching-pages-copy.md`。

## 正式资源

本轮新增五章39步、84个文案键与672条八语言完整字符串，五份纯合成合法项目。章节步数为7/6/7/12/7，含17个信息确认和22个真实操作步骤。全部接入i18n、正式catalog和C05 JSON；课程数据不能提供可执行回调。中文与七语言删除按钮名称对齐软件实际的删除/Delete/Supprimer/Eliminar/Löschen/Удалить/삭제/削除；同时修正C04日文正文里引用的确认按钮为实际“次の手順”。

| 章节 | 步数 | 素材与实际操作 |
| --- | ---: | --- |
| board | 7 | 初始批注/WHITE，进入白板、切黑板、切回白板、退出白板；说明页面/批注边界，不抓桌面 |
| add_switch | 6 | 初始一页，真实新增第二页、上页、下页；换页后恢复批注笔的配置仅作准确说明 |
| rename_delete | 7 | 初始A/B两页，开缩略图、实际重命名、明确取消删除并保留原内容，再确认删除A而保留B；说明页面删除/历史边界 |
| copy_position | 12 | 初始A/B/C当前B，依次设置before/after/first/last并真实复制当时的当前页；新ID、内容、插入位置及其他页面均核对 |
| reorder | 7 | 开缩略图、真实选C、识别页码与身份、拖C到A前；最终C/A/B且当前仍C、页码1/3 |

素材完全由项目合成，标记synthetic_teaching，不读取用户项目、名单、截图或桌面。初始化只允许当前活跃私有练习路径，采用确定笔型/板色与after复制配置，关闭旧面板和私有预设。普通父进程的文档、历史与配置不参与材料初始化。

## 可信事件与目标

事件白名单由31增为38：board.style_changed、page.renamed、page.deleted、page.copied、page.copy_placement_changed、page.reordered、thumbnails.opened。目标由45增为52：真实板色图标、右下角页码、缩略图列表、页面重命名/删除/复制、真实设置下拉框。

所有操作在入口捕获上下文，完整业务/UI尾部及native scope清理后才交付；程序准备、同值、空操作、取消、异常或旧epoch不伪造适用步骤成功。

- 缩略图选页抑制内部提前事件，在视图刷新完成后交付page.changed；刷新失败不能先计成功。
- 重命名只报告实际有效变化及稳定page_id，事件不携带用户输入的页面名。
- 删除取消是本章明确要求的cancelled步骤；retained校核页面ID、当前身份、序列化内容和顺序。确认删除只在指定原页实际消失时成功；普通取消不能领取成功删除步骤。
- 页面复制校核唯一新ID、来源内容一致、正确插入索引、所有原页面及顺序保留，新副本确为当前页。局部创建后丢掉其他页面不计成功。
- 复制位置必须是真实有效变化，设置写入标记、文件和对应值确实一致才报告success；初始化persist=False、同值、非法值和写入失败不计完成。
- 排序检查最后真实顺序和当前页身份，回调尾部又恢复原序不计完成。PageListWidget在startDrag开始时借可信应用scope捕获上下文，drop嵌套操作复用入口上下文，拖动结束及清理后才flush；旧拖动不能给新epoch签发结果。初始化/退出拖动异常都清理源标记和实际拥有的QDrag。
- 目标reveal只展示真实面板，设置和缩略图互相让位；设置下拉框通过现有QScrollArea目标机制滚入可见区域，定向流程核对其矩形在viewport内。

## 复现与修复证据

首轮有效业务契约为14 failed、12 passed，8.88秒；失败对应待实现事件/目标及缩略图先交付后刷新的真实时序问题。接通后三文件组合49 passed，9.91秒；拖动初始化残留先1 failed再修复。复制回调丢页、排序回调反转、拖动收尾实际对象未删除三个反例先3 failed，再加严。随后三文件组合53 passed，10.66秒。删除取消内容被改变的反例先1 failed，再校核完整序列化内容；隐私用例确认重命名事件没有输入名。

本轮一次编辑脚本误匹配DrawingCanvas的同名方法，造成ControlPanel定义缺失，组合出现49 setup errors。已从已验证基线恢复main.py，按AST定位ControlPanel方法重新应用；所有顶层类保留、DrawingCanvas AST与基线一致，main.py/page_list.py原有UTF-8 BOM保留。这是未提交编辑错误，不计为用户软件缺陷或通过证据。

五课程串联首轮1 failed、61 passed，105.85秒；子进程在C05.add_switch的add步骤超时。直接复现证明批注章结束后，私有换章按旧窗口可见性隐藏新白板需要的page_rail。修复仅在可信私有换章恢复后，按新章节模型重建白板视图；普通原工作仍走原有精确恢复。直接用例先1 failed，随后五课程与换章/中心组合31 passed，22.34秒。

补查换章期间暂停/隐藏，两个直接用例先2 failed、7 deselected，1.81秒：恢复教学后旧页面条仍隐藏。页面条的目标reveal现在按当前模型重新显示控件。旧缩略图还可能被窗口快照重新显示，额外用例先1 failed、9 deselected，5.47秒；可信私有换章恢复后关闭旧菜单、设置与缩略图，页码目标reveal确保首次点击真正打开。普通原工作恢复路径不改变；暂停/隐藏时不主动显示场景，真正恢复目标后才展示所需控件。

## 最终验证

同一真实QProcess已连续完成C01–C05共19章137步，父侧接收各章完成记录，PID与会话token保持一致；父工作仅挂起一次，最终退出仅恢复一次，私有根清理且父文档签名不变。操作通过实际业务/控件完成，不直接移动引擎步骤。拖动测试拥有实际列表与模型，模拟QDrag.exec的drop和native选择结果，不注入系统输入。

首轮83文件冻结组合为2041 passed、1 deselected、3346 subtests passed，335.56秒，162份源码/测试/课程资源SHA-256一致；该轮早于上述暂停/隐藏及旧面板复核，不作为最后源码验收。最后边界/生命周期/完整流程组合为**99 passed，24.97秒**。最终**83文件（54教学+29相关旧功能）**为**2044 passed、1 deselected、3346 subtests passed，339.53秒**，pytest退出0；**162份源码/测试/课程资源SHA-256前后一致**。Python为3.11.9，PyQt/Qt均为6.11.0；明确排除test_overlay_is_independent_border_only_input_transparent_and_nonactivating这个合成QWidget.grab用例。各轮测试范围重叠，不相加为覆盖率。

10个修改/新增Python文件通过AST，main.py/page_list.py原有UTF-8 BOM保留，所有顶层类和DrawingCanvas AST与基线一致，`git diff --check`通过。正式catalog核对为五课19章137步、20份合成项目/私有恢复材料。验收收据：`C:\Users\WIN10\AppData\Local\Temp\myscreendraw-c05-accepted-fjbhk2xb\receipt.json`；同目录保存完整pytest输出。临时证据不提交，不含用户数据或凭据。

全程Qt offscreen、MYSCREENDRAW_NO_KEYBOARD=1、PYNPUT_BACKEND=dummy，使用测试拥有的临时路径与子进程；没有实屏、桌面捕获、原生鼠标/键盘/触控注入或可见原生应用测试。一个文案代理仅写pages_copy.py和中文文案文件，主线程审查、对齐实际标签并独立验证；代理已关闭，未再派新代理。

正式资源现为五课19章137步。整体工程估算约88%，可复核课程范围为5/13门、19/46章；C06–C13剩27章及全目录联合验收仍需继续。本地检查点不push、不合并main、不build/安装/发布、不改6.1.0标签或资产；离屏结果不能证明物理硬件与真实冻结EXE。
