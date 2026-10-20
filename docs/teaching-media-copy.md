# C09 图片与 PDF 文案、素材和成功条件

本文件对应 C09 的两个章节：

- image：导入一张私有合成 PNG，切换到框选并提交一次图片尺寸变化。
- pdf_pages：导入私有两页 PDF，确认生成两个独立白板页，在第二页批注，再返回第一张导入页。

正式文案在 teaching/media_copy.py，准备器在 teaching/media_fixtures.py。本写集固定为 29 个键、232 条字符串：课程标题 1 个、章节标题 2 个、13 步各自的 title/body 共 26 个键；每个值按 zh、en、fr、es、de、ru、ko、ja 顺序提供静态八语言 tuple。复用已有 teaching_group_files，本模块不新增组标题。

## 真实控件和结果

| 用途 | 真实控件或函数 | 有效结果 |
| --- | --- | --- |
| 导入图片或 PDF | 文件栏“导入图片/PDF”，btn_import_media → import_media_from_file_panel → import_media | 选择私有素材并完成一个 media.imported 成功事务 |
| 选择工具 | 工具栏“框选”，btn_select → handle_select_click | 工具切到 SELECT，仅点击画布不算 |
| 缩放图片 | 选中图片后拖动右下 scale 手柄并松开 | selection.transformed 的 action=scale，图片对象尺寸发生变化，且只选中本次导入图片 |
| 翻页 | 页面栏“下页”/“上页”，rail_next / rail_prev | 真实 page.changed 到指定独立白板页 |
| 批注 | 普通笔 PEN，pen_width=4，在当前 PDF 页画一笔后抬笔 | 新笔画实际提交；按下未成线或停在错误页面不算 |
| 信息确认 | 现有“下一步”，多语言标签来自 teaching_next | 只确认当前信息步或本章，不替代业务结果 |

导入结果由主线程适配层校验：图片必须新增恰好一个非空图片对象，并记录 kind=image、images=1、source_sample=True；PDF 必须新增恰好两张页面，每张有一个图像对象、页面 ID 独立、原有页面顺序不变，并记录 kind=pdf、pages_added=2、separate_pages=True、source_sample=True。PDF 导入成功后当前页是第一张新导入页。

## 私有素材和准备器

| 文件 | 用途 | 内容和事实 |
| --- | --- | --- |
| assets/tutorials/fixtures/media.c09.image.msd | media.c09.image 初始项目 | schema 1 的 myscreendraw-project，单页 WHITE 白板，内容可空，metadata.synthetic_teaching=true |
| assets/tutorials/fixtures/media.c09.pdf_pages.msd | media.c09.pdf_pages 初始项目 | 同样是单页 WHITE 白板，确保 PDF 导入前只有原始一页 |
| assets/tutorials/fixtures/media-c09-sample.png | 图片导入源 | 主线程修正后的 320×200 合成色块 PNG；不含用户数据 |
| assets/tutorials/fixtures/media-c09-sample.pdf | PDF 导入源 | 两页合法合成 PDF，每页包含不同的简单几何色块，供 QtPdf 逐页渲染 |

prepare_media_fixture(panel, loader, fixture, paths) 只接受 media.c09.image 和 media.c09.pdf_pages。它先验证当前是活跃私有练习且 context.paths == paths，然后在事件抑制区结束文字编辑和活动笔、清除激光/取点/选择、关闭符号菜单和设置面板，切回可绘图 PEN、宽度 4，并关闭智能识别。它把对应 PNG 或 PDF 复制到当前私有根的 data/media-fixtures，将实际路径写入 panel._teaching_media_source_path；不会预插入媒体，也不会读取真实数据。

宿主在每章开始时清空 panel._teaching_media_original_id，避免前一章的图片身份残留影响本章的 same_imported_image 判定。

## image：中文 6 步

| step_id | 中文标题和正文 | 目标、成功条件和不完成反例 |
| --- | --- | --- |
| intro | **开始导入图片**。本章在当前私有练习中导入一张合成 PNG，再用框选工具改变它的显示尺寸。只有真实图片对象和一次已提交的尺寸变化才算完成，打开面板或只读说明不算。 | 信息步点击“下一步”才确认。只打开文件栏、只读本步或没有后续图片变换都不计完成。 |
| import_image | **导入一张图片**。点击文件栏的“导入图片/PDF”，在当前私有练习目录中选择 media-c09-sample.png。只有图片实际插入画布并产生一个图片对象后才完成；取消选择、只打开文件栏或导入失败都不算。 | 目标是 btn_import_media。有效结果是一次成功的 media.imported，新增恰好 1 个图片对象，且 source_sample=True；取消文件选择器、坏文件或新增数不是 1 都失败。 |
| select_mode | **切换到框选**。点击工具栏的“框选”，确认工具状态切换为 SELECT。只点击图片、保持普通笔，或打开选择面板但没有完成工具切换，都不算完成。 | 目标是 btn_select / handle_select_click，结果是 tool.changed(tool=SELECT)。点击图片不等于选择工具切换。 |
| resize_image | **拖动手柄改变图片尺寸**。在画布点击图片使它成为当前选中对象，再拖动右下缩放手柄，让包围框尺寸实际改变并松开提交。只点击、拖动空白处、移动图片，或尺寸没有变化，都不算。 | 目标是当前导入图片的右下 scale 手柄。有效结果是 selection.transformed、action=scale、image_only=True、same_imported_image=True，且尺寸确实变化；选择别的对象、只移动、原地拖动或没有释放不算。 |
| size_info | **了解图片尺寸限制**。位图导入会受有界解码约束：最长边最多 2560 像素，单张解码最多 8000000 像素；缩放只改变显示尺寸，不恢复原始细节。读完点击现有“下一步”确认。 | 信息步只要求阅读并点击“下一步”。不能把显示缩放说成恢复原始分辨率，也不要求等待或重新导入。 |
| done | **完成图片练习**。确认图片对象已经保留，并确认尺寸变化已提交。点击“下一步”只确认本章；教学不会自动切换章节，跳过导入或缩放不计完成。 | 只有导入成功和有效缩放都已发生后，点击“下一步”才能确认本章；它不自动换章，也不等同于退出教学。 |

