# C07 文字与公式正式教学文案

日期：2026-10-11（Asia/Shanghai）。本稿落实已批准的 [2026-10-07 软件教学系统实施计划](superpowers/plans/2026-10-07-software-teaching-system.md) C07/T7 范围。资源为 [teaching/text_copy.py](../teaching/text_copy.py)。本写集只编辑该资源与本文；业务事件、真实目标、课程/目录 JSON、私有合成素材、测试、打包和最终运行验收由主线程负责。本文给出成功条件契约，不把静态文案交付等同于业务已验收。

## 资源结构与严格步序

TEXT_COPY 只有 132 个键：课程标题 1＋章标题 3＋64 步各自 title/body 128；每个值为 zh、en、fr、es、de、ru、ko、ja 顺序的 8 字符串 literal tuple，共 1056 条完整纯文本。资源只有静态字典赋值，无导入、运行时模板、插值占位符或 HTML。

课程键为 teaching_c07_title，章节键为 teaching_c07_edit_title、teaching_c07_format_title、teaching_c07_formula_title；步骤键为 teaching_c07_章节_步骤_title/body（这里只解释命名，实际文件已全部展开）。

三章严格为 edit（12）、format（12）、formula（40），总计 64 步；10 个信息步骤、54 个操作步骤。信息仅包括各章 intro/done 与 keyboard_ime_info、font_info、navigate_info、limits_info，全部由用户点击现有 teaching_next 确认。操作只由相应真实有效业务结果完成，按钮展示、初始化、自动目标展开、同值、取消、旧事件、未收束输入或点击教学“下一步”不替代结果。

各章 done 只确认本章，此前所有必做结果和信息确认必须实际完成。不会自动换章或退出；用户另在教学中心换章，或点击 teaching_exit 回原工作。跳过不计完成。

### 固定步骤清单

- edit（12）：intro → choose_text → create_box → type_text → insert_middle → backspace → newline → finish → reedit → finish_again → keyboard_ime_info → done
- format（12）：intro → choose_select → select_box → size → color → move → scale → rotate → copy → delete_copy → font_info → done
- formula（40）：intro → choose_text → open_symbols → greek → operator → relation → calculus → open_formula → structure → frac → frac_num → frac_den → frac_edit → root_after_frac → sup → sup_base → sup_exp → root_after_sup → sub → sub_base → sub_sub → root_after_sub → sqrt → sqrt_frac → sqrt_num → sqrt_den → root_after_sqrt → sum → sum_lo → sum_hi → sum_arg → root_after_sum → integral → integral_lo → integral_hi → integral_arg → navigate_info → finish → limits_info → done

## 示例与成功条件的边界

AB/C/ACB、分数1/2、上标x/2、下标a/1、根号内分数1/2、求和i=1/n/i、积分0/1/x等，只帮助说明，不作为指定答案。文字输入核对至少两个已提交字符且非空；中间插入要在原内容内部，退格/换行要实际改变内容，重新编辑要回同一原ID并在末尾新增至少一字符。公式填槽按本次新建结构的实际路径和真实新增字符判定，不能以旧的非空内容代替。

固定的控件/符号/结构要求仍须准确：S 的四个面板符号是 α、±、∈、∫；结构类型是 frac/sup/sub/sqrt/sum/int；format.size 的实际值是粗细6、字号36。S 初始文本“Symbols: ”和 F 初始主行“F = ”用于合成素材身份定位，不是要求用户重打的答案或硬编码UUID。

**五个 root_after 已按主线程补充方向修订：** 每次必须先在画布点中 F = 主行，再向正在使用的输入框发送真实 End，到当前根槽末尾，随后真实新增至少一个连接字符。连接文字如 + 或带空格的加号仅是示例，不强制精确匹配。必须核对点击→根槽→End→根槽末尾新增的顺序和本次内容变更，不能只看已有根槽状态或旧分隔文字。框外点击可能仍留在原槽，不能教成自动返根槽；在子槽里按 End 后输入也不完成。

## 真实控件、函数和输入范围

事实先核对根 AGENTS.md、docs/agents/domain.md、计划 C07/T7，再参考现有教学文案布局。代码依据为 [main.py](../main.py)、[formula.py](../formula.py)、[i18n.py](../i18n.py)，并静态阅读 [test_text_workflow.py](../tests/test_text_workflow.py)、[test_text_box.py](../tests/test_text_box.py)、[test_formula.py](../tests/test_formula.py)。未运行这些测试或应用。

- 文本工具是 panel.btn_text / icon_buttons['text']，实际标签由 text 读取；handle_text_click 调用 set_tool('TEXT')。框选为 panel.btn_select / icon_buttons['select']，标签为 select，handle_select_click 切到 SELECT。正文不额外要求先开工具菜单。
- 创建文本框走 canvas 的按下/移动/释放→finish_text_box→create_text_item→begin_text_edit。两个轴位移均小于 TEXT_DRAG_MIN_PX=12 时是点击，不建框；满足拖动后最终宽高至少为 TEXT_MIN_W=60、TEXT_MIN_H=36。TEXT 模式单击空白不新建；点击已有框进入编辑，点击正在编辑框内移动光标，不另建框。创建成功等实际释放/输入收尾，不能仅凭预览或 press 判定。
- 原文本框按当前 text_font_size、pen_width 初始化；纯文本在 panel.text_input（_TextInputEdit）提交后写到模型。set_caret_at 支持画布点中间；text_backspace 删除光标之前内容，text_newline 插入真实换行。自动折行不等于换行字符。
- text_panel 内“退格”“换行”“完成”“键盘”按钮由 _build_text_panel 创建，没有独立存储在 panel.btn_text_done 等字段；目标按当前面板、实际 i18n 标签与绑定回调定位，不能虚构控件属性。“完成”走 _text_done→end_text_edit；非空原框保留，空/纯空白框默认丢弃。普通 Escape 可结束编辑，但本稿 finish 步骤指定实际“完成”按钮，不把替代按键算作本按钮操作。
- 选中面板滑条为 select_width_slider，范围1到40，经 on_selection_width_changed→apply_selection_width 把选中文字 width 设为滑条值、size=max(8,width×6)，再 fit_text_box；6对应36。不是独立字号输入或字体下拉框，也不能仅看 canvas.pen_width 或标签变化。短文本不一定长高，框高按实际重排，不能强制增长。
- “改色”按钮在 select_panel 内按 change_color 标签定位，走 open_selection_color→QColorDialog→apply_selection_color。对话框须接受且颜色不同；取消/同色/仅预览不完成。主线程应授权拥有的模态对话框，不能只放行原改色按钮而挡住其确认。
- 移动从选中框内部拖动，走 move_selection，没有独立移动柄。selection_handles 只返回一个右下 scale 柄和一个上方 rotate 柄；对应 scale_selection/rotate_selection，释放后核对实际倍率/角度与原ID。整体缩放不等于独立拖边调框宽；文字字体由 text_font 请求 Microsoft YaHei，没有字体选择UI。
- panel.btn_dup 的中文实际标签是“复”，duplicate_selection 新建不同ID副本并自动选中副本；panel.btn_del 是“删”，delete_selection 立即删除当前选中对象，本稿只删除刚复制的 T2。复制方向依实际算法，不要求一律在右侧，不额外要求重新选原框。

### 符号目标自动展开与结构目标

主线程的目标解析会自动展开 greek/operator/relation/calculus 对应组，并仅允许指定 α/±/∈/∫ 按钮。四步正文直接点击已展开的符号，**不要求再点击被屏障禁止的分组按钮**；自动展开仅准备目标，不计完成。成功必须来自该组普通符号按钮 _symbol_pressed(entry) 的真实插入，不能用键盘输入相同字符或展示列表代替。

structure 步骤单独要求用户点击 _symbol_group_buttons['structure']，中文实际标签是“公式结构”（“结构”是描述简称）；_toggle_symbol_group 真实打开对应网格后完成。后续各结构按钮解析可自动确保 structure 组展开，不要求用户重复开组。按钮由 symbol_grid_layout 动态创建，切组会 deleteLater 旧按钮，目标不能缓存失效指针。

| 步骤 | 结构按钮标签 | 真实节点类型 | 必填槽/默认首槽 |
| --- | --- | --- | --- |
| frac | a/b | frac | num、den；首槽num |
| sup | x² | sup | base、exp；首槽base |
| sub | x₁ | sub | base、sub；首槽base |
| sqrt | √‾ | sqrt | arg；本章再在arg内插frac并填num/den |
| sum | ∑ | sum | lo、hi、arg；首槽lo |
| integral | ∫ | int | lo、hi、arg；首槽lo |

_symbol_pressed 对普通字符串调用 text_insert，对 !kind 结构 entry 调用 text_insert_structure。微积分组的 ∫ 只是字符，结构组的 !int/∫ 才产生带上下限和主体的节点；类似字形或普通 x²、a/b 字符串不等于结构。首次插结构把原纯文本搬入公式树并保留主行；每次插入当前有效槽，自动进入新节点首槽。

结构节点本身没有独立UUID；主线程记录本次实际根索引、结构节点和槽路径/身份关系，不把固定位置作为用户答案。formula.SLOTS/get_slot 支持实际路径，set_caret_at→formula.hit_slot 选择最深命中的槽，面板同步当前槽的投影；结构在投影里占一个位置，不能把占位显示当正文输入。

### 屏障与键盘/输入法

