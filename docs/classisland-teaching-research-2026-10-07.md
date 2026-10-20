# ClassIsland 软件使用教学系统调研报告

日期：2026-10-07（Asia/Shanghai）
项目：MyScreenDraw
状态：调研完成，方案已获用户批准并开始实施；调研阶段未使用子代理。具体实现状态见 `docs/teaching-implementation-progress.md`。

## 1. 结论先行

这里的“教学”是**教人使用 MyScreenDraw 的操作引导系统**，不是添加课堂预设、考勤、课堂录制或新的授课工具。

建议全面参考 ClassIsland 的用户教学机制，而不是只做一个欢迎窗口：课程中心、分章学习、真实控件高亮、操作成功后自动前进、条件分支、完成状态、暂停、跳过和重播均纳入本次范围。入口固定为**工具 → 教学**，首次遇到教学系统的用户收到可跳过的欢迎引导。

最重要的差异是练习隔离。MyScreenDraw 的操作会修改笔迹、页面、撤销栈、项目路径、自动保存和导出结果。因此推荐**由当前程序启动一个使用真实功能的独立练习进程**。原进程保留原工作，练习进程使用私有数据和虚构素材；不能把当前画布清空后再用项目文件“恢复”当作无损隔离。

交付目标是完整课程与可靠引擎，不包括可视化课程编辑器、Lua/任意脚本执行、云端课程和强制联网。未批准自动发布新版本；本计划默认提供验收包，发行另行确认。

## 2. 调研对象与证据边界

### 2.1 精确对应 D 盘安装版本

- 安装目录：`D:\ClassIsland\app-2.1.0.1-0`。
- `ClassIsland.dll` 文件版本：`2.1.0.1`。
- 产品版本所含源码提交：`15273f82c9d2d55929df83b5fb806e68ee4547c0`。
- 技术栈：C# / Avalonia；安装包内为 .NET 8 运行时。
- 该目录是安装包而不是源码 Git 工作区。调研读取了本地程序集、XML 文档、教学图片，以及对应提交的官方源码，没有启动 ClassIsland，也没有读取或修改其个人 `data` 配置。
- 本地调研缓存：`.ccgui/classisland-reference-15273f82c9d2/`，包含版本记录、官方 Git 树、64 个源码文件和分析笔记。此缓存被 Git 忽略，不是交付实现的一部分。

2026-10-07 重新进行内容核对：

| 核对项 | 结果 |
|---|---|
| `classisland.getStarted.json` 在安装 DLL 中的内容 | CRLF/LF 归一化后逐字节匹配 |
| `classisland.test.json` 在安装 DLL 中的内容 | CRLF/LF 归一化后逐字节匹配 |
| `classisland.sp.json` 在安装 DLL 中的内容 | CRLF/LF 归一化后逐字节匹配 |
| 本地随附教学图片与该提交的 Git blob SHA-1 | 13 / 13 匹配 |

所以本报告分析的是**这台机器上安装版本的实现**，没有把 GitHub 主分支的新实现当成你本地安装版本，也没有声称 2.1.0.1 是 ClassIsland 的全球最新版本。

### 2.2 MyScreenDraw 基线

- 仓库：`D:\MyScreenDraw`。
- 本轮开始时工作区干净；本地 `main` 为 `9e9feed574c7e0f20ac50664ddb429725d0451ee`，提交说明是 `Document 6.1.0 publication and verified public downloads`。
- 已发布 6.1.0 代码提交：`bfd172c5d15546b7a8c4b0181d7821f55fe71646`。
- 本机只读绑定检查确认：PyQt / Qt 均为 `6.11.0`，`QProcess`、`QLocalServer`、`QLocalSocket` 和 `UserAccessOption` 可用。
- 6.1.0 的测试与发行证据保存在 `docs/release-validation-6.1.0.md`。这些是旧版本的验证，不是新教学功能的验证。

## 3. ClassIsland 的实现方式

### 3.1 四层课程结构

```text
TutorialGroup（课程组）
  └─ Tutorial（课程）
       └─ TutorialParagraph（章节）
            └─ TutorialSentence（步骤）
```

课程使用 JSON 描述，运行时注册到教学服务。步骤可提供标题、说明、图标、图片、目标控件选择器、定位方式、高亮/遮罩、左右按钮及其动作、初始化动作、等待真实操作的标签；源码还支持可选 Lua 钩子。

内置注册位置：`ClassIsland/App.Services.xaml.cs:317–319`。真正启用的是 `classisland.getStarted.json`；测试课程和另一份课程虽然随包存在，但注册语句被注释，不能说三个课程组都向普通用户开放。

