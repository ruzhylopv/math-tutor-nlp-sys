import copy
from typing import Any

import pytest

from tutor.nodes.retrieve import TOP_K, focus_lines, retrieve
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
    }
    return TutorState(**(base | fields))  # type: ignore[typeddict-item]


@pytest.fixture
def searches(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, int]]:
    seen: list[tuple[str, str, int]] = []

    def fake(previous: str, written: str, k: int = 5) -> list[Misconception]:
        seen.append((previous, written, k))
        return [_match("M001", 0.9), _match("M002", 0.5)]

    monkeypatch.setattr(retrieval, "search", fake)
    return seen


def test_the_first_step_is_compared_with_the_problem() -> None:
    assert focus_lines(_state()) == ("3(x + 2) = 15", "3x + 2 = 15")


def test_a_later_focus_step_is_compared_with_the_line_before_it() -> None:
    assert focus_lines(_state(focus_step=2)) == ("3x + 2 = 15", "3x = 13")


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
def test_nothing_to_look_for_gives_no_lines_and_no_search(
    changes: dict[str, Any], searches: list[tuple[str, str, int]]
) -> None:
    state = _state(**changes)
    assert focus_lines(state) is None
    assert retrieve(state) == {"misconception_candidates": [], "misconception": None}
    assert searches == []


def test_a_missing_error_type_or_focus_step_is_treated_like_none(
    searches: list[tuple[str, str, int]],
) -> None:
    state = _state()
    del state["error_type"]
    assert retrieve(state)["misconception"] is None
    state = _state()
    del state["focus_step"]
    assert retrieve(state)["misconception"] is None
    assert searches == []


def test_the_best_match_is_the_misconception_and_all_are_candidates(
    searches: list[tuple[str, str, int]],
) -> None:
    result = retrieve(_state())
    assert [m.id for m in result["misconception_candidates"]] == ["M001", "M002"]
    assert result["misconception"] == result["misconception_candidates"][0]
    assert searches == [("3(x + 2) = 15", "3x + 2 = 15", TOP_K)]


def test_an_empty_search_gives_no_misconception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(retrieval, "search", lambda previous, written, k=5: [])
    assert retrieve(_state()) == {"misconception_candidates": [], "misconception": None}


def test_only_the_declared_fields_are_returned_and_the_state_is_not_changed(
    searches: list[tuple[str, str, int]],
) -> None:
    state = _state()
    before = copy.deepcopy(state)
    assert set(retrieve(state)) == {"misconception_candidates", "misconception"}
    assert state == before
