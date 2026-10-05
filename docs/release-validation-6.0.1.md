# MyScreenDraw 6.0.1 验证记录

日期：2026-10-05。**最终本地构建、隔离自动重启及手动迁移演练通过；公开发布与回下载尚待完成。** 本结论不包含实屏、物理触控或跨设备验收。

## 1. 最终包身份

- 打包源码提交：`6d6b5d9f78308aafca61e354cbf7182c9d6cb8b2`。之后的文档提交不改变二进制输入；发布前仍须通过源码／提交／收据一致性门禁。
- 源码快照 SHA-256：`6c175a371eb25b899d89d1ef2663be9d4809ebd86985026b6bab716e3f7bdfe6`。
- ZIP：`MyScreenDraw-v6.0.1-windows-x64.zip`。
- ZIP SHA-256：`408ba00326c0e434cde8705207a489a462400af109b3a9d0baa93479e072d925`。
- EXE SHA-256：`553ac46dc4f945a1c3df21c0a5c09fdb80190b4423a8c735ad562c3417ebd3fc`。
- 验收收据：`build/release-receipts/MyScreenDraw-v6.0.1-windows-x64.zip.json`。
- Windows 版本资源：`6.0.1.0`／`v6.0.1`；清单版本 `6.0.1`，签名状态 `none`。哈希与收据不是数字签名。

本轮原始证据位于本地 `exports/release-6.0.1-closeout-2026-10-05/`，下文简称“证据目录”。原始日志、隔离安装和合成数据不提交到 Git，不装入 Release。

## 2. 构建与自动化

环境：Windows 10 build 19045 x64；Python 3.11.9；pytest 9.1.1（内置子测试支持）；PyQt6 6.11.0；PyInstaller 6.21.0。子进程禁用软键盘，Qt 使用 `offscreen`。

`build.ps1` 执行的完整回归范围：

```powershell
$env:MYSCREENDRAW_NO_KEYBOARD = '1'
$env:QT_QPA_PLATFORM = 'offscreen'
python -m pytest -q --ignore=tests/test_touch_injection.py --ignore=tests/test_multitouch_injection.py --ignore=tests/test_multitouch.py
```

- 完整回归：**1347 passed, 7 skipped, 1197 subtests passed**。
- `build.log` 包含最终 ZIP／EXE 哈希、`Portable build verified` 和 `BUILD_EXIT=0`。测试摘要不是唯一依据：只有测试进程正常退出，构建脚本才进入 PyInstaller。
- 收据中的四项检查均通过：完整回归、构建目录 EXE 冒烟、解压文件逐项比对、解压 EXE 冒烟。
- 后续专项复验：114 项及 164 个子测试通过，退出码 0，见 `resumed-test-summary.json`／`resumed-regression.log`。
- 项目／设置／迁移相关回归另记录 289 项及 110 个子测试通过，见 `migration-regression.log`；不把这些数字相加当作独立覆盖率。
- 本次接续工作重新执行 `release_artifact.py verify`，确认当前源码、HEAD、ZIP、校验文件和收据一致，退出码 0。

7 个跳过项：3 项系统托盘路径在离屏平台不可用，4 项真实键盘／焦点路径未授权。上述三个触控测试文件为**显式排除**，不计为通过。

## 3. 安装事务与自动重启

执行脚本及参数形状：

```powershell
python tests/verify_updater_restart.py MyScreenDraw-v6.0.0-windows-x64.zip MyScreenDraw-v6.0.1-windows-x64.zip 6.0.1 exports/release-6.0.1-closeout-2026-10-05/restart-check
```

证据目录必须新建；已存在时脚本拒绝覆盖。已有用户自启动项时脚本拒绝正常启动验收，避免程序自动纠正用户真实注册表路径。

`restart-check/restart-verification.json` 记录：

- 旧包 SHA-256：`6ec2008cc89e7213f31d206e939191f71016872f339c8cde13b777f8e013210b`。
- 最终新包和安装后的 EXE 哈希均与第 1 节一致。
- 安装路径包含中文、空格及方括号；由**当前源码更新器**操作旧包副本，不操作用户正在使用的安装。
- 自动重启和新事件循环就绪确认通过；保存的运行版本为 v6.0.1。观测事务及启动耗时 **21.36 秒**，不是未来耗时保证。
- 4 个合成用户文件和 5 项设置保留；新进程定向关闭后，安装后的 EXE 再次 `--smoke-ui` 成功。
- 全程离屏，无桌面截图，无触控注入。子进程 PATH 排除 Python，不等于在另一台未安装 Python 的机器验证。

**此结果不证明 6.0.0 自带更新器已修复。** 从 6.0.0 升级仍应遵循 README 的手动换目录步骤。

## 4. 手动换目录迁移演练

`manual-migration/manual-migration.json` 与同目录的本地演练脚本记录：

- 使用第 1 节最终包和上述正式 6.0.0 包，离屏操作隔离目录。
- 新 EXE 正常启动两次；5 项设置保留，旧目录、用户备份及外部合成项目未变。
- 旧版保存的空白合成项目恢复通过；不能外推为任意真实课堂项目均已验收。
- 未操作用户快捷方式或开机自启项，未验收真实托盘退出交互；用户迁移时仍须核对这些步骤。
- 此演练使用本地包，尚不等于公开附件下载验证。

## 5. 数据保全及失败记录

接续前后的原有 **90 个 `data/`／`exports/` 文件全部存在且 SHA-256 未变**。新增文件均属于独立的发布验收目录；不能把整个 `exports/` 文件数量增加描述成原数据被改写，也不能声称目录完全没有新增文件。

本轮没有忽略失败：

1. 初始候选在中文／空格／方括号路径中 `Start-Process` 失败，事务回滚；该候选未发布。改为 `.NET ProcessStartInfo` 按字面路径启动并增加真实控制台程序回归后，重新构建最终包。
2. 一轮测试断言全部通过后在 SIP 解释器退出阶段发生原生崩溃，构建门禁拒绝继续。测试 fixture 改为持有会话级 QApplication，在隔离运行路径仍生效时停止定时器／后台工作并销毁窗口，不使用 `os._exit` 或忽略退出码绕过。
3. Qt 清理测试通过旧行为反例校准：不提前销毁控件时断言失败，修复后正常退出。新增重启验收自启动保护测试也以“移除保护”和“一律拒绝”两个错误版本校准。
4. 重启验收日志改用文件句柄，避免长期运行的新进程继承管道导致等待 EOF 超时；成功同时要求版本、哈希、就绪确认和进程存在。

更早 `.git/release-validation/601-resumed-build.log` 中的另一包哈希不是当前最终包，不与本报告的收据混用。

## 6. 公开附件及未覆盖项

- 正式 Release／公开附件回下载：**待完成**。
- 真实触控大屏、Windows 11、多屏／DPI、另一台无 Python 机器、长时间课堂使用：**未验证**。
- 实屏下载进度／取消、真实托盘交互、真实快捷方式及自启动迁移：**未验证**。
- 断电、磁盘损坏、杀毒隔离和所有权限故障：不在无条件恢复保证范围内。
- 未签名；哈希与回滚不能代替发布者签名或用户备份。

正式附件公开并回下载核验后才切换 README 下载入口和发布状态；保留上述边界，不把本地测试写成全设备验收。
