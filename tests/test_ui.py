from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from tutor import ui
from tutor.state import Decision
from tutor.tools import structured
from tutor.tools.learner_db import record_attempt


@pytest.fixture(autouse=True)
def _greeting(canned_llm: Callable[..., None]) -> None:
    canned_llm(Decision=Decision(action="reply", reason="greeting", reply_text="Hello!"))


def _send(tutor: ui.Tutor, student_id: str, chat: int, text: str) -> ui.TurnView:
    *_, view = ui.send_stream(tutor, student_id, chat, text)
    assert isinstance(view, ui.TurnView)  # the stream always ends with one
    return view


@pytest.fixture
def tutor() -> ui.Tutor:
    return ui.build_tutor(":memory:")


def test_send_returns_the_reply_and_the_visited_nodes(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    view = _send(tutor, "ada", 1, "hi")
    assert view.reply == "Hello!"
    assert view.hint_level is None
    assert not view.error
    assert "orchestrator" in view.visited


def test_history_comes_from_the_checkpoint(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    _send(tutor, "ada", 1, "hi")
    assert ui.load_history(tutor, "ada", 1) == [("user", "hi"), ("assistant", "Hello!")]
    assert ui.load_history(tutor, "ada", 2) == []  # another chat
    assert ui.load_history(tutor, "bob", 1) == []  # another name


def test_a_failed_run_becomes_a_friendly_reply(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("429")

    monkeypatch.setattr(tutor.graph, "stream", boom)
    view = _send(tutor, "ada", 1, "hi")
    assert view.error
    assert view.reply == ui.ERROR_REPLY


def test_new_chat_is_a_new_thread_and_latest_chat_finds_the_newest(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert ui.latest_chat(tutor, "ada") == 1
    assert ui.next_chat(tutor, "ada") == 1
    _send(tutor, "ada", 1, "first")
    assert ui.next_chat(tutor, "ada") == 2
    _send(tutor, "ada", 2, "second")
    _send(tutor, "ada", 3, "third")
    _send(tutor, "adam", 9, "someone else")
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


def test_send_stream_logs_each_step_with_its_time(tutor: ui.Tutor) -> None:
    *steps, view = list(ui.send_stream(tutor, "ada", 1, "hi"))
    assert steps == [
        ui.StepStarted("parse_input", ui.PROGRESS_LABELS["parse_input"]),
        ui.StepFinished("parse_input", ui.PROGRESS_LABELS["parse_input"], steps[1].seconds),
        ui.StepStarted("orchestrator", ui.PROGRESS_LABELS["orchestrator"]),
        ui.StepFinished("orchestrator", ui.PROGRESS_LABELS["orchestrator"], steps[3].seconds),
    ]
    assert all(s.seconds >= 0 for s in steps if isinstance(s, ui.StepFinished))
    assert isinstance(view, ui.TurnView)
    assert view.reply == "Hello!"


def test_step_time_is_measured_from_start_to_result(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Graph:
        def stream(self, *args: object, **kwargs: object) -> list[tuple[tuple[()], str, object]]:
            return [
                ((), "tasks", {"id": "a", "name": "hint", "input": {}, "triggers": []}),
                ((), "tasks", {"id": "a", "name": "hint", "result": {}, "error": None}),
            ]

        def get_state(self, config: object) -> object:
            return type("S", (), {"values": {"reply_text": "Try again"}})()

    clock = iter([10.0, 12.5])
    monkeypatch.setattr(ui.time, "monotonic", lambda: next(clock))
    events = list(ui.send_stream(replace(tutor, graph=Graph()), "ada", 1, "x"))  # type: ignore[arg-type]
    assert ui.StepFinished("hint", ui.PROGRESS_LABELS["hint"], 2.5) in events


def test_a_node_without_a_label_is_logged_by_its_name(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ui, "PROGRESS_LABELS", {"orchestrator": "Deciding…"})
    events = list(ui.send_stream(tutor, "ada", 1, "hi"))
    assert [e.label for e in events if isinstance(e, ui.StepFinished)] == [
        "parse_input",
        "Deciding…",
    ]


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

    view = _send(replace(tutor, graph=Graph()), "ada", 1, "x")  # type: ignore[arg-type]
    assert (view.hint_level, view.reply, view.error) == (2, "Try again", False)


def test_an_empty_reply_is_an_error(tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch) -> None:
    class Graph:
        def stream(self, *args: object, **kwargs: object) -> list[object]:
            return []

        def get_state(self, config: object) -> object:
            return type("S", (), {"values": {}})()

    view = _send(replace(tutor, graph=Graph()), "ada", 1, "x")  # type: ignore[arg-type]
    assert view.error and view.reply == ui.ERROR_REPLY


def test_no_quota_tells_the_student_through_a_real_graph_run(
    tutor: ui.Tutor, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_quota(*args: object, **kwargs: object) -> None:
        raise structured.QuotaExceededError("429")

    monkeypatch.setattr(structured, "call_structured", no_quota)
    events = list(ui.send_stream(tutor, "ada", 1, "x + 1 = 2"))
    assert events[-1] == ui.TurnView(reply=ui.NO_QUOTA_REPLY, error=True)


def test_a_finished_step_carries_its_graph_path_and_details(tutor: ui.Tutor) -> None:
    events = list(ui.send_stream(tutor, "ada", 1, "hi"))
    finished = [e for e in events if isinstance(e, ui.StepFinished)]
    assert [e.path for e in finished] == ["parse_input", "orchestrator"]
    assert "why: greeting" in finished[1].details
    assert not finished[1].failed


def test_a_step_inside_the_diagnosis_gets_its_full_path(tutor: ui.Tutor) -> None:
    namespace = ("diagnosis:abc",)

    class Graph:
        def stream(self, *args: object, **kwargs: object) -> list[tuple[object, str, object]]:
            return [
                (namespace, "tasks", {"id": "a", "name": "verify", "input": {}, "triggers": []}),
                (namespace, "tasks", {"id": "a", "name": "verify", "result": None, "error": "x"}),
            ]

        def get_state(self, config: object) -> object:
            return type("S", (), {"values": {"reply_text": "ok"}})()

    events = list(ui.send_stream(replace(tutor, graph=Graph()), "ada", 1, "x"))  # type: ignore[arg-type]
    assert isinstance(events[0], ui.StepStarted) and events[0].path == "diagnosis:verify"
    assert isinstance(events[1], ui.StepFinished) and events[1].failed


def test_a_reason_for_an_action_code_overruled_is_not_shown(
    tutor: ui.Tutor, canned_llm: Callable[..., None]
) -> None:
    canned_llm(Decision=Decision(action="diagnose", reason="has working"))  # no steps, so `ask`
    events = list(ui.send_stream(tutor, "ada", 1, "hi"))
    orchestrator = next(
        e for e in events if isinstance(e, ui.StepFinished) and e.node == "orchestrator"
    )
    assert "action: ask" in orchestrator.details
    assert not any(line.startswith("why:") for line in orchestrator.details)
