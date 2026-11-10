"""What the Streamlit app needs from the tutor: send a message, reload a chat, read the sidebar.

Kept apart from `app.py` so it can be tested without Streamlit. One chat is one checkpointer
thread, `<student_id>|<number>`; the chat history shown is the checkpointed `messages`, not a
second copy. The learner profile is read only (`get_profile`); starting a new chat never touches it.
"""

import logging
import re
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import StateSnapshot

from tutor.config import ConfigError, checkpoint_db_path
from tutor.graph import build_main_graph, new_turn
from tutor.state import LearnerProfile, TutorState
from tutor.tools.canned_hints import MAX_LEVEL
from tutor.tools.checkpointer import sqlite_checkpointer
from tutor.tools.learner_db import get_profile, learner_db_path
from tutor.tools.structured import QuotaExceededError
from tutor.trace import node_details, node_path

logger = logging.getLogger(__name__)

ERROR_REPLY = "Sorry, something went wrong on my side. Please send your message again."
NO_QUOTA_REPLY = "Sorry, the tutor has no model quota left right now. Please try again later."

# What the student sees while a node runs. A node missing here (one added later) is shown by its
# own name, so every step still gets a line in the log.
PROGRESS_LABELS = {
    "parse_input": "Reading your message…",
    "orchestrator": "Deciding what to do next…",
    "diagnosis": "Diagnosing your solution…",
    "verify": "Checking your steps…",
    "localize": "Finding the first wrong step…",
    "retrieve": "Looking for the likely misconception…",
    "hint": "Writing a hint…",
}


def step_label(node: str) -> str:
    return PROGRESS_LABELS.get(node, node)


@dataclass(frozen=True)
class StepStarted:
    """A node has started; `label` is what to show while it runs."""

    node: str
    label: str
    path: str = field(default="", compare=False)  # the node's id in the drawn graph


@dataclass(frozen=True)
class StepFinished:
    """A node has finished after `seconds` (wall clock, measured in the UI layer)."""

    node: str
    label: str
    seconds: float
    path: str = field(default="", compare=False)
    details: tuple[str, ...] = field(default=(), compare=False)  # for the developer view only
    failed: bool = field(default=False, compare=False)


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
    max_hint_level: int = MAX_LEVEL


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


def hard_line_breaks(text: str) -> str:
    """The student's text with every newline kept: Markdown otherwise joins single newlines."""
    return text.replace("\r\n", "\n").replace("\n", "  \n")


# Display-only LaTeX for the tutor's replies. The hint prompt puts math in backticks as plain text
# (`x^2 + 5x = 6`); the leakage check and the next prompts read that form, so it is converted only
# here, as text: no SymPy round-trip, which would reorder or evaluate what the tutor quoted.
_FRAGMENT = re.compile(r"`([^`\n]+)`")
_MATH_CHARS = re.compile(r"[A-Za-z0-9\s+\-*/^=<>!().,|]+")
_TOKEN = re.compile(r"\s+|\d+(?:\.\d+)?|[A-Za-z]+|\+-|<=|>=|!=|.")
_FUNCTIONS = {"sqrt", "abs"}
_WORDS = {"or", "and"}
_SYMBOLS = {"*": r"\cdot ", "+-": r"\pm ", "<=": r"\le ", ">=": r"\ge ", "!=": r"\ne "}

# A parsed fragment: a token ("tok", text), a bracketed group ("group", nodes), a function call
# ("func", name, nodes), a power ("pow", base, exponent) or a fraction ("frac", a, b).
_Node = tuple[Any, ...]


class _NotMath(Exception):
    """The fragment is not plain math this converter can render; it stays in backticks."""


def _parse(tokens: list[str], start: int, closing: bool) -> tuple[list[_Node], int]:
    """Nodes up to the matching ")" (when `closing`) or the end, and the index after them."""
    nodes: list[_Node] = []
    i = start
    while i < len(tokens):
        token = tokens[i]
        if token == ")":
            if not closing:
                raise _NotMath
            return _operators(nodes), i + 1
        if token == "(":
            inner, i = _parse(tokens, i + 1, closing=True)
            if nodes and nodes[-1][0] == "tok" and nodes[-1][1] in _FUNCTIONS:
                nodes[-1] = ("func", nodes[-1][1], inner)
            else:
                nodes.append(("group", inner))
            continue
        if token.isalpha() and len(token) > 2 and token not in _FUNCTIONS:
            raise _NotMath  # a word, not a product of letters
        nodes.append(("tok", token))
        i += 1
    if closing:
        raise _NotMath
    return _operators(nodes), i