启用的入门组：

| 课程 | 章节 | JSON 步骤总数 |
|---|---:|---:|
| 欢迎/入门 | 10 | 30 |
| 档案编辑 | 6 | 56 |
| 组件编辑 | 6 | 42 |
| 合计 | 22 | 128 |

128 是定义中的步骤总数，不是每个人都必须点击 128 次；课程中有拒绝、跳转和条件分支。

### 3.2 不是幻灯片：真实控件与真实操作联动

主要服务：`ClassIsland/Services/TutorialService.cs`。

- 每次只允许一个活动教程。
- 章节通过窗口类型解析宿主 `TopLevel`，步骤通过选择器找到真实控件。
- 用 `TeachingTip` 展示气泡；通过 adorner 层附加高亮、聚光遮罩与交互阻挡。
- `WaitForNextCommand` 配合 `Tag` 等待业务操作。业务处理器调用 `PushToNextSentenceByTag`；服务先检查是否正在执行初始化动作、当前步骤是否等待、标签是否相同，再前进。
- 主窗口进入/退出编辑模式、打开设置、档案编辑的选择和创建等动作，均有相应教学信号。
- 步骤切换会清理气泡和装饰器；宿主内容替换时有 detach/reattach 逻辑，避免旧高亮遗留或引用失效。

这套思想适合直接借鉴：**指向正在使用的控件，等待真实功能成功，而不是只等待“下一步”按钮**。

### 3.3 教学中心与控制器

- 教学中心支持整课重播、单章播放、完成数显示和停止。
- 首次欢迎询问是否学习；拒绝后解释以后如何从菜单进入“教学…”。
- 独立小控制器提供当前课程/章节和跳过操作，按目标屏幕工作区和 DPI 定位在左下角。
- 进入某些编辑功能时，通过 `BeginNotCompletedTutorials` 补充首次功能引导。

相关文件：`TutorialCenterWindow.axaml[.cs]`、`TutorialControllerWindow.axaml[.cs]`、`TutorialCenterViewModel.cs`。

### 3.4 进度与边界：不能全部照抄

`ClassIsland/Models/Tutorial/TutorialSettings.cs` 使用完成章节路径集合，持久化到 `Tutorial.json`。

- `SkipTutorial()` 会把当前章节写成完成，再停止。
- 持久化不是精确到每个步骤的断点恢复。
- 源码具有课程编辑器和 Lua 能力，但它们不是用户已经确认的 MyScreenDraw 范围。

MyScreenDraw 要改进这些点：**完成、跳过、欢迎关闭分别记录**；中断后从章节开始重新创建安全练习，而不是凭一个步骤索引假装恢复了练习环境。

## 4. MyScreenDraw 的接入点和限制

以下行号以研究基线为准，文件修改后可能移动。

| 位置 | 现有行为 | 教学接入要求 |
|---|---|---|
| `main.py:10030`，`setup_tools_sub` | 计算器、点名、辅助工具、计时、放大镜、聚光灯 | 在这里增加教学入口 |
| `main.py:9238`，`build_toolbar_buttons` | 图标按钮放在 `icon_buttons`；共同使用展示用对象名 | 注册稳定语义 ID，解析当前可见图标；旧按钮隐藏，不能误定位 |
| `main.py:10045`，`setup_file_sub` | 项目打开/保存、导入及四种导出 | 文件教学必须指向“文件”而不是“工具” |
| `main.py:318–345` | 程序、数据、导出、自动保存、配置、名单、日志路径为模块全局量 | 子进程在初始化写盘前绑定私有路径；资源路径与数据路径分开 |
| `main.py:8962–8973` | 构造面板就启动心跳、自动保存、键盘监听和生命周期/托盘 | 子进程不得再创建真实托盘或第二个全局键盘钩子 |
| `main.py:9841` | F12 触发后台操作并结束监听 | 教学期间由父进程唯一监听并转发；不能误退出监听 |
| `main.py:12420` | `pause_callbacks` 停若干定时器，但不包含原计时器时钟等完整状态 | 教学挂起需独立、可逆的状态管理 |
| `app_lifecycle.py:496` | 正常后台隐藏会结束文字编辑、切换鼠标模式、关临时窗 | 不能把它当成精确保留原现场的教学挂起 |
| `main.py:14877–14968` | 更新启动确认与项目恢复/自动保存恢复先执行 | 欢迎排在恢复结束且 UI 就绪后；不覆盖恢复对话框 |
| `MyScreenDraw.spec:29` | 当前数据文件只列许可证 | 显式包含课程、图片和练习素材，并验证冻结包 |
| `i18n.py:5–15` | 所有用户文案走 `tr/trf`，八语言完整 | 教学 UI 和课程文案同样遵守 |

