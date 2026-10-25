# SPDX-License-Identifier: GPL-3.0-or-later
"""Calculator tutorials use a separate process and restore synthetic user state."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys

import pytest
from PyQt6.QtWidgets import QApplication

from teaching.bootstrap import practice_arguments
from test_teaching_application import until
from test_teaching_application_isolation import drain
from test_teaching_complete_process import (BRIDGE, CHAPTERS, parent_coordinator,
                                            practice_request, run_course_process)

ROOT = Path(__file__).resolve().parents[1]

CALCULATOR_CHAPTERS = ('c12.calculator', 'c12.scientific_calculator')


def snapshot(panel):
    widget = panel.calculator_widget
    return (widget.mode, copy.deepcopy(widget.drafts), widget.expression_edit.text(),
            widget.engine.angle_mode, widget.engine.ans, widget.engine.memory,
            tuple(entry.to_dict() for entry in widget.history.entries),
            panel.calculator_history_retention, widget.history.retention,
            panel.calc_panel.geometry(), panel.calc_panel.isVisible())


def seed_parent_calculator(panel):
    panel.set_calculator_history_retention('forever', persist=False)
    panel.open_calculator()
    widget = panel.calculator_widget
    widget.set_mode('scientific')
    widget._set_expression('41+1')
    widget.scientific_buttons['equals'].click()
    widget.engine.memory_add(Decimal('17'))
    widget.toggle_angle()
    widget._set_expression('123+7')
    widget.set_mode('basic')
    widget._set_expression('8+9')
    drain(QApplication.instance())
    history_path = widget.history.path
    assert history_path.is_file() and not history_path.resolve().is_relative_to(ROOT)
    config_path = panel.runtime_context.paths.config_file
    return snapshot(panel), history_path, history_path.read_bytes(), config_path, config_path.read_bytes()


def test_calculator_chapters_finish_without_touching_user_drafts_memory_or_history(
        parent_coordinator, tmp_path, monkeypatch):
    panel, _ = parent_coordinator
    before, history_path, history_bytes, config_path, config_bytes = seed_parent_calculator(panel)
    bridge = BRIDGE.replace('chapters = ' + repr(CHAPTERS),
                            'chapters = ' + repr(CALCULATOR_CHAPTERS))
    assert bridge != BRIDGE
    monkeypatch.setenv('PYTHONFAULTHANDLER', '1')
    diagnostic_path = tmp_path / 'calculator-progress.json'
    error_path = tmp_path / 'calculator-slot-errors.txt'
    slot_guard = (
        "def capture_slot_error(exc_type, exception, tb):\n"
        + '    with Path(' + repr(str(error_path)) + ").open('a', encoding='utf-8') as stream:\n"
        + "        stream.write(''.join(traceback.format_exception(exc_type, exception, tb)))\n"
        + "sys.excepthook = capture_slot_error\n")
    bridge = bridge.replace('chapters = ' + repr(CALCULATOR_CHAPTERS),
                            slot_guard + 'chapters = ' + repr(CALCULATOR_CHAPTERS))
    bridge = bridge.replace(
        "    trace['pids'].append(os.getpid()); trace['stage'] = stage",
        "    trace['pids'].append(os.getpid()); trace['stage'] = stage\n"
        + '    Path(' + repr(str(diagnostic_path)) + ").write_text(json.dumps(trace), encoding='utf-8')")
    # Forbid the child from opening the synthetic user's history, even read-only.
    guard = """
from calculator_history import CalculatorHistoryStore
history_load = CalculatorHistoryStore.load
history_save = CalculatorHistoryStore.save
def isolated_history_load(store):
    assert store.path.resolve() != Path(USER_HISTORY).resolve(), 'tutorial read user history'
    return history_load(store)
def isolated_history_save(store, **kwargs):
    assert store.path.resolve() != Path(USER_HISTORY).resolve(), 'tutorial wrote user history'
    return history_save(store, **kwargs)
