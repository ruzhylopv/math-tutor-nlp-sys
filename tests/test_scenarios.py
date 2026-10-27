"""Replay scenarios A and B through the real graph with the model scripted.

The model nodes (parse_input, classify, orchestrator decision, hint wording) and `retrieve` are
scripted; verify, localize, finish_diagnosis, the orchestrator's plain-code modes, the leakage
check, the checkpointer and the learner DB are real. This tests the wiring and the routing rules,
not the model; the live replay is `evals/scripts/eval_orchestrator.py`.
"""

from typing import Any

import pytest
from pydantic import BaseModel

from evals.scenario_runner import Scenario, ScenarioResult, load_scenario, replay, scenario_paths
from tutor import graph as graph_module
from tutor.state import (
    Classification,
    Decision,
    HintText,
    Misconception,
    ParsedInput,
    Step,
    TutorState,
)
from tutor.tools import structured

PARSED: dict[str, ParsedInput] = {
    "3(x + 2) = 15. I got x = 13/3": ParsedInput(problem="3(x + 2) = 15"),
    "3x + 2 = 15; 3x = 13; x = 13/3": ParsedInput(
        steps=[Step(claim="3x + 2 = 15"), Step(claim="3x = 13"), Step(claim="x = 13/3")]
    ),
    "3x + 6 = 15; 3x = 9; x = 3": ParsedInput(
        steps=[Step(claim="3x + 6 = 15"), Step(claim="3x = 9"), Step(claim="x = 3")]
    ),
    "sqrt(x + 7) = x - 5. x + 7 = x^2 - 25; x^2 - x - 32 = 0; x = (1 +- sqrt(129))/2": ParsedInput(
        problem="sqrt(x + 7) = x - 5",
        steps=[
            Step(claim="x + 7 = x^2 - 25", operation="square"),
            Step(claim="x^2 - x - 32 = 0"),
            Step(claim="x = (1 + sqrt(129))/2 or x = (1 - sqrt(129))/2"),
        ],
    ),
    "isn't (x - 5)^2 just x^2 - 25?": ParsedInput(),
    "x + 7 = x^2 - 10x + 25; x^2 - 11x + 18 = 0; (x - 9)(x - 2) = 0; x = 9 or x = 2": ParsedInput(
        steps=[
            Step(claim="x + 7 = x^2 - 10x + 25", operation="square"),
            Step(claim="x^2 - 11x + 18 = 0"),
            Step(claim="(x - 9)(x - 2) = 0"),
            Step(claim="x = 9 or x = 2"),
        ]
    ),
    "Checking x = 9 works; x = 2 fails (sqrt(9) = 3, 2 - 5 = -3), so x = 9": ParsedInput(
        steps=[
            Step(claim="x + 7 = x^2 - 10x + 25", operation="square"),
            Step(claim="x^2 - 11x + 18 = 0"),
            Step(claim="(x - 9)(x - 2) = 0"),
            Step(claim="x = 9 or x = 2"),
            Step(claim="sqrt(9 + 7) = 9 - 5"),
            Step(claim="x = 9"),
        ]
    ),
}
DECISIONS: dict[str, Decision] = {
    "3(x + 2) = 15. I got x = 13/3": Decision(
        action="ask", reason="answer only", reply_text="Can you show me your steps?"
    ),
    "isn't (x - 5)^2 just x^2 - 25?": Decision(action="hint", reason="a question"),
}


@pytest.fixture(autouse=True)
def scripted(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(name: str, schema: type[BaseModel], text: str, retries: int = 1) -> Any:
        if name == "parse_input":
            return PARSED[text.split("Student message:\n", 1)[1]]
        if name == "classify":
            return Classification(topic="Algebra", level=2)
        if name == "orchestrator":
            message = text.split("Student message: ", 1)[1].split("\nStored problem:", 1)[0]
            return DECISIONS.get(message, Decision(action="diagnose", reason="steps"))
        if name == "hint":
            return HintText(text="What does the 3 multiply in `3(x + 2)`? You did well so far.")
        raise AssertionError(name)

    def retrieve(state: TutorState) -> dict[str, Any]:
        if state.get("error_type") == "omission_extraneous_root":
            found = ("M064", "squaring_extraneous")
        elif "sqrt" in state.get("problem", ""):
            found = ("M038", "exponents")
        else:
            found = ("M010", "distribution")
        return {
            "misconception": Misconception(id=found[0], description="d", topic="Algebra", score=1)
        }

    monkeypatch.setattr(structured, "call_structured", fake)
    monkeypatch.setattr(graph_module, "retrieve", retrieve)


def _scenario(name: str) -> Scenario:
    path = next(p for p in scenario_paths() if p.stem == name)
    return load_scenario(path)


def _replay(name: str) -> ScenarioResult:
    return replay(_scenario(name))


def test_both_scenarios_are_present_and_load() -> None:
    assert [p.stem for p in scenario_paths()] == ["a", "b"]


@pytest.mark.parametrize("name", ["a", "b"])
def test_scenario_meets_every_expectation(name: str) -> None:
    result = _replay(name)
    for number, turn in enumerate(result.turns, 1):
        assert turn.failures == [], f"turn {number}: {turn.failures}"
        assert turn.misconception_ok in (None, True), f"turn {number}: {turn.misconception}"


def test_scenario_b_levels_follow_the_misconceptions() -> None:
    levels = [turn.hint_level for turn in _replay("b").turns]
    assert levels == [1, 2, 1, None]


def test_scenario_a_offers_practice_on_the_third_occurrence() -> None:
    last = _replay("a").turns[-1]
    assert "practice" in last.reply


def test_hints_given_counts_published_hints() -> None:
    assert _replay("b").hints_given == 3
