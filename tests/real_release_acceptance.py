# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in release acceptance: real Windows input; saves evidence outside Git.

Usage: python tests/real_release_acceptance.py <private-evidence-directory>
Occupies the desktop and pointer. Do not run during a lesson.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _real_beta7_check as probe
from PyQt6.QtCore import QPoint, QTimer
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import QApplication, QMessageBox
import main
import toolbar_windows


def move(point):
    # Qt maps logical coordinates for the current monitor; raw absolute SendInput
    # coordinates can change after a capture helper changes DPI awareness.
    QCursor.setPos(point)
    probe.pump(55)


def click_logical(x, y):
    move(QPoint(x, y))
    if (QCursor.pos() - QPoint(x, y)).manhattanLength() > 3:
        raise RuntimeError(f"Pointer missed during desktop acceptance: wanted ({x}, {y}), got {QCursor.pos()}")
    probe._send(probe.MOUSEEVENTF_LEFTDOWN); probe.pump(40)
    probe._send(probe.MOUSEEVENTF_LEFTUP); probe.pump(60)


probe.click_logical = click_logical


def draw_path(points):
    move(points[0]); probe._send(probe.MOUSEEVENTF_LEFTDOWN); probe.pump(50)
    try:
        for point in points[1:]: move(point)
    finally:
        probe._send(probe.MOUSEEVENTF_LEFTUP); probe.pump(100)


def attached(panel):
    logo, toolbar = panel.logo_window, panel.toolbar_window
    gap = toolbar_windows.LOGO_GAP
    target = (logo.x(), logo.y()+logo.height()+gap) if panel.orientation == 'portrait' else (logo.x()+logo.width()+gap, logo.y())
    return (toolbar.x(), toolbar.y()) == target and not logo.geometry().intersects(toolbar.geometry())


def exercise_preferences(panel, canvas):
    area = QApplication.primaryScreen().availableGeometry()
    panel.open_settings_panel(); probe.pump(300)
    scroll = panel.settings_scroll
    scroll.verticalScrollBar().setValue(0); probe.pump(200)
    notice = panel.release_notice
    probe.check('launch notice visible at settings top', notice.isVisible() and panel.notice_state['launches'] == 1)
    probe.grab(probe.OUT/'settings-notice.png', panel.settings_panel)
    probe.click_button(notice.close_button); probe.pump(100)
    panel.settings_panel.hide(); panel.open_settings_panel(); probe.pump(200)
    probe.check('dismissed notice stays hidden on reopening', notice.isHidden())

    def click_visible(widget):
        # Rebuilding per-pen option rows posts a layout request. Let it settle
        # before scrolling to the button's NEW position.
        probe.pump(150)
        scroll.ensureWidgetVisible(widget, 4, 6); probe.pump(160)
        center = widget.mapTo(scroll.viewport(), widget.rect().center())
        if not scroll.viewport().rect().contains(center):
            raise RuntimeError(f"Scrolled control outside viewport: {center}, viewport={scroll.viewport().rect()}")
        probe.click_button(widget); probe.pump(150)

    click_visible(panel.auto_pen_checkbox)
    probe.check('auto return real toggle off', not panel.whiteboard_auto_pen)
    click_visible(panel.auto_pen_checkbox)
    probe.check('auto return real toggle on', panel.whiteboard_auto_pen)
    editor = panel.pen_defaults_editor
    for i, key in enumerate((*main.PEN_STYLES, 'marker', 'laser')):
        editor.set_current_key(key)
        editor.color_edit.setText('#315ca8')
        editor.width_spin.setValue(10+i)
        for name, control in editor.option_controls.items():
            control.setValue(control.minimum())
        click_visible(editor.save_button)
        probe.check(f'{key} preset saved via real click', panel.pen_defaults[key]['width']==10+i and panel.pen_defaults[key]['color']=='#315ca8')
    probe.grab(probe.OUT/'settings-presets.png',panel.settings_panel)
    if not panel.pen_defaults_enabled: click_visible(panel.pen_defaults_checkbox)
    probe.check('preset switch real click enables', panel.pen_defaults_enabled)
    panel.settings_panel.hide()
    for i,key in enumerate(main.PEN_STYLES):
        panel.choose_pen_style(key);panel.show_only_sub(None)
        canvas.pen_width=35
        panel.set_tool('ERASER',panel.btn_eraser)
        panel.choose_pen_style(key);panel.show_only_sub(None)
        probe.check(f'{key} re-entry restores preset', canvas.pen_width==10+i)
    # First-contact changes use real Windows input on an unobstructed whiteboard.
    canvas.smart_shapes_enabled=False
    for i,state in enumerate(('ERASER','SELECT','SHAPE','TEXT','MAGNIFIER','SPOTLIGHT')):
        panel.choose_pen_style('chalk');panel.show_only_sub(None)
        panel.set_tool(state,panel.btn_eraser)
        canvas.new_page();panel.update_whiteboard_ui();probe.pump(200)
        before=len(canvas.all_segments)
        x,y=area.center().x(),area.center().y()
        draw_path([QPoint(x+j*5,y+(j%5)*3) for j in range(20)])
        probe.check(f'{state} page first contact restores and draws',canvas.draw_state=='PEN' and canvas.pen_style=='chalk' and len(canvas.all_segments)>before)
    panel.set_tool('ERASER',panel.btn_eraser)
    canvas.new_page();panel.update_whiteboard_ui();probe.pump(150)
    probe.click_button(panel.toolbar_window.icon_buttons['eraser']);probe.pump(100)
    draw_path([area.center(),area.center()+QPoint(60,10)])
    probe.check('manual eraser choice wins after paging',canvas.draw_state=='ERASER' and not canvas._page_return_pending)
    panel.show_only_sub(None)
    panel.choose_pen_style('chalk');panel.show_only_sub(None)
    panel.pen_defaults_enabled=True
    panel.pen_defaults[canvas.pen_style]['width']=17
    canvas.pen_width=28
    panel.set_drawing_mode(False)
    canvas.switch_page(-1);probe.pump(150)
    draw_path([area.center(),area.center()+QPoint(70,12)])
    probe.check('mouse-mode page return captures initial contact',canvas.is_drawing_mode and canvas.draw_state=='PEN' and not canvas._mouse_passthrough)
    probe.check('mouse-mode page return applies same pen preset',canvas.pen_width==17)
    panel.whiteboard_auto_pen=False
    panel.set_tool('ERASER',panel.btn_eraser);canvas.new_page();probe.pump(150)
    draw_path([area.center(),area.center()+QPoint(70,12)])
    probe.check('disabled page return retains eraser',canvas.draw_state=='ERASER')
    panel.whiteboard_auto_pen=True
    panel.pen_defaults_enabled=False
    # Return to a single disposable page for the legacy acceptance section.
    canvas.pages=[canvas.capture_page()];canvas.current_page=0
    panel.choose_pen_style('pen');panel.show_only_sub(None)
    panel.save_settings()


