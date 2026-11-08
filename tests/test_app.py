"""Smoke test of app.py with Streamlit's AppTest; the tutor is built on an in-memory saver."""

import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import streamlit as st
from streamlit.proto.ChatInput_pb2 import ChatInput
from streamlit.testing.v1 import AppTest

from tutor import ui
from tutor.state import Decision
from tutor.tools.canned_hints import MAX_LEVEL
from tutor.trace import VISITED

APP = Path(__file__).resolve().parent.parent / "app.py"


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, canned_llm: Callable[..., None]) -> AppTest:
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("MODEL_NAME", "m")
    monkeypatch.setenv("CHECKPOINT_DB_PATH", ":memory:")
    monkeypatch.delenv("LEARNER_DB_PATH", raising=False)
    monkeypatch.setattr("tutor.config.load_dotenv", lambda: False)

    canned_llm(Decision=Decision(action="reply", reason="greeting", reply_text="Hello!"))
    return AppTest.from_file(str(APP), default_timeout=30)


def test_name_gate_then_a_message_round_trip(app: AppTest) -> None:
    app.run()
    assert app.chat_input == []  # no chat before a name
    app.text_input[0].set_value("Ada").run()
    app.button[0].click().run()
    app.chat_input[0].set_value("hi").run()
    assert [m.name for m in app.chat_message] == ["user", "assistant"]
    assert not app.exception


def test_new_chat_clears_the_conversation(app: AppTest) -> None:
    app.run()
    app.text_input[0].set_value("Ada").run()
    app.button[0].click().run()
    app.chat_input[0].set_value("hi").run()
    next(b for b in app.sidebar.button if b.label == "New chat").click().run()
    assert app.session_state.chat == 2
    assert list(app.chat_message) == []


