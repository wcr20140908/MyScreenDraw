# MyScreenDraw 完整软件使用教学系统实施计划

日期：2026-10-07（Asia/Shanghai）
状态：**用户已批准，实施进行中；未完成的任务不得声称已实现或测试通过。**
研究基线：`9e9feed574c7e0f20ac50664ddb429725d0451ee`。
配套证据：`docs/classisland-teaching-research-2026-10-07.md`。

## 一、目标、边界和审核默认值

### 1.1 最终交付

- **工具 → 教学**入口，首次遇到该系统的用户有可跳过的欢迎教学；6.1.0 升级用户也包含在内。
- 完整教学中心：课程/章节列表、说明、真实进度、继续学习、从头重播、单章重播、停止、清除进度、关闭首次功能提示。
- 教学引擎：目标控件定位、高亮与说明气泡、受控输入屏障、真实操作判定、分支、前后导航、暂停、跳过、退出和异常恢复。
- 独立真实练习：使用同一可执行程序和实际功能，练习数据隔离，结束回到原工作。
- 13 门课程、46 个章节，覆盖当前软件功能；首轮核心入门 6 章、24 步。
- 所有教学 UI 与课程说明遵循现有八语言 `tr/trf` 约定；课程与素材随包，完全离线可用。
- 单元、离屏集成、原生实屏和冻结包测试，逐项输出可复核报告。

### 1.2 不做的内容

本轮不做可视化课程编辑器、Lua/Python 任意脚本、用户导入课程、云端课程下载、同步账户、课堂录制、考勤分析，也不重构与教学无关的笔迹/导出算法。参考 ClassIsland 的机制，不复制其代码、文案和图片。

### 1.3 已确认与供审核的默认值

已确认：完整教学、工具入口、首次欢迎、真实且独立的练习、JSON 维护。调研不使用子代理；用户于实施启动后允许最多同时 1 个子代理（含主代理共 2 路）。

以下三点是未收到答案后的建议默认值，而不是用户已经选定：

1. 首次只走核心入门，完整目录随时可用；不强迫一次学完所有课程。
2. 重要功能首次使用可显示一次**不抢焦点、不自动开课**的小提示；用户点击才进入练习，并可全局关闭。
3. 交付未发布验收包，不自动发布 6.2.0；6.1.0 标签和资产保持不变。

## 二、用户流程与状态规则

### 2.1 正常首次启动

```text
普通启动
  → 原有初始化/更新启动确认
  → --restore 或自动保存恢复流程结束
  → 主窗口布局与生命周期就绪
  → 无活动模态框、手势、输入法组字、文字编辑及后台文件操作
  → 可跳过的欢迎
      ├─ 开始学习：先持久化 accepted，再启动核心入门
      ├─ 稍后学习：记为 skipped，说明工具 → 教学入口
      └─ 关闭欢迎：记为 dismissed，不反复弹出
```

- 自动启动的欢迎不能抢正在输入的焦点；安全条件不满足就排队，主软件照常工作。
- 手动教学入口同样检查安全条件；显示“请先结束当前编辑/文件操作”的非抢焦点提示，不替人提交或取消。
- `--smoke`、`--smoke-ui`、练习子进程和自动化测试不会计入欢迎，也不启动首次提示。
- 欢迎决定与课程完成分开记录。用户接受后即使启动练习失败或中断，下一次也不重复欢迎；中心提供重新开始/继续。
- 文案修订或后续版本升级不重置欢迎。只有显式重置且勾选“下次启动显示欢迎”才重置。
- 状态文件不可写时不自动弹欢迎；教学中心提示进度不能保存，允许在可写临时根进行手动练习。损坏/未知高版本状态不静默覆盖、不循环弹窗。

### 2.2 教学中心

按“入门、绘图与内容、文件与工具”三组展示 C01–C13，支持关键字搜索与已完成/未完成筛选。每门课程显示章节完成数，单章标记**未开始、进行中、完成、跳过**；硬件/能力不可用的条件步骤以明确说明分支呈现，不能把说明当作该硬件已实测。

- “继续”从最近未完成章节的开始处重建练习，不跨程序重启恢复到一个环境未知的句子。
- 在同一次练习中暂停/恢复保留当前步骤和私有文档。
- 单章重播不会自动清除之前的完成历史；只有重置进度才清除。
- 同时只允许一个活动练习。再次启动课程时先确认结束当前练习，再建立新会话。
- 练习进程中的“工具 → 教学”也可打开中心，显示当前课程；切换章节必须清理旧步骤并重新建立章节素材，不创建第三个进程。

### 2.3 步骤按钮与完成含义

- 信息步骤：下一步表示已阅读；不能替代实操步骤。
- 实操步骤：显示“等待你完成……”；只有指定业务结果符合谓词才前进。
- 上一步：回到教学说明和目标。需重做的步骤重新布置私有素材；不伪装成对原文档的撤销。
- “跳过本章”和“退出教学”始终可达。跳过写 `skipped`，退出写 `in_progress`，均不增加完成数。
- 显式教学取消操作的步骤可以等待 `cancelled`；保存/导出成功步骤只接受 `success`，取消或部分失败绝不完成。
- 暂停时取消输入屏障并收起说明；恢复后重新解析真实目标和业务状态，旧异步事件不补触发。

