# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure-domain coverage for the classroom calculator."""
from decimal import Decimal

import pytest

import calculator


def test_engine_uses_decimal_arithmetic_and_commits_ans_only_on_request():
    engine = calculator.CalculatorEngine()

    preview = engine.calculate("0.1+0.2", commit=False)
    assert preview.display == "0.3"
    assert engine.ans == Decimal(0)

    committed = engine.calculate("0.1+0.2", commit=True)
    assert committed.display == "0.3"
    assert engine.ans == Decimal("0.3")


def test_engine_supports_classroom_scientific_syntax_and_degree_mode():
    engine = calculator.CalculatorEngine(angle_mode="deg")

    result = engine.calculate("sin(30)+√16", commit=True)
    assert result.display == "4.5"
    assert engine.calculate("Ans×2", commit=True).display == "9"
    assert engine.calculate("2π", commit=False).value == engine.calculate("2*pi", commit=False).value
    assert engine.calculate("2(3+4)", commit=False).display == "14"
    assert engine.calculate("(1+2)(3+4)", commit=False).display == "21"


def test_engine_rejects_non_whitelisted_python_syntax():
    engine = calculator.CalculatorEngine()

    for expression in (
        "__import__('os').system('echo unsafe')",
        "(1).__class__",
        "[x for x in (1,2)]",
        "sin30",
    ):
        with pytest.raises(calculator.CalculatorError):
            engine.calculate(expression)


def test_memory_is_shared_engine_state_but_not_changed_by_preview():
    engine = calculator.CalculatorEngine()
    engine.calculate("5", commit=True)
    engine.memory_add()
    engine.calculate("2", commit=False)

    assert engine.memory_recall() == Decimal("5")
    engine.memory_subtract(Decimal("2"))
    assert engine.memory_recall() == Decimal("3")
    engine.memory_clear()
    assert engine.memory_recall() == Decimal(0)


def test_metric_unit_conversion_uses_declared_classroom_unit_sets():
    assert calculator.convert_unit("length", "1000", "mm", "m") == Decimal("1")
    assert calculator.convert_unit("area", "10000", "m²", "ha") == Decimal("1")
    assert calculator.convert_unit("volume", "1000", "mL", "L") == Decimal("1")
    assert calculator.convert_unit("mass", "1000", "g", "kg") == Decimal("1")
    assert calculator.convert_unit("temperature", "0", "°C", "K") == Decimal("273.15")
    assert calculator.convert_unit("speed", "36", "km/h", "m/s") == Decimal("10")
    assert calculator.convert_unit("angle", "180", "°", "rad").quantize(Decimal("0.000000000001")) == Decimal("3.141592653590")

    assert tuple(calculator.UNIT_CATEGORIES) == (
        "length", "area", "volume", "mass", "temperature", "time", "speed", "angle"
    )
    assert tuple(calculator.UNIT_CATEGORIES["length"]) == ("mm", "cm", "dm", "m", "km")


def test_statistics_parser_is_strict_and_description_is_complete():
    values = calculator.parse_statistics("1, 2 3;4\n5", decimal_separator=".")
    summary = calculator.describe_statistics(values)

    assert {key: value for key, value in summary.items() if key != "population_stddev"} == {
        "count": 5,
        "sum": Decimal("15"),
        "mean": Decimal("3"),
        "median": Decimal("3"),
        "minimum": Decimal("1"),
        "maximum": Decimal("5"),
        "range": Decimal("4"),
        "population_variance": Decimal("2"),
    }
    assert calculator.format_decimal(summary["population_stddev"]) == "1.41421356237"
    assert calculator.parse_statistics("1,5; 2,5", decimal_separator=",") == [Decimal("1.5"), Decimal("2.5")]
    with pytest.raises(calculator.CalculatorError):
        calculator.parse_statistics("1; bad; 3")


def test_base_conversion_uses_signed_arbitrary_precision_without_twos_complement():
    assert calculator.convert_base("0xff", 16, 10) == "255"
    assert calculator.convert_base("-255", 10, 16) == "-FF"
    assert calculator.convert_base("1111_0000", 2, 16) == "F0"
    assert calculator.convert_base("777", 8, 2) == "111111111"
    with pytest.raises(calculator.CalculatorError):
        calculator.convert_base("2", 2, 10)
    with pytest.raises(calculator.CalculatorError):
        calculator.convert_base("1" * 257, 2, 10)


