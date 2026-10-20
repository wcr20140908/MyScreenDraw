# C10 导出课程交付

2026-10-13（Asia/Shanghai）。三章17步：formats(7)、progress_cancel(4)、result(6)。38个文案键、304条八语言字符串，三份自产私有练习项目。

实现实际PNG/PDF/SVG/EPS文件导出；真实进度取消按钮；私有示例空目录令第2页写入失败，确认部分导出后清除该空目录重试。完整成功、取消、部分失败分别判定，错误格式不推进；原工作和普通导出不使用示例路径。

验证：`tests/test_teaching_export_courses.py tests/test_teaching_export_adapters.py`为7 passed；`tests/test_teaching_export_process.py`为1 passed（27.06秒），同一实际QProcess完成C01–C10共35章314步和7次C10导出校验。原父现场、文档、undo/redo和配置/自动保存/导出文件哈希恢复或保持，练习根退出后清理，子进程正常退出。

按用户速度优先要求只运行直接相关验证；没有全仓回归、实屏或原生输入。结果框UI未单独验收，不能把测试中的结果采集代替模态窗口验收。
