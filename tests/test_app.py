"""Smoke test of app.py with Streamlit's AppTest; the tutor is built on an in-memory saver."""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tutor import ui
from tutor.state import Decision

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