def exercise(panel, canvas):
    area = QApplication.primaryScreen().availableGeometry()
    logo, toolbar = panel.logo_window, panel.toolbar_window
    for orientation in ('portrait', 'landscape'):
        panel.set_orientation(orientation); panel.set_drawing_mode(True)
        panel._toolbar_detached = False; logo.move(area.left()+100, area.top()+100)
        toolbar.show(); logo.show(); panel._sync_split_geometry(); panel.bind_topmost_stack(); probe.pump(500)
        for label, endpoint in [('bottom-right', area.bottomRight()-QPoint(3,3)), ('top-left', area.topLeft()+QPoint(3,3))]:
            start = logo.logo_btn.mapToGlobal(logo.logo_btn.rect().center())
            points = [start]+[QPoint(start.x()+(endpoint.x()-start.x())*i//14, start.y()+(endpoint.y()-start.y())*i//14) for i in range(1,15)]
            draw_path(points)
            probe.check(f'{orientation} {label} group remains attached', attached(panel), f'logo={logo.geometry()} toolbar={toolbar.geometry()}')
            probe.check(f'{orientation} {label} pair contained', area.contains(logo.frameGeometry()) and area.contains(toolbar.frameGeometry()))
            probe.check(f'{orientation} {label} drag did not collapse', toolbar.isVisible())
            probe.check(f'{orientation} {label} pressed state cleared', not logo.logo_btn.isDown())
        move(area.center()); probe.pump(600)
        probe.check(f'{orientation} no pointer hover after leaving', not logo.logo_btn.underMouse() and not logo.logo_btn.isDown())
        probe.grab(probe.OUT/f'logo-{orientation}.png', logo, toolbar)
        probe.click_button(logo.logo_btn); probe.pump(180)
        probe.check(f'{orientation} ordinary click collapses', not toolbar.isVisible())
        probe.click_button(logo.logo_btn); probe.pump(180)
        probe.check(f'{orientation} ordinary click restores', toolbar.isVisible() and attached(panel))
    panel.set_orientation('portrait');logo.move(30,30);panel._sync_split_geometry();probe.pump(250)
    if not canvas.whiteboard_mode: panel.toggle_whiteboard()
    panel.set_drawing_mode(True);probe.pump(250)
    for i,style in enumerate(main.PEN_STYLES):
        panel.choose_pen_style(style);panel.show_only_sub(None)
        canvas.pen_color = QColor('#184ab8');canvas.pen_width=8
        before=len(canvas.all_segments)
        x=area.left()+220+(i%3)*390;y=area.top()+160+(i//3)*160
        draw_path([QPoint(x+j*9,y+int(25*((j%12)/6-1))) for j in range(30)])
        probe.check(f'real input produces {style} ink',len(canvas.all_segments)>before)
    probe.grab(probe.OUT/'all-pen-styles.png',canvas)
    probe.click_button(panel.rail_new); probe.pump(250)
    probe.check('new page via real click', len(canvas.pages)==2 and canvas.current_page==1)
    probe.click_button(panel.rail_count); probe.pump(250)
    probe.check('page list fits current screen',panel.thumbnail_panel.isVisible() and area.contains(panel.thumbnail_panel.frameGeometry()))
    for answer in (QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Yes):
        def answer_dialog(answer=answer):
            dialogs=[w for w in QApplication.topLevelWidgets() if isinstance(w,QMessageBox) and w.isVisible()]
            if len(dialogs)!=1:
                probe.check('delete dialog visible',False)
                for w in dialogs:w.reject()
                return
            box=dialogs[0]
            probe.check('delete defaults to cancel',box.defaultButton()==box.button(QMessageBox.StandardButton.Cancel))
            probe.click_button(box.button(answer))
        QTimer.singleShot(250,answer_dialog)
        probe.click_button(panel.btn_delete_page);probe.pump(250)
        expected=2 if answer==QMessageBox.StandardButton.Cancel else 1
        probe.check(f'delete page {answer.name}',len(canvas.pages)==expected)
    panel.close_thumbnail_panel()
    exercise_preferences(panel,canvas)
    panel.open_settings_panel();probe.pump(250)
    probe.check('settings visible and fits',panel.settings_panel.isVisible() and area.contains(panel.settings_panel.frameGeometry()))
    panel.settings_panel.hide()
    panel.set_ui_radius(17,persist=False);panel.set_ui_opacity(73,persist=False)
    panel.save_settings();saved=json.loads(Path(main.CONFIG_FILE).read_text(encoding='utf-8'))
    panel.set_ui_radius(3,persist=False);panel.set_ui_opacity(95,persist=False);panel.load_settings()
    probe.check('real window settings reload',panel.ui_radius==17 and panel.ui_opacity==73 and panel.collect_settings()['pen_profiles']==saved['pen_profiles'])
    panel.set_ui_opacity(100,persist=False)
    # Existing desktop acceptance covers mode switching, page rail, tray and native warnings.
    canvas.all_segments.clear();canvas.text_items.clear();canvas.shape_items.clear()
    if canvas.whiteboard_mode:panel.toggle_whiteboard()
    panel.logo_window.move(30,30);panel._sync_split_geometry();probe.pump(250)
    probe.run(QApplication.instance(),panel,canvas)


def main_():
    app=QApplication(sys.argv);app.setQuitOnLastWindowClosed(False)
    start_cursor=QCursor.pos()
    with tempfile.TemporaryDirectory(prefix='msd-release-real-') as folder:
        main.CONFIG_FILE=str(Path(folder)/'config.json')
        for name, relative in (('DATA_DIR','.'),('AUTOSAVE_DIR','autosave'),('EXPORT_DIR','exports'),
                               ('ROSTER_FILE','roster.json'),('TELEMETRY_FILE','events.jsonl'),('LOG_FILE','app.log')):
            setattr(main,name,str(Path(folder)/relative))
        Path(main.AUTOSAVE_DIR).mkdir();Path(main.EXPORT_DIR).mkdir()
        panel=main.ControlPanel();canvas=main.DrawingCanvas(panel);panel.canvas=canvas
        panel.apply_theme();panel.load_settings();panel.begin_usage_session()
        if os.environ.get('MYSCREENDRAW_TEST_THEME') in panel.THEMES:
            panel.theme_name=os.environ['MYSCREENDRAW_TEST_THEME'];panel.theme=panel.THEMES[panel.theme_name];panel.apply_theme()
        panel.update_whiteboard_ui();panel.update_history_ui()
        panel.show();canvas.show();panel.bind_topmost_stack()
        code=[1]
        def go():
            try:exercise(panel,canvas)
            except Exception:
                if panel.settings_panel is not None and panel.settings_panel.isVisible():
                    probe.grab(probe.OUT/"failure-settings.png",panel.settings_panel)
                traceback.print_exc();probe.check('harness exception',False,traceback.format_exc().splitlines()[-1])
            finally:
                probe._send(probe.MOUSEEVENTF_LEFTUP)
                failed=[r for r in probe.RESULTS if not r[1]]
                (probe.OUT/'release-acceptance.json').write_text(json.dumps({'version':main.APP_VERSION,'checks':probe.RESULTS,'failed':failed},indent=2),encoding='utf-8')
                print(f'RELEASE ACCEPTANCE: {len(probe.RESULTS)-len(failed)}/{len(probe.RESULTS)} passed',flush=True)
                code[0]=bool(failed)
                for name in ('listener','timer','autosave_timer','update_check_timer','_split_save_timer'):
                    obj=getattr(panel,name,None)
                    if obj is not None:obj.stop()
                if getattr(panel,'lifecycle',None) and panel.lifecycle.tray_icon:panel.lifecycle.tray_icon.hide()
                panel.stop_update_worker();QCursor.setPos(start_cursor);app.quit()
        QTimer.singleShot(1200,go);app.exec()
    return int(code[0])

if __name__=='__main__':raise SystemExit(main_())
