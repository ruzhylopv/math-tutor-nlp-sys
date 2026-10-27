"""Hand-written student messages for the `parse_input` dataset, with the expected parse worked out
by reading each message, not by running the node.

`problem` is the expected new problem (None when the message states none) and `steps` the expected
claims, in the plain-text math of the node's prompt. Wrong steps are kept wrong on purpose: the
parser transcribes, it does not correct. None of these is used in the prompt.
"""

from typing import Any

Case = dict[str, Any]


def _case(
    message: str,
    problem: str | None,
    steps: list[str],
    *,
    stored: str | None = None,
    features: tuple[str, ...] = (),
) -> Case:
    return {
        "message": message,
        "stored_problem": stored,
        "problem": problem,
        "steps": steps,
        "features": list(features),
    }


# Ordered so that kinds are interleaved: the builder sends every third case to the test split.
HANDWRITTEN: list[Case] = [
    _case("Solve 3x + 7 = 22\n3x = 15\nx = 5", "3x + 7 = 22", ["3x = 15", "x = 5"]),
    _case(
        "why do we subtract first?",
        None,
        [],
        stored="2x + 3 = 11",
        features=("question_only",),
    ),
    _case(
        "i have to solve x/3 + 2 = 6. first i take away 2 so x/3 = 4 "
        "and then multiply by 3 so x = 12",
        "x/3 + 2 = 6",
        ["x/3 = 4", "x = 12"],
        features=("one_line", "connectors"),
    ),
    _case(
        "problem: 4(x - 2) = 20\n1. 4x - 8 = 20\n2. 4x = 28\n3. x = 7",
        "4(x - 2) = 20",
        ["4x - 8 = 20", "4x = 28", "x = 7"],
        features=("numbered",),
    ),
    _case(
        "Solve 5x - 4 = 11. 5x = 7, x = 7/5",
        "5x - 4 = 11",
        ["5x = 7", "x = 7/5"],
        features=("wrong_step", "one_line"),
    ),
    _case(
        "(x-2)(x-3)=0\nx = 2 or x = 3",
        None,
        ["(x-2)(x-3) = 0", "x = 2 or x = 3"],
        stored="x^2 - 5x + 6 = 0",
        features=("steps_only",),
    ),
    _case(
        "Simplify (x+3)² − 9\nx² + 6x + 9 − 9\nx² + 6x",
        "(x+3)^2 - 9",
        ["x^2 + 6x + 9 - 9", "x^2 + 6x"],
        features=("unicode",),
    ),
    _case(
        "is the answer x = 4?",
        None,
        [],
        stored="2x + 3 = 11",
        features=("answer_only",),
    ),
    _case(
        "Problem: $2x^2 = 50$. $x^2 = 25$ so $x = \\pm 5$",
        "2x^2 = 50",
        ["x^2 = 25", "x = +-5"],
        features=("latex",),
    ),
    _case(
        "can you help me solve 7 - 2x = 1",
        "7 - 2x = 1",
        [],
        features=("problem_only",),
    ),
    _case(
        "solve two x plus one equals eleven. two x equals ten. x equals five",
        "2x + 1 = 11",
        ["2x = 10", "x = 5"],
        features=("spoken",),
    ),
    _case(
        "ok next one: x + 5 = 12, x = 7",
        "x + 5 = 12",
        ["x = 7"],
        stored="3x = 9",
        features=("new_problem",),
    ),
    _case(
        "helo! i triedd this: 2x+6=14 , 2x = 8 , x = 4. is it corect??",
        "2x+6=14",
        ["2x = 8", "x = 4"],
        features=("typos", "chatty", "one_line"),
    ),
    _case(
        "Expand (x+2)(x-5)\nx^2 - 5x + 2x - 10\nx^2 - 3x - 10",
        "(x+2)(x-5)",
        ["x^2 - 5x + 2x - 10", "x^2 - 3x - 10"],
    ),
    _case(
        "9 - 2(x+1) = 3: 9 - 2x - 2 = 3 (distributed), 7 - 2x = 3 (9-2=7), -2x = -4, x = 2",
        "9 - 2(x+1) = 3",
        ["9 - 2x - 2 = 3", "7 - 2x = 3", "-2x = -4", "x = 2"],
        features=("one_line", "justifications"),
    ),
    _case("hello", None, [], features=("greeting",)),
    _case(
        "Factor x^2 + 7x + 12. (x+3)(x+4)",
        "x^2 + 7x + 12",
        ["(x+3)(x+4)"],
        features=("one_line",),
    ),
    _case(
        "Step 1: 4x - 3 = 9\nStep 2: 4x = 12\nStep 3: x = 3",
        None,
        ["4x - 3 = 9", "4x = 12", "x = 3"],
        stored="6x - 3 = 2x + 9",
        features=("steps_only", "numbered"),
    ),
    _case(
        "Solve 3(x+1) = 12: x + 1 = 4 => x = 3",
        "3(x+1) = 12",
        ["x + 1 = 4", "x = 3"],
        features=("one_line",),
    ),
    _case(
        "i dont know how to start with x^2 = 49",
        "x^2 = 49",
        [],
        features=("problem_only",),
    ),
    _case(
        "sqrt(x+4) = 3, x + 4 = 9, x = 5",
        "sqrt(x+4) = 3",
        ["x + 4 = 9", "x = 5"],
        features=("one_line",),
    ),
    _case(
        "$\\frac{x}{2} = 7$, $x = 14$",
        "(x)/(2) = 7",
        ["x = 14"],
        features=("latex", "one_line"),
    ),
    _case(
        "Solve |x - 2| = 5 → x - 2 = 5 or x - 2 = -5 → x = 7 or x = -3",
        "abs(x - 2) = 5",
        ["x - 2 = 5 or x - 2 = -5", "x = 7 or x = -3"],
        features=("unicode", "one_line"),
    ),
    _case(
        "Problem: Twice a number decreased by 4 is 10. My work: 2x - 4 = 10, 2x = 14, x = 7.",
        "Twice a number decreased by 4 is 10.",
        ["2x - 4 = 10", "2x = 14", "x = 7"],
        features=("word_problem",),
    ),
    _case("ans: x = 5", None, [], stored="x - 2 = 3", features=("answer_only",)),
    _case(
        "Evaluate 6 × 4 ÷ 2: 24 ÷ 2 = 12",
        "6 * 4 / 2",
        ["24 / 2 = 12"],
        features=("unicode", "one_line"),
    ),
    _case(
        "x = 3 / 0.5\nx = 6",
        None,
        ["x = 3 / 0.5", "x = 6"],
        stored="0.5x = 3",
        features=("steps_only",),
    ),
    _case(
        "Solve -3x = 12. x = 4",
        "-3x = 12",
        ["x = 4"],
        features=("wrong_step", "one_line"),
    ),
    _case(
        "thanks, that makes sense now!",
        None,
        [],
        stored="2x + 3 = 11",
        features=("smalltalk",),
    ),
]