## 三、完整课程目录

章节 ID 为 `cXX.<slug>`，稳定且与显示语言无关。下面是本轮完整范围，不只实现 C01。

| 课程 | 章节 ID 后缀（数量） | 内容与主要实操 |
|---|---|---|
| C01 核心入门 | `interface, ink, select, pages, files, finish`（6） | 24 步，见下表 |
| C02 笔与批注 | `styles, color_width, transient`（3） | 11 种笔型逐一认识/试写；颜色、粗细、预设；荧光与激光的临时效果 |
| C03 擦除和历史 | `erase, history_clear`（2） | 当前支持的橡皮模式/尺寸；撤销、重做、清空及不可回退边界说明 |
| C04 选择与编辑 | `select_move, transform, copy_delete`（3） | 选取、移动；缩放、旋转和控制柄；复制、删除及框选 |
| C05 白板与页面 | `board, add_switch, rename_delete, copy_position, reorder`（5） | 白/黑板与批注切换；加页和翻页；重命名/删除；四种复制插入位置与设置；拖动排序/缩略图 |
| C06 形状与构图 | `plane, solid, points, recognition_snap`（4） | 14 种形状的平面/立体部分；取点顺序、取消；停笔定形与当前支持的吸附/构造 |
| C07 文字与公式 | `edit, format, formula`（3） | 编辑/结束编辑/键盘和输入法；字号与文本框操作；公式、符号与导航 |
| C08 项目与恢复 | `save, open_guard, recovery, interval`（4） | 保存/另存为；打开项目时未保存选择；历史预览/恢复；自动保存间隔与过短成本 |
| C09 图片与 PDF | `image, pdf_pages`（2） | 私有示例图片导入、尺寸调整；示例 PDF 每页导入独立白板页 |
| C10 导出 | `formats, progress_cancel, result`（3） | PNG/PDF/SVG/EPS；逐页进度与取消；全成功/取消/部分失败结果的区别 |
| C11 测量辅助 | `instruments, calibration`（2） | 直尺、量角器、三角板及相应操作；屏幕标定，仅修改练习配置 |
| C12 工具箱 | `calculator, roster, timer, magnifier, spotlight`（5） | 计算器；虚构名单点名；计时与响铃；放大镜；聚光灯 |
| C13 界面与设置 | `layout_theme, monitor_audio, lifecycle, system`（4） | 横竖/折叠/主题/透明度；显示器与音量；后台/托盘/退出；更新与自启只讲解，不执行系统变更 |

每种笔型、形状和导出格式都有可定位的子步骤；不以一个总括说明代替全部操作。操作能力取自当前代码及已锁定依赖，不教软件没有的功能。

### 核心入门固定 24 步

| 章节 | 4 个步骤 |
|---|---|
| `c01.interface` | 确认“独立练习”标识与退出入口；选择批注；提交第一笔；切换鼠标穿透再恢复批注 |
| `c01.ink` | 选择颜色；设置粗细；再画一笔观察变化；擦除已有笔迹 |
| `c01.select` | 撤销；重做；选择现有对象；移动并提交对象变化 |
| `c01.pages` | 进入白板；新增页面；返回上一页；再切回新页 |
| `c01.files` | 保存练习项目；重新打开刚保存项目；预览预置私有恢复历史；恢复所选示例版本 |
| `c01.finish` | PNG 导出成功；暂停/恢复教学并说明 F12/托盘路径；打开工具 → 教学查看后续课程再返回；完成确认、结束练习并回到原工作 |

取消导出练习若在本机瞬间完成，不误判为取消；提供重试、真实完成后的解释分支或跳过，状态记清楚。没有触屏/第二显示器时走对应说明分支，报告注明该硬件操作未验证。

### 素材要求

由项目自己生成/绘制：样例笔迹与形状、三页合法 PDF、图片、文本/公式、合法项目与自动保存历史、六个明确标注为虚构的练习名字。较长导出练习使用有界多页样例，不拿用户真实文件做素材。

课程中的每一个界面文案引用 `i18n.py` 的键；图片使用语言无关的示意，必要的图中文字也需本地化。课程/素材无网络 URL 加载，不包含用户数据或上游 ClassIsland 资产。

## 四、架构与明确接口

### 4.1 结构

```text
原进程
  教学中心 / TutorialStateStore / PracticeSession / 唯一托盘与全局热键
       │ QProcess + 用户级 QLocalServer/QLocalSocket
       │ 有界、带会话校验的 JSON 协议
       ▼
练习进程（同一 main.py / MyScreenDraw.exe）
  私有 RuntimePaths + 正常 Canvas/ControlPanel
  TutorialEngine + TargetRegistry + 教学控件
  私有配置、名单、日志、自动保存、导入素材和导出
```

引擎和目标解析在练习进程本地运行；不经 IPC 转发每次鼠标移动/笔迹，避免延迟。IPC 只承载启动、控制、章节状态和持久化确认。原进程是进度持久化的唯一写入者。

