# 主面板 UI 配色只读研究报告

- **资源调研截止日期：2026-10-09（Asia/Shanghai）；报告补全与复核：2026-10-10。**
- **推荐 A「石墨青绿」双主题**：保留青绿识别色，使用中性表面；优先改善小字选中对比度、工具栏图标状态色、控件必要边界，而非重做布局。
- **交付性质：研究与未来改动建议，未实施 UI 变更。** 本次配色研究唯一写入文件：`D:\MyScreenDraw\docs\ui-main-panel-color-research-2026-10-09.md`。
- **证据边界：没有看过实屏，没有截图、桌面抓取、原生输入、可见程序启动，也没有离屏渲染。** “现有颜色”指代码明确指定的颜色；Qt 未显式配置的 native/disabled 图标模式及最终像素仍待离屏检查。计算结果不是屏幕测色。

## 1. 范围、版本与只读取证

### 1.1 本地代码基线

主线程正在修改教学，故不读取工作树 `main.py` 作为配色审计依据；使用 `git show 5074c70:main.py`。完整提交为 `5074c70959dfb16cb2070c5df9f7cbc86926a950`，提交时间 **2026-10-08 21:21:10 +08:00**。

下文 `@5074c70:L…` 指该提交内容的 **1-based 行号，不是正在变化的工作树行号**，可重新用 `git show` 核查。实际相关 UI 模块已只读查看，并核实当前 Git blob 与基线一致：

| 绝对路径 | 已核实 Git blob |
|---|---|
| `D:\MyScreenDraw\toolbar_windows.py` | `633c74415b2892b58c88012eba9b586af34d9fcf` |
| `D:\MyScreenDraw\themed_controls.py` | `ca4d03c07881fe2734435b4a2abb56fb6b04360c` |
| `D:\MyScreenDraw\ui_icons.py` | `6ba45a86149947137ac18cad7239f69032c45330` |
| `D:\MyScreenDraw\tests\test_theme_contrast.py` | `120ef7521dbe871a74f990c386740c8a8f12b9ed` |

教学仅核对基线高亮色的兼容边界，不审查当前教学实现。已有和并行产生的工作树修改不回滚、不覆盖。

### 1.2 官方 skill 快照与随附本地数据

已调用 web 核实指定官方仓库和文档；web 未返回可引用正文，随后通过官方 GitHub HTTPS/API、raw 文本端点只读核实内容，并固定到同一提交：

- 仓库：`nextlevelbuilder/ui-ux-pro-max-skill`。
- 当次读取的 `main`：**`50d8a7de0900119855614541f15a1a616691eb33`**。
- GitHub committer 时间：**2026-10-09T05:06:45Z**，即上海时间 **2026-10-09 13:06:45**。
- 这是当次仓库快照，**不等于 skill 文件发布日期或发布版本；未核实 release/tag，不宣称“最新版本号”**。[S1]

“本地数据”指仓库随 skill 打包的 CSV；本次在内存中读取正文和解析记录，未安装 skill、未保存其他下载文件、未运行远端搜索/安装脚本、未改变全局配置。

| 官方仓库内资料 | 实际核实内容 | 固定 Git blob |
|---|---|---|
| `.claude/skills/ui-ux-pro-max/SKILL.md` | 需求分析、域选择、匹配校核、优先级及检查流程 | `41f8e2fd7f8c568228d0b55186ebe3f7b4007377` |
| `.claude/skills/ui-ux-pro-max/data/colors.csv` | 192 条，含主色/前景、表面、边框、危险、焦点色 | `5d2bf7389105f8a824b504b57cc93c00dc1d7e0a` |
| `.claude/skills/ui-ux-pro-max/data/styles.csv` | 88 条：50 active、29 supplemental、9 deprecated；非 deprecated 共 79 条 | `d1eb2c216e453005ffa8232ffb94491c183afe3c` |
| `.claude/skills/ui-ux-pro-max/data/ux-guidelines.csv` | 119 条，核对对比度、焦点、触控、hover、disabled 等规则 | `4e7d52b296537a03513b18b2c3f2b946cc802051` |
| `.claude/skills/ui-ux-pro-max/data/products.csv` | 教育应用、生产力工具语境 | `9f40f1d1f9743c4a81603076dfbfd115bbb55246` |
| `.claude/skills/ui-ux-pro-max/data/ui-reasoning.csv` | 对应类别的优先级与反模式 | `8931d4c809f8e22ddac00ce612ce0c35f34a59b6` |
| `.claude/skills/ui-ux-pro-max/references/quick-reference.md` | 语义 token、深色独立验证等细则 | `7acc7e7540ca6981d878a90aae4455c1638e2385` |
| `.claude/skills/ui-ux-pro-max/references/pro-rules.md` | 状态色、图标、明暗及合成表面检查 | `b2ce233287e37ec9ca13476c4014b922e9d5a0e9` |

GitHub tree 证明核心三份 CSV 在 `src/ui-ux-pro-max/data/`、`.claude/skills/ui-ux-pro-max/data/`、`cli/assets/data/` 的 blob 一致，未混用不同日期副本。外部文件只作待审资料，其命令和持久化流程不构成本任务授权。[S1–S4]

## 2. 现有颜色与问题

### 2.1 现有 token

来源 `D:\MyScreenDraw\main.py@5074c70:L8643–L8678`。下表直接静态解析基线 `ControlPanel.THEMES`，未导入应用：