- 使用中的整个 text_panel 与 canvas＋text_input 组合由主线程按步骤放行。先声明各步真正用到的根窗口/控件，不能裸 target_only 禁掉同一步需要的画布点槽、输入光标或确认对话框；正文不额外索取无关工具点击。四个自动展开符号仍按主线程要求只点指定按钮。
- 文字符号、填槽和光标操作的输入目标是拥有的 panel.text_input，不是不会接收常规文字焦点的透明画布。纯文本由原生编辑控件同步；公式由 keyPressEvent/inputMethodEvent 通过 canvas.text_insert 修改当前槽，再投影回来。程序性同步、预编辑串和真实用户提交必须区分。
- IME preedit 不等于 commit；组字期间不能用自动重开面板/抢焦点取消组字。需要结束组字再操作按钮。输入后的框内容/槽内容真实变更才是成功，不能以键盘窗口出现或输入框镜像文字独立判定。
- 方向键、Home、End在当前槽的投影内移动，不自动跨分子分母/上下限；本稿的 root_after 必须实际 End。没有专用下一槽/父槽按钮，不承诺 Tab 跨槽。
- 公式拒绝换行（text_newline 返回失败，Return/Enter被接受但不插换行）。公式不是 LaTeX 解析器，也不求值。剪贴板/组合快捷键不作为必做输入路径，未承诺其复杂行为。
- open_text_input 会请求系统键盘，“键盘”按钮也仅发请求；本机触摸键盘、输入法、End输入和实际字体可用性未由本文做环境验证。不要求更改系统配置；缺少能力可重试或跳过，跳过不计完成。

## 实际八语言标签

下面按 i18n 原值列出，width_value 展示值按本章6展开，不留下资源占位符；结构按钮字形是语言无关标签。

| i18n 键 | zh | en | fr | es | de | ru | ko | ja |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| teaching_next | 下一步 | Next step | Étape suivante | Paso siguiente | Nächster Schritt | Следующий шаг | 다음 단계 | 次の手順 |
| teaching_exit | 退出教学 | Exit tutorial | Quitter le tutoriel | Salir del tutorial | Tutorial beenden | Выйти из обучения | 튜토리얼 종료 | チュートリアルを終了 |
| text | 文本框 | Text | Texte | Texto | Text | Текст | 텍스트 | テキスト |
| select | 框选 | Select | Sélection | Seleccionar | Auswählen | Выбор | 선택 | 選択 |
| change_color | 改色 | Colour | Couleur | Color | Farbe | Цвет | 색상 | 色変更 |
| duplicate | 复 | Copy | Copie | Copia | Kopie | Копия | 복사 | 複製 |
| delete | 删 | Del | Suppr | Borrar | Löschen | Удал. | 삭제 | 削除 |
| text_done | 完成 | Done | Terminé | Listo | Fertig | Готово | 완료 | 完了 |
| text_backspace | 退格 | Backspace | Retour | Retroceso | Rücktaste | Забой | 백스페이스 | 後退 |
| text_newline | 换行 | New line | Nouvelle ligne | Nueva línea | Neue Zeile | Новая строка | 줄 바꿈 | 改行 |
| text_keyboard | 键盘 | Keyboard | Clavier | Teclado | Tastatur | Клавиатура | 키보드 | キーボード |
| text_editor_title | 文字 / 公式 | Text / formula | Texte / formule | Texto / fórmula | Text / Formel | Текст / формула | 텍스트 / 수식 | テキスト / 数式 |
| width_value | 粗细: 6 | Width: 6 | Épaisseur : 6 | Grosor: 6 | Stärke: 6 | Толщина: 6 | 굵기: 6 | 太さ: 6 |
| sym_group_greek | 希腊字母 | Greek | Grec | Griego | Griechisch | Греческие | 그리스 문자 | ギリシャ文字 |
| sym_group_operator | 运算符 | Operators | Opérateurs | Operadores | Operatoren | Операторы | 연산자 | 演算子 |
| sym_group_relation | 集合与逻辑 | Sets & logic | Ensembles et logique | Conjuntos y lógica | Mengen & Logik | Множества и логика | 집합과 논리 | 集合と論理 |
| sym_group_calculus | 微积分 | Calculus | Analyse | Cálculo | Analysis | Анализ | 미적분 | 微積分 |
| sym_group_structure | 公式结构 | Structures | Structures | Estructuras | Strukturen | Структуры | 구조 | 構造 |

## 主线程提供的三章私有合成素材

| 章节 | 初始素材/状态 | 必须记录的身份和结果 |
| --- | --- | --- |
| edit | 空白白板，PEN，text_font_size=24、pen_width=4；无文本/编辑/公式，历史空 | create_box 后记录实际原 T.id，后续输入、两次finish、reedit只追踪同一T。AB/C不是答案；创建、文字提交和退出结果分别验收。 |
| format | 唯一非空纯文本框 T1，size=24、width=4、scale=1、rotation=0，有有效box；PEN，未选/未编辑，历史空 | 各动作前后记录T1；copy记录新T2实际ID及自动选中，delete_copy只能移除T2并保留T1。颜色、位置、倍率、角度不指定样例值，size固定6/36。 |
| formula | 独立S.text='Symbols: '，pos=(160,100)、size=24；F.text='F = '，pos=(120,320)、size=18，采用现有无固定box的内容自适应模型，不设置固定宽540的box。两者初始无formula，PEN，无编辑/选中，历史空；坐标为私有练习画布坐标。 | 记录并保留实际S/F ID及F主行前缀；四个固定符号写S，公式只写同一F。逐次记录新结构和实际槽路径，五次根槽导航/End/末尾新增连接文字各有本步结果。学员字母数字及连接文字示例不强制精确匹配。 |

公式素材调整依据：主线程完整公式联测已复现固定F宽540使六种结构主行后半越出命中框，因此F使用现有无box、按内容自适应的模型，字号18、位置(120,320)，保留原F =前缀及同一F.id；S仍位于(160,100)、字号24。此调整只属于formula素材，edit/format的初始字号24不变，不要求学员输入精确样例字符串。完整运行验收结果由主线程报告，本写集不据此宣称自行运行测试。

T/T1/T2/S/F只是本文的身份记号，不是固定UUID、用户需输入的文字或未填资源模板。布局坐标由主线程按私有练习画布准备，不来自桌面捕获或用户项目；三章均独立重建，原工作、历史与设置不变，不承诺跨章自动恢复。

## 64步中文全文、真实目标与成功条件

以下逐步正文与 TEXT_COPY 的 zh 项完全一致，步骤按批准顺序列出。所有目标只描述现有控件/函数与主线程放行责任，不新增产品按钮。

### edit｜创建、编辑与结束编辑

#### edit.intro｜开始文字编辑练习

**类型：** 信息

**资源键前缀：** teaching_c07_edit_intro（_title / _body）

**教学正文：**

本章从空白私有白板和普通笔开始，初始字号24、粗细4。你将拖出文本框、输入和修改文字，再结束并重新编辑同一框。字母仅作示例，素材、历史和设置不改原工作。点击“下一步”开始。

**真实目标/函数：**

教学控制器 teaching_next

**精确成功条件与不完成反例：**

用户在当前信息步骤阅读后点击现有 teaching_next 明确确认；展示文案、初始化、业务事件、自动推进和跳过不代替确认。 初始 whiteboard_mode=True、draw_state=PEN、text_font_size=24、pen_width=4、无文本对象/编辑目标/公式，历史为空。

#### edit.choose_text｜选择文本框工具

**类型：** 操作

**资源键前缀：** teaching_c07_edit_choose_text（_title / _body）

**教学正文：**

点击系统展示的“文本框”工具，真实切换到文本框模式。先选好工具，再按本章要求在私有画布中操作。

**真实目标/函数：**

panel.btn_text / icon_buttons['text']；handle_text_click→set_tool

**精确成功条件与不完成反例：**

用户实际点击文本框入口，draw_state 从 PEN→TEXT，绘图可用且文本工具选中；保持本章初始对象。仅预置 TEXT、显示工具或点击教学“下一步”不完成。

#### edit.create_box｜拖出一个文本框

**类型：** 操作

**资源键前缀：** teaching_c07_edit_create_box（_title / _body）

**教学正文：**

在空白处按下，拖出有宽高的文本框，再抬起。真实建立新框并进入“文字 / 公式”输入面板后完成；只点一下、小幅抖动或未抬起的预览不算。

**真实目标/函数：**

canvas；mousePress/Move/ReleaseEvent→finish_text_box→create_text_item→begin_text_edit

**精确成功条件与不完成反例：**

用户在本次空白区域真实拖放并释放，超过 TEXT_DRAG_MIN_PX=12 的点击容差，normalized rect 至少一个轴达到点击容差阈值，最终 box 按 TEXT_MIN_W=60/TEXT_MIN_H=36 钳制并具有有效宽高；新增唯一文本对象 T，记录实际新 ID/box/box_min_h，editing_text_id=T.id，输入面板针对 T 可用且历史/输入收尾完成。点击、小幅抖动、未释放、旧框或仅展示面板不完成。

#### edit.type_text｜输入至少两个字符

**类型：** 操作

**资源键前缀：** teaching_c07_edit_type_text（_title / _body）

**教学正文：**

在输入框中输入并提交至少两个字符，例如 AB；可以使用自己的文字。必须写入刚创建的同一文本框，未提交的输入法组字不算。

**真实目标/函数：**

panel.text_input；_TextInputEdit._on_text_changed/inputMethodEvent

**精确成功条件与不完成反例：**

