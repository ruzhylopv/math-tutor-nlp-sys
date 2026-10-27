import copy
from typing import Any

import pytest

from tutor.nodes.retrieve import TOP_K, build_query, retrieve
from tutor.state import Misconception, Step, TutorState
from tutor.tools import retrieval


def _match(identifier: str, score: float) -> Misconception:
    return Misconception(id=identifier, description=f"d {identifier}", topic="Algebra", score=score)


def _state(**fields: Any) -> TutorState:
    base: dict[str, Any] = {
        "problem": "3(x + 2) = 15",
        "student_steps": [Step(claim="3x + 2 = 15"), Step(claim="3x = 13")],
        "focus_step": 1,
        "error_type": "algebraic_transformation",
        "topic": "Algebra",
    }
    return TutorState(**(base | fields))  # type: ignore[typeddict-item]


@pytest.fixture
def searches(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    seen: list[tuple[str, int]] = []

    def fake(query: str, k: int = 5) -> list[Misconception]:
        seen.append((query, k))
        return [_match("M001", 0.9), _match("M002", 0.5)]

    monkeypatch.setattr(retrieval, "search", fake)
    return seen


def test_the_query_has_the_catalogue_example_shape_for_the_first_step() -> None:
    assert build_query(_state()) == (
        "Algebra. algebraic transformation. Example: 3(x + 2) = 15 -> 3x + 2 = 15"
    )


def test_a_later_focus_step_uses_the_line_before_it() -> None:
    query = build_query(_state(focus_step=2))
    assert query is not None and query.endswith("Example: 3x + 2 = 15 -> 3x = 13")


def test_a_missing_topic_is_left_out() -> None:
    state = _state()
    del state["topic"]
    assert build_query(state) == "algebraic transformation. Example: 3(x + 2) = 15 -> 3x + 2 = 15"


@pytest.mark.parametrize(
    "changes",
    [
        {"focus_step": None},
        {"error_type": None},
        {"error_type": "other"},
        {"focus_step": 0},
        {"focus_step": 3},
        {"student_steps": []},
    ],
)
def test_nothing_to_look_for_gives_no_query_and_no_search(
    changes: dict[str, Any], searches: list[tuple[str, int]]
) -> None:
    state = _state(**changes)
    assert build_query(state) is None
    assert retrieve(state) == {"misconception_candidates": [], "misconception": None}
    assert searches == []


def test_the_best_match_is_the_misconception_and_all_are_candidates(
    searches: list[tuple[str, int]],
) -> None:
    result = retrieve(_state())
    assert [m.id for m in result["misconception_candidates"]] == ["M001", "M002"]
    assert result["misconception"] == result["misconception_candidates"][0]
    assert searches == [(build_query(_state()), TOP_K)]


def test_an_empty_search_gives_no_misconception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(retrieval, "search", lambda query, k=5: [])
    assert retrieve(_state()) == {"misconception_candidates": [], "misconception": None}


def test_only_the_declared_fields_are_returned_and_the_state_is_not_changed(
    searches: list[tuple[str, int]],
) -> None:
    state = _state()
    before = copy.deepcopy(state)
    assert set(retrieve(state)) == {"misconception_candidates", "misconception"}
    assert state == before
