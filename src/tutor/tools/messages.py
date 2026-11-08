"""Read the student's and the tutor's latest messages from the conversation."""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from tutor.state import TutorState

MAX_HISTORY_MESSAGES = 20  # enough for a normal session; keeps the prompt's cost bounded


def _text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content.strip()
    parts = (part if isinstance(part, str) else str(part.get("text", "")) for part in content)
    return " ".join(part for part in parts if part).strip()


def conversation_text(state: TutorState) -> str:
    """The chat before the latest student message, oldest first; an empty string if there is none.

    Only the last `MAX_HISTORY_MESSAGES` messages are kept, one `Student:` or `Tutor:` line each.
    """
    messages = state.get("messages", [])
    latest = next(
        (i for i in reversed(range(len(messages))) if isinstance(messages[i], HumanMessage)), 0
    )
    lines = [
        f"{'Student' if isinstance(message, HumanMessage) else 'Tutor'}: {_text(message)}"
        for message in messages[:latest]
        if isinstance(message, HumanMessage | AIMessage)
    ]
    return "\n".join(lines[-MAX_HISTORY_MESSAGES:])


def latest_student_message(state: TutorState) -> str:
    """The text of the latest student message, or an empty string."""
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            return _text(message)
    return ""


def last_tutor_message(state: TutorState) -> str:
    """The tutor's message before the latest student message, or an empty string."""
    seen_student = False
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage):
            if seen_student:
                return ""  # two student messages in a row: the tutor has not answered
            seen_student = True
        elif isinstance(message, AIMessage) and seen_student:
            return _text(message)
    return ""