当前编辑对象必须是 create_box 的 T；本步由真实用户输入提交，使 T.text 实际变化且含至少 2 个已提交字符、strip 后非空。记录实际文本和光标，不要求 AB 或任何精确示例。未提交 preedit、纯空白、错对象、初始化旧内容或仅控件文字变化不完成。

#### edit.insert_middle｜在文字中间插入字符

**类型：** 操作

**资源键前缀：** teaching_c07_edit_insert_middle（_title / _body）

**教学正文：**

在画布上点击两个已有字符之间，把插入点放到文字中间，再在输入框中输入至少一个字符，例如 C。示例 AB 可变成 ACB；在末尾追加不算本步完成。

**真实目标/函数：**

canvas＋panel.text_input；set_editing_slot_at→set_caret_at→文本输入

**精确成功条件与不完成反例：**

同一 T；用户实际点击已有字符之间得到严格内部光标 0<offset<len(before_text)，随后在该 offset 提交至少一个字符；after_text=原前缀＋新增字符＋原后缀，前后原内容均保留，光标随插入前进。AB/C/ACB 只是示例。末尾追加、首位插入、替换原内容、错框或只有光标移动不完成。

#### edit.backspace｜实际退格删除

**类型：** 操作

**资源键前缀：** teaching_c07_edit_backspace（_title / _body）

**教学正文：**

点击文字面板的“退格”，实际删除当前插入点前的字符。必须让同一文本框的已提交内容减少；只点按钮而没有删除不算完成。

**真实目标/函数：**

text_panel 内 text_backspace 按钮；_text_backspace→canvas.text_backspace

**精确成功条件与不完成反例：**

用户真实点击 text_backspace，T.text 从本步前内容实际减少，删除位置位于当前 caret 之前，保留同一 ID 且输入框和画布同步。插入文字示例 C 可被删掉，但不要求删除指定字符或恢复精确 AB。起点空退格、空框、只按按钮、自动同步或删除别框不完成。

#### edit.newline｜插入真实换行

**类型：** 操作

**资源键前缀：** teaching_c07_edit_newline（_title / _body）

**教学正文：**

点击文字面板的“换行”，在当前插入点插入一个真实换行。必须改变同一框的文字内容；框变窄造成的自动折行不算本步完成。

**真实目标/函数：**

text_panel 内 text_newline；_text_newline→canvas.text_newline

**精确成功条件与不完成反例：**

真实用户点击 text_newline，当前仍编辑同一纯文本 T；在当前 caret 位置插入真实换行字符，T.text 与 before_text 不同且对应前后内容保留，画布与输入框同步。视觉折行、公式中被拒绝的换行、按钮展示或旧换行不完成。

#### edit.finish｜结束这次编辑

**类型：** 操作

**资源键前缀：** teaching_c07_edit_finish（_title / _body）

**教学正文：**

点击文字面板的“完成”，结束当前编辑。输入面板关闭，已输入的非空内容和同一文本框身份保留后才完成；只隐藏面板或让空框消失不算。

**真实目标/函数：**

text_panel 内 text_done；_text_done→end_text_edit

**精确成功条件与不完成反例：**

用户实际点击当前 text_panel 的 text_done，执行 _text_done→end_text_edit；此前 T.text.strip() 非空，结束后 editing_text_id/editing_slot 清空、text_panel 关闭、光标停止，T 原 ID/已提交内容保留且本次输入与私有页面保存收尾完成。只隐藏窗口、此前已不在编辑、空框丢弃、错 ID 或旧完成事件不完成。

#### edit.reedit｜重新编辑同一文本框

**类型：** 操作

**资源键前缀：** teaching_c07_edit_reedit（_title / _body）

**教学正文：**

在画布上点击刚才保留的原文本框，重新打开它的输入面板，再在末尾追加至少一个字符，例如 C。必须编辑同一原框并保留已有内容，不要在空白处新建另一个框。

**真实目标/函数：**

canvas＋panel.text_input；text_at→begin_text_edit→文本输入

**精确成功条件与不完成反例：**

接续真实 finish 后 editing_text_id=None；用户点击本章原 T，实际重新进入 editing_text_id=T.id，随后在原文本末尾提交至少一个字符，after_text.startswith(before_text) 且实际增长。文本对象数不增，原 ID 保持；不要求 C 或任何示例字符串。新框、复制框、只打开面板、未提交 IME 或内部替换不完成。

#### edit.finish_again｜再次结束编辑并保留原框

**类型：** 操作

**资源键前缀：** teaching_c07_edit_finish_again（_title / _body）

**教学正文：**

点击文字面板的“完成”，结束当前编辑。输入面板关闭，已输入的非空内容和同一文本框身份保留后才完成；只隐藏面板或让空框消失不算。

**真实目标/函数：**

text_panel 内 text_done；_text_done→end_text_edit

**精确成功条件与不完成反例：**

必须接续本章 reedit 的真实重新编辑和末尾追加；用户实际点击当前 text_panel 的 text_done，执行 _text_done→end_text_edit；此前 T.text.strip() 非空，结束后 editing_text_id/editing_slot 清空、text_panel 关闭、光标停止，T 原 ID/已提交内容保留且本次输入与私有页面保存收尾完成。只隐藏窗口、此前已不在编辑、空框丢弃、错 ID 或旧完成事件不完成。 不能复用第一次 finish 的事件，保留 reedit 后的实际新内容，不指定样例答案。

#### edit.keyboard_ime_info｜了解键盘与输入法限制

**类型：** 信息

**资源键前缀：** teaching_c07_edit_keyboard_ime_info（_title / _body）

**教学正文：**

字母数字在输入框内由实体或系统键盘输入。输入法组字需提交后才写入正文；组字时不要切换控件或反复打开面板。“键盘”按钮仅请求系统键盘，不保证本机能弹出软键盘。此步只说明，不要求更改系统输入法。读完点击“下一步”。

**真实目标/函数：**

教学控制器 teaching_next

**精确成功条件与不完成反例：**

用户在当前信息步骤阅读后点击现有 teaching_next 明确确认；展示文案、初始化、业务事件、自动推进和跳过不代替确认。 本步只说明实际 _TextInputEdit 的 preedit/commit 与焦点、_text_show_keyboard/_request_keyboard 的请求语义；不要求启动软键盘、系统输入法切换、物理延迟测量或硬件验证。

#### edit.done｜确认本章完成

**类型：** 信息

**资源键前缀：** teaching_c07_edit_done（_title / _body）

**教学正文：**

完成本章必做步骤后，点击“下一步”确认本章完成；不会自动换章或退出。你可在教学中心选择其他章节，或点击“退出教学”回到原工作。跳过不计完成。

**真实目标/函数：**

教学控制器 teaching_next

**精确成功条件与不完成反例：**

此前本章全部必做业务结果与信息确认均已实际完成，用户再点击本步 teaching_next，只确认本章，不自动换章或退出；用户另在中心换章或用 teaching_exit 返回原工作，跳过不计完成。

### format｜文字大小与文本框操作

#### format.intro｜开始文字格式与文本框练习

**类型：** 信息

**资源键前缀：** teaching_c07_format_intro（_title / _body）

**教学正文：**

私有白板上只有一个非空合成文本框，初始字号24、粗细4、缩放1、旋转0。你将选择它，改变大小与颜色，移动、缩放和旋转，再复制并只删除副本。内容、历史和设置不改原工作。点击“下一步”开始。

**真实目标/函数：**

教学控制器 teaching_next

**精确成功条件与不完成反例：**

用户在当前信息步骤阅读后点击现有 teaching_next 明确确认；展示文案、初始化、业务事件、自动推进和跳过不代替确认。 主线程准备唯一非空纯文本 T1，size=24、width=4、scale=1.0、rotation=0.0，box 有效、无 formula，draw_state=PEN、无编辑/选中，历史为空。

#### format.choose_select｜切换到框选工具

**类型：** 操作

**资源键前缀：** teaching_c07_format_choose_select（_title / _body）

**教学正文：**

点击系统展示的“框选”，真实切换到选择模式。下一步只选中本章的合成文本框。

**真实目标/函数：**

panel.btn_select / icon_buttons['select']；handle_select_click→set_tool

**精确成功条件与不完成反例：**

用户点击真实框选入口，draw_state 从 PEN→SELECT，编辑状态保持关闭，唯一 T1 内容不变。预置 SELECT、显示入口或无真实切换不完成。

#### format.select_box｜只选中样例文本框

**类型：** 操作

**资源键前缀：** teaching_c07_format_select_box（_title / _body）

**教学正文：**

在画布上单击唯一的样例文本框并抬起，确认只选中它，选中面板显示其操作。先不要移动，也不要进入文字编辑。

**真实目标/函数：**

canvas；SELECT 模式 hit_object_at / mousePress/ReleaseEvent

**精确成功条件与不完成反例：**

真实用户点选释放后 selected_ids 从空变为 {T1.id}，仍 draw_state=SELECT、editing_text_id=None，T1 身份/内容/几何保持且选中面板可用。空选、多选、仅按下、别对象、预选或进入 TEXT 编辑不完成。

#### format.size｜把粗细调到6，字号变为36

**类型：** 操作

**资源键前缀：** teaching_c07_format_size（_title / _body）

**教学正文：**

保持原框单独选中，把选中面板的粗细滑条实际调到6。该文本框的粗细应变为6、字号变为36；这是现有的大小联动，不是字体或独立字号下拉框。

**真实目标/函数：**

panel.select_width_slider / select_width_label；on_selection_width_changed→apply_selection_width→fit_text_box

**精确成功条件与不完成反例：**