### 4.2 文件职责

| 文件 | 职责 |
|---|---|
| `runtime_paths.py`（新） | 不可变运行路径；正常与练习模式分离；校验私有根与真实资源路径 |
| `teaching/models.py`（新） | 课程/步骤/事件/运行态和进度记录；纯数据类型 |
| `teaching/catalog.py`（新） | 离线课程载入、结构与引用校验、条件/动作白名单 |
| `teaching/engine.py`（新） | 单一课程状态机、步骤 epoch、分支、暂停与真实事件判定 |
| `teaching/state.py`（新） | 原子进度保存、恢复/损坏/只读处理、版本迁移 |
| `teaching/events.py`（新） | 业务操作上下文与窄事件接口；无教程时低成本空操作 |
| `teaching/targets.py`（新） | 稳定语义 ID、当前控件弱引用、展开/滚动/重解析 |
| `teaching/widgets.py`（新） | 欢迎、中心、控制器、气泡、高亮和本程序内输入屏障 |
| `teaching/protocol.py`（新） | 有界帧编解码、协议版本、会话验证与 ACK |
| `teaching/practice.py`（新） | 父进程 PracticeSession、子进程入口、私有素材、退出与清理 |
| `main.py`（修改） | 工具入口、启动顺序、业务成功事件、数据边界、练习能力开关 |
| `app_lifecycle.py`（修改） | 可逆教学挂起/恢复、唯一热键/托盘路由、故障收尾 |
| `i18n.py`、`ui_icons.py`（修改） | 八语言教学文案和教学图标 |
| `assets/tutorials/catalog.json`、`courses/*.json`（新） | 三组课程索引和 13 个课程文件 |
| `assets/tutorials/images/`、`fixtures/`（新） | 项目自产图片及合成练习素材 |
| `MyScreenDraw.spec`、`tests/`、`docs/`（修改/新增） | 包含资源、测试、验收和使用/维护文档 |

在 `runtime_paths.py` 定义 RuntimeContext（路径与能力）并以可选关键字参数传入 `ControlPanel(runtime=None)` / `DrawingCanvas(panel, runtime=None)`，保持既有构造调用兼容。能力明确包含 ui_active、global_keyboard、tray、updates、autostart、usage_tracking；练习 ui_active 仅在 activate 后设为真；global_keyboard/tray/updates/autostart/usage_tracking 始终关闭。UI 心跳与私有自动保存可以在激活后启用，但不能在初始化时抢屏。

保持现有 `main.DATA_DIR` 等全局名字可被旧测试隔离补丁覆盖；新路径绑定在所有目录创建、日志、设置/名单载入之前完成。`APP_DIR` 仍是程序所在目录，资源使用冻结包真实资源根，不能把它改成练习根。

### 4.3 数据与函数契约

以下是计划中的接口，不是已经添加到生产代码：

```python
from dataclasses import dataclass
from typing import Literal, Mapping

Outcome = Literal['success', 'cancelled', 'failed', 'partial']
ChapterStatus = Literal['not_started', 'in_progress', 'completed', 'skipped']

@dataclass(frozen=True)
class OperationContext:
    session_id: str
    run_id: str
    step_epoch: int
    operation_id: str

@dataclass(frozen=True)
class TutorialEvent:
    context: OperationContext
    name: str
    outcome: Outcome
    details: Mapping[str, object]

# events.py
# begin_operation(name: str) -> OperationContext | None
# emit_result(context: OperationContext | None, name: str,
#             outcome: Outcome, details: Mapping[str, object]) -> None
# engine.py
# start(course_id: str, chapter_id: str) -> None
# consume(event: TutorialEvent) -> bool  # 是否接受并推进
# pause() -> None; resume() -> None; skip_chapter() -> None; stop() -> None
# targets.py
# register(target_id: str, resolver, reveal=None) -> None
# resolve(target_id: str) -> QWidget | None
# state.py
# set_welcome(decision: str) -> None
# record_chapter(chapter_id: str, status: ChapterStatus, compat_revision: int) -> None
# practice.py
# start(course_id: str, chapter_id: str) -> None
# request_pause(hidden: bool = False) -> None
# request_resume() -> None; request_stop(reason: str) -> None
```

异步操作必须在**开始时**捕获 `OperationContext`，完成时带回原上下文；不能在完成回调中读取当前步骤后制造一个新事件。步骤切换递增 epoch，重播递增 run_id；每个 operation_id 去重。事件还必须满足当前步骤预期名称、结果和 details 谓词。

### 4.4 课程结构与动作白名单

例：

