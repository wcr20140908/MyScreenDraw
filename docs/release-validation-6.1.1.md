# 6.1.1 发布验证

日期：2026-10-13（Asia/Shanghai）。基线 `bd0512d`；独立发行工作区 `D:/MyScreenDraw-worktrees/release-6.1.1`。

范围：落笔性能优化和四套界面配色，版本/资源统一6.1.1。不包含teaching模块、课程或教学入口；原教学开发分支单独继续6.2.0。

按用户最新要求缩小测试范围，未完成或宣称全仓回归；此前两次全量运行中止。构建门禁仅验证本次落笔、空间索引、缓存绘制、文档保存、主题实际切换与持久化，以及版本一致性。结果：**84 passed, 114 subtests passed in 14.33s**。全部GUI为offscreen，禁系统键盘钩子，使用临时合成数据；没有实屏或原生输入验证。

PyInstaller构建成功；许可证及Qt依赖检查通过；staging EXE离屏启动、ZIP结构检查、全部解压文件哈希对比、解压EXE离屏启动通过。收据中的unit_tests表示上述限定用例通过，不代表全仓测试。

- EXE SHA-256：`af7f8406ceda1ca6847d111bcb0d6b6c1aaf31193515f29145f41a6a16bcc824`。
- ZIP SHA-256：`ca24b783a74391cc1a5f12143333baaa846ca9cff43401d3eefe5315d58eb0aa`。
- 源码指纹：`de063916eb8b7e4b7aa94ddba6633b2ed9471b8a7e46a5973f32ca03f440332b`。
- 便携包：`MyScreenDraw-v6.1.1-windows-x64.zip`，随附同名`.sha256`。

状态：发布提交`d0eeaa7e7ada2b32d411cd867172b262ba7a2ee8`及标签`v6.1.1`已推送；2026-10-13 20:14:09（Asia/Shanghai）正式发布。GitHub发行ID为411633609，非草稿、非预览；ZIP附件44,058,085字节，校验文件102字节，服务器记录的SHA-256均与本地文件一致。匿名ZIP回下载超时，未将该项记为通过；没有因此重复构建或追加测试。合成离屏性能分析见`ink-latency-analysis-2026-10-08.md`，不等同触屏物理延迟。