保持唯一 selected_ids={T1.id}；用户真实把选中滑条 4→6，T1.width=6、T1.size=36，重新 fit_text_box/折行，非空文字及原 ID 保持。必须模型字段变化，不以标签或 canvas.pen_width 单独变化算完成；同值、未选 T1、改主笔滑条或其它值不完成。不得要求短文字框高一定增加。

#### format.color｜确认一个不同的文字颜色

**类型：** 操作

**资源键前缀：** teaching_c07_format_color（_title / _body）

**教学正文：**

保持原框选中，点击选中面板的“改色”，在颜色对话框中选一个不同颜色并确认。原文本框颜色必须实际改变；取消对话框或确认原色不算完成。

**真实目标/函数：**

select_panel 中 change_color 按钮→open_selection_color；拥有的 QColorDialog 确认

**精确成功条件与不完成反例：**

T1 仍单选；用户通过真实改色按钮打开 QColorDialog，选择不同颜色并 Accepted，apply_selection_color 后 T1.color 与动作前不同、ID/内容保留，对话框收尾完成。不指定颜色答案。取消、同色、仅画笔颜色/预览变色、错对象或仅弹窗不完成；主线程需放行该拥有的模态对话框。

#### format.move｜移动原文本框

**类型：** 操作

**资源键前缀：** teaching_c07_format_move（_title / _body）

**教学正文：**

按住已选中文本框的内部，拖到另一处再抬起。原框的位置必须实际改变，文字和身份保留；只选中、只按下或拖回原位不算完成。

**真实目标/函数：**

canvas；SELECT 框内部 drag_action=move→move_selection→mouseReleaseEvent

**精确成功条件与不完成反例：**

selected_ids={T1.id}、draw_state=SELECT；用户从选中框内部真实拖动并释放，T1.pos 与 before_pos 不同，ID/文字/box/样式保留，本次历史与输入收束。无位移、仅按下、拖回原位、错对象或未提交不完成。移动区域是框内部，不虚构专用移动柄。

#### format.scale｜用右下角柄缩放文本框

**类型：** 操作

**资源键前缀：** teaching_c07_format_scale（_title / _body）

**教学正文：**

拖动选中框右下角的缩放柄，再抬起，让原文本框实际整体缩放。文字和原ID保留；这是整体缩放，不是单独拖边改变文本框宽度。

**真实目标/函数：**

canvas；selection_handles()['scale']→hit_selection_handle→scale_selection→释放

**精确成功条件与不完成反例：**

用户命中 selection_handles 的真实右下 scale 柄，实际拖动并释放；T1.scale 相对动作前发生有效变化，显示边界相应变化，原 ID/文字保留，历史提交。普通平移、仅命中柄、无倍率变化、未释放或单独修改 box 宽字段不完成；不得将其描述为独立调宽。

#### format.rotate｜用上方柄旋转文本框

**类型：** 操作

**资源键前缀：** teaching_c07_format_rotate（_title / _body）

**教学正文：**

拖动选中框上方的旋转柄，再抬起，让原框实际转过一个角度。保持同一框和内容；只移动框、只打开面板或没有角度变化不算完成。

**真实目标/函数：**

canvas；selection_handles()['rotate']→rotate_selection→释放

**精确成功条件与不完成反例：**

用户命中选中范围上方的真实 rotate 柄，实际拖动释放；T1.rotation 归一化角度与动作前不同，原 ID/文字保留并完成历史提交。不要求指定角度；平移、零角度/等价整圈、未释放、其它对象或仅显示柄不完成。

#### format.copy｜复制原框并保留原件

**类型：** 操作

**资源键前缀：** teaching_c07_format_copy（_title / _body）

**教学正文：**

保持原文本框单独选中，点击“复”。必须新增一个内容相同、ID不同的副本，原件保留；副本会自动成为当前选中对象。

**真实目标/函数：**

panel.btn_dup（duplicate 实际标签）→duplicate_selection

**精确成功条件与不完成反例：**

本步开始只选 T1；用户点击真实 duplicate 控件，新增唯一文本副本 T2，T2.id≠T1.id、非空内容/box/样式与来源一致（位置按实际复制算法偏移），T1 的 ID/内容保留，selected_ids={T2.id}。记录实际新 ID，不指定固定 UUID 或复制方向；旧对象、同 ID、多副本/错来源或仅外观相同不完成。

#### format.delete_copy｜只删除新副本

**类型：** 操作

**资源键前缀：** teaching_c07_format_delete_copy（_title / _body）

**教学正文：**

刚创建的副本已自动选中。点击“删”，只删除这个副本，保留原文本框和原内容；不需要先再选一次原框。

**真实目标/函数：**

panel.btn_del（delete 实际标签）→delete_selection

**精确成功条件与不完成反例：**

必须是 copy 新建并自动选中的 T2；用户点击真实 delete，T2.id 从文本对象集合实际移除，原 T1.id/内容/样式保留，未删其它对象。空删除、删原件、删旧副本、仅隐藏、按钮点击无结果或复制后自动删掉不完成。

#### format.font_info｜了解字体与缩放边界

**类型：** 信息

**资源键前缀：** teaching_c07_format_font_info（_title / _body）

**教学正文：**

画布文字请求 Microsoft YaHei 字体，当前没有选择字体的控件。选中面板的粗细会联动文字大小；右下角柄缩放整个对象，不是独立调文本框宽度。实际字形取决于本机字体。读完点击“下一步”。

**真实目标/函数：**

教学控制器 teaching_next

**精确成功条件与不完成反例：**

用户在当前信息步骤阅读后点击现有 teaching_next 明确确认；展示文案、初始化、业务事件、自动推进和跳过不代替确认。 本步按 text_font、apply_selection_width 与 scale_selection 说明；不要求换字体、设置 bold、独立拖边调宽、枚举系统字体或任何额外格式操作。

#### format.done｜确认本章完成

**类型：** 信息

**资源键前缀：** teaching_c07_format_done（_title / _body）

**教学正文：**

完成本章必做步骤后，点击“下一步”确认本章完成；不会自动换章或退出。你可在教学中心选择其他章节，或点击“退出教学”回到原工作。跳过不计完成。

**真实目标/函数：**

教学控制器 teaching_next

**精确成功条件与不完成反例：**

此前本章全部必做业务结果与信息确认均已实际完成，用户再点击本步 teaching_next，只确认本章，不自动换章或退出；用户另在中心换章或用 teaching_exit 返回原工作，跳过不计完成。

### formula｜符号、公式结构与槽位导航

#### formula.intro｜开始符号与公式练习

**类型：** 信息

**资源键前缀：** teaching_c07_formula_intro（_title / _body）

**教学正文：**

私有白板有两个独立文本框：S 的文字为 Symbols: ，F 的主行为 F = 。先在 S 插入符号，再在 F 真实插入并填写六种公式结构，练习槽位与主行导航。填入的字母数字仅作示例，素材、历史和设置不改原工作。点击“下一步”。

**真实目标/函数：**

教学控制器 teaching_next

**精确成功条件与不完成反例：**

用户在当前信息步骤阅读后点击现有 teaching_next 明确确认；展示文案、初始化、业务事件、自动推进和跳过不代替确认。 主线程合成两个有实际不同 ID 的非空纯文本框 S.text='Symbols: '、S.pos=(160,100)、S.size=24；F.text='F = '、F.pos=(120,320)、F.size=18且不设置固定box，使用现有内容自适应模型；两者初始 formula 不存在，draw_state=PEN、无编辑/选择、历史为空。F前缀与同一F.id须保留，edit/format初始字号24不变。

#### formula.choose_text｜选择文本框工具

**类型：** 操作

**资源键前缀：** teaching_c07_formula_choose_text（_title / _body）

**教学正文：**

点击系统展示的“文本框”工具，真实切换到文本框模式。先选好工具，再按本章要求在私有画布中操作。

**真实目标/函数：**

panel.btn_text / icon_buttons['text']；handle_text_click→set_tool

**精确成功条件与不完成反例：**

用户实际点击文本框入口，draw_state 从 PEN→TEXT，绘图可用且文本工具选中；保持本章初始对象。仅预置 TEXT、显示工具或点击教学“下一步”不完成。

#### formula.open_symbols｜打开符号样例框 S

**类型：** 操作

**资源键前缀：** teaching_c07_formula_open_symbols（_title / _body）

**教学正文：**

在画布上点击文字以 Symbols: 开头的样例框 S 并抬起，真实打开它的文字输入面板。先在这一个框里练习符号，不要点击空白处新建框。

**真实目标/函数：**

canvas；text_at→begin_text_edit→open_text_input

**精确成功条件与不完成反例：**

TEXT 模式下用户真实点中本章 S 并释放；editing_text_id=S.id、输入面板针对 S 可用，S 原文字及 F 保留、文本数仍 2。只显示面板、点 F、空白新框、程序预置编辑或未抬起不完成。

#### formula.greek｜插入希腊字母α

**类型：** 操作

**资源键前缀：** teaching_c07_formula_greek（_title / _body）

**教学正文：**

系统已展开本步的符号列表，直接点击“α”。它必须实际写入当前 S 框；不用再点击分组，键入相似文字或只展示符号都不算本步。

**真实目标/函数：**

系统自动展开 greek 组后，symbol_grid_layout 中指定 α 按钮；_symbol_pressed('α')→text_insert

**精确成功条件与不完成反例：**

目标解析自动确保 greek 组展开，不能用自动展开计成功；用户真实点击该组指定普通符号 α，当前 editing_text_id=S.id，S.text 在当前 caret 实际增加此固定符号且原内容保留，F 不变，S 仍无 formula。只展示列表、再次点分组、旧符号/键盘输入、相似字符、错对象或结构组的同字形按钮不完成。