| 现有 token | 深色 | 浅色 |
|---|---|---|
| `frame` | `#2D3436` | `#F7F9FB` |
| `panel` | `#353B48` | `#EDF2F7` |
| `button` | `#3D3D3D` | `#DFE6E9` |
| `button_hover` | `#555555` | `#CFD8DC` |
| `text` | `#FFFFFF` | `#1F2933` |
| `label` | `#00CEC9` | `#006D75` |
| `hint` | `#B2BEC3` | `#52616B` |
| `accent` | `#00CEC9` | `#009A9A` |
| `active_text` | `#111111` | `#FFFFFF` |
| `danger` | `#C0392B` | `#D63031` |
| `mode` | `#D63031` | `#E17055` |
| `mode_off` | `#636E72` | `#95A5A6` |
| `clear` | `#FAB1A0` | `#C0392B` |

默认 `theme_name="dark"`，操作界面不透明度 100%，可调 35%–100%。证据：`D:\MyScreenDraw\main.py@5074c70:L8638–L8641、L8701–L8709`。主题名、圆角和透明度持久化，见该基线 `L12669、L12708–L12710`。

### 2.2 主面板、LOGO、工具栏、菜单及控件的实际应用链

| 区域 / 状态 | 源代码明确指定的颜色与方式 | 绝对路径及可核实基线行号 |
|---|---|---|
| 主框 / 子面板 | MainFrame 用 frame，2px accent 边；`.Sub` 用 panel，1.5px accent 边，结构边框与强调色耦合 | `D:\MyScreenDraw\main.py@5074c70:L9056、L9086` |
| 普通 / hover / pressed / disabled / selected 按钮 | 普通 button/text；hover button_hover；pressed/checked/ActiveTool 为 accent/active_text；disabled 为 button/mode_off。这是主面板样式，不是分体工具栏完整规则 | `D:\MyScreenDraw\main.py@5074c70:L9060–L9074` |
| 实际分体工具栏 | 外框 frame/accent；普通 QToolButton button/text；hover button_hover；pressed **只改背景为 accent**；IconBtnActive 改为 accent/active_text；没有显式 QToolButton disabled/focus 规则 | `D:\MyScreenDraw\toolbar_windows.py@5074c70:L463–L499` |
| 工具栏图标 | 图标栅格源色取 text；同步投影 enabled 与 ActiveTool→IconBtnActive，不按选中态重绘图标前景。文字 QSS 色不等于图标源色 | `D:\MyScreenDraw\main.py@5074c70:L9293–L9324、L9393–L9406、L9420–L9463`；`D:\MyScreenDraw\ui_icons.py@5074c70:L492–L507` |
| 浮动 LOGO | 按钮 button、2px accent 边；hover button_hover、pressed accent。图标内部另绘 button 填充及 accent 的屏幕/笔迹图案，后者不是用户墨迹 | `D:\MyScreenDraw\toolbar_windows.py@5074c70:L163–L190`；`D:\MyScreenDraw\main.py@5074c70:L9164–L9185` |
| 程序品牌图标 | 程序/任务栏/托盘多尺寸 LOGO 固定 #5B8DEF，与浮动 LOGO 主题图标是不同路径；不应顺手替换品牌资源 | `D:\MyScreenDraw\ui_icons.py@5074c70:L510–L520` |
| 菜单 / Tooltip | panel/text，accent 边；菜单选中 accent/active_text，disabled mode_off；菜单项 padding 为 10px/24px | `D:\MyScreenDraw\main.py@5074c70:L9081–L9085` |
| 标签 / 标题 / 提示 | QLabel 为 label、11px；设置标题 accent、12px bold；说明 hint、10px；计时 accent、26px bold。并非全都是“大字” | `D:\MyScreenDraw\main.py@5074c70:L9075–L9080、L9125–L9128` |
| 下拉 / 输入 / spinbox / popup | panel/text，accent/active_text 选中，1px accent 边；disabled mode_off；popup 明确 outline:0，但不能只据此断言没有任何原生焦点提示 | `D:\MyScreenDraw\themed_controls.py@5074c70:L7–L42` |
| Windows 下拉弹出层 | QPalette 与 styled delegate 共同下发；Highlight=accent、HighlightedText=active_text，仅改主面板 QSS 不能覆盖所有 popup 路径 | `D:\MyScreenDraw\themed_controls.py@5074c70:L9–L16、L46–L53` |
| 滑块 / 滚动条 | groove 和滚动条 handle 用 button_hover，slider handle 用 accent；必要视觉线索须单独测量 | `D:\MyScreenDraw\main.py@5074c70:L9087–L9089、L9101–L9103` |
| 危险动作 / 模式镜像 | clear 文字用 clear；legacy exit 用 danger 底、硬编码白字；mode 按钮用 mode 或 mode_off 底与白字。disabled 前景与模式背景混用，分体栏不直接继承这些局部样式 | `D:\MyScreenDraw\main.py@5074c70:L9066、L9123–L9133、L11367–L11368` |

主界面默认统一图标式分体 UI；经典按钮仍是状态真相与镜像源，**不得为颜色改动删除或重新接线这条单向状态链**。见 `D:\MyScreenDraw\main.py@5074c70:L8704–L8707、L9137–L9140、L9420–L9463`。

### 2.3 优先问题：静态证据，不是实屏结论

