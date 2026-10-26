"""SymPy checks for verify: a restricted parser, the step relation and the answer check.

All math verification goes through here; no LLM is involved.
Rules: docs/plans/nodes/2026-10-26-m2-verify.md.

Limits (by design for M2): one variable per equation, real solutions only, no inequalities, no
branching solutions, no nested abs, no stacked powers, exponents up to 1000 (50 on a bracketed
base), inputs up to 200 characters. Any line this module cannot handle, and any SymPy failure
or timeout, is reported as `unparsable` (or `None` / `False` for the helpers): "cannot judge" is
never turned into a verdict.
"""

import re
import signal
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Literal, ParamSpec

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

P = ParamSpec("P")

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
_FUNCTIONS = frozenset({"sqrt", "abs"})
_UNSUPPORTED_FUNCTIONS = {"sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "exp"}
ALLOWED_CHARS = re.compile(r"[0-9A-Za-z+\-*/^().\s]*")
_BAD_DOT = re.compile(r"\.(?!\d)|(?<!\d)\.|\d+\.\d+\.")  # a dot needs digits on both sides, once
_PYTHON_NUMBER = re.compile(r"\d[eE][+-]?\d|\b0[xXbBoO]")  # 3e+2 and 0x10 are Python, not math here
_PLUS_MINUS = re.compile(r"\+-|±")
_WORDS = re.compile(r"[A-Za-z]+")
_PLAIN_NUMBER = re.compile(r"\d+(\.\d+)?")
_MAX_VARIABLE_RUN = 3  # "xyz" is x*y*z; longer letter runs are not math
_MAX_LENGTH = 200
_MAX_EXPONENT = 1000  # a number or a single variable to a power: cheap
_MAX_GROUP_EXPONENT = 50  # (x+1)^n is expanded by simplify: keep n small
_TIMEOUT_SECONDS = 5.0
_UNPARSABLE_RELATION: Relation = "unparsable"
_UNPARSABLE_ANSWER: AnswerVerdict = "unparsable"
_CANNOT_JUDGE: bool | None = None
_UNICODE = str.maketrans({"−": "-", "–": "-", "×": "*", "·": "*", "÷": "/", "≠": "!"})


class UnparsableError(ValueError):
    """The text is not a statement this module handles."""


class _Timeout(BaseException):
    """SymPy ran past the deadline (a BaseException, so SymPy's own `except Exception` skips it)."""


@contextmanager
def _deadline(seconds: float) -> Iterator[None]:
    """Raise _Timeout after `seconds` of wall-clock time (Unix main thread only; else no guard)."""
    if threading.current_thread() is not threading.main_thread() or not hasattr(
        signal, "setitimer"
    ):
        yield
        return

    def expire(signum: int, frame: object) -> None:
        raise _Timeout

    previous = signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _guarded[T](default: T) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Return `default` when SymPy fails or times out instead of letting the error escape."""

    def decorate(function: Callable[P, T]) -> Callable[P, T]:
        @wraps(function)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                with _deadline(_TIMEOUT_SECONDS):
                    return function(*args, **kwargs)
            except (_Timeout, Exception):  # any failure inside SymPy means "cannot judge"
                return default

        return wrapper

    return decorate


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


def _check_powers(text: str) -> None:
    """Reject stacked powers (9^9^9) and huge exponents before SymPy evaluates them.

    A bracketed base is capped lower than a number or a single variable, because simplify expands
    it. In `2^3x^3` the exponent is just `3` (implicit multiplication follows), not `3x`.
    """
    for match in re.finditer(r"\^", text):
        base_is_group = text[: match.start()].rstrip().endswith(")")
        rest = text[match.end() :].lstrip()
        if rest[:1] in ("+", "-"):
            rest = rest[1:].lstrip()
        if rest.startswith("("):
            depth, end = 0, -1
            for index, char in enumerate(rest):
                depth += (char == "(") - (char == ")")
                if depth == 0:
                    end = index
                    break
            if end < 0:
                raise UnparsableError("unbalanced brackets")
            inner, after = rest[1:end], rest[end + 1 :].lstrip()
        else:
            operand = re.match(r"\d+(?:\.\d+)?|[A-Za-z]", rest)
            inner = operand.group(0) if operand else ""
            after = rest[len(inner) :].lstrip()
        if "^" in inner or after.startswith("^"):
            raise UnparsableError("stacked powers are not handled")
        cap = _MAX_GROUP_EXPONENT if base_is_group else _MAX_EXPONENT
        if _PLAIN_NUMBER.fullmatch(inner.strip()) and float(inner) > cap:
            raise UnparsableError("exponent too large")


def _parse_expression(text: str) -> sp.Expr:
    stripped = text.strip().replace("**", "^")
    if not stripped:
        raise UnparsableError("empty")
    if len(stripped) > _MAX_LENGTH:
        raise UnparsableError("too long")
    if not ALLOWED_CHARS.fullmatch(stripped) or _BAD_DOT.search(stripped):
        raise UnparsableError("characters outside the allowed set")
    if _PYTHON_NUMBER.search(stripped):
        raise UnparsableError("Python number syntax")
    for word in _WORDS.findall(stripped):
        if word.lower() in _UNSUPPORTED_FUNCTIONS:
            raise UnparsableError(f"unsupported function: {word}")
        if word not in _FUNCTIONS and len(word) > _MAX_VARIABLE_RUN:
            raise UnparsableError(f"unknown word: {word}")
    _check_powers(stripped)
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
    if any(a.args[0].has(sp.Abs) for a in value.atoms(sp.Abs)):
        raise UnparsableError("nested abs is not handled")  # solveset gets it wrong
    value = value.xreplace({s: sp.Symbol(s.name, real=True) for s in value.free_symbols})
    if value.is_real is False:
        raise UnparsableError("not a real value")
    return value


def _expand_plus_minus(text: str) -> str:
    """`x = 1 +- 2` or `x = 1 ± 2` becomes two equations joined by "or"."""
    count = len(_PLUS_MINUS.findall(text))
    if count == 0:
        return text
    if count > 1 or re.search(r"\sor\s", text, flags=re.IGNORECASE):
        raise UnparsableError("one plus-or-minus and no 'or' alongside it")
    return f"{_PLUS_MINUS.sub('+', text)} or {_PLUS_MINUS.sub('-', text)}"


def parse_statement(text: str) -> Statement:
    """Parse an expression, an equation, or equations joined by "or"."""
    if len(text) > _MAX_LENGTH:
        raise UnparsableError("too long")
    cleaned = _expand_plus_minus(text.translate(_UNICODE).strip())
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
        if not isinstance(found, sp.Set) or found.has(sp.ConditionSet):
            raise UnparsableError("could not solve")
        if isinstance(found, sp.FiniteSet) and any(
            sp.simplify((lhs - rhs).subs(symbol, root)) != 0 for root in found
        ):
            raise UnparsableError("the solver returned a root that fails")
        result = result.union(found)
    return result


def _same_set(first: sp.Set, second: sp.Set) -> bool:
    return bool(
        first == second or (first.is_subset(second) is True and second.is_subset(first) is True)
    )


def _proper_subset(inner: sp.Set, outer: sp.Set) -> bool:
    # is_subset can return None (unknown); that counts as "not a subset", so the step is not_valid
    return bool(inner.is_subset(outer) is True and not _same_set(inner, outer))


@_guarded(_UNPARSABLE_RELATION)
def step_relation(prev: str, curr: str, original: str | None = None) -> Relation:
    """How `curr` relates to `prev`: equivalent, implies, narrows, not_valid or unparsable.

    `original` is the problem's own equation; it is only needed to recognise `narrows`
    (rejecting an extraneous root). A closed statement (no variables) is valid if it is true,
    whatever `prev` is. Callers compare a line with the previous line that is not a check.
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
    if old == sp.EmptySet:
        return "not_valid"  # "solving" a contradiction: anything follows from no solutions
    if _proper_subset(old, new):
        return "implies"
    if original is not None and _proper_subset(new, old):
        source = parse_statement(original)
        if isinstance(source, Equations) and _same_set(_solutions(source), new):
            return "narrows"
    return "not_valid"


Answer = list[tuple[str | None, sp.Expr]]


def _answer_values(text: str) -> Answer | sp.Expr:
    """Values (with the variable name when given) for "9", "2, 9" or "x = 9 or x = 2".

    An expression with variables ("2x + 3") is returned as one expression.
    """
    if re.search(r"\d,\d{3}(?!\d)", text):
        raise UnparsableError("1,000 could be a number or a list")
    depth, pieces, start = 0, [], 0
    for index, char in enumerate(text):
        depth += (char == "(") - (char == ")")
        if char == "," and depth == 0:
            pieces.append(text[start:index])
            start = index + 1
    pieces.append(text[start:])
    values: Answer = []
    for piece in pieces:
        statement = parse_statement(piece)
        if isinstance(statement, Expression):
            values.append((None, statement.value))
            continue
        for lhs, rhs in statement.pairs:
            if lhs.free_symbols and not rhs.free_symbols:
                values.append((str(next(iter(lhs.free_symbols))), rhs))
            elif rhs.free_symbols and not lhs.free_symbols:
                values.append((str(next(iter(rhs.free_symbols))), lhs))
            else:
                raise UnparsableError("not an answer of the form x = value")
    if len(values) == 1 and values[0][1].free_symbols and values[0][0] is None:
        return values[0][1]
    if any(value.free_symbols for _, value in values):
        raise UnparsableError("mixed answer")
    return values


@_guarded(_UNPARSABLE_ANSWER)
def check_answer(answer: str, ground_truth: str) -> AnswerVerdict:
    """Compare a final answer with the ground truth: numbers, lists of roots, or expressions.

    A variable name is compared when both sides give one ("x = 3" is not "y = 3"). An answer with
    leftover letters ("9 cm") against a numeric truth cannot be judged and is `unparsable`.
    """
    try:
        given, expected = _answer_values(answer), _answer_values(ground_truth)
    except UnparsableError:
        return "unparsable"
    if isinstance(given, sp.Expr) and isinstance(expected, sp.Expr):
        return "correct" if _equal(given, expected) else "incorrect"
    if isinstance(given, list) and isinstance(expected, list):
        given_names = {name for name, _ in given if name}
        expected_names = {name for name, _ in expected if name}
        if given_names and expected_names and given_names != expected_names:
            return "incorrect"
        same = all(any(_equal(g, e) for _, e in expected) for _, g in given) and all(
            any(_equal(e, g) for _, g in given) for _, e in expected
        )
        return "correct" if same else "incorrect"
    return "unparsable"  # an expression with letters against a list of numbers


def parses(text: str) -> bool:
    """True if the text is a statement this module can handle."""
    try:
        parse_statement(text)
    except UnparsableError:
        return False
    return True


def is_equation(text: str) -> bool:
    """True for an equation (or equations joined by "or") that is not a closed statement."""
    try:
        statement = parse_statement(text)
    except UnparsableError:
        return False
    return isinstance(statement, Equations) and not statement.is_closed()


def is_closed_statement(text: str) -> bool:
    """True for a statement without variables, such as a check like "sqrt(9+7) = 9-5"."""
    try:
        statement = parse_statement(text)
    except UnparsableError:
        return False
    return isinstance(statement, Equations) and statement.is_closed()


@_guarded(_CANNOT_JUDGE)
def claim_truth(text: str) -> bool | None:
    """Whether a closed claim such as "-2 + -9 = 11" is true; None if it is not a closed claim.

    Equations joined by "or" are true if any part is ("2+2=5 or 1=1" is true).
    """
    try:
        statement = parse_statement(text)
    except UnparsableError:
        return None
    if isinstance(statement, Equations) and statement.is_closed():
        return statement.is_true()
    return None


@_guarded(_CANNOT_JUDGE)
def final_answer_matches(problem: str, final_line: str) -> bool | None:
    """Whether the student's last line answers the problem; None if that cannot be judged.

    For an equation the answer must be exactly its real solution set ("x = 9", "9" or "2, 9").
    For an expression the last line must be equivalent to it; whether it is fully simplified
    cannot be told from the text alone. Answers such as "no solution" or "all real numbers" are
    not recognised. Note the answer rule is looser than the step rule: a bare "3" answers
    "x + 1 = 4" but is not a valid step after it.
    """
    try:
        original = parse_statement(problem)
        if isinstance(original, Equations):
            truth = _solutions(original)
            values = _answer_values(final_line)
            if not isinstance(values, list):
                return False
            return _same_set(truth, sp.FiniteSet(*(value for _, value in values)))
        final = parse_statement(final_line)
    except UnparsableError:
        return None
    return isinstance(final, Expression) and _equal(original.value, final.value)