#### formula.operator｜插入运算符±

**类型：** 操作

**资源键前缀：** teaching_c07_formula_operator（_title / _body）

**教学正文：**

系统已展开本步的符号列表，直接点击“±”。它必须实际写入当前 S 框；不用再点击分组，键入相似文字或只展示符号都不算本步。

**真实目标/函数：**

系统自动展开 operator 组后，symbol_grid_layout 中指定 ± 按钮；_symbol_pressed('±')→text_insert

**精确成功条件与不完成反例：**

目标解析自动确保 operator 组展开，不能用自动展开计成功；用户真实点击该组指定普通符号 ±，当前 editing_text_id=S.id，S.text 在当前 caret 实际增加此固定符号且原内容保留，F 不变，S 仍无 formula。只展示列表、再次点分组、旧符号/键盘输入、相似字符、错对象或结构组的同字形按钮不完成。

#### formula.relation｜插入集合符号∈

**类型：** 操作

**资源键前缀：** teaching_c07_formula_relation（_title / _body）

**教学正文：**

系统已展开本步的符号列表，直接点击“∈”。它必须实际写入当前 S 框；不用再点击分组，键入相似文字或只展示符号都不算本步。

**真实目标/函数：**

系统自动展开 relation 组后，symbol_grid_layout 中指定 ∈ 按钮；_symbol_pressed('∈')→text_insert

**精确成功条件与不完成反例：**

目标解析自动确保 relation 组展开，不能用自动展开计成功；用户真实点击该组指定普通符号 ∈，当前 editing_text_id=S.id，S.text 在当前 caret 实际增加此固定符号且原内容保留，F 不变，S 仍无 formula。只展示列表、再次点分组、旧符号/键盘输入、相似字符、错对象或结构组的同字形按钮不完成。

#### formula.calculus｜插入积分字符∫

**类型：** 操作

**资源键前缀：** teaching_c07_formula_calculus（_title / _body）

**教学正文：**

系统已展开本步的符号列表，直接点击“∫”。它必须实际写入当前 S 框；不用再点击分组，键入相似文字或只展示符号都不算本步。 这里的∫仅是普通字符，不带上下限或主体槽；后面再练习真正的积分结构。

**真实目标/函数：**

系统自动展开 calculus 组后，symbol_grid_layout 中指定 ∫ 按钮；_symbol_pressed('∫')→text_insert

**精确成功条件与不完成反例：**

目标解析自动确保 calculus 组展开，不能用自动展开计成功；用户真实点击该组指定普通符号 ∫，当前 editing_text_id=S.id，S.text 在当前 caret 实际增加此固定符号且原内容保留，F 不变，S 仍无 formula。只展示列表、再次点分组、旧符号/键盘输入、相似字符、错对象或结构组的同字形按钮不完成。

#### formula.open_formula｜切换到公式样例框 F

**类型：** 操作

**资源键前缀：** teaching_c07_formula_open_formula（_title / _body）

**教学正文：**

在画布上点击主行以 F = 开头的原样例框并抬起，真实从 S 切换到 F 的输入面板。S 的符号应保留；不要新建另一框或把公式结构插进 S。

**真实目标/函数：**

canvas；text_at→end_text_edit→begin_text_edit(F)

**精确成功条件与不完成反例：**

用户真实点中并释放原 F，editing_text_id 从 S.id→F.id，F 初始纯文字主行保留，输入面板同步到 F，S 原 ID/四个已插符号保留且文本数仍 2。初始化跳转、只显示 F、点击 S/空白、创建新框或未抬起不完成。

#### formula.structure｜打开公式结构分组

**类型：** 操作

**资源键前缀：** teaching_c07_formula_structure（_title / _body）

**教学正文：**

点击文字面板中的“公式结构”分组，真实打开结构按钮列表。本步只要求打开这一组；接下来分别插入结构，不要把普通符号当作结构。

**真实目标/函数：**

panel._symbol_group_buttons['structure']→_toggle_symbol_group

**精确成功条件与不完成反例：**

本步必须由用户真实点击 structure 分组，_open_symbol_group 从非 structure→structure，symbol_grid_host 可见且包含六种结构按钮，当前仍 F、未插入结构。初始化或目标解析自动展开、仅展示分组、再次点击导致关闭、其它组或直接插结构不完成。后续结构按钮步骤可由系统确保此组展开。

#### formula.frac｜插入分数结构

**类型：** 操作

**资源键前缀：** teaching_c07_formula_frac（_title / _body）

**教学正文：**

直接点击系统已展开的结构按钮“a/b”，在 F 当前主行插入这种结构。真实建立新结构并自动进入第一个槽后完成；本步先不填写。普通字符或已有结构不能代替这次插入。

**真实目标/函数：**

structure 组 a/b 按钮（!frac）；_symbol_pressed→text_insert_structure('frac')

**精确成功条件与不完成反例：**

用户真实点击 structure 组对应 !frac 按钮，当前编辑原 F 的主行/根槽，实际新增一个 kind=frac 节点并进入 SLOTS['frac'][0]、caret_offset=0；记录本次实际根索引和槽路径，原内容保留。frac 首次插入还须把原 F.text 保留搬入 formula 树。自动确保组展开不计成功；普通 Unicode/键盘字符、已有节点、错槽/错框或只有点击不完成。

#### formula.frac_num｜填写分子

**类型：** 操作

**资源键前缀：** teaching_c07_formula_frac_num（_title / _body）

**教学正文：**

结构的第一个槽已自动选中。在输入框中提交至少一个字符，例如 1。必须实际写入当前槽并保留其它内容；示例只是帮助，不是指定答案。

**真实目标/函数：**

panel.text_input；已自动激活的首槽→_TextInputEdit→text_insert

**精确成功条件与不完成反例：**

frac 本步新建分数 的本次实际 num 槽路径为目标；当前 editing_text_id=F.id。首槽由该次插入自动激活，不要求额外点分组或槽。 本步实际新增至少一个已提交字符，使此槽内容与动作前不同，保留其它槽、结构和 S；不限定示例 1。纯 preedit、自动投影同步、导航无输入、旧非空槽、同值、错节点/槽/框或键盘字符落在主行不完成。

#### formula.frac_den｜填写分母

**类型：** 操作

**资源键前缀：** teaching_c07_formula_frac_den（_title / _body）

**教学正文：**

在画布上点击刚创建结构的分母槽，再在输入框中提交至少一个字符，例如 2。必须实际改变这个槽，保留其它槽；点错槽、只有导航或旧内容不算，示例不强制。

**真实目标/函数：**

canvas 对应真实槽＋panel.text_input；set_editing_slot_at→set_caret_at→formula.hit_slot→text_insert

**精确成功条件与不完成反例：**

同一个 frac 新建分数 的本次实际 den 槽路径为目标；当前 editing_text_id=F.id。用户须在画布真实点中该槽，命中最深有效路径，再通过输入框提交。 本步实际新增至少一个已提交字符，使此槽内容与动作前不同，保留其它槽、结构和 S；不限定示例 2。纯 preedit、自动投影同步、导航无输入、旧非空槽、同值、错节点/槽/框或键盘字符落在主行不完成。

#### formula.frac_edit｜在分母已有内容前插入字符

**类型：** 操作

**资源键前缀：** teaching_c07_formula_frac_edit（_title / _body）

**教学正文：**

保持当前分母槽，在输入框中把光标放到已有字符之前，再提交至少一个字符。例如原分母为2，在它前面输入1会变为12。必须在原字符前插入，末尾追加不算；字符示例不强制。

**真实目标/函数：**

panel.text_input；Qt 光标移动→_on_cursor_moved→set_caret→text_insert

**精确成功条件与不完成反例：**

仍是 frac/frac_den 实际创建并填写的同一分数.den；before_slot 已有至少 1 字符。用户在拥有的 text_input 把光标置于某个已有字符之前，0≤offset<slot_length(before_slot)，再提交至少 1 字符；实际在原字符前插入且原后缀保持、分母内容变化，其它槽和 S/F 身份保留。位置可首位，不要求样例 2/1/12；末尾追加、替换/删掉原字符、错槽、只有移动或旧内容不完成。

#### formula.root_after_frac｜回主行末尾并输入连接文字

**类型：** 操作

**资源键前缀：** teaching_c07_formula_root_after_frac（_title / _body）

**教学正文：**

先在画布上点击公式主行的 F = 处，再在输入框中按 End 到当前主行末尾，输入至少一个连接字符，例如 + 或空格加号空格。必须实际回到根槽并在末尾新增文字，样例不强制；不要把点击框外当作返回主行。

**真实目标/函数：**

canvas 主行 F =＋panel.text_input 的 End 和字符输入；set_caret_at→_TextInputEdit.keyPressEvent/_on_cursor_moved→text_insert

**精确成功条件与不完成反例：**

本步按顺序记录：用户在画布真实点中 F 主行前缀得到根槽（路径 None/() 依源码语义归一），再向当前 F 的 text_input 发送真实 End，使根槽 caret 到实际 slot_length(root)；随后在根槽末尾提交至少 1 字符，根行内容/长度实际增加且原主行、各结构槽和 S 保留。连接文字 + 或空格形式只是示例，不要求精确字符串；需核对至少 1 字符的真实末尾插入与上述点击/End，不能只认已有根槽状态。框外点击仍在旧槽、子槽里按 End/输入、仅导航、已有分隔、预编辑或复用前一 root_after 结果不完成。

