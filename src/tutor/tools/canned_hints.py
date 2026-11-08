"""One fixed, answer-free hint per level, for when a generated hint leaks twice (used by M6).

They use no numbers and no math of the student's, so they cannot leak. Levels follow
docs/architecture.md: 1 a question, 2 try a number, 3 name the idea, 4 the most direct. A solution
that stopped before an answer has nothing wrong in it, so it gets one text that suggests no mistake.
A student with no working yet has no line to look at, so they get their own text.
"""

MAX_LEVEL = 4
NO_WORKING = "no_working"  # the kind for a student who has not written any working yet

_HINTS = {
    1: "Look again at the step where your work changed. What rule did you use to get from the "
    "line before to the line you wrote?",
    2: "Pick a small whole number for the variable and put it into the line before and into your "
    "line. Do both lines give the same result?",
    3: "The line you wrote does not follow from the line before it. Think about which rule you "
    "applied there, and whether that rule works for every number.",
    4: "Go back to the step where the two lines stop agreeing. Redo just that step slowly, one "
    "piece at a time, and compare it with what you wrote.",
}

_STOPPED_HINT = (
    "Your work so far is correct, but you have not reached the final answer yet. "
    "What would you do next, starting from your last line?"
)


_NO_WORKING_HINT = (
    "That is a fine place to start from. What is the problem asking you to find, "
    "and what is one small thing you could try first?"
)


def canned_hint(level: int, error_type: str | None = None) -> str:
    """The fixed hint for a level; a level outside 1-4 is clamped.

    `incomplete` and `NO_WORKING` each have their own text.
    """
    if error_type == "incomplete":
        return _STOPPED_HINT
    if error_type == NO_WORKING:
        return _NO_WORKING_HINT
    return _HINTS[min(max(level, 1), MAX_LEVEL)]
