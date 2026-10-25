# SPDX-FileCopyrightText: MyScreenDraw contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Safe, dependency-free domain layer for the classroom calculator."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from decimal import Decimal, DecimalException, InvalidOperation, Underflow, localcontext
import math
import re
from typing import Iterable


MAX_EXPRESSION_LENGTH = 512
MAX_TOKENS = 256
MAX_NESTING = 32
MAX_ABS_VALUE = Decimal("1e10000")
MAX_FACTORIAL = 1000
MAX_COMBINATION_N = 100_000
MAX_STATISTICS_VALUES = 10_000
MAX_BASE_DIGITS = 256
DECIMAL_PRECISION = 34
DISPLAY_SIGNIFICANT_DIGITS = 12
MAX_DECIMAL_EXPONENT = 10_000
MAX_INTEGER_DIGITS = MAX_DECIMAL_EXPONENT + 1


class CalculatorError(ValueError):
    """A user-correctable calculator error with a stable category."""

    def __init__(self, message: str, code: str = "invalid"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CalculationResult:
    value: Decimal
    display: str
    full_text: str
    canonical_expression: str


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    position: int


_TOKEN_RE = re.compile(
    r"\s*(?:(?P<number>(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
    r"|(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?P<op>[+\-*/^(),!%√]))"
)
_VALUE_STARTS = {"number", "name", "(", "√"}
_PI = Decimal("3.1415926535897932384626433832795028841971693993751")
_E = Decimal("2.7182818284590452353602874713526624977572470937000")


def _error(message: str = "表达式无效", code: str = "invalid") -> CalculatorError:
    return CalculatorError(message, code)


def _decimal(value: object) -> Decimal:
    try:
        if isinstance(value, str):
            text = value.strip()
            if len(text) > MAX_EXPRESSION_LENGTH or not re.fullmatch(
                    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text):
                raise _error("数值无效", "invalid_number")
            if "e" in text.lower():
                exponent = int(text.lower().split("e", 1)[1])
                if abs(exponent) > MAX_DECIMAL_EXPONENT:
                    raise _error("指数超出范围", "domain")
            result = Decimal(text)
        elif isinstance(value, Decimal):
            result = value
        elif type(value) is int:
            result = Decimal(value)
        elif isinstance(value, float):
            result = Decimal(str(value))
        else:
            raise _error("数值无效", "invalid_number")
    except (DecimalException, ValueError, TypeError) as exc:
        if isinstance(exc, CalculatorError):
            raise
        raise _error("数值无效", "invalid_number") from exc
    if not result.is_finite():
        raise _error("结果溢出", "overflow")
    return result


def _checked(value: Decimal) -> Decimal:
    value = _decimal(value)
    if value.copy_abs() > MAX_ABS_VALUE:
        raise _error("结果溢出", "overflow")
    if value and value.adjusted() < -MAX_DECIMAL_EXPONENT:
        raise _error("指数超出范围", "domain")
    return value


def _binary(left: Decimal, right: Decimal, operator: str) -> Decimal:
    """Keep integer operations exact without changing ordinary decimal precision."""
    with localcontext() as context:
        integral = left == left.to_integral_value() and right == right.to_integral_value()
        exact_division = (operator == "/" and integral and right != 0
                          and int(left) % int(right) == 0)
        context.prec = (MAX_INTEGER_DIGITS + 2
                        if integral and (operator != "/" or exact_division)
                        else DECIMAL_PRECISION)
        try:
            if operator == "+":
                value = left + right
            elif operator == "-":
                value = left - right
            elif operator == "*":
                value = left * right
            else:
                value = left / right
            return _checked(value)
        except DecimalException as exc:
            raise _error("计算错误", "arithmetic") from exc


def format_full_decimal(value: Decimal) -> str:
    """Return a normalized copy representation, preserving every result digit."""
    value = _checked(value)
    if value == 0:
        return "0"
    if value == value.to_integral_value():
        return format(value, "f").split(".", 1)[0]
    if -20 <= value.adjusted() <= 50:
        return format(value, "f").rstrip("0").rstrip(".")
    sign, digits, exponent = value.as_tuple()
    digits = list(digits)
    while digits[-1] == 0:
        digits.pop()
        exponent += 1
    normalized = Decimal((sign, tuple(digits), exponent))
    return format(normalized, "g").replace("E+", "e").replace("E", "e")


# Retain the old private name for callers from earlier calculator implementations.
_full_decimal_text = format_full_decimal


def format_decimal(value: Decimal, significant_digits: int = DISPLAY_SIGNIFICANT_DIGITS) -> str:
    """Format the compact display without changing the underlying exact result."""
    value = _checked(value)
    if value == 0:
        return "0"
    significant_digits = max(1, min(DISPLAY_SIGNIFICANT_DIGITS, int(significant_digits)))
    with localcontext() as context:
        context.prec = significant_digits
        rounded = +value
    if -6 <= rounded.adjusted() < significant_digits:
        if rounded == rounded.to_integral_value():
            return format(rounded, "f").split(".", 1)[0]
        return format(rounded, "f").rstrip("0").rstrip(".")
    # format(..., "e") does not consult the ambient Decimal context.
    mantissa, exponent = format(rounded, "e").split("e")
    mantissa = mantissa.rstrip("0").rstrip(".") if "." in mantissa else mantissa
    return f"{mantissa}e{int(exponent)}"


def _normalize_expression(expression: str, decimal_separator: str) -> str:
    if not isinstance(expression, str) or not expression.strip():
        raise _error()
    if len(expression) > MAX_EXPRESSION_LENGTH:
        raise _error("表达式过长", "too_long")
    text = (expression.replace("×", "*").replace("÷", "/")
            .replace("−", "-").replace("π", "pi").replace("**", "^"))
    if decimal_separator == ",":
        text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    return text.replace(";", ",")


def _tokenize(expression: str, decimal_separator: str) -> tuple[list[_Token], str]:
    canonical = _normalize_expression(expression, decimal_separator)
    tokens: list[_Token] = []
    position = 0
    while position < len(canonical):
        match = _TOKEN_RE.match(canonical, position)
        if not match:
            if canonical[position:].strip() == "":
                position = len(canonical)
                break
            raise _error()
        if match.lastgroup == "number":
            kind = "number"
        elif match.lastgroup == "name":
            kind = "name"
        else:
            kind = match.group("op")
        value = match.group(match.lastgroup)
        tokens.append(_Token(kind, value, match.start(match.lastgroup)))
        position = match.end()
        if len(tokens) > MAX_TOKENS:
            raise _error("表达式过长", "too_long")
    tokens.append(_Token("eof", "", len(canonical)))
    return tokens, canonical


class _Parser:
    def __init__(self, tokens: list[_Token], *, angle_mode: str, ans: Decimal):
        self.tokens = tokens
        self.index = 0
        self.depth = 0
        self.call_depth = 0
        self.angle_mode = angle_mode
        self.ans = ans

    @property
    def current(self) -> _Token:
        return self.tokens[self.index]

    def consume(self, kind: str | None = None) -> _Token:
        token = self.current
        if kind is not None and token.kind != kind:
            raise _error()
        self.index += 1
        return token

    def parse(self) -> Decimal:
        value = self.expression()
        if self.current.kind != "eof":
            raise _error()
        return _checked(value)

    def expression(self) -> Decimal:
        value = self.term()
        while self.current.kind in ("+", "-"):
            operator = self.consume().kind
            right = self.term()
            value = _binary(value, right, operator)
        return value

    def term(self) -> Decimal:
        value = self.unary()
        while True:
            if self.current.kind in ("*", "/"):
                operator = self.consume().kind
                right = self.unary()
                try:
                    value = _binary(value, right, operator)
                except (ArithmeticError, InvalidOperation, ZeroDivisionError) as exc:
                    raise _error("计算错误", "arithmetic") from exc
                value = _checked(value)
                continue
            if self.current.kind in _VALUE_STARTS:
                value = _binary(value, self.unary(), "*")
                continue
            return value

    def unary(self) -> Decimal:
        self.call_depth += 1
        if self.call_depth > MAX_NESTING + 1:
            raise _error("表达式过长", "too_long")
        try:
            if self.current.kind == "+":
                self.consume("+")
                return self.unary()
            if self.current.kind == "-":
                self.consume("-")
                return _checked(self.unary().copy_negate())
            return self.power()
        finally:
            self.call_depth -= 1

    def power(self) -> Decimal:
        value = self.postfix()
        if self.current.kind == "^":
            self.consume("^")
            value = self._power(value, self.unary())
        return value

    def postfix(self) -> Decimal:
        value = self.primary()
        while self.current.kind in ("!", "%"):
            operator = self.consume().kind
            if operator == "%":
                value = _binary(value, Decimal(100), '/')
            else:
                integer = self._integer(value, "factorial")
                if integer < 0 or integer > MAX_FACTORIAL:
                    raise _error("阶乘参数超出范围", "domain")
                value = _checked(Decimal(math.factorial(integer)))
        return value

    def primary(self) -> Decimal:
        token = self.current
        if token.kind == "number":
            self.consume("number")
            return _checked(_decimal(token.value))
        if token.kind == "(":
            self.consume("(")
            self.depth += 1
            if self.depth > MAX_NESTING:
                raise _error("表达式过长", "too_long")
            value = self.expression()
            self.consume(")")
            self.depth -= 1
            return value
        if token.kind == "√":
            self.consume("√")
            return self._call("sqrt", [self.unary()])
        if token.kind == "name":
            name = self.consume("name").value.lower()
            constants = {"pi": _PI, "e": _E, "ans": self.ans}
            if name in constants:
                return constants[name]
            if self.current.kind == "(":
                self.consume("(")
                self.depth += 1
                if self.depth > MAX_NESTING:
                    raise _error("表达式过长", "too_long")
                arguments: list[Decimal] = []
                if self.current.kind != ")":
                    arguments.append(self.expression())
                    while self.current.kind == ",":
                        self.consume(",")
                        arguments.append(self.expression())
                self.consume(")")
                self.depth -= 1
                return self._call(name, arguments)
            raise _error("不支持的表达式", "unsupported")
        raise _error()

    @staticmethod
    def _integer(value: Decimal, operation: str) -> int:
        if value != value.to_integral_value():
            raise _error(f"{operation} 需要整数", "domain")
        return int(value)

    def _power(self, base: Decimal, exponent: Decimal) -> Decimal:
        try:
            if exponent.copy_abs() > MAX_DECIMAL_EXPONENT:
                raise _error("指数超出范围", "domain")
            with localcontext() as context:
                context.Emax = MAX_DECIMAL_EXPONENT
                context.Emin = -MAX_DECIMAL_EXPONENT
                context.traps[Underflow] = True
                if exponent == exponent.to_integral_value():
                    integer = int(exponent)
                    if base == base.to_integral_value() and integer >= 0:
                        if base.copy_abs() > 1 and base.adjusted() * integer > MAX_DECIMAL_EXPONENT:
                            raise _error("结果溢出", "overflow")
                        context.prec = MAX_INTEGER_DIGITS + 2
                    return _checked(base ** integer)
                if base < 0:
                    raise _error("幂运算定义域错误", "domain")
                return _checked(base ** exponent)
        except CalculatorError:
            raise
        except (ArithmeticError, ValueError) as exc:
            raise _error("计算错误", "arithmetic") from exc

    def _call(self, name: str, arguments: list[Decimal]) -> Decimal:
        unary = {"sin", "cos", "tan", "asin", "acos", "atan", "log", "ln", "sqrt", "abs"}
        if name in unary and len(arguments) != 1:
            raise _error("函数参数数量错误", "arity")
        try:
            if name == "abs":
                return _checked(arguments[0].copy_abs())
            if name == "sqrt":
                if arguments[0] < 0:
                    raise _error("平方根定义域错误", "domain")
                value = arguments[0]
                if value == value.to_integral_value():
                    root = math.isqrt(int(value))
                    if root * root == int(value):
                        return Decimal(root)
                return _checked(value.sqrt())
            if name in {"sin", "cos", "tan"}:
                if self.angle_mode == "deg":
                    with localcontext() as context:
                        context.prec = MAX_INTEGER_DIGITS + 2
                        reduced = arguments[0] % Decimal(360)
                    quarter, remainder = divmod(reduced, Decimal(90))
                    if not remainder:
                        quadrant = int(quarter) % 4
                        if name == "sin":
                            return Decimal((0, 1, 0, -1)[quadrant])
                        if name == "cos":
                            return Decimal((1, 0, -1, 0)[quadrant])
                        if quadrant % 2:
                            raise _error("正切定义域错误", "domain")
                        return Decimal(0)
                    angle = math.radians(float(reduced))
                else:
                    angle = float(arguments[0])
                    if not math.isfinite(angle):
                        raise _error("角度超出范围", "domain")
                    if name == "tan" and math.isclose(
                            abs(math.remainder(angle, math.pi)), math.pi / 2,
                            rel_tol=0, abs_tol=1e-14):
                        raise _error("正切定义域错误", "domain")
                return _checked(_decimal(getattr(math, name)(angle)))
            if name in {"asin", "acos", "atan"}:
                result = getattr(math, name)(float(arguments[0]))
                if self.angle_mode == "deg":
                    result = math.degrees(result)
                return _checked(_decimal(result))
            if name == "log":
                if arguments[0] <= 0:
                    raise _error("对数定义域错误", "domain")
                return _checked(arguments[0].log10())
            if name == "ln":
                if arguments[0] <= 0:
                    raise _error("对数定义域错误", "domain")
                return _checked(arguments[0].ln())
            if name == "root":
                if len(arguments) != 2:
                    raise _error("函数参数数量错误", "arity")
                degree = self._integer(arguments[1], "root")
                if degree == 0 or abs(degree) > 1000:
                    raise _error("根指数超出范围", "domain")
                value = arguments[0]
                if value < 0 and degree % 2 == 0:
                    raise _error("根式定义域错误", "domain")
                if value == 0 and degree < 0:
                    raise _error("根式定义域错误", "domain")
                magnitude = value.copy_abs()
                root = None
                if magnitude == magnitude.to_integral_value():
                    integer = int(magnitude)
                    candidate = _integer_root(integer, abs(degree))
                    if candidate ** abs(degree) == integer:
                        root = Decimal(candidate)
                if root is None:
                    root = magnitude ** (Decimal(1) / abs(degree))
                if degree < 0:
                    root = _binary(Decimal(1), root, "/")
                return _checked(root.copy_negate() if value < 0 else root)
            if name in {"ncr", "npr"}:
                if len(arguments) != 2:
                    raise _error("函数参数数量错误", "arity")
                n = self._integer(arguments[0], name)
                r = self._integer(arguments[1], name)
                if n < 0 or r < 0 or r > n or n > MAX_COMBINATION_N:
                    raise _error("排列组合参数超出范围", "domain")
                log_size = (math.lgamma(n + 1) - math.lgamma(n - r + 1)
                            - (math.lgamma(r + 1) if name == "ncr" else 0)) / math.log(10)
                if log_size > MAX_DECIMAL_EXPONENT + 1:
                    raise _error("结果溢出", "overflow")
                result = math.comb(n, r) if name == "ncr" else math.perm(n, r)
                return _checked(Decimal(result))
        except CalculatorError:
            raise
        except (ArithmeticError, InvalidOperation, OverflowError, ValueError) as exc:
            raise _error("计算错误", "arithmetic") from exc
        raise _error("不支持的函数", "unsupported")


def _integer_root(value: int, degree: int) -> int:
    if value < 2 or degree == 1:
        return value
    if degree >= value.bit_length():
        return 1
    candidate = 1 << ((value.bit_length() + degree - 1) // degree)
    for _ in range(2000):
        next_candidate = ((degree - 1) * candidate
                          + value // candidate ** (degree - 1)) // degree
        if next_candidate >= candidate:
            return candidate
        candidate = next_candidate
    raise _error("根式参数超出范围", "domain")


class CalculatorEngine:
    """State shared by the basic and scientific calculator pages."""

    def __init__(self, *, angle_mode: str = "deg"):
        self.angle_mode = angle_mode if angle_mode in ("deg", "rad") else "deg"
        self.ans = Decimal(0)
        self.memory = Decimal(0)

    def calculate(self, expression: str, *, commit: bool = False,
                  decimal_separator: str = ".", ans_value: Decimal | None = None) -> CalculationResult:
        tokens, canonical = _tokenize(expression, decimal_separator)
        try:
            with localcontext() as context:
                context.prec = DECIMAL_PRECISION
                value = _Parser(tokens, angle_mode=self.angle_mode,
                                ans=self.ans if ans_value is None else _checked(ans_value)).parse()
        except DecimalException as exc:
            raise _error("计算错误", "arithmetic") from exc
        result = CalculationResult(value, format_decimal(value), _full_decimal_text(value), canonical)
        if commit:
            self.ans = value
        return result

    def set_angle_mode(self, mode: str) -> None:
        if mode not in ("deg", "rad"):
            raise _error("角度模式无效", "invalid_mode")
        self.angle_mode = mode

    def memory_clear(self) -> None:
        self.memory = Decimal(0)

    def memory_recall(self) -> Decimal:
        return self.memory

    def memory_add(self, value: Decimal | None = None) -> Decimal:
        self.memory = _binary(self.memory, self.ans if value is None else _checked(_decimal(value)), "+")
        return self.memory

    def memory_subtract(self, value: Decimal | None = None) -> Decimal:
        self.memory = _binary(self.memory, self.ans if value is None else _checked(_decimal(value)), "-")
        return self.memory


def evaluate(expression: str) -> float | int:
    """Backward-compatible numeric evaluation used by the existing basic UI."""
    value = CalculatorEngine().calculate(expression).value
    if value == value.to_integral_value():
        return int(value)
    return float(value)


UNIT_CATEGORIES: dict[str, dict[str, Decimal]] = {
    "length": {"mm": Decimal("0.001"), "cm": Decimal("0.01"), "dm": Decimal("0.1"),
               "m": Decimal(1), "km": Decimal(1000)},
    "area": {"mm²": Decimal("0.000001"), "cm²": Decimal("0.0001"),
             "dm²": Decimal("0.01"), "m²": Decimal(1), "ha": Decimal(10_000),
             "km²": Decimal(1_000_000)},
    "volume": {"cm³": Decimal("0.000001"), "mL": Decimal("0.000001"),
               "dm³": Decimal("0.001"), "L": Decimal("0.001"), "m³": Decimal(1)},
    "mass": {"mg": Decimal("0.000001"), "g": Decimal("0.001"),
             "kg": Decimal(1), "t": Decimal(1000)},
    "temperature": {"°C": Decimal(1), "K": Decimal(1)},
    "time": {"ms": Decimal("0.001"), "s": Decimal(1), "min": Decimal(60),
             "h": Decimal(3600), "d": Decimal(86_400)},
    "speed": {"m/s": Decimal(1), "km/h": Decimal(5) / Decimal(18)},
    "angle": {"°": _PI / Decimal(180), "rad": Decimal(1)},
}


def convert_unit(category: str, value: object, source_unit: str, target_unit: str) -> Decimal:
    if category not in UNIT_CATEGORIES:
        raise _error("单位类别无效", "invalid_unit")
    units = UNIT_CATEGORIES[category]
    if source_unit not in units or target_unit not in units:
        raise _error("单位无效", "invalid_unit")
    amount = _checked(_decimal(value))
    try:
        if category == "temperature":
            kelvin = (Fraction(amount) + Fraction(27315, 100)
                      if source_unit == "°C" else Fraction(amount))
            if kelvin < 0:
                raise _error("温度低于绝对零度", "domain")
            converted = kelvin - Fraction(27315, 100) if target_unit == "°C" else kelvin
        else:
            factors = {unit: Fraction(factor) for unit, factor in units.items()}
            if category == "speed":
                factors["km/h"] = Fraction(5, 18)
            elif category == "angle":
                factors["°"] = Fraction(_PI) / 180
            converted = Fraction(amount) * factors[source_unit] / factors[target_unit]
        return _binary(Decimal(converted.numerator), Decimal(converted.denominator), "/")
    except (DecimalException, ZeroDivisionError, OverflowError) as exc:
        raise _error("计算错误", "arithmetic") from exc


def convert_all_units(category: str, value: object, source_unit: str) -> dict[str, Decimal]:
    if category not in UNIT_CATEGORIES:
        raise _error("单位类别无效", "invalid_unit")
    return {unit: convert_unit(category, value, source_unit, unit)
            for unit in UNIT_CATEGORIES[category]}


def parse_statistics(text: str, *, decimal_separator: str = ".") -> list[Decimal]:
    if not isinstance(text, str) or not text.strip():
        raise _error("请输入统计数据", "empty")
    if len(text) > MAX_STATISTICS_VALUES * (MAX_EXPRESSION_LENGTH + 1):
        raise _error("统计数据过多", "too_many_values")
    separators = r";" if decimal_separator == "," else r"[;,]"
    values: list[Decimal] = []
    for group in re.split(separators, text.strip()):
        items = group.split() or [""]
        for item in items:
            if len(values) >= MAX_STATISTICS_VALUES:
                raise _error("统计数据过多", "too_many_values")
            index = len(values) + 1
            try:
                if decimal_separator == ",":
                    item = item.replace(",", ".")
                values.append(_checked(_decimal(item)))
            except (CalculatorError, DecimalException, ValueError) as exc:
                raise _error(f"第 {index} 项数据无效", "invalid_item") from exc
    return values


def describe_statistics(values: Iterable[object]) -> dict[str, Decimal | int]:
    numbers: list[Decimal] = []
    for value in values:
        if len(numbers) >= MAX_STATISTICS_VALUES:
            raise _error("统计数据过多", "too_many_values")
        try:
            numbers.append(_checked(_decimal(value)))
        except CalculatorError as exc:
            raise _error(f"第 {len(numbers) + 1} 项数据无效", "invalid_item") from exc
    if not numbers:
        raise _error("请输入统计数据", "empty")
    try:
        with localcontext() as context:
            context.prec = DECIMAL_PRECISION
            count = len(numbers)
            total = Decimal(0)
            for value in numbers:
                total = _binary(total, value, "+")
            mean = _binary(total, Decimal(count), "/")
            ordered = sorted(numbers)
            middle = count // 2
            median = (ordered[middle] if count % 2 else
                      _binary(_binary(ordered[middle - 1], ordered[middle], "+"), Decimal(2), "/"))
            squared_differences = Decimal(0)
            for value in numbers:
                difference = _binary(value, mean, "-")
                squared_differences = _binary(
                    squared_differences, _binary(difference, difference, "*"), "+")
            variance = _binary(squared_differences, Decimal(count), "/")
            return {
                "count": count,
                "sum": total,
                "mean": mean,
                "median": median,
                "minimum": ordered[0],
                "maximum": ordered[-1],
                "range": _binary(ordered[-1], ordered[0], "-"),
                "population_variance": variance,
                "population_stddev": _checked(variance.sqrt()),
            }
    except DecimalException as exc:
        raise _error("计算错误", "arithmetic") from exc


_BASE_PREFIXES = {2: "0b", 8: "0o", 16: "0x"}
_BASE_DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def convert_base(text: str, source_base: int, target_base: int) -> str:
    if source_base not in (2, 8, 10, 16) or target_base not in (2, 8, 10, 16):
        raise _error("进制无效", "invalid_base")
    if not isinstance(text, str) or not text.strip():
        raise _error("请输入整数", "empty")
    cleaned = re.sub(r"[\s_]", "", text.strip())
    sign = ""
    if cleaned[:1] in ("+", "-"):
        sign, cleaned = cleaned[0], cleaned[1:]
    lowered = cleaned.lower()
    for base, prefix in _BASE_PREFIXES.items():
        if lowered.startswith(prefix):
            if base != source_base:
                raise _error("前缀与来源进制不匹配", "invalid_base")
            cleaned = cleaned[len(prefix):]
            break
    if not cleaned or len(cleaned) > MAX_BASE_DIGITS:
        raise _error("进制数过长" if cleaned else "请输入整数",
                     "too_long" if cleaned else "empty")
    try:
        value = int(("-" if sign == "-" else "") + cleaned, source_base)
    except ValueError as exc:
        raise _error("数字与来源进制不匹配", "invalid_digit") from exc
    if value == 0:
        return "0"
    negative = value < 0
    remaining = abs(value)
    digits: list[str] = []
    while remaining:
        remaining, remainder = divmod(remaining, target_base)
        digits.append(_BASE_DIGITS[remainder])
    result = "".join(reversed(digits))
    return "-" + result if negative else result