1. **P1：浅色选中小字不够。** 白字与 #009A9A 只有 3.448922:1；12px 粗体标题 accent 对 panel 只有 3.062123:1。10–12px 不能因 bold 套用 3:1 大字阈值。[S5]
2. **P1：分体工具栏图标/pressed 前景脱节。** 深色白色源图标对青绿底 1.967779:1；浅色普通深色源图标对选中底 4.278168:1（超过非文字 3:1，但不足小字 4.5:1）；pressed 缺显式前景。它是源色配对风险，Qt 对 QIcon 模式的最终生成/变换尚未测量，不能说已经见到图标消失。[S5–S6]
3. **P2：accent 的多角色耦合。** 浅色 accent 对 button 边界仅 2.731704:1；输入、菜单等必须按不同相邻颜色检查。必要边界和装饰分隔线不应使用同一验收要求。[S6]
4. **P2：状态规则重复、不完整。** 主面板有 disabled，分体栏缺显式完整规则；mode_off 既作 disabled 文字又作可交互模式底色。浅色白字对 mode_off 是 2.557669:1，不能把可交互的模式状态当 disabled 豁免。
5. **P2：原有测试不是小字 AA 判据。** `D:\MyScreenDraw\tests\test_theme_contrast.py@5074c70:L8–L10、L24、L152–L181` 统一使用 3.0。转折点沿用 0.03928，本报告按现行规范用 0.04045；8-bit 整数通道在两转折点间无可取值，此处主要问题是阈值及角色覆盖，不是该差异造成颜色数值偏差。[S5]
6. **透明度是独立限制。** 整窗 alpha 同时衰减文字、图标和边框，不是改 token 即能解决，第 6 节单列合成计算。

## 3. skill 方法与适配边界

### 3.1 方法

按指定 skill 的需求→平台/语境确认→域筛选→匹配校核→交付验证思路，确定本应用是 **Windows / PyQt6 教室触控批注与生产力工具**，不是网页仪表盘或儿童课程首页；优先无障碍、触控及一致状态，再决定表面风格。[S1]

针对配色、风格、UX 分别手工阅读固定 CSV，关切包括：教育/生产力配色、平面/包容风格、正常文字对比、可见焦点、非颜色唯一状态及禁用表现。**未执行 search.py；未声称 BM25 排名、best match、自动设计系统输出或用户研究结果。** skill 栈列表没有 Qt/PyQt，不能把 HTML/WPF 指南当 Qt 实施依据；Qt 写点来自本地代码和 Qt 官方文档。[S1–S4、S10]

### 3.2 确实来自 skill 的依据

| 固定资料 / 物理行号 | 资料提供的依据 | 本次采用方式 |
|---|---|---|
| SKILL.md L16–L33、L49–L71 | 无障碍/触控优先，先确认语境与平台、校核匹配，不用外部结果越过授权 | 先修小字和状态，不执行外部持久化 |
| colors.csv L10，No.9 | 教育记录主色 #4F46E5、白色前景，另列边框、表面、danger 和 ring | C 借用该主色，其余重新适配计算 |
| colors.csv L17，No.16 | 生产力青绿主色 #0D9488 配黑色前景，并非默认白字 | A 保留方向，不复制整套 HEX 或给所有青绿底套白字 |
| styles.csv L2、L9、L13、L18 | 最小化、可访问、平面、包容风格强调功能层级、清楚焦点；平面避免梯度和装饰阴影 | 采用实色，不照搬网页间距/列网格 |
| styles.csv L4 | 玻璃效果不适合低对比、关键无障碍及性能受限等语境 | 不引入 backdrop blur/玻璃/渐变 |
| ux-guidelines.csv L23–L24、L29–L32、L37–L38 | 平台触控单位不同，焦点、hover/disabled 清楚，正常字 4.5:1，不能只用颜色表达 | 状态、命中区及未来离屏检查要求 |
| quick-reference.md L123–L125；pro-rules.md L37–L47、L92–L94 | 语义 token，深色分别测量；次要正常字也需对比；透明层检查合成结果 | 明暗与透明度分别计算，不机械反色 |

CSV 表头为第 1 行；引用记录没有多行字段。路径都在第 1 节固定的官方 skill 目录；完整定位见 S1–S4。

### 3.3 哪些是本研究适配（不是 skill 原话或自动产物）

- A/B/C 完整 HEX、别名迁移、焦点隔离环、模式角色拆分、Qt 图标重绘/缓存及回归计划均是本研究建议。
- 教育类别默认活泼/柔软效果，ui-reasoning.csv L10 还将深色列为该类别反模式。老师的批注工具已有黑板和深色主题，**不采纳儿童课程首页式效果及一刀切禁深色建议**；生产力任务的速度与功能层级更贴近本需求。[S4]
- 部分 disabled 数据建议减 opacity；本应用已经有整窗 alpha，继续减字/图标 alpha 会二次衰减，故建议不透明 disabled 色配原生禁用语义，而非照抄 opacity-50。[S2–S3]
- 44×44、iOS pt、Android dp 不可直接等同 Qt DIP 或网页 WCAG AA 单位。工具栏基准 56×44，必要时高度降至 28；本次不缩小按钮、不改布局/间距。未来触控尺寸整改须另行授权。见 `D:\MyScreenDraw\toolbar_windows.py@5074c70:L14–L20、L343–L359`；主面板触控常量见 `D:\MyScreenDraw\main.py@5074c70:L330–L339`。[S2、S9]

## 4. 三套双主题 HEX token

共同边界：只调整 UI chrome、状态前景；不改用户 pen/marker/laser、预设、彩虹、白板内容或批注颜色点；不加渐变/玻璃，不大改布局或减少命中面积。