CalculatorHistoryStore.load = isolated_history_load
CalculatorHistoryStore.save = isolated_history_save
""".replace('USER_HISTORY', repr(str(history_path)))
    bridge = bridge.replace('from teaching.application import ApplicationTeachingHost, PracticeChild',
                            guard + '\nfrom teaching.application import ApplicationTeachingHost, PracticeChild')
    proof = run_course_process(parent_coordinator, tmp_path, monkeypatch,
        chapters=CALCULATOR_CHAPTERS, bridge_source=bridge, expected_steps=18)
    assert not error_path.exists() or not error_path.read_text('utf-8')
    assert proof['c12_basic_result'] == '5'
    assert proof['c12_scientific_result'] == '4.5' and proof['c12_scientific_ans'] == '9'
    assert proof['c12_scientific_restored'] == 'sin(30)+√16'
    assert snapshot(panel) == before
    assert history_path.read_bytes() == history_bytes
    assert config_path.read_bytes() == config_bytes


STOP_BRIDGE = r"""
import json, runpy, sys
from pathlib import Path
app_dir, resources, role, user_history = sys.argv[1:5]
proof_path = Path(sys.argv[5])
sys.path.insert(0, app_dir)
sys._MEIPASS = resources
from PyQt6.QtCore import QTimer
from calculator_history import CalculatorHistoryStore
from teaching.application import ApplicationTeachingHost
history_load, history_save = CalculatorHistoryStore.load, CalculatorHistoryStore.save
def guard_load(store):
    assert store.path.resolve() != Path(user_history).resolve(), 'tutorial read user history'
    return history_load(store)
def guard_save(store, **kwargs):
    assert store.path.resolve() != Path(user_history).resolve(), 'tutorial wrote user history'
    return history_save(store)
CalculatorHistoryStore.load, CalculatorHistoryStore.save = guard_load, guard_save
activate_original = ApplicationTeachingHost.activate
def activate(self):
    activate_original(self)
    def actions():
        widget = self.panel.calculator_widget
        assert widget.history.retention == 'session' and not widget.history.persistent
        assert not widget.history.entries and widget.engine.memory == 0 and widget.engine.ans == 0
        widget.set_mode('scientific')
        widget._set_expression('3+4')
        widget.scientific_buttons['equals'].click()
        widget.engine.memory_add()
        widget._set_expression('42+8')
        assert widget.engine.memory == 7 and widget.engine.ans == 7
        assert len(widget.history.entries) == 1
        proof = {'private_history': str(widget.history.path), 'draft': widget.expression_edit.text(),
                 'ans': str(widget.engine.ans), 'memory': str(widget.engine.memory),
                 'history_count': len(widget.history.entries), 'role': role}
        proof_path.write_text(json.dumps(proof), encoding='utf-8')
        if role == 'error': self.failed.emit('synthetic-calculator-error')
        else: self.exit_requested.emit()
    QTimer.singleShot(50, actions)
ApplicationTeachingHost.activate = activate
sys.argv = [str(Path(app_dir)/'main.py'), *sys.argv[6:]]
runpy.run_path(str(Path(app_dir)/'main.py'), run_name='__main__')
"""


@pytest.mark.parametrize('chapter', CALCULATOR_CHAPTERS)
@pytest.mark.parametrize('role', ['cancel', 'error'])
def test_calculator_cancel_and_error_restore_user_state_and_delete_private_runtime(
        parent_coordinator, tmp_path, chapter, role):
    panel, coordinator = parent_coordinator
    before, history_path, history_bytes, config_path, config_bytes = seed_parent_calculator(panel)
    proof = tmp_path / 'calculator-stop-proof.json'
    script = tmp_path / 'calculator-stop-child.py'
    script.write_text(STOP_BRIDGE, encoding='utf-8')
    def command(request):
        return sys.executable, ['-B', str(script), str(ROOT), str(ROOT), role,
            str(history_path), str(proof), *practice_arguments(request.paths, request.channel,
                                                              request.course_id, request.chapter_id)]
    coordinator.session.command_factory = command
    assert coordinator.start('c12', chapter)
    private_root = coordinator.session.paths.runtime_root
    until(lambda: coordinator.session.phase == 'stopped', timeout=15000,
          diagnostic=lambda: (coordinator.session.phase, coordinator.session.last_error,
                              proof.read_text('utf-8') if proof.exists() else 'no child proof'))
    assert proof.is_file()
    details = json.loads(proof.read_text('utf-8'))
    assert details['draft'] == '42+8' and details['ans'] == details['memory'] == '7'
    assert details['history_count'] == 1 and details['role'] == role
    assert Path(details['private_history']).is_relative_to(private_root)
    assert not private_root.exists() and coordinator.session.process is None
    assert coordinator.session.last_error == ('child_error' if role == 'error' else None)
    assert coordinator.state_store.chapter_status(chapter) != 'completed'
    assert not panel._teaching_suspended and not coordinator.restore_errors
    assert snapshot(panel) == before
    assert history_path.read_bytes() == history_bytes
    assert config_path.read_bytes() == config_bytes
