# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Qt panel for the classroom calculator."""
from __future__ import annotations

from decimal import Decimal, DecimalException
from typing import Callable

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QBoxLayout, QComboBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton,
    QSizePolicy, QStackedWidget, QTextEdit, QToolButton, QVBoxLayout, QWidget,
)

from calculator import (
    CalculatorEngine, CalculatorError, UNIT_CATEGORIES, convert_all_units,
    convert_base, describe_statistics, format_decimal, format_full_decimal, parse_statistics,
)
from calculator_history import CalculatorHistoryStore, HistoryEntry, MODES


MODE_KEYS = ("basic", "scientific", "unit", "statistics", "base")
MODE_LABEL_KEYS = {
    "basic": "calculator_mode_basic",
    "scientific": "calculator_mode_scientific",
    "unit": "calculator_mode_unit",
    "statistics": "calculator_mode_statistics",
    "base": "calculator_mode_base",
}
STATISTIC_LABEL_KEYS = {
    "count": "calculator_stat_count",
    "sum": "calculator_stat_sum",
    "mean": "calculator_stat_mean",
    "median": "calculator_stat_median",
    "minimum": "calculator_stat_minimum",
    "maximum": "calculator_stat_maximum",
    "range": "calculator_stat_range",
    "population_variance": "calculator_stat_variance",
    "population_stddev": "calculator_stat_stddev",
}


class CalculatorStack(QStackedWidget):
    """Only the visible mode contributes to the floating window's geometry."""

    def sizeHint(self):
        page = self.currentWidget()
        return page.sizeHint() if page is not None else QSize(0, 0)

    def minimumSizeHint(self):
        page = self.currentWidget()
        return page.minimumSizeHint() if page is not None else QSize(0, 0)


class ExpressionEdit(QLineEdit):
    def __init__(self, panel):
        super().__init__('0', panel)
        self.panel = panel

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Paste):
            self.panel._prepare_insertion(QGuiApplication.clipboard().text())
        elif event.text() and not event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            if event.key() not in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Backspace,
                                   Qt.Key.Key_Delete, Qt.Key.Key_Escape, Qt.Key.Key_Tab):
                self.panel._prepare_insertion(event.text())
        elif event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.panel._just_committed = False
        super().keyPressEvent(event)

    def inputMethodEvent(self, event):
        if event.commitString():
            self.panel._prepare_insertion(event.commitString())
        super().inputMethodEvent(event)