- **A 石墨青绿（推荐）**：保留青绿识别方向，中性表面减少所有边界都用饱和色的干扰，蓝色 focus 与教学黄区分，迁移最贴近现有主题。是否更舒适须用户视觉验收，不能从 HEX 推断实屏体验。
- **B 冷灰钢蓝**：偏蓝色工具外观，选中对比裕量更大，但对现有识别色改动更明显；并非声称实现某个 Windows 官方完整设计系统。
- **C 暖灰靛蓝**：借用官方教育数据靛蓝主色，暖灰实色面板；适合希望与蓝绿课件区分的用户。投影色偏与提示层级未验证。

`on_*` 是对应底色的前景；`disabled` 指禁用文字/图标，背景仍用 button；surface 对应旧 frame，panel 对应菜单/输入/子面板。透明度不编码在 HEX 中。

### 4.1 A 石墨青绿（推荐）

| token | 浅色 HEX | 深色 HEX |
|---|---|---|
| `surface` | `#F5F7FA` | `#20272F` |
| `panel` | `#FFFFFF` | `#28323D` |
| `button` | `#E8EEF3` | `#34414F` |
| `border` | `#647787` | `#A3B4C4` |
| `text` | `#17212B` | `#F5F7FA` |
| `muted` | `#4A5D6B` | `#C5D0DA` |
| `accent` | `#00746F` | `#5EEAD4` |
| `selected` | `#00746F` | `#5EEAD4` |
| `on_selected` | `#FFFFFF` | `#102A28` |
| `hover` | `#DAE6EC` | `#435365` |
| `disabled` | `#6B7A88` | `#93A4B4` |
| `focus` | `#1D4ED8` | `#93C5FD` |
| `danger` | `#B42318` | `#FFC1B8` |
| `on_danger` | `#FFFFFF` | `#3B0A06` |

### 4.2 B 冷灰钢蓝

| token | 浅色 HEX | 深色 HEX |
|---|---|---|
| `surface` | `#F4F7FB` | `#1B2533` |
| `panel` | `#FFFFFF` | `#253246` |
| `button` | `#E8EEF7` | `#31425A` |
| `border` | `#66788F` | `#A0B2CB` |
| `text` | `#17243A` | `#F5F8FD` |
| `muted` | `#4B5D75` | `#C9D5E5` |
| `accent` | `#2456A6` | `#93C5FD` |
| `selected` | `#2456A6` | `#93C5FD` |
| `on_selected` | `#FFFFFF` | `#102A4C` |
| `hover` | `#D7E4F5` | `#405574` |
| `disabled` | `#6A7A8F` | `#A0ACC0` |
| `focus` | `#6D28D9` | `#5EEAD4` |
| `danger` | `#B42318` | `#FFC1B8` |
| `on_danger` | `#FFFFFF` | `#3B0A06` |

### 4.3 C 暖灰靛蓝

| token | 浅色 HEX | 深色 HEX |
|---|---|---|
| `surface` | `#F7F5F0` | `#252420` |
| `panel` | `#FFFEFA` | `#302E29` |
| `button` | `#ECE9E2` | `#3C3933` |
| `border` | `#746F67` | `#ABA394` |
| `text` | `#28251F` | `#FAF7F0` |
| `muted` | `#5D574E` | `#D0C8BA` |
| `accent` | `#4F46E5` | `#C4B5FD` |
| `selected` | `#4F46E5` | `#C4B5FD` |
| `on_selected` | `#FFFFFF` | `#241B4B` |
| `hover` | `#E1DED6` | `#4B473F` |
| `disabled` | `#7A746A` | `#A89F90` |
| `focus` | `#006D75` | `#5EEAD4` |
| `danger` | `#B42318` | `#FFC1B8` |
| `on_danger` | `#FFFFFF` | `#3B0A06` |

`accent` 与 `selected` 目前取同色，但保持两个语义角色，未来不会迫使标题文字、选中底和所有边框共用一个用途。危险动作采用 danger/on_danger 配对，**深色危险底不能继续硬编码白字**。

## 5. 确定性对比度计算（默认不透明）

### 5.1 判据与计算定义

- 正常文字（含 10–12px 粗体和次要说明）使用 **4.5:1**；大型文字可使用 3:1，但需达到 18pt 或 14pt bold 等等效大小，不能仅凭加粗判为大字。计时器单独判断。此处以 WCAG 2.2 作设计基准，不声称完成 Qt 桌面应用的整套 WCAG 认证。[S5]
- 识别控件/选中态所必需的图形、边界按相邻颜色 **3:1**。并非所有装饰性 panel 边或 hover 色差都必须 3:1；若可见文字已充分标识普通按钮，其外框适用性要具体判断。inactive 控件有对比豁免，但本方案自行以 disabled 对 button 至少 3:1 为可读性目标，不把说明文字或可点击模式状态冒充 disabled。[S5–S6]
- 状态不能只有颜色；保留图标、文案、原生 enabled 状态及可访问名称。焦点可见属于 AA；2px 周长/状态 3:1 的 Focus Appearance 属 AAA，此报告的焦点环是设计目标，不把 AAA 条目混称 AA 强制要求。[S7–S8]
- 每个 #RRGGBB 通道归一化为 `s=c/255`：`s<=0.04045` 用 `s/12.92`，否则用 `((s+0.055)/1.055)^2.4`。相对亮度 `L=0.2126R+0.7152G+0.0722B`，比率 `(max(L1,L2)+0.05)/(min(L1,L2)+0.05)`。[S5]

