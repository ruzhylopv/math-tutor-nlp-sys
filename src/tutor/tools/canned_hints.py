"""One fixed, answer-free hint per level, for when a generated hint leaks twice (used by M6).

They use no numbers and no math of the student's, so they cannot leak. Levels follow
docs/architecture.md: 1 a question, 2 try a number, 3 name the idea, 4 the most direct.
"""

MAX_LEVEL = 4

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


def canned_hint(level: int) -> str:
    """The fixed hint for a level; a level outside 1-4 is clamped."""
    return _HINTS[min(max(level, 1), MAX_LEVEL)]
