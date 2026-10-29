# 6.3.0 构建与离屏验收记录

记录日期：2026-10-29。修复教学计算器退出阶段的 Qt 对象销毁顺序后，正式包已通过下述离屏验收。此前被拒候选不供发布。**本轮按用户要求只采用离屏验收，不把原生桌面或物理触控列为通过项。** 同一验收包已在 GitHub 和 GitCode 正式发布，并完成公开附件和客户端双线路的匿名验证。

## 完整构建与字节绑定

继承并复核前轮完整 `build.ps1` 日志和最终提升的验收收据：4096 项收集，4089 passed、7 skipped、3744 subtests passed，用时 804.47 秒；三个 worker，`--dist=loadfile`。7 项跳过未计入通过，既有离屏门禁排除三个真实触控注入文件。PyInstaller、教学资源、暂存/解压 EXE 冒烟、归档/解压文件核对和源码收据门禁完成。

本轮重新执行 `release_artifact.verify_release`，源码快照、ZIP/EXE 字节、校验文件和既有收据一致。没有重新生成收据给未经构建验证的包放行；仅测试与文档收尾不影响已验收的打包输入。

| 对象 | SHA-256 |
| --- | --- |
| 6.3.0 ZIP | `14c231cc1c92e7f49ff9198c7f196bf2c68b5a15338795b741d8518bd25c0195` |
| 6.3.0 EXE | `aa08467de6a54bc3ef1a5052e3664f45c612d8372dfd7fb477f767b681a8d490` |
| 源码快照 | `135dfd60807dd0d01aad328ca59c606e3b5b7eed6391a50203c72590737c3650` |

## 本轮新执行的离屏验收

- 48 章教学：每章启动全新的真实冻结 EXE 子进程，检查 hello/ready/activated、暂停、恢复、停止、IPC 和私有目录清理、父工作状态恢复一次。48 项全部通过，退出均为 NormalExit / 0；未冒充课堂业务动作或章节完成验收。
- 计算器专项：基础与科学章节各重复两次，共 4 项全部通过，绑定上述已验收 EXE；不再出现旧候选的 CrashExit -1073741819。
- 6.2.0 → 6.3.0：真实冻结包、合成数据，安装事务与自动重启 29.78 秒；手动重新打开冒烟通过，4 个合成文件、5 项偏好和 GitCode 线路设置保留。并非独立手动换目录迁移验收，也不是旧 6.2.0 内嵌更新器的在线端到端验收。
- 文档往返：真实解压 EXE 的离屏恢复、异步自动保存、内容/偏好往返通过；自动保存版本为 v6.3.0，最终 ZIP/EXE 哈希与上表一致。
- 针对性回归：`python -B -m pytest tests/test_teaching_calculator_teardown.py tests/test_teaching_safety_review.py tests/test_update_sources.py tests/test_update_notes.py tests/test_release_artifact.py tests/test_publish_release_state.py -q`：185 passed、58 subtests passed，39.44 秒。

前轮两个仅涉及测试等待时间的改动保持原业务断言；新增慢线程回归确保等待完整，而非删除失败或放松内容校验。

## 拒绝候选与原生范围

旧候选 ZIP SHA-256 `430651c1b329fb98601d53435154deb9d543848b915802522930dcaffe917021`、EXE SHA-256 `7b7d4f3c0d76caa709ef53494e709e4471e4328ff9131c3b466567d6ccb03148` 只用于识别被拒字节，绝不作为最终附件值。

用户明确要求离屏后不继续实屏操作。此前一次隔离原生尝试未通过且不计入验收；其拥有的进程正常停止、私有目录清理，无残留 MyScreenDraw.exe。物理教学触屏、Windows 11、多屏混合 DPI、实际听感及长期课堂体验仍需目标设备验证。Ed25519 更新描述文件签名不是 Windows Authenticode；EXE 未进行代码签名。

## 发布状态