本次只用标准库和 `python -B` 计算，未导入应用或 Qt，未启动监听器、网络更新或自动保存。判定使用未舍入 float64 值，表格显示三位小数；先验证黑/白为 21、同色为 1，不用四舍五入后的“3.000”放宽门槛。复算函数见第 10 节。

### 5.2 现有基线的关键配对

| 实际角色 / 配对 | 前景或边界 | 背景 / 相邻色 | 比率 | 解释 |
|---|---|---|---:|---|
| 浅色选中文字 | `#FFFFFF` | `#009A9A` | 3.449:1 | 小字低于 4.5 |
| 浅色设置标题 | `#009A9A` | `#EDF2F7` | 3.062:1 | 12px bold 仍按正常文字，低于 4.5 |
| 浅色强调字 / frame | `#009A9A` | `#F7F9FB` | 3.268:1 | 小字低于 4.5；大型计时字另判 |
| 深色正文 / panel | `#FFFFFF` | `#353B48` | 11.227:1 | 正文充分 |
| 深色选中文字 | `#111111` | `#00CEC9` | 9.596:1 | 选中文字充分 |
| 深色选中 / pressed 图标源色 | `#FFFFFF` | `#00CEC9` | 1.968:1 | 低于必要图标的 3；最终 Qt 模式像素未检查 |
| 浅色 pressed 文字 / 图标源色 | `#1F2933` | `#009A9A` | 4.278:1 | 小字低于 4.5；非文字已超过 3 |
| 浅色边界 / button | `#009A9A` | `#DFE6E9` | 2.732:1 | 若该边界是必要视觉线索则低于 3 |
| 浅色 mode 镜像白字 | `#FFFFFF` | `#E17055` | 3.158:1 | 小字低于 4.5；不是分体栏 active_text |
| 浅色 mode_off 镜像白字 | `#FFFFFF` | `#95A5A6` | 2.558:1 | 可交互模式状态不能套 inactive 豁免 |
| 浅色退出白字 | `#FFFFFF` | `#D63031` | 4.854:1 | 超过 4.5 |
| 深色 disabled / button | `#636E72` | `#3D3D3D` | 2.071:1 | 2 左右；属 inactive 豁免，但不便辨认 |
| 浅色 disabled / button | `#95A5A6` | `#DFE6E9` | 2.026:1 | 2 左右；属 inactive 豁免，但不便辨认 |

配对的使用位置见第 2.2 节；图标数值是未应用 Qt 模式变换的源色，而非实屏像素。菜单/正文通常已很清楚，因此不建议全局反色或整体加亮。

### 5.3 三套明暗主题的文字、选中与边界

“普通面集合” = surface/panel/button/hover。文字与 muted 取该集合最小值；border 也取集合最小值；selected 对 button/hover 检查是必要选中填充相对未选中的状态区分。本次这组数值全部在 **alpha=1、实色、不叠加桌面** 条件下计算。

| 方案 | text 最小 | muted 最小 | on_selected / selected | selected / button | selected / hover | border 最小 |
|---|---:|---:|---:|---:|---:|---:|
| A 浅色 | 12.811:1 | 5.380:1 | 5.634:1 | 4.817:1 | 4.429:1 | 3.644:1 |
| A 深色 | 7.345:1 | 5.034:1 | 10.258:1 | 7.045:1 | 5.329:1 | 3.710:1 |
| B 浅色 | 12.079:1 | 5.223:1 | 7.102:1 | 6.089:1 | 5.515:1 | 3.508:1 |
| B 深色 | 7.123:1 | 5.103:1 | 7.990:1 | 5.660:1 | 4.205:1 | 3.511:1 |
| C 浅色 | 11.364:1 | 5.316:1 | 6.288:1 | 5.186:1 | 4.677:1 | 3.708:1 |
| C 深色 | 8.638:1 | 5.568:1 | 8.531:1 | 6.232:1 | 5.006:1 | 3.696:1 |

### 5.4 焦点、危险和禁用角色

以下 focus 的最小值仅针对普通面集合，**不包含 selected**。danger 文字也按普通面集合取最小值；危险填充另配 on_danger。

| 方案 | focus / 普通面最小 | danger 文字最小 | on_danger / danger | disabled / button |
|---|---:|---:|---:|---:|
| A 浅色 | 5.269:1 | 5.169:1 | 6.574:1 | 3.769:1 |
| A 深色 | 4.372:1 | 5.095:1 | 11.016:1 | 4.074:1 |
| B 浅色 | 5.517:1 | 5.105:1 | 6.574:1 | 3.756:1 |
| B 深色 | 5.126:1 | 4.900:1 | 11.016:1 | 4.450:1 |
| C 浅色 | 4.535:1 | 4.890:1 | 6.574:1 | 3.820:1 |
| C 深色 | 6.247:1 | 5.973:1 | 11.016:1 | 4.398:1 |

**不隐瞒焦点例外：** A 的 focus 直接贴 selected 时，浅色为 1.190:1、深色为 1.219:1，不能声称直接接触也达到 3:1。建议使用 **selected → 1 DIP surface 隔离带 → 2 DIP focus 环**：先以 surface 分隔，再检验两条接触边；selected/surface 分别为 5.249:1、10.193:1，focus/surface 分别为 6.244:1、8.362:1。该做法是本研究适配，不是已经实现的焦点样式。应以 paint-only/既有边框槽实现，不能增加 layout padding、挤掉图标或减少触控面积。[S6、S8]

