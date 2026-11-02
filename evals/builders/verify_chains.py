"""Hand-written multi-step chains for `verify`: definitions (substitution), reason lines, answers.

Dev split only (flexible-input plan, layer 3). Each chain has the problem, the steps (claim and the
`kind` parse_input would give, sometimes a wrong one on purpose), the expected relation of every
step and the expected `is_correct`, worked out by hand, not by running the node. A check line that
holds is `equivalent`, as in verify_steps.jsonl. Run this module to write
evals/datasets/dev/verify_chains.jsonl.
"""

import json
import logging
from pathlib import Path
from typing import Any

Chain = dict[str, Any]
OUT = Path(__file__).resolve().parents[1] / "datasets" / "dev" / "verify_chains.jsonl"
logger = logging.getLogger("verify_chains")


def _chain(
    problem: str,
    steps: list[tuple[str, str, str]],
    is_correct: bool,
    *features: str,
) -> Chain:
    return {
        "problem": problem,
        "steps": [{"claim": claim, "kind": kind} for claim, kind, _ in steps],
        "expected_relations": [relation for _, _, relation in steps],
        "expected_is_correct": is_correct,
        "features": list(features),
    }


EQ, DEF, REASON = "equation", "definition", "reason"
CHAINS: list[Chain] = [
    _chain(
        "(2x-1)^2 - 5(2x-1) + 6 = 0",
        [
            ("u = 2x - 1", DEF, "equivalent"),
            ("u^2 - 5u + 6 = 0", EQ, "equivalent"),
            ("(u - 2)(u - 3) = 0", EQ, "equivalent"),
            ("u = 2 or u = 3", EQ, "equivalent"),
            ("x = 3/2 or x = 2", EQ, "equivalent"),
        ],
        True,
        "definition",
    ),
    _chain(
        "(2x-1)^2 - 5(2x-1) + 6 = 0",
        [
            ("u = 2x - 1", DEF, "equivalent"),
            ("u^2 - 5u + 6 = 0", EQ, "equivalent"),
            ("u = 2 or u = 3", EQ, "equivalent"),
            ("x = 1/2 or x = 1", EQ, "not_valid"),
        ],
        False,
        "definition",
        "wrong_back_substitution",
    ),
    _chain(
        "x^4 - 10x^2 + 9 = 0",
        [
            ("w = x^2", DEF, "equivalent"),
            ("w^2 - 10w + 9 = 0", EQ, "equivalent"),
            ("(w - 1)(w - 9) = 0", EQ, "equivalent"),
            ("w = -1 or w = -9", EQ, "not_valid"),
        ],
        False,
        "definition",
        "wrong_after_definition",
    ),
    _chain(
        "x^4 - 13x^2 + 36 = 0",
        [
            ("s = x^2", DEF, "equivalent"),
            ("s^2 - 13s + 36 = 0", EQ, "equivalent"),
            ("s = 4 or s = 9", EQ, "equivalent"),
        ],
        False,
        "definition",
        "answer_in_new_letter",
    ),
    _chain(
        "3x + 2 = 11",
        [("x = 11 - 2", DEF, "not_valid")],
        False,
        "not_a_definition",
    ),
    _chain(
        "4(x - 3) = 0",
        [
            ("4 is not zero", REASON, "unparsable"),
            ("x - 3 = 0", EQ, "equivalent"),
            ("x = 3", EQ, "equivalent"),
        ],
        True,
        "reason",
    ),
    _chain(
        "x^2 = 16",
        [
            ("x = 4 or x = -4", EQ, "equivalent"),
            ("x = 4", REASON, "not_valid"),
        ],
        False,
        "reason_that_parses",
    ),
    _chain(
        "2x - 7 = 3",
        [
            ("2x = 10", EQ, "equivalent"),
            ("x = 5", EQ, "equivalent"),
            ("so that's the answer", REASON, "unparsable"),
        ],
        True,
        "reason",
    ),
    _chain(
        "1/(x+1)^2 - 1/(x+1) = 2",
        [
            ("a = x + 1", DEF, "equivalent"),
            ("b = 1/a", DEF, "equivalent"),
            ("b^2 - b = 2", EQ, "equivalent"),
            ("b = 2 or b = -1", EQ, "equivalent"),
            ("x = -1/2 or x = -2", EQ, "equivalent"),
        ],
        True,
        "definition",
        "nested_definition",
    ),
    _chain(
        "(x - 2)^2 = 9",
        [
            ("y = x - 2", DEF, "equivalent"),
            ("y^2 = 9", EQ, "equivalent"),
            ("y = 3 or y = -3", EQ, "equivalent"),
            ("x = 5 or x = -1", EQ, "equivalent"),
            ("(5 - 2)^2 = 9", "check", "equivalent"),
        ],
        True,
        "definition",
        "check",
    ),
    _chain(
        "(a + b)^2 - (a + b)",
        [
            ("s = a + b", DEF, "equivalent"),
            ("s^2 - s", EQ, "equivalent"),
            ("s*(s - 1)", EQ, "equivalent"),
            ("(a + b)(a + b - 1)", EQ, "equivalent"),
        ],
        True,
        "definition",
        "expression",
    ),
    _chain(
        "3(x^2 - 4x + 3) = 0",
        [
            ("A = x^2 - 4x + 3", DEF, "equivalent"),
            ("3A = 0", EQ, "equivalent"),
            ("3 is not zero so", REASON, "unparsable"),
            ("A = 0", EQ, "equivalent"),
            ("x^2 - 4x + 3 = 0", EQ, "equivalent"),
            ("(x - 1)(x - 3) = 0", EQ, "equivalent"),
            ("x = 1 or x = 3", EQ, "equivalent"),
        ],
        True,
        "definition",
        "reason",
    ),
    _chain(
        "(x + 3)^2 + 2(x + 3) - 8 = 0",
        [
            ("k = x + 3", EQ, "equivalent"),
            ("k^2 + 2k - 8 = 0", EQ, "equivalent"),
            ("(k + 4)(k - 2) = 0", EQ, "equivalent"),
        ],
        False,
        "definition",
        "mislabelled_definition",
        "answer_in_new_letter",
    ),
    _chain(
        "2(x + 1)^2 = 8",
        [
            ("(x + 1)^2 = 8", EQ, "not_valid"),
            ("p = x + 1", DEF, "equivalent"),
            ("p^2 = 8", EQ, "equivalent"),
            ("p = sqrt(8) or p = -sqrt(8)", EQ, "equivalent"),
        ],
        False,
        "definition",
        "wrong_before_definition",
    ),
]


def chain_records() -> list[dict[str, Any]]:
    """The chains as dataset records."""
    return [
        {
            "id": f"chain/{index:03d}",
            **chain,
            "source": "handwritten",
            "provenance": {"spot_check": "pending"},
        }
        for index, chain in enumerate(CHAINS)
    ]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    records = chain_records()
    OUT.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    logger.info("Wrote %d chains to %s", len(records), OUT)


if __name__ == "__main__":
    main()
