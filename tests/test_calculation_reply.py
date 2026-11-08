from typing import Any

import pytest
from pydantic import BaseModel

from tutor.graph import build_diagnosis_graph, route_after_verify
from tutor.nodes.hint import hint
from tutor.nodes.orchestrator import orchestrator
from tutor.nodes.verify import verify
from tutor.state import ErrorContext, HintText, Misconception, Step, TutorState
from tutor.tools import structured
from tutor.tools.diagnosis import is_calculation_reply

CONTEXT = ErrorContext(step_number=1, before="4x - 3(x + 1) = 5", after="4x - 3x + 1 = 5")
MISCONCEPTION = Misconception(id="M001", description="drops a sign", topic="Algebra", score=0.9)


def _reply(*claims: str, **extra: Any) -> TutorState:
    state: TutorState = {
        "problem": "4x - 3(x + 1) = 5",
        "student_steps": [Step(claim=claim, kind="equation") for claim in claims],
        "intent": "answer",
        "error_context": CONTEXT,
        "misconception": MISCONCEPTION,
        "error_type": "algebraic_transformation",
        "first_error_step": 1,
        "focus_step": 1,
        "hint_level": 2,
        "hints_used": 1,
        "misconceptions_seen": ["M001"],
    }
    state.update(extra)  # type: ignore[typeddict-item]
    return state


def _checked(*claims: str, **extra: Any) -> TutorState:
    state = _reply(*claims, **extra)
    state.update(verify(state))  # type: ignore[typeddict-item]
    return state


def test_a_new_attempt_in_a_reply_is_not_a_calculation() -> None:
    assert not is_calculation_reply(_reply("4x - 3x - 3 = 5", "x = 8"))


def test_a_message_with_no_earlier_diagnosis_is_not_a_calculation_reply() -> None:
    state = _checked("2 + 3 = 6", error_context=None)
    assert not is_calculation_reply(state)
    assert route_after_verify(state) == "localize"


def test_a_calculation_is_not_localized_and_the_diagnosis_stands() -> None:
    out = build_diagnosis_graph().invoke(_reply("-3 * 1 = 3"))
    assert out["step_verdicts"][0].check_holds is False
    assert out["first_error_step"] == 1 and out["focus_step"] == 1
    assert out["error_type"] == "algebraic_transformation"
    assert out["misconception"] == MISCONCEPTION


@pytest.mark.parametrize("claim", ["-3 * 1 = 3", "-3 * 1 = -3"])
def test_the_orchestrator_keeps_the_context_and_the_level(claim: str) -> None:
    out = orchestrator(_checked(claim, stage="diagnosed"))
    assert out == {"next_action": "hint", "hint_retries": 0}


@pytest.fixture
def prompts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []

    def fake(name: str, schema: type[BaseModel], text: str, retries: int = 1) -> HintText:
        seen.append(text)
        return HintText(text="What sign do you expect?", reply_moves_forward=False)

    monkeypatch.setattr(structured, "call_structured", fake)
    return seen


@pytest.mark.parametrize(("claim", "verdict"), [("-3 * 1 = 3", "false"), ("-3 * 1 = -3", "true")])
def test_the_hint_is_told_the_verdict_of_sympy(
    prompts: list[str], claim: str, verdict: str
) -> None:
    hint(_checked(claim))
    assert f"SymPy checked the reply: `{claim}` is {verdict}" in prompts[0]
    assert "Line before the wrong step: 4x - 3(x + 1) = 5" in prompts[0]


def test_a_wrong_calculation_does_not_raise_the_level(prompts: list[str]) -> None:
    state = _checked("-3 * 1 = 3")
    out = hint(state)
    assert out["reply_moves_forward"] is None
    state.update(out)  # type: ignore[typeddict-item]
    state["stage"] = "hinted"
    assert "hint_level" not in orchestrator(state)


def test_another_reply_still_gets_the_verdict_of_the_model(prompts: list[str]) -> None:
    out = hint(_reply(student_steps=[]))
    assert out["reply_moves_forward"] is False
    assert "SymPy checked" not in prompts[0]
