"""Graph wiring: the diagnosis subgraph and the main graph."""

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from tutor.nodes.classify import classify
from tutor.nodes.finish_diagnosis import finish_diagnosis
from tutor.nodes.hint import hint
from tutor.nodes.localize import localize
from tutor.nodes.orchestrator import orchestrator
from tutor.nodes.parse_input import parse_input
from tutor.nodes.retrieve import retrieve
from tutor.nodes.verify import verify
from tutor.state import TutorState
from tutor.tools.diagnosis import is_clean_solution


def route_after_verify(state: TutorState) -> Literal["finish_diagnosis", "localize"]:
    """A clean correct solution ends the diagnosis; anything else goes on to localize."""
    return "finish_diagnosis" if is_clean_solution(state) else "localize"


def build_diagnosis_graph() -> CompiledStateGraph[TutorState, None, TutorState, TutorState]:
    """parse_input -> classify -> verify -> (localize -> retrieve ->) finish_diagnosis."""
    graph = StateGraph(TutorState)
    graph.add_node("parse_input", parse_input)
    graph.add_node("classify", classify)
    graph.add_node("verify", verify)
    graph.add_node("localize", localize)
    graph.add_node("retrieve", retrieve)
    graph.add_node("finish_diagnosis", finish_diagnosis)
    graph.add_edge(START, "parse_input")
    graph.add_edge("parse_input", "classify")
    graph.add_edge("classify", "verify")
    graph.add_conditional_edges("verify", route_after_verify)
    graph.add_edge("localize", "retrieve")
    graph.add_edge("retrieve", "finish_diagnosis")
    graph.add_edge("finish_diagnosis", END)
    return graph.compile()


def route_from_orchestrator(state: TutorState) -> Literal["diagnosis", "hint", "__end__"]:
    """Follow `next_action`: diagnose and hint go on; ask and reply end the run.

    A missing `next_action` ends the run (the state is `total=False`). "__end__" is langgraph's
    END; it must stay a literal here because langgraph reads the edge targets from this annotation.
    """
    action = state.get("next_action", "reply")
    if action == "diagnose":
        return "diagnosis"
    if action == "hint":
        return "hint"
    return "__end__"


def build_main_graph() -> CompiledStateGraph[TutorState, None, TutorState, TutorState]:
    """orchestrator <-> diagnosis / hint. Both always return to the orchestrator."""
    graph = StateGraph(TutorState)
    graph.add_node("orchestrator", orchestrator)
    graph.add_node("diagnosis", build_diagnosis_graph())
    graph.add_node("hint", hint)
    graph.add_edge(START, "orchestrator")
    graph.add_conditional_edges("orchestrator", route_from_orchestrator)
    graph.add_edge("diagnosis", "orchestrator")
    graph.add_edge("hint", "orchestrator")
    return graph.compile()