### 4.1 为什么项目快照还原不够

`capture_page()` 只保存页面内容、身份和修订信息，不包含完整撤销记录、正在编辑的文字、选区、工具运行态和所有窗口；`load_page()` 会清理编辑与构造状态。用它们切换临时练习再还原，最多是恢复内容，不是恢复工作现场。

### 4.2 为什么不在同一进程随手再建一个面板

另建面板会复制监听、托盘和定时器。当前窗口归属通过 QWidget 属性、父链及已注册工具发现，同进程第二套窗口还会影响关闭、置顶、焦点和全局样式。要安全实现，必须做较大范围的运行上下文重构；本次没有必要承担这条路径的风险。

### 4.3 三种方案比较

| 方案 | 优点 | 代价/风险 | 结论 |
|---|---|---|---|
| 当前文档临时替换、结束还原 | 初期代码少 | 撤销/编辑/设置与失败恢复不完整；易写入真实自动保存 | 不采用 |
| 同进程独立文档/面板与运行上下文 | 启动快 | 全局路径、样式、焦点、窗口归属、钩子和托盘重构较广 | 不推荐本次采用 |
| 同程序独立练习进程 | 原文档留在原进程；Qt 样式和运行数据天然分开；复用真实 UI | 需子进程启动、IPC、挂起/恢复和冻结包验证 | 推荐 |

独立进程是产品数据隔离设计，**不是防恶意代码的操作系统安全沙箱**。文件边界仍必须由实际读取/写入函数验证，不能只改变文件对话框的初始目录。

## 5. 建议产品行为

### 已确认的范围

1. 完整使用教学系统，不是只有一个短欢迎页。
2. 工具 → 教学为主入口；首次遇到该系统的老用户升级后也有可跳过的欢迎。
3. 真实操作练习使用独立环境，结束返回原工作。
4. 课程用校验过的 JSON 维护；本次不做可视化编辑器或任意脚本。
5. 不使用子代理。

### 尚未得到回答的问题：采用供审核的默认值

前序三项选择问题没有收到答案，以下是本计划的建议，不是已获用户确认：

- 首次引导先完成 6 章 / 24 步的核心入门；之后在课程中心自由学习全部内容。
- 第一次使用重要功能时最多出现一次不抢焦点的提示，点击后才开始独立练习；可以关闭这类提示。
- 完成功能、测试和未发布验收包；不自动发 6.2.0，也不替换 6.1.0。

完整课程目录、逐章范围、状态机、接口、实施顺序和验收门槛见配套实施计划。

## 6. 必须解决的风险

- **正常启动/恢复顺序**：恢复提示、`--restore` 和更新确认优先；`--smoke`、`--smoke-ui` 不启动、不计数教学。
- **初始化可见性**：Canvas 构造与设置载入会显示窗口，练习需在实际 show 调用点保持隐藏，父进程挂起后才激活，不能先显示后补救。
- **安全启动时点**：有未结束笔迹、触控手势、输入法组字、活动文字编辑、模态对话框、导入/导出/保存/更新工作时先等待安全时点，不能偷偷提交或取消原操作。
- **无损挂起**：不序列化替换原文档；保留选区、撤销重做、工具、窗口可见性和位置。原计时器暂停且不补扣整个练习耗时；恢复需明示此行为。
- **目标重定位**：菜单未打开、目标被折叠/滚出可视区、布局重建、窗口移动、DPI 或屏幕改变时重解析，不依赖旧 QWidget 或中文标签。
- **输入屏障**：绘图步骤必须放行整个真实画布；按钮步骤只限制本程序其他控件；气泡/高亮不进入项目、截图导出、缩略图或笔迹记录。
- **操作成功判定**：取消、失败、部分失败和旧异步回调不能完成成功步骤。教学“取消操作”的步骤必须明确等待取消事件，不能与成功混淆。
- **文件边界**：项目、自动保存、日志、名单、导入和导出均使用私有根；路径穿越、盘符切换、符号链接/目录联接和文件对话框越界都要拒绝。
- **系统设置**：教学中不能安装更新、改注册表自启、重启原应用、访问真实名单或将假文档交给正常恢复入口。
- **退出故障**：子进程启动失败、崩溃、断开通信、父进程退出都要有明确收尾；只管理本次创建的子进程和有标记的私有目录。
- **进度真实**：跳过不等于完成；文案更新不重弹欢迎；重播失败不能删除以前真正完成的历史。
- **资源与语言**：离线完整；八语言键与占位符齐全；中文路径、空格路径和冻结子进程均实测。
- **实屏真实性**：Windows 原生输入注入、离屏 Qt 测试、虚拟屏模拟、物理触控/双屏是不同证据，报告不得混称。