def test_legacy_evaluate_contract_remains_numeric():
    assert calculator.evaluate("2+3") == 5
    assert calculator.evaluate("1/4") == 0.25
    assert type(calculator.evaluate("2+3")) is int


def test_percentage_preserves_large_exact_integral_division():
    assert calculator.CalculatorEngine().calculate('((10^40+1)*100)%').value == 10**40 + 1



def test_exact_integer_arithmetic_and_copy_preserve_all_digits():
    engine = calculator.CalculatorEngine()
    literal = "12345678901234567890123456789012345"
    result = engine.calculate(literal, commit=True)
    assert result.value == Decimal(literal)
    assert result.full_text == literal
    assert result.display == "1.23456789012e34"
    assert engine.calculate("Ans+1-Ans").full_text == "1"
    assert engine.calculate("30!").full_text == "265252859812191058636308480000000"
    assert engine.calculate("nCr(100,50)").full_text == "100891344545564193334812497256"
    assert engine.calculate("2^200").full_text == (
        "1606938044258990275541962092341162602522202993782792835301376"
    )
    engine.memory_add(result.value)
    assert engine.memory_recall() == Decimal(literal)


def test_complete_decimal_format_never_rounds_to_the_display_precision():
    decimal = Decimal("0.1234567890123456789012345678901234")
    result = calculator.CalculatorEngine().calculate(str(decimal))
    assert result.value == decimal
    assert result.full_text == str(decimal)
    assert calculator.format_full_decimal(decimal) == str(decimal)
    assert calculator.format_full_decimal(Decimal("2000.000")) == "2000"
    assert calculator.format_full_decimal(Decimal("0E+10")) == "0"
    assert calculator.format_full_decimal(Decimal("1E-100")) == "1e-100"


@pytest.mark.parametrize("text", ["1e1000001", "1e-1000001", "1e10001", "1e-10001"])
def test_numeric_exponent_limits_raise_calculator_errors_everywhere(text):
    with pytest.raises(calculator.CalculatorError):
        calculator.CalculatorEngine().calculate(text)
    with pytest.raises(calculator.CalculatorError, match="第 2 项"):
        calculator.parse_statistics("1;" + text)
    with pytest.raises(calculator.CalculatorError):
        calculator.convert_unit("length", text, "m", "m")


def test_expression_limits_bound_nested_calls_powers_tokens_and_output():
    engine = calculator.CalculatorEngine()
    assert engine.calculate("(" * 32 + "1" + ")" * 32).full_text == "1"
    for expression in (
        "(" * 33 + "1" + ")" * 33,
        "-" * 40 + "1",
        "^".join(["1"] * 40),
        "+".join(["1"] * 130),
        "1" * 513,
        "(1e1000)^10000",
        "(1e-1000)^10000",
        "nCr(100000,50000)",
    ):
        with pytest.raises(calculator.CalculatorError):
            engine.calculate(expression)
    assert engine.calculate("1e10000").value == Decimal("1e10000")
    assert len(engine.calculate("1e10000").full_text) == 10001
    assert engine.calculate("1e-10000").full_text == "1e-10000"


@pytest.mark.parametrize("text,index", [("1;1__2;3", 2), ("1,,2", 2), ("1;", 2),
                                        ("1;NaN", 2), ("1;Infinity", 2)])
def test_statistics_rejects_invalid_or_empty_items_at_their_index(text, index):
    with pytest.raises(calculator.CalculatorError, match=f"第 {index} 项"):
        calculator.parse_statistics(text)


