"""A turn stopped by a 429 leaves the chat as it was: real graph and saver, scripted model."""

from typing import Any

import pytest
from pydantic import BaseModel

from tutor import ui
from tutor.state import Decision, HintText, ParsedInput, Step
from tutor.tools import structured

NO_QUOTA = structured.QuotaExceededError("429")
GOOD_HINT = HintText(text="Good so far. What comes next?")
WORKING = ParsedInput(
    problem="x^2 + 4 = 5x",
    steps=[Step(claim="x^2 - 5x + 4 = 0")],
    intent="stuck",
    topic="Algebra",
    level=2,
)
STUCK = ParsedInput(intent="stuck")
DIAGNOSE = Decision(action="diagnose", reason="working")
HINT = Decision(action="hint", reason="wants help")


@pytest.fixture(autouse=True)
def _no_learner_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LEARNER_DB_PATH", raising=False)
    monkeypatch.setattr("tutor.config.load_dotenv", lambda: False)


@pytest.fixture
def tutor() -> ui.Tutor:
    return ui.build_tutor(":memory:")


def _script(monkeypatch: pytest.MonkeyPatch, *answers: BaseModel | Exception) -> None:
    """Each model call gets the answer of its schema; an exception is raised instead."""
    by_schema = {type(a).__name__: a for a in answers if isinstance(a, BaseModel)}

    def fake(prompt_name: str, schema: type[BaseModel], user_text: str, retries: int = 1) -> Any:
        if schema.__name__ in by_schema:
            return by_schema[schema.__name__]
        raise NO_QUOTA

    monkeypatch.setattr(structured, "call_structured", fake)


def _send(tutor: ui.Tutor, text: str) -> ui.TurnView:
    *_, view = ui.send_stream(tutor, "ada", 1, text)
    assert isinstance(view, ui.TurnView)
    return view


def _counters(tutor: ui.Tutor) -> dict[str, Any]:
    values = tutor.graph.get_state(ui._config("ada", 1)).values
    keys = ("hint_level", "hints_used", "turns", "misconceptions_seen", "stage")
    return {key: values.get(key) for key in keys}


def _first_turn(tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch) -> None:
    _script(monkeypatch, WORKING, DIAGNOSE, GOOD_HINT)
    view = _send(tutor, "my work")
    assert (view.error, view.hint_level) == (False, 1)


def test_a_429_in_hint_changes_nothing_however_often_it_is_retried(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    _first_turn(tutor, monkeypatch)
    counters = _counters(tutor)
    history = ui.load_history(tutor, "ada", 1)
    assert counters["hint_level"] == 1 and counters["turns"] == 1

    _script(monkeypatch, STUCK, HINT)  # no HintText: the hint node gets a 429
    for _ in range(2):
        assert _send(tutor, "I am stuck") == ui.TurnView(reply=ui.NO_QUOTA_REPLY, error=True)
        assert _counters(tutor) == counters
        assert ui.load_history(tutor, "ada", 1) == history

    _script(monkeypatch, STUCK, HINT, GOOD_HINT)
    view = _send(tutor, "I am stuck")
    assert (view.error, view.hint_level) == (False, 2)  # the next level, none skipped
    assert _counters(tutor)["turns"] == 2
    assert ui.load_history(tutor, "ada", 1) == [
        *history,
        ("user", "I am stuck"),
        ("assistant", GOOD_HINT.text),
    ]


def test_a_429_after_a_diagnosis_does_not_raise_the_level_on_retry(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    _first_turn(tutor, monkeypatch)
    counters = _counters(tutor)

    _script(monkeypatch, WORKING, DIAGNOSE)  # the diagnosis runs, then the hint node gets a 429
    assert _send(tutor, "my work again").error
    assert _counters(tutor) == counters

    _script(monkeypatch, WORKING, DIAGNOSE, GOOD_HINT)
    view = _send(tutor, "my work again")
    assert (view.error, view.hint_level) == (False, 2)
    assert [role for role, _ in ui.load_history(tutor, "ada", 1)] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]


def test_a_429_on_the_first_message_leaves_an_empty_chat(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    _script(monkeypatch, WORKING, DIAGNOSE)
    assert _send(tutor, "my work").reply == ui.NO_QUOTA_REPLY
    assert ui.load_history(tutor, "ada", 1) == []
    assert tutor.graph.get_state(ui._config("ada", 1)).values == {}
    assert ui.next_chat(tutor, "ada") == 1  # the failed chat was not saved

    _script(monkeypatch, WORKING, DIAGNOSE, GOOD_HINT)
    view = _send(tutor, "my work")
    assert (view.error, view.hint_level) == (False, 1)
    assert ui.load_history(tutor, "ada", 1) == [
        ("user", "my work"),
        ("assistant", GOOD_HINT.text),
    ]


def test_the_student_is_still_told_when_the_undo_fails(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("database is locked")

    monkeypatch.setattr(tutor.saver, "delete_thread", broken)
    _script(monkeypatch, WORKING, DIAGNOSE)
    assert _send(tutor, "my work") == ui.TurnView(reply=ui.NO_QUOTA_REPLY, error=True)
