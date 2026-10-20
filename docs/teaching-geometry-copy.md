# C06 形状与构图正式教学文案

日期：2026-10-11（Asia/Shanghai）。本稿落实已批准的 [2026-10-07 软件教学系统实施计划](superpowers/plans/2026-10-07-software-teaching-system.md) C06/T7 文案范围。资源为 [teaching/geometry_copy.py](../teaching/geometry_copy.py)。本写集只直接写该资源与本文；真实业务接入、课程/目录 JSON、私有合成素材、资源打包、全部测试和最终验收由主线程负责。本文的成功条件是接入契约，不表示相应业务已经实现或运行通过。

## 资源契约与步骤语义

- 导出唯一数据字典 `GEOMETRY_COPY`：115 键＝课程标题 1＋章标题 4＋55 步各自 title/body 110；每值为按 `zh, en, fr, es, de, ru, ko, ja` 排列的 8 字符串 tuple，共 920 条完整纯文本。保存为 UTF-8，字符串全部展开，无导入、HTML 或未填占位符，也不依赖 i18n 导入或运行时模板。
- 键名为 `teaching_c06_title`、`teaching_c06_<chapter>_title`、`teaching_c06_<chapter>_<step>_title/body`。后两种是本文解释命名规则的记号，实际资源不存在未展开模板键。
- 四章严格为 plane（22）、solid（10）、points（10）、recognition_snap（13），共 55 步。11 个信息确认步骤、44 个真实操作步骤；intro、done、order_info、limits_info、construction_info 均由用户点击现有 teaching_next 确认。
- 操作步骤只等真实业务结果。预置状态、控件高亮、说明出现、初始化、仅点击教学“下一步”、跳过、失败、取消或无效操作不代替相应成功结果。points.cancel 专门以真实取消并保留已提交内容作为成功结果。
- 平面取点在源码 add_pending_point 中可能已于最后按下时产生对象；教学必须继续等最后抬起及历史提交/输入收束，不能在手指或鼠标仍按住时宣称本步完成。识别也必须先实际定形替换笔迹，再等用户抬起收束。
- done 只确认本章，且此前所有必做步骤均须实际完成。不自动换章或结束练习；用户另在教学中心选择章节，或点击 teaching_exit 返回原工作。跳过不计完成，不新增“完成确认”按钮。
- 每章重建独立私有合成练习，素材、页面内容、历史、工具与设置只影响练习，原工作和原设置不变。不得把取消写成历史重做，也不承诺自动重做或跨章恢复。

## 源码核对与必须保留的差异

已先读取根 AGENTS.md、docs/agents/domain.md 和计划 C06/T7，再参考 teaching/pages_copy.py 与 docs/teaching-pages-copy.md。当前仓库没有根 GLOSSARY.md 或 docs/adr/，按领域说明正常继续，不创建补位文件，也不提出架构改动或读取工单。

事实依据为 [main.py](../main.py) 的 POINT_SHAPES、build_point_shape、add_pending_point、finish_shape_item、SHAPE_HINTS、SHAPE_OPS、_start_smart_hold、finish_smart_stroke、snap_to_line_endpoint、single_flat_shape、apply_shape_op、_aux_cross、_make_op_items_unsafe 与 open_more_menu；控件标签直接核对 [i18n.py](../i18n.py)。未导入应用，未读取用户项目、设置、名单、素材、桌面或凭据。

1. 设置页实际目标是 btn_settings_smart。关闭/开启标签为“智能识别图形：关”/“智能识别图形：开”，不是名为“智能图形识别”的独立按钮。本稿用“智能图形识别”描述功能，操作正文使用真实开关标签；系统展示练习设置目标后，用户自己点击关闭态按钮开启。
2. LINE 的 midpoint 操作真实菜单项是“中点标记”，不是“中点”。它生成两条辅助 LINE 构成的十字，保留原线。本稿实操使用真实名称。
3. 日文现有教学确认按钮是“次の手順”；八语言均使用 teaching_next/teaching_exit 的实际值，不能沿用“次のステップ”等旧译名，也不修改 i18n。
4. **椭圆存在给定要求与当前实现的事实冲突。** 用户给定“包围框两对角”，但当前 build_point_shape('ELLIPSE', pts) 将第一点作为 center，rx/ry 分别为两点 x/y 差的绝对值，rotation=0.0；SHAPE_HINTS 指向 hint_ellipse，实际提示也是“中心+外缘 1 点”。例如 (240,220)、(340,280) 生成中心 (240,220)、半轴 (100,60) 的椭圆；如果真按包围框对角计算，中心应为 (290,250)、半轴 (50,30)，结果不同。第二点用于尺寸定位，不保证位于数学意义的椭圆曲线上。

为遵守“不能教不存在的功能”，本稿 draw_ellipse 八语言正文和成功条件都按当前“中心＋外缘定位点”实现写，并明确这里不支持旋转绘制。**本稿不能声称已经交付包围框两对角语义。** 若主线程最终采用对角点要求，须先实现/确认实际业务，再同步本步骤八语言正文和成功条件；不得只改文案或 JSON 来宣称功能已有。此差异保持键名、55 步数量和顺序不变，本写集不改 main.py/i18n.py。

## 真实控件标签

以下按 i18n.py 原值列出，包括“图形”、14 个图形按钮、普通笔、取消取点、识别开关、历史、两项实操菜单和教学确认/退出。引号仅为文案排版；按钮实际文字不包含引号。