```json
{
  "schema_version": 1,
  "id": "c08",
  "revision": 1,
  "compat_revision": 1,
  "title_key": "teaching_c08_title",
  "chapters": [{
    "id": "c08.save",
    "fixture": "project_basic",
    "steps": [{
      "id": "save_project",
      "title_key": "teaching_save_title",
      "body_key": "teaching_save_body",
      "target": "file.save",
      "input_policy": "target_only",
      "reveal": ["open_file_panel"],
      "wait": {"event": "project.saved", "outcome": "success"},
      "next": "save_as"
    }, {
      "id": "save_as",
      "title_key": "teaching_save_as_title",
      "body_key": "teaching_save_as_body",
      "target": "file.save_as",
      "input_policy": "target_only",
      "reveal": ["open_file_panel"],
      "wait": {"event": "project.saved", "outcome": "success",
               "equals": {"save_as": true}},
      "next": "end_chapter"
    }]
  }]
}
```

- `schema_version` 检查格式；`revision` 是内容版本；`compat_revision` 只有改变必做实操语义时递增。
- wait 支持单事件，或有序 sequence（例如先鼠标穿透再恢复批注），序列项仍为白名单事件/outcome/equals；允许 min_count 数量下限。sequence 必须按序匹配，其他无关事件不前进；跳步或更早上下文无效。步骤可给 allowed_targets 数组，当前序列阶段只放行对应控件及说明控制器。例如 c01.interface 最后一步依次放行 toolbar.mode 和 toolbar.pen，避免目标屏障挡住第二个必做动作。
- 显式 ID、引用和白名单；拒绝重复 ID、悬空跳转、无法抵达结束的闭环、未知字段/动作/事件、找不到的素材及语言键。
- `reveal` 只允许：展开工具栏、打开指定子菜单/设置分类/教学中心、显示页面列表、滚动指定 Qt 控件；不得伪造用户学习目标的成功。
- 素材准备只允许通过章节 fixture ID 建立私有示例。不得让 JSON 指定文件系统绝对路径、调用 shell、导入函数、反射类或执行任意表达式。
- 条件只允许已有能力：是否触控输入、显示器数量、PDF 能力、当前界面模式、工具/文档类型、章节进度；布尔比较和预先登记的枚举，不使用 `eval`。
- 控制动作只允许 previous/next/jump/end/pause/stop 及上述导航/素材能力。

### 4.5 稳定目标与高亮

语义 ID 示例：`toolbar.pen`、`toolbar.tools`、`toolbar.file`、`tools.teaching`、`file.save`、`canvas.ink`、`pages.add`、`selection.rotate`、`settings.autosave`。

- 当前基线 `set_ui_mode` 实际统一为图标主栏，隐藏旧按钮；通过 `icon_buttons` 解析当前可见/启用控件，不靠共享 `IconBtn` 名称或翻译文字，也不为了教学重新开放已废弃的 classic 界面。
- 目标未显示时执行受控 reveal；用 `QScrollArea.ensureWidgetVisible` 展开到可视区域，再计算全局矩形。
- 订阅宿主移动、尺寸、布局、显示/隐藏、滚动和屏幕变化，合并一次重定位；只在活动教程期间存在监听。
- 保留弱引用和销毁通知。目标丢失时暂停当前步骤；两秒内尝试重新解析，仍不存在就显示重试/跳章/退出，不永久遮住软件。
- 气泡与控制器限制在目标屏幕工作区，支持负坐标和 DPI。加入现有受管理的置顶顺序，不与 ClassIsland/其他程序反复争夺最顶层。
- `canvas` 步骤全部放行真实画布；信息步骤和 `target_only` 用本进程事件过滤器限制其他本程序控件，不建立覆盖整个桌面、阻挡其他软件的屏障。控制器、退出、当前目标的子控件与其实际弹出菜单始终可操作，多动作步骤按 allowed_targets/sequence 阶段放行，不能只允许第一颗按钮。
- 高亮/控制器是独立 UI，不通过文档画笔绘制；没有教程时不影响焦点、鼠标穿透、触摸、多点输入和导出。
- 原生文件对话框期间移除教学屏障并隐藏气泡，等待操作返回；不把 Windows 原生对话框控件当作 Qt 锚点。

### 4.6 进度存储

`DATA_DIR/tutorial-state.json`，父进程原子写临时文件并替换；文件中仅有教学 ID、状态与必要版本，没有真实文档或名单。

```json
{
  "schema_version": 1,
  "welcome": "accepted",
  "context_hints_enabled": true,
  "context_seen": ["file.export"],
  "chapters": {"c01.interface": {"status": "completed", "compat_revision": 1}},
  "last_started": {"course_id": "c01", "chapter_id": "c01.ink"}
}
```

欢迎枚举为 `unseen/accepted/skipped/dismissed`。完成仅统计走完适用分支全部必做步骤的章节；保存失败显示一次非阻断警告并保留内存进度。损坏文件保留诊断副本，在可写时建立欢迎已关闭的安全空状态；未知高版本进入只读模式，禁止覆盖。新增课程只标为新内容，不重新欢迎。兼容版本改变时只把相关章节标为需要复习，保留之前完成历史。

## 五、练习进程的隔离和生命周期

### 5.1 启动与资源