普通 hover 与 button 的低幅色差不承担唯一的选中/焦点提示，不将两者色差 3:1 当普遍 WCAG 要求；实际按下和选中采用 selected/on_selected，触控不依赖 hover。selected:hover 应保持 selected，不落回普通 hover 底；disabled 应覆盖 hover/pressed，禁止误显可点击状态。[S2、S6–S8]



## 6. 整窗透明度：不能用更好的 HEX 掩盖合成限制

### 6.1 实际机制与设置兼容

基线 `D:\MyScreenDraw\main.py@5074c70:L8640–L8641、L12355–L12384` 将界面透明度限定在 **35–100%**，默认 100%；`apply_window_opacity()` 对 `opacity_targets()` 使用 `setWindowOpacity()`，不是只给底色加 alpha。画布不在该操作界面透明度目标中，不能为了面板主题把用户墨迹一起变淡。Qt 文档对 windowOpacity 的 0–1 含义、平台支持及更新时机有明确说明；本次不改变机制。[S10]

因此，桌面背景不仅混入面板底，也混入文字、图标与边框：

```text
最终前景 = alpha × 前景色 + (1 − alpha) × 桌面背景
最终面色 = alpha × 面色   + (1 − alpha) × 桌面背景
```

这是**归一化 sRGB 通道直接线性插值的简化合成模型**，随后按第 5.1 节转换亮度求对比。它不模拟 Windows 色彩管理、抗锯齿、8-bit alpha 量化或投影机，也没有测量任何桌面。不能只把背景混合、仍假定文字完全不透明。

### 6.2 A 方案的示例合成结果

每格是白色、黑色、`#808080` 三种**同一像素位置、均匀桌面底色**下的最小比率；文字、muted、border 均与 button 配对。**不是所有真实桌面、所有控件底色的最坏值保证。**

| 整窗 alpha | 浅色 text/button | 浅色 muted/button | 浅色 on_selected/selected | 浅色 border/button | 深色 text/button | 深色 muted/button | 深色 on_selected/selected | 深色 border/button |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 100% | 13.931:1 | 5.850:1 | 5.634:1 | 3.963:1 | 9.711:1 | 6.654:1 | 10.258:1 | 4.905:1 |
| 90% | 10.475:1 | 4.640:1 | 4.637:1 | 3.323:1 | 7.253:1 | 5.179:1 | 7.819:1 | 3.961:1 |
| 80% | 7.533:1 | 3.724:1 | 3.821:1 | 2.814:1 | 5.445:1 | 4.048:1 | 5.777:1 | 3.207:1 |
| 60% | 3.967:1 | 2.499:1 | 2.623:1 | 2.074:1 | 3.223:1 | 2.592:1 | 3.249:1 | 2.193:1 |
| 35% | 2.036:1 | 1.631:1 | 1.700:1 | 1.485:1 | 1.855:1 | 1.638:1 | 1.813:1 | 1.494:1 |

结论：**A 不透明状态的配色计算通过，不代表低透明度也通过。** 80% 的示例已使多项小字/必要边界不足；35% 即使换色仍有明显风险。90% 只在所列配对与三种底色下有余量，不能把它宣称为通用最低可用值。

建议保持默认 100%，保留用户已有 35–100% 设置与配置格式；不静默把旧设置改回 100%，不把控制条或某些文字强制改成不透明以造成设置语义突变。若日后需要“高可读性模式”或单独的背景 alpha，必须作为**另行批准的行为设计**，不混进本次 token-only 配色优化。

## 7. 最小改动方案：仅供审核，不在本轮执行

### 7.1 颜色角色映射

保留 `light` / `dark` 主题标识以及旧配置兼容性。先由统一主题工厂生成语义角色和旧键别名，而不是把所有样式表一次性改名。

| 旧键/使用路径 | 未来建议角色 | 注意点 |
|---|---|---|
| `frame` | `surface` | 只改 UI chrome；不是白板或画布颜色 |
| `panel` | `panel` | 输入、菜单、子面板使用同一受测表面 |
| `button` / `button_hover` | `button` / `hover` | hover 不覆盖选中或禁用状态 |
| `text` / `hint` | `text` / `muted` | 小字仍按 4.5；不通过减 alpha 来制造层级 |
| `accent` 作为标题文字 | `accent` | 不再兼作所有装饰边界 |
| `accent` / `active_text` 作为选中配对 | `selected` / `on_selected` | QSS、QPalette 与图标状态都用同一配对 |
| 输入/控件必要边界 | `border` | 保留既有边框尺寸和命中区，不扩大 padding |
| `mode_off` 作为禁用前景 | `disabled` | 和“模式未开启但仍可点击”分开；原生 enabled 语义保持 |
| 可交互的 `mode` / `mode_off` | 普通或 selected/on_selected + 原有模式文案 | 不再硬编码白字配任意 mode_off 底 |
| `danger` 填充动作 | `danger` / `on_danger` | 深色危险填充必须使用配套深色前景；clear 的确认流程不变 |
| 焦点指示 | `focus` + surface 隔离带 | 第 5.4 节例外必须保留；focus/selected 不能直接套 3:1 结论 |

不要仅改 `ControlPanel.THEMES`：分体工具栏、菜单 popup 的 palette/delegate、经典状态镜像、图标像素都需要同步核查，否则文字颜色与图标颜色仍可能脱节。

### 7.2 拟议写入范围

仅在获得配色实施批准后，考虑以下小范围改动：

