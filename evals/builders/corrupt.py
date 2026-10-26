"""Rule-based wrong steps for `verify`'s not_valid cases.

The label comes from the rule that broke the line (drop a term, flip a sign, bump a number, change
an exponent). A corruption is kept only when exact arithmetic finds a witness: a point where the new
line provably differs from the old one (for equations, a point where the old equation holds and the
new one fails). The witness uses evaluation, not SymPy's simplifier or solver, so a corruption that
is secretly still equivalent is discarded instead of being mislabelled.
"""

import random
import re
from dataclasses import dataclass

import sympy as sp

from evals.builders.mine_math import StepPair
from tutor.tools.algebra import Equations, Expression, UnparsableError, parse_statement

RULES = ("drop_term", "flip_sign", "bump_number", "change_exponent")
_POINTS = [sp.Rational(n, d) for d in (1, 2) for n in range(-24, 25) if n % d == 0 or d == 2]
_SYMBOL_VALUES = [2, 3, -1, 5, sp.Rational(1, 2), 7, -3, 4]


@dataclass(frozen=True)
class Corruption:
    text: str
    rule: str


def split_terms(text: str) -> list[str]:
    """Split at top-level + and -, keeping each sign with the term that follows it."""
    terms: list[str] = []
    depth, start = 0, 0
    for index, char in enumerate(text):
        depth += (char == "(") - (char == ")")
        previous = text[:index].rstrip()
        binary = bool(previous) and previous[-1] not in "(^*/+-"
        if depth == 0 and char in "+-" and binary:
            terms.append(text[start:index])
            start = index
    terms.append(text[start:])
    return [term for term in terms if term.strip()]


def _join(terms: list[str]) -> str:
    return "".join(terms).strip().lstrip("+").strip()


def apply_rule(rule: str, text: str, rng: random.Random) -> str | None:
    """Apply one corruption rule to one side of a line, or None if it does not apply."""
    terms = split_terms(text)
    if rule == "drop_term" and len(terms) >= 2:
        index = rng.randrange(len(terms))
        return _join(terms[:index] + terms[index + 1 :])
    if rule == "flip_sign" and terms:
        index = rng.randrange(len(terms))
        term = terms[index].strip()
        if term.startswith("+"):
            flipped = "-" + term[1:].strip()
        elif term.startswith("-"):
            flipped = "+" + term[1:].strip()
        else:
            flipped = "-" + term
        return _join(terms[:index] + [" " + flipped] + terms[index + 1 :])
    if rule == "bump_number":
        numbers = list(re.finditer(r"(?<![A-Za-z0-9.^])\d+(?![0-9.]*\s*\^)", text))
        if not numbers:
            return None
        found = rng.choice(numbers)
        bumped = int(found.group(0)) + 1
        return text[: found.start()] + str(bumped) + text[found.end() :]
    if rule == "change_exponent":
        exponents = list(re.finditer(r"\^\s*(\d)", text))
        if not exponents:
            return None
        found = rng.choice(exponents)
        new = int(found.group(1)) + 1
        return text[: found.start(1)] + str(new) + text[found.end(1) :]
    return None


def _assignments(symbols: list[sp.Symbol]) -> list[dict[sp.Symbol, sp.Expr]]:
    if not symbols:
        return [{}]
    return [
        {symbol: sp.Integer(value) if isinstance(value, int) else value for symbol in symbols}
        | {symbols[0]: sp.Integer(shift) if isinstance(shift, int) else shift}
        for value in _SYMBOL_VALUES[:3]
        for shift in _SYMBOL_VALUES
    ]


def expression_differs(prev: str, curr: str) -> bool:
    """Exact arithmetic finds a point where the two expressions have different values."""
    try:
        first, second = parse_statement(prev), parse_statement(curr)
    except UnparsableError:
        return False
    if not (isinstance(first, Expression) and isinstance(second, Expression)):
        return False
    symbols = sorted(first.value.free_symbols | second.value.free_symbols, key=str)
    for point in _assignments(symbols):
        try:
            difference = sp.nsimplify(first.value.subs(point) - second.value.subs(point))
            if difference.is_number and difference.is_real and sp.simplify(difference) != 0:
                return True
        except (ZeroDivisionError, TypeError):
            continue
    return False


def equation_loses_a_solution(prev: str, curr: str) -> bool:
    """A point where the old equation holds and the new one fails (curr does not follow)."""
    try:
        first, second = parse_statement(prev), parse_statement(curr)
    except UnparsableError:
        return False
    if not (isinstance(first, Equations) and isinstance(second, Equations)):
        return False
    symbols = set().union(*(a.free_symbols | b.free_symbols for a, b in first.pairs + second.pairs))
    if len(symbols) != 1:
        return False
    (symbol,) = symbols

    def holds(statement: Equations, value: sp.Expr) -> bool | None:
        try:
            return any(sp.simplify((a - b).subs(symbol, value)) == 0 for a, b in statement.pairs)
        except (ZeroDivisionError, TypeError):
            return None

    return any(holds(first, point) is True and holds(second, point) is False for point in _POINTS)


def corrupt_pair(pair: StepPair, rng: random.Random) -> Corruption | None:
    """One rule-based wrong version of `pair.curr`, or None if no rule gave a witnessed error."""
    rules = list(RULES)
    rng.shuffle(rules)
    for rule in rules:
        if pair.kind == "equation":
            left, _, right = pair.curr.partition("=")
            side = rng.choice((0, 1))
            changed = apply_rule(rule, (left, right)[side], rng)
            if changed is None:
                continue
            candidate = (
                f"{changed} = {right.strip()}" if side == 0 else f"{left.strip()} = {changed}"
            )
            if equation_loses_a_solution(pair.prev, candidate):
                return Corruption(candidate, rule)
        else:
            candidate_text = apply_rule(rule, pair.curr, rng)
            if candidate_text and expression_differs(pair.prev, candidate_text):
                return Corruption(candidate_text, rule)
    return None