| i18n 键 | zh | en | fr | es | de | ru | ko | ja |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `teaching_next` | 下一步 | Next step | Étape suivante | Paso siguiente | Nächster Schritt | Следующий шаг | 다음 단계 | 次の手順 |
| `teaching_exit` | 退出教学 | Exit tutorial | Quitter le tutoriel | Salir del tutorial | Tutorial beenden | Выйти из обучения | 튜토리얼 종료 | チュートリアルを終了 |
| `pen` | 普通笔 | Pen | Stylo | Pluma | Stift | Перо | 펜 | ペン |
| `shape` | 图形 | Shapes | Formes | Formas | Formen | Фигуры | 도형 | 図形 |
| `undo` | 撤销 | Undo | Annuler | Deshacer | Rückgängig | Отменить | 실행 취소 | 元に戻す |
| `redo` | 重做 | Redo | Rétablir | Rehacer | Wiederholen | Повторить | 다시 실행 | やり直す |
| `cancel_points` | 取消取点 | Cancel points | Annuler les points | Cancelar puntos | Punkte verwerfen | Отменить точки | 점 취소 | 点をキャンセル |
| `smart_shapes_off` | 智能识别图形：关 | Smart shapes: OFF | Formes auto : OFF | Formas auto: OFF | Formerkennung: AUS | Распознавание фигур: ВЫКЛ | 도형 인식: 꺼짐 | 図形認識: オフ |
| `smart_shapes_on` | 智能识别图形：开 | Smart shapes: ON | Formes auto : ON | Formas auto: ON | Formerkennung: EIN | Распознавание фигур: ВКЛ | 도형 인식: 켜짐 | 図形認識: オン |
| `op_midpoint` | 中点标记 | Midpoint marker | Marque du milieu | Marca del punto medio | Mittelpunktmarke | Отметка середины | 중점 표시 | 中点マーク |
| `op_perp_bisector` | 垂直平分线 | Perpendicular bisector | Médiatrice | Mediatriz | Mittelsenkrechte | Серединный перпендикуляр | 수직이등분선 | 垂直二等分線 |
| `shape_line` | 直线 | Line | Ligne | Línea | Linie | Линия | 직선 | 直線 |
| `shape_dashed_line` | 虚线 | Dashed line | Pointillés | Discontinua | Gestrichelt | Пунктир | 점선 | 破線 |
| `shape_triangle` | 三角形 | Triangle | Triangle | Triángulo | Dreieck | Треугольник | 삼각형 | 三角形 |
| `shape_rect` | 矩形 | Rectangle | Rectangle | Rectángulo | Rechteck | Прямоугольник | 직사각형 | 長方形 |
| `shape_parallelogram` | 平行四边形 | Parallelogram | Parallélogramme | Paralelogramo | Parallelogramm | Параллелограмм | 평행사변형 | 平行四辺形 |
| `shape_trapezoid` | 梯形 | Trapezoid | Trapèze | Trapecio | Trapez | Трапеция | 사다리꼴 | 台形 |
| `shape_diamond` | 菱形 | Rhombus | Losange | Rombo | Raute | Ромб | 마름모 | ひし形 |
| `shape_angle` | 角 | Angle | Angle | Ángulo | Winkel | Угол | 각 | 角 |
| `shape_circle` | 圆形+圆心 | Circle + centre | Cercle + centre | Círculo + centro | Kreis + Mittelpunkt | Круг + центр | 원 + 중심 | 円 + 中心 |
| `shape_ellipse` | 椭圆形 | Ellipse | Ellipse | Elipse | Ellipse | Эллипс | 타원 | 楕円 |
| `shape_cuboid` | 长方体 | Cuboid | Pavé droit | Prisma | Quader | Параллелепипед | 직육면체 | 直方体 |
| `shape_cube` | 正方体 | Cube | Cube | Cubo | Würfel | Куб | 정육면체 | 立方体 |
| `shape_cylinder` | 圆柱体 | Cylinder | Cylindre | Cilindro | Zylinder | Цилиндр | 원기둥 | 円柱 |
| `shape_cone` | 圆锥体 | Cone | Cône | Cono | Kegel | Конус | 원뿔 | 円錐 |

## 真实取点、识别和构造事实

### 平面图形规则

| 类型 | 有效点数 | 点的含义与结果 |
| --- | --- | --- |
| LINE / DASHED_LINE | 2 | 两端点，相距应大于 8 像素；原地双击或过近第二点会被忽略。LINE/DASHED_LINE 的点可吸附到已提交直线/虚线的端点，不能据此宣称所有工具自动吸附。 |
| TRIANGLE | 3 | 依次三个顶点，练习采用非共线三点；不足三点时无已提交三角形。 |
| RECT | 2 | 包围矩形的两对角点；normalized QRectF 自动生成四角。 |
| PARALLELOGRAM | 3 | 沿边依次取三个相邻顶点 A/B/C；D=A+C−B 自动补出，不是先取一条对角线。 |
| TRAPEZOID | 4 | 第一底边 A/B，另一底边第三点 C，第四落点投影到过 C 且平行于 AB 的直线上，得到 D；练习须避免退化。 |
| DIAMOND | 3 | 先取一条对角线 A/C，再取侧点；侧点在垂直于 AC 的方向上的投影决定另一条半对角线，两侧关于中心对称。源码将过小半对角线钳制到绝对值 6；练习不用该边界代替有效取点。 |
| ANGLE | 3 | 第一为顶点，第二/第三为两臂端点；练习采用两臂有长度且张开的角。 |
| CIRCLE | 2 | 第一圆心，第二圆周点，距离为半径；真实按钮叫“圆形+圆心”。 |
| ELLIPSE | 2 | 当前源码为中心＋外缘尺寸定位点，两点横/纵差分别为半轴，rotation=0；不是包围框两对角点，差异见上。 |

十种平面图形均逐点点击，不拖动绘制；每次点击按下再抬起，最后抬起、真实提交和历史收束后才能完成对应绘图步骤。源码的通用边界判断不能替代本练习的有效几何要求；例如仅一个方向有长度也可能通过通用大小守卫，但不满足本稿要求的有效矩形、椭圆或立体矩形。

### 立体线框、取消和识别

- CUBOID/CUBE/CYLINDER/CONE 的真实按钮均在图形列表中，SHAPE_HINTS 未登记时提示“拖拽绘制”。按下后拖出宽/高均非零的矩形，抬起走 finish_shape_item/make_shape_item/add_shape_item，生成相应 type、kind=rect 的二维线框；不教三维编辑或真实体积，正方体步骤不额外要求用户把预览矩形拖成正方形。
- points 中前两点只是未完成取点/预览，不增加已提交 shape_items；cancel_points 实际清空 pending_points，既不新建图形，也不删除已提交图形，更不等同 undo/redo。
- 普通笔 draw_state=PEN 且 pen_style=pen 才进入智能停笔识别。SMART_HOLD_MS=650 是静止判定阈值，移出容差会重新计时。抬笔本身仅收束手绘，不触发识别；不得承诺真实响应时延、压力效果或每笔都可识别。
- 识别成功要核对同一新笔 stroke_id 的原 segments 被标准 LINE 对象替换；一次撤销只回到原手绘，第二次才可能回到落笔前，本章只做一次。一次重做恢复同一标准线并再次替换原手绘，不能用另画一条线或自动再识别充当重做。
- 直线吸附候选来自已提交 LINE/DASHED_LINE 的两个端点，LINE_SNAP_RADIUS=18。snap_line 必须记录实际第二落点 Q 与结果端点 B 的差异，证实 Q 被吸到指定锚端；只有同为 LINE 类型或刚好落在锚端不能证明吸附。

### “⋯”的可用范围与说明项

single_flat_shape 要求恰好选中一个平面图形。立体、多选、空选不具备本稿的通用“⋯”操作；菜单随形状变化。下面列出实际 SHAPE_OPS，**除 LINE 的中点标记和垂直平分线外，本章都只说明，不实操、不设额外成功等待。** 菜单存在也不保证无效几何能生成构造，需按 _make_op_items 的真实有效输出判定。

| 图形 | 实际菜单项（中文） |
| --- | --- |
| TRIANGLE | 外接圆、内切圆、三条中线、三条高、中位线三角形 |
| RECT | 对角线、外接圆、内切圆、中心点 |
| PARALLELOGRAM | 对角线、中心点 |
| TRAPEZOID | 对角线、高 |
| DIAMOND | 对角线、内切圆、中心点 |
| CIRCLE | 直径、半径、内接正方形、外切正方形、内接等边三角形 |
| ELLIPSE | 长轴与短轴、两个焦点 |
| LINE / DASHED_LINE | 中点标记、垂直平分线 |
| ANGLE（open_more_menu 专用分支） | 当前角度（只读）、角度 +5°、角度 −5°、设为常用角（30°/45°/60°/90°/120°/135°）、作角平分线 |

midpoint 调用 _aux_cross，实际新建两条实线辅助线，默认半长 7；perp_bisector 新增虚线辅助线，过原线中点且垂直，半长 max(30,原线长度×0.4)。两者都不替换原线，辅助对象 select=False，原线保持单选。本章必须重开“⋯”选择第二项；打开/关闭菜单、空输出、异常或旧辅助线不能代替新构造成功。角度调整源码限制在 5°到175°之间，本章只介绍范围，不要求执行。

