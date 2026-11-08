"""Streamlit chat for the math tutor. Run: `uv run streamlit run app.py`."""

import logging
import time
from dataclasses import dataclass

import streamlit as st
from langchain_core.runnables.graph import Graph
from streamlit.delta_generator import DeltaGenerator

from tutor.config import ConfigError, load_config
from tutor.panel import mount_graph, push_update
from tutor.trace import Trace, panel_view
from tutor.ui import (
    StepFinished,
    StepStarted,
    TurnView,
    Tutor,
    build_tutor,
    hard_line_breaks,
    latest_chat,
    load_history,
    next_chat,
    normalise_name,
    send_stream,
    sidebar_info,
)

logging.basicConfig(level=logging.INFO)

# The panel is fixed on the right of a wide window; on a narrow one it stays in the page flow. It
# goes above the pinned chat bar (z-index 99, full width), which otherwise swallows the wheel over
# the bottom of the panel and hides the last lines of the log.
PANEL_CSS = """
<style>
.st-key-trace_updates { display: none; }
@media (min-width: 1000px) {
  .st-key-trace_panel {
    position: fixed;
    top: 3.75rem;
    right: 0;
    z-index: 100;
    width: 380px;
    height: calc(100vh - 3.75rem);
    overflow-y: auto;
    padding: 1rem;
    border-left: 1px solid rgba(128, 128, 128, 0.3);
  }
  [data-testid="stMainBlockContainer"],
  [data-testid="stBottomBlockContainer"] {
    padding-right: 420px;
    max-width: none;
  }
}
</style>
"""


@dataclass(frozen=True)
class Panel:
    """The slots that are redrawn while a turn runs, and the graph drawn from them."""

    graph: Graph
    updates: DeltaGenerator
    log: DeltaGenerator


@st.cache_resource
def get_tutor() -> Tutor:
    return build_tutor()


def show_sidebar(tutor: Tutor, student_id: str, chat: int) -> None:
    """Name, new-chat button, hint counters, learner profile."""
    with st.sidebar:
        st.markdown(f"**{student_id}** · chat {chat}")
        if st.button("New chat"):
            st.session_state.chat = next_chat(tutor, student_id)
            st.session_state.pop("last_turn", None)
            st.session_state.pop("step_log", None)
            st.session_state.pop("trace", None)
            st.rerun()
        if st.button("Switch name"):
            for key in ("student_id", "chat", "last_turn", "failed_text", "step_log", "trace"):
                st.session_state.pop(key, None)
            st.rerun()
        info = sidebar_info(tutor, student_id, chat)
        cap = info.max_hint_level
        level = f"{info.hint_level} / {cap}" if info.hint_level else f"none yet (max {cap})"
        st.markdown(f"Hint level: **{level}**")
        st.markdown(f"Hints used: **{info.hints_used}**")
        if info.profile is not None:
            st.markdown("**Profile**")
            topics = ", ".join(info.profile.weak_topics) or "nothing recorded yet"
            st.caption(f"Weak topics: {topics}")
            for mid, count in info.profile.misconception_counts.items():
                st.caption(f"{mid}: seen {count}×")


def clear_last_turn_log() -> None:
    """Runs on send, before the script: the previous turn's log must not stay on screen."""
    st.session_state.pop("step_log", None)
    st.session_state.pop("trace", None)


def show_step_log(lines: list[str], summary: str) -> None:
    with st.expander(summary):
        for line in lines:
            st.write(line)


def draw_log(panel: Panel, steps: list[StepFinished]) -> None:
    with panel.log.container():
        for step in steps:
            if step.path not in panel.graph.nodes:  # the `diagnosis` wrapper: its steps are listed
                continue
            st.text(f"{'✗' if step.failed else '✓'} {step.path} · {step.seconds:.1f}s")
            if step.details:  # a code block is literal: model text is not Markdown
                st.code("\n".join(step.details), language=None, wrap_lines=True)