class CalculatorPanel(QWidget):
    """Five-mode calculator content embedded in the existing tool window."""

    submitted = pyqtSignal(str, str, str)  # mode, input, result
    mode_changed = pyqtSignal(str)
    angle_changed = pyqtSignal(str)
    history_recalled = pyqtSignal(str)
    history_visibility_changed = pyqtSignal(bool)
    settings_requested = pyqtSignal()
    hide_requested = pyqtSignal()
    layout_changed = pyqtSignal()

    def __init__(self, history: CalculatorHistoryStore, *,
                 translate: Callable[[str], str],
                 event_callback: Callable[..., None] | None = None,
                 angle_mode: str = "deg", initial_mode: str = "basic",
                 decimal_separator: str = ".", touch_button_size: int = 32,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.history = history
        self.t = translate
        self.event_callback = event_callback or (lambda *_args, **_kwargs: None)
        self.decimal_separator = "," if decimal_separator == "," else "."
        self.touch_button_size = max(28, int(touch_button_size))
        self.engine = CalculatorEngine(angle_mode=angle_mode)
        self.mode = "basic"
        self.drafts = {"basic": "0", "scientific": "0"}
        self._just_committed = False
        self._syncing_expression = False
        self._second = False
        self._last_preview = None
        self._committed_result = None
        self._committed_input = ''
        self._continuation_ans = None
        self._draft_results = {}
        self._statistics_summary = None
        self._unit_selected: tuple[str, str] | None = None
        self._base_valid = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        mode_row = QHBoxLayout()
        self.mode_buttons: dict[str, QPushButton] = {}
        for mode in MODE_KEYS:
            button = QPushButton(self.t(MODE_LABEL_KEYS[mode]))
            button.setCheckable(True)
            button.setToolTip(button.text())
            button.setMinimumHeight(self.touch_button_size)
            button.setMinimumWidth(52)
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda _checked=False, value=mode: self.set_mode(value))
            mode_row.addWidget(button)
            self.mode_buttons[mode] = button
        self.history_toggle = QToolButton()
        self.history_toggle.setText(self.t("calculator_history"))
        self.history_toggle.setCheckable(True)
        self.history_toggle.setMinimumHeight(self.touch_button_size)
        self.history_toggle.setMinimumWidth(52)
        self.history_toggle.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.history_toggle.toggled.connect(self._set_history_visible)
        mode_row.addWidget(self.history_toggle)
        root.addLayout(mode_row)

        self.expression_frame = QFrame()
        expression_layout = QVBoxLayout(self.expression_frame)
        expression_layout.setContentsMargins(0, 0, 0, 0)
        expression_layout.setSpacing(2)
        self.expression_edit = ExpressionEdit(self)
        self.expression_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.expression_edit.setMinimumHeight(self.touch_button_size)
        self.expression_edit.textChanged.connect(self._expression_changed)
        self.expression_edit.returnPressed.connect(self.commit_expression)
        expression_layout.addWidget(self.expression_edit)
        preview_row = QHBoxLayout()
        self.preview_label = QLabel("0")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.preview_label.setObjectName("CalculatorPreview")
        preview_row.addWidget(self.preview_label, 1)
        self.copy_button = QPushButton(self.t("copy_result"))
        self.copy_button.clicked.connect(self.copy_result)
        preview_row.addWidget(self.copy_button)
        self.copy_menu_button = QToolButton()
        self.copy_menu_button.setText("▾")
        self.copy_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        copy_menu = QMenu(self.copy_menu_button)
        copy_menu.addAction(self.t("calculator_copy_input"), self.copy_input)
        copy_menu.addAction(self.t("calculator_copy_equation"), self.copy_equation)
        self.copy_menu_button.setMenu(copy_menu)
        preview_row.addWidget(self.copy_menu_button)
        expression_layout.addLayout(preview_row)
        self.error_label = QLabel("")
        self.error_label.setObjectName("CalculatorError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        expression_layout.addWidget(self.error_label)
        root.addWidget(self.expression_frame)

        self.body_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.stack = CalculatorStack()
        self.pages: dict[str, QWidget] = {}
        self.pages["basic"] = self._build_basic_page()
        self.pages["scientific"] = self._build_scientific_page()
        self.pages["unit"] = self._build_unit_page()
        self.pages["statistics"] = self._build_statistics_page()
        self.pages["base"] = self._build_base_page()
        for mode in MODE_KEYS:
            self.stack.addWidget(self.pages[mode])
        self.body_layout.addWidget(self.stack, 1, Qt.AlignmentFlag.AlignTop)
        self.history_frame = self._build_history_panel()
        self.history_frame.setMinimumWidth(0)
        self.history_frame.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.history_frame.setVisible(False)
        self.body_layout.addWidget(self.history_frame)
        root.addLayout(self.body_layout, 1)
        self.storage_status = QLabel('')
        self.storage_status.setWordWrap(True)
        self.storage_status.hide()
        root.addWidget(self.storage_status)

        self.history.load()
        self.refresh_history()
        self.set_mode(initial_mode if initial_mode in MODE_KEYS else "basic", emit=False)
        self.update_responsive_layout()
        # Touch targets include secondary actions, selectors and copy menus.
        for control in self.findChildren(QWidget):
            if not isinstance(control, (QPushButton, QToolButton, QComboBox)):
                continue
            control.setMinimumHeight(self.touch_button_size)
            if isinstance(control, (QPushButton, QToolButton)):
                control.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _button(self, text: str, callback, *, code: str | None = None) -> QPushButton:
        button = QPushButton(text)
        button.setMinimumSize(self.touch_button_size + 12, self.touch_button_size)
        button.clicked.connect(callback)
        if code is not None:
            button.setProperty("calculatorCode", code)
        return button

    def _build_basic_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        memory_row = QHBoxLayout()
        for label, action in (("MC", self.memory_clear), ("MR", self.memory_recall),
                              ("M+", self.memory_add), ("M−", self.memory_subtract)):
            memory_row.addWidget(self._button(label, action))
        layout.addLayout(memory_row)
        keys = [
            ("C", "C"), ("⌫", "B"), ("%", "%"), ("÷", "/"),
            ("7", "7"), ("8", "8"), ("9", "9"), ("×", "*"),
            ("4", "4"), ("5", "5"), ("6", "6"), ("−", "-"),
            ("1", "1"), ("2", "2"), ("3", "3"), ("+", "+"),
            ("±", "N"), ("0", "0"), (".", "."), ("=", "="),
        ]
        grid = QGridLayout()
        grid.setSpacing(3)
        self.basic_buttons: dict[str, QPushButton] = {}
        for index, (label, code) in enumerate(keys):
            button = self._button(label, lambda _checked=False, value=code: self.input_code(value), code=code)
            grid.addWidget(button, index // 4, index % 4)
            self.basic_buttons[code] = button
        layout.addLayout(grid)
        return page

    def _build_scientific_page(self) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        specs = [
            ("2nd", "second", self.toggle_second), (self.engine.angle_mode.upper(), "angle", self.toggle_angle),
            ("(", "left_paren", lambda: self.insert_text("(")), (")", "right_paren", lambda: self.insert_text(")")),
            ("sin", "trig1", lambda: self.insert_function("sin")), ("cos", "trig2", lambda: self.insert_function("cos")),
            ("tan", "trig3", lambda: self.insert_function("tan")), ("π", "pi", lambda: self.insert_text("π")),
            ("x²", "square", lambda: self.insert_text("^2")), ("xʸ", "power", lambda: self.insert_text("^")),
            ("√", "sqrt", lambda: self.insert_text("√")), ("ʸ√x", "root", lambda: self.insert_function("root")),
            ("1/x", "reciprocal", self.insert_reciprocal), ("|x|", "abs", lambda: self.insert_function("abs")),
            ("x!", "factorial", lambda: self.insert_text("!")), ("e", "e", lambda: self.insert_text("e")),
            ("nCr", "ncr", lambda: self.insert_function("nCr")), ("nPr", "npr", lambda: self.insert_function("nPr")),
            ("log", "log", lambda: self.insert_function("log")), ("ln", "ln", lambda: self.insert_function("ln")),
            ("Ans", "ans", lambda: self.insert_text("Ans")), ("EE", "ee", lambda: self.insert_text("e")),
            ("C", "clear", lambda: self.input_code("C")), ("＝", "equals", self.commit_expression),
        ]
        self.scientific_buttons: dict[str, QPushButton] = {}
        for index, (label, key, callback) in enumerate(specs):
            button = self._button(label, callback)
            layout.addWidget(button, index // 4, index % 4)
            self.scientific_buttons[key] = button
        numbers = [('7','7'), ('8','8'), ('9','9'), ('÷','/'),
                   ('4','4'), ('5','5'), ('6','6'), ('×','*'),
                   ('1','1'), ('2','2'), ('3','3'), ('−','-'),
                   ('0','0'), (self.decimal_separator,'.'), ('⌫','B'), ('+','+'),
                   ('±','N'), ('%','%'), (';', ';'), ('MR', 'MR')]
        for index, (label, code) in enumerate(numbers):
            action = self.memory_recall if code == 'MR' else lambda _checked=False, value=code: self.input_code(value)
            button = self._button(label, action)
            layout.addWidget(button, index // 4, 4 + index % 4)
            self.scientific_buttons['key_' + code] = button
        for index, (label, action) in enumerate((('MC',self.memory_clear), ('M+',self.memory_add), ('M−',self.memory_subtract))):
            layout.addWidget(self._button(label, action), 5, 4 + index)
        return page

    def _build_unit_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.unit_category = QComboBox()
        for category in UNIT_CATEGORIES:
            self.unit_category.addItem(self.t("calculator_unit_" + category), category)
        self.unit_value = QLineEdit("1")
        self.unit_source = QComboBox()
        row.addWidget(self.unit_category)
        row.addWidget(self.unit_value, 1)
        row.addWidget(self.unit_source)
        layout.addLayout(row)
        self.unit_results = QListWidget()
        layout.addWidget(self.unit_results, 1)
        self.unit_error = QLabel('')
        self.unit_error.setWordWrap(True)
        self.unit_error.hide()
        layout.addWidget(self.unit_error)
        action_row = self.unit_action_layout = QHBoxLayout()
        self.unit_copy = QPushButton(self.t("copy_result"))
        self.unit_copy.clicked.connect(self.copy_result)
        self.unit_save = QPushButton(self.t("calculator_save_result"))
        self.unit_save.clicked.connect(self.save_unit_result)
        action_row.addWidget(self.unit_copy)
        action_row.addWidget(self.unit_save)
        layout.addLayout(action_row)
        self.unit_category.currentIndexChanged.connect(self._unit_category_changed)
        self.unit_source.currentIndexChanged.connect(self.refresh_unit_results)
        self.unit_value.textChanged.connect(self.refresh_unit_results)
        self.unit_results.itemDoubleClicked.connect(self._promote_unit_result)
        self.unit_promote = self._button(self.t('calculator_unit_use_source'),
                                        lambda: self._promote_unit_result(self.unit_results.currentItem()))
        layout.addWidget(self.unit_promote)
        self._unit_category_changed()
        return page

    def _build_statistics_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.statistics_input = QTextEdit()
        self.statistics_input.setPlaceholderText(self.t("calculator_statistics_placeholder"))
        self.statistics_input.setMaximumHeight(112)
        self.statistics_input.textChanged.connect(self._invalidate_statistics)
        layout.addWidget(self.statistics_input, 1)
        self.statistics_error = QLabel("")
        self.statistics_error.setWordWrap(True)
        self.statistics_error.hide()
        layout.addWidget(self.statistics_error)
        self.statistics_results = QListWidget()
        layout.addWidget(self.statistics_results, 1)
        self.statistics_calculate = QPushButton(self.t("calculator_calculate"))
        self.statistics_calculate.clicked.connect(self.calculate_statistics)
        layout.addWidget(self.statistics_calculate)
        self.statistics_copy = self._button(self.t('copy_result'), self.copy_result)
        layout.addWidget(self.statistics_copy)
        return page

    def _build_base_page(self) -> QWidget:
        page = QWidget()
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.base_source = QComboBox()
        self.base_target = QComboBox()
        for combo in (self.base_source, self.base_target):
            for label, base in (("BIN", 2), ("OCT", 8), ("DEC", 10), ("HEX", 16)):
                combo.addItem(label, base)
        self.base_source.setCurrentIndex(self.base_source.findData(10))
        self.base_target.setCurrentIndex(self.base_target.findData(16))
        self.base_input = QLineEdit("0")
        self.base_result = QLineEdit("0")
        self.base_result.setReadOnly(True)
        self.base_error = QLabel("")
        self.base_error.setWordWrap(True)
        self.base_error.hide()
        layout.addWidget(self.base_source, 0, 0)
        layout.addWidget(self.base_input, 0, 1)
        layout.addWidget(self.base_target, 1, 0)
        layout.addWidget(self.base_result, 1, 1)
        layout.addWidget(self.base_error, 2, 0, 1, 2)
        self.base_save = QPushButton(self.t("calculator_save_result"))
        self.base_save.clicked.connect(self.save_base_result)
        layout.addWidget(self.base_save, 3, 0, 1, 2)
        self.base_copy = self._button(self.t('copy_result'), self.copy_result)
        layout.addWidget(self.base_copy, 4, 0, 1, 2)
        self.base_source.currentIndexChanged.connect(self.refresh_base_result)
        self.base_target.currentIndexChanged.connect(self.refresh_base_result)
        self.base_input.textChanged.connect(self.refresh_base_result)
        self.refresh_base_result()
        return page

    def _build_history_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("CalculatorHistoryPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 0, 0, 0)
        search_row = QHBoxLayout()
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText(self.t("calculator_history_search"))
        self.history_filter = QComboBox()
        self.history_filter.addItem(self.t("calculator_history_all"), None)
        for mode in MODE_KEYS:
            self.history_filter.addItem(self.t(MODE_LABEL_KEYS[mode]), mode)
        search_row.addWidget(self.history_search, 1)
        search_row.addWidget(self.history_filter)
        layout.addLayout(search_row)
        self.history_status = QLabel("")
        self.history_status.setWordWrap(True)
        self.history_status.hide()
        layout.addWidget(self.history_status)
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(lambda _item: self.restore_selected_history())
        layout.addWidget(self.history_list, 1)
        buttons = QGridLayout()
        for key, callback in (("calculator_history_restore", self.restore_selected_history),
                              ("copy_result", self.copy_selected_history_result),
                              ("calculator_history_delete", self.delete_selected_history),
                              ("calculator_history_clear", self.clear_history)):
            index = buttons.count()
            buttons.addWidget(self._button(self.t(key), callback), index // 2, index % 2)
        layout.addLayout(buttons)
        history_copy = QToolButton()
        history_copy.setText(self.t('calculator_copy_input'))
        history_copy.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(history_copy)
        menu.addAction(self.t('calculator_copy_input'), lambda: self.copy_selected_history('input'))
        menu.addAction(self.t('calculator_copy_equation'), lambda: self.copy_selected_history('equation'))
        history_copy.setMenu(menu)
        layout.addWidget(history_copy)
        settings = QPushButton(self.t("calculator_settings"))
        settings.clicked.connect(self.settings_requested)
        layout.addWidget(settings)
        self.history_search.textChanged.connect(self.refresh_history)
        self.history_filter.currentIndexChanged.connect(self.refresh_history)
        return frame

    def set_mode(self, mode: str, *, emit: bool = True) -> None:
        if mode not in MODE_KEYS:
            mode = "basic"
        if self.mode in self.drafts and hasattr(self, "expression_edit"):
            self.drafts[self.mode] = self.expression_edit.text() or "0"
            self._draft_results[self.mode] = (self._just_committed, self._committed_input,
                                              self._committed_result, self._continuation_ans)
        self.mode = mode
        self.stack.setCurrentWidget(self.pages[mode])
        calculation_mode = mode in self.drafts
        self.expression_frame.setVisible(calculation_mode)
        if calculation_mode:
            state = self._draft_results.get(mode, (False, '', None, None))
            self._continuation_ans = state[3]
            self._set_expression(self.drafts[mode])
            self._just_committed, self._committed_input, self._committed_result = state[:3]
        for key, button in self.mode_buttons.items():
            button.setChecked(key == mode)
        if emit:
            self.mode_changed.emit(mode)
            self._event("calculator_mode_changed", mode=mode, outcome="success")
        self.stack.updateGeometry()
        self.layout().invalidate()
        self.updateGeometry()
        self.layout_changed.emit()

    def _set_expression(self, text: str) -> None:
        self._syncing_expression = True
        try:
            self.expression_edit.setText(text or "0")
        finally:
            self._syncing_expression = False
        self._expression_changed(self.expression_edit.text())

    def _expression_changed(self, text: str) -> None:
        if 'ans' not in text.lower():
            self._continuation_ans = None
        if not self._syncing_expression:
            self._just_committed = False
            self._committed_result = None
            self._committed_input = ''
        if self.mode in self.drafts:
            self.drafts[self.mode] = text or "0"
        if not text.strip():
            self._last_preview = None
            self.preview_label.clear()
            self.error_label.clear()
            self.error_label.hide()
            return
        try:
            self._last_preview = self.engine.calculate(text, decimal_separator=self.decimal_separator,
                                                       ans_value=self._continuation_ans)
            self.preview_label.setText(self._local_number(self._last_preview.display))
            self.error_label.clear()
            self.error_label.hide()
        except CalculatorError as exc:
            self._last_preview = None
            self.preview_label.clear()
            self.error_label.setText(self._error_text(exc))
            self.error_label.show()
        self.layout_changed.emit()

    def input_code(self, code: str) -> None:
        expression = self.expression_edit.text() or "0"
        if code == "C":
            expression = "0"
            self._just_committed = False
        elif code == "B":
            self._just_committed = False
            self.expression_edit.backspace()
            if not self.expression_edit.text():
                self._set_expression('0')
            return
        elif code == "N":
            if self._just_committed and self._committed_result is not None:
                expression = self._local_number(self._committed_result.full_text)
            expression = expression[1:] if expression.startswith("-") else ("-" + expression if expression != "0" else "0")
            self._just_committed = False
        elif code == "=":
            self.commit_expression()
            return
        else:
            self.insert_text(self.decimal_separator if code == '.' else code)
            self._event('calculator_input', mode=self.mode, action='button')
            return
        self._set_expression(expression)
        self._event("calculator_input", mode=self.mode, action="button")

    def _prepare_insertion(self, text: str) -> None:
        if not text:
            return
        operator = text[:1] in '+-*/^%!×÷−'
        if self.expression_edit.selectedText() == self.expression_edit.text():
            self._continuation_ans = None
        if self._just_committed:
            if operator and self._committed_result is not None:
                full = self._committed_result.full_text
                self._continuation_ans = self._committed_result.value if len(full) >= 480 else None
                self._set_expression(self._local_number(full) if len(full) < 480 else 'Ans')
                self.expression_edit.setCursorPosition(len(self.expression_edit.text()))
            else:
                self.expression_edit.selectAll()
        elif self.expression_edit.text() == '0' and not operator:
            self.expression_edit.selectAll()
        self._just_committed = False

    def insert_text(self, text: str) -> None:
        self._prepare_insertion(text)
        self.expression_edit.insert(text)
        self._just_committed = False

    def insert_function(self, name: str) -> None:
        self.insert_text(name + "(")

    def insert_reciprocal(self) -> None:
        current = self.expression_edit.text().strip()
        self._set_expression(f"1/({current})" if current and current != "0" else "1/(")

    def commit_expression(self) -> None:
        if self.mode not in ("basic", "scientific"):
            return
        if self._just_committed:
            return
        expression = self.expression_edit.text().strip()
        prior_ans = self._canonical_number(self.engine.ans if self._continuation_ans is None else self._continuation_ans)
        try:
            result = self.engine.calculate(expression, commit=True, decimal_separator=self.decimal_separator,
                                           ans_value=self._continuation_ans)
        except CalculatorError as exc:
            self.error_label.setText(self._error_text(exc))
            self.error_label.show()
            self.layout_changed.emit()
            self._event("calculator_calculated", mode=self.mode, outcome="error", error=exc.code)
            return
        self._add_history(self.mode, result.canonical_expression, result.full_text,
                         {"canonical": result.canonical_expression, "full_result": result.full_text,
                          "angle_mode": self.engine.angle_mode, "ans": prior_ans})
        self._set_expression(self._local_number(result.display))
        self._committed_result = result
        self._committed_input = result.canonical_expression
        self._just_committed = True
        self.refresh_history()
        self.submitted.emit(self.mode, expression, result.display)
        self._event("calculator_calculated", mode=self.mode, outcome="success")

    def memory_clear(self) -> None:
        self.engine.memory_clear()
        self._event("calculator_memory", mode=self.mode, action="clear")

    def memory_recall(self) -> None:
        self.insert_text(self._local_number(format_full_decimal(self.engine.memory_recall())))
        self._event("calculator_memory", mode=self.mode, action="recall")

    def _preview_value(self) -> Decimal | None:
        if self._just_committed and self._committed_result is not None:
            return self._committed_result.value
        return self._last_preview.value if self._last_preview is not None else None

    def memory_add(self) -> None:
        value = self._preview_value()
        if value is not None:
            try:
                self.engine.memory_add(value)
            except CalculatorError as exc:
                self.error_label.setText(self._error_text(exc))
                self.error_label.show()
                self.layout_changed.emit()
                return
            self._event("calculator_memory", mode=self.mode, action="add")

    def memory_subtract(self) -> None:
        value = self._preview_value()
        if value is not None:
            try:
                self.engine.memory_subtract(value)
            except CalculatorError as exc:
                self.error_label.setText(self._error_text(exc))
                self.error_label.show()
                self.layout_changed.emit()
                return
            self._event("calculator_memory", mode=self.mode, action="subtract")

    def toggle_second(self) -> None:
        self._second = not self._second
        labels = ("asin", "acos", "atan") if self._second else ("sin", "cos", "tan")
        for index, key in enumerate(("trig1", "trig2", "trig3")):
            button = self.scientific_buttons[key]
            button.setText(labels[index])
            try:
                button.clicked.disconnect()
            except TypeError:
                pass
            button.clicked.connect(lambda _checked=False, name=labels[index]: self.insert_function(name))

    def toggle_angle(self) -> None:
        mode = "rad" if self.engine.angle_mode == "deg" else "deg"
        self.engine.set_angle_mode(mode)
        self.scientific_buttons["angle"].setText(mode.upper())
        self.angle_changed.emit(mode)
        self._expression_changed(self.expression_edit.text())
        self._event("calculator_angle_changed", mode=self.mode, angle=mode)

    def _unit_category_changed(self) -> None:
        category = self.unit_category.currentData()
        self.unit_source.blockSignals(True)
        self.unit_source.clear()
        if category in UNIT_CATEGORIES:
            self.unit_source.addItems(list(UNIT_CATEGORIES[category]))
        self.unit_source.blockSignals(False)
        self.refresh_unit_results()

    def refresh_unit_results(self) -> None:
        if not hasattr(self, "unit_results"):
            return
        previous = self.unit_results.currentItem()
        selected = previous.data(Qt.ItemDataRole.UserRole)[0] if previous is not None else None
        self.unit_results.clear()
        self._unit_selected = None
        category = self.unit_category.currentData()
        source = self.unit_source.currentText()
        try:
            amounts = parse_statistics(self.unit_value.text(), decimal_separator=self.decimal_separator)
            if len(amounts) != 1:
                raise CalculatorError('invalid source value', 'invalid_number')
            results = convert_all_units(category, amounts[0], source)
        except CalculatorError as exc:
            self.unit_error.setText(self._error_text(exc))
            self.unit_error.show()
            self.unit_save.setEnabled(False)
            self.layout_changed.emit()
            return
        self.unit_error.clear()
        self.unit_error.hide()
        self.unit_save.setEnabled(True)
        for unit, value in results.items():
            display = self._local_number(format_decimal(value))
            item = QListWidgetItem(f"{display} {unit}")
            item.setData(Qt.ItemDataRole.UserRole, (unit, format_full_decimal(value)))
            self.unit_results.addItem(item)
            if unit == selected:
                self.unit_results.setCurrentItem(item)
        self.layout_changed.emit()

    def _promote_unit_result(self, item: QListWidgetItem) -> None:
        if item is None:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        unit, value = data
        self.unit_value.setText(self._local_number(value))
        self.unit_source.setCurrentText(unit)

    def save_unit_result(self) -> None:
        item = self.unit_results.currentItem()
        if item is None:
            return
        target, result = item.data(Qt.ItemDataRole.UserRole)
        category = self.unit_category.currentData()
        source = self.unit_source.currentText()
        source_value = format_full_decimal(parse_statistics(self.unit_value.text(), decimal_separator=self.decimal_separator)[0])
        input_text = f"{source_value} {source}"
        result_text = f"{result} {target}"
        self._add_history("unit", input_text, result_text,
                         {"category": category, "source_unit": source,
                          "target_unit": target, "source_value": source_value, "target_value": result})
        self.refresh_history()
        self.submitted.emit("unit", input_text, result_text)
        self._event("calculator_saved", mode="unit", outcome="success")

    def calculate_statistics(self) -> None:
        self.statistics_error.clear()
        self.statistics_results.clear()
        try:
            values = parse_statistics(self.statistics_input.toPlainText(), decimal_separator=self.decimal_separator)
            summary = describe_statistics(values)
        except CalculatorError as exc:
            self.statistics_error.setText(self._error_text(exc))
            self.statistics_error.show()
            self.layout_changed.emit()
            self._event("calculator_calculated", mode="statistics", outcome="error", error=exc.code)
            return
        payload_summary = {key: str(value) if isinstance(value, int) else self._canonical_number(value)
                           for key, value in summary.items()}
        self._render_statistics(payload_summary)
        mean = self._canonical_number(summary['mean'])
        canonical_values = [self._canonical_number(value) for value in values]
        source = '; '.join(canonical_values)
        self._add_history("statistics", source, mean,
                         {"values": canonical_values, "summary": payload_summary})
        self.refresh_history()
        self.submitted.emit("statistics", source, mean)
        self._event("calculator_calculated", mode="statistics", outcome="success", count=len(values))

    def _invalidate_statistics(self):
        self._statistics_summary = None
        if hasattr(self, 'statistics_results'):
            self.statistics_results.clear()

    def _render_statistics(self, summary):
        self._statistics_summary = summary
        self.statistics_error.clear()
        self.statistics_error.hide()
        self.statistics_results.clear()
        for key in STATISTIC_LABEL_KEYS:
            if key not in summary:
                continue
            full = str(summary[key])
            item = QListWidgetItem(f'{self.t(STATISTIC_LABEL_KEYS[key])}: {self._local_number(format_decimal(Decimal(full)))}')
            item.setData(Qt.ItemDataRole.UserRole, full)
            self.statistics_results.addItem(item)
        self.layout_changed.emit()

    def refresh_base_result(self) -> None:
        if not hasattr(self, "base_result"):
            return
        try:
            result = convert_base(self.base_input.text(), self.base_source.currentData(), self.base_target.currentData())
            self.base_result.setText(result)
            self.base_error.clear()
            self.base_error.hide()
            self._base_valid = True
        except CalculatorError as exc:
            self.base_result.clear()
            self.base_error.setText(self._error_text(exc))
            self.base_error.show()
            self._base_valid = False
        self.layout_changed.emit()

    def save_base_result(self) -> None:
        if not self._base_valid:
            return
        source_base = self.base_source.currentData()
        target_base = self.base_target.currentData()
        source = convert_base(self.base_input.text(), source_base, source_base)
        result = self.base_result.text()
        input_text = source
        result_text = result
        self._add_history("base", input_text, result_text,
                         {"source_base": source_base, "target_base": target_base,
                          "source_value": source, "target_value": result})
        self.refresh_history()
        self.submitted.emit("base", input_text, result_text)
        self._event("calculator_saved", mode="base", outcome="success")

    def _set_history_visible(self, visible: bool) -> None:
        self.history_frame.setVisible(bool(visible))
        if visible:
            self.refresh_history()
        self.update_responsive_layout()
        self.history_visibility_changed.emit(bool(visible))
        self._event("calculator_history_toggled", mode=self.mode, visible=bool(visible))
        self.layout_changed.emit()

    def refresh_history(self) -> None:
        if not hasattr(self, "history_list"):
            return
        query = self.history_search.text()
        mode = self.history_filter.currentData()
        entries = self.history.search(query, mode=mode)
        self.history_list.clear()
        for entry in reversed(entries):
            source, result = self._history_display(entry)
            item = QListWidgetItem(f"[{self.t(MODE_LABEL_KEYS[entry.mode])}] {source} = {result}")
            item.setData(Qt.ItemDataRole.UserRole, entry.id)
            self.history_list.addItem(item)
        if self.history.read_error:
            self.history_status.setText(self.t("calculator_history_read_error"))
        elif self.history.write_error:
            self.history_status.setText(self.t("calculator_history_write_error"))
        else:
            self.history_status.setText("")
        self.history_status.setVisible(bool(self.history_status.text()))
        self.storage_status.setText(self.history_status.text())
        self.storage_status.setVisible(bool(self.history_status.text()))
        self.layout_changed.emit()

    def _add_history(self, *args):
        try:
            self.history.add(*args)
        except (ValueError, OSError) as exc:
            self.history.write_error = str(exc)

    def _local_number(self, text):
        return str(text).replace('.', self.decimal_separator)

    @staticmethod
    def _canonical_number(value):
        if value and (value.adjusted() > 64 or value.adjusted() < -32):
            coefficient, exponent = format(value, 'e').split('e')
            if '.' in coefficient:
                coefficient = coefficient.rstrip('0').rstrip('.')
            return coefficient + 'e' + exponent.lstrip('+')
        return format_full_decimal(value)

    def _local_expression(self, text):
        return text.replace(',', ';').replace('.', ',') if self.decimal_separator == ',' else text

    def _history_number(self, text):
        try:
            return self._local_number(format_decimal(Decimal(text)))
        except (DecimalException, CalculatorError, ValueError):
            return self._local_number(text)

    def _history_display(self, entry):
        if entry.mode == 'statistics' and isinstance(entry.payload.get('summary'), dict):
            mean = entry.payload['summary'].get('mean', entry.result)
            return self._local_number(entry.input), f"{self.t('calculator_stat_mean')}: {self._history_number(mean)}"
        if entry.mode == 'base':
            labels = {2: 'BIN', 8: 'OCT', 10: 'DEC', 16: 'HEX'}
            return (f"{entry.input} ({labels.get(entry.payload.get('source_base'), '')})",
                    f"{entry.result} ({labels.get(entry.payload.get('target_base'), '')})")
        if entry.mode == 'unit' and 'target_value' in entry.payload:
            return (self._local_expression(entry.input),
                    f"{self._history_number(entry.payload['target_value'])} {entry.payload.get('target_unit', '')}".strip())
        return self._local_expression(entry.input), self._history_number(entry.result)

    def _selected_history(self) -> HistoryEntry | None:
        item = self.history_list.currentItem()
        if item is None:
            return None
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        return next((entry for entry in self.history.entries if entry.id == entry_id), None)

    def restore_selected_history(self) -> None:
        entry = self._selected_history()
        if entry is None:
            return
        self.set_mode(entry.mode)
        self._just_committed = False
        if entry.mode in ("basic", "scientific"):
            angle = entry.payload.get('angle_mode', self.engine.angle_mode)
            if angle in ('deg', 'rad'):
                self.engine.set_angle_mode(angle)
                self.scientific_buttons['angle'].setText(angle.upper())
                self.angle_changed.emit(angle)
            if isinstance(entry.payload.get('ans'), str):
                try:
                    if len(entry.payload['ans']) > 10_032:
                        raise ValueError('invalid answer')
                    value = Decimal(entry.payload['ans'])
                    format_full_decimal(value)
                    self._continuation_ans = value
                except (CalculatorError, ValueError, ArithmeticError):
                    self._continuation_ans = Decimal(0)
            self._set_expression(self._local_expression(entry.payload.get('canonical', entry.input)))
        elif entry.mode == "statistics":
            values = entry.payload.get("values", [])
            self.statistics_input.setPlainText("; ".join(self._local_number(value) for value in values))
            summary = entry.payload.get('summary')
            if isinstance(summary, dict):
                try:
                    self._render_statistics(summary)
                except (ValueError, ArithmeticError):
                    self._invalidate_statistics()
        elif entry.mode == "unit":
            self.unit_category.setCurrentIndex(self.unit_category.findData(entry.payload.get("category")))
            self.unit_source.setCurrentText(str(entry.payload.get("source_unit", "")))
            self.unit_value.setText(self._local_number(entry.payload.get("source_value", "")))
            self.refresh_unit_results()
            for index in range(self.unit_results.count()):
                item = self.unit_results.item(index)
                if item.data(Qt.ItemDataRole.UserRole)[0] == entry.payload.get('target_unit'):
                    self.unit_results.setCurrentItem(item)
                    break
        elif entry.mode == "base":
            self.base_source.setCurrentIndex(self.base_source.findData(entry.payload.get("source_base")))
            self.base_target.setCurrentIndex(self.base_target.findData(entry.payload.get("target_base")))
            self.base_input.setText(str(entry.payload.get("source_value", "")))
        self.history_recalled.emit(entry.id)
        self._event("calculator_history_recalled", mode=entry.mode, outcome="success")

    def copy_selected_history_result(self) -> None:
        self.copy_selected_history('result')

    def copy_selected_history(self, kind='result') -> None:
        entry = self._selected_history()
        if entry is not None:
            result = str(entry.payload.get('full_result', entry.payload.get('target_value', entry.result)))
            text = entry.input if kind == 'input' else f'{entry.input} = {result}' if kind == 'equation' else result
            QGuiApplication.clipboard().setText(text)
            self._event("calculator_copied", mode=entry.mode, kind=kind)

    def delete_selected_history(self) -> None:
        entry = self._selected_history()
        if entry is not None and self.history.delete(entry.id):
            self.refresh_history()

    def clear_history(self) -> None:
        self.history.clear()
        self.refresh_history()

    def current_copy_parts(self) -> tuple[str, str]:
        if self.mode in ("basic", "scientific"):
            if self._just_committed and self._committed_result is not None:
                return self._committed_input, self._committed_result.full_text
            source = self.expression_edit.text()
            result = self._last_preview.full_text if self._last_preview is not None else ""
            return source, result
        if self.mode == "unit":
            item = self.unit_results.currentItem()
            if item is None:
                return "", ""
            return f"{self.unit_value.text()} {self.unit_source.currentText()}", item.data(Qt.ItemDataRole.UserRole)[1]
        if self.mode == "statistics":
            selected = self.statistics_results.currentItem()
            result = (selected.data(Qt.ItemDataRole.UserRole) if selected is not None
                      else (self._statistics_summary or {}).get('mean', ''))
            return self.statistics_input.toPlainText(), str(result)
        if self.mode == "base":
            return self.base_input.text(), self.base_result.text()
        return "", ""

    def copy_result(self) -> None:
        _source, result = self.current_copy_parts()
        if result:
            QGuiApplication.clipboard().setText(result)
            self._event("calculator_copied", mode=self.mode, kind="result")

    def copy_input(self) -> None:
        source, _result = self.current_copy_parts()
        if source:
            QGuiApplication.clipboard().setText(source)
            self._event("calculator_copied", mode=self.mode, kind="input")

    def copy_equation(self) -> None:
        source, result = self.current_copy_parts()
        if source and result:
            QGuiApplication.clipboard().setText(f"{source} = {result}")
            self._event("calculator_copied", mode=self.mode, kind="equation")

    def update_responsive_layout(self, width=None) -> None:
        if width is None:
            width = self.width()
            # A scroll host may keep this widget at its old minimum width while
            # shrinking. Choose the drawer layout from the visible viewport.
            parent = self.parentWidget()
            if parent is not None:
                width = min(width, parent.width())
        action_width = (self.unit_copy.minimumSizeHint().width() + self.unit_save.minimumSizeHint().width()
                        + self.unit_action_layout.spacing())
        self.unit_action_layout.setDirection(
            QBoxLayout.Direction.TopToBottom if width < action_width else QBoxLayout.Direction.LeftToRight)
        self.pages['unit'].layout().invalidate()
        side_width = max(720, self.stack.minimumSizeHint().width() + 280 + self.body_layout.spacing())
        direction = (QBoxLayout.Direction.LeftToRight if width >= side_width
                     else QBoxLayout.Direction.TopToBottom)
        self.body_layout.setDirection(direction)
        if direction == QBoxLayout.Direction.LeftToRight:
            self.history_frame.setMinimumWidth(280)
            self.history_frame.setMaximumWidth(420)
        else:
            self.history_frame.setMinimumWidth(0)
            self.history_frame.setMaximumWidth(16_777_215)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_responsive_layout()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _event(self, name: str, **payload) -> None:
        safe_payload = {key: value for key, value in payload.items()
                        if key in {'mode', 'action', 'outcome', 'error'}}
        for key in ('kind', 'angle', 'visible'):
            if key in payload:
                safe_payload['action'] = str(payload[key])
        if 'count' in payload:
            count = payload['count']
            safe_payload['count_bucket'] = '1-10' if count <= 10 else '11-100' if count <= 100 else '101-1000' if count <= 1000 else '1001-10000'
        self.event_callback(name, **safe_payload)

    def _error_text(self, error: CalculatorError) -> str:
        key = "calc_" + getattr(error, "code", "error")
        text = self.t(key)
        if error.code == 'invalid_item':
            import re
            match = re.search(r'\d+', str(error))
            return self.t('calculator_invalid_item').format(index=match.group() if match else '?')
        return self.t("calc_error") if text == key else text