1. `D:\MyScreenDraw\main.py`：主题角色/兼容别名、局部状态样式、选中/禁用/pressed 图标前景同步。**保留 BOM**，不改业务按钮连接或教学语义 ID。
2. `D:\MyScreenDraw\toolbar_windows.py`：普通/hover/pressed/checked/disabled/focus 的状态规则；延续原布局和尺寸。
3. `D:\MyScreenDraw\themed_controls.py`：QPalette Highlight/HighlightedText 与 popup delegate 的对应前景；不删除现有 Windows 兼容路径。
4. 必要时 `D:\MyScreenDraw\ui_icons.py`：按 theme、语义前景、图标大小/DPR、状态缓存已有 glyph；不更换图标形状、笔颜色点或品牌多尺寸资源。
5. `D:\MyScreenDraw\tests\test_theme_contrast.py` 和新增定向状态测试：测试阈值按真实角色区分，而非把所有内容统一按 3:1。

现有选中/禁用投影应仍由经典按钮状态单向决定图标按钮。图标不在心跳中无条件重生成；可按状态变化失效缓存，不为配色增加绘图/热键/自动保存的工作量。

### 7.3 教学与用户内容兼容

- 保留 `D:\MyScreenDraw\teaching\widgets.py@5074c70` 的教学高亮 `#F5B700` 作为独立教学提示，不把普通工具栏焦点也改成黄环。
- 黄环在任意白板/桌面上**没有固定对比保证**；需要时增加双层中性边界，应另补离屏边界测算，不能声称黄色本身对所有画布都足够。
- 不改变目标控件 geometry、按钮对象、注册器 ID、窗口归属、置顶顺序、输入屏障或透明穿透；否则颜色重构可能破坏课程定位。
- 不改教学正文中的颜色选择动作，不改笔/荧光笔/激光笔的用户颜色、工具预设、彩虹笔、白板背景和文档序列化。
- 不把教学控制条主题化、课程图片生成或布局升级附带进来；这些不是用户此次配色研究的实施授权。

## 8. 后续验证门槛与顺序

这些是**拟议测试，不是本次已经执行的测试**。任何屏幕/硬件验收仍受用户“不实屏”限制。

### 8.1 确定性与离屏测试

| 检查 | 预期证据 |
|---|---|
| 不透明文字和选中前景 | 两主题 text/muted 对所有实际表面 ≥4.5；选中文字/菜单/tooltip 同样测试 |
| 必要图标/边界/滑块 | 按实际相邻色和状态测试 ≥3；装饰边不混充必要边界 |
| Qt 图标状态 | 离屏检查 QIcon Normal/Active/Selected/Disabled × On/Off、pressed QSS 与源图像前景；不以 QSS 的 color 代替图标结论 |
| 焦点 | plain 和 selected 状态均可见；双层隔离环按实际接触边计算；不缩小点击区 |
| Windows styled popup | 在离屏可覆盖的 palette/delegate 路径验证选中底/字；原生差异单列未验收 |
| 配置兼容 | 旧主题名、opacity/radius/竖横栏/折叠标识加载不变；颜色不触发笔工具参数改变 |
| 多语言与缩放 | 八语言、长文本、100/125/150/200% 的逻辑尺寸和图标 DPR 检查；不是物理 DPI/投影验收 |
| 教学兼容 | 目标定位、菜单展开、暂停/恢复、完成/退出、高亮不得进导出图；不增删教学记录 |
| 性能 | 切换主题只触发必要缓存失效；连续书写的真实业务路径不增全量扫描或每笔 QIcon 重绘 |

测试必须使用 `QT_QPA_PLATFORM=offscreen`、`MYSCREENDRAW_NO_KEYBOARD=1`、`PYNPUT_BACKEND=dummy`，并按文件明确选取。离屏渲染仅是可选的未来检查；本次报告没有生成位图、没有桌面截图、没有真实点击/拖拽/笔触注入。

### 8.2 实施阶段拆分

- **P0 审核**：用户选 A/B/C 或提出调整；本报告不等于批准实施。
- **P1 token 与前景**：统一明暗语义色，修小字/菜单/selected/危险配对；先保持全部几何不变。
- **P2 状态闭环**：修图标状态、disabled、focus、popup，跑主题/触控/菜单/穿透/教学离屏回归。
- **P3 单独视觉验收**：仅在用户重新授权后进行；没授权就保留限制，不以静态比率或离屏结果替代实屏结论。

## 9. 结论与官方来源

**建议选择 A「石墨青绿」作为未来最小改动方向。** 当前最值得解决的是浅色选中小字、分体图标选中/pressed 前景及必要边界；中性表面能与单一青绿强调角色形成清楚层级。这个判断是本研究的设计建议，不是用户研究或已见实屏的结论。

本次已完成代码静态审计、固定官方资料核实、三套明暗色板、对比度复算、透明度限制、兼容写点和测试计划。没有实施新色板，不改布局，不动用户墨迹；后续须按本报告的门槛实施并验证。

### 官方来源定位

仓库相关 S1–S4 均固定到 `50d8a7de0900119855614541f15a1a616691eb33`；2026-10-10 主线程独立只读复核第 1.2 节的八个 blob，全部一致。标准/Qt 文档是规则与 API 依据，不是本应用认证或本机 Qt 版本声明。

