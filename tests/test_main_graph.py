import runpy
import sys
from pathlib import Path
from typing import Any

import pytest
from langgraph.graph import END, START

from tutor import graph as graph_module
from tutor.graph import build_main_graph, route_from_orchestrator
from tutor.state import TutorState


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


def test_with_the_stubs_a_run_replies_and_ends() -> None:
    result = build_main_graph().invoke({"student_id": "ada"})
    assert result["reply_text"] == "TODO"


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


def test_parse_input_runs_once_per_message_not_once_per_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs: list[str] = []

    def scripted_parse(state: TutorState) -> dict[str, Any]:
        runs.append("parse_input")
        return {}

    def scripted(state: TutorState) -> dict[str, Any]:
        stage = state.get("stage", "new_message")
        if stage == "new_message":
            return {"next_action": "diagnose"}
        return {"next_action": "reply", "reply_text": "done"}

    monkeypatch.setattr(graph_module, "parse_input", scripted_parse)
    monkeypatch.setattr(graph_module, "orchestrator", scripted)
    build_main_graph().invoke({"stage": "new_message"})
    assert runs == ["parse_input"]  # the diagnosis ran and returned; parse_input did not rerun


def test_draw_script_writes_mermaid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "graph.mmd"
    monkeypatch.setattr(sys, "argv", ["draw_graph.py", "--out", str(out)])
    script = Path(__file__).resolve().parents[1] / "scripts" / "draw_graph.py"
    runpy.run_path(str(script), run_name="__main__")
    text = out.read_text(encoding="utf-8")
    assert "orchestrator" in text
    assert "verify" in text