#### formula.sup｜插入上标结构

**类型：** 操作

**资源键前缀：** teaching_c07_formula_sup（_title / _body）

**教学正文：**

直接点击系统已展开的结构按钮“x²”，在 F 当前主行插入这种结构。真实建立新结构并自动进入第一个槽后完成；本步先不填写。普通字符或已有结构不能代替这次插入。

**真实目标/函数：**

structure 组 x² 按钮（!sup）；_symbol_pressed→text_insert_structure('sup')

**精确成功条件与不完成反例：**

用户真实点击 structure 组对应 !sup 按钮，当前编辑原 F 的主行/根槽，实际新增一个 kind=sup 节点并进入 SLOTS['sup'][0]、caret_offset=0；记录本次实际根索引和槽路径，原内容保留。frac 首次插入还须把原 F.text 保留搬入 formula 树。自动确保组展开不计成功；普通 Unicode/键盘字符、已有节点、错槽/错框或只有点击不完成。

#### formula.sup_base｜填写底部主体

**类型：** 操作

**资源键前缀：** teaching_c07_formula_sup_base（_title / _body）

**教学正文：**

结构的第一个槽已自动选中。在输入框中提交至少一个字符，例如 x。必须实际写入当前槽并保留其它内容；示例只是帮助，不是指定答案。

**真实目标/函数：**

panel.text_input；已自动激活的首槽→_TextInputEdit→text_insert

**精确成功条件与不完成反例：**

sup 本步新建上标 的本次实际 base 槽路径为目标；当前 editing_text_id=F.id。首槽由该次插入自动激活，不要求额外点分组或槽。 本步实际新增至少一个已提交字符，使此槽内容与动作前不同，保留其它槽、结构和 S；不限定示例 x。纯 preedit、自动投影同步、导航无输入、旧非空槽、同值、错节点/槽/框或键盘字符落在主行不完成。

#### formula.sup_exp｜填写上标指数

**类型：** 操作

**资源键前缀：** teaching_c07_formula_sup_exp（_title / _body）

**教学正文：**

在画布上点击刚创建结构的上标指数槽，再在输入框中提交至少一个字符，例如 2。必须实际改变这个槽，保留其它槽；点错槽、只有导航或旧内容不算，示例不强制。

**真实目标/函数：**

canvas 对应真实槽＋panel.text_input；set_editing_slot_at→set_caret_at→formula.hit_slot→text_insert

**精确成功条件与不完成反例：**

同一个 sup 新建上标 的本次实际 exp 槽路径为目标；当前 editing_text_id=F.id。用户须在画布真实点中该槽，命中最深有效路径，再通过输入框提交。 本步实际新增至少一个已提交字符，使此槽内容与动作前不同，保留其它槽、结构和 S；不限定示例 2。纯 preedit、自动投影同步、导航无输入、旧非空槽、同值、错节点/槽/框或键盘字符落在主行不完成。

#### formula.root_after_sup｜回主行末尾并输入连接文字

**类型：** 操作

**资源键前缀：** teaching_c07_formula_root_after_sup（_title / _body）

**教学正文：**

先在画布上点击公式主行的 F = 处，再在输入框中按 End 到当前主行末尾，输入至少一个连接字符，例如 + 或空格加号空格。必须实际回到根槽并在末尾新增文字，样例不强制；不要把点击框外当作返回主行。

**真实目标/函数：**

canvas 主行 F =＋panel.text_input 的 End 和字符输入；set_caret_at→_TextInputEdit.keyPressEvent/_on_cursor_moved→text_insert

**精确成功条件与不完成反例：**

本步按顺序记录：用户在画布真实点中 F 主行前缀得到根槽（路径 None/() 依源码语义归一），再向当前 F 的 text_input 发送真实 End，使根槽 caret 到实际 slot_length(root)；随后在根槽末尾提交至少 1 字符，根行内容/长度实际增加且原主行、各结构槽和 S 保留。连接文字 + 或空格形式只是示例，不要求精确字符串；需核对至少 1 字符的真实末尾插入与上述点击/End，不能只认已有根槽状态。框外点击仍在旧槽、子槽里按 End/输入、仅导航、已有分隔、预编辑或复用前一 root_after 结果不完成。

#### formula.sub｜插入下标结构

**类型：** 操作

**资源键前缀：** teaching_c07_formula_sub（_title / _body）

**教学正文：**

直接点击系统已展开的结构按钮“x₁”，在 F 当前主行插入这种结构。真实建立新结构并自动进入第一个槽后完成；本步先不填写。普通字符或已有结构不能代替这次插入。

**真实目标/函数：**

structure 组 x₁ 按钮（!sub）；_symbol_pressed→text_insert_structure('sub')

**精确成功条件与不完成反例：**

用户真实点击 structure 组对应 !sub 按钮，当前编辑原 F 的主行/根槽，实际新增一个 kind=sub 节点并进入 SLOTS['sub'][0]、caret_offset=0；记录本次实际根索引和槽路径，原内容保留。frac 首次插入还须把原 F.text 保留搬入 formula 树。自动确保组展开不计成功；普通 Unicode/键盘字符、已有节点、错槽/错框或只有点击不完成。

#### formula.sub_base｜填写底部主体

**类型：** 操作

**资源键前缀：** teaching_c07_formula_sub_base（_title / _body）

**教学正文：**

结构的第一个槽已自动选中。在输入框中提交至少一个字符，例如 a。必须实际写入当前槽并保留其它内容；示例只是帮助，不是指定答案。

**真实目标/函数：**

panel.text_input；已自动激活的首槽→_TextInputEdit→text_insert

**精确成功条件与不完成反例：**

sub 本步新建下标 的本次实际 base 槽路径为目标；当前 editing_text_id=F.id。首槽由该次插入自动激活，不要求额外点分组或槽。 本步实际新增至少一个已提交字符，使此槽内容与动作前不同，保留其它槽、结构和 S；不限定示例 a。纯 preedit、自动投影同步、导航无输入、旧非空槽、同值、错节点/槽/框或键盘字符落在主行不完成。

#### formula.sub_sub｜填写下标

**类型：** 操作

**资源键前缀：** teaching_c07_formula_sub_sub（_title / _body）

**教学正文：**

在画布上点击刚创建结构的下标槽，再在输入框中提交至少一个字符，例如 1。必须实际改变这个槽，保留其它槽；点错槽、只有导航或旧内容不算，示例不强制。

**真实目标/函数：**

canvas 对应真实槽＋panel.text_input；set_editing_slot_at→set_caret_at→formula.hit_slot→text_insert

**精确成功条件与不完成反例：**

同一个 sub 新建下标 的本次实际 sub 槽路径为目标；当前 editing_text_id=F.id。用户须在画布真实点中该槽，命中最深有效路径，再通过输入框提交。 本步实际新增至少一个已提交字符，使此槽内容与动作前不同，保留其它槽、结构和 S；不限定示例 1。纯 preedit、自动投影同步、导航无输入、旧非空槽、同值、错节点/槽/框或键盘字符落在主行不完成。

#### formula.root_after_sub｜回主行末尾并输入连接文字

**类型：** 操作

**资源键前缀：** teaching_c07_formula_root_after_sub（_title / _body）

**教学正文：**

先在画布上点击公式主行的 F = 处，再在输入框中按 End 到当前主行末尾，输入至少一个连接字符，例如 + 或空格加号空格。必须实际回到根槽并在末尾新增文字，样例不强制；不要把点击框外当作返回主行。

**真实目标/函数：**

canvas 主行 F =＋panel.text_input 的 End 和字符输入；set_caret_at→_TextInputEdit.keyPressEvent/_on_cursor_moved→text_insert

**精确成功条件与不完成反例：**

本步按顺序记录：用户在画布真实点中 F 主行前缀得到根槽（路径 None/() 依源码语义归一），再向当前 F 的 text_input 发送真实 End，使根槽 caret 到实际 slot_length(root)；随后在根槽末尾提交至少 1 字符，根行内容/长度实际增加且原主行、各结构槽和 S 保留。连接文字 + 或空格形式只是示例，不要求精确字符串；需核对至少 1 字符的真实末尾插入与上述点击/End，不能只认已有根槽状态。框外点击仍在旧槽、子槽里按 End/输入、仅导航、已有分隔、预编辑或复用前一 root_after 结果不完成。

#### formula.sqrt｜插入平方根结构

**类型：** 操作

**资源键前缀：** teaching_c07_formula_sqrt（_title / _body）

**教学正文：**

直接点击系统已展开的结构按钮“√‾”，在 F 当前主行插入这种结构。真实建立新结构并自动进入第一个槽后完成；本步先不填写。普通字符或已有结构不能代替这次插入。

**真实目标/函数：**

structure 组 √‾ 按钮（!sqrt）；_symbol_pressed→text_insert_structure('sqrt')

**精确成功条件与不完成反例：**

用户真实点击 structure 组对应 !sqrt 按钮，当前编辑原 F 的主行/根槽，实际新增一个 kind=sqrt 节点并进入 SLOTS['sqrt'][0]、caret_offset=0；记录本次实际根索引和槽路径，原内容保留。frac 首次插入还须把原 F.text 保留搬入 formula 树。自动确保组展开不计成功；普通 Unicode/键盘字符、已有节点、错槽/错框或只有点击不完成。

#### formula.sqrt_frac｜在根号内插入分数

**类型：** 操作

**资源键前缀：** teaching_c07_formula_sqrt_frac（_title / _body）