def test_missing_setup_shows_a_message(app: AppTest, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODEL_NAME")
    app.run()
    assert any("Setup needed" in e.value for e in app.error)


def test_a_failed_run_keeps_the_message_visible(
    app: AppTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    def failing(*args: object, **kwargs: object) -> Iterator[ui.TurnView]:
        yield ui.TurnView(reply=ui.ERROR_REPLY, error=True)

    monkeypatch.setattr(ui, "send_stream", failing)
    app.run()
    app.text_input[0].set_value("Ada").run()
    app.button[0].click().run()
    app.chat_input[0].set_value("2x = 4").run()
    assert any(ui.ERROR_REPLY in e.value for e in app.error)
    assert any("2x = 4" in str(m.markdown[0].value) for m in app.chat_message)
    assert app.session_state.failed_text == "2x = 4"


def test_the_step_log_stays_after_the_reply(app: AppTest) -> None:
    app.run()
    app.text_input[0].set_value("Ada").run()
    app.button[0].click().run()
    app.chat_input[0].set_value("hi").run()
    (log,) = [e for e in app.expander if e.label.startswith("Done in")]
    lines = [m.value for m in log.markdown]
    assert [line.split(" — ")[0] for line in lines] == [
        "✓ Reading your message",
        "✓ Deciding what to do next",
    ]
    next(b for b in app.sidebar.button if b.label == "New chat").click().run()
    assert not [e for e in app.expander if e.label.startswith("Done in")]


def _start(app: AppTest) -> None:
    app.run()
    app.text_input[0].set_value("Ada").run()
    app.button[0].click().run()


def _panel_text(app: AppTest) -> list[str]:
    return [t.value for t in app.text]


def test_the_panel_lists_nodes_and_timings_for_everyone(app: AppTest) -> None:
    _start(app)
    app.chat_input[0].set_value("hi").run()
    lines = _panel_text(app)
    assert [line.split(" · ")[0] for line in lines] == ["✓ parse_input", "✓ orchestrator"]
    assert all(re.fullmatch(r"\d+\.\ds", line.split(" · ")[1]) for line in lines)
    assert not app.exception


def test_what_a_node_decided_needs_the_developer_view(app: AppTest) -> None:
    _start(app)
    app.chat_input[0].set_value("hi").run()
    assert not any("why: greeting" in line for line in _panel_text(app))
    next(t for t in app.sidebar.toggle if t.label == "Developer view").set_value(True).run()
    assert any("why: greeting" in line for line in _panel_text(app))


def test_a_new_chat_clears_the_panel(app: AppTest) -> None:
    _start(app)
    app.chat_input[0].set_value("hi").run()
    next(b for b in app.sidebar.button if b.label == "New chat").click().run()
    assert _panel_text(app) == []


def _sidebar_text(app: AppTest) -> list[str]:
    return [m.value for m in app.sidebar.markdown]


def test_the_sidebar_counters_are_normal_text_and_show_the_cap(app: AppTest) -> None:
    _start(app)
    assert len(app.sidebar.metric) == 0
    assert f"Hint level: **none yet (max {MAX_LEVEL})**" in _sidebar_text(app)
    assert "Hints used: **0**" in _sidebar_text(app)


def test_the_sidebar_shows_the_current_level_out_of_the_cap(
    app: AppTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    info = ui.SidebarInfo(hint_level=2, hints_used=3, profile=None)
    monkeypatch.setattr(ui, "sidebar_info", lambda *args: info)
    _start(app)
    assert f"Hint level: **2 / {MAX_LEVEL}**" in _sidebar_text(app)
    assert "Hints used: **3**" in _sidebar_text(app)


def _scripted_turn(*args: object, **kwargs: object) -> Iterator[object]:
    yield ui.StepStarted("parse_input", "Reading…", "parse_input")
    yield ui.StepFinished("parse_input", "Reading…", 1.2, "parse_input")
    yield ui.StepStarted("diagnosis", "Diagnosing…", "diagnosis")
    yield ui.StepStarted("verify", "Checking…", "diagnosis:verify")
    yield ui.StepFinished("verify", "Checking…", 0.5, "diagnosis:verify", failed=True)
    yield ui.StepFinished("diagnosis", "Diagnosing…", 0.6, "diagnosis", failed=True)
    yield ui.TurnView(reply=ui.ERROR_REPLY, error=True)


def test_the_panel_marks_a_failed_step_and_skips_the_diagnosis_wrapper(
    app: AppTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ui, "send_stream", _scripted_turn)
    _start(app)
    app.chat_input[0].set_value("2x = 4").run()
    assert _panel_text(app) == ["✓ parse_input · 1.2s", "✗ diagnosis:verify · 0.5s"]
    (log,) = [e for e in app.expander if e.label.startswith("Failed after")]
    assert [m.value for m in log.markdown] == [
        "✓ Reading — 1.2s",
        "✗ Checking — 0.5s",
        "✗ Diagnosing — 0.6s",
    ]


def test_the_graph_is_drawn_and_marks_the_nodes_a_turn_visited(app: AppTest) -> None:
    _start(app)
    assert f'fillcolor="{VISITED}"' not in app.get("graphviz_chart")[0].proto.spec
    app.chat_input[0].set_value("hi").run()
    spec = app.get("graphviz_chart")[0].proto.spec
    assert '"hint" [label="hint"' in spec
    assert f'"parse_input" [label="parse_input" fillcolor="{VISITED}"' in spec


def test_the_input_is_off_while_a_turn_runs(app: AppTest) -> None:
    _start(app)
    assert app.chat_input[0].proto.submit_mode == ChatInput.SubmitMode.SUBMIT_MODE_DISABLE


def test_sending_clears_the_previous_turns_log_before_the_new_turn(
    app: AppTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    left_over: list[bool] = []

    def recording(*args: object, **kwargs: object) -> Iterator[ui.TurnView]:
        left_over.append("trace" in st.session_state or "step_log" in st.session_state)
        yield ui.TurnView(reply="Hello!")

    _start(app)
    app.chat_input[0].set_value("hi").run()
    assert "trace" in app.session_state and "step_log" in app.session_state
    monkeypatch.setattr(ui, "send_stream", recording)
    app.chat_input[0].set_value("hi again").run()
    assert left_over == [False]


def _user_messages(app: AppTest) -> list[str]:
    return [str(m.markdown[0].value) for m in app.chat_message if m.name == "user"]


def test_a_message_keeps_its_lines_in_the_history(app: AppTest) -> None:
    _start(app)
    app.chat_input[0].set_value("2x = 4\nx = 2").run()
    assert _user_messages(app)[-1] == "2x = 4  \nx = 2"


def test_a_failed_message_keeps_its_lines(app: AppTest, monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(*args: object, **kwargs: object) -> Iterator[ui.TurnView]:
        yield ui.TurnView(reply=ui.ERROR_REPLY, error=True)

    monkeypatch.setattr(ui, "send_stream", failing)
    _start(app)
    app.chat_input[0].set_value("2x = 4\nx = 2").run()
    assert _user_messages(app)[-1] == "2x = 4  \nx = 2"
