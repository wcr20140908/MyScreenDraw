# GitHub/GitCode 双线路与 6.3.0 发布实施计划

**Goal:** 用户可选择国外线路（GitHub）或国内线路（GitCode），两平台发布同一已验收的 6.3.0 便携包。关联 GitHub Issue #18。

**Architecture:** 更新来源与稳定/预览频道独立。旧设置默认 GitHub，后台工作捕获来源并拒绝过期响应；国内线路只使用公开 Release 附件。6.3.0 起从两平台读取由同一 Ed25519 公钥验证的描述文件，绑定 ZIP 大小、SHA-256、版本、EXE 哈希和源码提交；下载安装归档验证在本地完成。

**Tech Stack:** Python 3.11、PyQt6、urllib、cryptography Ed25519、PowerShell、GitHub/GitCode API。

## 1. 来源和完整性
- 新建 update_sources.py，定义两个官方 API/附件地址、公钥和有界签名校验；添加 tests/test_update_sources.py 的合法附件、预览、来源归档拒绝、签名篡改、大小/哈希不符用例。
- main.py 复用现有 urllib 注入，按来源检查 Release 和精确版本说明，下载时流式计算哈希。
- 新建 sign_update.py，从本地密钥签名已通过 release_artifact 验收的包；凭据和私钥不进入源码或包。
- 验证命令：python -m pytest tests/test_update_sources.py tests/test_beta6_updater.py tests/test_updater_601.py -q。

## 2. 设置和说明
- main.py、i18n.py 增加 update_source 和双线路选择；切换时清空候选/NEW，捕获 (source, channel)，下载期间拒绝改源。
- update_notes.py 为说明缓存增加来源作用域，保留既有安装历史；源切换忽略旧线程结果。
- tests/test_upgrade_settings.py 审计新的持久化字段；新用例覆盖来源切换及说明隔离。

## 3. 发布输入
- version.py、version_info.txt、build.ps1、create_release.ps1 统一 6.3.0。
- 同步 requirements 和 THIRD_PARTY_LICENSES.txt；补齐历史说明链接。
- 更新 README、release-notes-v6.3.0.md、docs/releasing.md；记录已覆盖范围和真实剩余边界。
- 本地 Git hook 检查 agent.md 和凭据，package gate 拒绝本地文件；既有 hook 先检查再保留。

## 4. 验收与发布
- 全离屏回归、提交全部既有授权功能（排除 data 和本地记录），快进推送两平台 main。
- 归档旧 build/dist 后执行 build.ps1；检查暂存/ZIP/解压 EXE、依赖/教学资源和收据；隔离成品升级与原生交互。
- 验收后签名描述文件；核对两远端源码一致，创建版本标签。GitHub draft 与 GitCode pre 上传 ZIP/校验/签名描述文件，逐个核验后正式发布。
- 两平台公开匿名回下载比对哈希，真实 fetch_release 检查两条线路；更新 Issue #18 与本地验收记录。

凭据仅位于本地 agent.md（被 .gitignore 与 .git/info/exclude 排除）。长久私钥只位于 .git/keys。发布、推送、实屏验证已有用户授权。