1. 原进程等待安全时点，并确保已有自动保存工作取得的快照/写盘收尾，不把未保存原文档当作练习素材。
2. 在可写临时目录建立 `MyScreenDraw/teaching/<install_id>/<session_uuid>/`，保存拥有者标记、会话 UUID、随机 nonce、父进程信息和安全配置副本。
3. 只复制显示设置：主题、语言、方向、大小/透明度、可用显示器偏好和允许的输入偏好。不复制真实名单、最近文件、更新状态、自启设置、遥测或旧自动保存。
4. 创建用户级 `QLocalServer`，启动一个 `QProcess`。源码运行以解释器加 `main.py` 参数启动；冻结运行以 `sys.executable` 启动；不通过 shell 拼接命令。
5. 子进程先解析独立 `--teaching-practice` 参数，验证根标记并完成握手，再建立日志、数据目录、面板和画布。握手失败不能回退为普通启动、写正常数据或展示正常欢迎。初始化全程保持隐藏：当前 `DrawingCanvas.__init__` 会直接 show，load_settings/set_ui_mode 会 show 分体栏，必须在这些实际调用点加 ui_active 能力守卫，不能等 ready 后再 hide。
6. 初始化期父界面仍可正常使用。子进程发 ready 后保持隐藏、不启动 UI/自动保存回调；父进程重新检查安全条件，完成可逆挂起后发送 activate，子进程才显示练习并回 activated。10 秒无 ready 则结束子进程、原工作不变；发送 activate 后 5 秒无确认则按收尾规则终止子进程并恢复原工作。等待用户结束编辑不算 ready 超时，期间可以取消待开始的练习。

冻结资源由 `MyScreenDraw.spec` 显式打包，按真实资源根载入，不根据当前工作目录查找；同一子进程必须从中文/空格路径和任意工作目录成功启动。

### 5.2 通信协议

- 协议版本固定为 1。每帧：4 字节大端长度 + UTF-8 JSON，长度不超过 64 KiB；不接受无限缓存或不受限嵌套。
- 每条消息含 `protocol_version/session_id/nonce/message_id/type`；每个消息 ID 幂等。
- 类型白名单：`hello/ready/activated/control/chapter_state/state_ack/error/stopping/stopped`。
- `control` 仅 `activate/pause/resume/stop`；activate 只能在 constructed 阶段接受一次。课程/章节必须来自已注册目录，不能通过 IPC 调用任意函数/路径/外部命令。
- 父进程是进度唯一写者：接收 chapter_state 后记录并 ACK；持久化失败的 ACK 明确 `persisted=false`，不冒充已保存。
- 子进程断开父通信后立即停止引导、隐藏窗口并收尾退出；父进程通过 QProcess 信号检测启动失败和退出，不轮询全机器进程。

### 5.3 原工作挂起与恢复

新增独立的 `TeachingSuspendToken`，不复用 `hide_to_background`：

- 安全开始前禁止活动文字编辑、输入法组字、手势和模态/文件操作，等待用户正常结束；不自动结束笔迹或提交文字。
- 记录原生命周期状态、各拥有窗口的可见性/位置、焦点、工具/选区及各回调的启停；只隐藏且暂停，不 `load_page`、`clear`、`set_tool` 或清空撤销。
- 添加教学挂起的窗口显示守卫，心跳/延迟回调不能把原窗口抢回屏幕；自动保存期间不生成教学版本。
- 原计时器明确暂停；恢复重置 `_timer_last`，不扣除练习耗时。原有声音/闪烁回调暂停，不在练习过程中混入练习响铃。
- 退出练习后按原可见性、工具、选区和位置恢复；安全焦点恢复失败只回到可见主窗口，不提交原编辑内容。恢复只执行一次。
- 教学期间原应用会话计时暂停；练习不触发普通 `app_started`、release notice 计数或常规使用统计。

### 5.4 托盘、热键和原有退出保护

父进程保持唯一托盘和全局键盘监听，子进程不创建它们。

- 教学期间 F12：向练习发送暂停并隐藏请求，监听继续工作；托盘“显示”恢复练习，不显示原工作来与练习争焦点。
- 普通暂停可保持练习画布可见；F12/后台必须隐藏全部练习拥有窗口与说明。
- 托盘退出/重启：先停止练习、恢复原工作，再走既有未保存确认。取消退出后继续原工作，不恢复已结束的练习。
- 练习界面的退出按钮只结束练习，不关闭父进程。
- 教学期间实际更新安装不可启动；正常更新检查/通知延后到返回原工作，启动确认不被教学延迟。

### 5.5 文件和系统边界

所有读取/写入入口做 canonical 路径验证，不能只把 QFileDialog 起始位置换成练习目录。

- 练习项目只读私有 fixtures 和本会话生成的项目；保存、另存为、导出、自动保存、名单、日志都只写私有根。
- 文件对话框选择根外文件/目录时返回本地化说明，不调用实际文件操作；后端直接调用也有相同守卫。
- 检查 `..`、另一盘符、UNC、符号链接/目录联接的真实解析路径；新输出文件检查其现有父目录，拒绝链接导致的根外写入。
- 练习配置可以变化但不回写父设置；更新下载/安装、自启注册表、真实恢复与系统重启明确禁用，教学中只解释相关界面。
- 练习关闭默认丢弃练习内容，提前说明；不主动复制到正常导出目录。