- **S1**：官方指定仓库 [SKILL.md 固定快照](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/50d8a7de0900119855614541f15a1a616691eb33/.claude/skills/ui-ux-pro-max/SKILL.md)，方法、语境/栈选择、优先级。
- **S2**：[colors.csv](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/50d8a7de0900119855614541f15a1a616691eb33/.claude/skills/ui-ux-pro-max/data/colors.csv) 与 [quick-reference.md](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/50d8a7de0900119855614541f15a1a616691eb33/.claude/skills/ui-ux-pro-max/references/quick-reference.md)，语义角色与可访问配对。
- **S3**：[styles.csv](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/50d8a7de0900119855614541f15a1a616691eb33/.claude/skills/ui-ux-pro-max/data/styles.csv)、[ux-guidelines.csv](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/50d8a7de0900119855614541f15a1a616691eb33/.claude/skills/ui-ux-pro-max/data/ux-guidelines.csv) 与 [pro-rules.md](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/50d8a7de0900119855614541f15a1a616691eb33/.claude/skills/ui-ux-pro-max/references/pro-rules.md)，风格边界、状态/触控规则及交付检查。
- **S4**：[products.csv](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/50d8a7de0900119855614541f15a1a616691eb33/.claude/skills/ui-ux-pro-max/data/products.csv) 与 [ui-reasoning.csv](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/50d8a7de0900119855614541f15a1a616691eb33/.claude/skills/ui-ux-pro-max/data/ui-reasoning.csv)，类别语境；未照搬其中不适合现有桌面工具的反模式。
- **S5**：W3C [SC 1.4.3 Contrast (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) 与 [WCAG 2.2 定义](https://www.w3.org/TR/WCAG22/#dfn-relative-luminance)，正常/大字阈值、亮度公式及 inactive 例外。
- **S6**：W3C [SC 1.4.11 Non-text Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)，必要图形/边界、相邻颜色、hover 与 inactive 边界。
- **S7**：W3C [SC 2.4.7 Focus Visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html)，AA 可见焦点。
- **S8**：W3C [SC 2.4.13 Focus Appearance](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance.html)，AAA 面积/状态对比目标；不混称 AA。
- **S9**：W3C [SC 2.5.8 Target Size (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)，CSS px 及间距/例外；不把网页单位直接等同 Qt DIP。
- **S10**：Qt 官方 [QWidget::windowOpacity](https://doc.qt.io/qt-6/qwidget.html#windowOpacity-prop)、[Style Sheets Reference](https://doc.qt.io/qt-6/stylesheet-reference.html) 与 [QIcon modes/states](https://doc.qt.io/qt-6/qicon.html)，Qt opacity、伪状态、图标模式/状态机制；具体写点以本地代码为准。

## 10. 附录：纯标准库复算代码

以下代码读取本报告中的表 4，不导入应用、不导入 Qt、不联网，不改变任何文件；路径请保持为绝对路径。`composite_contrast` 只是第 6 节明确的简化模型。

```python
from pathlib import Path
import re

report = Path(r'D:\MyScreenDraw\docs\ui-main-panel-color-research-2026-10-09.md').read_text(encoding='utf-8')

def rgb(hex_color):
    return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (1, 3, 5))

def luminance(channels):
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
              for v in channels]
    return sum(w * v for w, v in zip((0.2126, 0.7152, 0.0722), linear))

def contrast(foreground, background):
    low, high = sorted((luminance(foreground), luminance(background)))
    return (high + 0.05) / (low + 0.05)

def mix(color, desktop, alpha):
    return tuple(alpha * c + (1 - alpha) * d for c, d in zip(color, desktop))

def composite_contrast(palette, foreground, background, alpha):
    return min(contrast(mix(rgb(palette[foreground]), rgb(desktop), alpha),
                        mix(rgb(palette[background]), rgb(desktop), alpha))
               for desktop in ('#000000', '#808080', '#FFFFFF'))

assert contrast(rgb('#FFFFFF'), rgb('#000000')) == 21.0
assert contrast(rgb('#808080'), rgb('#808080')) == 1.0
palettes = {}
for index, name in enumerate('ABC', 1):
    block = report.split(f'### 4.{index} {name} ', 1)[1].split('###', 1)[0].split('## 5', 1)[0]
    rows = re.findall(r'^\| `([a-z_]+)` \| `(#\w{6})` \| `(#\w{6})` \|', block, re.M)
    assert len(rows) == 14
    palettes[name] = {
        mode: {role: row[1 if mode == 'light' else 2] for row in rows for role in [row[0]]}
        for mode in ('light', 'dark')
    }
    for mode, p in palettes[name].items():
        backgrounds = [p[key] for key in ('surface', 'panel', 'button', 'hover')]
        values = [min(contrast(rgb(p[key]), rgb(bg)) for bg in backgrounds)
                  for key in ('text', 'muted')]
        values += [contrast(rgb(p['on_selected']), rgb(p['selected'])),
                   contrast(rgb(p['selected']), rgb(p['button'])),
                   contrast(rgb(p['selected']), rgb(p['hover'])),
                   min(contrast(rgb(p['border']), rgb(bg)) for bg in backgrounds)]
        assert values[0] >= 4.5 and values[1] >= 4.5 and values[2] >= 4.5
        assert all(value >= 3.0 for value in values[3:])
        print(name, mode, *(f'{value:.3f}:1' for value in values))

for alpha in (1.0, 0.9, 0.8, 0.6, 0.35):
    values = [composite_contrast(p, foreground, background, alpha)
              for p in palettes['A'].values()
              for foreground, background in (('text', 'button'), ('muted', 'button'),
                                              ('on_selected', 'selected'), ('border', 'button'))]
    print(alpha, *(f'{value:.3f}:1' for value in values))
```

使用未舍入数值判定，三位小数仅用于展示。纯数值通过后仍需第 8 节的实际状态检查；禁止从本附录推导“实屏已验收”或“投影/触屏没有问题”。
