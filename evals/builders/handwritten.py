"""Hand-written verify cases: implies, narrows, unparsable and typical not_valid slips.

Written by the agent with the relation worked out by hand (not by running SymPy), then checked
against the checker in tests/test_build_handwritten.py. A disagreement means a checker bug or a
wrong label here, and is investigated. The developer spot-checks a sample (M2 plan).
"""

from typing import TypedDict


class Case(TypedDict):
    task_type: str
    problem: str
    prev: str
    curr: str
    relation: str
    original: str | None


def _case(
    task: str, problem: str, prev: str, curr: str, relation: str, original: str | None = None
) -> Case:
    return Case(
        task_type=task,
        problem=problem,
        prev=prev,
        curr=curr,
        relation=relation,
        original=original,
    )


_A = "Solve $3(x+2) = 15$."
_B = "Solve $\\sqrt{x+7} = x-5$."
_C = "Solve $5x - 7 = 2x + 8$."
_Q = "Solve $x^2 - 5x + 6 = 0$."
_RAD = "Solve $\\sqrt{2x+3} = x$."
_RAT = "Solve $\\frac{(x-2)(x+1)}{x-2} = 0$."
_BAD = "Solve $x = 1$."

HANDWRITTEN: list[Case] = [
    # --- equivalent ---------------------------------------------------------------------
    _case("solve", _A, "3(x+2) = 15", "3x + 6 = 15", "equivalent"),
    _case("solve", _A, "3x + 6 = 15", "3x = 9", "equivalent"),
    _case("solve", _A, "3x = 9", "x = 3", "equivalent"),
    _case("solve", _C, "5x - 7 = 2x + 8", "3x - 7 = 8", "equivalent"),
    _case("solve", _C, "3x - 7 = 8", "3x = 15", "equivalent"),
    _case("solve", _Q, "x^2 - 5x + 6 = 0", "(x - 2)(x - 3) = 0", "equivalent"),
    _case("solve", _Q, "(x - 2)(x - 3) = 0", "x = 2 or x = 3", "equivalent"),
    _case("solve", _B, "x + 7 = x^2 - 10x + 25", "x^2 - 11x + 18 = 0", "equivalent"),
    _case("solve", _B, "x^2 - 11x + 18 = 0", "(x - 9)(x - 2) = 0", "equivalent"),
    _case("solve", "Solve $\\frac1x + \\frac12 = 1$.", "1/x + 1/2 = 1", "2 + x = 2x", "equivalent"),
    _case("expand", "Expand $(x+3)^2$.", "(x+3)^2", "x^2 + 6x + 9", "equivalent"),
    _case("factor", "Factor $x^2 - 9$.", "x^2 - 9", "(x-3)(x+3)", "equivalent"),
    _case(
        "simplify",
        "Simplify $2(x+1) + 3(x-2)$.",
        "2(x+1) + 3(x-2)",
        "2x + 2 + 3x - 6",
        "equivalent",
    ),
    _case("simplify", "Simplify $2(x+1) + 3(x-2)$.", "2x + 2 + 3x - 6", "5x - 4", "equivalent"),
    _case("simplify", "Simplify $\\sqrt{50}$.", "sqrt(50)", "5 sqrt(2)", "equivalent"),
    _case("simplify", "Simplify $\\frac12 + \\frac13$.", "1/2 + 1/3", "5/6", "equivalent"),
    _case("solve", "Solve $|x-1| = 2$.", "abs(x - 1) = 2", "x - 1 = 2 or x - 1 = -2", "equivalent"),
    _case("solve", "Solve $\\sqrt{x} = 3$.", "sqrt(x) = 3", "x = 9", "equivalent"),
    _case("solve", _B, "x = 9", "sqrt(9 + 7) = 9 - 5", "equivalent"),  # a true check
    # --- implies (a non-reversible step adds solutions) -----------------------------------
    _case("solve", _B, "sqrt(x+7) = x-5", "x + 7 = (x-5)^2", "implies"),
    _case("solve", "Solve $x = 3$.", "x = 3", "x^2 = 9", "implies"),
    _case("solve", "Solve $x - 1 = 0$.", "x - 1 = 0", "x(x - 1) = 0", "implies"),
    _case("solve", _RAD, "sqrt(2x+3) = x", "2x + 3 = x^2", "implies"),
    _case("solve", _RAT, "(x-2)(x+1)/(x-2) = 0", "(x-2)(x+1) = 0", "implies"),
    _case("solve", "Solve $x = -3$.", "x = -3", "x^2 = 9", "implies"),
    _case("solve", "Solve $\\sqrt{x} = x - 2$.", "sqrt(x) = x - 2", "x = (x - 2)^2", "implies"),
    _case("solve", "Solve $x - 2 = 0$.", "x - 2 = 0", "(x - 2)(x + 5) = 0", "implies"),
    _case("solve", "Solve $2x = 6$.", "2x = 6", "2x(x - 1) = 6(x - 1)", "implies"),
    _case("solve", "Solve $\\sqrt{x+2} = x$.", "sqrt(x + 2) = x", "x + 2 = x^2", "implies"),
    _case("solve", "Solve $2x + 1 = 5$.", "2x + 1 = 5", "(2x + 1)(x - 4) = 5(x - 4)", "implies"),
    # Relabelled from `implies` on 2026-10-26: this equation has no solutions, and "solving" a
    # contradiction is not valid (review finding; the checker's empty-set rule).
    _case(
        "solve",
        "Solve $\\frac{x}{x-3} = \\frac{3}{x-3}$.",
        "x/(x-3) = 3/(x-3)",
        "x = 3",
        "not_valid",
    ),
    # --- narrows (rejecting an extraneous root of the original problem) ---------------------
    _case("solve", _B, "x = 9 or x = 2", "x = 9", "narrows", "sqrt(x+7) = x-5"),
    _case("solve", _RAD, "x = 3 or x = -1", "x = 3", "narrows", "sqrt(2x+3) = x"),
    _case("solve", _RAT, "x = 2 or x = -1", "x = -1", "narrows", "(x-2)(x+1)/(x-2) = 0"),
    _case(
        "solve", "Solve $\\sqrt{x+2} = x$.", "x = 2 or x = -1", "x = 2", "narrows", "sqrt(x+2) = x"
    ),
    _case(
        "solve",
        "Solve $\\sqrt{x} = x - 2$.",
        "x = 1 or x = 4",
        "x = 4",
        "narrows",
        "sqrt(x) = x - 2",
    ),
    _case(
        "solve",
        "Solve $\\frac{(x-2)(x+5)}{x-2} = 0$.",
        "x = 2 or x = -5",
        "x = -5",
        "narrows",
        "(x-2)(x+5)/(x-2) = 0",
    ),
    _case("solve", _RAD, "x^2 - 2x - 3 = 0", "x = 3", "narrows", "sqrt(2x+3) = x"),
    _case("solve", _B, "(x - 9)(x - 2) = 0", "x = 9", "narrows", "sqrt(x+7) = x-5"),
    # --- not_valid: equations ---------------------------------------------------------------
    _case("solve", _A, "3(x+2) = 15", "3x + 2 = 15", "not_valid"),  # only the first term
    _case("solve", _A, "3x + 6 = 15", "3x = 21", "not_valid"),
    _case("solve", _A, "3x = 9", "x = 6", "not_valid"),
    _case("solve", _C, "5x - 7 = 2x + 8", "7x - 7 = 8", "not_valid"),
    _case("solve", _Q, "x^2 - 5x + 6 = 0", "(x - 2)(x + 3) = 0", "not_valid"),
    _case("solve", _B, "sqrt(x+7) = x-5", "x + 7 = x^2 - 25", "not_valid"),  # (a - b)^2 = a^2 - b^2
    _case("solve", _B, "x + 7 = x^2 - 10x + 25", "x^2 - 9x + 18 = 0", "not_valid"),
    _case("solve", "Solve $x^2 - x = 0$.", "x^2 - x = 0", "x - 1 = 0", "not_valid", "x^2 - x = 0"),
    _case("solve", _B, "x = 9 or x = 2", "x = 2", "not_valid", "sqrt(x+7) = x-5"),
    _case("solve", "Solve $|x-1| = 2$.", "abs(x - 1) = 2", "x - 1 = 2", "not_valid"),
    # --- not_valid: expressions ---------------------------------------------------------------
    _case("expand", "Expand $(x+3)^2$.", "(x+3)^2", "x^2 + 9", "not_valid"),
    _case("factor", "Factor $x^2 - 9$.", "x^2 - 9", "(x-3)^2", "not_valid"),
    _case("simplify", "Simplify $2(x+1) + 3(x-2)$.", "2x + 2 + 3x - 6", "5x + 8", "not_valid"),
    _case("simplify", "Simplify $\\frac12 + \\frac13$.", "1/2 + 1/3", "2/5", "not_valid"),
    _case("simplify", "Simplify $\\sqrt{50}$.", "sqrt(50)", "25 sqrt(2)", "not_valid"),
    _case("simplify", "Evaluate $3 + 4 \\cdot 2$.", "3 + 4 * 2", "14", "not_valid"),
    _case("simplify", "Simplify $-(x-4)$.", "-(x - 4)", "-x - 4", "not_valid"),
    _case("simplify", "Simplify $2x^2 \\cdot 3x$.", "2x^2 * 3x", "5x^3", "not_valid"),
    _case("simplify", "Simplify $(2x)^2$.", "(2x)^2", "2x^2", "not_valid"),
    # --- not_valid: a false check -------------------------------------------------------------
    _case("solve", _B, "x = 2", "sqrt(2 + 7) = 2 - 5", "not_valid"),
    # --- unparsable ----------------------------------------------------------------------------
    _case("solve", _BAD, "x = 1", "x + * 3", "unparsable"),
    _case("solve", _BAD, "x = 1", "three x plus two", "unparsable"),
    _case("solve", _BAD, "x = 1", "3x + = 5", "unparsable"),
    _case("solve", _BAD, "x = 1", "x = = 2", "unparsable"),
    _case("solve", _BAD, "x = 1", "sin(x) = 0", "unparsable"),
    _case("solve", _BAD, "x = 1", "x = 9 or", "unparsable"),
    _case("solve", _BAD, "x = 1", "x ≠ 3", "unparsable"),
    _case("solve", _BAD, "x = 1", "x + y = 2", "unparsable"),
    _case("solve", _BAD, "x ++", "x = 1", "unparsable"),
    _case("solve", _BAD, "x = 1", "x =", "unparsable"),
    _case("solve", _BAD, "x = 1", "2x + (3", "unparsable"),
    _case("solve", _BAD, "x = 1", "5 / 0", "unparsable"),
    _case("solve", _BAD, "x = 1", "log(x) = 1", "unparsable"),
    _case("solve", _BAD, "x = 1", "x^2 > 4", "unparsable"),
    _case("solve", _BAD, "x = 1", "x \u2248 3.2", "unparsable"),
    _case("solve", _BAD, "x = 1", "x = 1.2.3", "unparsable"),
    _case("solve", _BAD, "x = 1", "__import__('os')", "unparsable"),
]
