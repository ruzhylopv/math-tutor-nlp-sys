"""Hand-written `localize` cases: one attempt each, with the expected first error step, focus
step and error type worked out by reading the attempt, not by running the node.

`problem` and the claims are plain-text math as `parse_input` would produce. `first` and `focus` are
1-based step numbers or None. A disagreement with the pipeline (`verify` then `localize`) means a
bug or a wrong label here and is investigated, never fixed by editing the label to match. The
developer spot-checks a sample (provenance `spot_check: pending`).
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

# Within each kind the builder alternates the cases between dev and test, starting with dev.
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
        "unparsable",
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
]