## 主线程准备的私有练习素材

下面是业务接入所需的独立合成初始状态，不是本写集创建的资源文件。坐标均为练习画布坐标，不是桌面坐标；主线程负责素材布局、足够的空白区以及目标定位，不通过实屏、截图、桌面捕获或系统输入生成样例。

| 章节 | 初始状态 | 合成素材与本章结果 |
| --- | --- | --- |
| plane | draw_state=SHAPE、shape_type=ELLIPSE、pending_points=[]、空白画布 | 第一 choose_line 必须独立按钮选择。十种平面图形依指定次序逐个选择、取点并提交；每步记录本次新对象 ID/类型/几何，既有对象不可顶替新结果。 |
| solid | draw_state=SHAPE、shape_type=LINE、pending_points=[]、空白画布 | 四种立体工具各真实选择后拖动提交，矩形宽高均明显有效，建议均大于 6 画布像素；线框和历史仅存本章。 |
| points | draw_state=SHAPE、shape_type=LINE、pending_points=[]、空白画布 | 第一轮建议 P1=(120,160)、P2=(360,160)，然后真实取消；新轮次 Q1=(120,160)、Q2=(360,160)、Q3=(240,340) 提交一个三角形。记录实际用户落点而非自动植入建议点。 |
| recognition_snap | draw_state=SHAPE、smart_shapes_enabled=False、pending_points=[]；可用 ELLIPSE 作为初始形状类型 | 唯一水平合成锚线 A：LINE，(120,150)→(240,150)。普通笔近直线示例为 (100,460)→(364,460)，识别/撤销/重做绑定本次 stroke_id 与结果 R。之后新线 S=(240,340)→(240,150)，第二实际落点示例 (248,157) 证明吸附。仅 S 为两项实操构造对象；保留 A/R。 |

A/R/S/P/Q 是本文为描述身份关系使用的记号，不是硬编码对象 ID、用户需输入的文字或未填资源占位符。主线程需记录实际 UUID/笔迹 ID、动作前后模型与用户输入，旧事件和已存在的相同外观不得完成新步骤。章节间不继承前章素材、点、识别状态或练习历史；原工作设置不受开启识别影响。

## 55 步中文全文与精确成功条件

固定顺序如下，各步骤同时列出 title/body 键前缀、中文全文及精确成功条件。全部正文直接对应 GEOMETRY_COPY 的 zh 项。
### plane｜逐点绘制平面图形

#### plane.intro｜开始平面图形练习

**类型：** 信息

**资源键前缀：** `teaching_c06_plane_intro`（`_title` / `_body`）

**教学正文：**

本章在独立私有练习里逐一点选十种平面图形。初始工具是“椭圆形”，先点击“下一步”，再亲自选择“直线”。各点依次点击，最后一次抬起提交才算完成；素材、历史和设置不改原工作。

**精确成功条件：**

用户在当前信息步骤阅读后点击现有 teaching_next 按钮明确确认；初始化、展示说明、业务事件、自动推进或跳过均不能替代确认。 初始 draw_state=SHAPE、shape_type=ELLIPSE，练习画布空白且无 pending_points；本步不得替用户选择 LINE。

#### plane.choose_line｜选择直线

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_choose_line`（`_title` / `_body`）

**教学正文：**

点击图形列表中的“直线”，真实切换到该图形工具。先完成按钮选择，再到空白处取点。

**精确成功条件：**

用户点击 shape_line 对应的真实图形按钮；draw_state=SHAPE 且 shape_type 从此前类型切换为 LINE，按钮选中、pending_points 为空。仅初始预置、展开列表或点击教学“下一步”不完成。

#### plane.draw_line｜逐点绘制直线

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_draw_line`（`_title` / `_body`）

**教学正文：**

在空白处先点击直线的第一个端点，再点击相隔一段距离的第二个端点。每次点击后抬起，第二次抬起并提交直线后完成；不要在原地双击，也不要拖动绘制。

**精确成功条件：**

已真实选择 LINE。本步由用户逐次有效点击取点；两端点有效且相距大于 8 画布像素，kind=poly、closed=False、points 恰为两个端点。 最后一次点击抬起、输入提交和历史收束后，实际新增一个不同 ID 的 LINE，pending_points 为空。预览、少点、仅按下未抬起、取消取点、既有图形或无效输入不完成；不以点击“下一步”完成。

#### plane.choose_dashed_line｜选择虚线

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_choose_dashed_line`（`_title` / `_body`）

**教学正文：**

点击图形列表中的“虚线”，真实切换到该图形工具。先完成按钮选择，再到空白处取点。

**精确成功条件：**

用户点击 shape_dashed_line 对应的真实图形按钮；draw_state=SHAPE 且 shape_type 从此前类型切换为 DASHED_LINE，按钮选中、pending_points 为空。仅初始预置、展开列表或点击教学“下一步”不完成。

#### plane.draw_dashed_line｜逐点绘制虚线

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_draw_dashed_line`（`_title` / `_body`）

**教学正文：**

先点击虚线的第一个端点，再在另一处点击第二个端点，并在最后一次点击后抬起提交。虚线由这两个端点生成，不用逐段画短线；不要原地双击或拖动绘制。

**精确成功条件：**

已真实选择 DASHED_LINE。本步由用户逐次有效点击取点；两端点有效且相距大于 8 画布像素，type=DASHED_LINE、kind=poly、closed=False、points 恰为两个端点；不能将普通 LINE 或三段识别虚线计为本步结果。 最后一次点击抬起、输入提交和历史收束后，实际新增一个不同 ID 的 DASHED_LINE，pending_points 为空。预览、少点、仅按下未抬起、取消取点、既有图形或无效输入不完成；不以点击“下一步”完成。

#### plane.choose_triangle｜选择三角形

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_choose_triangle`（`_title` / `_body`）

**教学正文：**

点击图形列表中的“三角形”，真实切换到该图形工具。先完成按钮选择，再到空白处取点。

**精确成功条件：**

用户点击 shape_triangle 对应的真实图形按钮；draw_state=SHAPE 且 shape_type 从此前类型切换为 TRIANGLE，按钮选中、pending_points 为空。仅初始预置、展开列表或点击教学“下一步”不完成。

#### plane.draw_triangle｜逐点绘制三角形

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_draw_triangle`（`_title` / `_body`）

**教学正文：**

依次点击三角形的第一、第二、第三个顶点，三点不要排成一条直线。前两点只是未完成预览；第三次点击抬起并提交后，才完成一个三角形。

**精确成功条件：**

已真实选择 TRIANGLE。本步由用户逐次有效点击取点；三个非共线顶点按点击顺序保存，kind=poly、closed=True、points 数量为 3。 最后一次点击抬起、输入提交和历史收束后，实际新增一个不同 ID 的 TRIANGLE，pending_points 为空。预览、少点、仅按下未抬起、取消取点、既有图形或无效输入不完成；不以点击“下一步”完成。

#### plane.choose_rect｜选择矩形

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_choose_rect`（`_title` / `_body`）

**教学正文：**

点击图形列表中的“矩形”，真实切换到该图形工具。先完成按钮选择，再到空白处取点。

**精确成功条件：**

用户点击 shape_rect 对应的真实图形按钮；draw_state=SHAPE 且 shape_type 从此前类型切换为 RECT，按钮选中、pending_points 为空。仅初始预置、展开列表或点击教学“下一步”不完成。

#### plane.draw_rect｜逐点绘制矩形

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_draw_rect`（`_title` / `_body`）

