# SPDX-License-Identifier: GPL-3.0-or-later
"""Render isolated settings/popup and chalk samples; never capture the desktop.

Usage: python tests/render_final_ui.py OUTPUT_DIRECTORY
Requires the pytest fixture dependencies; all application data is temporary.
"""
import ast
import math
import os
from pathlib import Path
import random
import sys
import tempfile
import zipfile

os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QFontDatabase, QImage, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QColorDialog
from pytest import MonkeyPatch
from test_upgrade_settings import rig


def render(output):
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc"
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    app.setFont(QFont("Microsoft YaHei", 10))
    with tempfile.TemporaryDirectory(prefix="msd-ui-render-") as temp, MonkeyPatch.context() as monkey:
        fixture = rig.__wrapped__(Path(temp), monkey, app)
        env = next(fixture)
        try:
            panel, canvas = env.fresh()
            panel.open_settings_panel()
            editor = panel.pen_defaults_editor
            editor.set_current_key("chalk")
            editor.color_edit.setText("#bb4ebae4")
            for name in ("dark", "light"):
                panel.theme_name, panel.theme = name, panel.THEMES[name]
                panel.apply_theme()
                for _ in range(4):
                    app.processEvents()
                panel.settings_scroll.ensureWidgetVisible(editor)
                app.processEvents()
                panel.settings_panel.grab().save(str(output / f"settings-{name}.png"))
                editor.grab().save(str(output / f"presets-{name}.png"))
                from PyQt6.QtWidgets import QWidget
                details = [(w.metaObject().className(), getattr(w, "text", lambda: "")(),
                            w.geometry().getRect(), w.sizeHint().height(), w.minimumSizeHint().height())
                           for w in editor.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)
                           if not w.isHidden()]
                from PyQt6.QtWidgets import QLayout
                details += [(q.metaObject().className(), q.geometry().getRect(), q.sizeHint().height(), q.minimumSize().height()) for q in editor.findChildren(QLayout)]
                details += [("editor", editor.sizeHint().height(), editor.minimumSizeHint().height())]
                (output / f"layout-{name}.txt").write_text(str(details), encoding="utf-8")
                for key, combo in (("pen", editor.pen_combo), ("channel", panel.update_channel_combo)):
                    panel.settings_scroll.ensureWidgetVisible(combo)
                    combo.showPopup()
                    app.processEvents()
                    combo.view().window().grab().save(str(output / f"popup-{key}-{name}.png"))
                    combo.hidePopup()
                from themed_controls import controls_stylesheet, theme_palette
                dialog = QColorDialog(editor)
                dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog)
                dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel)
                dialog.setCurrentColor(QColor("#bb4ebae4"))
                dialog.setPalette(theme_palette(panel.theme))
                dialog.setStyleSheet(controls_stylesheet(panel.theme))
                dialog.show()
                app.processEvents()
                dialog.grab().save(str(output / f"picker-{name}.png"))
                dialog.close()

            # The pre-fix source checkpoint provides an actual old-render comparison.
            checkpoint = output / "source-before-fixes.zip"
            old = None
            if checkpoint.exists():
                with zipfile.ZipFile(checkpoint) as archive:
                    tree = ast.parse(archive.read("main.py").decode("utf-8-sig"))
                fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "style_texture")
                namespace = dict(QImage=QImage, QColor=QColor, Qt=Qt, random=random,
                                 normalize_pen_options=env.main.normalize_pen_options, _TEXTURE_CACHE={})
                exec(compile(ast.Module(body=[fn], type_ignores=[]), "pre-fix-texture", "exec"), namespace)
                old = namespace["style_texture"]
            image = QImage(1400, 1050, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(QColor("#e4e8ed"))
            painter = QPainter(image)
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setFont(QFont("Microsoft YaHei", 20))
                for col, (label, texture) in enumerate((("原版 · 48px 颗粒", old or env.main.style_texture),
                                                       ("改进 · 多尺度粉块 + 细粉", env.main.style_texture))):
                    x = col * 700
                    painter.setPen(QColor("#18252b"))
                    painter.setFont(QFont("Microsoft YaHei", 20))
                    painter.drawText(x + 30, 40, label)
                    for row, (bg, colors) in enumerate((("#15372e", ("#faf7e9", "#f5c94b", "#ec7c77")),
                                                       ("#faf9f4", ("#343d49", "#1769ae", "#d93e4d")))):
                        y = 60 + row * 490
                        painter.fillRect(x + 20, y, 660, 470, QColor(bg))
                        for index, width in enumerate((6, 16, 36)):
                            color = QColor(colors[index])
                            path = QPainterPath(QPointF(x + 50, y + 90 + index * 120))
                            for i in range(1, 581):
                                path.lineTo(x + 50 + i, y + 90 + index * 120 + 25 * math.sin(i / 35))
                            painter.setPen(QPen(QBrush(texture("chalk", color)), width,
                                                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                            painter.drawPath(path)
                        painter.setPen(QColor(colors[0]))
                        painter.setFont(QFont("Microsoft YaHei", 11))
                        painter.drawText(x + 45, y + 440, "同色 / 同密度 58% / 同不透明度 94% · 笔宽 6 / 16 / 36 px")
            finally:
                painter.end()
            image.save(str(output / "chalk-comparison.png"))
        finally:
            try:
                next(fixture)
            except StopIteration:
                pass
    print(f"Rendered isolated UI and chalk samples: {output}")


if __name__ == "__main__":
    render(Path(sys.argv[1]).resolve())
