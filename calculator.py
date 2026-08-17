# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Safe arithmetic expression evaluator without eval/exec."""
from __future__ import annotations
import ast
import math

MAX_EXPRESSION_LENGTH = 300
MAX_NODES = 100
MAX_ABS_VALUE = 1e100

class CalculatorError(ValueError):
    pass


def evaluate(expression: str) -> float | int:
    if not isinstance(expression, str) or not expression.strip() or len(expression) > MAX_EXPRESSION_LENGTH:
        raise CalculatorError("表达式无效")
    expression = expression.replace("×", "*").replace("÷", "/").replace("−", "-")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError) as exc:
        raise CalculatorError("表达式无效") from exc
    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise CalculatorError("表达式过长")
    value = _visit(tree.body)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) or abs(float(value)) > MAX_ABS_VALUE:
        raise CalculatorError("结果溢出")
    return value


def _visit(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        if abs(float(node.value)) > MAX_ABS_VALUE:
            raise CalculatorError("数值过大")
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _visit(node.operand)
        return +value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod)):
        left, right = _visit(node.left), _visit(node.right)
        try:
            if isinstance(node.op, ast.Add): value = left + right
            elif isinstance(node.op, ast.Sub): value = left - right
            elif isinstance(node.op, ast.Mult): value = left * right
            elif isinstance(node.op, ast.Div): value = left / right
            else: value = left % right
        except (ArithmeticError, OverflowError) as exc:
            raise CalculatorError("计算错误") from exc
        if abs(float(value)) > MAX_ABS_VALUE:
            raise CalculatorError("结果溢出")
        return value
    raise CalculatorError("不支持的表达式")
