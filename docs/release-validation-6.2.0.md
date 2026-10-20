# 6.2.0 本次发行验证记录

日期：2026-10-20（Asia/Shanghai）。本次包含当前工作树的页面列表、教学交互和构建修复。

用户明确要求尽快发布、不进行实屏测试，并省略额外验证；本轮采用相关回归、构建检查和包校验。最初的全量扫描已中止，不能记为全量通过；未执行物理触屏、原生桌面输入、长时间课堂测试或额外的冻结包逐章流程。

## 测试与修复

- 页面与课堂偏好定向回归：63 passed、10 subtests passed。
- 中断框选及选择业务回归：123 passed。修复旧选框在下一次按下时未清理、松开后覆盖点选结果的问题。
- 更新说明和更新器独立进程回归：27 passed。
- 精简综合回归：363 passed、243 subtests passed，另有1项文档措辞失败。唯一失败来自安全说明中的“完全离线环境”触发绝对离线措辞检查；改为“断网运行环境”后，发布元数据检查9 passed、176 subtests passed。
- 最终构建相关回归：78 passed、176 subtests passed。范围为 `test_release_hygiene.py`、`test_build_dependencies.py`、`test_teaching_packaging.py`。
- 实际 PyInstaller 构建发现 spec 的 `globals().get("SPEC", __file__)` 会提前求值未定义的 `__file__`。补充无 `__file__` 的 PyInstaller 命名空间用例，先复现失败，再改为惰性回退；现有 runpy 场景和新场景均通过。

以上执行范围存在重叠，不相加作为唯一用例数。综合回归包含400步单屏教学进程用例；这是离屏控件与业务驱动，不是实屏验收。

## 便携包

- 文件：`MyScreenDraw-v6.2.0-windows-x64.zip`
- ZIP SHA-256：`b4556978692ad2b64beab07c02463cb63937359ec2e3bd78dc80b7fdb546658f`
- EXE SHA-256：`f1ec9b19a0944373939e9598546aff10db800472b4597dac88ce81e363b7fe4b`
- 源码快照 SHA-256：`3006fc5add01c033f82ad143eea5b3a276175af72ff2d21daed572b4d7e00fd5`
- 包内66个教学资源通过精确路径及字节校验；归档结构、依赖、许可证、隐私内容检查通过。
- 构建目录和解压目录中的 EXE 均通过 `--smoke-ui`，强制 Qt offscreen 并禁用软键盘。
- PyInstaller 完成后会话在压缩阶段中断；核对原测试日志及源码快照一致后，从原 `build.ps1` 的包检查阶段续接，并重新完成 staging smoke、压缩、解压比对及 extracted smoke。没有重复编译或改写验收收据绕过校验。
- 验收收据由原构建逻辑生成，保存在本地 `build/release-receipts/`；原始日志和运行记录留在 `.git/release-validation/620-20261019/`，不进入便携包。
- 仓库 `data/` 与 `exports/` 的102个原有文件在本轮前后哈希一致。

环境：Windows 10 19045、Python 3.11.9、PyQt6/Qt 6.11.0、pytest 9.1.1、PyInstaller 6.21.0。程序未使用代码签名。
