"""Hand-written `localize` cases: one attempt each, with the expected first error step, focus
step and error type worked out by reading the attempt, not by running the node.

`problem` and the claims are plain-text math as `parse_input` would produce. `first` and `focus` are
1-based step numbers or None. A disagreement with the pipeline (`verify` then `localize`) means a
bug or a wrong label here and is investigated, never fixed by editing the label to match. The
developer spot-checks a sample (provenance `spot_check: pending`).

Conventions behind the labels:
- `control` cases may contain a check line that is false (`sqrt(2 + 7) = 2 - 5`). That is how a
  student rejects an extraneous root: `check_holds` False is information, not an error, so the
  expected outcome stays "nothing wrong".
- `mismatch_then_invalid`: a step whose written justification claim is false AND a later step is
  not a valid consequence. The wrong justification counts as the earlier error, so the first error
  step is the step with the false claim and the type is `reasoning_result_mismatch`.
- `lost_solution` is labelled `algebraic_transformation`: the step is not a valid consequence of
  the previous one (a design choice, see evals/datasets/README.md).
- `checker_limit` is not worked out by reading the math: `2x + 1 > 7` is a correct solution that
  the checker cannot judge (no inequalities), so `other` records the limitation of the checker.

The builder splits these cases by problem text (whole groups), see `build_localize.py`.
"""

from typing import Any

Case = dict[str, Any]


def _step(claim: str, justification: str = "", claim_check: str | None = None) -> dict[str, Any]:
    return {"claim": claim, "justification": justification, "justification_claim": claim_check}


def _case(
    kind: str,
    problem: str,
    steps: list[dict[str, Any]],
    first: int | None,
    focus: int | None,
    error_type: str | None,
) -> Case:
    return {
        "kind": kind,
        "problem": problem,
        "steps": steps,
        "expected": {"first_error_step": first, "focus_step": focus, "error_type": error_type},
    }


def _plain(*claims: str) -> list[dict[str, Any]]:
    return [_step(claim) for claim in claims]


ALG = "algebraic_transformation"
OMIT = "omission_extraneous_root"
MISMATCH = "reasoning_result_mismatch"

