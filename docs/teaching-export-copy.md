# C10 导出文案、素材和成功条件

本文件对应 C10 的三个章节：

- formats：用三页合成白板分别导出 PNG、PDF、SVG、EPS。
- progress_cancel：用 24 页合成白板在真实进度框中取消 PNG，并核对已写文件。
- result：用三页合成白板先观察两页成功、一页失败，再重试完成全部导出。

正式文案在 [export_copy.py](../teaching/export_copy.py)，准备器在 [export_fixtures.py](../teaching/export_fixtures.py)。本写集固定为 38 个键、304 条字符串：课程标题 1 个、章节标题 3 个、17 步各自的 title/body 共 34 个键；每个值按 zh、en、fr、es、de、ru、ko、ja 顺序提供静态八语言 tuple。复用已有 teaching_group_files，不新增组标题。

## 真实控件、函数和事件

| 用途 | 真实控件或函数 | 有效结果 |
| --- | --- | --- |
| PNG | 文件栏 **PNG 图片**，btn_export_png → do_export("PNG") | 三页时逐页写成三个私有 PNG 文件 |
| PDF | 文件栏 **PDF 文档**，btn_export_pdf → do_export("PDF") | 三页写成一个私有多页 PDF |
| SVG | 文件栏 **SVG 矢量图**，btn_export_svg → do_export("SVG") | 三页逐页写成三个私有 SVG 文件 |
| EPS | 文件栏 **EPS 矢量图**，btn_export_eps → do_export("EPS") | 三页逐页写成三个私有 EPS 文件 |
| 进度取消 | QProgressDialog 的 **取消**，真实 tr("cancel") | export.finished 的 outcome=cancelled 且 cancelled=True |
| 信息确认 | 现有 **下一步**，teaching_next | 只确认当前信息步或章节，不替代导出结果 |

导出主路径是 do_export → _export_pages_with_result → _export_pages_operation。export.finished 的成功条件为 format 与当前格式相同、pages=total、failed_pages=0、complete=True、cancelled=False。取消条件为 outcome=cancelled、cancelled=True；取消时已提交的 PNG 保留，未到达提交阶段的页不算成功。

partial 练习的第一次 PNG 结果必须是 outcome=failed、format=PNG、pages=2、total=3、failed_pages=1、complete=True、cancelled=False，并由主线程加入 partial=True 说明；complete 只表示所有源页都已尝试，不表示全部成功。重试的第二次结果必须回到完整成功条件。

导出结果由应用拥有的 QMessageBox 展示失败页和已写文件信息；文案只要求真实导出结果，不把关闭信息框另列为教学步骤，也不要求额外打开目录或详细信息按钮。

## 私有素材和准备器

| 文件 | 用途 | 内容和事实 |
| --- | --- | --- |
| assets/tutorials/fixtures/export.c10.formats.msd | formats 初始项目 | schema 1 的 myscreendraw-project，WHITE 白板，3 页，只有自产线段和矩形，synthetic_teaching=true |
| assets/tutorials/fixtures/export.c10.progress_cancel.msd | progress_cancel 初始项目 | WHITE 白板，24 页，只有自产线段和矩形，synthetic_teaching=true |
| assets/tutorials/fixtures/export.c10.result.msd | result 初始项目 | WHITE 白板，3 页，只有自产线段和矩形，synthetic_teaching=true |

prepare_export_fixture(panel, fixture, paths) 只接受 export.c10.formats、export.c10.progress_cancel 和 export.c10.result。它先验证当前是活跃私有会话且 context.paths == paths，然后在事件抑制区结束文字编辑和活动笔、取消激光/取点/选择、关闭符号菜单和设置面板，切回可绘图的普通 PEN，宽度 4，smart_shapes_enabled=False，并确保白板模式开启。它设置 panel._teaching_export_fixture=fixture，不创建故障目录，也不写真实配置。

主线程导出入口按当前步骤安全创建或清理私有输出。输出使用固定私有前缀 c10_formats、c10_progress_cancel、c10_result。第一次 result 导出前，主线程在本会话 paths.export_dir 内将第二页目标 c10_result_p2.png 预置成空目录，第一、三页实际写入成功；retry_png 的新导出入口只移除该私有示例空目录，然后执行完整三页导出。准备器不创建、清理或注入这一障碍，也不注入渲染假异常；正常使用须先查明失败原因并修正后再重试。