**教学正文：**

先点击矩形的一个角，再点击与它对角的另一个角，两点在横向和纵向都要分开。最后一次抬起提交后，软件自动补出其余两个角，生成矩形。

**精确成功条件：**

已真实选择 RECT。本步由用户逐次有效点击取点；两对角点在 x/y 方向均有非零差值，实际结果为两点的 normalized QRectF 四角，kind=poly、closed=True、points 数量为 4。 最后一次点击抬起、输入提交和历史收束后，实际新增一个不同 ID 的 RECT，pending_points 为空。预览、少点、仅按下未抬起、取消取点、既有图形或无效输入不完成；不以点击“下一步”完成。

#### plane.choose_parallelogram｜选择平行四边形

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_choose_parallelogram`（`_title` / `_body`）

**教学正文：**

点击图形列表中的“平行四边形”，真实切换到该图形工具。先完成按钮选择，再到空白处取点。

**精确成功条件：**

用户点击 shape_parallelogram 对应的真实图形按钮；draw_state=SHAPE 且 shape_type 从此前类型切换为 PARALLELOGRAM，按钮选中、pending_points 为空。仅初始预置、展开列表或点击教学“下一步”不完成。

#### plane.draw_parallelogram｜逐点绘制平行四边形

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_draw_parallelogram`（`_title` / `_body`）

**教学正文：**

沿着平行四边形的边，依次点击三个相邻顶点，不要先点一条对角线。第三次抬起提交后，第四个顶点自动补出，形成平行四边形。

**精确成功条件：**

已真实选择 PARALLELOGRAM。本步由用户逐次有效点击取点；三个相邻顶点 A/B/C 非共线，第四顶点严格按 D=A+C−B 自动计算；kind=poly、closed=True、points=[A,B,C,D]。 最后一次点击抬起、输入提交和历史收束后，实际新增一个不同 ID 的 PARALLELOGRAM，pending_points 为空。预览、少点、仅按下未抬起、取消取点、既有图形或无效输入不完成；不以点击“下一步”完成。

#### plane.choose_trapezoid｜选择梯形

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_choose_trapezoid`（`_title` / `_body`）

**教学正文：**

点击图形列表中的“梯形”，真实切换到该图形工具。先完成按钮选择，再到空白处取点。

**精确成功条件：**

用户点击 shape_trapezoid 对应的真实图形按钮；draw_state=SHAPE 且 shape_type 从此前类型切换为 TRAPEZOID，按钮选中、pending_points 为空。仅初始预置、展开列表或点击教学“下一步”不完成。

#### plane.draw_trapezoid｜逐点绘制梯形

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_draw_trapezoid`（`_title` / `_body`）

**教学正文：**

先点击同一条底边的两个端点，再点击另一条底边的第三个顶点，最后点击第四个顶点并抬起。第四点会投影到经过第三点、与第一条底边平行的直线上；提交后生成梯形。

**精确成功条件：**

已真实选择 TRAPEZOID。本步由用户逐次有效点击取点；第一底边 A/B 非重合，第三点 C 不在 AB 上；第四点 D=project_to_parallel(C,B−A,第四次落点)，CD 与 AB 平行且非退化；kind=poly、closed=True、points 数量为 4。 最后一次点击抬起、输入提交和历史收束后，实际新增一个不同 ID 的 TRAPEZOID，pending_points 为空。预览、少点、仅按下未抬起、取消取点、既有图形或无效输入不完成；不以点击“下一步”完成。

#### plane.choose_diamond｜选择菱形

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_choose_diamond`（`_title` / `_body`）

**教学正文：**

点击图形列表中的“菱形”，真实切换到该图形工具。先完成按钮选择，再到空白处取点。

**精确成功条件：**

用户点击 shape_diamond 对应的真实图形按钮；draw_state=SHAPE 且 shape_type 从此前类型切换为 DIAMOND，按钮选中、pending_points 为空。仅初始预置、展开列表或点击教学“下一步”不完成。

#### plane.draw_diamond｜逐点绘制菱形

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_draw_diamond`（`_title` / `_body`）

**教学正文：**

先依次点击菱形一条对角线的两个顶点，再点击侧面一点，决定另一条半对角线的长度。第三次抬起提交后，软件按中心对称补出两侧顶点，生成菱形。

**精确成功条件：**

已真实选择 DIAMOND。本步由用户逐次有效点击取点；前两点 A/C 为不同对角顶点，中心=(A+C)/2；第三点在 AC 的垂直方向的投影决定另一条半对角线，两侧顶点关于中心对称；kind=poly、closed=True、points 数量为 4。 最后一次点击抬起、输入提交和历史收束后，实际新增一个不同 ID 的 DIAMOND，pending_points 为空。预览、少点、仅按下未抬起、取消取点、既有图形或无效输入不完成；不以点击“下一步”完成。

#### plane.choose_angle｜选择角

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_choose_angle`（`_title` / `_body`）

**教学正文：**

点击图形列表中的“角”，真实切换到该图形工具。先完成按钮选择，再到空白处取点。

**精确成功条件：**

用户点击 shape_angle 对应的真实图形按钮；draw_state=SHAPE 且 shape_type 从此前类型切换为 ANGLE，按钮选中、pending_points 为空。仅初始预置、展开列表或点击教学“下一步”不完成。

#### plane.draw_angle｜逐点绘制角

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_draw_angle`（`_title` / `_body`）

**教学正文：**

先点击角的顶点，再点击第一条边上的端点，最后点击第二条边上的端点。两边要张开且各有长度；第三次抬起提交后生成角，第一点始终是顶点。

**精确成功条件：**

已真实选择 ANGLE。本步由用户逐次有效点击取点；kind=angle，vertex 为第一点、p1 为第二点、p2 为第三点；两臂长度非零且角非退化，不将首点作为边端点。 最后一次点击抬起、输入提交和历史收束后，实际新增一个不同 ID 的 ANGLE，pending_points 为空。预览、少点、仅按下未抬起、取消取点、既有图形或无效输入不完成；不以点击“下一步”完成。

#### plane.choose_circle｜选择圆形+圆心

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_choose_circle`（`_title` / `_body`）

**教学正文：**

点击图形列表中的“圆形+圆心”，真实切换到该图形工具。先完成按钮选择，再到空白处取点。

**精确成功条件：**

用户点击 shape_circle 对应的真实图形按钮；draw_state=SHAPE 且 shape_type 从此前类型切换为 CIRCLE，按钮选中、pending_points 为空。仅初始预置、展开列表或点击教学“下一步”不完成。

#### plane.draw_circle｜逐点绘制圆形+圆心

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_draw_circle`（`_title` / `_body`）

**教学正文：**

先点击圆心，再点击圆周上的一点，第二点要与圆心分开。第二次抬起提交后，软件以两点距离为半径生成圆；不用拖动，也不用逐点围出圆周。

**精确成功条件：**

已真实选择 CIRCLE。本步由用户逐次有效点击取点；kind=circle，center=第一点，radius=第一点到第二点距离且有效非零；真实控件名称为 shape_circle 的“圆形+圆心”。 最后一次点击抬起、输入提交和历史收束后，实际新增一个不同 ID 的 CIRCLE，pending_points 为空。预览、少点、仅按下未抬起、取消取点、既有图形或无效输入不完成；不以点击“下一步”完成。