**教学正文：**

当前已进入刚创建的根号内容槽。直接点击系统已展开的“a/b”结构按钮，在根号内部新建分数，并自动进入它的分子。先不填写；插到主行或只输入1/2文字不能代替嵌套结构。

**真实目标/函数：**

structure 组 a/b（!frac）按钮；_symbol_pressed→text_insert_structure，当前 sqrt.arg

**精确成功条件与不完成反例：**

当前必须是 sqrt 步骤实际新建节点的 arg 槽；用户真实点击 !frac，在该 sqrt.arg 内新增 kind=frac 子节点，记录实际嵌套路径，自动进入其 num、caret_offset=0。保留根号、其它根行结构和 S。插到根行/另一个槽、复用已有分数、键盘文字 1/2、普通 /、只点击或错误层级不完成。

#### formula.sqrt_num｜填写分子

**类型：** 操作

**资源键前缀：** teaching_c07_formula_sqrt_num（_title / _body）

**教学正文：**

结构的第一个槽已自动选中。在输入框中提交至少一个字符，例如 1。必须实际写入当前槽并保留其它内容；示例只是帮助，不是指定答案。

**真实目标/函数：**

panel.text_input；已自动激活的首槽→_TextInputEdit→text_insert

**精确成功条件与不完成反例：**

sqrt_frac 本次在 sqrt.arg 新建的嵌套分数 的本次实际 num 槽路径为目标；当前 editing_text_id=F.id。首槽由该次插入自动激活，不要求额外点分组或槽。 本步实际新增至少一个已提交字符，使此槽内容与动作前不同，保留其它槽、结构和 S；不限定示例 1。纯 preedit、自动投影同步、导航无输入、旧非空槽、同值、错节点/槽/框或键盘字符落在主行不完成。

#### formula.sqrt_den｜填写分母

**类型：** 操作

**资源键前缀：** teaching_c07_formula_sqrt_den（_title / _body）

**教学正文：**

在画布上点击刚创建结构的分母槽，再在输入框中提交至少一个字符，例如 2。必须实际改变这个槽，保留其它槽；点错槽、只有导航或旧内容不算，示例不强制。

**真实目标/函数：**

canvas 对应真实槽＋panel.text_input；set_editing_slot_at→set_caret_at→formula.hit_slot→text_insert

**精确成功条件与不完成反例：**

同一个 sqrt_frac 根号内嵌套分数 的本次实际 den 槽路径为目标；当前 editing_text_id=F.id。用户须在画布真实点中该槽，命中最深有效路径，再通过输入框提交。 本步实际新增至少一个已提交字符，使此槽内容与动作前不同，保留其它槽、结构和 S；不限定示例 2。纯 preedit、自动投影同步、导航无输入、旧非空槽、同值、错节点/槽/框或键盘字符落在主行不完成。

#### formula.root_after_sqrt｜回主行末尾并输入连接文字

**类型：** 操作

**资源键前缀：** teaching_c07_formula_root_after_sqrt（_title / _body）

**教学正文：**

先在画布上点击公式主行的 F = 处，再在输入框中按 End 到当前主行末尾，输入至少一个连接字符，例如 + 或空格加号空格。必须实际回到根槽并在末尾新增文字，样例不强制；不要把点击框外当作返回主行。

**真实目标/函数：**

canvas 主行 F =＋panel.text_input 的 End 和字符输入；set_caret_at→_TextInputEdit.keyPressEvent/_on_cursor_moved→text_insert

**精确成功条件与不完成反例：**

本步按顺序记录：用户在画布真实点中 F 主行前缀得到根槽（路径 None/() 依源码语义归一），再向当前 F 的 text_input 发送真实 End，使根槽 caret 到实际 slot_length(root)；随后在根槽末尾提交至少 1 字符，根行内容/长度实际增加且原主行、各结构槽和 S 保留。连接文字 + 或空格形式只是示例，不要求精确字符串；需核对至少 1 字符的真实末尾插入与上述点击/End，不能只认已有根槽状态。框外点击仍在旧槽、子槽里按 End/输入、仅导航、已有分隔、预编辑或复用前一 root_after 结果不完成。

#### formula.sum｜插入带上下限的求和结构

**类型：** 操作

**资源键前缀：** teaching_c07_formula_sum（_title / _body）

**教学正文：**

直接点击系统已展开的结构按钮“∑”，在 F 当前主行插入这种结构。真实建立新结构并自动进入第一个槽后完成；本步先不填写。普通字符或已有结构不能代替这次插入。

**真实目标/函数：**

structure 组 ∑ 按钮（!sum）；_symbol_pressed→text_insert_structure('sum')

**精确成功条件与不完成反例：**

用户真实点击 structure 组对应 !sum 按钮，当前编辑原 F 的主行/根槽，实际新增一个 kind=sum 节点并进入 SLOTS['sum'][0]、caret_offset=0；记录本次实际根索引和槽路径，原内容保留。frac 首次插入还须把原 F.text 保留搬入 formula 树。自动确保组展开不计成功；普通 Unicode/键盘字符、已有节点、错槽/错框或只有点击不完成。

#### formula.sum_lo｜填写下限

**类型：** 操作

**资源键前缀：** teaching_c07_formula_sum_lo（_title / _body）

**教学正文：**

结构的第一个槽已自动选中。在输入框中提交至少一个字符，例如 i=1。必须实际写入当前槽并保留其它内容；示例只是帮助，不是指定答案。

**真实目标/函数：**

panel.text_input；已自动激活的首槽→_TextInputEdit→text_insert

**精确成功条件与不完成反例：**

sum 本步新建求和 的本次实际 lo 槽路径为目标；当前 editing_text_id=F.id。首槽由该次插入自动激活，不要求额外点分组或槽。 本步实际新增至少一个已提交字符，使此槽内容与动作前不同，保留其它槽、结构和 S；不限定示例 i=1。纯 preedit、自动投影同步、导航无输入、旧非空槽、同值、错节点/槽/框或键盘字符落在主行不完成。

#### formula.sum_hi｜填写上限

**类型：** 操作

**资源键前缀：** teaching_c07_formula_sum_hi（_title / _body）

**教学正文：**

在画布上点击刚创建结构的上限槽，再在输入框中提交至少一个字符，例如 n。必须实际改变这个槽，保留其它槽；点错槽、只有导航或旧内容不算，示例不强制。

**真实目标/函数：**

canvas 对应真实槽＋panel.text_input；set_editing_slot_at→set_caret_at→formula.hit_slot→text_insert

**精确成功条件与不完成反例：**

同一个 sum 新建求和 的本次实际 hi 槽路径为目标；当前 editing_text_id=F.id。用户须在画布真实点中该槽，命中最深有效路径，再通过输入框提交。 本步实际新增至少一个已提交字符，使此槽内容与动作前不同，保留其它槽、结构和 S；不限定示例 n。纯 preedit、自动投影同步、导航无输入、旧非空槽、同值、错节点/槽/框或键盘字符落在主行不完成。

#### formula.sum_arg｜填写主体表达式

**类型：** 操作

**资源键前缀：** teaching_c07_formula_sum_arg（_title / _body）

**教学正文：**

在画布上点击刚创建结构的主体表达式槽，再在输入框中提交至少一个字符，例如 i。必须实际改变这个槽，保留其它槽；点错槽、只有导航或旧内容不算，示例不强制。

**真实目标/函数：**

canvas 对应真实槽＋panel.text_input；set_editing_slot_at→set_caret_at→formula.hit_slot→text_insert

**精确成功条件与不完成反例：**

同一个 sum 新建求和 的本次实际 arg 槽路径为目标；当前 editing_text_id=F.id。用户须在画布真实点中该槽，命中最深有效路径，再通过输入框提交。 本步实际新增至少一个已提交字符，使此槽内容与动作前不同，保留其它槽、结构和 S；不限定示例 i。纯 preedit、自动投影同步、导航无输入、旧非空槽、同值、错节点/槽/框或键盘字符落在主行不完成。

#### formula.root_after_sum｜回主行末尾并输入连接文字

**类型：** 操作

**资源键前缀：** teaching_c07_formula_root_after_sum（_title / _body）

**教学正文：**

先在画布上点击公式主行的 F = 处，再在输入框中按 End 到当前主行末尾，输入至少一个连接字符，例如 + 或空格加号空格。必须实际回到根槽并在末尾新增文字，样例不强制；不要把点击框外当作返回主行。

**真实目标/函数：**

canvas 主行 F =＋panel.text_input 的 End 和字符输入；set_caret_at→_TextInputEdit.keyPressEvent/_on_cursor_moved→text_insert

**精确成功条件与不完成反例：**

本步按顺序记录：用户在画布真实点中 F 主行前缀得到根槽（路径 None/() 依源码语义归一），再向当前 F 的 text_input 发送真实 End，使根槽 caret 到实际 slot_length(root)；随后在根槽末尾提交至少 1 字符，根行内容/长度实际增加且原主行、各结构槽和 S 保留。连接文字 + 或空格形式只是示例，不要求精确字符串；需核对至少 1 字符的真实末尾插入与上述点击/End，不能只认已有根槽状态。框外点击仍在旧槽、子槽里按 End/输入、仅导航、已有分隔、预编辑或复用前一 root_after 结果不完成。

#### formula.integral｜插入带上下限的积分结构

**类型：** 操作

**资源键前缀：** teaching_c07_formula_integral（_title / _body）

**教学正文：**

直接点击系统已展开的结构按钮“∫”，在 F 当前主行插入这种结构。真实建立新结构并自动进入第一个槽后完成；本步先不填写。普通字符或已有结构不能代替这次插入。

