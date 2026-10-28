from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from tutor import ui
from tutor.state import Decision
from tutor.tools.learner_db import record_attempt


@pytest.fixture(autouse=True)
def _greeting(canned_llm: Callable[..., None]) -> None:
    canned_llm(Decision=Decision(action="reply", reason="greeting", reply_text="Hello!"))


@pytest.fixture
def tutor() -> ui.Tutor:
    return ui.build_tutor(":memory:")


def test_send_returns_the_reply_and_the_visited_nodes(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = ui.send(tutor, "ada", 1, "hi")
    assert view.reply == "Hello!"
    assert view.hint_level is None
    assert not view.error
    assert "orchestrator" in view.visited


def test_history_comes_from_the_checkpoint(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    ui.send(tutor, "ada", 1, "hi")
    assert ui.load_history(tutor, "ada", 1) == [("user", "hi"), ("assistant", "Hello!")]
    assert ui.load_history(tutor, "ada", 2) == []  # another chat
    assert ui.load_history(tutor, "bob", 1) == []  # another name


def test_a_failed_run_becomes_a_friendly_reply(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("429")

    monkeypatch.setattr(tutor.graph, "stream", boom)
    view = ui.send(tutor, "ada", 1, "hi")
    assert view.error
    assert view.reply == ui.ERROR_REPLY


def test_new_chat_is_a_new_thread_and_latest_chat_finds_the_newest(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert ui.latest_chat(tutor, "ada") == 1
    assert ui.next_chat(tutor, "ada") == 1
    ui.send(tutor, "ada", 1, "first")
    assert ui.next_chat(tutor, "ada") == 2
    ui.send(tutor, "ada", 2, "second")
    ui.send(tutor, "ada", 3, "third")
    ui.send(tutor, "adam", 9, "someone else")
    assert ui.latest_chat(tutor, "ada") == 3
    assert ui.next_chat(tutor, "ada") == 4
    assert ui.load_history(tutor, "ada", 2) == [("user", "second"), ("assistant", "Hello!")]


def test_sidebar_reads_the_profile_across_chats(
    tutor: ui.Tutor, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = str(tmp_path / "learner.db")
    monkeypatch.setenv("LEARNER_DB_PATH", db)
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("MODEL_NAME", "m")
    from tutor.state import MisconceptionRecord

    record_attempt(
        db, "ada", "p", "algebra", 1, 2, 1, True, [MisconceptionRecord(misconception_id="M038")]
    )
    for chat in (1, 2):
        info = ui.sidebar_info(tutor, "ada", chat)
        assert info.profile is not None
        assert info.profile.misconception_counts == {"M038": 1}
        assert info.hints_used == 0
        assert info.hint_level is None


def test_sidebar_without_a_learner_db_has_no_profile(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("MODEL_NAME", "m")
    monkeypatch.delenv("LEARNER_DB_PATH", raising=False)
    monkeypatch.setattr("tutor.config.load_dotenv", lambda: False)
    assert ui.sidebar_info(tutor, "ada", 1).profile is None


def test_names_are_trimmed_and_collapsed() -> None:
    assert ui.normalise_name("  Ada   Lovelace ") == "Ada Lovelace"


def test_send_stream_yields_progress_then_the_turn(tutor: ui.Tutor) -> None:
    events = list(ui.send_stream(tutor, "ada", 1, "hi"))
    *progress, view = events
    assert [event.text for event in progress if isinstance(event, ui.Progress)] == [
        ui.PROGRESS_LABELS["parse_input"],
        ui.PROGRESS_LABELS["orchestrator"],
    ]
    assert isinstance(view, ui.TurnView)
    assert view.reply == "Hello!"


def test_a_node_without_a_label_shows_nothing(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ui, "PROGRESS_LABELS", {"orchestrator": "Deciding…"})
    events = list(ui.send_stream(tutor, "ada", 1, "hi"))
    assert [e.text for e in events if isinstance(e, ui.Progress)] == ["Deciding…"]


def test_a_failed_stream_ends_with_an_error_turn(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("429")

    monkeypatch.setattr(tutor.graph, "stream", boom)
    events = list(ui.send_stream(tutor, "ada", 1, "hi"))
    assert events == [ui.TurnView(reply=ui.ERROR_REPLY, error=True)]


def test_a_published_hint_sets_the_hint_level(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Graph:
        def stream(self, *args: object, **kwargs: object) -> list[tuple[tuple[()], str, object]]:
            return [((), "updates", {"hint": {}})]

        def get_state(self, config: object) -> object:
            return type("S", (), {"values": {"reply_text": "Try again", "hint_level": 2}})()

    view = ui.send(replace(tutor, graph=Graph()), "ada", 1, "x")  # type: ignore[arg-type]
    assert (view.hint_level, view.reply, view.error) == (2, "Try again", False)


def test_an_empty_reply_is_an_error(tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch) -> None:
    class Graph:
        def stream(self, *args: object, **kwargs: object) -> list[object]:
            return []

        def get_state(self, config: object) -> object:
            return type("S", (), {"values": {}})()

    view = ui.send(replace(tutor, graph=Graph()), "ada", 1, "x")  # type: ignore[arg-type]
    assert view.error and view.reply == ui.ERROR_REPLY
