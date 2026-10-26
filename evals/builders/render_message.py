"""Render a known problem and known steps as a messy student message.

The labels of the `parse_input` dataset come from this direction: the steps are known first (mined
from MATH solutions, or corrupted on purpose), then written down in a layout and a notation the
parser has to undo. Math in plain text uses what `tutor.tools.algebra` parses: `^`, `*`, `/`,
`sqrt(...)`, `(a)/(b)` for fractions.

Layouts: plain lines, numbered lines, connector words between lines, everything on one line.
Notations: ascii, latex, unicode, spoken. Extras: a chatty frame and typos in the words (never in
the math).
"""

import random
import re

LAYOUTS = ("plain", "numbered", "connectors", "one_line")
NOTATIONS = ("ascii", "latex", "unicode", "spoken")

_CONNECTORS = ("so", "then", "which gives", "therefore", "now")
_OPENERS = (
    "hi! i tried this:",
    "hello, here is my work",
    "ok so",
    "my attempt:",
    "hey, can you check",
)
_CLOSERS = ("is it right?", "did i do it correctly?", "thanks!", "where did i go wrong?")
_SOLVE_WORDS = ("Solve", "solve", "I need to solve", "Problem:", "help me with")
_SIMPLIFY_WORDS = ("Simplify", "simplify", "I need to simplify", "Problem: simplify", "evaluate")
_NUMBERING = ("{n}) ", "{n}. ", "Step {n}: ", "({n}) ")


def _group(text: str, start: int) -> tuple[str, int] | None:
    """The inside of the parenthesis group opening at text[start], and the index after it."""
    if start >= len(text) or text[start] != "(":
        return None
    depth = 0
    for index in range(start, len(text)):
        depth += (text[index] == "(") - (text[index] == ")")
        if depth == 0:
            return text[start + 1 : index], index + 1
    return None


_EXPONENT = re.compile(r"-?(?:\d+(?:\.\d+)?|[A-Za-z])")


def _power(text: str, start: int) -> tuple[str, int] | None:
    """The LaTeX power for the `^` at text[start] and the index after it, or None.

    The exponent is a bracket group, a signed number or a single letter, nothing more, so
    `x^2y` is `x^{2}y` and never `x^{2y}`.
    """
    if text[start : start + 1] != "^":
        return None
    if group := _group(text, start + 1):
        return "^{" + to_latex(group[0]) + "}", group[1]
    if token := _EXPONENT.match(text, start + 1):
        return "^{" + token.group(0) + "}", token.end()
    return None


def to_latex(text: str) -> str:
    """Plain-text math as LaTeX (fractions, roots, powers, products)."""
    out: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if text.startswith("sqrt(", index) and (group := _group(text, index + 4)):
            out.append("\\sqrt{" + to_latex(group[0]) + "}")
            index = group[1]
        elif char == "(" and (group := _group(text, index)):
            after = group[1]
            denominator = _group(text, after + 1) if text[after : after + 1] == "/" else None
            if denominator:
                bottom, index = to_latex(denominator[0]), denominator[1]
                if power := _power(text, index):  # a/(b^2), not (a/b)^2
                    bottom, index = bottom + power[0], power[1]
                out.append("\\frac{" + to_latex(group[0]) + "}{" + bottom + "}")
            else:
                out.append("(" + to_latex(group[0]) + ")")
                index = after
        elif power := _power(text, index):
            out.append(power[0])
            index = power[1]
        elif char == "*":
            out.append(" \\cdot ")
            index += 1
        else:
            out.append(char)
            index += 1
    return re.sub(r"\s*\\cdot\s*", lambda _: " \\cdot ", "".join(out))


def to_unicode(text: str) -> str:
    """Plain-text math with ², ³, ×, √ and the minus sign."""
    text = re.sub(r"\^2(?!\w)", "²", text)
    text = re.sub(r"\^3(?!\w)", "³", text)
    text = re.sub(r"\s*\*\s*", " × ", text)
    text = text.replace("sqrt(", "√(")
    return re.sub(r"(?<=[\w)])\s-\s(?=[\w(])", " − ", text)


def to_spoken(text: str) -> str:
    """Operators spelled out as words; numbers and letters stay."""
    text = re.sub(r"\^2(?!\w)", " squared", text)
    text = re.sub(r"\^3(?!\w)", " cubed", text)
    text = re.sub(r"\s*=\s*", " equals ", text)
    text = re.sub(r"(?<=[\w)])\s*\+\s*(?=[\w(])", " plus ", text)
    text = re.sub(r"(?<=[\w)])\s+-\s+(?=[\w(])", " minus ", text)
    return re.sub(r"\s*\*\s*", " times ", text)


def notate(text: str, notation: str, *, inline: bool = True) -> str:
    """The text in a notation. LaTeX is wrapped in dollar signs when `inline`."""
    if notation == "latex":
        return f"${to_latex(text)}$" if inline else to_latex(text)
    if notation == "unicode":
        return to_unicode(text)
    if notation == "spoken":
        return to_spoken(text)
    return text


def typo(word: str, rng: random.Random) -> str:
    """Swap two neighbouring letters of a word of five letters or more."""
    if len(word) < 5 or not word.isalpha():
        return word
    index = rng.randrange(1, len(word) - 2)
    return word[:index] + word[index + 1] + word[index] + word[index + 2 :]


def render_message(
    problem: str | None,
    steps: list[str],
    *,
    kind: str,
    layout: str,
    notation: str,
    chatty: bool,
    typos: bool,
    rng: random.Random,
) -> str:
    """The student's message for a problem (or none) and steps, in one layout and notation.

    `kind` is "equation" or "expression" and only chooses the verb in front of the problem.
    """
    verbs = _SOLVE_WORDS if kind == "equation" else _SIMPLIFY_WORDS
    lines = [notate(step, notation) for step in steps]
    if layout == "numbered":
        template = rng.choice(_NUMBERING)
        lines = [template.format(n=n) + line for n, line in enumerate(lines, 1)]
    elif layout == "connectors":
        words = [rng.choice(_CONNECTORS) for _ in lines]
        lines = [lines[0]] + [
            f"{word} {line}" for word, line in zip(words[1:], lines[1:], strict=True)
        ]
    head = f"{rng.choice(verbs)} {notate(problem, notation)}" if problem is not None else ""
    if layout == "one_line" and lines:
        body = rng.choice((" => ", "; ", " , ", " so ")).join(lines)
        text = f"{head}: {body}" if head else body
    elif layout == "connectors":
        text = (head + (" . " if head else "") + " , ".join(lines)).strip()
    else:
        text = "\n".join(([head] if head else []) + lines)
    if chatty:
        text = f"{rng.choice(_OPENERS)}\n{text}\n{rng.choice(_CLOSERS)}"
    return _typos_in_words(text, rng) if typos else text


_NO_TYPOS = {"x", "y", "z", "equals", "minus", "plus", "times", "squared", "cubed"}


def _typos_in_words(text: str, rng: random.Random) -> str:
    """Typos in the plain words of a message; digits, math symbols and spoken operators are left."""
    out = []
    for token in re.split(r"(\s+)", text):
        plain = token.isalpha() and token.lower() not in _NO_TYPOS
        out.append(typo(token, rng) if plain and rng.random() < 0.5 else token)
    return "".join(out)
