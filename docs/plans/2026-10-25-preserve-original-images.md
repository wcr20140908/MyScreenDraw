# 保留原图 Implementation Plan

**Goal:** 增加默认开启、可在设置中关闭并持久保存的“保留原图”，保护所有导入图片及 PDF 页。

**Architecture:** 使用应用级布尔偏好 preserve_original_images，不修改 .msd 页面格式。画布统一排除受保护图片的选择与变换；擦除和清空只处理批注。新旧页面立即适用，关闭后图片恢复可编辑。图像位于批注下方，屏幕与导出顺序一致。

**Tech Stack:** Python、PyQt6、JSON 配置、pytest。

## 已确认方案

用户已确认名称“保留原图”、默认开启、可设置，以及擦除／清空保留原图、避免误拖动的行为。设置中使用普通复选框，沿用当前字号和主题；说明仅一句“擦除和清空保留原图；关闭后可调整图片。”。关闭时恢复图片选择、移动、缩放、旋转、复制、删除、擦除及清空。切换不改图片内容，不加入文档撤销记录。整页复制、删除整页、撤销导入、新建／打开项目继续按原流程执行。教学中的图片变换练习显式在私有练习环境关闭该选项，不修改日常设置。

## Task 1: 偏好与界面

修改 main.py 的初始化、collect_settings、load_settings、set_preserve_original_images；在 document_preferences.py 中增加复选框并同步状态；i18n.py 增加八语言文案。缺少字段和非布尔值回退 true；false 能可靠保存、重启读取。

## Task 2: 图像保护

在 DrawingCanvas 中统一过滤受保护图片选择；覆盖点选、框选、导入自动选择、选择删除／复制／移动／缩放／旋转，开启时清除已有图片选择。execute_erase 和 ControlPanel.clear 保留图片，只有图片时清空为无操作。调整 draw_content、hit_object_at 和 eps_export.py 的叠放顺序，确保批注在图像上可见。

## Task 3: 回归与教学

新增 tests/test_preserve_original_images.py，使用 tests/test_upgrade_settings.py 的隔离 rig。先运行失败测试，再实现：默认值／非法旧配置／关闭后重新加载；实际复选框点击；圆形和整笔擦除；清空及撤销／重做；点选／框选／变换；已有图片／新图片／PDF 独立页面；项目往返及导出可见性。需要编辑图片的旧测试和 C09 私有练习显式关闭保护，并保留对默认开启的独立覆盖。

## Task 4: 验收

运行定向 pytest，再运行媒体导入、独立 PDF 页、选择、撤销、多点触控、设置、升级保存、导出和 C09 教学相关回归。使用隔离合成数据检查真实设置页面及图片批注行为，保存私有证据。更新 README 与 docs/testing.md；检查 diff 保留本轮之前的未提交工作。本轮不构建或发布新 EXE。
