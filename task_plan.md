# 6.1.0 implementation and verification plan

## Objective / acceptance
Preserve the complete requested scope. Keep extensive offscreen verification. Latest explicit user instruction (2026-10-06) now authorizes and requests extensive real-screen testing, superseding the earlier offscreen-only restriction. Real tests must use isolated synthetic data and operate only owned application windows. At most one child agent is active at a time. Never write credentials into tracked files or logs.

## Design / decisions
Use incremental changes around the existing PyQt6 application rather than a rewrite. Keep the complete document independent of visible whiteboard mode; desktop annotation edits its active page; revision-keyed caches and immutable serialization snapshots feed background persistence. Keep Qt painting on its owning thread and stream one export page at a time. Modal unsaved-content and partial-export dialogs are required. Retain compatibility with existing projects. New controls follow the current page rail/settings patterns. PDF import creates one board page per PDF page. Page copy placement defaults after source, with before/front/back choices. Teaching-feature discussion is an assessment, not an unrequested feature build.

## Phases
- [complete] 1. Inspect and reproduce data-loss/open failures; run full offscreen baseline.
- [complete] 2. Fix document state, readable atomic writes, unsaved guards (open/update/exit).
- [complete] 3. Revision-aware background autosave, recovery history preview, interval settings.
- [complete] 4. Streaming PNG/PDF exports, cancellation/progress/failed-page dialogs; PDF page import.
- [complete] 5. Page duplicate/rename/drag reorder; revision/visible-first thumbnails.
- [complete] 6. Baseline stroke rendering benchmark then completed-path/bounds and incremental stroke caches.
- [complete] 7. Monitor settings and timer-end volume default 100; teaching feature assessment.
- [complete] 8. Full offscreen regressions, package smoke/reopen verification, 6.1.0 release evidence and publish.

## Requirement evidence matrix
Each phase must record relevant tests and commands in progress.md, with explicit release acceptance in docs/release-validation-6.1.0.md. A green test unrelated to a requirement is not evidence for it. Native Windows testing is explicitly authorized by the latest instruction. Keep native-input runs serial, synthetic and isolated; monitor selection is checked by code and synthetic screens without changing the OS primary monitor.

## Errors
Custom autosave selector resynchronized itself to its preceding preset; fixed and verified. Legacy update tests needed separate install-confirmation and Save/Discard/Cancel dialog results. Compression-by-suffix prevented reopening renamed files; regression reproduced, magic-byte reader implemented.

## Final acceptance
All implementation and local/public release phases are complete. Version 6.1.0 is published at release commit bfd172c5d15546b7a8c4b0181d7821f55fe71646. Public assets match the accepted ZIP/EXE hashes and extracted smoke exited 0. Hardware limits are explicit in docs/release-validation-6.1.0.md. Final documentation follow-up and clean remote status are checked before closing the goal.


---

# 6.3.0 双更新线路与双平台发布

## 目标与授权

用户授权：核实 GitCode 仓库，新增 GitHub／GitCode 更新线路，真实检查／下载／校验／安装；完成 commit、push、打包及两边 release。本地 agent.md 保存授权和凭据，绝不提交、上传、打包或打印。已有工作树改动均为待纳入6.3.0的前序功能；保留用户数据和私有证据。

## 阶段

1. [in_progress] 核实两平台真实 API、匿名更新与附件访问、发布与 Git 认证；记录可信下载域名和限制。
2. [pending] 已授权方案细化，GitHub Issue 跟踪；新增线路偏好、统一发布模型、校验清单、下载与界面同步，兼容现有稳定／预览与关闭自动检查偏好。
3. [pending] 回归、版本统一6.3.0、更新说明和文档链接，完成源代码与凭据隔离审计。
4. [pending] commit并push同一源码至两平台，确认同一提交／标签；归档旧构建目录并生成候选ZIP、收据及校验文件。
5. [pending] 最终解压EXE、教学资源、更新事务／旧数据保留、隔离原生界面与触控验证，完成接受收据。
6. [pending] 同一包上传两平台（先draft或等价预发布保护），核对远端附件；公开后匿名回下载校验两边SHA-256，确认实际线路能检查／下载；更新正式README和收据状态。

## 约束

正常客户端不含维护者token；所有请求必须可匿名执行。agent.md只在本机，Git和ZIP双重检查。新线路元数据、附件URL和重定向继续限制可信来源，不能削弱路径／体积／EXE／版本验证。当前6.2.0公开包不替换，6.3.0新标签不得覆盖既有发布。保留失效历史说明时优先归档与修正链接，避免恢复被删除的根目录旧文件。

## 错误

- 先前独立代码审查代理有 Azure 资源不匹配，若本次仍不可用，主代理逐项审查并如实记录。
