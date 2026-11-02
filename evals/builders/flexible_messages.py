"""Hand-written `parse_input` messages for line kinds and intent (flexible-input plan, layer 2).

Dev split only. Each case also has the tutor's last message (or None), the expected `kind` of each
expected step and the expected intent, worked out by reading the message, not by running the node.
None of these is used in the prompt. Run this module to (re)write the `flex/` cases at the end of
evals/datasets/dev/parse_input.jsonl; every other line of that file is kept as it is.
"""

import json
import logging
from pathlib import Path
from typing import Any

Case = dict[str, Any]
DEV_FILE = Path(__file__).resolve().parents[1] / "datasets" / "dev" / "parse_input.jsonl"
logger = logging.getLogger("flexible_messages")


def _case(
    message: str,
    problem: str | None,
    steps: list[tuple[str, str]],
    intent: str,
    *,
    stored: str | None = None,
    tutor: str | None = None,
    features: tuple[str, ...] = (),
) -> Case:
    return {
        "message": message,
        "stored_problem": stored,
        "tutor_message": tutor,
        "problem": problem,
        "steps": [claim for claim, _ in steps],
        "kinds": [kind for _, kind in steps],
        "intent": intent,
        "features": list(features),
    }


FLEXIBLE: list[Case] = [
    _case(
        "let t = x + 1\nt^2 - 3t - 10 = 0\n(t - 5)(t + 2) = 0\nt = 5 or t = -2\n"
        "how do I get back to x?",
        None,
        [
            ("t = x + 1", "definition"),
            ("t^2 - 3t - 10 = 0", "equation"),
            ("(t - 5)(t + 2) = 0", "equation"),
            ("t = 5 or t = -2", "equation"),
        ],
        "stuck",
        stored="(x+1)^2 - 3(x+1) - 10 = 0",
        features=("definition",),
    ),
    _case(
        "Solve 2^(2x) - 6*2^x + 8 = 0\nput y = 2^x\ny^2 - 6y + 8 = 0\ny = 2 or y = 4\n"
        "x = 1 or x = 2",
        "2^(2x) - 6*2^x + 8 = 0",
        [
            ("y = 2^x", "definition"),
            ("y^2 - 6y + 8 = 0", "equation"),
            ("y = 2 or y = 4", "equation"),
            ("x = 1 or x = 2", "equation"),
        ],
        "check_work",
        features=("definition",),
    ),
    _case(
        "x^2 = -9\na square can't be negative\nI don't know what to do now",
        None,
        [("x^2 = -9", "equation"), ("a square can't be negative", "reason")],
        "stuck",
        stored="x^2 + 9 = 0",
        features=("reason",),
    ),
    _case(
        "x - 2 = 0 because 5 is not zero\nx = 2",
        None,
        [("x - 2 = 0", "equation"), ("x = 2", "equation")],
        "check_work",
        stored="5(x - 2) = 0",
        features=("reason_attached",),
    ),
    _case(
        "one of the brackets must be zero\nx - 3 = 0 or x + 4 = 0\nx = 3 or x = -4",
        None,
        [
            ("one of the brackets must be zero", "reason"),
            ("x - 3 = 0 or x + 4 = 0", "equation"),
            ("x = 3 or x = -4", "equation"),
        ],
        "check_work",
        stored="(x - 3)(x + 4) = 0",
        features=("reason",),
    ),
    _case(
        "4x = 16\nx = 4\ncheck: 4*4 - 7 = 9",
        None,
        [("4x = 16", "equation"), ("x = 4", "equation"), ("4*4 - 7 = 9", "check")],
        "check_work",
        stored="4x - 7 = 9",
        features=("check",),
    ),
    _case(
        "2x = 12",
        None,
        [("2x = 12", "equation")],
        "answer",
        stored="2x + 3 = 15",
        tutor="Good start. What do you get if you subtract 3 from both sides?",
        features=("reply_math",),
    ),
    _case(
        "zero",
        None,
        [],
        "answer",
        stored="6/(x - 2) = 3",
        tutor="Which number can never be a divisor?",
        features=("reply_words",),
    ),
    _case(
        "at least one of them is zero",
        None,
        [],
        "answer",
        stored="(2x - 1)(x + 5) = 0",
        tutor="If a product of two factors is zero, what can you say about the factors?",
        features=("reply_words",),
    ),
    _case(
        "what does it mean to distribute?",
        None,
        [],
        "explain",
        stored="3(x + 4) = 2x - 1",
    ),
    _case(
        "ok got it. new one: 7 - 3x = 16",
        "7 - 3x = 16",
        [],
        "new_problem",
        stored="x + 5 = 9",
        tutor="Well done, x = 4 is right!",
    ),
    _case(
        "I have no idea where to begin",
        None,
        [],
        "stuck",
        stored="x^2 - 5x + 6 = 0",
    ),
    _case(
        "Solve x/3 + 2 = 6. First I took away 2 and got x/3 = 4, then times 3 so x = 12. Right?",
        "x/3 + 2 = 6",
        [("x/3 = 4", "equation"), ("x = 12", "equation")],
        "check_work",
        features=("prose",),
    ),
    _case(
        "brb, dinner",
        None,
        [],
        "other",
        stored="2x = 10",
        tutor="What could you divide both sides by?",
    ),
    _case(
        "say u = 1/x, then u + u^2 = 6, so u^2 + u - 6 = 0, u = 2 or u = -3. now I'm lost",
        None,
        [
            ("u = 1/x", "definition"),
            ("u + u^2 = 6", "equation"),
            ("u^2 + u - 6 = 0", "equation"),
            ("u = 2 or u = -3", "equation"),
        ],
        "stuck",
        stored="1/x + 1/x^2 = 6",
        features=("definition", "prose"),
    ),
]


def flexible_records() -> list[dict[str, Any]]:
    """The cases as dataset records (dev split)."""
    return [
        {
            "id": f"flex/{index:03d}",
            "message": case["message"],
            "stored_problem": case["stored_problem"],
            "tutor_message": case["tutor_message"],
            "expected_problem": case["problem"],
            "expected_steps": case["steps"],
            "expected_kinds": case["kinds"],
            "expected_intent": case["intent"],
            "features": case["features"],
            "source": "flexible",
            "provenance": {"spot_check": "pending"},
        }
        for index, case in enumerate(FLEXIBLE)
    ]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    lines = DEV_FILE.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if line and not json.loads(line)["id"].startswith("flex/")]
    added = [json.dumps(record) for record in flexible_records()]
    DEV_FILE.write_text("\n".join(kept + added) + "\n", encoding="utf-8")
    logger.info("%s: %d lines kept, %d flex cases written", DEV_FILE, len(kept), len(added))


if __name__ == "__main__":
    main()
