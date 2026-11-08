"""The conversation text that the orchestrator and hint read."""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from tutor.state import TutorState
from tutor.tools.messages import MAX_HISTORY_MESSAGES, conversation_text


def _state(*messages: BaseMessage) -> TutorState:
    return {"messages": list(messages)}


def test_the_conversation_stops_before_the_latest_student_message() -> None:
    state = _state(HumanMessage("Hi"), AIMessage("Hello!"), HumanMessage("I am stuck"))
    assert conversation_text(state) == "Student: Hi\nTutor: Hello!"


def test_a_first_message_has_no_conversation() -> None:
    assert conversation_text(_state(HumanMessage("Hi"))) == ""
    assert conversation_text({}) == ""


def test_other_message_types_are_left_out() -> None:
    state = _state(SystemMessage("rules"), HumanMessage("Hi"), HumanMessage("again"))
    assert conversation_text(state) == "Student: Hi"


def test_only_the_most_recent_messages_are_kept() -> None:
    older = [HumanMessage(f"m{i}") for i in range(MAX_HISTORY_MESSAGES + 5)]
    lines = conversation_text(_state(*older, HumanMessage("latest"))).splitlines()
    assert len(lines) == MAX_HISTORY_MESSAGES
    assert lines[0] == "Student: m5" and lines[-1] == f"Student: m{MAX_HISTORY_MESSAGES + 4}"
