import runpy
import sys
from pathlib import Path
from typing import Any, Literal

import pytest
from langgraph.graph import END, START

from tutor import graph as graph_module
from tutor.graph import build_main_graph, route_from_orchestrator
from tutor.state import Decision, TutorState
from tutor.tools import structured


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