## pdf_pages：中文 7 步

| step_id | 中文标题和正文 | 目标、成功条件和不完成反例 |
| --- | --- | --- |
| intro | **开始导入 PDF 页面**。本章在原有白板之后导入一份两页合成 PDF，并在新增页面之间翻页和批注。成功依据是真实生成两张独立白板页及一次新笔提交，不是只打开 PDF 选择器。 | 信息步点击“下一步”确认。打开选择器、只读说明或没有真实新增页面都不计完成。 |
| import_pdf | **导入两页 PDF**。点击文件栏的“导入图片/PDF”，选择当前私有练习目录中的 media-c09-sample.pdf。成功时原来的一页之后会新增两张独立白板页，并停在第一张导入页；取消、失败或页数未增加都不算。 | 目标是 btn_import_media。有效结果是 media.imported(kind=pdf)，pages_added=2、separate_pages=True、source_sample=True，当前页为第一张导入页；整批取消或任一页失败都应保持原文档不变。 |
| next_page | **翻到下一张导入页**。在第一张导入页上点击页面栏的“下页”，确认当前页切换到第二张导入页。只点击画布或停留在原页不算，必须发生真实页面切换。 | 目标是 rail_next，结果是从第一张导入页到第二张导入页的 page.changed。不改变当前页不算。 |
| annotate | **在第二页用普通笔批注**。保持普通笔，在当前第二张导入页上画出一笔新的有效笔画，再抬笔提交。只按下未形成笔画、使用选择工具、或在别的页面作画都不算本步结果。 | 目标是当前页画布与 PEN。有效结果是第二张导入页上的新 ink.committed；按下未释放、空笔画、使用 SELECT 或画在第一张/原始页不算。 |
| previous_page | **返回第一张导入页**。完成第二页批注后点击页面栏的“上页”，确认回到第一张导入页。点击无效区域、没有发生页面切换，或回到原始白板页都不算完成。 | 目标是 rail_prev，结果是第二张导入页切回第一张导入页的 page.changed。这里不要求删除批注，也不应回到导入前的原始页。 |
| limits_info | **了解 PDF 导入边界**。整批 PDF 在全部页面成功渲染前不会提交；取消或失败会保留原文档。当前单次最多取前 50 页，PDF 总驻留像素上限 32000000，单页还受最长边 2560 与单图 8000000 像素约束；读完点击“下一步”。 | 信息步点击“下一步”确认。不得承诺每页必定导入，也不得把取消后的部分页面当成已提交；当前边界来自 MAX_PDF_PAGES、MAX_PDF_TOTAL_PIXELS、MAX_IMPORT_PIXELS 和 MAX_IMAGE_PIXELS。 |
| done | **完成 PDF 页面练习**。确认两张导入页仍是独立白板页，第二张上的批注已保留，并确认已经回到第一张导入页。点击“下一步”只确认本章，不自动切换或退出教学。 | 只有两张独立导入页、第二页批注和回到第一张导入页都成立后，点击“下一步”才能确认本章。导入失败、批注未提交或停留第二页都不算。 |

## 失败边界和冻结记录

- 图片是位图。导入器在解码阶段执行有界缩放，成功缩放只改变画布中的显示尺寸，不恢复被限制掉的原始细节。
- PDF 逐页渲染后整批提交；取消进度或任一页渲染失败时，原文档和原页数保持不变。
- PDF 导入页是独立白板页，不把两页内容合并到当前页；每页有自己的页面 ID 和一个图片对象。
- 本文档在 PNG 修正后按 320×200 合成色块素材记录事实。主线程已重生成该 PNG；本代理不覆盖冻结素材，也不运行应用测试。
- 主线程在上一轮测试收束后已修正文案：PDF done 中文指第二张页面的批注；日文导入按钮与 i18n 的「画像/PDF を読み込む」一致；西文信息/确认步骤使用「Paso siguiente」；日文 annotate 使用「この手順」。页面事件名称与实际 page.changed 对齐。

## 静态核对范围

本代理只核对了 C09 文案键结构、准备器路径边界、主程序媒体导入函数和合成素材描述；没有运行应用、没有截图或桌面捕获、没有读取真实数据或凭据。主线程负责目录接入、目标映射、课程测试和最终资源修正。