## 7. 6.1.0 文档核查和本轮修订

### 核查结论

6.1.0 的中英文 README、更新说明和发行验证文档此前已更新；`9e9feed` 是发布后的文档跟进提交。不能回答“完全没有更新”，也不能把教学系统写成已经随 6.1.0 交付。

本轮已在工作区修正：

1. `README.md`：项目文件入口由“工具 → 打开 / 保存”改为“文件 → 打开 / 保存”。
2. `README.en.md`：同样由 `Tools` 改为 `File`。
3. `docs/release-validation-6.1.0.md`：替换误解范围的课堂预设讨论，明确软件使用教学尚未在 6.1.0 实现；注明 2026-10-07 纠正日期与计划性质。

新教学功能尚未存在，不修改历史发行包、校验和、`v6.1.0` 标签或生产版本号。

### 本轮验证

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:MYSCREENDRAW_NO_KEYBOARD = '1'
python -B -m pytest -q -p no:cacheprovider tests/test_file_panel.py tests/test_i18n_and_telemetry.py
git diff --check
```

结果：**11 tests passed，17 subtests passed**；三份修订文档的差异检查通过。这是文件菜单与既有语言机制的定向回归，不是新教学系统的验收。

### Commit / GitHub 状态

规划阶段环境将 `.git` 设为只读，修订当时只保存在本地，没有绕过权限。用户批准实施后权限恢复，2026-10-07 再次通过定向回归后，三份纠错文档已独立提交并推送到 GitHub：`bd0512d`，提交说明为 `docs: correct 6.1.0 file menu and software-use teaching scope`。

研究报告与实施计划单独保存，不混入该纠错提交。教学系统的实现与验收状态持续更新在 `docs/teaching-implementation-progress.md`，本报告不作为功能完成证明。

## 8. 可复核的参考位置

以下源码路径均相对固定提交缓存的 `source/`：

| 证据 | 文件/位置 |
|---|---|
| 模型与接口 | `ClassIsland.Core/Models/Tutorial/`；`ClassIsland.Core/Abstractions/Services/ITutorialService.cs` |
| 注册与实际启用课程 | `ClassIsland/App.Services.xaml.cs:317–319`；`ClassIsland.Core/Extensions/Registry/TutorialRegistryExtensions.cs` |
| 操作标签校验 | `ClassIsland/Services/TutorialService.cs:210–217`（本地文件行号） |
| 清理和宿主重建 | 同文件 `263–348` |
| 跳过写成完成 | 同文件 `577–583` |
| 进度存储 | `ClassIsland/Models/Tutorial/TutorialSettings.cs` |
| 遮罩/高亮 | `ClassIsland/Controls/Tutorial/`；`ClassIsland.Core/Controls/Tutorial/TutorialBarrier.axaml.cs` |
| 教学中心/控制器 | `ClassIsland/Views/TutorialCenterWindow.axaml[.cs]`；`TutorialControllerWindow.axaml[.cs]` |
| 欢迎及功能入口 | `ClassIsland/MainWindow.axaml.cs`；`Views/SettingsWindowNew.axaml.cs`；`Views/ProfileSettingsWindow.axaml.cs` |
| 课程内容 | `ClassIsland/Assets/Tutorials/classisland.getStarted.json` |

官方资料地址（固定源码版本；Qt/PyInstaller 的在线文档可能显示比本机更新的版本，接口还以本机绑定检查和锁定依赖测试为准）：

```text
https://raw.githubusercontent.com/ClassIsland/ClassIsland/15273f82c9d2d55929df83b5fb806e68ee4547c0/ClassIsland/Services/TutorialService.cs
https://doc.qt.io/qt-6/qlocalserver.html
https://doc.qt.io/qt-6/qprocess.html
https://pyinstaller.org/en/stable/runtime-information.html
```

本次参考机制和交互设计，不复制 ClassIsland 的课程文案、图片、Logo 或整个服务源码；实现和素材由 MyScreenDraw 独立编写。将参考来源记入开发说明；若后来决定直接引入上游代码/素材，应另行做来源与许可审计。
