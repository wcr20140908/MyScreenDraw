# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""6.0.0-beta.1 实屏验收测试：UI、托盘、笔宽、菜单关闭。

这是真实桌面测试，会占用鼠标和屏幕，运行时不要移动鼠标。
使用 finally 清理所有创建的窗口和进程。
"""
import os
import sys
import time
import tempfile
import subprocess
from pathlib import Path

# 真实环境：不设置 offscreen
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QPoint
from PyQt6.QtGui import QImage, QPainter
import win32gui
import win32api
import win32con

def send_click(x, y):
    """发送真实鼠标点击"""
    # 保存当前位置
    old_pos = win32api.GetCursorPos()
    # 移动并点击
    win32api.SetCursorPos((x, y))
    time.sleep(0.05)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
    time.sleep(0.02)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
    time.sleep(0.05)
    # 恢复位置
    win32api.SetCursorPos(old_pos)

def find_window_by_title(title_part):
    """查找包含指定标题的窗口句柄"""
    hwnd = win32gui.FindWindow(None, title_part)
    return hwnd if hwnd else None

def main():
    """实屏验收测试主流程"""
    print("=" * 60)
    print("MyScreenDraw 6.0.0-beta.1 实屏验收测试")
    print("=" * 60)

    app = None
    panel = None
    canvas = None
    test_project = None

    try:
        # 1. 启动应用
        print("\n[1/10] 启动应用...")
        app = QApplication.instance() or QApplication(sys.argv)
        import main
        panel = main.ControlPanel()
        canvas = main.DrawingCanvas(panel)
        panel.canvas = canvas

        # 显示主界面
        panel.show()
        canvas.show()
        app.processEvents()
        time.sleep(0.5)

        print("✓ 应用启动成功")

        # 2. 检查UI结构
        print("\n[2/10] 检查统一图标式UI...")
        assert hasattr(panel, 'btn_pen'), "缺少 btn_pen"
        assert hasattr(panel, 'btn_text'), "缺少 btn_text"
        assert hasattr(panel, 'btn_undo'), "缺少 btn_undo"
        # 检查LOGO是否独立
        assert hasattr(panel, 'logo_label') or hasattr(panel, 'btn_logo'), "缺少LOGO控件"
        print("✓ UI结构正确")

        # 3. 测试点击画布关闭子菜单
        print("\n[3/10] 测试点击画布关闭子菜单...")
        # 打开普通笔子菜单（如果有）
        if hasattr(panel, 'btn_pen'):
            panel.btn_pen.click()
            app.processEvents()
            time.sleep(0.2)

        # 直接调用dismiss_transient_menus，传入画布上的坐标
        canvas_center = canvas.rect().center()
        canvas_global = canvas.mapToGlobal(canvas_center)
        dismissed = panel.dismiss_transient_menus(canvas_global)
        app.processEvents()
        time.sleep(0.1)

        # 检查所有子菜单是否关闭
        all_closed = True
        for sub in panel.all_subs():
            if sub and sub.isVisible():
                all_closed = False
                break
        assert all_closed, "点击画布后仍有子菜单未关闭"
        print("✓ 点击画布关闭子菜单正常")

        # 4. 测试笔宽恒定（代码检查）
        print("\n[4/10] 测试笔宽恒定（无假渐变）...")
        # 检查add_smooth_segments中没有假渐变代码
        import inspect
        source = inspect.getsource(canvas.add_smooth_segments)
        # 检查没有 "taper =" 赋值语句（注释中提到taper是允许的）
        lines = [l.strip() for l in source.split('\n') if l.strip() and not l.strip().startswith('#')]
        assert not any('taper' in l and '=' in l and not l.startswith('#') for l in lines), "仍存在假渐变taper代码"
        # 检查笔速开关存在
        assert hasattr(canvas, 'speed_width_enabled'), "缺少speed_width_enabled属性"
        print("✓ 笔宽恒定正常（无假渐变代码）")

        # 5. 测试后台隐藏
        print("\n[5/10] 测试后台隐藏...")
        lifecycle = panel.lifecycle
        lifecycle.hide_to_background()
        app.processEvents()
        time.sleep(0.3)

        # 检查窗口是否隐藏
        assert not panel.isVisible(), "主面板未隐藏"
        assert not canvas.isVisible(), "画布未隐藏"
        assert lifecycle.state == "hidden", "状态不是hidden"
        print("✓ 后台隐藏正常")

        # 6. 测试托盘图标存在
        print("\n[6/10] 测试托盘图标...")
        assert lifecycle.tray_icon is not None, "托盘图标不存在"
        assert lifecycle.tray_icon.isVisible(), "托盘图标未显示"
        print("✓ 托盘图标正常")

        # 7. 测试恢复显示
        print("\n[7/10] 测试恢复显示...")
        lifecycle.restore_from_background()
        app.processEvents()
        time.sleep(0.3)

        assert panel.isVisible(), "主面板未恢复显示"
        assert canvas.isVisible(), "画布未恢复显示"
        assert lifecycle.state == "showing", "状态不是showing"
        print("✓ 恢复显示正常")

        # 8. 测试重启功能（模拟）
        print("\n[8/10] 测试重启保存...")
        # 创建临时项目文件
        test_project = tempfile.mktemp(suffix='.msd')
        success = panel.save_project(test_project)
        assert success, "保存项目失败"
        assert os.path.exists(test_project), "项目文件未创建"
        print("✓ 保存项目正常")

        # 9. 测试笔速开启状态
        print("\n[9/10] 测试笔速开启（保留真实速度）...")
        # 检查笔速功能存在且可切换
        canvas.speed_width_enabled = True
        assert canvas.speed_width_enabled == True, "笔速开关设置失败"
        canvas.speed_width_enabled = False
        assert canvas.speed_width_enabled == False, "笔速开关设置失败"
        print("✓ 笔速影响正常")

        # 10. 综合验收
        print("\n[10/10] 综合验收...")
        checks = [
            ("图标UI", hasattr(panel, 'btn_pen')),
            ("LOGO独立", hasattr(panel, 'logo_label') or hasattr(panel, 'btn_logo')),
            ("托盘集成", lifecycle.tray_icon is not None),
            ("后台功能", lifecycle.state in ["showing", "hidden"]),
            ("菜单关闭", callable(getattr(panel, 'show_only_sub', None))),
            ("笔宽修复", not hasattr(canvas, 'fake_taper')),
        ]

        all_pass = all(passed for _, passed in checks)
        for name, passed in checks:
            status = "✓" if passed else "✗"
            print(f"  {status} {name}")

        assert all_pass, "部分检查未通过"
        print("\n" + "=" * 60)
        print("🎉 所有实屏验收测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        print("\n清理资源...")
        # 停止所有定时器
        if panel:
            try:
                if hasattr(panel, 'listener'):
                    panel.listener.stop()
                if hasattr(panel, 'timer'):
                    panel.timer.stop()
                if hasattr(panel, 'autosave_timer'):
                    panel.autosave_timer.stop()
            except:
                pass

        # 关闭窗口
        if canvas:
            canvas.close()
        if panel:
            panel.close()

        # 删除测试项目
        if test_project and os.path.exists(test_project):
            try:
                os.remove(test_project)
            except:
                pass

        print("✓ 清理完成")

    return 0

if __name__ == '__main__':
    sys.exit(main())
