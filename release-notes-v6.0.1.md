# MyScreenDraw v6.0.1 — 更新器修复候选（待发布）

**候选草稿：尚未声明实现完成、测试通过或正式附件可下载。** 更新器源码仍在修改，由发布负责人依据 [6.0.1 验证记录](docs/release-validation-6.0.1.md) 补齐证据后修订。当前已发布下载仍为 6.0.0；不要把其附件误认为包含本轮修复。

## 修复范围（最终包待验收）

- 下载状态与检查更新状态独立，提供下载百分比、已下载字节及取消操作。仅在总大小可信且已知时显示百分比；未知总大小时使用不定进度与字节数，不伪造百分比。
- 从源码运行时，不允许应用内覆盖安装源码目录。
- 便携包安装传递目标版本和旧进程 PID，安全等待旧进程完全退出后替换应用文件；超时或不能安全确认退出时，不应继续覆盖。
- 校验清单目标版本与 EXE SHA-256；等待新进程事件循环发回就绪确认后才提交安装并清理备份。新进程早退时回滚；若新进程仍存活但未确认就绪，则保留新文件和回滚备份，不强行覆盖运行中的程序。保留 `data/`、`exports/`、配置、名单、自动保存、日志等用户文件，不用发行包内容覆盖隐私文件。

以上修复已进入源码候选，最终发布包仍须完成下述验收。更新器测试、最终 EXE、回滚和用户数据保全均需本轮证据，6.0.0 的历史测试数字不能代用。

## 6.0.0 用户：本次请手动换目录升级

**6.0.0 正在运行的更新器自身存在下载/安装缺陷。新包不能追溯修改旧版正在执行的下载或安装代码，因此不要依赖 6.0.0 的应用内更新完成本次升级。**

待 **6.0.1 正式 Release 发布并核验后**：

1. 从官方仓库的正式 Release 下载 `MyScreenDraw-v6.0.1-windows-x64.zip` 与同版 `.zip.sha256`，校验 SHA-256；不要选择 Source code 源码附件。当前不提供尚不存在的附件直链。
2. 将 ZIP 的全部内容解压到全新的空目录，保留 EXE 与 `_internal/` 的相对位置。不覆盖旧目录或源码工作树，先不要启动新程序。
3. 保存工作，通过旧版托盘菜单完全退出并处理保存确认，确认旧进程已结束。F12/隐藏到托盘不是退出。
4. 备份旧版 `data/`、`exports/` 和外部项目，再将 `data/`、`exports/` 复制到新目录。不要用默认或示例文件覆盖配置、名单、日志、自动保存等隐私文件；若目标已有用户文件，先备份双方并逐项解决冲突。保留旧目录和备份以备回退。
5. 将桌面、开始菜单、任务栏快捷方式改为新目录的 `MyScreenDraw.exe`；如已开启开机自启，同时核对并更新其路径。
6. 启动新 EXE，确认 **v6.0.1**，核对设置、项目与导出，再完全退出并重启验证。不要同时运行两个版本操作同一份数据。

**For 6.0.0 users:** the running updater has its own download/installation defects; a new package cannot retroactively fix that old code. After the official stable 6.0.1 Release is published and verified, download and verify its portable ZIP, extract it into a new empty directory, fully exit 6.0.0, then back up and copy `data/` and `exports/` without overwriting private files. Point shortcuts and any enabled autostart entry to the new EXE, verify v6.0.1 and restart. Do not rely on the old in-app updater for this migration. See the [English README](README.en.md) for full steps.

## 验证与限制（待发布负责人填写）

- 最终源码身份、环境、精确命令及通过/失败/跳过数量：**待填**。
- 下载状态、进度、取消、源码保护、PID 等待、版本/重启与失败回滚：**待验收**。
- 构建、ZIP/EXE 哈希、清单、收据、解压启动及公开附件回下载：**待验证**。
- 6.0.0 手动迁移、隐私数据保全、实际 Windows/触控覆盖：**待验收**。
- 程序的现有发布策略为未签名；本候选签名状态须与最终清单核对。SHA-256 是完整性校验，不是发布者数字签名；回滚不保证断电、权限或磁盘故障下的数据恢复，升级前仍须备份。

发布负责人应先核对证据并修订草稿，再执行发布流程；公开附件发布并回下载验证后，才把 README 的 6.0.0 下载链接及候选状态切为 6.0.1 正式版。未验证项目必须保留真实状态和限制，不能改写为通过。
