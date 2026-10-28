"""Streamlit chat for the math tutor. Run: `uv run streamlit run app.py`."""

import logging

import streamlit as st

from tutor.config import ConfigError, load_config
from tutor.ui import (
    Progress,
    TurnView,
    Tutor,
    build_tutor,
    latest_chat,
    load_history,
    next_chat,
    normalise_name,
    send_stream,
    sidebar_info,
)

logging.basicConfig(level=logging.INFO)


@st.cache_resource
def get_tutor() -> Tutor:
    return build_tutor()


def show_sidebar(tutor: Tutor, student_id: str, chat: int) -> bool:
    """Name, new-chat button, hint counters and the learner profile. Returns the debug toggle."""
    with st.sidebar:
        st.markdown(f"**{student_id}** · chat {chat}")
        if st.button("New chat"):
            st.session_state.chat = next_chat(tutor, student_id)
            st.session_state.pop("last_turn", None)
            st.rerun()
        if st.button("Switch name"):
            for key in ("student_id", "chat", "last_turn", "failed_text"):
                st.session_state.pop(key, None)
            st.rerun()
        info = sidebar_info(tutor, student_id, chat)
        st.metric("Hint level", info.hint_level if info.hint_level else "none yet")
        st.metric("Hints used", info.hints_used)
        if info.profile is not None:
            st.markdown("**Profile**")
            topics = ", ".join(info.profile.weak_topics) or "nothing recorded yet"
            st.caption(f"Weak topics: {topics}")
            for mid, count in info.profile.misconception_counts.items():
                st.caption(f"{mid}: seen {count}×")
        return st.toggle("Show visited nodes")


def run_turn(tutor: Tutor, student_id: str, chat: int, text: str) -> TurnView:
    """Send one message, showing what the tutor is doing while it works."""
    view: TurnView | None = None
    with st.chat_message("assistant"):
        with st.status("Thinking…") as status:
            for event in send_stream(tutor, student_id, chat, text):
                if isinstance(event, Progress):
                    status.update(label=event.text)
                else:
                    view = event
            assert view is not None  # the stream always ends with a TurnView
            status.update(
                label="Failed" if view.error else "Done",
                state="error" if view.error else "complete",
            )
        st.write(view.reply)
    return view


def main() -> None:
    st.set_page_config(page_title="Math tutor", page_icon="➕")
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
    debug = show_sidebar(tutor, student_id, chat)

    for role, text in load_history(tutor, student_id, chat):
        with st.chat_message(role):
            st.write(text)
    last: TurnView | None = st.session_state.get("last_turn")
    if last is not None and last.error:  # a failed run is not in the checkpoint
        if failed := st.session_state.get("failed_text"):
            with st.chat_message("user"):
                st.write(failed)
        st.error(last.reply)
    if debug and last is not None:
        st.caption("Visited: " + " → ".join(last.visited))

    if text := st.chat_input("Paste a problem and your steps, or ask a question"):
        with st.chat_message("user"):
            st.write(text)
        view = run_turn(tutor, student_id, chat, text)
        st.session_state.failed_text = text if view.error else None
        st.session_state.last_turn = view
        st.rerun()


main()