### 5.6 收尾、崩溃和清理

- 停止先移除所有教学过滤器/高亮，停止新文件任务，取消/收尾已有私有文件工作，再退出子进程。
- 5 秒未退出则只对本次 QProcess 调用 terminate；再过 2 秒仍未退出则 kill。确认进程不再运行后才清理私有目录并恢复原 UI。
- 无法确认子进程终止时保留目录和挂起保护，提供重试停止；不得删除活跃进程的文件或同时恢复两套交互 UI。
- 删除前验证绝对路径仍在指定临时教学命名空间、UUID 和标记匹配，拒绝目录联接；只删除已拥有会话，不删用户指定目录、父数据或其他程序。
- 下次启动可清理经标记且确认拥有者进程已终止的旧私有根；PID 重用/权限导致活性不确定则保留，不猜测删除。
- 子进程崩溃不记完成；原进程恢复一次。父进程退出导致连接断开，子进程自行收尾；练习文件绝不进入普通启动恢复候选。

## 六、实施任务与验证顺序

每个任务按“新增失败测试 → 确认失败 → 最小实现 → 测试通过 → 自审差异”的节奏执行。实施可使用最多同时 1 个子代理，任务写入范围必须不重叠。新测试名是本计划定义，当前不存在。

### T0：独立文档纠错提交

已在本地修改三份文档并通过定向回归。允许 Git 写入的环境中仅提交这三个文件：

```powershell
git diff --check
git add -- README.md README.en.md docs/release-validation-6.1.0.md
git commit -m "docs: correct 6.1.0 file menu and software-use teaching scope"
git push origin main
```

前置：核对工作区和远端状态，存在新远端变更时先正常协调，禁止 force push；推送后验证远端提交。实施启动后权限恢复，三份文档已独立提交并推送：`bd0512d`。研究报告与计划未混入该纠错提交。

### T1：模型、课程校验和进度

文件：`teaching/models.py`、`catalog.py`、`state.py`，最小课程及相应测试。

```python
# tests/test_teaching_state.py
# state_store 是隔离临时目录中的 TutorialStateStore 测试 fixture。
def test_skipping_is_not_completion(state_store):
    state_store.record_chapter('c01.ink', 'skipped', compat_revision=1)
    assert state_store.completed_count() == 0
    assert state_store.chapter_status('c01.ink') == 'skipped'

# tests/test_teaching_catalog.py
# catalog_loader 载入完整样例目录；invalid_jump 指向不存在的步骤。
def test_catalog_rejects_dangling_jump(catalog_loader, invalid_jump):
    import pytest
    with pytest.raises(ValueError, match='jump'):
        catalog_loader.validate(invalid_jump)
```

同时覆盖重复 ID、无结束闭环、未知字段/动作/条件、路径素材越界、八语言缺键、损坏/未知高版本/只读状态、欢迎关闭不重复、修订不重置、重播不清历史。

运行：`python -B -m pytest -q tests/test_teaching_catalog.py tests/test_teaching_state.py`。

### T2：真实业务事件和引擎

文件：`events.py`、`engine.py`，以及 `main.py` 已有功能的窄接入点。

事件字典至少涵盖 `tool.changed/ink.committed/ink.erased/history.undo/history.redo/selection.changed/object.transformed/object.copied/object.deleted/board.changed/page.created/page.switched/page.renamed/page.deleted/page.copied/page.reordered/text.committed/shape.committed/project.saved/project.opened/unsaved.decision/recovery.previewed/recovery.applied/media.imported/export.finished/settings.changed/tool.window_opened/timer.started/timer.finished`，每个事件带已定义上下文和必要枚举/数量详情，不携带用户文本或名单。

在业务成功点发信号：项目函数实际返回成功、导出 `ExportResult` 收尾、页面/对象修改提交、文本/形状结束提交；不在按钮点击时冒充成功。

```python
# tests/test_teaching_engine.py
# waiting_engine 已停在等待 export.finished/success 的步骤。
# event_factory 默认生成与当前会话、run、epoch 对应的不同 operation_id。
def test_export_cancel_does_not_finish_success_step(waiting_engine, event_factory):
    before = waiting_engine.current_step_id
    event = event_factory('export.finished', outcome='cancelled')
    assert waiting_engine.consume(event) is False
    assert waiting_engine.current_step_id == before

def test_old_epoch_result_is_ignored(waiting_engine, event_factory):
    event = event_factory('export.finished', outcome='success', epoch_offset=-1)
    assert waiting_engine.consume(event) is False
```

补充 failed/partial、重复结果、自动准备产生的事件、其他会话、上一步后旧回调、暂停期间结果、显式取消步骤、分支终止和必做操作缺失。运行 `tests/test_teaching_engine.py`、`test_teaching_events.py` 加现有文档/页面/导出/文本回归。

### T3：目标注册、教学控件与工具入口

文件：`targets.py`、`widgets.py`、`ui_icons.py`、`main.py:setup_tools_sub/build_toolbar_buttons`、`i18n.py`。