## formats：中文 7 步

| step_id | 中文标题和正文 | 目标、成功条件和不完成反例 |
| --- | --- | --- |
| intro | **开始格式导出练习**。本章用三页合成白板，分别导出 PNG、PDF、SVG 和 EPS 到当前私有练习目录。读完点击“下一步”，随后逐项确认全部页成功导出。 | 信息步只在点击 teaching_next 后确认。初始化、只看文件栏或跳过格式操作不算。 |
| png | **逐页导出 PNG**。点击文件栏的“PNG 图片”，将本练习三页逐页导出到私有目录。只有三页都实际写成 PNG 文件才完成，取消、失败或仅点击按钮都不算。 | btn_export_png → do_export("PNG")。要求 export.finished 为 success，format=PNG、pages=3、total=3、failed_pages=0、complete=True、cancelled=False；少于三页、取消或只出现按钮点击均失败。 |
| pdf | **导出一个多页 PDF**。点击文件栏的“PDF 文档”，将三页白板导出为一个三页 PDF 文件。只有全部页成功且文件完成提交才算完成，部分文件、失败或取消都不算。 | btn_export_pdf → do_export("PDF")。要求 success 且 pages=total=3、failed_pages=0、complete=True、cancelled=False；结果应是一个三页 PDF，部分提交或校验失败不完成。 |
| svg | **逐页导出 SVG**。点击文件栏的“SVG 矢量图”，将三页合成白板分别导出为 SVG 文件。必须三页全部成功；此处练习线段和几何，不表示任意位图都会自动变成矢量图形。 | btn_export_svg → do_export("SVG")。要求 success 且三页全部成功；文案只说明本素材的线段和几何可导出，不宣称任意位图自动矢量化。 |
| eps | **逐页导出 EPS**。点击文件栏的“EPS 矢量图”，将三页合成白板分别导出为 EPS 文件。必须看到三页全部成功的结果；格式名称不保证任意图片都会转换成可编辑矢量内容。 | btn_export_eps → do_export("EPS")。要求 success 且 pages=total=3、failed_pages=0、complete=True、cancelled=False；失败、取消或文件数不足不完成。 |
| formats_info | **核对各格式的文件组织**。本练习的 PNG、SVG、EPS 每页各一个文件，PDF 则把三页放在一个文件中。核对结果中的成功页数后点击“下一步”，格式名称不等于每页都已导出。 | 信息步阅读后点击 teaching_next。它不替代四个导出结果，也不要求额外打开输出目录。 |
| done | **完成格式导出练习**。确认四种格式都已导出本练习全部三页，再点击“下一步”确认本章。需要换章或返回原工作时，在教学中心选择章节或使用“退出教学”。 | 四个导出均满足完整成功后才能点击 teaching_next 确认本章；done 不补齐被跳过的操作、不自动换章或退出。 |

## progress_cancel：中文 4 步

| step_id | 中文标题和正文 | 目标、成功条件和不完成反例 |
| --- | --- | --- |
| intro | **开始导出取消练习**。本章使用二十四页合成白板，练习在真实导出进度框中取消 PNG 导出。读完点击“下一步”，随后以实际取消终态确认操作，而不是只看见进度框。 | 信息步点击 teaching_next。初始化 24 页、出现进度框或只读说明不计确认。 |
| cancel_png | **在进度框取消 PNG 导出**。点击“PNG 图片”开始导出，再在真实进度框中点击“取消”。必须得到实际取消结果；若全部页已太快导完，本次不算取消，可再次开始并在进度期间重试。 | btn_export_png → QProgressDialog 取消按钮。要求 export.finished outcome=cancelled、format=PNG、total=24、cancelled=True；全 24 页成功、只见进度、未取消或只有失败终态不完成。人机速度未经实屏验证，过快完成时允许重试。 |
| cancel_info | **核对取消后的保留文件**。取消会保留已经写好的 PNG 文件，尚未导出的页不算成功。核对取消结果和实际已导出页数后点击“下一步”，不要把本次取消当成全部完成。 | 信息步阅读真实取消结果后点击 teaching_next。无需删除已写文件，不承诺取消时至少已经落盘某一页。 |
| done | **完成取消练习**。确认已经得到实际取消结果，并理解已写文件保留和未导出页未完成的区别。点击“下一步”只确认本章，不会自动补导出、切换章节或退出教学。 | cancel_png 实际完成后点击 teaching_next 确认本章；done 不替代取消，不自动补写未导出的页。 |

