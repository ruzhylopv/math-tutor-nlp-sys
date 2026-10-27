import sympy as sp

from tutor.tools import algebra
from tutor.tools.counterexample import CANDIDATES, Counterexample, counterexample


def test_two_expressions_get_the_values_they_have_at_one_number() -> None:
    found = counterexample("(x - 5)^2", "x^2 - 25", "(x - 5)^2")
    assert found == Counterexample("expression", {"x": 2}, "9", "-21")


def test_the_number_is_substituted_by_sympy_not_guessed() -> None:
    found = counterexample("a + b", "a", "a + b")
    assert found is not None and found.assignment == {"a": 2, "b": 3}
    assert (found.before_value, found.after_value) == ("5", "2")


def test_an_equation_with_one_changed_side_reports_that_side() -> None:
    found = counterexample("3(x + 2) = 15", "3x + 2 = 15", "3(x + 2) = 15")
    assert found == Counterexample("side", {"x": 2}, "12", "8", "left")


def test_an_equation_with_both_sides_changed_reports_the_balance() -> None:
    found = counterexample("2x + 6 = 10", "2x = 16", "2x + 6 = 10")
    assert found is not None and found.kind == "balance"
    assert found.before_value != found.after_value


def test_a_solution_of_the_problem_is_never_used() -> None:
    # 3(x + 2) = 15 has the solution x = 3; the candidate order tries 2 then 3.
    solutions = algebra.solution_set("3(x + 2) = 15")
    assert solutions is not None and solutions.contains(3) == sp.true
    for problem in ("3(x + 2) = 15", "x = 3"):
        found = counterexample("3(x + 2)", "3x + 2", problem)
        assert found is not None
    skipped = counterexample("x^2", "x", "x = 2")
    assert skipped is not None and skipped.assignment != {"x": 2}


def test_a_value_that_breaks_a_fraction_is_skipped() -> None:
    found = counterexample("1/(x - 2)", "1/(x - 3)", "x")
    assert found is not None and found.assignment["x"] not in (2, 3)


def test_a_valid_rewrite_has_no_counterexample() -> None:
    assert counterexample("3(x + 2) = 15", "3x + 6 = 15", "3(x + 2) = 15") is None
    assert counterexample("2x + 6 = 10", "x + 3 = 5", "2x + 6 = 10") is None
    assert counterexample("(x + 1)^2", "x^2 + 2x + 1", "x") is None


def test_unhandled_input_gives_none() -> None:
    assert counterexample("x > 1", "x > 2", "x > 1") is None  # inequality
    assert counterexample("x + 1 = 4", "x + 1", "x + 1 = 4") is None  # equation vs expression
    assert counterexample("x = 1 or x = 2", "x = 3", "x") is None
    assert counterexample("two plus x", "x", "x") is None
    assert counterexample("2 + 3", "5", "2 + 3") is None  # no variable


def test_candidates_avoid_zero_and_one() -> None:
    assert 0 not in CANDIDATES and 1 not in CANDIDATES
