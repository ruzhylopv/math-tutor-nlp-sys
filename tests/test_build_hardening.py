"""Regression tests for the miner and converter problems found by the M2 review."""

import pytest

from evals.builders.latex import latex_to_text
from evals.builders.mine_math import (
    _variables,
    extract_chains,
    pairs_from_chains,
)


# --- converter ---------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "latex",
    [
        r"1+2+\cdots+10",  # \cdots is not \cdot
        r"x \rightarrow 3",  # \rightarrow is not \right
        r"x \leftarrow 3",
        r"1\,000",  # would be read as 1 * 000
        r"2\,500",
        "1,000",
        "a_1",
        "x_{1}",
        r"\left| x \right|",
        "5 > 3",
        "5 < 3",
        "3!",
        r"\frac12",
        r"3\frac{1}{2}",  # a mixed number or a product: ambiguous
        r"37 \frac{1}{2}",
    ],
)
def test_input_outside_the_supported_set_is_dropped(latex: str) -> None:
    assert latex_to_text(latex) is None


@pytest.mark.parametrize(
    ("latex", "plain"),
    [
        (r"2 \times 3", "2 * 3"),
        (r"6 \div 3", "6 / 3"),
        (r"3\frac{x}{2}", "3((x)/(2))"),  # a variable numerator: a product, not a mixed number
        (r"\sqrt{\frac{1}{2}}", "sqrt(((1)/(2)))"),
        (r"\left(x+1\right)", "(x+1)"),
    ],
)
def test_supported_input_still_converts(latex: str, plain: str) -> None:
    assert latex_to_text(latex) == plain


# --- miner: environments and line breaks -------------------------------------------------------
@pytest.mark.parametrize("environment", ["align", "align*", "aligned"])
def test_all_align_environments_are_read(environment: str) -> None:
    solution = (
        rf"\begin{{{environment}}}(x+1)^2 &= x^2+2x+1 \\ &= x^2 + 2x + 1 + 0\end{{{environment}}}"
    )
    (chain,) = extract_chains(solution)
    assert chain.items == ("(x+1)^2", "x^2+2x+1", "x^2 + 2x + 1 + 0")


def test_a_line_break_with_a_length_is_a_line_break() -> None:
    solution = r"\begin{align*}(x+1)^2 &= x^2+2x+1 \\[2mm] &= (x+1)(x+1)\end{align*}"
    (chain,) = extract_chains(solution)
    assert chain.items == ("(x+1)^2", "x^2+2x+1", "(x+1)(x+1)")


def test_several_columns_on_one_line_do_not_become_one_chain() -> None:
    solution = r"\begin{align*}2+2 &= 4, & 3+3 &= 6 \\ &= 5\end{align*}"
    assert pairs_from_chains(extract_chains(solution), "simplify") == []


# --- miner: display math -----------------------------------------------------------------------
def test_display_math_does_not_break_the_later_inline_chains() -> None:
    chains = extract_chains(r"$$2+3 = 5 = 10/2$$ and then $4+4 = 8 = 2\cdot 4$ done")
    assert [chain.items for chain in chains] == [
        ("2+3", "5", "10/2"),
        ("4+4", "8", "2 * 4"),
    ]


# --- miner: what counts as an identity ---------------------------------------------------------
def test_unrelated_true_statements_are_not_a_derivation() -> None:
    solution = r"\begin{align*}2^2 &= 4 \\ 3^2 &= 9 \\ 4^2 &= 16\end{align*}"
    (chain,) = extract_chains(solution)
    assert chain.kind == "equation"
    assert pairs_from_chains([chain], "other") == []


def test_equation_pairs_keep_the_same_variables() -> None:
    solution = r"\begin{align*}3x+6 &= 15 \\ 3x &= 9 \\ y &= 2\end{align*}"
    pairs = pairs_from_chains(extract_chains(solution), "solve")
    assert [(pair.prev, pair.curr) for pair in pairs] == [("3x+6 = 15", "3x = 9")]


def test_known_residual_two_equations_with_the_same_solution_are_paired() -> None:
    # documented in pairs_from_chains: rare, and the SymPy filter cannot tell them apart
    solution = r"\begin{align*}x+3 &= 5 \\ x+7 &= 9\end{align*}"
    assert len(pairs_from_chains(extract_chains(solution), "solve")) == 1


def test_variable_chains_need_a_simplify_style_problem() -> None:
    chains = extract_chains(r"$3x+2 = 2x+5 = 7$")
    assert pairs_from_chains(chains, "other") == []
    assert pairs_from_chains(chains, "solve") == []


def test_numeric_chains_are_kept_for_any_task() -> None:
    chains = extract_chains(r"$2+3 = 5 = 10/2$")
    assert len(pairs_from_chains(chains, "other")) == 2


def test_equation_chains_skip_complex_numbers_and_named_quantities() -> None:
    assert (
        pairs_from_chains(
            extract_chains(r"\begin{align*}AB &= 3 \\ AB^2 &= 9\end{align*}"), "solve"
        )
        == []
    )


def test_variables_ignore_function_words_only_as_whole_words() -> None:
    assert _variables("sqrt(x) + abs(y)") == frozenset({"x", "y"})
    assert _variables("2ab") == frozenset({"a", "b"})