def draw_panel(panel: Panel, trace: Trace, steps: list[StepFinished]) -> None:
    """Send the new progress to the graph that is already on the page, and redraw the log."""
    with panel.updates:
        push_update(panel_view(panel.graph, trace, steps))
    draw_log(panel, steps)


def open_panel(tutor: Tutor) -> Panel:
    """Create the right-hand panel, showing the last turn if there is one."""
    st.html(PANEL_CSS)
    graph = tutor.graph.get_graph(xray=True)
    trace, steps = st.session_state.get("trace", (Trace(), []))
    with st.container(key="trace_panel"):
        st.markdown("**How the tutor works**")
        mount_graph(panel_view(graph, trace, steps))
        panel = Panel(graph, st.container(key="trace_updates").empty(), st.empty())
    draw_log(panel, steps)
    return panel


def run_turn(tutor: Tutor, student_id: str, chat: int, text: str, panel: Panel) -> TurnView:
    """Send one message; the status shows the running step and logs each finished one with its time.

    The log and the trace are kept in `session_state` so they stay visible after the rerun.
    """
    view: TurnView | None = None
    lines: list[str] = []
    trace = Trace()
    steps: list[StepFinished] = []
    start = time.monotonic()
    with st.chat_message("assistant"):
        with st.status("Thinking…", expanded=True) as status:
            for event in send_stream(tutor, student_id, chat, text):
                if isinstance(event, StepStarted):
                    status.update(label=event.label)
                    trace = trace.start(event.path)
                elif isinstance(event, StepFinished):
                    mark = "✗" if event.failed else "✓"
                    lines.append(f"{mark} {event.label.rstrip('…')} — {event.seconds:.1f}s")
                    st.write(lines[-1])
                    trace = trace.finish(event.path, event.failed)
                    steps.append(event)
                else:
                    view = event
                    trace = trace.end(view.error)
                draw_panel(panel, trace, steps)
            assert view is not None  # the stream always ends with a TurnView
            total = time.monotonic() - start
            summary = f"Failed after {total:.1f}s" if view.error else f"Done in {total:.1f}s"
            status.update(label=summary, state="error" if view.error else "complete")
        st.write(view.reply)
    st.session_state.step_log = (lines, summary)
    st.session_state.trace = (trace, steps)
    return view


def main() -> None:
    st.set_page_config(page_title="Math tutor", page_icon="➕", layout="wide")
    st.title("Math tutor")
    try:
        load_config()
        tutor = get_tutor()
    except ConfigError as error:
        st.error(f"Setup needed: {error}")
        return

    if "student_id" not in st.session_state:
        name = st.text_input("Your name (it only tells your chats apart; there is no password)")
        if st.button("Start") and normalise_name(name):
            student_id = normalise_name(name)
            st.session_state.student_id = student_id
            st.session_state.chat = latest_chat(tutor, student_id)
            st.rerun()
        return

    student_id: str = st.session_state.student_id
    chat: int = st.session_state.chat
    show_sidebar(tutor, student_id, chat)

    for role, text in load_history(tutor, student_id, chat):
        with st.chat_message(role):
            st.write(hard_line_breaks(text) if role == "user" else text)
    last: TurnView | None = st.session_state.get("last_turn")
    if last is not None and last.error:  # a failed run is not in the checkpoint
        if failed := st.session_state.get("failed_text"):
            with st.chat_message("user"):
                st.write(hard_line_breaks(failed))
        st.error(last.reply)
    if step_log := st.session_state.get("step_log"):
        show_step_log(*step_log)
    panel = open_panel(tutor)

    # A message sent during a turn would rerun the script and abort the turn, so the input is off.
    if text := st.chat_input(
        "Paste a problem and your steps, or ask a question (Shift+Enter for a new line)",
        submit_mode="disable",
        on_submit=clear_last_turn_log,
    ):
        with st.chat_message("user"):
            st.write(hard_line_breaks(text))
        view = run_turn(tutor, student_id, chat, text, panel)
        st.session_state.failed_text = text if view.error else None
        st.session_state.last_turn = view
        st.rerun()


main()
