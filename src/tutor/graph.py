"""Graph wiring: the diagnosis subgraph (and, later, the main graph)."""

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from tutor.nodes.classify import classify
from tutor.nodes.finish_diagnosis import finish_diagnosis
from tutor.nodes.localize import localize
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
