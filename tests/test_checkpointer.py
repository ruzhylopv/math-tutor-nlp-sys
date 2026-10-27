"""State survives between invokes (and between savers on the same file) under a thread_id."""

from pathlib import Path
from typing import Any

import pytest
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from tutor.graph import build_main_graph, new_turn
from tutor.state import Decision, ParsedInput
from tutor.tools import structured
from tutor.tools.checkpointer import sqlite_checkpointer


@pytest.fixture(autouse=True)
def scripted_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(name: str, schema: type[BaseModel], text: str, retries: int = 1) -> Any:
        if schema is ParsedInput:
            return ParsedInput(problem="3(x + 2) = 15")
        return Decision(action="ask", reason="no steps")

    monkeypatch.setattr(structured, "call_structured", fake)


def _config(thread: str) -> RunnableConfig:
    return {"configurable": {"thread_id": thread}}


def test_new_turn_starts_a_run_in_new_message_mode() -> None:
    turn = new_turn("ada", "hello")
    assert turn["stage"] == "new_message"
    assert turn["student_id"] == "ada"
    assert turn["messages"][0].content == "hello"


def test_state_carries_over_to_the_next_message(tmp_path: Path) -> None:
    graph = build_main_graph(sqlite_checkpointer(str(tmp_path / "ck.db")))
    first = graph.invoke(new_turn("ada", "3(x+2)=15, I got 13/3"), _config("t1"))
    second = graph.invoke(new_turn("ada", "ok"), _config("t1"))
    assert first["turns"] == 1
    assert second["turns"] == 2  # turns was restored from the first run
    assert second["problem"] == "3(x + 2) = 15"
    assert len(second["messages"]) == 4  # two student messages, two replies


def test_threads_do_not_share_state(tmp_path: Path) -> None:
    graph = build_main_graph(sqlite_checkpointer(str(tmp_path / "ck.db")))
    graph.invoke(new_turn("ada", "hi"), _config("t1"))
    other = graph.invoke(new_turn("bob", "hi"), _config("t2"))
    assert other["turns"] == 1


def test_state_survives_a_new_saver_on_the_same_file(tmp_path: Path) -> None:
    path = str(tmp_path / "ck.db")
    build_main_graph(sqlite_checkpointer(path)).invoke(new_turn("ada", "hi"), _config("t1"))
    again = build_main_graph(sqlite_checkpointer(path)).invoke(new_turn("ada", "hi"), _config("t1"))
    assert again["turns"] == 2
