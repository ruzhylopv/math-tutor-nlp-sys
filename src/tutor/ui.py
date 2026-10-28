"""What the Streamlit app needs from the tutor: send a message, reload a chat, read the sidebar.

Kept apart from `app.py` so it can be tested without Streamlit. One chat is one checkpointer
thread, `<student_id>|<number>`; the chat history shown is the checkpointed `messages`, not a
second copy. The learner profile is read only (`get_profile`); starting a new chat never touches it.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph

from tutor.config import ConfigError, checkpoint_db_path
from tutor.graph import build_main_graph, new_turn
from tutor.state import LearnerProfile, TutorState
from tutor.tools.checkpointer import sqlite_checkpointer
from tutor.tools.learner_db import get_profile, learner_db_path

logger = logging.getLogger(__name__)

ERROR_REPLY = "Sorry, something went wrong on my side. Please send your message again."

# What the student sees while a node runs. A node missing here (a subgraph's inner nodes, or one
# added later) simply shows no new label.
PROGRESS_LABELS = {
    "parse_input": "Reading your message…",
    "orchestrator": "Deciding what to do next…",
    "verify": "Checking your steps…",
    "localize": "Finding the first wrong step…",
    "retrieve": "Looking for the likely misconception…",
    "hint": "Writing a hint…",
}


@dataclass(frozen=True)
class Progress:
    """A node has started; `text` is what to show while it runs."""

    text: str


@dataclass(frozen=True)
class TurnView:
    """The result of one student message, as the UI shows it."""

    reply: str
    hint_level: int | None = None  # only when a hint was published this turn
    visited: list[str] = field(default_factory=list)
    error: bool = False


@dataclass(frozen=True)
class SidebarInfo:
    hint_level: int | None
    hints_used: int
    profile: LearnerProfile | None  # None when no learner DB is configured


@dataclass(frozen=True)
class Tutor:
    graph: CompiledStateGraph[TutorState, None, TutorState, TutorState]
    saver: SqliteSaver


def build_tutor(path: str | None = None) -> Tutor:
    """The main graph on a SQLite checkpointer (the file's folder is created if missing)."""
    path = path or checkpoint_db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    saver = sqlite_checkpointer(path)
    return Tutor(graph=build_main_graph(saver), saver=saver)


def normalise_name(name: str) -> str:
    return " ".join(name.split())


def thread_id(student_id: str, chat: int) -> str:
    return f"{student_id}|{chat}"


def _config(student_id: str, chat: int) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id(student_id, chat)}}


def _saved_chats(tutor: Tutor, student_id: str) -> list[int]:
    """Chat numbers saved for this name, newest checkpoint first (with repeats)."""
    numbers: list[int] = []
    for saved in tutor.saver.list(None):
        owner, _, number = saved.config["configurable"]["thread_id"].rpartition("|")
        if owner == student_id and number.isdigit():
            numbers.append(int(number))
    return numbers


def latest_chat(tutor: Tutor, student_id: str) -> int:
    """The chat saved most recently for this name, or 1 for a name with no chat yet."""
    return next(iter(_saved_chats(tutor, student_id)), 1)


def next_chat(tutor: Tutor, student_id: str) -> int:
    """A fresh chat number: one above the highest saved for this name."""
    return max(_saved_chats(tutor, student_id), default=0) + 1


def load_history(tutor: Tutor, student_id: str, chat: int) -> list[tuple[str, str]]:
    """The chat so far as (role, text) pairs, role "user" or "assistant"."""
    values = tutor.graph.get_state(_config(student_id, chat)).values
    history: list[tuple[str, str]] = []
    for message in values.get("messages", []):
        if isinstance(message, HumanMessage):
            history.append(("user", str(message.content)))
        elif isinstance(message, AIMessage):
            history.append(("assistant", str(message.content)))
    return history


def send_stream(
    tutor: Tutor, student_id: str, chat: int, text: str
) -> Iterator[Progress | TurnView]:
    """One student message is one run of the graph: `Progress` events, then one `TurnView`.

    A failure ends the stream with a friendly `TurnView` (error=True) instead of raising.
    """
    config = _config(student_id, chat)
    visited: list[str] = []
    shown = ""
    try:
        # with several modes and subgraphs each chunk is (namespace, mode, data); the stub types
        # do not say so
        chunks: Iterator[Any] = tutor.graph.stream(
            new_turn(student_id, text),
            config,
            stream_mode=["tasks", "updates"],
            subgraphs=True,
        )
        for _, mode, data in chunks:
            if mode == "updates":
                visited.extend(data)
            elif "result" not in data and "error" not in data:  # a node starts
                label = PROGRESS_LABELS.get(data["name"])
                if label and label != shown:
                    shown = label
                    yield Progress(label)
        state = tutor.graph.get_state(config).values
    except Exception:  # the UI must survive a model, network or config failure
        logger.exception("ui: the graph run failed")
        yield TurnView(reply=ERROR_REPLY, error=True)
        return
    reply = state.get("reply_text") or ERROR_REPLY
    published = "hint" in visited and bool(state.get("reply_text"))
    yield TurnView(
        reply=reply,
        hint_level=state.get("hint_level") if published else None,
        visited=visited,
        error=not state.get("reply_text"),
    )


def send(tutor: Tutor, student_id: str, chat: int, text: str) -> TurnView:
    """`send_stream` without the progress: the final `TurnView`."""
    *_, view = send_stream(tutor, student_id, chat, text)
    assert isinstance(view, TurnView)  # the stream always ends with one
    return view


def sidebar_info(tutor: Tutor, student_id: str, chat: int) -> SidebarInfo:
    """Hint level and hints used for this chat, and the person's profile across all chats."""
    values = tutor.graph.get_state(_config(student_id, chat)).values
    try:
        profile: LearnerProfile | None = get_profile(learner_db_path(), student_id)
    except ConfigError:
        profile = None
    return SidebarInfo(
        hint_level=values.get("hint_level"),
        hints_used=values.get("hints_used", 0),
        profile=profile,
    )