def _operators(nodes: list[_Node]) -> list[_Node]:
    """Attach each `^` to its base and exponent, then each `/` to its two operands."""
    for symbol, kind in (("^", "pow"), ("/", "frac")):
        out: list[_Node] = []
        i = 0
        while i < len(nodes):
            if nodes[i] != ("tok", symbol):
                out.append(nodes[i])
                i += 1
                continue
            if not out or i + 1 >= len(nodes):
                raise _NotMath
            operand, i = nodes[i + 1], i + 2
            if symbol == "^" and operand == ("tok", "-") and i < len(nodes):
                operand, i = ("group", [operand, nodes[i]]), i + 1  # a negative exponent
            if operand[0] == "tok" and not operand[1][0].isalnum():  # an operator, not an operand
                raise _NotMath
            out[-1] = (kind, out[-1], operand)
        nodes = out
    return nodes


def _latex(nodes: list[_Node]) -> str:
    return "".join(_node_latex(node) for node in nodes)


def _bare(node: _Node) -> str:
    """A node without its outer parentheses: they are not needed inside braces."""
    return _latex(node[1]) if node[0] == "group" else _node_latex(node)


def _node_latex(node: _Node) -> str:
    kind = node[0]
    if kind == "group":
        return rf"\left({_latex(node[1])}\right)"
    if kind == "func":
        inner = _latex(node[2])
        return rf"\sqrt{{{inner}}}" if node[1] == "sqrt" else rf"\left|{inner}\right|"
    if kind == "pow":
        return rf"{_node_latex(node[1])}^{{{_bare(node[2])}}}"
    if kind == "frac":
        return rf"\frac{{{_bare(node[1])}}}{{{_bare(node[2])}}}"
    token: str = node[1]
    if token in _FUNCTIONS:
        raise _NotMath  # "sqrt" without its brackets
    if token in _WORDS:
        return rf"\text{{ {token} }}"
    return _SYMBOLS.get(token, token)


def _fragment_latex(fragment: str) -> str | None:
    """The fragment as LaTeX, or None when it is not plain math."""
    if not _MATH_CHARS.fullmatch(fragment):
        return None
    try:
        tokens = [token for token in _TOKEN.findall(fragment) if not token.isspace()]
        return _latex(_parse(tokens, 0, closing=False)[0])
    except _NotMath:
        return None


def render_math(text: str) -> str:
    """A tutor reply for Markdown: backtick math becomes `$...$`, and a `$` in the prose is escaped.

    A fragment that is not plain math (a word, unicode, unbalanced brackets) keeps its backticks.
    """
    out: list[str] = []
    last = 0
    for match in _FRAGMENT.finditer(text):
        out.append(text[last : match.start()].replace("$", r"\$"))
        latex = _fragment_latex(match.group(1))
        out.append(match.group(0) if latex is None else f"${latex}$")
        last = match.end()
    out.append(text[last:].replace("$", r"\$"))
    return "".join(out)


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


def _undo_run(tutor: Tutor, config: RunnableConfig, before: StateSnapshot) -> None:
    """Put a chat back as it was before a run that failed, so the failed turn leaves no trace.

    A copy of the earlier checkpoint becomes the newest one; a first message has no earlier
    checkpoint, so the thread is emptied. If this fails too, the failure is only logged.
    """
    try:
        if before.metadata is None:  # nothing was saved before this run
            tutor.saver.delete_thread(config["configurable"]["thread_id"])
        else:
            tutor.graph.update_state(before.config or config, None, as_node="__copy__")
    except Exception:
        logger.exception("ui: could not undo the failed run")


def send_stream(
    tutor: Tutor, student_id: str, chat: int, text: str
) -> Iterator[StepStarted | StepFinished | TurnView]:
    """One student message is one run of the graph: a `StepStarted` and a `StepFinished` per node
    run (a node that runs twice is logged twice), then one `TurnView`.

    A failure ends the stream with a friendly `TurnView` (error=True) instead of raising. A run
    stopped by a 429 is undone, so a retry does not raise the hint level or store the message twice.
    """
    config = _config(student_id, chat)
    visited: list[str] = []
    started: dict[str, float] = {}  # task id -> start time
    try:
        before = tutor.graph.get_state(config)
        # with several modes and subgraphs each chunk is (namespace, mode, data); the stub types
        # do not say so
        chunks: Iterator[Any] = tutor.graph.stream(
            new_turn(student_id, text),
            config,
            stream_mode=["tasks", "updates"],
            subgraphs=True,
        )
        for namespace, mode, data in chunks:
            if mode == "updates":
                visited.extend(data)
                continue
            node, label = data["name"], step_label(data["name"])
            path = node_path(namespace, node)
            if "result" not in data and "error" not in data:  # a node starts
                started[data["id"]] = time.monotonic()
                yield StepStarted(node, label, path)
            elif data["id"] in started:  # the same task has finished
                seconds = time.monotonic() - started.pop(data["id"])
                logger.info("ui: %s took %.2fs", node, seconds)
                details = node_details(node, data.get("result") or {})
                yield StepFinished(
                    node, label, seconds, path, details, data.get("error") is not None
                )
        state = tutor.graph.get_state(config).values
    except QuotaExceededError:
        logger.warning("ui: the model provider has no quota left")
        _undo_run(tutor, config, before)
        yield TurnView(reply=NO_QUOTA_REPLY, error=True)
        return
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
