# 贡献指南 / Contributing to MyScreenDraw

感谢你愿意参与。MyScreenDraw 面向**教室触控大屏**，
所以本项目对"在讲台上不会出错"的要求高于"功能多"。

---

## 1. 快速开始

### 环境要求

- Windows 10 / 11（程序使用 Win32 API，暂不支持 macOS / Linux 运行）
- Python 3.10 – 3.12（开发基线为 3.11）

### 搭建

```powershell
git clone https://github.com/<owner>/MyScreenDraw.git
cd MyScreenDraw

python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 可复现安装（推荐）
pip install -r requirements.lock

# 需要打包时再装构建依赖
pip install -r requirements-build.lock
```

### 运行

```powershell
python main.py
```

按 **F12** 退出程序（全局热键，全屏画布下也有效）。

### 跑测试

```powershell
python -m unittest discover -s tests
```

测试全部在**离屏模式**下运行（`QT_QPA_PLATFORM=offscreen`），不会弹窗、不会抢屏，
可以安全地在开发机上反复执行。

### 打包便携版（Windows）

```powershell
.\build.ps1
```

构建结果位于 `dist/MyScreenDraw/`（PyInstaller onedir），整目录压缩为 ZIP 即得便携版。
构建脚本会随包分发 `LICENSE` 与 `THIRD_PARTY_LICENSES.txt`（GPL 合规），
`MyScreenDraw.spec` 已关闭 UPX 压缩以降低杀软误报率。

---

## 2. 项目结构

```text
main.py                 主程序：画布、控制面板、识别器（体积大，正在渐进拆分）
display_utils.py        屏幕/DPI/直尺/量角器的纯函数（无 Qt 依赖，易测试）
persistence.py          项目文件 schema、校验、原子写入
calculator.py           基于 AST 白名单的安全表达式求值
i18n.py                 界面文案与语言选择
version.py              唯一版本号来源
tests/                  单元与回归测试
docs/                   架构、发布、签名、代码来源审计等文档
```

### 三个核心类（都在 `main.py`）

| 类 | 职责 |
| --- | --- |
| `DrawingCanvas` | 全屏透明画布：笔迹、图形、文本、选择、教具、撤销栈 |
| `ControlPanel` | 悬浮工具栏、所有子菜单、设置持久化、窗口置顶管理 |
| `StrokeShapeRecognizer` | 纯几何的手绘图形识别（无模型、无网络） |

> `main.py` 目前偏大，我们正按 `docs/architecture.md` 的计划**渐进**拆分。
> 请**不要**提交"大规模重写 main.py"的 PR，它无法被安全审查。
> 小步、可测试、单一职责的拆分 PR 非常欢迎。

---

## 3. 提交流程

1. 先开 Issue 讨论（Bug 除外，小 Bug 可直接 PR）
2. 从 `main` 切分支：`fix/xxx`、`feat/xxx`、`docs/xxx`
3. 编码 + **补测试**
4. 本地跑通 `python -m unittest discover -s tests`
5. 提交 PR，填写模板

### 提交信息

建议使用 Conventional Commits：

```text
fix(canvas): 停笔定形后继续书写不再另起一笔
feat(export): 支持导出 SVG
docs(readme): 补充快捷键表
test(layout): 锁定横版白板区不被撑高
```

---

## 4. 代码规范

### 硬性要求

- **Python 3.10+ 语法**，4 空格缩进，遵循 PEP 8
- **不要引入新的第三方依赖**，除非在 Issue 中讨论并达成一致
  （每多一个依赖都会增大发行包体积并带来许可证问题）
- **所有面向用户的文案必须走 `tr()`**，禁止在界面里硬编码中文或英文
  （见 `i18n.py`；新增文案要同时补齐全部语言）
- **不要用裸 `except Exception` 吞掉错误**。请捕获具体异常
  （`OSError` / `ValueError` / `json.JSONDecodeError` / `RuntimeError` 等），
  并通过 `notify_user()` 给出用户能看懂的提示
- **Qt 虚函数（如 `paintEvent`）内不得抛出异常**：PyQt6 遇到未捕获异常会直接终止进程

### 注释

本项目的注释风格是**解释"为什么"，不复述"做了什么"**。
尤其是涉及 Win32 窗口层级、触控手势、Qt 布局这些反直觉的地方，
请写清楚**踩过什么坑**，否则后来者会把修复改回去。

反例：

```python
self.timer.stop()   # 停止定时器
```

正例：

```python
# 弹出期间必须停掉置顶心跳：心跳里的 force_topmost(画布) 会把全屏画布拉到置顶层最顶端，
# 这个 QMenu 没有 owner 保护，500ms 内就会被画布盖住。
self.timer.stop()
```

---

## 5. 测试要求

| 改动类型 | 测试要求 |
| --- | --- |
| 修 Bug | **必须**先写一个能复现该 Bug 的失败测试 |
| 新功能 | 覆盖正常路径 + 至少一个边界情况 |
| 布局/UI | 用尺寸断言锁定（参考 `tests/test_touch_layout.py`） |
| 识别算法 | 用合成笔迹做准确率断言，不要只测单个样例 |
| 纯函数 | 直接单测（`display_utils.py`、`persistence.py`、`calculator.py`） |

写 UI 测试的技巧：`tests/test_touch_layout.py` 里有构造真实
`QMouseEvent` 驱动完整"按下→拖动→停笔→抬笔"链路的例子，可直接借用。

---

## 6. 触控大屏注意事项

这是本项目最容易翻车的地方，改动前务必了解：

1. **不要给按钮加全局 `min-height`**
   Qt 样式表里 `min-height` 会和上下 `padding` **相加**。
   v4.8.0 就因此把每颗按钮撑到 50px 以上，整条工具栏变形。
   要放大触控目标，请调整具体控件，不要动全局 `QPushButton` 规则。

2. **触屏没有右键**
   程序主动关闭了 Windows 的"按住变右键"手势（否则会打断停笔定形）。
   因此任何**只能靠右键完成**的操作，都必须再提供一个可点击入口
   （例如教具的红色 ✕、图形工具的"取消取点"按钮）。

3. **窗口置顶很脆弱**
   画布是全屏置顶窗口，面板必须显式排在它之上。
   新增浮动窗口时，记得加入 `bind_topmost_stack()` 管理的列表。



---

## 7. 许可证

本项目采用 **GPL-3.0-or-later**（见 `LICENSE`）。

提交 PR 即表示你同意：

- 你的贡献以 GPL-3.0-or-later 授权；
- 你有权提交这些代码（不是从不兼容许可证的项目复制而来）。

**特别提醒**：请勿从许可证不兼容的项目（例如 MIT 之外的专有代码、
或任何未经授权的商业软件）复制代码。若你参考了其他开源项目的实现，
请在 PR 描述中注明来源与其许可证，我们会记入 `docs/provenance-audit.md`。

---

## 8. 需要帮手的方向

| 方向 | 难度 | 说明 |
| --- | --- | --- |
| 英文/其他语言翻译 | ⭐ | `i18n.py`，改动集中、风险低 |
| 真机测试反馈 | ⭐ | 有触控大屏就能帮上忙 |
| 文档与教程 | ⭐ | 用户手册、录屏 |
| 手绘识别准确率 | ⭐⭐⭐ | 需要几何功底与评测意识 |
| `main.py` 渐进拆分 | ⭐⭐⭐ | 见 `docs/architecture.md`，务必小步 |
| 性能优化（空间索引） | ⭐⭐⭐ | 大页面命中测试与重绘 |

---

## 9. 行为准则

参与本项目即表示你同意遵守 [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)。