**真实目标/函数：**

structure 组 ∫ 按钮（!int）；_symbol_pressed→text_insert_structure('int')

**精确成功条件与不完成反例：**

用户真实点击 structure 组对应 !int 按钮，当前编辑原 F 的主行/根槽，实际新增一个 kind=int 节点并进入 SLOTS['int'][0]、caret_offset=0；记录本次实际根索引和槽路径，原内容保留。frac 首次插入还须把原 F.text 保留搬入 formula 树。自动确保组展开不计成功；普通 Unicode/键盘字符、已有节点、错槽/错框或只有点击不完成。

#### formula.integral_lo｜填写下限

**类型：** 操作

**资源键前缀：** teaching_c07_formula_integral_lo（_title / _body）

**教学正文：**

结构的第一个槽已自动选中。在输入框中提交至少一个字符，例如 0。必须实际写入当前槽并保留其它内容；示例只是帮助，不是指定答案。

**真实目标/函数：**

panel.text_input；已自动激活的首槽→_TextInputEdit→text_insert

**精确成功条件与不完成反例：**

integral 本步新建 int 积分 的本次实际 lo 槽路径为目标；当前 editing_text_id=F.id。首槽由该次插入自动激活，不要求额外点分组或槽。 本步实际新增至少一个已提交字符，使此槽内容与动作前不同，保留其它槽、结构和 S；不限定示例 0。纯 preedit、自动投影同步、导航无输入、旧非空槽、同值、错节点/槽/框或键盘字符落在主行不完成。

#### formula.integral_hi｜填写上限

**类型：** 操作

**资源键前缀：** teaching_c07_formula_integral_hi（_title / _body）

**教学正文：**

在画布上点击刚创建结构的上限槽，再在输入框中提交至少一个字符，例如 1。必须实际改变这个槽，保留其它槽；点错槽、只有导航或旧内容不算，示例不强制。

**真实目标/函数：**

canvas 对应真实槽＋panel.text_input；set_editing_slot_at→set_caret_at→formula.hit_slot→text_insert

**精确成功条件与不完成反例：**

同一个 integral 新建 int 积分 的本次实际 hi 槽路径为目标；当前 editing_text_id=F.id。用户须在画布真实点中该槽，命中最深有效路径，再通过输入框提交。 本步实际新增至少一个已提交字符，使此槽内容与动作前不同，保留其它槽、结构和 S；不限定示例 1。纯 preedit、自动投影同步、导航无输入、旧非空槽、同值、错节点/槽/框或键盘字符落在主行不完成。

#### formula.integral_arg｜填写主体表达式

**类型：** 操作

**资源键前缀：** teaching_c07_formula_integral_arg（_title / _body）

**教学正文：**

在画布上点击刚创建结构的主体表达式槽，再在输入框中提交至少一个字符，例如 x。必须实际改变这个槽，保留其它槽；点错槽、只有导航或旧内容不算，示例不强制。

**真实目标/函数：**

canvas 对应真实槽＋panel.text_input；set_editing_slot_at→set_caret_at→formula.hit_slot→text_insert

**精确成功条件与不完成反例：**

同一个 integral 新建 int 积分 的本次实际 arg 槽路径为目标；当前 editing_text_id=F.id。用户须在画布真实点中该槽，命中最深有效路径，再通过输入框提交。 本步实际新增至少一个已提交字符，使此槽内容与动作前不同，保留其它槽、结构和 S；不限定示例 x。纯 preedit、自动投影同步、导航无输入、旧非空槽、同值、错节点/槽/框或键盘字符落在主行不完成。

#### formula.navigate_info｜了解公式槽位导航

**类型：** 信息

**资源键前缀：** teaching_c07_formula_navigate_info（_title / _body）

**教学正文：**

画布点击决定当前公式槽，嵌套时以点中的最深槽为准。方向键、Home、End只移动当前槽内的光标，不自动换分子、分母或上下限。回主行要点击 F = 再按 End；点框外不会自动返根槽。此步只说明，读完点击“下一步”。

**真实目标/函数：**

教学控制器 teaching_next

**精确成功条件与不完成反例：**

用户在当前信息步骤阅读后点击现有 teaching_next 明确确认；展示文案、初始化、业务事件、自动推进和跳过不代替确认。 本步只说明 set_caret_at→formula.hit_slot 的最深命中和 _TextInputEdit 的当前槽导航；不要求任何新增导航操作，也不改变现有树/槽内容/历史。不虚构下一槽、父槽按钮或 Tab 跨槽规则。

#### formula.finish｜结束编辑并保留完整公式

**类型：** 操作

**资源键前缀：** teaching_c07_formula_finish（_title / _body）

**教学正文：**

点击文字面板的“完成”，实际结束 F 的编辑。原 F 框与本章完整公式树必须保留，S 的符号也仍在；只隐藏面板、丢失结构或保留另一个框不算完成。

**真实目标/函数：**

text_panel 内 text_done→_text_done→end_text_edit

**精确成功条件与不完成反例：**

用户真实点击 text_done，当前编辑必须是原 F；结束后 editing_text_id/editing_slot 清空、text_panel 关闭，F.id 及本章实际构建完整 formula 树保持，S.id/四个符号保持，输入/保存收尾完成。六种实际新结构 frac/sup/sub/sqrt/sum/int、sqrt 内嵌 frac，以及各必做实际填槽、分母前插入和五次根槽末尾连接结果不得丢失；不要求例示字母数字值。只隐藏、空框丢弃、丢节点、错 ID、旧事件或此前未编辑不完成。

#### formula.limits_info｜了解公式与输入能力的边界

**类型：** 信息

**资源键前缀：** teaching_c07_formula_limits_info（_title / _body）

**教学正文：**

公式由现有结构按钮和槽位内容组成，不是 LaTeX 解析器，也不自动计算答案。普通符号与结构不同；输入框的结构占位显示不能当正文填写。公式不支持换行，方向键、Home、End只在当前槽内。系统软键盘及 End 键输入能力取决于本机，本练习不改系统设置。读完点击“下一步”。

**真实目标/函数：**

教学控制器 teaching_next

**精确成功条件与不完成反例：**

用户在当前信息步骤阅读后点击现有 teaching_next 明确确认；展示文案、初始化、业务事件、自动推进和跳过不代替确认。 必须位于本章实际 finish 之后，只阅读确认；不重开 F、不要求新增结构/键盘启动/LaTeX 输入、系统切换或求值。End 与软键盘的本机可用性不由文案保证，跳过不计完成。

#### formula.done｜确认本章完成

**类型：** 信息

**资源键前缀：** teaching_c07_formula_done（_title / _body）

**教学正文：**

完成本章必做步骤后，点击“下一步”确认本章完成；不会自动换章或退出。你可在教学中心选择其他章节，或点击“退出教学”回到原工作。跳过不计完成。

**真实目标/函数：**

教学控制器 teaching_next

**精确成功条件与不完成反例：**

此前本章全部必做业务结果与信息确认均已实际完成，用户再点击本步 teaching_next，只确认本章，不自动换章或退出；用户另在中心换章或用 teaching_exit 返回原工作，跳过不计完成。

## 业务接入与最终验收

主线程负责132键接入i18n、三章64步课程/目录JSON、私有素材、真实目标解析、当前步骤用户操作上下文、模型结果事件、原工作隔离与退出恢复，以及全部测试/布局/冻结包/最终验收。本写集不修改 main.py、i18n.py、catalog、fixtures 或 tests，不运行应用，也不访问真实data、用户项目或凭据。

核心验收不能只按按钮名称、埋点或总步数通过：edit须识别同一原框、真实拖放/提交、中间非末尾插入、实际删除/换行、两次结束和重新编辑后的末尾新增；format须核对选中T1、6/36联动、接受不同颜色、释放后的实际变换、不同ID复制和仅删除T2；formula须核对自动展示与真实符号插入的区别、独立structure点击、六种本次新节点、各槽实际新增内容、分母前插入、根号内嵌层级、五个独立根槽点击/End/末尾新增，以及finish保留原F完整树和S。

所有模型成功结果须绑定当前私有练习、当前步骤/轮次与真实用户输入，过滤旧事件、初始化、自动展开/投影、无效同值、取消、未提交IME和未收束手势。文字与公式的样例值不作为精确答题条件；现有按钮、规定符号/结构类型、format6/36，以及指定导航动作按实际契约核对。

## 本次静态自查

2026-10-11 使用 Python AST 解析源文本与字符串/标签比对，没有导入应用或执行应用测试。落盘 TEXT_COPY 的132键集合/顺序精确一致且无重复，全部为字面量八字符串tuple，共1056条非空完整纯文本，语言顺序zh/en/fr/es/de/ru/ko/ja；无导入、HTML、插值占位符、控制字符或隐藏软连字符。

三章步骤12/12/40共64，含10信息和54操作；各信息步骤使用现有八语言teaching_next，三章done同时使用现有teaching_exit。实际文本/框选/完成/退格/换行/改色/复/删/结构分组标签已核对，日文教学确认是“次の手順”。正文已遵循自动展开符号后直接点击、结构组单独用户打开、后续结构自动确保展开、根槽End后实际新增连接字符且样例不强制的新方向。

此结果只证明资源结构、文案/文档一致性与已读取标签和代码事实；真实事件接入、素材隔离、复杂IME/键盘能力、八语言布局与最终运行验收仍由主线程完成，不能把文案静态通过写成应用测试通过。
