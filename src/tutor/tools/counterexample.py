"""A numeric counterexample for a wrong step, computed by SymPy (the LLM never does the arithmetic).

Given the line before the wrong step and the line the student wrote, find a small whole number to
put in for the variable(s) at which the lines disagree:
- two expressions: their values differ (`kind` "expression");
- two equations where one side stayed the same and the other changed to something not equivalent:
  the values of the changed side (`kind` "side", `where` "left" or "right"). Truth values would not
  help here: two different equations are both false at almost every number, and the number that
  makes the line before true is the problem's answer;
- two equations where both sides changed and the difference left - right is not just scaled: the
  value of left - right in each line (`kind` "balance").
A number that solves the original problem is never used, so the counterexample cannot hand over the
answer. Returns None when there is no such number or the lines are not handled (inequalities,
prose, a mix of expression and equation, equations joined by "or", valid rewrites).
"""

from dataclasses import dataclass
from typing import Literal

import sympy as sp

from tutor.tools import algebra

CANDIDATES = (2, 3, 4, -1, 5, -2, 6, 7, -3, 10)  # not 0 or 1: they hide many wrong rules

Kind = Literal["expression", "side", "balance"]


@dataclass(frozen=True)
class Counterexample:
    """The same numbers put into both lines, and what each line gives."""

    kind: Kind
    assignment: dict[str, int]
    before_value: str
    after_value: str
    where: str = ""  # "left" or "right" for kind "side"


def _finite(value: sp.Expr) -> bool:
    return bool(value.is_number) and not value.has(sp.zoo, sp.nan, sp.oo, -sp.oo)


def _same(first: sp.Expr, second: sp.Expr) -> bool:
    return bool(sp.simplify(first - second) == 0)


def _is_solution(excluded: sp.Set | None, numbers: dict[str, int]) -> bool:
    if excluded is None or len(numbers) != 1:
        return False
    (value,) = numbers.values()
    return bool(excluded.contains(value) == sp.true)


def _first_difference(
    one: sp.Expr, two: sp.Expr, excluded: sp.Set | None
) -> tuple[dict[str, int], sp.Expr, sp.Expr] | None:
    """The first candidate numbers where the two expressions have different finite values."""
    symbols = sorted(one.free_symbols | two.free_symbols, key=str)
    if not symbols:
        return None
    for start in CANDIDATES:
        numbers = {str(symbol): start + index for index, symbol in enumerate(symbols)}
        if _is_solution(excluded, numbers):
            continue
        values = {symbol: numbers[str(symbol)] for symbol in symbols}
        left, right = one.subs(values), two.subs(values)
        if _finite(left) and _finite(right) and not _same(left, right):
            return numbers, left, right
    return None


def _proportional(first: sp.Expr, second: sp.Expr) -> bool:
    """True when `second` is `first` times a nonzero constant (a valid rewrite of an equation)."""
    if _same(first, 0):
        return _same(second, 0)
    ratio = sp.simplify(second / first)
    return bool(ratio.is_number and ratio != 0)


def _equation_counterexample(
    before: tuple[sp.Expr, sp.Expr], after: tuple[sp.Expr, sp.Expr], excluded: sp.Set | None
) -> Counterexample | None:
    changed = [
        (where, old, new)
        for where, old, new in (("left", before[0], after[0]), ("right", before[1], after[1]))
        if not _same(old, new)
    ]
    if len(changed) == 1:
        where, old, new = changed[0]
        found = _first_difference(old, new, excluded)
        if found:
            numbers, left, right = found
            return Counterexample("side", numbers, str(left), str(right), where)
        return None
    if len(changed) == 2:
        old_gap, new_gap = before[0] - before[1], after[0] - after[1]
        if _proportional(old_gap, new_gap):
            return None
        found = _first_difference(old_gap, new_gap, excluded)
        if found:
            numbers, left, right = found
            return Counterexample("balance", numbers, str(left), str(right))
    return None


_NONE: Counterexample | None = None


@algebra.guarded(_NONE)
def counterexample(before: str, after: str, problem: str) -> Counterexample | None:
    """The first small number at which `before` and `after` disagree, or None."""
    try:
        first, second = algebra.parse_statement(before), algebra.parse_statement(after)
    except algebra.UnparsableError:
        return None
    excluded = algebra.solution_set(problem)
    if isinstance(first, algebra.Expression) and isinstance(second, algebra.Expression):
        found = _first_difference(first.value, second.value, excluded)
        if found:
            numbers, one, two = found
            return Counterexample("expression", numbers, str(one), str(two))
        return None
    if isinstance(first, algebra.Equations) and isinstance(second, algebra.Equations):
        if len(first.pairs) == 1 and len(second.pairs) == 1:
            return _equation_counterexample(first.pairs[0], second.pairs[0], excluded)
    return None
