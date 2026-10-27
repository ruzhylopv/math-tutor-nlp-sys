"""Deterministic answer-leakage check for a hint (no LLM).

A hint leaks when it states the problem's answer ("x = 3" for a solution) or writes out the correct
form of a line: an expression structurally equal to the value, `expand`, `factor` or `simplify` of
a side of the problem or of the line before the wrong step. Structural, not just equivalent, and
quoting a side as written is fine: `3(x + 2)` is allowed, `3x + 6` is not.

Math is read from backtick fragments (the hint prompt asks for them); a bare `var = number` in the
prose is checked too. Limits: only these forms are caught, not every correct next step, and a
fragment that does not parse is ignored.
"""

import re

import sympy as sp

from tutor.tools import algebra

_FRAGMENT = re.compile(r"`([^`]+)`")
_BARE_ASSIGNMENT = re.compile(r"\b([a-z])\s*=\s*(-?\d+(?:\.\d+)?(?:\s*/\s*\d+)?)")


def _parts(text: str) -> list[tuple[str, sp.Expr]]:
    """Each side of an equation (or the whole expression) as (text without spaces, value)."""
    parts: list[tuple[str, sp.Expr]] = []
    for piece in re.split(r"=|\s+or\s+", text):
        try:
            statement = algebra.parse_statement(piece)
        except algebra.UnparsableError:
            continue
        if isinstance(statement, algebra.Expression):
            parts.append((re.sub(r"\s+", "", piece), statement.value))
    return parts


def _forms(parts: list[tuple[str, sp.Expr]]) -> list[sp.Expr]:
    """The expanded, factored and simplified form of each part (SymPy has already distributed
    a number over a bracket when it parsed, so the part itself is one of the forms)."""
    forms: list[sp.Expr] = []
    for _, value in parts:
        for form in (value, sp.expand(value), sp.factor(value), sp.simplify(value)):
            if form not in forms:
                forms.append(form)
    return forms


def _assigned(text: str, solutions: sp.Set | None) -> str | None:
    """The solution a fragment states, if it is a bare `variable = number`; else None."""
    if solutions is None:
        return None
    try:
        statement = algebra.parse_statement(text)
    except algebra.UnparsableError:
        return None
    if not isinstance(statement, algebra.Equations):
        return None
    for left, right in statement.pairs:
        for variable, value in ((left, right), (right, left)):
            if variable.is_Symbol and value.is_number and solutions.contains(value) == sp.true:
                return f"{variable} = {value}"
    return None


_NONE: list[str] | None = None


@algebra.guarded(_NONE)
def _find_leaks(text: str, problem: str, before: str) -> list[str] | None:
    solutions = algebra.solution_set(problem)
    given = _parts(problem) + _parts(before)
    quoted = {written for written, _ in given}
    forms = _forms(given)
    fragments = _FRAGMENT.findall(text)
    fragments += [f"{name} = {number}" for name, number in _BARE_ASSIGNMENT.findall(text)]
    leaks: list[str] = []
    for fragment in fragments:
        stated = _assigned(fragment, solutions)
        if stated:
            leaks.append(f"states the answer: {stated}")
            continue
        for written, side in _parts(fragment):
            if written not in quoted and side in forms:
                leaks.append(f"writes out a correct form: {fragment.strip()}")
                break
    return list(dict.fromkeys(leaks))


def find_leaks(text: str, problem: str, before: str) -> list[str]:
    """Why the hint leaks (empty if it does not). If SymPy fails the hint is judged not to leak."""
    return _find_leaks(text, problem, before) or []
