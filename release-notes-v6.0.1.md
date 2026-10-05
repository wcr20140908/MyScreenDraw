# MyScreenDraw v6.0.1 — 更新进度与安装重启修复

## 修复内容

- 检查、下载、校验、安装使用独立状态。下载显示百分比、已下载／总大小（MiB）并支持取消；未知总大小时使用不定进度及已下载大小，不伪造百分比。
- 下载完成回调排队时仍阻止重复检查／下载；取消、失败或拒绝安装后恢复控件并清理临时下载。
- 源码运行时拒绝应用内覆盖安装，即使目录中存在 EXE；便携安装传递目标版本和旧进程 PID，等待退出，不强杀任意 Python 进程。
- 校验清单版本及 EXE SHA-256，重置 PyInstaller 启动环境。使用 .NET 按字面路径启动，修复中文、空格和方括号目录下的重启失败。
- 收到新进程事件循环就绪确认后才提交安装并清理备份。替换失败或新进程早退时尝试回滚；进程仍存活但未确认就绪时保留备份，不强行覆盖运行中的文件。
- 保留 `data/`、`exports/` 和未参与替换的用户文件。回滚不是断电、磁盘损坏或权限故障下的无条件恢复保证，升级前仍须备份。

## 6.0.0 用户：本次请手动换目录升级

**6.0.0 正在运行的更新器自身有缺陷，新包不能追溯修复旧进程中的代码。不要依赖 6.0.0 应用内更新完成这次升级。**

1. 从本版本正式 Release 下载 `MyScreenDraw-v6.0.1-windows-x64.zip` 和同版 `.zip.sha256`，核对 SHA-256。不要选择 GitHub 自动生成的 Source code 源码附件。
2. 将 ZIP 全部内容解压到新的空目录，保留 EXE 与 `_internal/` 的相对位置；不覆盖旧目录或源码目录，先不要启动新程序。
3. 保存工作，通过旧版托盘菜单完全退出并处理保存确认，确认旧进程已结束。F12／隐藏到托盘不是退出。
4. 备份旧版 `data/`、`exports/` 和外部项目，再复制 `data/`、`exports/` 到新目录。目标若已有用户文件，先分别备份并逐项处理冲突，不整目录覆盖。保留旧目录及备份。
5. 将桌面、开始菜单、任务栏快捷方式改为新 EXE；如启用了开机自启，也须核对并更新其路径，避免又打开旧版。
6. 运行新 EXE，确认 **v6.0.1**，核对设置、项目和导出，再完全退出并重新打开。不要让两个版本同时操作同一份数据。

**For 6.0.0 users:** do not rely on its embedded updater. Download and verify the 6.0.1 portable ZIP from the official release, extract it into a new empty directory, fully exit the old version, then back up and copy `data/` and `exports/`. Resolve existing-file conflicts individually. Update shortcuts and any enabled autostart path, confirm v6.0.1, and restart. Keep the old installation and backups. See the [English README](https://github.com/wcr20140908/MyScreenDraw/blob/main/README.en.md) for details.

## 本轮验证与限制

- Windows 10 x64，Python 3.11.9、pytest 9.1.1、PyQt6 6.11.0、PyInstaller 6.21.0。
- 完整构建门禁：**1347 项通过、7 项跳过、1197 个子测试通过，构建退出码 0**。Qt 会话结束时先销毁测试窗口，避免将对象留到解释器退出；不忽略原生崩溃退出码。
- 构建目录及 ZIP 解压目录中的真实 EXE 均通过离屏启动；源码快照、包内容、EXE 哈希与验收收据一致。
- 带中文、空格、方括号的隔离目录中，当前更新事务自动重启到 6.0.1，观测耗时 **21.36 秒**，再次打开通过；4 个合成用户文件和 5 项设置保留。耗时仅为本机本次观察，不是启动时限承诺，也不证明旧版内嵌更新器已修好。
- 手动换目录迁移演练：新 EXE 两次正常启动，5 项设置保留，旧目录、备份及外部合成项目未变；只验证空白合成项目，未操作真实快捷方式或自启动项。
- 原有 90 个用户数据／导出文件哈希未变。验收数据单独保存在本地，不随包分发。
- 未进行真实触控大屏、Windows 11、多屏／DPI、另一台无 Python 机器或长时间课堂验收。程序未签名，SHA-256 不是发布者数字签名。
- 公开附件回下载状态及详细证据见 [6.0.1 验证记录](https://github.com/wcr20140908/MyScreenDraw/blob/main/docs/release-validation-6.0.1.md)。本地验收不能替代公开附件核验。

ZIP SHA-256：`408ba00326c0e434cde8705207a489a462400af109b3a9d0baa93479e072d925`
