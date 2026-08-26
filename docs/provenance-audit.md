# 代码来源审计 / Code Provenance Audit

**审计日期**：2026-08-17
**审计版本**：v5.2.1
**审计目的**：确认代码库中不存在与 GPL-3.0-or-later 不兼容的第三方代码，
满足 GitHub 开源发布的合规前提。

> 免责声明：本审计为工程尽职调查，不构成法律意见。

---

## 1. 审计范围

| 文件 | 行数 | 结论 |
| --- | ---: | --- |
| `main.py` | ~6,500 | 原创 |
| `display_utils.py` | 146 | 原创 |
| `persistence.py` | 133 | 原创 |
| `i18n.py` | ~90 | 原创 |
| `calculator.py` | 45 | 原创 |
| `version.py` | 3 | 原创 |
| `tests/*.py` | ~900 | 原创 |
| `build.ps1`、`MyScreenDraw.spec` | ~50 | 原创（基于 PyInstaller 官方模板结构） |

---

## 2. 自动化扫描结果

### 2.1 第三方版权 / 许可证声明

```powershell
Select-String -Path *.py,tests\*.py `
  -Pattern "Copyright|copyright|\(c\)\s*[0-9]{4}|SPDX|Licensed under|GPL|MIT License|BSD|Apache"
```

**结果：0 处命中。**

代码中不存在任何遗留的第三方版权头或许可证声明，
说明没有整段复制带许可证头的外部源码。

### 2.2 复制来源标记

```powershell
Select-String -Path *.py,tests\*.py `
  -Pattern "stackoverflow|StackOverflow|gist\.github|copied from|adapted from|based on http|from https?://"
```

**结果：0 处命中。**

### 2.3 外部 URL 引用

```powershell
Select-String -Path *.py,tests\*.py -Pattern "https?://"
```

**结果：0 处命中。**

代码中没有指向外部代码片段的链接，也不存在运行时下载行为。

### 2.4 依赖盘点

对全部 `import` / `from ... import` 语句去重后，模块清单为：

**Python 标准库**
`__future__`、`ast`、`csv`、`ctypes`、`datetime`、`importlib`、`json`、`logging`、
`math`、`os`、`pathlib`、`random`、`re`、`sys`、`tempfile`、`threading`、`time`、
`typing`、`unittest`、`uuid`、`winsound`

**第三方**
`PyQt6`（GPL v3 / 商业）、`PyQt6.QtSvg`（随 PyQt6 分发，GPL v3 / 商业）、
`PyQt6.QtPdf`（随 PyQt6 分发，GPL v3 / 商业）、`pynput`（LGPL-3.0）

**项目自有**
`calculator`、`display_utils`、`i18n`、`main`、`persistence`、`version`

**结论**：无隐藏依赖，无与 GPL-3.0-or-later 不兼容的第三方库。

---

## 3. 关键算法来源说明

以下算法为本项目自行实现的通用数学方法。这些方法本身属于公有领域的数学知识
（教科书内容），不受版权保护；此处说明实现来源以备查。

| 位置 | 算法 | 来源性质 |
| --- | --- | --- |
| `StrokeShapeRecognizer._pca` | 二维主成分分析（协方差矩阵特征向量） | 标准线性代数，自行实现 |
| `StrokeShapeRecognizer._resample_closed` | 等弧长重采样 | 标准数值方法，自行实现 |
| `StrokeShapeRecognizer._detect_corners` | 弦角法拐点检测 + 非极大值抑制 | 通用思路，自行实现 |
| `StrokeShapeRecognizer._fit_round` | 代数圆拟合（Kåsa 型线性最小二乘） | 教科书方法，自行用高斯消元实现 |
| `StrokeShapeRecognizer._fit_ellipse` | 基于 PCA 轴系的椭圆参数估计 | 自行实现 |
| `StrokeShapeRecognizer._solve3` | 3×3 高斯消元（带主元选择） | 教科书方法，自行实现 |
| `StrokeShapeRecognizer._poly_residual` | 点到线段最短距离 | 标准几何公式 |
| `calculator.py` | AST 白名单表达式求值 | 自行实现（Python 官方推荐的 `eval` 替代思路） |
| `persistence.atomic_write_json` | 临时文件 + `fsync` + `os.replace` | POSIX/Win32 通用原子写惯例 |
| `disable_touch_gestures` | `SetProp` + `MicrosoftTabletPenServiceProperty` | Microsoft 官方文档记载的公开 API 用法 |

