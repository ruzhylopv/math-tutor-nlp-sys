"""The data the graph panel draws, built without Streamlit from the real compiled graph."""

import json
from dataclasses import dataclass
from typing import Any

import pytest
from langchain_core.runnables.graph import Graph, Node
from langgraph.checkpoint.memory import MemorySaver

from tutor.graph import build_main_graph
from tutor.trace import Trace, node_details, panel_view


@dataclass(frozen=True)
class Step:
    path: str
    seconds: float = 1.0
    details: tuple[str, ...] = ()
    failed: bool = False


@pytest.fixture
def graph() -> Graph:
    return build_main_graph(MemorySaver()).get_graph(xray=True)


def _node(view: dict[str, Any], node_id: str) -> dict[str, Any]:
    return next(n for n in view["nodes"] if n["id"] == node_id)


def _edge(view: dict[str, Any], source: str, target: str) -> dict[str, Any]:
    return next(e for e in view["edges"] if (e["source"], e["target"]) == (source, target))


def test_every_real_node_is_there_and_the_inner_end_is_joined_through(graph: Graph) -> None:
    view = panel_view(graph, Trace(), [])
    ids = {n["id"] for n in view["nodes"]}
    assert {"__start__", "parse_input", "orchestrator", "hint", "__end__"} <= ids
    assert {"diagnosis:verify", "diagnosis:localize", "diagnosis:retrieve"} <= ids
    assert "diagnosis:__end__" not in ids
    assert _edge(view, "diagnosis:retrieve", "orchestrator")["back"]
    assert [g["id"] for g in view["groups"]] == ["diagnosis"]


def test_a_new_node_appears_by_itself() -> None:
    graph = Graph()
    graph.nodes = {
        name: Node(id=name, name=name, data=None, metadata=None)
        for name in ("__start__", "fresh_node", "__end__")
    }
    graph.add_edge(graph.nodes["__start__"], graph.nodes["fresh_node"])
    graph.add_edge(graph.nodes["fresh_node"], graph.nodes["__end__"])
    node = _node(panel_view(graph, Trace(), []), "fresh_node")
    assert (node["label"], node["rank"], node["group"]) == ("fresh_node", 1, None)


def test_the_view_is_json(graph: Graph) -> None:
    trace = Trace().start("parse_input").finish("parse_input")
    json.dumps(panel_view(graph, trace, [Step("parse_input", details=("intent: solve",))]))


def test_rows_run_down_the_graph_and_loops_do_not_push_them(graph: Graph) -> None:
    view = panel_view(graph, Trace(), [])
    rank = {n["id"]: n["rank"] for n in view["nodes"]}
    assert rank["__start__"] < rank["parse_input"] < rank["orchestrator"]
    assert rank["orchestrator"] < rank["hint"]
    assert rank["diagnosis:verify"] < rank["diagnosis:localize"] < rank["diagnosis:retrieve"]
    assert _edge(view, "hint", "orchestrator")["back"]
    assert not _edge(view, "orchestrator", "hint")["back"]


def test_a_group_stays_in_one_column_in_the_middle(graph: Graph) -> None:
    view = panel_view(graph, Trace(), [])
    slot = {n["id"]: n["slot"] for n in view["nodes"]}
    assert slot["diagnosis:verify"] == slot["diagnosis:localize"] == slot["diagnosis:retrieve"]
    assert slot["hint"] < slot["diagnosis:verify"] < slot["__end__"]


def test_each_status_is_reported(graph: Graph) -> None:
    trace = Trace().start("parse_input").finish("parse_input").start("orchestrator")
    view = panel_view(graph, trace, [])
    assert _node(view, "parse_input")["status"] == "done"
    assert _node(view, "orchestrator")["status"] == "running"
    assert _node(view, "hint")["status"] == "idle"
    failed = panel_view(graph, trace.end(error=True), [])
    assert _node(failed, "orchestrator")["status"] == "failed"


def test_a_group_shows_the_worst_of_its_members(graph: Graph) -> None:
    def status(trace: Trace) -> str:
        return panel_view(graph, trace, [])["groups"][0]["status"]

    assert status(Trace()) == "idle"
    verifying = Trace().start("diagnosis").start("diagnosis:verify")
    assert status(verifying) == "running"
    assert status(verifying.finish("diagnosis:verify").finish("diagnosis")) == "done"
    assert status(verifying.finish("diagnosis:verify", failed=True)) == "failed"


def test_runs_durations_and_repeats_belong_to_their_node(graph: Graph) -> None:
    trace = Trace().start("orchestrator").finish("orchestrator").start("orchestrator")
    steps = [Step("orchestrator", 1.25, ("action: hint",)), Step("diagnosis", 9.0)]
    view = panel_view(graph, trace, steps)
    node = _node(view, "orchestrator")
    assert (node["count"], node["seconds"]) == (2, 1.25)
    assert node["runs"] == [{"seconds": 1.25, "failed": False, "details": ["action: hint"]}]
    assert "diagnosis" not in {n["id"] for n in view["nodes"]}  # the wrapper is the group


def test_only_the_edges_this_turn_used_are_taken(graph: Graph) -> None:
    trace = Trace().start("parse_input").finish("parse_input").start("orchestrator")
    view = panel_view(graph, trace, [])
    assert _edge(view, "__start__", "parse_input")["taken"]
    assert _edge(view, "parse_input", "orchestrator")["taken"]
    assert not _edge(view, "orchestrator", "hint")["taken"]
    assert not _edge(view, "orchestrator", "__end__")["taken"]
    done = panel_view(graph, trace.finish("orchestrator").end(error=False), [])
    assert _edge(done, "orchestrator", "__end__")["taken"]
    assert _node(done, "__end__")["status"] == "done"


def test_the_draft_hint_never_reaches_the_page(graph: Graph) -> None:
    update = {"hint_text": "THE ANSWER IS 7", "reply_moves_forward": True}
    step = Step("hint", details=node_details("hint", update))
    assert "THE ANSWER" not in json.dumps(panel_view(graph, Trace(), [step]))