2026-10-29：两平台正式发布 v6.3.0。发布时两平台 main 与版本标签均为验收提交 `d12e1e03a379d574c64c1ddfb5fd9a8310ba0ec1`；签名描述文件绑定同一提交。GitHub 为非 draft、非 prerelease，GitCode 匿名响应明确为 `latest`，不是 pre。

两平台各三个附件均已匿名完整回下载；ZIP、checksum、签名描述文件的大小与 SHA-256 一致。ZIP 为 48,844,355 字节，checksum 为 102 字节，描述文件为 497 字节。除上表 ZIP/EXE 外，checksum 文件 SHA-256 为 `1151065e9bf2e3b37535c83fd207cbbdb91c89aeeecfc505a69cb6b182ffc435`，描述文件 SHA-256 为 `d636eb12b060f5fcddc233feb4d3830516311adbc1541acca3181e8ad3b1218d`。

真实调用客户端 `fetch_release`、`fetch_release_notes`、`UpdateDownloadWorker`，不注入维护者 token、不替换网络函数；两线路均读取 v6.3.0、说明一致、完整下载并通过签名/本地归档/源码/EXE 哈希绑定。版本检查使用默认 6 秒超时，下载使用默认 15 秒 socket 超时。GitHub 使用本机既有代理，GitCode 在隔离子进程直连官方 HTTPS；未修改系统代理。GitCode 一次匿名 429 无 Retry-After，退避 120 秒后真实客户端检查、说明及下载通过；这不保证未来服务不再限流。

从 GitHub 公开回下载 ZIP 新目录解压后，文件核对与真实 EXE 的 `--smoke-ui` 离屏启动退出码 0；GitCode 公开包与其字节完全相同。最后重新核对最终验收收据和签名描述文件通过。

[GitHub 正式页面](https://github.com/wcr20140908/MyScreenDraw/releases/tag/v6.3.0) · [GitCode 便携包匿名下载](https://api.gitcode.com/api/v5/repos/wcr20140908/MyScreenDraw/releases/v6.3.0/attach_files/MyScreenDraw-v6.3.0-windows-x64.zip/download)。证据与合成数据保持本地，不公开凭据、私钥、真实用户数据或桌面截图。

本页正式结果是在发布后完成的纯文档跟进；后续文档提交不移动 v6.3.0 标签、不重签已有描述文件、不改发布包。验收源码快照与最终包持续一致。

## 独立审查与最终发布门禁

独立审查未发现计算器 Qt 清理补丁阻断问题；其另外提醒，基础构建收据不包含构建之后的冻结验收。本次增加仅本地的最终发布入口：不可覆盖收据绑定提交、ZIP/EXE/源码快照及上述四组 JSON 证据哈希；签名、发布前最后校验、结束后都重新核对。新包正对照通过，旧拒绝 ZIP 负对照被拒绝。该入口不改变已验收产品输入，凭据仍只由子进程环境注入。

文档/许可证/版本和计算器面板补充回归：82 passed、252 subtests passed，5.31 秒。

## 发布故障与恢复边界

GitHub 草稿按 tag 读取返回 404，私有入口只定位唯一同 tag 的 draft 再按 ID 读取，保留名称/正文/状态/附件门禁。GitHub 三附件完整回读通过后，恢复时仅复用同一不可变资产 ID、大小及服务端 SHA-256 digest 的已核验字节；公开后再次完整匿名下载，未用缓存代替公开验收。GitCode 初次流式 PUT 因系统代理超时，保留 pre、确认缺失附件，再通过官方预签名 HTTPS 地址进行有界 curl 上传，并完整核对远端字节。没有覆盖不同附件、强推、修改全局 Git/代理配置或向客户端加入访问凭据。

平台下载使用量包含 Clone、Pull、源码 ZIP 和 Release 附件请求；本次完整验证、Range 探测和重试会贡献统计，不能将累计下载次数视为独立真实用户数。
