"""A small LaTeX to plain-text converter for the subset that appears in MATH algebra solutions.

Returns None when the input uses anything outside that subset, so a caller drops the line instead
of guessing. The output is what `tutor.tools.algebra` parses: `^`, `*`, `/`, `sqrt(...)`.
"""

import re

from tutor.tools.algebra import ALLOWED_CHARS

_SPACING = re.compile(r"\\[,;:! ]|\\quad|\\qquad|~")
_DROP = re.compile(r"\\(left|right|displaystyle)(?![A-Za-z])")  # not \rightarrow, \leftarrow
_OPERATORS = {r"\cdot": "*", r"\times": "*", r"\div": "/"}
_DIGIT_SPACE = re.compile(r"\d\s*(\\[,;:! ]|\\quad|\\qquad|~)\s*\d")  # 1\,000
_FRACTIONS = ("\\dfrac", "\\tfrac", "\\frac")


def _group(text: str, start: int) -> tuple[str, int] | None:
    """The brace group starting at text[start] == "{", and the index after its closing brace."""
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    for index in range(start, len(text)):
        depth += (text[index] == "{") - (text[index] == "}")
        if depth == 0:
            return text[start + 1 : index], index + 1
    return None


def latex_to_text(source: str) -> str | None:
    """Convert one math fragment, or return None if it is outside the supported subset."""
    text = source.strip().strip("$").strip()
    if _DIGIT_SPACE.search(text):
        return None  # 1\,000 would be read as a product of 1 and 000
    text = _DROP.sub("", text)
    text = _SPACING.sub(" ", text).replace("&", " ")
    for latex, plain in _OPERATORS.items():
        text = re.sub(re.escape(latex) + r"(?![A-Za-z])", f" {plain} ", text)  # not \cdots
    text = text.replace("\\boxed", "")
    out: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            command = re.match(r"\\[A-Za-z]+", text[index:])
            if command is None:
                return None
            name = command.group(0)
            index += len(name)
            if name in _FRACTIONS:
                numerator = _group(text, index)
                denominator = _group(text, numerator[1]) if numerator else None
                if numerator is None or denominator is None:
                    return None
                after_digit = "".join(out).rstrip().endswith(tuple("0123456789"))
                if (
                    after_digit
                    and numerator[0].strip().isdigit()
                    and denominator[0].strip().isdigit()
                ):
                    return None  # 3\frac{1}{2} is a mixed number or a product: ambiguous
                top, bottom = latex_to_text(numerator[0]), latex_to_text(denominator[0])
                if top is None or bottom is None:
                    return None
                out.append(f"(({top})/({bottom}))")
                index = denominator[1]
            elif name == "\\sqrt":
                radicand = _group(text, index)
                if radicand is None:
                    return None
                inner = latex_to_text(radicand[0])
                if inner is None:
                    return None
                out.append(f"sqrt({inner})")
                index = radicand[1]
            else:
                return None  # \text, \pm, \pi, \le, \infty, ...
        elif char == "{":
            block = _group(text, index)
            if block is None:
                return None
            inner = latex_to_text(block[0])
            if inner is None:
                return None
            out.append(f"({inner})")
            index = block[1]
        elif char == "}":
            return None
        else:
            out.append(char)
            index += 1
    result = re.sub(r"\s+", " ", "".join(out)).strip().rstrip(".,;:").strip()
    if not result or not ALLOWED_CHARS.fullmatch(result):
        return None  # |x|, 1,000, a_1, 5 > 3: characters the checker cannot read
    return result