#### plane.choose_ellipse｜选择椭圆形

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_choose_ellipse`（`_title` / `_body`）

**教学正文：**

点击图形列表中的“椭圆形”，真实切换到该图形工具。先完成按钮选择，再到空白处取点。

**精确成功条件：**

用户点击 shape_ellipse 对应的真实图形按钮；draw_state=SHAPE 且 shape_type 从此前类型切换为 ELLIPSE，按钮选中、pending_points 为空。仅初始预置、展开列表或点击教学“下一步”不完成。

#### plane.draw_ellipse｜逐点绘制椭圆形

**类型：** 操作

**资源键前缀：** `teaching_c06_plane_draw_ellipse`（`_title` / `_body`）

**教学正文：**

按当前工具规则，先点击椭圆中心，再点击一个横向、纵向都与中心分开的外缘定位点，确定两个半轴。第二次抬起提交后生成椭圆；此处不是包围框两对角取点，也不支持旋转绘制。

**精确成功条件：**

已真实选择 ELLIPSE。本步由用户逐次有效点击取点；按当前 build_point_shape：kind=ellipse、center=第一点、rx=|第二点.x−第一点.x|、ry=|第二点.y−第一点.y|、rotation=0.0，两个半轴均有效非零。用户给定的包围框两对角语义与当前源码冲突，本稿不将未实现语义作为事实；接入前由主线程核对。 最后一次点击抬起、输入提交和历史收束后，实际新增一个不同 ID 的 ELLIPSE，pending_points 为空。预览、少点、仅按下未抬起、取消取点、既有图形或无效输入不完成；不以点击“下一步”完成。

#### plane.done｜确认本章完成

**类型：** 信息

**资源键前缀：** `teaching_c06_plane_done`（`_title` / `_body`）

**教学正文：**

完成本章必做步骤后，点击“下一步”确认本章完成；不会自动换章或退出。你可在教学中心选择其他章节，或点击“退出教学”回到原工作。跳过不计完成。

**精确成功条件：**

此前本章全部必做操作与信息确认已实际完成，用户再点击本步 teaching_next，只确认本章；不自动换章或退出。用户另在教学中心换章或用 teaching_exit 返回原工作，跳过不计完成。

### solid｜拖动绘制立体线框

#### solid.intro｜开始立体线框练习

**类型：** 信息

**资源键前缀：** `teaching_c06_solid_intro`（`_title` / `_body`）

**教学正文：**

本章在独立私有画布中练习长方体、正方体、圆柱体和圆锥体。每次先选择真实图形按钮，再按下、拖出有宽高的矩形并抬起，创建立体线框；这里不做三维编辑或计算真实体积。点击“下一步”开始，原工作不变。

**精确成功条件：**

用户在当前信息步骤阅读后点击现有 teaching_next 按钮明确确认；初始化、展示说明、业务事件、自动推进或跳过均不能替代确认。 主线程准备空白私有画布，draw_state=SHAPE、shape_type=LINE；四次选择和拖动均须由用户实际完成。

#### solid.choose_cuboid｜选择长方体

**类型：** 操作

**资源键前缀：** `teaching_c06_solid_choose_cuboid`（`_title` / `_body`）

**教学正文：**

点击图形列表中的“长方体”，真实选中这个立体图形工具。选好后，再在空白处拖动绘制线框。

**精确成功条件：**

用户点击 shape_cuboid 真实按钮，shape_type 从此前类型变为 CUBOID、draw_state=SHAPE、按钮选中、无 pending_points。预置、只展开列表或点击“下一步”不完成。

#### solid.draw_cuboid｜拖出长方体线框

**类型：** 操作

**资源键前缀：** `teaching_c06_solid_draw_cuboid`（`_title` / `_body`）

**教学正文：**

在空白处按下，拖到另一处，让预览矩形的宽和高都明显大于零，再抬起。真实新增“长方体”线框后完成；仅点一下、未抬起的预览或退化矩形不算完成。

**精确成功条件：**

已实际选中 CUBOID。在空白处真实按下、移动形成 normalized QRectF，宽和高均明显非零（练习采用均大于 6 画布像素），最后抬起走 finish_shape_item/add_shape_item，实际新增一个不同 ID 的 CUBOID、kind=rect、rotation=0.0，并清理 preview_shape/shape_start、提交历史。预览、无移动、未抬起、退化输入或新增其他类型均不完成。该图形是二维画布上的立体线框，不验收三维编辑或物理体积。

#### solid.choose_cube｜选择正方体

**类型：** 操作

**资源键前缀：** `teaching_c06_solid_choose_cube`（`_title` / `_body`）

**教学正文：**

点击图形列表中的“正方体”，真实选中这个立体图形工具。选好后，再在空白处拖动绘制线框。

**精确成功条件：**

用户点击 shape_cube 真实按钮，shape_type 从此前类型变为 CUBE、draw_state=SHAPE、按钮选中、无 pending_points。预置、只展开列表或点击“下一步”不完成。

#### solid.draw_cube｜拖出正方体线框

**类型：** 操作

**资源键前缀：** `teaching_c06_solid_draw_cube`（`_title` / `_body`）

**教学正文：**

在空白处按下，拖到另一处，让预览矩形的宽和高都明显大于零，再抬起。真实新增“正方体”线框后完成；仅点一下、未抬起的预览或退化矩形不算完成。

**精确成功条件：**

已实际选中 CUBE。在空白处真实按下、移动形成 normalized QRectF，宽和高均明显非零（练习采用均大于 6 画布像素），最后抬起走 finish_shape_item/add_shape_item，实际新增一个不同 ID 的 CUBE、kind=rect、rotation=0.0，并清理 preview_shape/shape_start、提交历史。预览、无移动、未抬起、退化输入或新增其他类型均不完成。该图形是二维画布上的立体线框，不验收三维编辑或物理体积。

#### solid.choose_cylinder｜选择圆柱体

**类型：** 操作

**资源键前缀：** `teaching_c06_solid_choose_cylinder`（`_title` / `_body`）

**教学正文：**

点击图形列表中的“圆柱体”，真实选中这个立体图形工具。选好后，再在空白处拖动绘制线框。

**精确成功条件：**

用户点击 shape_cylinder 真实按钮，shape_type 从此前类型变为 CYLINDER、draw_state=SHAPE、按钮选中、无 pending_points。预置、只展开列表或点击“下一步”不完成。

#### solid.draw_cylinder｜拖出圆柱体线框

**类型：** 操作

**资源键前缀：** `teaching_c06_solid_draw_cylinder`（`_title` / `_body`）

**教学正文：**

在空白处按下，拖到另一处，让预览矩形的宽和高都明显大于零，再抬起。真实新增“圆柱体”线框后完成；仅点一下、未抬起的预览或退化矩形不算完成。

**精确成功条件：**

已实际选中 CYLINDER。在空白处真实按下、移动形成 normalized QRectF，宽和高均明显非零（练习采用均大于 6 画布像素），最后抬起走 finish_shape_item/add_shape_item，实际新增一个不同 ID 的 CYLINDER、kind=rect、rotation=0.0，并清理 preview_shape/shape_start、提交历史。预览、无移动、未抬起、退化输入或新增其他类型均不完成。该图形是二维画布上的立体线框，不验收三维编辑或物理体积。

#### solid.choose_cone｜选择圆锥体

**类型：** 操作

**资源键前缀：** `teaching_c06_solid_choose_cone`（`_title` / `_body`）

**教学正文：**

点击图形列表中的“圆锥体”，真实选中这个立体图形工具。选好后，再在空白处拖动绘制线框。

**精确成功条件：**

用户点击 shape_cone 真实按钮，shape_type 从此前类型变为 CONE、draw_state=SHAPE、按钮选中、无 pending_points。预置、只展开列表或点击“下一步”不完成。

#### solid.draw_cone｜拖出圆锥体线框

**类型：** 操作

**资源键前缀：** `teaching_c06_solid_draw_cone`（`_title` / `_body`）

**教学正文：**

在空白处按下，拖到另一处，让预览矩形的宽和高都明显大于零，再抬起。真实新增“圆锥体”线框后完成；仅点一下、未抬起的预览或退化矩形不算完成。

**精确成功条件：**

已实际选中 CONE。在空白处真实按下、移动形成 normalized QRectF，宽和高均明显非零（练习采用均大于 6 画布像素），最后抬起走 finish_shape_item/add_shape_item，实际新增一个不同 ID 的 CONE、kind=rect、rotation=0.0，并清理 preview_shape/shape_start、提交历史。预览、无移动、未抬起、退化输入或新增其他类型均不完成。该图形是二维画布上的立体线框，不验收三维编辑或物理体积。

#### solid.done｜确认本章完成

**类型：** 信息

**资源键前缀：** `teaching_c06_solid_done`（`_title` / `_body`）

**教学正文：**

完成本章必做步骤后，点击“下一步”确认本章完成；不会自动换章或退出。你可在教学中心选择其他章节，或点击“退出教学”回到原工作。跳过不计完成。

**精确成功条件：**

此前本章全部必做操作与信息确认已实际完成，用户再点击本步 teaching_next，只确认本章；不自动换章或退出。用户另在教学中心换章或用 teaching_exit 返回原工作，跳过不计完成。

### points｜取点顺序与取消

#### points.intro｜开始取点与取消练习

**类型：** 信息

**资源键前缀：** `teaching_c06_points_intro`（`_title` / `_body`）

**教学正文：**

本章从“直线”工具和空白私有画布开始。你将亲自选择三角形，取两个点后取消，再重新取三个点完成；不会自动重做或恢复上一章结果。点击“下一步”开始，练习素材、历史和设置不改原工作。

**精确成功条件：**

用户在当前信息步骤阅读后点击现有 teaching_next 按钮明确确认；初始化、展示说明、业务事件、自动推进或跳过均不能替代确认。 初始 draw_state=SHAPE、shape_type=LINE、pending_points=[]、shape_items 无已提交练习图形。

#### points.choose_triangle｜选择三角形工具

**类型：** 操作

**资源键前缀：** `teaching_c06_points_choose_triangle`（`_title` / `_body`）

**教学正文：**

点击图形列表中的“三角形”，从当前“直线”真实切换到三角形工具。选择完成后才开始取点。

**精确成功条件：**

用户点击 shape_triangle 真实按钮使 shape_type 从 LINE 变为 TRIANGLE，draw_state=SHAPE、pending_points=[]，且未创建图形。只预置 TRIANGLE 或展示控件不完成。

#### points.point1｜取第一个点

**类型：** 操作

**资源键前缀：** `teaching_c06_points_point1`（`_title` / `_body`）

**教学正文：**

在空白处点击第一个顶点并抬起，建议位置为 (120,160)。此时只保留一个未完成取点，还没有新建三角形。

**精确成功条件：**

shape_type=TRIANGLE，用户本次点击并抬起后 pending_points 从 0 变为 1，记录真实第一点（建议 P1=(120,160)）；shape_items 数量和已提交历史内容不增加。仅按下未释放、未实际落点或已创建图形不完成。

#### points.point2｜取第二个点，保留预览

**类型：** 操作

**资源键前缀：** `teaching_c06_points_point2`（`_title` / `_body`）

**教学正文：**

在第一点右侧点击第二个顶点并抬起，建议位置为 (360,160)。两点仍只是未完成预览，尚未提交三角形；本步先停在这里。

**精确成功条件：**

用户真实点击并抬起后 pending_points 从 1 变为 2，保持此前第一点且记录不同的第二点（建议 P2=(360,160)）；两点只能作为未完成预览，shape_items 仍无新增 TRIANGLE。第三点、提前完成或纯展示预览不完成本步。

#### points.cancel｜取消这两个未完成点

**类型：** 操作

**资源键前缀：** `teaching_c06_points_cancel`（`_title` / `_body`）

**教学正文：**

点击真实“取消取点”按钮，清空刚才的两个点和未完成预览。没有新建图形，也不会替你重做；这次取消不删除已经提交的图形。

**精确成功条件：**

本步开始时 pending_points 恰有 2 点；用户点击 cancel_points 实际执行 cancel_pending_points，数组 2→0、未完成预览清空，shape_items 与已提交内容/历史保持且没有新 TRIANGLE。空数组上的空操作、关闭面板或自动清点均不完成。

#### points.restart1｜重新取第一个点

**类型：** 操作

**资源键前缀：** `teaching_c06_points_restart1`（`_title` / `_body`）

**教学正文：**

取消后，重新点击第一个顶点并抬起，建议仍为 (120,160)。这是新一轮取点，之前的两个点没有自动恢复；此时仍没有三角形。

**精确成功条件：**

此前真实 cancel 已完成，pending_points=[]；本步由用户新一次点击并抬起，使 pending_points 0→1，记录新轮次 Q1（建议 (120,160)），无新增图形。不能从旧两点恢复或自动重做计为完成。

#### points.restart2｜重新取第二个点

**类型：** 操作

**资源键前缀：** `teaching_c06_points_restart2`（`_title` / `_body`）

**教学正文：**

在新第一点的右侧，重新点击第二个顶点并抬起，建议仍为 (360,160)。现在保存的是新一轮的两个点，仍只有未完成预览；第三点尚未取。

**精确成功条件：**

本步保留 restart1 新建的 Q1；用户新的第二次点击并抬起使 pending_points 1→2，记录 Q2（建议 (360,160)），只有未完成预览且无新增 TRIANGLE。不能复用取消前的两点或提前提交。

#### points.finish3｜取第三个点并完成三角形

**类型：** 操作

**资源键前缀：** `teaching_c06_points_finish3`（`_title` / `_body`）

**教学正文：**

在前两点下方点击第三个顶点并抬起，建议位置为 (240,340)。三点不要共线；最后一次抬起并真实提交后，生成一个三角形，未完成点清空。

**精确成功条件：**

保留 restart1/restart2 的 Q1/Q2；本步用户落 Q3（建议 (240,340)），三点非共线，并在最后抬起/历史提交后新增唯一一个不同 ID 的 TRIANGLE、kind=poly、closed=True、points=[Q1,Q2,Q3]，pending_points 为空。仅第三点按下、预览、取消、错序或旧轮次顶点不完成。

#### points.order_info｜理解点的含义与取消范围

**类型：** 信息

**资源键前缀：** `teaching_c06_points_order_info`（`_title` / `_body`）

**教学正文：**

每种图形的取点含义不同：直线取两端，矩形取两对角，三角形取三个顶点，圆先取圆心再取圆周点。取消只丢弃未完成点，不删除已提交图形，也不自动重做或跨章恢复。读完点击“下一步”。

**精确成功条件：**

用户在当前信息步骤阅读后点击现有 teaching_next 按钮明确确认；初始化、展示说明、业务事件、自动推进或跳过均不能替代确认。 保留 finish3 已提交的唯一三角形，不再次取消、不重新取点，不自动重做或恢复上一章状态。

#### points.done｜确认本章完成

**类型：** 信息

**资源键前缀：** `teaching_c06_points_done`（`_title` / `_body`）

**教学正文：**

完成本章必做步骤后，点击“下一步”确认本章完成；不会自动换章或退出。你可在教学中心选择其他章节，或点击“退出教学”回到原工作。跳过不计完成。

**精确成功条件：**

此前本章全部必做操作与信息确认已实际完成，用户再点击本步 teaching_next，只确认本章；不自动换章或退出。用户另在教学中心换章或用 teaching_exit 返回原工作，跳过不计完成。

### recognition_snap｜停笔识别、端点吸附与构造

#### recognition_snap.intro｜开始识别、吸附与构造练习

**类型：** 信息

**资源键前缀：** `teaching_c06_recognition_snap_intro`（`_title` / `_body`）

**教学正文：**

本章初始为图形工具，智能识别关闭。私有画布上方已有从 (120,150) 到 (240,150) 的水平合成锚线；接下来练习停笔定形、撤销与重做、端点吸附和两种辅助构造。素材、历史与设置只在本练习内生效。点击“下一步”开始。

**精确成功条件：**

用户在当前信息步骤阅读后点击现有 teaching_next 按钮明确确认；初始化、展示说明、业务事件、自动推进或跳过均不能替代确认。 初始 draw_state=SHAPE、smart_shapes_enabled=False、pending_points=[]；主线程提供唯一合成锚线 A，type=LINE、kind=poly、closed=False、points=[(120,150),(240,150)]，无识别手绘或辅助构造。

#### recognition_snap.enable｜开启智能图形识别

**类型：** 操作

**资源键前缀：** `teaching_c06_recognition_snap_enable`（`_title` / `_body`）

**教学正文：**

系统已展示本练习的设置目标。点击“智能识别图形：关”，真实开启后按钮应变为“智能识别图形：开”。这项操作只改私有练习设置，不改原工作设置。

**精确成功条件：**

主线程展示真实 btn_settings_smart 目标；用户点击当前 smart_shapes_off，执行 toggle_smart_shapes/set_smart_shapes 后 smart_shapes_enabled False→True，按钮显示 smart_shapes_on。draw_state 仍为 SHAPE，锚线不变。仅展示设置、预置 True、点击同值或修改原工作设置不完成。

#### recognition_snap.pen｜选择普通笔

**类型：** 操作

**资源键前缀：** `teaching_c06_recognition_snap_pen`（`_title` / `_body`）

**教学正文：**

选择列表中的“普通笔”，真实进入普通笔绘写状态。接下来用这支笔画近似直线，先不要换成图形工具或其它笔型。

**精确成功条件：**

用户点击真实普通笔入口，draw_state 从 SHAPE→PEN，pen_style=pen、当前普通笔选中，smart_shapes_enabled=True。只展开列表、预置笔状态或选择其它笔型不完成；锚线不变。

#### recognition_snap.recognize_line｜停在末端，把手绘变为直线

**类型：** 操作

**资源键前缀：** `teaching_c06_recognition_snap_recognize_line`（`_title` / `_body`）

**教学正文：**

用普通笔从空白处画一笔近似直线，例如从 (100,460) 到 (364,460)。按住末端不移动约 650 ms，等它定形成标准直线再抬起；必须真实新增直线并替换原手绘。仅点一下、未定形就抬笔或取消都不算完成。

**精确成功条件：**

draw_state=PEN、pen_style=pen、smart_shapes_enabled=True；用户绘出当前新笔 stroke_id 的非零有效近直线。停住约 SMART_HOLD_MS=650 后 finish_smart_stroke 得到 spec.type=LINE，实际增加标准 LINE 对象 R，并从 all_segments 移除该 stroke_id 的原手绘；记录可核对的原手绘 segments 与 R 的 ID/几何。用户随后抬起、该输入收束后完成。原锚线 A 保持，未定形、只点击、提前抬起、取消、其他类型或手绘/图形并存不完成。650 ms 是停住判定阈值，不作为物理时延保证。

#### recognition_snap.undo_recognition｜撤销识别，找回原手绘

**类型：** 操作

**资源键前缀：** `teaching_c06_recognition_snap_undo_recognition`（`_title` / `_body`）

**教学正文：**

点击一次“撤销”，让刚识别的直线回到同一笔原手绘。上方锚线应保留；本步撤销的是识别转换，不是再撤销到落笔之前。

**精确成功条件：**

用户一次有效 undo 对识别转换执行：R 从 shape_items 移除，原 stroke_id 的 segments 实际恢复且点/笔迹属性与识别前一致；A ID/端点不变，重做栈包含本次转换。空撤销、仅堆栈数变化、把手绘也撤销或删掉锚线均不完成。

#### recognition_snap.redo_recognition｜重做识别，恢复标准直线

**类型：** 操作

**资源键前缀：** `teaching_c06_recognition_snap_redo_recognition`（`_title` / `_body`）

**教学正文：**

点击一次“重做”，把刚恢复的原手绘重新变为同一标准直线。直线恢复、原手绘再次被替换后才完成；上方锚线仍保留。

**精确成功条件：**

接续本章真实 undo_recognition，用户一次有效 redo 恢复相同 R 的 ID/type=LINE/几何及笔迹属性，原 stroke_id segments 再次移除，A 不变。空重做、自动再识别、额外新画一条 LINE 或原手绘仍在均不完成。

#### recognition_snap.limits_info｜了解识别的适用范围

**类型：** 信息

**资源键前缀：** `teaching_c06_recognition_snap_limits_info`（`_title` / `_body`）

**教学正文：**

智能识别只支持普通笔，不是所有手写都能识别。约 650 ms 是笔尖停住的判定阈值，不保证实际响应延迟、压力效果或每一笔都定形；单纯抬笔不会触发识别。读完点击“下一步”。

**精确成功条件：**

用户在当前信息步骤阅读后点击现有 teaching_next 按钮明确确认；初始化、展示说明、业务事件、自动推进或跳过均不能替代确认。 本步只说明 _start_smart_hold 的 PEN/pen 限制与 SMART_HOLD_MS=650，不改变识别开关、笔型、图形或历史，也不要求硬件、压力测试或另画一笔。

#### recognition_snap.choose_line｜切换到直线工具

**类型：** 操作

**资源键前缀：** `teaching_c06_recognition_snap_choose_line`（`_title` / `_body`）

**教学正文：**

在系统展开的图形列表中直接点击“直线”，从普通笔切换到直线工具。下一步将用两个点击取端点，练习已支持的端点吸附。

**精确成功条件：**

系统仅展开真实图形列表，用户直接点击当前目标 shape_line 按钮；draw_state 从 PEN→SHAPE，shape_type=LINE、pending_points=[]、直线按钮选中；A/R 原有内容保持。只打开列表或仍为普通笔不完成，不自动换工具。

#### recognition_snap.snap_line｜把第二端吸到锚线右端

**类型：** 操作

**资源键前缀：** `teaching_c06_recognition_snap_snap_line`（`_title` / `_body`）

**教学正文：**

先在空白处点击第一端点 (240,340) 并抬起，再点击上方锚线右端附近，例如 (248,157)，最后抬起提交。新直线第二端应实际吸到 (240,150)；只画出普通线或没有吸附都不算完成，也不表示所有图形工具都自动吸附。

**精确成功条件：**

用户真实选择 LINE 后，第一点击落在空白 P=(240,340)，第二实际落点 Q 在锚线 A 的右端附近但不同于 B=(240,150)（例 Q=(248,157)，距离小于 LINE_SNAP_RADIUS=18）；snap_to_line_endpoint 实际将 Q→B。最后抬起和历史提交后新增 S：type=LINE、kind=poly、closed=False、points=[P,B]，pending_points=[]，selected_ids={S.id}。A/R 保持。无吸附、吸错端、落点本来就在 B、普通笔画线、DASHED_LINE、预览或只按下不完成；不能仅凭 shape_created 埋点判成功。

#### recognition_snap.midpoint｜生成中点辅助十字

**类型：** 操作

**资源键前缀：** `teaching_c06_recognition_snap_midpoint`（`_title` / `_body`）

**教学正文：**

保持刚创建的直线单独选中，点击选中面板“⋯”，再选择真实菜单项“中点标记”。线的中点应新增辅助十字，原直线保留；只打开或关闭菜单不算完成。

**精确成功条件：**

本步对象必须是 snap_line 新建的 S，恰好单选 S；用户打开真实 btn_more/QMenu 并选 op_midpoint（实际标签“中点标记”），执行 midpoint。实际新增两个不同 ID 的 LINE 辅助对象构成十字：在示例端点下中点 M=(240,245)，线段 (233,245)→(247,245) 与 (240,238)→(240,252)，closed=False；S ID/端点/类型保留，A/R 保留，selected_ids 仍为 {S.id}。菜单打开/关闭、空操作、别的形状、无新增或替换 S 不完成。

#### recognition_snap.perp_bisector｜新增垂直平分线

**类型：** 操作

**资源键前缀：** `teaching_c06_recognition_snap_perp_bisector`（`_title` / `_body`）

**教学正文：**

重新打开选中面板“⋯”，选择“垂直平分线”。软件应实际新增一条经过当前直线中点、与原线垂直的辅助线；原直线和中点十字保留。只打开菜单或无效操作不算完成。

**精确成功条件：**

仍恰好单选原 S，用户重新打开 btn_more/QMenu 并选 op_perp_bisector，实际新增唯一辅助 DASHED_LINE 对象，经过 S 中点并与 S 垂直（点积为 0）。S 长 190 时 half=max(30,190×0.4)=76，辅助端点为 (164,245)/(316,245)（顺序可反），kind=poly、closed=False。S、中点两条辅助 LINE、A/R 的 ID/几何保持。关闭菜单、失败、空返回、重用既有线或错误对象不完成。

#### recognition_snap.construction_info｜了解更多构造的范围

**类型：** 信息

**资源键前缀：** `teaching_c06_recognition_snap_construction_info`（`_title` / `_body`）

**教学正文：**

“⋯”只对单个选中的平面图形开放，菜单依形状变化。三角形可作外接圆、内切圆、中线、高和中位线三角形；四边形有对角线等相应操作；圆有半径、直径、内接和外切正方形、内接等边三角形；椭圆有轴和焦点；角有角度调整与角平分线。这些是功能说明，本章只实操中点标记和垂直平分线，不教立体通用菜单。读完点击“下一步”。

**精确成功条件：**

用户在当前信息步骤阅读后点击现有 teaching_next 按钮明确确认；初始化、展示说明、业务事件、自动推进或跳过均不能替代确认。 以 SHAPE_OPS 和 open_more_menu 的 ANGLE 专用分支为说明边界，只阅读确认，不要求执行其他菜单项，不生成额外构造，不把立体、多选、空选择或无效构造视作可用/成功。

#### recognition_snap.done｜确认本章完成

**类型：** 信息

**资源键前缀：** `teaching_c06_recognition_snap_done`（`_title` / `_body`）

**教学正文：**

完成本章必做步骤后，点击“下一步”确认本章完成；不会自动换章或退出。你可在教学中心选择其他章节，或点击“退出教学”回到原工作。跳过不计完成。

**精确成功条件：**

此前本章全部必做操作与信息确认已实际完成，用户再点击本步 teaching_next，只确认本章；不自动换章或退出。用户另在教学中心换章或用 teaching_exit 返回原工作，跳过不计完成。

## 业务接入与最终验收责任

主线程负责课程/目录 JSON 的 55 步顺序、115 个键的接入、资源打包和八语言布局，准备四章私有合成素材，接好真实控件与模型操作结果，确保原工作/历史/设置隔离及退出恢复，并完成所有单元、离屏、应用、实屏或冻结包等计划内测试与最终验收。本写集不修改业务代码、i18n、JSON、素材、测试或计划状态，也不运行应用测试。

关键接入验收须逐步核对：第一 choose_line 从 ELLIPSE 的真实按钮选择；平面各点语义和最后抬起/提交；立体真实选择后拖动抬起；points 的 0→1→2→0→1→2→提交，取消不新增不删除；识别的普通笔限制、停住约 650 ms、标准 LINE 替换同一原手绘、一次撤销/一次重做；S 的实际落点 Q→指定锚端 B；两个菜单动作实际生成辅助对象且保留 S/A/R；11 个信息步骤真实点击 teaching_next 和四个 done 只确认本章。

不得把 track_event 的 shape_created/smart_shape/shape_op 等尝试埋点、菜单展示、计时器回调、纯按钮点击、总步数或“无异常”当作全部成功证明。须绑定当前步骤、私有练习、同一次真实用户操作和动作前后结果，过滤旧事件、空输出、无效输入与未收束的手势。椭圆对角点要求与当前实现的差异必须先由主线程核对并完成必要业务，再同步正文；本稿明确未声称该语义已经实现。


## 本次静态自查

2026-10-11 仅以 Python AST 解析源文本和文字比对核验，不导入应用、不执行应用测试或界面操作。115 个键的集合与顺序精确一致且无重复，115 个值均为字面量八字符串 tuple，共 920 条非空完整纯文本；无导入、HTML、未填占位符、控制字符或隐藏软连字符。八语言顺序为 zh/en/fr/es/de/ru/ko/ja。

四章步骤数为 22/10/10/13，共 55 步，ID/顺序与本稿逐步目录一致；55 个中文标题和正文逐一对应资源，并均有精确成功条件。11 个信息步骤使用各语言现有 teaching_next，四个 done 同时使用现有 teaching_exit；14 个图形选择按钮、普通笔、取消取点、识别开关的关/开、撤销/重做以及两项实操菜单均核对实际标签，日文确认标签是“次の手順”。

静态核对确认椭圆当前仍采用中心＋外缘尺寸定位点，包围框两对角语义的事实冲突已明确记录；没有为满足文字要求而宣称业务已改变。写稿期间 main.py 出现并行业务接入修改，本稿重新读取相关实现与标签核对，本次写操作始终只涉及 geometry_copy.py 和本文，不修改或撤回外部改动。

这些结果只证明本写集的资源结构、文本一致性、已读取控件标签与事实边界，不能代替真实业务、素材隔离、八语言布局或最终运行验收。业务接入、JSON、素材、所有测试与最终验收由主线程完成。
