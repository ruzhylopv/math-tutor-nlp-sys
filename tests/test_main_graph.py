import runpy
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START

from tutor import graph as graph_module
from tutor.graph import build_main_graph, new_turn, route_from_orchestrator
from tutor.state import Decision, HintText, ParsedInput, Step, TutorState
from tutor.tools import structured
from tutor.tools.canned_hints import canned_hint


@pytest.mark.parametrize(
    ("action", "expected"),
    [("diagnose", "diagnosis"), ("hint", "hint"), ("ask", END), ("reply", END)],
)
def test_routing_follows_next_action(action: str, expected: str) -> None:
    state: TutorState = {"next_action": action}  # type: ignore[typeddict-item]
    assert route_from_orchestrator(state) == expected


def test_a_missing_action_ends_the_run() -> None:
    assert route_from_orchestrator({}) == END


def test_main_graph_has_the_designed_nodes_and_edges() -> None:
    drawn = build_main_graph().get_graph()
    assert {"parse_input", "orchestrator", "diagnosis", "hint"} <= set(drawn.nodes)
    edges = {(edge.source, edge.target) for edge in drawn.edges}
    assert {
        (START, "parse_input"),
        ("parse_input", "orchestrator"),
        ("orchestrator", "diagnosis"),
        ("orchestrator", "hint"),
        ("orchestrator", END),
        ("diagnosis", "orchestrator"),
        ("hint", "orchestrator"),
    } <= edges
    # parse_input runs once per message: nothing in the loop leads back to it
    assert {edge.source for edge in drawn.edges if edge.target == "parse_input"} == {START}


def test_a_greeting_replies_and_ends(monkeypatch: pytest.MonkeyPatch) -> None:
    # parse_input is the real node here; it makes no LLM call because the state has no messages.
    # The orchestrator is real too; only its model call is scripted.
    monkeypatch.setattr(
        structured,
        "call_structured",
        lambda name, schema, text, retries=1: Decision(
            action="reply", reason="greeting", reply_text="Hello!"
        ),
    )
    result = build_main_graph().invoke({"student_id": "ada"})
    assert result["reply_text"] == "Hello!"


@pytest.mark.parametrize("action", ["ask", "reply"])
def test_ask_and_reply_end_the_run(monkeypatch: pytest.MonkeyPatch, action: str) -> None:
    calls: list[str] = []

    def scripted(state: TutorState) -> dict[str, Any]:
        calls.append(action)
        return {"next_action": action, "reply_text": f"{action} text"}

    monkeypatch.setattr(graph_module, "orchestrator", scripted)
    result = build_main_graph().invoke({})
    assert calls == [action]  # the orchestrator ran once and the run ended
    assert result["reply_text"] == f"{action} text"


def test_diagnosis_and_hint_both_return_to_the_orchestrator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """diagnose -> diagnosis -> orchestrator -> hint -> orchestrator -> reply."""
    seen: list[str] = []

    def scripted(state: TutorState) -> dict[str, Any]:
        stage = state.get("stage", "new_message")
        seen.append(stage)
        if stage == "new_message":
            return {"next_action": "diagnose"}
        if stage == "diagnosed":
            return {"next_action": "hint"}
        return {"next_action": "reply", "reply_text": "done"}

    monkeypatch.setattr(graph_module, "orchestrator", scripted)
    result = build_main_graph().invoke({"stage": "new_message"})
    assert seen == ["new_message", "diagnosed", "hinted"]
    assert result["reply_text"] == "done"


def test_parse_input_runs_first_and_the_orchestrator_sees_its_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []

    def scripted_parse(state: TutorState) -> dict[str, Any]:
        order.append("parse_input")
        return {"problem": "2x = 4"}

    def scripted(state: TutorState) -> dict[str, Any]:
        order.append(f"orchestrator sees {state.get('problem')}")
        return {"next_action": "reply", "reply_text": "ok"}

    monkeypatch.setattr(graph_module, "parse_input", scripted_parse)
    monkeypatch.setattr(graph_module, "orchestrator", scripted)
    build_main_graph().invoke({})
    assert order == ["parse_input", "orchestrator sees 2x = 4"]


def _script_loop(
    monkeypatch: pytest.MonkeyPatch, route_after_diagnosis: Literal["hint", "reply"]
) -> dict[str, list[str]]:
    """Script parse_input, diagnosis and the orchestrator; record how often each one ran."""
    calls: dict[str, list[str]] = {
        "parse_input": [],
        "diagnosis": [],
        "hint": [],
        "orchestrator": [],
    }

    def scripted_parse(state: TutorState) -> dict[str, Any]:
        calls["parse_input"].append("run")
        return {}

    def scripted_diagnosis(state: TutorState) -> dict[str, Any]:
        calls["diagnosis"].append("run")
        return {"stage": "diagnosed"}

    def scripted_hint(state: TutorState) -> dict[str, Any]:
        calls["hint"].append("run")
        return {"stage": "hinted"}

    def scripted_orchestrator(state: TutorState) -> dict[str, Any]:
        calls["orchestrator"].append("run")
        stage = state.get("stage", "new_message")
        if stage == "new_message":
            return {"next_action": "diagnose"}
        if stage == "diagnosed" and route_after_diagnosis == "hint":
            return {"next_action": "hint"}
        return {"next_action": "reply", "reply_text": "done"}

    monkeypatch.setattr(graph_module, "parse_input", scripted_parse)
    monkeypatch.setattr(graph_module, "build_diagnosis_graph", lambda: scripted_diagnosis)
    monkeypatch.setattr(graph_module, "hint", scripted_hint)
    monkeypatch.setattr(graph_module, "orchestrator", scripted_orchestrator)
    return calls


