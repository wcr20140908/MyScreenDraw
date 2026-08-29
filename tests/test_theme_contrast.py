"""主题下的文字可读性。

由来：5.4.x 里「粗细: 4」这一行标签的样式写死了 ``color: white``，而它所在的 ``.Sub``
面板在亮色主题下背景是 ``#edf2f7``。白字白底，实测对比度 1.13 —— 那一行在亮色主题下
等于消失了。代码审查看不出这种问题（两处都「看起来没错」），只有把颜色配对起来算才
看得出，所以这里量的是**渲染出来的实际配色**，不是「代码里写了什么」。

阈值取 WCAG AA 的 3.0（粗体/大字号档）。界面标签多是加粗小字，正文档 4.5 更严，
但主题里有几个刻意的低对比提示色（次要说明文字），一律按 4.5 卡会逼着改设计；
3.0 足以挡住「白字白底」这一类真正读不出来的情况。
"""
import os
import re
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MIN_RATIO = 3.0


def _relative_luminance(rgb):
    """WCAG 相对亮度。"""
    channels = []
    for value in rgb:
        srgb = value / 255.0
        channels.append(srgb / 12.92 if srgb <= 0.03928
                        else ((srgb + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg, bg):
    """WCAG 对比度，1.0（完全相同）到 21.0（黑白）。"""
    lighter = max(_relative_luminance(fg), _relative_luminance(bg))
    darker = min(_relative_luminance(fg), _relative_luminance(bg))
    return (lighter + 0.05) / (darker + 0.05)


class ContrastMathTests(unittest.TestCase):
    """先证明尺子本身是准的——尺子错了，后面的结论全是噪声。"""

    def test_known_ratios(self):
        self.assertAlmostEqual(contrast_ratio((0, 0, 0), (255, 255, 255)), 21.0, places=1)
        self.assertAlmostEqual(contrast_ratio((255, 255, 255), (255, 255, 255)), 1.0, places=3)
        # 正是当初那个 bug 的配色：白字打在亮色 .Sub 背景上
        self.assertLess(contrast_ratio((255, 255, 255), (0xed, 0xf2, 0xf7)), 1.2)


class ThemeContrastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])
        import main

        cls.main = main
        try:
            cls.panel = main.ControlPanel()
            cls.canvas = main.DrawingCanvas(cls.panel)
            cls.panel.canvas = cls.canvas
        except Exception as exc:  # pragma: no cover - no display / no input hook
            raise unittest.SkipTest(f"cannot build ControlPanel: {exc}")

    @classmethod
    def tearDownClass(cls):
        panel = getattr(cls, "panel", None)
        for stopper in (getattr(panel, "listener", None),
                        getattr(panel, "timer", None),
                        getattr(panel, "autosave_timer", None)):
            try:
                stopper.stop()
            except Exception:
                pass

    def _use_theme(self, name):
        while self.panel.theme_name != name:
            self.panel.toggle_theme()
        self.panel.apply_theme()

    @staticmethod
    def _declared_color(widget):
        """从控件自己的样式表里取 color: 值；没写就返回 None。"""
        match = re.search(r"color:\s*(#[0-9a-fA-F]{3,8}|\w+)", widget.styleSheet() or "")
        return match.group(1) if match else None

    def _rendered_background(self, widget):
        """把控件渲染一遍，取左上角那个像素当背景色。

        直接读样式表推不出背景：``.Sub`` 的背景写在祖先 QFrame 上，标签自己是透明的。
        渲染是唯一能把「层层叠上来之后到底是什么颜色」问出来的办法。
        """
        from PyQt6.QtGui import QPixmap

        widget.setFixedSize(max(24, widget.sizeHint().width()),
                            max(12, widget.sizeHint().height()))
        pixmap = QPixmap(widget.size())
        pixmap.fill(self._parent_fill(widget))
        widget.render(pixmap)
        image = pixmap.toImage()
        color = image.pixelColor(0, 0)
        return (color.red(), color.green(), color.blue())

    def _parent_fill(self, widget):
        """祖先里最近一个有背景色的 QFrame 的颜色。"""
        from PyQt6.QtGui import QColor

        node = widget.parentWidget()
        while node is not None:
            match = re.search(r"background(?:-color)?:\s*(#[0-9a-fA-F]{3,8})",
                              node.styleSheet() or "")
            if match:
                return QColor(match.group(1))
            node = node.parentWidget()
        # 兜底用主题的面板色：主样式表把它下发给 .Sub/#MainFrame
        return QColor(self.panel.theme["panel"])

    def test_label_w_follows_the_theme(self):
        """回归：粗细标签不能写死颜色。"""
        from PyQt6.QtGui import QColor

        for theme in ("dark", "light"):
            self._use_theme(theme)
            declared = self._declared_color(self.panel.label_w)
            self.assertIsNotNone(declared, "label_w 应当有明确的颜色")
            self.assertNotEqual(declared.lower(), "white",
                                f"{theme} 主题下 label_w 写死了白色")
            self.assertEqual(QColor(declared).name().lower(),
                             QColor(self.panel.theme["label"]).name().lower(),
                             f"{theme} 主题下 label_w 没跟着主题的 label 色")

    def test_label_w_is_readable_in_both_themes(self):
        """量渲染出来的实际对比度，而不是「代码里看着对」。"""
        from PyQt6.QtGui import QColor

        for theme in ("dark", "light"):
            self._use_theme(theme)
            fg = QColor(self._declared_color(self.panel.label_w))
            background = self._parent_fill(self.panel.label_w)
            ratio = contrast_ratio((fg.red(), fg.green(), fg.blue()),
                                   (background.red(), background.green(), background.blue()))
            self.assertGreaterEqual(
                ratio, MIN_RATIO,
                f"{theme} 主题下「粗细」标签对比度只有 {ratio:.2f}:1（{fg.name()} on {background.name()}）")

    def test_theme_token_pairs_are_readable(self):
        """主题里成对使用的前景/背景 token 都要过阈值。

        这些配对来自 apply_theme() 里实际的用法：文字打在面板上、标签打在子面板上、
        高亮文字打在强调色上。任何一对掉到 3.0 以下，界面上就会有一块读不出来。
        """
        from PyQt6.QtGui import QColor

        pairs = (
            ("text", "panel"), ("text", "frame"), ("label", "panel"),
            ("label", "frame"), ("text", "button"),
            # accent 作背景，上面压 active_text：ActiveTool / IconBtnActive /
            # QPushButton:pressed / :checked / QMenu::item:selected
            ("active_text", "accent"),
            # accent 作文字，打在浅色面板/外框上：QLabel#SettingsSection（5.5.0 新增）、
            # QLabel#TimerDisplay、QLabel#MiniTimer。这个方向当初漏了，
            # 结果亮色主题下设置页的分区标题只有 2.60:1。
            ("accent", "panel"), ("accent", "frame"),
        )
        failures = []
        for name, theme in self.main.ControlPanel.THEMES.items():
            for fg_key, bg_key in pairs:
                if fg_key not in theme or bg_key not in theme:
                    continue
                fg, bg = QColor(theme[fg_key]), QColor(theme[bg_key])
                if not fg.isValid() or not bg.isValid():
                    continue
                ratio = contrast_ratio((fg.red(), fg.green(), fg.blue()),
                                       (bg.red(), bg.green(), bg.blue()))
                if ratio < MIN_RATIO:
                    failures.append(f"{name}: {fg_key}({fg.name()}) on "
                                    f"{bg_key}({bg.name()}) = {ratio:.2f}:1")
        self.assertEqual(failures, [], "以下配色读不出来:\n  " + "\n  ".join(failures))

    def test_no_hardcoded_white_text_on_theme_surfaces(self):
        """扫一遍源码：不允许再出现写死的白色文字样式。

        写死白色在暗色主题下看不出问题，切到亮色就消失——正是当初那个 bug 的形态。
        """
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        offenders = []
        for index, line in enumerate(source.splitlines(), start=1):
            if "setStyleSheet" not in line:
                continue
            if re.search(r'color:\s*white', line) and "background" not in line:
                offenders.append(f"main.py:{index}: {line.strip()}")
        self.assertEqual(offenders, [],
                         "写死白色文字，切到亮色主题就看不见了:\n  " + "\n  ".join(offenders))

    def test_settings_page_labels_are_readable(self):
        """设置页是 5.5.0 新增的一整屏文字，两个主题都要能读。"""
        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtGui import QColor

        self.panel.open_settings_panel()
        failures = []
        for theme in ("dark", "light"):
            self._use_theme(theme)
            self.panel.sync_settings_panel()
            for label in self.panel.settings_panel.findChildren(QLabel):
                if not label.text().strip():
                    continue
                declared = self._declared_color(label)
                fg = QColor(declared) if declared else QColor(self.panel.theme["text"])
                bg = self._parent_fill(label)
                if not fg.isValid():
                    continue
                ratio = contrast_ratio((fg.red(), fg.green(), fg.blue()),
                                       (bg.red(), bg.green(), bg.blue()))
                if ratio < MIN_RATIO:
                    failures.append(f"{theme}: {label.text()[:24]!r} "
                                    f"{fg.name()} on {bg.name()} = {ratio:.2f}:1")
        self.assertEqual(failures, [], "设置页有读不出来的文字:\n  " + "\n  ".join(failures))


if __name__ == "__main__":
    unittest.main(verbosity=2)