```python
# tests/test_teaching_targets.py
# panel 是无真实托盘/钩子的隔离 Qt 面板；registry 绑定该面板。
def test_pen_target_uses_visible_icon(panel, registry):
    panel.set_ui_mode('icon', persist=False)
    target = registry.resolve('toolbar.pen')
    assert target is panel.icon_buttons['pen']
    assert target.isVisible()
```

该示例使用基线已经存在的 `set_ui_mode(mode, persist=True)`。覆盖隐藏旧按钮不能被选为目标、菜单未开、滚动、折叠、横竖栏、控件重建/销毁、窗口移动和屏幕/DPI；验证所有步骤始终有退出按钮，遮罩不吞画布手势，导出图像无教学 UI。

运行 `tests/test_teaching_targets.py`、`test_teaching_widgets.py`，以及现有 touch/passthrough/z-order/theme/file-panel tests。

### T4：路径隔离与 IPC/子进程

文件：`runtime_paths.py`、`protocol.py`、`practice.py`、`main.py` 启动与实际文件边界、spec 资源。

```python
# tests/test_teaching_practice.py
# practice 是私有根的 RuntimePaths；outside_project 在另一临时目录。
def test_practice_rejects_external_project(practice, outside_project):
    import pytest
    with pytest.raises(ValueError, match='outside'):
        practice.require_read_path(outside_project)

# tests/test_teaching_protocol.py
# codec 实现上述 4-byte length + JSON 协议；包超过 64 KiB。
def test_oversized_frame_is_rejected(codec):
    import pytest
    with pytest.raises(ValueError, match='size'):
        codec.feed((65537).to_bytes(4, 'big'))
```

覆盖另一盘符/UNC/`..`/目录联接、正常路径零行为变化、握手身份不匹配、重复消息、部分帧、未知类型、启动失败/超时、持久化 ACK 失败；实际启动隔离 child，确认没有真实托盘、第二热键、普通恢复/欢迎、更新或自启写入。

运行 `tests/test_teaching_runtime_paths.py`、`test_teaching_protocol.py`、`test_teaching_practice.py` 加既有 `test_runtime_isolation.py` 与更新保留回归。

### T5：原现场挂起/恢复和所有退出路径

文件：`app_lifecycle.py`、`practice.py`、`main.py` 的回调/会话计时路由。

```python
# tests/test_teaching_lifecycle.py
# panel 有多页未保存文档、撤销/重做、选区、工具设置和多个工具窗。
# runtime_snapshot 除持久内容外记录 undo/redo、page IDs、dirty/path 与窗口态。
def test_practice_exit_preserves_original_runtime(panel, broker, runtime_snapshot):
    before = runtime_snapshot(panel)
    broker.run_bounded_private_exercise_and_stop()
    assert runtime_snapshot(panel) == before
```

测试 fixture 必须实际执行子进程练习并写/导出私有文件，不能把 `run_bounded_private_exercise_and_stop` 写成空模拟。对比包括内容/修订/页面顺序/ID、undo/redo、dirty/当前文件、选区/工具、父配置与原自动保存/导出目录文件哈希；原计时器允许按明示的暂停规则比较。

覆盖未结束笔迹/文本/IME 延后、原计时暂停不扣练习时间、F12/托盘暂停恢复、退出确认取消、重启与未保存保护、子崩溃/父断连、并发启动阻止、关闭两次、超时 terminate/kill 和不安全清理拒绝。

运行 `tests/test_teaching_lifecycle.py`、`test_teaching_cleanup.py`，并跑现有 lifecycle/text/keyboard/update/auto-save 回归。T4/T5 安全测试未过不推进课程扩充。

### T6：首次引导和一次性功能提示

文件：`widgets.py`、`state.py`、`main.py` 启动末段和选定功能入口。

```python
# tests/test_teaching_startup.py
# boot_harness 记录原恢复/更新确认/欢迎发生顺序。
def test_welcome_is_after_recovery(boot_harness):
    boot_harness.normal_start(welcome='unseen', recovery_available=True)
    assert boot_harness.events.index('recovery.finished') < boot_harness.events.index('welcome.shown')

def test_dismissed_welcome_does_not_repeat(boot_harness):
    boot_harness.normal_start(welcome='dismissed')
    assert 'welcome.shown' not in boot_harness.events
```

同时验证 --restore、恢复选择取消、首次老用户升级、accepted 后启动失败、只读/损坏/高版本状态、smoke 不计数、首次提示不抢焦点/不自动开课、关闭提示后不再出现。

运行 `tests/test_teaching_startup.py`、`test_teaching_context_hints.py` 加既有 release notice / update startup ack tests。

### T7：完整课程、素材和八语言

文件：13 份 course JSON、catalog、fixtures/images、`i18n.py`。按 C01 → C02–C07 → C08–C13 实施，每章验证目标/事件/分支/结束清理。

