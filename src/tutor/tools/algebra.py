"""SymPy checks for verify: a restricted parser, the step relation and the answer check.

All math verification goes through here; no LLM is involved.
Rules: docs/plans/nodes/2026-10-26-m2-verify.md.

Limits (by design for M2): one variable per equation, real solutions only, no inequalities, no
branching solutions. A line that cannot be handled is `unparsable`.
"""

import re
from dataclasses import dataclass
from typing import Literal

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    rationalize,
    standard_transformations,
)

from tutor.state import Relation

AnswerVerdict = Literal["correct", "incorrect", "unparsable"]

# rationalize turns 2.28 into 57/25, so decimal arithmetic is exact and 2.28 * 5 equals 11.4
_TRANSFORMATIONS = (
    *standard_transformations,
    rationalize,
    implicit_multiplication_application,
    convert_xor,
)
_NAMESPACE = {
    "Symbol": sp.Symbol,
    "Function": sp.Function,
    "Integer": sp.Integer,
    "Float": sp.Float,
    "Rational": sp.Rational,
}
_FUNCTIONS = {"sqrt": sp.sqrt, "abs": sp.Abs}
_UNSUPPORTED_FUNCTIONS = {"sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "exp"}
_ALLOWED_CHARS = re.compile(r"[0-9A-Za-z+\-*/^().\s]*")
_BAD_DOT = re.compile(r"\.(?!\d)|(?<!\d)\.|\d+\.\d+\.")  # a dot needs digits on both sides, once
_WORDS = re.compile(r"[A-Za-z]+")
_MAX_VARIABLE_RUN = 3  # "xyz" is x*y*z; longer letter runs are not math
_UNICODE = str.maketrans({"−": "-", "–": "-", "×": "*", "·": "*", "÷": "/", "≠": "!"})


class UnparsableError(ValueError):
    """The text is not a statement this module handles."""


@dataclass(frozen=True)
class Expression:
    value: sp.Expr


@dataclass(frozen=True)
class Equations:
    """One or more equations joined by "or" (each a left side and a right side)."""

    pairs: tuple[tuple[sp.Expr, sp.Expr], ...]

    def is_closed(self) -> bool:
        return all(not (lhs.free_symbols | rhs.free_symbols) for lhs, rhs in self.pairs)

    def is_true(self) -> bool:
        """For a closed statement: true when at least one of the "or" parts holds."""
        return any(sp.simplify(lhs - rhs) == 0 for lhs, rhs in self.pairs)


Statement = Expression | Equations


def _parse_expression(text: str) -> sp.Expr:
    stripped = text.strip()
    if not stripped:
        raise UnparsableError("empty")
    if not _ALLOWED_CHARS.fullmatch(stripped) or _BAD_DOT.search(stripped):
        raise UnparsableError("characters outside the allowed set")
    for word in _WORDS.findall(stripped):
        if word.lower() in _UNSUPPORTED_FUNCTIONS:
            raise UnparsableError(f"unsupported function: {word}")
        if word not in _FUNCTIONS and len(word) > _MAX_VARIABLE_RUN:
            raise UnparsableError(f"unknown word: {word}")
    try:
        value = parse_expr(
            stripped.replace("abs(", "Abs("),
            local_dict={"sqrt": sp.sqrt, "Abs": sp.Abs},
            global_dict=dict(_NAMESPACE),
            transformations=_TRANSFORMATIONS,
        )
    except Exception as exc:  # any parse or evaluation failure means "not handled"
        raise UnparsableError(str(exc)[:80]) from exc
    if not isinstance(value, sp.Expr) or value.has(sp.I, sp.zoo, sp.nan, sp.oo):
        raise UnparsableError("not a real expression")
    if any(not isinstance(f, sp.Abs) for f in value.atoms(sp.Function)):
        raise UnparsableError("unsupported function")
    return value


def parse_statement(text: str) -> Statement:
    """Parse an expression, an equation, or equations joined by "or"."""
    cleaned = text.translate(_UNICODE).strip()
    parts = re.split(r"\s+or\s+", cleaned, flags=re.IGNORECASE)
    pairs: list[tuple[sp.Expr, sp.Expr]] = []
    for part in parts:
        sides = part.split("=")
        if len(sides) == 1:
            if len(parts) > 1:
                raise UnparsableError('"or" needs equations on both sides')
            return Expression(_parse_expression(part))
        if len(sides) != 2:
            raise UnparsableError("more than one '=' in a part")
        pairs.append((_parse_expression(sides[0]), _parse_expression(sides[1])))
    return Equations(tuple(pairs))


def _equal(first: sp.Expr, second: sp.Expr) -> bool:
    return bool(sp.simplify(first - second) == 0)


def _solutions(statement: Equations) -> sp.Set:
    symbols = set().union(*(lhs.free_symbols | rhs.free_symbols for lhs, rhs in statement.pairs))
    if len(symbols) != 1:
        raise UnparsableError("only one variable per equation is handled")
    (symbol,) = symbols
    result: sp.Set = sp.EmptySet
    for lhs, rhs in statement.pairs:
        found = sp.solveset(lhs - rhs, symbol, domain=sp.S.Reals)
        if isinstance(found, sp.ConditionSet):
            raise UnparsableError("could not solve")
        result = result.union(found)
    return result


def _same_set(first: sp.Set, second: sp.Set) -> bool:
    return bool(
        first == second or (first.is_subset(second) is True and second.is_subset(first) is True)
    )


def _proper_subset(inner: sp.Set, outer: sp.Set) -> bool:
    return bool(inner.is_subset(outer) is True and not _same_set(inner, outer))


def step_relation(prev: str, curr: str, original: str | None = None) -> Relation:
    """How `curr` relates to `prev`: equivalent, implies, narrows, not_valid or unparsable.

    `original` is the problem's own equation; it is only needed to recognise `narrows`
    (rejecting an extraneous root). A closed statement (no variables) is valid if it is true.
    Callers compare a line with the previous line that is not a check; see the M2 plan.
    """
    try:
        before, after = parse_statement(prev), parse_statement(curr)
        if isinstance(after, Equations) and after.is_closed():
            return "equivalent" if after.is_true() else "not_valid"
        if isinstance(before, Expression) and isinstance(after, Expression):
            return "equivalent" if _equal(before.value, after.value) else "not_valid"
        if isinstance(before, Equations) and isinstance(after, Equations):
            return _equation_relation(before, after, original)
    except UnparsableError:
        return "unparsable"
    return "not_valid"  # an expression became an equation, or the other way round


def _equation_relation(before: Equations, after: Equations, original: str | None) -> Relation:
    old, new = _solutions(before), _solutions(after)
    if _same_set(old, new):
        return "equivalent"
    if _proper_subset(old, new):
        return "implies"
    if original is not None and _proper_subset(new, old):
        source = parse_statement(original)
        if isinstance(source, Equations) and _same_set(_solutions(source), new):
            return "narrows"
    return "not_valid"


def _answer_values(text: str) -> list[sp.Expr] | sp.Expr:
    """A list of values for "9", "2, 9" or "x = 9 or x = 2"; an expression if it has variables."""
    depth, pieces, start = 0, [], 0
    for index, char in enumerate(text):
        depth += (char == "(") - (char == ")")
        if char == "," and depth == 0:
            pieces.append(text[start:index])
            start = index + 1
    pieces.append(text[start:])
    values: list[sp.Expr] = []
    for piece in pieces:
        statement = parse_statement(piece)
        if isinstance(statement, Expression):
            values.append(statement.value)
            continue
        for lhs, rhs in statement.pairs:
            if lhs.free_symbols and not rhs.free_symbols:
                values.append(rhs)
            elif rhs.free_symbols and not lhs.free_symbols:
                values.append(lhs)
            else:
                raise UnparsableError("not an answer of the form x = value")
    if len(values) == 1 and values[0].free_symbols:
        return values[0]
    if any(value.free_symbols for value in values):
        raise UnparsableError("mixed answer")
    return values


def check_answer(answer: str, ground_truth: str) -> AnswerVerdict:
    """Compare a final answer with the ground truth: numbers, lists of roots, or expressions."""
    try:
        given, expected = _answer_values(answer), _answer_values(ground_truth)
    except UnparsableError:
        return "unparsable"
    if isinstance(given, sp.Expr) and isinstance(expected, sp.Expr):
        return "correct" if _equal(given, expected) else "incorrect"
    if isinstance(given, list) and isinstance(expected, list):
        same = all(any(_equal(g, e) for e in expected) for g in given) and all(
            any(_equal(e, g) for g in given) for e in expected
        )
        return "correct" if same else "incorrect"
    return "incorrect"
