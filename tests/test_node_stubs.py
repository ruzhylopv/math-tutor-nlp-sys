from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from tutor.nodes.finish_diagnosis import finish_diagnosis
from tutor.nodes.hint import hint
from tutor.nodes.verify import verify
from tutor.state import ErrorContext, Step, TutorState

Node = Callable[[TutorState], dict[str, Any]]

DECLARED_WRITES: dict[str, set[str]] = {
    "verify": {"is_correct", "step_verdicts"},
    "finish_diagnosis": {"stage", "error_context"},
    "hint": {"hint_text", "stage"},
}
NODES: dict[str, Node] = {
    "verify": verify,
    "finish_diagnosis": finish_diagnosis,
    "hint": hint,
}
PROMPTS = Path(__file__).resolve().parents[1] / "src" / "tutor" / "prompts"


@pytest.mark.parametrize("name", NODES)
def test_stub_returns_only_its_declared_fields(name: str) -> None:
    assert set(NODES[name]({})) == DECLARED_WRITES[name]


@pytest.mark.parametrize("name", NODES)
def test_stub_values_have_the_declared_types(name: str) -> None:
    result = NODES[name]({})
    TypeAdapter(TutorState).validate_python(result)


@pytest.mark.parametrize("name", ["parse_input", "classify", "localize", "hint", "orchestrator"])
def test_llm_node_prompt_has_the_required_sections(name: str) -> None:
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    for section in ("## Role", "## Inputs", "## Task", "## Output format", "## Rules"):
        assert section in text
    assert "## Role\nTODO" not in text  # the Role is filled in (the other sections come later)


def test_finish_diagnosis_marks_the_stage() -> None:
    assert finish_diagnosis({"stage": "new_message"}) == {
        "stage": "diagnosed",
        "error_context": None,
    }


def test_finish_diagnosis_stores_the_wrong_step() -> None:
    state: TutorState = {
        "problem": "2(x + 3) = 10",
        "student_steps": [Step(claim="2x + 3 = 10"), Step(claim="2x = 7")],
        "focus_step": 1,
    }
    assert finish_diagnosis(state)["error_context"] == ErrorContext(
        step_number=1, before="2(x + 3) = 10", after="2x + 3 = 10"
    )
    state["focus_step"] = 2
    assert finish_diagnosis(state)["error_context"] == ErrorContext(
        step_number=2, before="2x + 3 = 10", after="2x = 7", correct_steps=["2x + 3 = 10"]
    )


@pytest.mark.parametrize("focus", [None, 0, 3])
def test_finish_diagnosis_clears_the_context_without_a_usable_focus_step(
    focus: int | None,
) -> None:
    state: TutorState = {
        "student_steps": [Step(claim="x = 3"), Step(claim="x = 3")],
        "focus_step": focus,
        "error_context": ErrorContext(step_number=1, before="a", after="b"),
    }
    state["focus_step"] = focus
    assert finish_diagnosis(state)["error_context"] is None


@pytest.mark.parametrize(
    ("steps", "focus", "before"),
    [
        (
            [
                Step(claim="2x = 8"),
                Step(claim="now divide by two", kind="reason"),
                Step(claim="x = 5"),
            ],
            3,
            "2x = 8",
        ),
        ([Step(claim="t = x + 3", kind="definition"), Step(claim="x = 5")], 2, "2x + 6 = 14"),
        (
            [Step(claim="2x = 8"), Step(claim="2*4 = 8", kind="check"), Step(claim="x = 5")],
            3,
            "2x = 8",
        ),
    ],
)
def test_finish_diagnosis_keeps_the_line_the_focus_step_was_really_compared_with(
    steps: list[Step], focus: int, before: str
) -> None:
    state: TutorState = {"problem": "2x + 6 = 14", "student_steps": steps, "focus_step": focus}
    state["step_verdicts"] = verify(state)["step_verdicts"]
    context = finish_diagnosis(state)["error_context"]
    assert context is not None and context.before == before