def test_statistics_limits_and_decimal_comma_preserve_values():
    values = calculator.parse_statistics("1,25; -2,5\n3", decimal_separator=",")
    assert values == [Decimal("1.25"), Decimal("-2.5"), Decimal("3")]
    assert len(calculator.parse_statistics(";".join(["1"] * 10000))) == 10000
    with pytest.raises(calculator.CalculatorError) as error:
        calculator.parse_statistics(";".join(["1"] * 10001))
    assert error.value.code == "too_many_values"
    with pytest.raises(calculator.CalculatorError):
        calculator.describe_statistics(iter([1] * 10001))
    with pytest.raises(calculator.CalculatorError):
        calculator.describe_statistics([Decimal("1e1000001")])
    summary = calculator.describe_statistics(["1", "2", "3", "4"])
    assert summary["sum"] == Decimal("10")
    assert summary["median"] == Decimal("2.5")
    assert summary["population_variance"] == Decimal("1.25")
    assert calculator.describe_statistics(["8"])["population_stddev"] == 0


def test_rational_units_and_temperature_keep_exact_ordinary_decimals():
    assert calculator.convert_unit("speed", "36", "km/h", "m/s") == Decimal("10")
    assert calculator.convert_unit("speed", "10", "m/s", "km/h") == Decimal("36")
    assert calculator.convert_unit("temperature", "273.15", "K", "°C") == 0
    assert calculator.convert_unit("temperature", "-273.15", "°C", "K") == 0
    with pytest.raises(calculator.CalculatorError):
        calculator.convert_unit("temperature", "-273.16", "°C", "K")
    assert calculator.convert_unit("length", "1e10000", "km", "km") == Decimal("1e10000")
    with pytest.raises(calculator.CalculatorError):
        calculator.convert_unit("length", "1e10000", "km", "mm")



def test_scientific_functions_cover_decimal_logs_roots_and_angle_domains():
    engine = calculator.CalculatorEngine(angle_mode="deg")
    assert engine.calculate("log(1e1000)").full_text == "1000"
    assert engine.calculate("log(1e-1000)").full_text == "-1000"
    assert engine.calculate("ln(1e-1000)").display == "-2302.58509299"
    assert engine.calculate("root(64,3)").full_text == "4"
    assert engine.calculate("root(-8,3)").full_text == "-2"
    assert engine.calculate("root(-8,-3)").full_text == "-0.5"
    assert engine.calculate("root(1e120,3)").full_text == "1" + "0" * 40
    assert engine.calculate("asin(1)").display == "90"
    assert engine.calculate("acos(-1)").display == "180"
    assert engine.calculate("atan(1)").display == "45"
    for expression in ("tan(90)", "tan(270)", "tan(-90)", "log(0)", "ln(-1)",
                       "root(-8,2)", "root(0,-3)", "root(1,0)", "asin(2)", "sin30"):
        with pytest.raises(calculator.CalculatorError):
            engine.calculate(expression)
    engine.set_angle_mode("rad")
    assert engine.calculate("sin(pi/2)").display == "1"
    assert engine.calculate("atan(1)").display == "0.785398163397"
    with pytest.raises(calculator.CalculatorError):
        engine.calculate("tan(pi/2)")
    assert engine.calculate("pi(2)").value == engine.calculate("pi*2").value
    assert engine.calculate("Ans(2)").value == 0



def test_exact_special_angles_and_perfect_square_roots_remain_exact():
    engine = calculator.CalculatorEngine(angle_mode="deg")
    for expression in ("sin(180)", "cos(90)", "cos(270)", "tan(180)"):
        assert engine.calculate(expression).full_text == "0"
    assert engine.calculate("sin(90)").full_text == "1"
    assert engine.calculate("sin(270)").full_text == "-1"
    assert engine.calculate("sqrt((123456789012345678901234567890123456789)^2)").full_text == (
        "123456789012345678901234567890123456789"
    )
    assert engine.calculate("50%+1/4").full_text == "0.75"


def test_base_digit_boundaries_preserve_prefix_sign_and_grouped_values():
    assert calculator.convert_base("-0x" + "F" * 256, 16, 2) == "-" + "1" * 1024
    assert calculator.convert_base("+0b" + "1" * 256, 2, 16) == "F" * 64
    assert calculator.convert_base("0o7_777", 8, 16) == "FFF"
    for text, base in (("F" * 257, 16), ("7" * 257, 8), ("1" * 257, 10),
                       ("0x10", 2), ("102", 2), ("1.2", 10)):
        with pytest.raises(calculator.CalculatorError):
            calculator.convert_base(text, base, 10)
