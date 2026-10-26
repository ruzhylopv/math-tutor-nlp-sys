import pytest

from tutor.tools.algebra import UnparsableError, check_answer, parse_statement, step_relation


# --- expressions -----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("prev", "curr"),
    [
        ("(2x-5)(x+7)", "2x(x)+2x(7)-5(x)-5(7)"),
        ("2x(x)+2x(7)-5(x)-5(7)", "2x^2+14x-5x-35"),
        ("2x^2+14x-5x-35", "2x^2+9x-35"),
        ("2x^2+9x-35 - (2x^2+9x-5)", "-30"),
        ("x^2-5x+6", "(x-2)(x-3)"),
    ],
)
def test_equivalent_expressions(prev: str, curr: str) -> None:
    assert step_relation(prev, curr) == "equivalent"


@pytest.mark.parametrize(
    ("prev", "curr"),
    [
        ("(2x-5)(x+7)", "2x(x)+7-5(x)-5(7)"),  # multiplied only the first term in the bracket
        ("2x^2+9x-35 - (2x^2+9x-5)", "-40"),
        ("(x-5)^2", "x^2-25"),
        ("x^2-5x+6", "(x-2)(x+3)"),
    ],
)
def test_expressions_that_are_not_equivalent(prev: str, curr: str) -> None:
    assert step_relation(prev, curr) == "not_valid"


# --- equations ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("prev", "curr"),
    [
        ("3(x+2) = 15", "3x + 6 = 15"),
        ("3x + 6 = 15", "3x = 9"),
        ("3x = 9", "x = 3"),
        ("x + 7 = x^2 - 10x + 25", "x^2 - 11x + 18 = 0"),
        ("x^2 - 11x + 18 = 0", "(x - 9)(x - 2) = 0"),
        ("(x - 9)(x - 2) = 0", "x = 9 or x = 2"),
    ],
)
def test_equivalent_equations(prev: str, curr: str) -> None:
    assert step_relation(prev, curr) == "equivalent"


def test_a_slip_in_an_equation_is_not_valid() -> None:
    assert step_relation("3(x+2) = 15", "3x + 2 = 15") == "not_valid"  # scenario A
    assert step_relation("sqrt(x+7) = x-5", "x + 7 = x^2 - 25") == "not_valid"  # scenario B


def test_squaring_both_sides_implies_but_is_not_equivalent() -> None:
    assert step_relation("sqrt(x+7) = x-5", "x + 7 = (x-5)^2") == "implies"


def test_losing_a_solution_is_not_valid() -> None:
    assert step_relation("x^2 - x = 0", "x - 1 = 0", original="x^2 - x = 0") == "not_valid"


def test_rejecting_an_extraneous_root_narrows_to_the_original_solution_set() -> None:
    original = "sqrt(x+7) = x-5"
    assert step_relation("x = 9 or x = 2", "x = 9", original=original) == "narrows"
    assert step_relation("x = 9 or x = 2", "x = 2", original=original) == "not_valid"
    assert step_relation("x = 9 or x = 2", "x = 9") == "not_valid"  # no original to compare with


def test_irrational_roots_are_compared_by_value() -> None:
    assert step_relation("x^2 - x - 32 = 0", "x = (1 + sqrt(129))/2 or x = (1 - sqrt(129))/2") == (
        "equivalent"
    )


# --- closed statements, type changes, unparsable -----------------------------------------
def test_a_true_closed_statement_is_valid_and_a_false_one_is_not() -> None:
    assert step_relation("x = 9", "sqrt(9+7) = 9-5") == "equivalent"
    assert step_relation("x = 2", "sqrt(2+7) = 2-5") == "not_valid"


def test_an_expression_that_becomes_an_equation_is_not_valid() -> None:
    assert step_relation("2x + 3", "2x + 3 = 0") == "not_valid"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "x ++",
        "hello world",
        "__import__('os')",
        "x.__class__",
        "2 +",
        "x = = 2",
        "x = 1 = 2",
        "sin(x)",
        "x = 9 or 5",
        "1.",
        "x[0]",
    ],
)
def test_unparsable_text(text: str) -> None:
    assert step_relation("x = 1", text) == "unparsable"
    with pytest.raises(UnparsableError):
        parse_statement(text)


def test_unparsable_when_the_previous_line_is() -> None:
    assert step_relation("one plus two", "3") == "unparsable"


def test_equations_with_two_variables_are_not_handled() -> None:
    assert step_relation("x + y = 2", "y = 2 - x") == "unparsable"


def test_nothing_is_executed() -> None:
    assert step_relation("x = 1", "exit()") in {"unparsable", "not_valid"}


# --- final answers -----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("answer", "truth"),
    [
        ("9", "9"),
        ("x = 9", "9"),
        ("-30", "-30"),
        ("2, 9", "x = 9 or x = 2"),
        ("2x+3", "3+2x"),
        ("1/2", "0.5"),
    ],
)
def test_correct_answers(answer: str, truth: str) -> None:
    assert check_answer(answer, truth) == "correct"


@pytest.mark.parametrize(
    ("answer", "truth"),
    [("9", "2, 9"), ("2x+3", "2x+4"), ("13/3", "3"), ("x", "9")],
)
def test_incorrect_answers(answer: str, truth: str) -> None:
    assert check_answer(answer, truth) == "incorrect"


def test_unparsable_answer() -> None:
    assert check_answer("see above", "9") == "unparsable"
