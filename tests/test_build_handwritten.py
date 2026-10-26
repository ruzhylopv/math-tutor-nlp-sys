import collections

from evals.builders.handwritten import HANDWRITTEN
from tutor.tools.algebra import step_relation


def test_the_checker_agrees_with_every_hand_labelled_case() -> None:
    disagreements = [
        (
            case["prev"],
            case["curr"],
            case["relation"],
            step_relation(case["prev"], case["curr"], case["original"]),
        )
        for case in HANDWRITTEN
        if step_relation(case["prev"], case["curr"], case["original"]) != case["relation"]
    ]
    assert disagreements == []


def test_every_relation_and_task_type_is_covered() -> None:
    relations = collections.Counter(case["relation"] for case in HANDWRITTEN)
    assert set(relations) == {"equivalent", "implies", "narrows", "not_valid", "unparsable"}
    assert min(relations.values()) >= 3
    assert {case["task_type"] for case in HANDWRITTEN} == {"solve", "simplify", "expand", "factor"}


def test_narrows_cases_carry_the_original_problem() -> None:
    narrows = [case for case in HANDWRITTEN if case["relation"] == "narrows"]
    assert narrows and all(case["original"] for case in narrows)
