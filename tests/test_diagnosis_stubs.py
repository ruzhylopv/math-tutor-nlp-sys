from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from tutor.nodes.classify import classify
from tutor.nodes.finish_diagnosis import finish_diagnosis
from tutor.nodes.localize import localize
from tutor.nodes.parse_input import parse_input
from tutor.nodes.retrieve import retrieve
from tutor.nodes.verify import verify
from tutor.state import TutorState

Node = Callable[[TutorState], dict[str, Any]]

DECLARED_WRITES: dict[str, set[str]] = {
    "parse_input": {"problem", "student_steps"},
    "classify": {"topic", "level"},
    "verify": {"is_correct", "step_verdicts"},
    "localize": {"first_error_step", "focus_step", "error_type"},
    "retrieve": {"misconception_candidates", "misconception"},
    "finish_diagnosis": {"stage"},
}
NODES: dict[str, Node] = {
    "parse_input": parse_input,
    "classify": classify,
    "verify": verify,
    "localize": localize,
    "retrieve": retrieve,
    "finish_diagnosis": finish_diagnosis,
}
PROMPTS = Path(__file__).resolve().parents[1] / "src" / "tutor" / "prompts"


@pytest.mark.parametrize("name", NODES)
def test_stub_returns_only_its_declared_fields(name: str) -> None:
    assert set(NODES[name]({})) == DECLARED_WRITES[name]


@pytest.mark.parametrize("name", NODES)
def test_stub_values_have_the_declared_types(name: str) -> None:
    result = NODES[name]({})
    TypeAdapter(TutorState).validate_python(result)


@pytest.mark.parametrize("name", ["parse_input", "classify", "localize"])
def test_llm_node_prompt_has_the_required_sections(name: str) -> None:
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    for section in ("## Role", "## Inputs", "## Task", "## Output format", "## Rules"):
        assert section in text
    assert "## Role\nTODO" not in text  # the Role is filled in
    assert "## Inputs\nTODO" in text  # the rest is still to do


def test_finish_diagnosis_marks_the_stage() -> None:
    assert finish_diagnosis({"stage": "new_message"}) == {"stage": "diagnosed"}