```python
# tests/test_teaching_content.py
# catalog 是打包后的完整课程目录。
def test_complete_catalog_has_all_required_chapters(catalog):
    assert len(catalog.courses) == 13
    assert sum(len(c.chapters) for c in catalog.courses) == 46
    assert catalog.step_count('c01') == 24

def test_every_required_step_has_a_real_wait_or_read_ack(catalog):
    for step in catalog.all_steps():
        assert step.wait is not None or step.kind == 'information'
```

增加每种笔/形状/导出格式与功能覆盖表，不以总步数替代完整性；八语言键集合/占位符/非空检查，最长文本排版、RTL 不在当前语言集合范围，不能额外承诺。课程内容审核应读实际文案而不是只检查键存在。

运行 `tests/test_teaching_content.py`、`test_teaching_i18n.py` 和全量 `python -B -m pytest -q`（离屏、隔离数据、关闭真实键盘）。

### T8：大量实屏、冻结包和交付文档

新增：`tests/real_teaching_acceptance.py`、`tests/run_real_teaching_isolated.py`、`tests/verify_teaching_frozen.py`、`docs/teaching-acceptance.md`；扩展实际 build/smoke 验证而不是只检查源代码。

计划测试矩阵（**不是当前通过数**）：

| 维度 | 最低验收范围 |
|---|---|
| 完整原生课程 | 13 课 × 深浅主题 × 横竖栏 = 52 次全流程 |
| 章节直达重播 | 46 章 × 深浅主题 = 92 次；检查初始素材和出口 |
| 首启/跳过/关闭/升级 | 4 状态 × 2 主题 × 2 方向 = 16 条原生路径 |
| 生命周期反复 | 至少 100 次开始/暂停/F12/恢复/退出混合循环，资源数不持续增长 |
| 故障 | 启动失败、坏帧、断连、崩溃、父进程退出、取消/失败/部分失败、写盘/权限故障 |
| 八语言 | 每种语言欢迎/中心/最长气泡/结尾实屏冒烟，完整字符串离屏排版检查 |
| 输入 | 真鼠标和 Windows 原生键盘/触控注入；物理触摸设备仅实际拥有时测试 |
| 布局/屏幕 | 折叠/拖动/滚动/中文长文；DPI 及负坐标模拟；物理双屏仅有设备时实测 |
| 冻结包 | extracted EXE + practice child + 全课程资源 + 打开保存恢复导出 + 崩溃返回 |
| 路径 | 中文、空格、任意工作目录、只读程序目录、正常便携数据迁移 |
| 原工作隔离 | 多页未保存、undo/redo、选择、工具、配置、真实自动保存和导出文件前后核对 |

测试驱动只对本轮拥有的隔离实例注入输入；真实教学等待必须用业务事件完成，不借测试代码直接移动引擎步骤。每条用例记录步骤预期、实际结果、运行模式和证据；截图/录屏脱敏，测试临时数据不提交。

冻结验收包只发布到本地供审核目录，版本字段使用经后续确认的版本，不占用或覆盖已发布 6.1.0；报告绑定源码提交、Python/Qt、资源清单和包哈希。如果未获版本号批准，保持源码版本，验收包明确标记“未发布开发构建”，不上传 Release、不造新标签。

## 七、硬性验收门槛

1. 三个入口路径成功：首次欢迎、正常工具 → 教学、练习内教学中心。
2. 13 课/46 章完整可达，每个适用步骤能由真实功能完成，跳过/停止始终可用。
3. 保存/打开/导出取消、失败、部分失败及旧异步结果不误推进成功步骤。
4. 所有练习操作都不改父文档、undo/redo、配置、真实名单、自动保存和导出目录。
5. 原进程安全挂起和子进程失败恢复通过；无第二托盘/全局钩子、活跃窗口/线程/过滤器残留。
6. 跳过不计完成，欢迎不反复出现，重播/升级/状态损坏规则可复核。
7. 实屏矩阵与冻结资源/子进程测试通过，原有完整回归无新增失败；原有 skip 原因记录。
8. 每种语言真实展示与全部键/占位符校验通过；课程/图片/fixture 不靠联网。
9. 报告区分离屏、原生注入、模拟显示器与物理硬件，不作“任何环境都没有问题”的保证。
10. 未达到门槛只报告实际结果和剩余风险，不把教学计划、旧版本测试或一次截图当作交付证明。

## 八、提交与审核检查点

- 独立 docs commit：6.1.0 三份纠错已由 `bd0512d` 完成并推送。
- 审核本计划后，提交研究/设计文档；再按 T1–T8 分别提交可通过验证的改动，不混入私有缓存、名单、日志和原始截图。
- 检查点 A：T1–T3，有可运行的最小章节，审阅交互，但不声称完整课程交付。
- 检查点 B：T4–T6，隔离/启动/退出安全全部通过，再扩充课程。
- 检查点 C：T7，完整课程和八语言通过，交出功能预验收。
- 检查点 D：T8 与硬门槛通过，交完整报告和未发布包；用户批准后才讨论正式版本发行。

用户已明确批准开始实施。最多同时 1 个子代理；当前目录使用独立功能分支保护发布主线，不另建未经用户请求的工作树。里程碑结果持续写入 `docs/teaching-implementation-progress.md`。
