import random

import pytest

from evals.builders.corrupt import (
    RULES,
    apply_rule,
    corrupt_pair,
    equation_loses_a_solution,
    expression_differs,
    split_terms,
)
from evals.builders.mine_math import StepPair, extract_chains, pairs_from_chains
from tutor.tools.algebra import step_relation


def test_split_terms_keeps_signs_and_brackets() -> None:
    assert split_terms("2x^2 +9x - 35") == ["2x^2 ", "+9x ", "- 35"]
    assert split_terms("(a+b) - (c-d)") == ["(a+b) ", "- (c-d)"]
    assert split_terms("-3x + 2") == ["-3x ", "+ 2"]
    assert split_terms("2^(-1) x") == ["2^(-1) x"]


def test_drop_term_removes_one_term() -> None:
    assert apply_rule("drop_term", "2x^2 + 9x - 35", random.Random(0)) in {
        "9x - 35",
        "2x^2 - 35",
        "2x^2 + 9x",
    }
    assert apply_rule("drop_term", "x", random.Random(0)) is None


def test_flip_sign_changes_one_sign() -> None:
    result = apply_rule("flip_sign", "x + 5", random.Random(1))
    assert result is not None and result.replace(" ", "") in {"-x+5", "x-5"}


def test_bump_number_and_change_exponent() -> None:
    assert apply_rule("bump_number", "3x + 6", random.Random(2)) in {"4x + 6", "3x + 7"}
    assert apply_rule("change_exponent", "x^2 + 1", random.Random(0)) == "x^3 + 1"
    assert apply_rule("change_exponent", "x + 1", random.Random(0)) is None


def test_exponents_are_not_bumped_as_numbers() -> None:
    assert apply_rule("bump_number", "x^2", random.Random(0)) is None


def test_expression_witness() -> None:
    assert expression_differs("2x + 6", "2x + 7")
    assert not expression_differs("2(x+3)", "2x + 6")
    assert not expression_differs("x + y", "y + x")


def test_equation_witness_needs_a_point_where_prev_holds_and_curr_fails() -> None:
    assert equation_loses_a_solution("3x + 6 = 15", "3x + 2 = 15")
    assert not equation_loses_a_solution("3x + 6 = 15", "3x = 9")  # equivalent: no witness
    assert not equation_loses_a_solution("x = 3", "x^2 = 9")  # implies: no witness


@pytest.mark.parametrize("seed", range(25))
def test_a_kept_corruption_is_never_equivalent(seed: int) -> None:
    solution = r"\begin{align*}(2x-5)(x+7) &= 2x^2+14x-5x-35\\ &= 2x^2+9x-35\end{align*}"
    pairs = pairs_from_chains(extract_chains(solution), "simplify")
    corruption = corrupt_pair(pairs[0], random.Random(seed))
    assert corruption is not None and corruption.rule in RULES
    assert step_relation(pairs[0].prev, corruption.text) == "not_valid"


@pytest.mark.parametrize("seed", range(10))
def test_equation_corruptions_are_not_valid(seed: int) -> None:
    pair = StepPair("3x + 6 = 15", "3x = 9", "equation", "align")
    corruption = corrupt_pair(pair, random.Random(seed))
    assert corruption is not None  # every seed finds a witnessed error for this simple equation
    assert step_relation(pair.prev, corruption.text) == "not_valid"


def test_corruption_is_reproducible() -> None:
    pair = StepPair("(x+1)(x+2)", "x^2 + 3x + 2", "expression", "inline")
    assert corrupt_pair(pair, random.Random(7)) == corrupt_pair(pair, random.Random(7))