def test_parse_input_runs_once_per_message_across_the_diagnosis_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _script_loop(monkeypatch, route_after_diagnosis="reply")
    result = build_main_graph().invoke({"stage": "new_message"})
    assert result["reply_text"] == "done"
    assert calls["diagnosis"] == ["run"]
    assert calls["orchestrator"] == ["run", "run"]  # before and after the diagnosis
    assert calls["parse_input"] == ["run"]  # the loop did not re-parse
    assert calls["hint"] == []


def test_parse_input_runs_once_per_message_across_the_hint_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _script_loop(monkeypatch, route_after_diagnosis="hint")
    result = build_main_graph().invoke({"stage": "new_message"})
    assert result["reply_text"] == "done"
    assert calls["diagnosis"] == ["run"]
    assert calls["hint"] == ["run"]
    assert calls["orchestrator"] == ["run", "run", "run"]  # new message, diagnosed, hinted
    assert calls["parse_input"] == ["run"]  # neither loop re-parsed


def test_draw_script_writes_mermaid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "graph.mmd"
    monkeypatch.setattr(sys, "argv", ["draw_graph.py", "--out", str(out)])
    script = Path(__file__).resolve().parents[1] / "scripts" / "draw_graph.py"
    runpy.run_path(str(script), run_name="__main__")
    text = out.read_text(encoding="utf-8")
    assert "orchestrator" in text
    assert "verify" in text


def test_a_stopped_substitution_and_a_reply_to_the_hint(
    monkeypatch: pytest.MonkeyPatch, canned_llm: Callable[..., None]
) -> None:
    """The chat that started the flexible-input work: both turns, only the model is scripted."""
    monkeypatch.delenv("LEARNER_DB_PATH", raising=False)
    monkeypatch.setattr("tutor.config.load_dotenv", lambda: False)
    graph = build_main_graph(InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "t"}}
    canned_llm(
        ParsedInput=ParsedInput(
            problem="5(x + 32x^2 + 2) = 0",
            steps=[
                Step(claim="A = x + 32x^2 + 2", kind="definition"),
                Step(claim="5A = 0"),
                Step(claim="5 is not zero", kind="reason"),
            ],
            intent="stuck",
            topic="Algebra",
            level=2,
        ),
        Decision=Decision(action="diagnose", reason="working"),
        HintText=HintText(text="Good so far. What must be true of `A`?"),
    )
    first = graph.invoke(new_turn("ada", "my work, what next?"), config)
    assert first["error_type"] == "incomplete" and first["focus_step"] == 2
    assert first["hint_level"] == 1 and first["hints_used"] == 1

    canned_llm(
        ParsedInput=ParsedInput(intent="answer"),
        HintText=HintText(text="Yes, that is the idea. What next?", reply_moves_forward=True),
    )  # no Decision: a reply is routed without the model
    second = graph.invoke(new_turn("ada", "It has to be equal to zero"), config)
    assert second["messages"][-1].content == "Yes, that is the idea. What next?"
    assert second["hint_level"] == 1 and second["hints_used"] == 2


def _stopped_turn() -> ParsedInput:
    return ParsedInput(
        problem="x^2 + 4 = 5x",
        steps=[Step(claim="x^2 - 5x + 4 = 0")],
        intent="check_work",
        topic="Algebra",
        level=2,
    )


def test_a_new_problem_labelled_answer_is_not_a_reply_to_the_old_diagnosis(
    monkeypatch: pytest.MonkeyPatch, canned_llm: Callable[..., None]
) -> None:
    monkeypatch.delenv("LEARNER_DB_PATH", raising=False)
    monkeypatch.setattr("tutor.config.load_dotenv", lambda: False)
    graph = build_main_graph(InMemorySaver())
    config: RunnableConfig = {"configurable": {"thread_id": "t"}}
    canned_llm(
        ParsedInput=_stopped_turn(),
        Decision=Decision(action="diagnose", reason="working"),
        HintText=HintText(text="Good so far. What comes next?"),
    )
    first = graph.invoke(new_turn("ada", "my work"), config)
    assert first["error_context"] is not None and first["hints_used"] == 1
    graph.update_state(config, {"hint_level": 3})  # as if earlier hints had raised it

    canned_llm(
        ParsedInput=ParsedInput(problem="2y = 6", intent="answer", topic="Algebra", level=1),
        Decision=Decision(action="ask", reason="no working", reply_text="Show me your steps."),
    )  # no HintText: a hint would fail the test
    second = graph.invoke(new_turn("ada", "2y = 6"), config)
    assert second["next_action"] == "ask"
    assert second["messages"][-1].content == "Show me your steps."
    assert second["hint_level"] == 1 and second["hints_used"] == 0
    assert second["error_context"] is None


def test_a_stopped_solution_through_a_leak_rejection_and_the_fallback(
    monkeypatch: pytest.MonkeyPatch, canned_llm: Callable[..., None]
) -> None:
    monkeypatch.delenv("LEARNER_DB_PATH", raising=False)
    monkeypatch.setattr("tutor.config.load_dotenv", lambda: False)
    canned_llm(
        ParsedInput=_stopped_turn(),
        Decision=Decision(action="diagnose", reason="working"),
        HintText=HintText(text="Try `(x - 1)(x - 4) = 0`."),
    )
    result = build_main_graph().invoke(new_turn("ada", "my work"))
    assert result["error_type"] == "incomplete"
    assert result["hint_retries"] == 1 and result["hints_used"] == 1
    assert result["messages"][-1].content == canned_hint(1, "incomplete")
