"""Mine step pairs from MATH solutions.

A pair is two consecutive lines of one chain in a human-written solution, so its label
(`equivalent`) comes from the solution's author, not from SymPy. Only chains that convert to plain
text are kept. Equation chains come from `align` blocks whose lines each carry their own left side.
"""

import re
from dataclasses import dataclass
from typing import Literal

from evals.builders.latex import latex_to_text

ChainKind = Literal["expression", "equation"]
TaskType = Literal["solve", "simplify", "expand", "factor"]

_ALIGN = re.compile(r"\\begin\{(align\*?|aligned)\}(.*?)\\end\{\1\}", re.DOTALL)
_LINE_BREAK = re.compile(r"\\\\(\[[^\]]*\])?")
_INLINE = re.compile(r"(?<!\\)\$(.+?)(?<!\\)\$", re.DOTALL)


@dataclass(frozen=True)
class Chain:
    kind: ChainKind
    items: tuple[str, ...]
    origin: Literal["align", "inline"]


@dataclass(frozen=True)
class StepPair:
    prev: str
    curr: str
    kind: ChainKind
    origin: str


def task_type(problem: str) -> TaskType:
    """A rough task type from the problem text (recorded in the dataset's provenance)."""
    lowered = problem.lower()
    if "expand" in lowered:
        return "expand"
    if "factor" in lowered:
        return "factor"
    if "solve" in lowered or ("find" in lowered and "=" in lowered):
        return "solve"
    return "simplify"


def _convert_all(pieces: list[str]) -> list[str | None]:
    return [latex_to_text(piece) for piece in pieces]


def _split_runs(items: list[str | None]) -> list[list[str]]:
    """Cut a chain at every item that could not be converted."""
    runs: list[list[str]] = [[]]
    for item in items:
        if item is None:
            runs.append([])
        else:
            runs[-1].append(item)
    return [run for run in runs if len(run) >= 2]


def _align_chains(block: str) -> list[Chain]:
    lines = [line.strip() for line in _LINE_BREAK.split(block) if line and line.strip()]
    lines = [line for line in lines if not line.startswith("[")]
    continuation = any(re.match(r"&\s*=", line) for line in lines)
    chains: list[Chain] = []
    if continuation:
        current: list[str | None] = []
        for line in lines:
            if re.match(r"&\s*=", line):
                current.extend(_convert_all(re.sub(r"^&\s*=", "", line).split("=")))
                continue
            chains.extend(Chain("expression", tuple(run), "align") for run in _split_runs(current))
            current = _convert_all(line.replace("&", " ").split("="))
        chains.extend(Chain("expression", tuple(run), "align") for run in _split_runs(current))
        return chains
    statements: list[str | None] = []
    for line in lines:
        if line.count("&") != 1 or line.count("=") != 1:
            statements.append(None)
            continue
        left, right = line.split("&")
        sides = (latex_to_text(left), latex_to_text(right.lstrip("= ").strip()))
        statements.append(f"{sides[0]} = {sides[1]}" if sides[0] and sides[1] else None)
    return [Chain("equation", tuple(run), "align") for run in _split_runs(statements)]


def extract_chains(solution: str) -> list[Chain]:
    """All convertible chains in one solution (align blocks first, then inline `a = b = c`)."""
    chains: list[Chain] = []
    for match in _ALIGN.finditer(solution):
        chains.extend(_align_chains(match.group(2)))
    remainder = _ALIGN.sub(" ", solution)
    for match in _INLINE.finditer(remainder):
        segment = match.group(1)
        if segment.count("=") >= 2 and "\\text" not in segment:
            pieces = _convert_all(segment.split("="))
            chains.extend(Chain("expression", tuple(run), "inline") for run in _split_runs(pieces))
    return chains


_COMPLEX = re.compile(r"(?<![A-Za-z])i(?![A-Za-z])")
_UPPERCASE = re.compile(r"[A-Z]")  # points, sets and named quantities, not algebra variables
_FUNCTION_NOTATION = re.compile(r"(?<![A-Za-z0-9)])[fgh]\(")  # f(x), g(2); x(x+1) is a product


def _is_identity_chain(chain: Chain, task: TaskType) -> bool:
    """Keep a chain only when its lines are meant to be equal as expressions.

    An `a = b = c` in a solution can also be a matching condition (`x^2 - 16x + k = (x+b)^2`), which
    is not a simplification step. Expression chains with variables are therefore kept only for
    simplify, expand and factor problems; chains of plain numbers always are. Complex numbers are
    out of scope.
    """
    if chain.kind != "expression":
        return True
    if any(_COMPLEX.search(item) or _UPPERCASE.search(item) for item in chain.items):
        return False
    has_variables = any(re.search(r"[A-Za-z]", item.replace("sqrt", "")) for item in chain.items)
    return not has_variables or task in ("simplify", "expand", "factor")


def _variables(text: str) -> frozenset[str]:
    return frozenset(re.findall(r"[A-Za-z]", text.replace("sqrt", "").replace("abs", "")))


def has_function_notation(problem: str) -> bool:
    """True if the problem uses f(x)-style functions or defines a custom operation.

    Lines in such solutions follow the problem's own definitions, not algebraic identities.
    """
    lowered = problem.lower()
    custom = "defined" in lowered or "operation" in lowered or "*" in problem
    return custom or bool(_FUNCTION_NOTATION.search(problem.replace("$", " ")))


def pairs_from_chains(chains: list[Chain], task: TaskType = "simplify") -> list[StepPair]:
    """Consecutive items of each identity chain, skipping identical neighbours."""
    pairs: list[StepPair] = []
    for chain in chains:
        if not _is_identity_chain(chain, task):
            continue
        for prev, curr in zip(chain.items, chain.items[1:], strict=False):
            if chain.kind == "expression" and _variables(prev) != _variables(curr):
                continue  # a substitution or a condition (x = 7, "= 0"), not an identity
            if prev.replace(" ", "") != curr.replace(" ", ""):
                pairs.append(StepPair(prev, curr, chain.kind, chain.origin))
    return pairs