## result：中文 6 步

| step_id | 中文标题和正文 | 目标、成功条件和不完成反例 |
| --- | --- | --- |
| intro | **开始部分失败与重试练习**。本章用三页合成白板和私有示例路径冲突，先观察部分失败，再完成一次重试。读完点击“下一步”，两次导出都以真实文件结果判定。 | 信息步点击 teaching_next。准备器初始化或将要创建冲突均不计教学完成。 |
| partial_png | **观察两页成功、一页失败**。点击“PNG 图片”，本次导出会遇到私有示例路径冲突，实际写出两页并使一页失败。查看结果中的失败页和已成功文件，不能把此结果当成三页全部成功。 | 第一次 btn_export_png → do_export("PNG") 要求 outcome=failed、format=PNG、pages=2、total=3、failed_pages=1、complete=True、cancelled=False，且主线程标记 partial=True；成功页文件保留，失败页为第2页。 |
| partial_info | **区分部分失败与完整成功**。本次结果的失败列表对应第二页，已成功写好的第一页和第三页文件会保留。读完点击“下一步”，已尝试全部页不等于全部页导出成功。 | 信息步核对失败列表和成功文件后点击 teaching_next。complete=True 不能解释为 success=True，不要求额外打开目录或详细按钮。 |
| retry_png | **重试并导出全部三页**。再次点击“PNG 图片”重试，本练习会在这次导出前移除私有示例障碍。只有三页都实际成功写出才完成，这种练习内清理不表示正常使用会自动修复所有错误。 | 第二次 btn_export_png → do_export("PNG") 要求 export.finished success，format=PNG、pages=total=3、failed_pages=0、complete=True、cancelled=False；前一次部分结果、取消或再次部分失败不完成。 |
| success_info | **核对重试后的完整结果**。本次重试应实际导出三页且没有失败页，正常使用遇错时应先检查原因并修正再重试。读完点击“下一步”，不要从本练习的示例清理推断任何错误都会自动修好。 | 信息步在 retry_png 成功后点击 teaching_next；不触发新重试，不承诺自动修复权限、磁盘、格式或其它真实错误。 |
| done | **完成结果检查练习**。确认已经观察真实部分失败，并通过重试完成三页全部导出。点击“下一步”只确认本章，随后可在教学中心换章或使用“退出教学”返回原工作。 | partial_png、partial_info、retry_png、success_info 均已成立后点击 teaching_next 确认本章；done 不自动换章、不自动退出。 |

## 静态核对范围

本代理只核对了导出按钮、导出结果模型、进度取消路径、私有准备器边界和合成项目结构；没有运行应用或测试，没有截图、桌面捕获、系统输入、真实数据或凭据访问。主线程负责课程接入、故障路径注入、QProcess 和最终回归。

## 续接记录（2026-10-11）

C09 的四类文案问题已由主线程修正，本轮不复查或修改 C09。C10 当前唯一代理的写集限于 teaching/export_copy.py、teaching/export_fixtures.py、本文档，以及 assets/tutorials/fixtures/export.c10.formats.msd、export.c10.progress_cancel.msd、export.c10.result.msd；课程顺序固定为 7／4／6 步，共 17 步，文案为 38 键／304 条八语言字符串。

本轮仅执行 Python AST、文案结构、项目纯数据规范化与文档一致性检查；未执行准备器，未运行应用或测试，未访问真实数据或凭据，未创建代理或提交。主线程继续负责导出事件、固定私有输出前缀、实际路径冲突与重试清理、目标屏障和回归；24 页素材的真实人机取消时机未经实屏验证，若先完整导完则不计取消并允许重试。后续按约 200k 上下文保存续接记录；生产资源开始测试后，任何修正先报告并等待主线程收束处理。