HANDWRITTEN: list[Case] = [
    _case("not_valid", "3(x + 2) = 15", _plain("3x + 2 = 15", "3x = 13", "x = 13/3"), 1, 1, ALG),
    _case(
        "omission",
        "sqrt(x + 7) = x - 5",
        _plain("x + 7 = x^2 - 10x + 25", "x^2 - 11x + 18 = 0", "x = 2 or x = 9"),
        None,
        1,
        OMIT,
    ),
    _case(
        "mismatch",
        "x^2 - 11x + 18 = 0",
        [
            _step("(x - 9)(x - 2) = 0", "-9 and -2 add to 11", "(-9) + (-2) = 11"),
            _step("x = 9 or x = 2"),
        ],
        1,
        1,
        MISMATCH,
    ),
    _case("unparsable", "x^2 - 5x + 6 = 0", _plain("x equals three plus"), None, 1, "other"),
    _case("incomplete", "3x + 6 = 15", _plain("3x = 9"), None, None, "other"),
    _case(
        "control",
        "3(x + 2) = 15",
        _plain("3x + 6 = 15", "3x = 9", "x = 3"),
        None,
        None,
        None,
    ),
    _case(
        "not_valid",
        "5x - 7 = 2x + 8",
        _plain("3x - 7 = 8", "3x = 1", "x = 1/3"),
        2,
        2,
        ALG,
    ),
    _case(
        "omission",
        "sqrt(2x + 3) = x",
        _plain("2x + 3 = x^2", "x^2 - 2x - 3 = 0", "(x - 3)(x + 1) = 0", "x = 3 or x = -1"),
        None,
        1,
        OMIT,
    ),
    _case(
        "mismatch",
        "3x + 6 = 15",
        [
            _step("3x = 15 - 6", "subtract 6 from both sides, 15 - 6 = 8", "15 - 6 = 8"),
            _step("3x = 9"),
            _step("x = 3"),
        ],
        1,
        1,
        MISMATCH,
    ),
    _case(
        "checker_limit",
        "2x + 1 > 7",
        _plain("2x > 6", "x > 3"),
        None,
        1,
        "other",
    ),
    _case("incomplete", "2(x + 3) = 14", _plain("2x + 6 = 14", "2x = 8"), None, None, "other"),
    _case(
        "control",
        "2x + 3 = 11",
        [_step("2x = 8", "11 - 3 = 8", "11 - 3 = 8"), _step("x = 4")],
        None,
        None,
        None,
    ),
    _case("not_valid", "3x + 6 = 15", _plain("3x = 9", "x = 6"), 2, 2, ALG),
    _case(
        "omission",
        "sqrt(x) = x - 2",
        _plain("x = (x - 2)^2", "x^2 - 5x + 4 = 0", "x = 1 or x = 4"),
        None,
        1,
        OMIT,
    ),
    _case(
        "mismatch",
        "5x - 7 = 2x + 8",
        [
            _step("3x - 7 = 8"),
            _step("3x = 15", "add 7 to both sides, 8 + 7 = 14", "8 + 7 = 14"),
            _step("x = 5"),
        ],
        2,
        2,
        MISMATCH,
    ),
    _case(
        "unparsable",
        "3x + 6 = 15",
        _plain("3x = 9", "x is about three"),
        None,
        2,
        "other",
    ),
    _case(
        "lost_solution",
        "x^2 = 3x",
        _plain("x = 3"),
        1,
        1,
        ALG,
    ),
    _case(
        "control",
        "sqrt(x + 7) = x - 5",
        _plain(
            "x + 7 = x^2 - 10x + 25",
            "x^2 - 11x + 18 = 0",
            "x = 2 or x = 9",
            "sqrt(2 + 7) = 2 - 5",
            "x = 9",
        ),
        None,
        None,
        None,
    ),
    _case("not_valid", "x + 5 = 12", _plain("x = 12 + 5", "x = 17"), 1, 1, ALG),
    _case(
        "omission",
        "sqrt(x + 2) = x",
        _plain("x + 2 = x^2", "x^2 - x - 2 = 0", "(x - 2)(x + 1) = 0", "x = 2 or x = -1"),
        None,
        1,
        OMIT,
    ),
    _case(
        "mismatch_then_invalid",
        "2x + 3 = 11",
        [_step("2x = 8", "11 - 3 = 7", "11 - 3 = 7"), _step("x = 5")],
        1,
        1,
        MISMATCH,
    ),
    _case(
        "lost_solution",
        "x^2 = 3x",
        _plain("x(x - 3) = 0", "x = 3"),
        2,
        2,
        ALG,
    ),
    _case(
        "correct_answer_invalid_step",
        "x + 3 = 5",
        _plain("x = 5 + 3", "x = 2"),
        1,
        1,
        ALG,
    ),
    _case(
        "several_errors",
        "2(x + 1) = 10",
        _plain("2x + 1 = 10", "2x = 8", "x = 4"),
        1,
        1,
        ALG,
    ),
    _case(
        "not_valid",
        "4x - 8 = 2x + 6",
        _plain("2x - 8 = 6", "2x = 14", "x = 28"),
        3,
        3,
        ALG,
    ),
    _case(
        "not_valid",
        "x^2 - 5x + 6 = 0",
        _plain("(x - 1)(x - 6) = 0", "x = 1 or x = 6"),
        1,
        1,
        ALG,
    ),
    _case(
        "not_valid",
        "(x + 3)^2 = 16",
        _plain("x^2 + 9 = 16", "x^2 = 7"),
        1,
        1,
        ALG,
    ),
    _case(
        "control",
        "x^2 = 3x",
        _plain("x(x - 3) = 0", "x = 0 or x = 3"),
        None,
        None,
        None,
    ),
    _case(
        "not_valid",
        "sqrt(x + 7) = x - 5",
        _plain("x + 7 = x^2 - 25", "x^2 - x - 32 = 0", "x = (1 +- sqrt(129))/2"),
        1,
        1,
        ALG,
    ),
    # Added after the review: more mismatch cases and a second case of each singleton kind.
    # 4x - 3 = 13: 4x = 16 is right, but the justification says 13 + 3 = 15 (false).
    _case(
        "mismatch",
        "4x - 3 = 13",
        [
            _step("4x = 16", "add 3 to both sides, 13 + 3 = 15", "13 + 3 = 15"),
            _step("x = 4"),
        ],
        1,
        1,
        MISMATCH,
    ),
    # sqrt(3x + 4) = x: squaring is an `implies` step, and the false claim sits on it (3*4 + 4 is
    # 16). The extraneous root -1 is rejected by a failing check line, so nothing else is wrong
    # and the final answer is right.
    _case(
        "mismatch",
        "sqrt(3x + 4) = x",
        [
            _step(
                "3x + 4 = x^2",
                "square both sides, at x = 4 the left side is 3*4 + 4 = 15",
                "3*4 + 4 = 15",
            ),
            _step("x^2 - 3x - 4 = 0"),
            _step("x = 4 or x = -1"),
            _step("sqrt(3*(-1) + 4) = -1"),
            _step("x = 4"),
        ],
        1,
        1,
        MISMATCH,
    ),
    # 2(x - 4) = 6: the first step is fine, the false claim is on the second.
    _case(
        "mismatch",
        "2(x - 4) = 6",
        [
            _step("2x - 8 = 6"),
            _step("2x = 14", "add 8 to both sides, 6 + 8 = 13", "6 + 8 = 13"),
            _step("x = 7"),
        ],
        2,
        2,
        MISMATCH,
    ),
    # 5x + 2 = 17: 5x = 15 is right but the claim 17 - 2 = 14 is false; then x = 4 is wrong.
    _case(
        "mismatch_then_invalid",
        "5x + 2 = 17",
        [_step("5x = 15", "17 - 2 = 14", "17 - 2 = 14"), _step("x = 4")],
        1,
        1,
        MISMATCH,
    ),
    # x - 4 = 9: "x = 9 - 4" is wrong (it is x = 5), "x = 13" is the right answer.
    _case(
        "correct_answer_invalid_step",
        "x - 4 = 9",
        _plain("x = 9 - 4", "x = 13"),
        1,
        1,
        ALG,
    ),
    # 3(x - 2) = 12: 3x - 2 = 12 forgets to multiply the 2; 3x = 10 is then wrong again.
    _case(
        "several_errors",
        "3(x - 2) = 12",
        _plain("3x - 2 = 12", "3x = 10", "x = 10/3"),
        1,
        1,
        ALG,
    ),
]
