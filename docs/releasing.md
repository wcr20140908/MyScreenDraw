# 构建与发布 / Building and releasing

**v6.0.0 已发布**；公开 ZIP 和校验文件已回下载核对，解压 EXE 通过离屏启动检查。本页描述现有构建流程与本次正式发布的验收要求；未勾选项不是已完成声明。

## 准备构建

使用 Windows x64 和 Python 3.11 开发基线，先按 [贡献指南](../CONTRIBUTING.md) 创建虚拟环境：

```powershell
python -m pip install -r requirements.lock -r requirements-build.lock
python -m pip install pytest pytest-subtests
.\build.ps1
```

运行前确认 `build/` 和 `dist/` 没有需要保留的数据：脚本会清理这些目录。测试工具当前没有独立锁文件，应在验证记录中注明实际版本；不要声称整个环境已完全锁定或二进制可逐字节复现。

## 脚本实际做什么

1. 校验 `version.py` 与脚本中的版本门禁一致（当前锁定 `6.0.0`）。
2. 执行离屏 pytest 门禁，排除真实触控层。
3. 使用 `MyScreenDraw.spec` 生成无控制台、禁用 UPX 的 onedir 包。spec 在依赖分析期间将 System32 放在 PATH 前，避免外部工具的同名系统 DLL（例如不兼容的 ICU）污染产物；分析结束后恢复环境。
4. 检查许可证、Qt 平台/图片/PDF/SVG 依赖，并拒绝用户数据、截图、源码和运行日志混入。
5. 执行构建目录中的 `--smoke-ui`，在函数内强制 Qt offscreen 并禁用软键盘启动，异常时也恢复调用方环境；清理验证产生的运行数据。
6. 写入 `RELEASE-MANIFEST.json`，包含应用版本、EXE SHA-256 和当前 `signature: none` 状态。
7. 打包 ZIP（排除 `data/`、`exports/`），执行 `release_artifact.py` 归档校验，再比对全部解压文件，并以同样的 offscreen 保护验证 EXE 启动与哈希。
8. 全部检查通过后，候选 ZIP 才提升为正式文件名，同时保存 `.sha256` 和 `build/release-receipts/` 下的验收收据。收据绑定包、EXE 及打包源码；不是数字签名。

成功构建后预期输出为 `dist/MyScreenDraw/`、`MyScreenDraw-v6.0.0-windows-x64.zip` 和同名 `.zip.sha256`。ZIP 根目录必须直接包含 `MyScreenDraw.exe`、`_internal/`、许可证和清单；不能额外套一层目录，也不能上传源码 ZIP 冒充便携版。

构建成功不等于实屏验收通过，也不会自动发布 GitHub Release。发布脚本要求干净工作树、指定提交等于 HEAD、远端提交存在，以及源码、清单、校验文件和验收收据一致；不会重写校验文件来认可未经验收的包。源码或构建脚本改变后需要重新打包，验证报告等文档可以在构建后补齐再提交。

## 下一版本必须同步的文件

- `version.py`：应用版本来源。
- `version_info.txt`：Windows 数值版本和完整 ProductVersion 字符串。
- `build.ps1`：硬编码版本门禁。
- `create_release.ps1`：版本门禁、标签、release notes 路径与 prerelease 标记。
- 中英文 README：源码版本与发布状态；便携下载链接及校验示例只指向已发布附件。
- `CHANGELOG.md`、对应版本的 release notes、`SECURITY.md`。
- 本页及其他描述“当前基线”的维护文档。

不要批量替换历史 release notes 的版本号。预览标签和 GitHub prerelease 标记应一致；正式版不能仍被标为预览。打包产物通过 Release 附件分发，不提交二进制包或用户数据到 Git。

## 每次正式版发布验收清单

以下为每个最终候选包重新核对的验收清单，不代表所有环境均已覆盖。6.0.0 历史证据、待复跑项及未覆盖环境见 [验证记录](release-validation-6.0.0.md)：

- [ ] 冻结功能；不存在已知的数据丢失、核心输入失效、崩溃或严重性能阻塞问题。
- [ ] [离屏回归](testing.md)通过，逐项解释跳过及未运行的测试。
- [ ] 最终 EXE 在目标触控大屏完成批注、鼠标穿透、多指、菜单、文字公式、白板和托盘验收。
- [ ] 用旧版配置和项目验证升级、独立笔形迁移、保存恢复；保留回退所需的数据备份。
- [ ] 验证下载失败、文件占用或权限失败时的更新行为，不损坏旧程序与用户数据。
- [ ] 完成长时间课堂使用和复杂页面压力验证。
- [ ] 记录 Windows 10/11、DPI 缩放、多屏、中文/空格路径、普通用户权限、无 Python 环境的实际覆盖范围。
- [ ] 验证断网及更新接口不可达时仍可启动和绘图。
- [ ] 校验便携 ZIP 内容、哈希、许可证、隐私清理和真实解压启动。
- [ ] 确认已知导出限制及未签名状态在用户文档中可见。

## 发布后验证

发布前先复核 `release-notes-v6.0.0.md` 草稿及验证记录，不能把历史日志或空白待填项写成最终通过。附件发布并核验后，才将 README 的 beta.8 下载/校验示例切换到 6.0.0，更新支持版本表及“未发布”状态。

从 GitHub Release 下载实际附件，不要只检查本地构建目录。比对 ZIP SHA-256，在新目录解压验证启动，确认版本显示、EXE 和 `_internal` 完整。Release 首屏和 README 提供便携 ZIP 直链，并明确 GitHub 自动生成的 Source code 附件不能直接运行。

签名策略见 [代码签名说明](code-signing.md)。仅更新文档或创建 commit 不会更新已发布 ZIP；不要声称旧附件包含后来改动。
