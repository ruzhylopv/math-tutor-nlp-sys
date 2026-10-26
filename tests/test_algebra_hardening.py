"""Regression tests for the problems found by the M2 review: denial of service, uncaught SymPy
errors, wrong solver answers, plus-or-minus, empty solution sets and answer-check edge cases."""

import time

import pytest

from tutor.tools import algebra
from tutor.tools.algebra import (
    UnparsableError,
    check_answer,
    claim_truth,
    final_answer_matches,
    parse_statement,
    step_relation,
)


# --- denial of service: nothing may run long -------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "x = 9^9^9",
        "x = 9**9**9",
        "x = 9^9^9^9",
        "x = 10^(10^7)",
        "x = 7^99999999",
        "(x+1)^5000",
        "(x+1)^(100000)",
        "x^(2^3)",
        "x" * 201,
    ],
)
def test_expensive_input_is_rejected_quickly(text: str) -> None:
    start = time.monotonic()
    assert step_relation("x = 1", text) == "unparsable"
    assert check_answer(text, "1") == "unparsable"
    assert time.monotonic() - start < 1.0


@pytest.mark.parametrize(
    ("prev", "curr"),
    [
        ("2^3x^3", "8x^3"),  # implicit multiplication ends the exponent: (2^3) * (x^3)
        ("7z^96 + 28z^97", "7z^96(1 + 4z)"),  # a monomial with a big exponent is cheap
        ("2^64", "18446744073709551616"),
        ("(x+1)^50", "(x+1)^50"),
    ],
)
def test_cheap_large_powers_are_allowed(prev: str, curr: str) -> None:
    assert step_relation(prev, curr) == "equivalent"


def test_a_bracketed_base_has_a_lower_exponent_cap() -> None:
    assert step_relation("(x+1)^51", "(x+1)^51") == "unparsable"
    assert step_relation("x^1001", "x^1001") == "unparsable"


def test_reasonable_powers_still_work() -> None:
    assert step_relation("(x+1)^2", "x^2 + 2x + 1") == "equivalent"
    assert step_relation("(x^2)^3", "x^6") == "equivalent"
    assert step_relation("x^(1/2)", "sqrt(x)") == "equivalent"
    assert step_relation("2^10", "1024") == "equivalent"


def test_a_stuck_solver_is_cut_off_and_reported_as_unparsable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def hang(statement: object) -> None:
        time.sleep(5)

    monkeypatch.setattr(algebra, "_solutions", hang)
    monkeypatch.setattr(algebra, "_TIMEOUT_SECONDS", 0.2)
    start = time.monotonic()
    assert step_relation("x + 1 = 2", "x = 1") == "unparsable"
    assert time.monotonic() - start < 2.0


# --- injection surface -----------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "1.5.__class__",
        "x.__class__",
        "__import__('os').system('true')",
        "().__class__",
        "lambda: 1",
        "exec(1)",
        "abcdefghij",
        "x[0]",
        "x;y",
        "3e+2",
        "1E5",
        "0x10",
        "0b11",
        "x = 1.5.2",
    ],
)
def test_nothing_outside_the_grammar_is_executed_or_accepted(text: str) -> None:
    with pytest.raises(UnparsableError):
        parse_statement(text)
    assert step_relation("x = 1", text) == "unparsable"


# --- SymPy failures never escape ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("prev", "curr"),
    [
        ("abs(x^2) + abs(x^x) = 2", "x = 1"),  # SymPy raises NotImplementedError here
        ("x^x = 4", "x = 2"),  # solveset gives a ConditionSet
    ],
)
def test_a_sympy_error_is_reported_as_unparsable(prev: str, curr: str) -> None:
    assert step_relation(prev, curr) == "unparsable"


def test_nested_abs_is_not_handled_because_the_solver_is_wrong_for_it() -> None:
    # solveset says abs(abs(x)-1) = 2 has no solutions, but x = 3 and x = -3 are solutions
    assert step_relation("abs(abs(x) - 1) = 2", "x = 3 or x = -3") == "unparsable"


# --- real domain, unusual values ---------------------------------------------------------------
def test_variables_are_real() -> None:
    assert step_relation("sqrt(x^2)", "abs(x)") == "equivalent"


def test_a_non_real_power_is_not_a_value() -> None:
    assert step_relation("(-8)^(1/3)", "-2") == "unparsable"


def test_an_identity_equation_has_all_reals_as_solutions() -> None:
    assert step_relation("x + 1 = x + 1", "x = x") == "equivalent"


# --- empty solution sets -----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("prev", "curr"),
    [
        ("x^2 + 1 = 0", "x = 1"),
        ("x + 1 = x + 2", "x = 5"),
        ("abs(x) = -1", "x = 1"),
    ],
)
def test_solving_a_contradiction_is_not_valid(prev: str, curr: str) -> None:
    assert step_relation(prev, curr) == "not_valid"


def test_two_contradictions_are_equivalent() -> None:
    assert step_relation("x + 1 = x + 2", "x^2 + 1 = 0") == "equivalent"


# --- plus or minus -----------------------------------------------------------------------------
def test_the_literal_scenario_b_line_with_plus_minus() -> None:
    assert (
        step_relation("x^2 - x - 32 = 0", "x = (1 +- sqrt(129))/2")
        == step_relation("x^2 - x - 32 = 0", "x = (1 + sqrt(129))/2 or x = (1 - sqrt(129))/2")
        == "equivalent"
    )


def test_plus_minus_forms() -> None:
    assert step_relation("x^2 = 4", "x = +-2") == "equivalent"
    assert step_relation("x^2 = 4", "x = ±2") == "equivalent"
    assert step_relation("x^2 = 4", "x = +2") == "not_valid"  # loses -2


@pytest.mark.parametrize("text", ["x = 1 +- 2 +- 3", "x = +-2 or x = 5", "+-2"])
def test_plus_minus_that_cannot_be_expanded_is_unparsable(text: str) -> None:
    assert step_relation("x = 1", text) == "unparsable"


# --- a separate rule for the check line ----------------------------------------------------------
def test_a_closed_claim_with_or_is_true_if_any_part_is() -> None:
    assert claim_truth("2 + 2 = 5 or 1 = 1") is True


# --- answer checks -----------------------------------------------------------------------------
def test_leftover_letters_cannot_be_judged() -> None:
    assert check_answer("9 cm", "9") == "unparsable"
    assert check_answer("x", "9") == "unparsable"


def test_a_thousands_separator_is_ambiguous() -> None:
    assert check_answer("1,000", "1000") == "unparsable"


def test_the_variable_name_is_compared_when_both_sides_give_one() -> None:
    assert check_answer("x = 3", "x = 3") == "correct"
    assert check_answer("x = 3", "y = 3") == "incorrect"
    assert check_answer("3", "y = 3") == "correct"


def test_the_answer_rule_is_looser_than_the_step_rule() -> None:
    assert final_answer_matches("x + 1 = 4", "3") is True
    assert step_relation("x + 1 = 4", "3") == "not_valid"


def test_no_solution_answers_are_not_recognised() -> None:
    assert final_answer_matches("2x + 3 = 2x + 4", "no solution") is None
