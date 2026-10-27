from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from tutor.nodes.finish_diagnosis import finish_diagnosis
from tutor.nodes.hint import hint
from tutor.nodes.orchestrator import orchestrator
from tutor.nodes.retrieve import retrieve
from tutor.nodes.verify import verify
from tutor.state import TutorState

Node = Callable[[TutorState], dict[str, Any]]

DECLARED_WRITES: dict[str, set[str]] = {
    "verify": {"is_correct", "step_verdicts"},
    "retrieve": {"misconception_candidates", "misconception"},
    "finish_diagnosis": {"stage"},
    "hint": {"hint_text", "stage"},
    "orchestrator": {"next_action", "reply_text"},
}
NODES: dict[str, Node] = {
    "verify": verify,
    "retrieve": retrieve,
    "finish_diagnosis": finish_diagnosis,
    "hint": hint,
    "orchestrator": orchestrator,
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
    assert finish_diagnosis({"stage": "new_message"}) == {"stage": "diagnosed"}
