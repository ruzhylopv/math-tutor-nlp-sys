"""Hand-written `retrieve` queries: the student's attempt at the moment of the error, and the
catalogue entry it shows, worked out by reading.

They cover the catalogue entries that have no mechanical rule (`misconception_rules.py`), plus
some paraphrases of mechanical ones in another shape. Each is a problem, the student's steps
(a claim, and optionally the words the student wrote with it), the step to focus on, the error
type that `localize` would give, and the id of the misconception in
`src/tutor/data/misconceptions.json`. The wrong lines use other numbers and wording than the
catalogue's examples. The developer spot-checks a sample (provenance `spot_check: pending`).

Known limit: the entries about inequalities, a bare plus-or-minus, and the reasons for
rejecting roots cannot be reached in the full pipeline, because `verify` cannot parse those
steps (`localize` gives `other`, and `retrieve` then returns nothing). Here `retrieve` is
evaluated on its own."""

from typing import Any

Step = str | tuple[str, str]  # a claim, or (claim, what the student wrote with it)
ALG = "algebraic_transformation"
OMIT = "omission_extraneous_root"
MISMATCH = "reasoning_result_mismatch"


def _query(
    expected: str, problem: str, steps: list[Step], focus: int, error_type: str = ALG
) -> dict[str, Any]:
    return {
        "expected": expected,
        "problem": problem,
        "steps": [
            {"claim": s, "justification": ""} if isinstance(s, str)
            else {"claim": s[0], "justification": s[1]}
            for s in steps
        ],
        "focus_step": focus,
        "error_type": error_type,
    }  # fmt: skip


HANDWRITTEN: list[dict[str, Any]] = [
    # --- entries without a mechanical rule
    _query("M024", "5n when n = 3", ["8"], 1),
    _query("M024", "2a + 1 when a = 6", ["2 + 6 + 1 = 9"], 1),
    _query("M035", "reciprocal of 5/7", ["-5/7"], 1),
    _query("M035", "reciprocal of 2/9", ["-2/9"], 1),
    _query("M058", "4n + 2 = 4n + 2", ["0 = 0", "no solution"], 2),
    _query("M058", "3(y + 1) = 3y + 3", ["3y + 3 = 3y + 3", "0 = 0", "no solution"], 3),
    _query("M060", "write 'a number decreased by 9' as an expression", ["9 - n"], 1),
    _query("M061", "write 'three times a number plus 5' as an expression", ["3(n + 5)"], 1),
    _query("M062", "7y when y = 2", ["72"], 1),
    _query(
        "M064",
        "sqrt(2x + 3) = x",
        [("2x + 3 = x^2", "square both sides"), "x^2 - 2x - 3 = 0", "x = 3 or x = -1"],
        1,
        OMIT,
    ),  # fmt: skip
    _query(
        "M064",
        "sqrt(n + 12) = n",
        [("n + 12 = n^2", "square both sides"), "n^2 - n - 12 = 0", "n = 4 or n = -3"],
        1,
        OMIT,
    ),  # fmt: skip
    _query(
        "M067",
        "sqrt(x + 2) = x",
        ["x + 2 = x^2", "x = 2 or x = -1", ("x = 2", "x = -1 is rejected because it is negative")],
        3,
        MISMATCH,
    ),  # fmt: skip
    _query(
        "M068",
        "sqrt(3t + 4) = t",
        [
            "3t + 4 = t^2",
            "t = 4 or t = -1",
            ("no solution", "t = -1 does not work in the original"),
        ],
        3,
        OMIT,
    ),  # fmt: skip
    _query("M077", "x^2 + 4x + 1 = 0", ["x = -4 +- sqrt(12)/2"], 1),
    _query("M077", "n^2 + 8n + 3 = 0", ["n = -8 +- sqrt(52)/2"], 1),
    _query("M093", "sqrt(25)", ["+-5"], 1),
    _query("M118", "(x^2 - 9)/(x - 3) = 0", ["x = 3 or x = -3"], 1, OMIT),
    # --- inequalities (not parsable by verify, see the module docstring)
    _query("M105", "-3x > 12", ["x > -4"], 1),
    _query("M105", "-5n <= 20", ["n <= -4"], 1),
    _query("M106", "x + 4 > 9", ["x < 5"], 1),
    _query("M107", "3x > 12", ["x = 4"], 1),
    _query("M108", "|3x - 1| < 7", ["3x - 1 < 7"], 1),
    _query("M109", "x^2 > 16", ["x > 4"], 1),
    _query("M110", "x^2 < 25", ["x < 5 or x > -5"], 1),
    _query("M111", "2/x > 3", ["2 > 3x"], 1),
    _query("M112", "1 < x < 6", ["x > 1 or x < 6"], 1),
    # --- paraphrases of mechanical entries, in another shape or at a later step
    _query("M010", "3(n + 4) = 30", ["3n + 4 = 30", "3n = 26", "n = 26/3"], 1),
    _query("M003", "2y + 7 = 19", [("2y = 19 + 7", "move the 7 over"), "2y = 26", "y = 13"], 1),
    _query("M054", "4(n + 3) = 36", ["4n + 12 = 36", "4n = 24", "n = 24"], 3),
    _query("M037", "(t + 6)^2 = 25", ["t^2 + 36 = 25"], 1),
    _query("M083", "t^2 - 7t + 12 = 0", ["(t + 3)(t + 4) = 0"], 1),
    _query("M084", "x^2 - 49 = 0", ["(x - 7)^2 = 0"], 1),
    _query("M014", "5 - 3(y + 2)", ["5 - 3y + 6"], 1),
    _query("M027", "2/3 + 1/4", ["3/7"], 1),
    _query("M040", "(n^3)^4", ["n^7"], 1),
    _query("M090", "sqrt(36 + 64)", ["6 + 8"], 1),
    _query("M053", "3x - 8 = 2x + 5", ["x - 8 = 2x + 5"], 1),
    _query("M099", "abs(y + 4) = 9", ["y + 4 = 9"], 1),
    _query("M115", "(2x + 6)/2", ["x + 6"], 1),
    _query("M073", "x^2 = 16", ["x = 4"], 1),
    _query("M022", "t^2 + t", ["t^3"], 1),
    _query("M071", "(x - 1)(x - 4) = 10", ["x - 1 = 10 or x - 4 = 10"], 1),
]