**说明**：`disable_touch_gestures` 中使用的 `TABLET_DISABLE_*` 常量值来自
Microsoft 公开文档（"Disabling the press and hold gesture"）。
常量数值属于 API 接口事实，不构成受保护的表达。

---

## 4. 资源文件

| 类别 | 结论 |
| --- | --- |
| 字体 | **未内置任何字体文件**。界面通过字体族名（如 `Microsoft YaHei`、`Consolas`）引用系统字体 |
| 图标 | **无图标文件**。旋转键等图标由 `make_rotate_icon()` 在运行时用 `QPainter` 绘制 |
| 图片 | 仓库中无随程序分发的图片素材 |
| 音频 | 计时提醒使用 `winsound.Beep()` 生成，无音频文件 |
| Unicode 符号 | 界面使用 `▲▼×⋯↺⠿🌈` 等标准 Unicode 字符，非第三方素材 |

`screenshots/` 中现有文件包含开发环境窗口、用户名路径、终端输出或其他桌面内容，**不得提交到公开仓库或发行包**。README 暂不引用这些截图；发布新的产品截图前，必须只保留 MyScreenDraw 界面并人工检查隐私信息。

---

## 5. 风险项与处置

| 风险 | 状态 | 处置 |
| --- | --- | --- |
| PyQt6 为 GPL/商业双许可，非 LGPL | **已识别** | 项目采用 GPL-3.0-or-later，兼容 GPL v3 版 PyQt6 |
| pynput 为 LGPL-3.0 | 已识别 | 与 GPL-3.0-or-later 兼容 |
| Qt 运行库含 LGPL 与 GPL 组件 | 已识别 | GPL-3.0-or-later 可满足两者 |
| 发行包未附许可证文本 | **待处理** | 见第 6 节：打包时须包含 `LICENSE` 与 `THIRD_PARTY_LICENSES.txt` |
| 截图包含个人或环境信息 | **已处置** | 现有截图禁止提交；README 不引用，`.gitignore` 排除 `screenshots/`；新截图须人工复核 |
| `data/roster.json` 含学生姓名 | 已处置 | `.gitignore` 已排除，且不随发行包分发 |

---

## 6. 发布前必办事项

- [x] 添加 `LICENSE`（GPL-3.0 官方全文）
- [x] 添加 `THIRD_PARTY_LICENSES.txt`
- [x] 锁定依赖版本（`requirements.lock`）
- [x] 源文件添加 SPDX 许可证标识
- [x] 打包时将 `LICENSE` 与 `THIRD_PARTY_LICENSES.txt` 纳入发行包
      （v5.0.0 起由 `MyScreenDraw.spec` 的 datas 带入发行包）
- [x] **禁止提交当前 `screenshots/` 目录**（含开发环境信息；新产品截图须先人工脱敏）
- [ ] **确认 Git 历史中未提交过 `data/roster.json`、`data/config.json` 等用户数据**
      （若仓库为新建则不适用）

---

## 7. 复核方法

任何人可用以下命令复核本审计：

```powershell
# 第三方版权声明
Select-String -Path *.py,tests\*.py -Pattern "Copyright|SPDX-FileCopyrightText|Licensed under"

# 复制来源标记
Select-String -Path *.py,tests\*.py -Pattern "stackoverflow|gist\.github|copied from|adapted from"

# 依赖清单
Select-String -Path *.py,tests\*.py -Pattern "^\s*(import|from)\s+"
```

预期结果：除本项目自行添加的 SPDX 标识外，无第三方版权声明；无复制来源标记；
依赖仅限标准库、PyQt6、pynput 与项目自有模块。
