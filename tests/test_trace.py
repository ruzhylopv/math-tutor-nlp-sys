from typing import Any

import pytest
from langchain_core.runnables.graph import Graph

from tutor.graph import build_main_graph
from tutor.state import Misconception, StepVerdict
from tutor.tools.diagnosis import fresh_problem_fields
from tutor.trace import ACTIVE, FAILED, TAKEN_EDGE, Trace, graph_dot, node_details, node_path


@pytest.fixture(scope="module")
def graph() -> Graph:
    return build_main_graph().get_graph(xray=True)


def _line(dot: str, start: str) -> str:
    return next(line for line in dot.splitlines() if line.startswith(start))


def test_every_real_node_is_drawn_and_the_inner_end_is_joined_through(graph: Graph) -> None:
    dot = graph_dot(graph, Trace())
    for node in ("parse_input", "orchestrator", "hint", "diagnosis:verify", "diagnosis:retrieve"):
        assert f'"{node}" [label=' in dot
    assert "diagnosis:__end__" not in dot
    assert '"diagnosis:retrieve" -> "orchestrator"' in dot
    assert '"diagnosis:verify" -> "orchestrator"' in dot


def test_the_running_node_is_green_and_only_it(graph: Graph) -> None:
    dot = graph_dot(graph, Trace().start("parse_input").finish("parse_input").start("orchestrator"))
    assert f'fillcolor="{ACTIVE}"' in _line(dot, '"orchestrator" [')
    assert dot.count(f'fillcolor="{ACTIVE}"') == 1


def test_the_subgraph_border_is_green_while_a_step_inside_runs(graph: Graph) -> None:
    trace = Trace().start("diagnosis").start("diagnosis:verify")
    dot = graph_dot(graph, trace)
    assert f'color="{ACTIVE}"' in dot.split('subgraph "cluster_diagnosis"')[1].split("\n")[1]
    assert f'fillcolor="{ACTIVE}"' in _line(dot, '"diagnosis:verify" [')


def test_nothing_is_green_after_the_turn_and_the_path_stays_marked(graph: Graph) -> None:
    trace = Trace().start("parse_input").finish("parse_input")
    trace = trace.start("orchestrator").finish("orchestrator").end(error=False)
    dot = graph_dot(graph, trace)
    assert f'fillcolor="{ACTIVE}"' not in dot
    assert f'color="{TAKEN_EDGE}"' in _line(dot, '"orchestrator" -> "__end__"')
    assert f'color="{TAKEN_EDGE}"' in _line(dot, '"__start__" -> "parse_input"')
    assert f'color="{TAKEN_EDGE}"' not in _line(dot, '"orchestrator" -> "hint"')


def test_a_node_that_runs_twice_is_counted(graph: Graph) -> None:
    trace = Trace().start("orchestrator").finish("orchestrator").start("orchestrator")
    assert 'label="orchestrator ×2"' in graph_dot(graph, trace)


def test_an_error_marks_what_was_running_as_failed(graph: Graph) -> None:
    dot = graph_dot(graph, Trace().start("parse_input").end(error=True))
    assert f'fillcolor="{FAILED}"' in _line(dot, '"parse_input" [')
    assert f'fillcolor="{ACTIVE}"' not in dot
    assert f'color="{TAKEN_EDGE}"' not in _line(dot, '"orchestrator" -> "__end__"')


def test_node_path_drops_the_task_id_of_a_subgraph() -> None:
    assert node_path((), "hint") == "hint"
    assert node_path(("diagnosis:3c4bbf71",), "verify") == "diagnosis:verify"


def test_the_hint_details_never_contain_the_draft() -> None:
    draft = "The answer is x = 3"
    details = node_details("hint", {"hint_text": draft, "stage": "hinted"})
    assert details == ("draft written",)


@pytest.mark.parametrize(
    ("node", "update", "expected"),
    [
        ("orchestrator", {"hint_retries": 1, "next_action": "hint"}, "leak check: rejected"),
        ("orchestrator", {"hints_used": 1, "next_action": "reply"}, "hint published"),
        ("orchestrator", {"next_action": "ask", "decision_reason": "no steps"}, "why: no steps"),
        ("parse_input", {"intent": "attempt", "student_steps": []}, "intent: attempt"),
        ("localize", {"first_error_step": 2, "error_type": "other"}, "first error step: 2"),
        ("retrieve", {"misconception": None}, "no misconception"),
    ],
)
def test_node_details_say_what_the_node_decided(
    node: str, update: dict[str, Any], expected: str
) -> None:
    assert any(expected in line for line in node_details(node, update))


def test_a_clean_solution_reports_the_reply_and_no_hint() -> None:
    update = {**fresh_problem_fields(), "next_action": "reply", "is_correct": True}
    assert node_details("orchestrator", update) == ("action: reply",)


def test_the_hint_level_shows_when_a_hint_is_routed_or_published() -> None:
    routed = {"next_action": "hint", "hint_level": 2, "hint_retries": 0}
    assert node_details("orchestrator", routed) == ("action: hint", "hint level: 2")
    published = {"next_action": "reply", "hints_used": 1, "hint_level": 3}
    assert node_details("orchestrator", published) == (
        "leak check finished, hint published",
        "hint level: 3",
    )


def test_verify_details_list_each_verdict() -> None:
    update = {
        "is_correct": False,
        "step_verdicts": [
            StepVerdict(step_index=1, relation="not_valid"),
            StepVerdict(step_index=2, relation="equivalent"),
        ],
    }
    assert node_details("verify", update) == (
        "answer correct: False",
        "steps: 1 not_valid, 2 equivalent",
    )


def test_retrieve_details_show_the_misconception() -> None:
    found = Misconception(id="M014", description="adds exponents", topic="Algebra", score=0.8249)
    assert node_details("retrieve", {"misconception": found}) == ("M014 (0.82): adds exponents",)


def test_an_unknown_node_or_an_empty_update_has_no_details() -> None:
    assert node_details("diagnosis", {"is_correct": True}) == ()
    assert node_details("hint", {}) == ()
