import pytest

from evals.builders.mine_math import (
    extract_chains,
    has_function_notation,
    pairs_from_chains,
    task_type,
)
from tutor.tools.algebra import step_relation

# A real MATH solution (Algebra, level 3).
SIMPLIFY_SOLUTION = r"""We expand each product separately: \begin{align*}
(2x-5)(x+7) &= 2x(x) + 2x(7) -5(x) -5(7)\\
&=2x^2 +14x - 5x -35\\
&= 2x^2 +9x - 35
\end{align*}and \begin{align*}
(x+5)(2x-1) &=x(2x) + x(-1) +5(2x) + 5(-1)\\
&=2x^2 -x + 10x -5\\
&=2x^2 +9x - 5.
\end{align*}So, we have \begin{align*}&\ \ \ \ (2x-5)(x+7) - (x+5)(2x-1) \\
&= 2x^2+9x -35 - (2x^2 +9x -5) = \boxed{-30}.\end{align*}"""


def test_each_align_block_is_a_chain() -> None:
    chains = extract_chains(SIMPLIFY_SOLUTION)
    assert [chain.kind for chain in chains] == ["expression"] * 3
    assert chains[0].items == (
        "(2x-5)(x+7)",
        "2x(x) + 2x(7) -5(x) -5(7)",
        "2x^2 +14x - 5x -35",
        "2x^2 +9x - 35",
    )


def test_the_mined_pairs_are_the_author_labelled_equivalents() -> None:
    pairs = pairs_from_chains(extract_chains(SIMPLIFY_SOLUTION), task_type("Simplify $x$."))
    # 3 + 3 + 1 pairs; the last step to -30 changes the variables, so it is not an identity pair
    assert len(pairs) == 7
    assert all(step_relation(pair.prev, pair.curr) == "equivalent" for pair in pairs)


def test_equation_lines_become_an_equation_chain() -> None:
    solution = r"We solve: \begin{align*} 3x+6 &= 15\\ 3x &= 9\\ x &= 3 \end{align*}"
    (chain,) = extract_chains(solution)
    assert chain.kind == "equation"
    assert chain.items == ("3x+6 = 15", "3x = 9", "x = 3")
    pairs = pairs_from_chains([chain], "solve")
    assert [step_relation(p.prev, p.curr) for p in pairs] == ["equivalent", "equivalent"]


def test_inline_equality_chains_are_mined() -> None:
    (chain,) = extract_chains(r"So $2(x+3) = 2x+6 = 2x + 3 \cdot 2$ as needed.")
    assert chain.origin == "inline" and len(chain.items) == 3


def test_a_single_inline_equation_is_not_a_chain() -> None:
    assert extract_chains(r"Then $x = 3$.") == []


def test_unsupported_pieces_cut_the_chain() -> None:
    chains = extract_chains(r"$a = b = \pi r = c = d$")
    assert [chain.items for chain in chains] == [("a", "b"), ("c", "d")]


def test_a_segment_with_text_is_skipped_whole() -> None:
    assert extract_chains(r"$a = b = \text{so} = c = d$") == []


def test_conditions_and_substitutions_are_not_identity_pairs() -> None:
    # the first step substitutes numbers for x and y, so only the numeric tail is a pair
    chains = extract_chains(r"$x^2+y^2+2xy = 90+2\cdot 27 = 144$")
    pairs = pairs_from_chains(chains, "simplify")
    assert [(pair.prev, pair.curr) for pair in pairs] == [("90+2 * 27", "144")]


def test_expression_chains_with_variables_need_a_simplify_style_problem() -> None:
    chains = extract_chains(r"$x^2-4 = (x-2)(x+2) = x^2-4$")
    assert pairs_from_chains(chains, "solve") == []
    assert len(pairs_from_chains(chains, "factor")) == 2


def test_complex_numbers_and_uppercase_names_are_skipped() -> None:
    assert pairs_from_chains(extract_chains(r"$3(2i) = 6i = 6i$"), "simplify") == []
    assert pairs_from_chains(extract_chains(r"$AB^2 = 25 = 5^2$"), "simplify") == []


@pytest.mark.parametrize(
    ("problem", "expected"),
    [
        ("Simplify $(x+1)^2$.", "simplify"),
        ("Expand $(x+1)(x+2)$.", "expand"),
        ("Factor $x^2-1$.", "factor"),
        ("Solve $x+1=3$.", "solve"),
        ("What is the value of $x+1$ when $x=2$?", "simplify"),
    ],
)
def test_task_type(problem: str, expected: str) -> None:
    assert task_type(problem) == expected


@pytest.mark.parametrize(
    "problem",
    [
        "If $f(x)=x+1$, find $f(2)$.",
        "Define $a*b = a+b$. Find $2*3$.",
        "The operation $\\star$ is defined",
    ],
)
def test_function_notation_and_custom_operations_are_flagged(problem: str) -> None:
    assert has_function_notation(problem)


def test_an_implicit_product_is_not_function_notation() -> None:
    assert not has_function_notation("Simplify $3(x+2) + x(x+1)$.")
