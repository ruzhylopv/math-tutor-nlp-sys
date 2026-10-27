"""Mechanical wrong rules for catalogue entries: a correct line and the line a student with that
misconception would write.

Each rule is a function of random numbers `a, b, c, d` (small, at least 2) and variable
letters `x, y` that returns `(previous line, wrong line)` in plain-text math. A draw is kept
only if SymPy finds the two lines not valid (`step_relation` is `not_valid`), so the wrong
line is really wrong; draws that come out equivalent (a coincidence of small numbers) are
discarded. The true misconception of a generated query is therefore known by construction. The
rules are written from the catalogue entries' rules, not from a model, and use other numbers
and variable letters than the catalogue's examples."""

import random
from collections.abc import Callable

from tutor.tools.algebra import step_relation

Pair = tuple[str, str]
Rule = Callable[[int, int, int, int, str, str], Pair]


def _rules() -> dict[str, Rule]:
    return {
        # --- signs and negatives
        "M001": lambda a, b, c, d, x, y: (f"{a + 4} - (-{b})", f"{a + 4} - {b}"),
        "M002": lambda a, b, c, d, x, y: (f"(-{a})(-{b})", f"-{a * b}"),
        "M003": lambda a, b, c, d, x, y: (f"{x} + {a} = {c + a}", f"{x} = {c + a} + {a}"),
        "M004": lambda a, b, c, d, x, y: (f"(-{a})^2", f"-{a * a}"),
        "M005": lambda a, b, c, d, x, y: (f"-({x} + {a})", f"-{x} + {a}"),
        "M006": lambda a, b, c, d, x, y: (f"(-{a * b})/(-{b})", f"-{a}"),
        "M007": lambda a, b, c, d, x, y: (f"-{a + b + 2} + {b}", f"{a + 2}"),
        "M008": lambda a, b, c, d, x, y: (f"{a} - {a + b}", f"{b}"),
        "M009": lambda a, b, c, d, x, y: (f"-{x} = {c}", f"{x} = {c}"),
        # --- distribution
        "M010": lambda a, b, c, d, x, y: (
            f"{a}({x} + {b}) = {c + a * b}",
            f"{a}{x} + {b} = {c + a * b}",
        ),
        "M011": lambda a, b, c, d, x, y: (f"-{a}({x} - {b})", f"-{a}{x} - {b}"),
        "M012": lambda a, b, c, d, x, y: (f"({x} + {b})^2", f"2{x} + {2 * b}"),
        "M013": lambda a, b, c, d, x, y: (f"({x} + {a})({x} + {b})", f"{x}^2 + {a * b}"),
        "M014": lambda a, b, c, d, x, y: (f"{c} - {a}({x} + {b})", f"{c} - {a}{x} + {b}"),
        "M015": lambda a, b, c, d, x, y: (f"{x}({x} + {a})", f"{x}^2 + {a}"),
        "M016": lambda a, b, c, d, x, y: (f"(1/{a})({x} + {a * b})", f"{x}/{a} + {a * b}"),
        "M017": lambda a, b, c, d, x, y: (f"({x} + {a})({x} - {a})", f"{x}^2 + {a * a}"),
        # --- like terms and order of operations
        "M018": lambda a, b, c, d, x, y: (f"{a}{x} + {b}{x}", f"{a + b}{x}^2"),
        "M019": lambda a, b, c, d, x, y: (f"{a}{x} + {b}", f"{a + b}{x}"),
        "M020": lambda a, b, c, d, x, y: (f"{a} + {b} * {c}", f"{(a + b) * c}"),
        "M021": lambda a, b, c, d, x, y: (f"({a} + {b}) * {c}", f"{a} + {b * c}"),
        "M022": lambda a, b, c, d, x, y: (f"{x}^2 + {x}", f"{x}^3"),
        "M023": lambda a, b, c, d, x, y: (f"{x} * {x}", f"2{x}"),
        "M025": lambda a, b, c, d, x, y: (f"-{a}{x} + {a + b}{x}", f"-{2 * a + b}{x}"),
        "M026": lambda a, b, c, d, x, y: (f"{x} + {x} + {x}", f"{x}^3"),
        # --- fractions
        "M027": lambda a, b, c, d, x, y: (f"1/{a} + 1/{b}", f"2/{a + b}"),
        "M028": lambda a, b, c, d, x, y: (f"{b + 1}/{b + 2} - 1/{b}", f"{b}/2"),
        "M029": lambda a, b, c, d, x, y: (f"(1/{a}) / (1/{b})", f"(1/{a})(1/{b})"),
        "M030": lambda a, b, c, d, x, y: (f"{a} + 1/{b}", f"{a + 1}/{b}"),
        "M031": lambda a, b, c, d, x, y: (f"{a} * (2/{b})", f"{2 * a}/{a * b}"),
        "M032": lambda a, b, c, d, x, y: (f"{a + 4}/{a + 6}", f"{a}/{a + 2}"),
        "M033": lambda a, b, c, d, x, y: (f"2{x}/{2 * a}", f"{x}/{2 * a}"),
        "M034": lambda a, b, c, d, x, y: (f"{x}/{a} + {b} = {c}", f"{x} + {b} = {a * c}"),
        "M036": lambda a, b, c, d, x, y: (f"(2/{a}) * {a * b}", f"{a * b}/2"),
        # --- exponents and powers
        "M037": lambda a, b, c, d, x, y: (f"({x} + {a})^2", f"{x}^2 + {a * a}"),
        "M038": lambda a, b, c, d, x, y: (f"({x} - {a})^2", f"{x}^2 - {a * a}"),
        "M039": lambda a, b, c, d, x, y: (f"{a}^{b + 1}", f"{a * (b + 1)}"),
        "M040": lambda a, b, c, d, x, y: (f"({x}^{a})^{b}", f"{x}^{a + b}"),
        "M041": lambda a, b, c, d, x, y: (f"{x}^{a} * {x}^{b}", f"{x}^{a * b}"),
        "M042": lambda a, b, c, d, x, y: (f"{x}^{a * b}/{x}^{b}", f"{x}^{a}"),
        "M043": lambda a, b, c, d, x, y: (f"({a}{x})^{b}", f"{a}{x}^{b}"),
        "M044": lambda a, b, c, d, x, y: (f"{a}^(-{b})", f"-{a**b}"),
        "M045": lambda a, b, c, d, x, y: (f"{a}^0", "0"),
        "M046": lambda a, b, c, d, x, y: (f"{x}^(1/2)", f"{x}/2"),
        "M047": lambda a, b, c, d, x, y: (f"{a}^{b} * {a}^{c}", f"{a * a}^{b + c}"),
        "M048": lambda a, b, c, d, x, y: (f"({x}^{a} {y})^{b}", f"{x}^{a} {y}^{b}"),
        # --- solving equations
        "M049": lambda a, b, c, d, x, y: (f"{a}{x} + {b} = {a * c}", f"{x} + {b} = {c}"),
        "M050": lambda a, b, c, d, x, y: (f"{a}{x} + {b} = {c + b}", f"{a}{x} = {c + b}"),
        "M051": lambda a, b, c, d, x, y: (f"{a}{x} = {a * c}", f"{x} = {a * c} - {a}"),
        "M052": lambda a, b, c, d, x, y: (f"{x}/{a} = {c}", f"{x} = {c}/{a}"),
        "M053": lambda a, b, c, d, x, y: (
            f"{a + b}{x} - {c} = {b}{x} + {d}",
            f"{a}{x} - {c} = {b}{x} + {d}",
        ),
        "M054": lambda a, b, c, d, x, y: (f"{a}{x} = {a * c}", f"{x} = {a * c}"),
        "M055": lambda a, b, c, d, x, y: (f"{a}{x} = {c}", f"{x} = {a}/{c}"),
        "M056": lambda a, b, c, d, x, y: (
            f"{a}({x} + {b}) = {d}{x} + {c}",
            f"{a}{x} + {a * b} = {c}",
        ),
        "M057": lambda a, b, c, d, x, y: (f"{x}/{a} = {b}/{c}", f"{b}{x} = {a * c}"),
        "M059": lambda a, b, c, d, x, y: (f"{a}{x} + {b} = {a}{x} + {b + 1}", f"{x} = 0"),
        # --- squaring and extraneous roots
        "M063": lambda a, b, c, d, x, y: (
            f"sqrt({x} + {a + b}) = {x} - {b}",
            f"{x} + {a + b} = {x}^2 - {b * b}",
        ),
        "M065": lambda a, b, c, d, x, y: (f"sqrt({x}) = {x} - {a}", f"{x} = {x}^2 - {a}"),
        "M066": lambda a, b, c, d, x, y: (
            f"sqrt({x}) + {a} = {a + b}",
            f"{x} + {a} = {(a + b) ** 2}",
        ),
        "M069": lambda a, b, c, d, x, y: (f"{x}^2 = {a}{x}", f"{x} = {a}"),
        "M070": lambda a, b, c, d, x, y: (f"{x}/({x} - {a}) = {a}/({x} - {a})", f"{x} = {a}"),
        # --- quadratics
        "M071": lambda a, b, c, d, x, y: (
            f"({x} - {a})({x} - {b}) = {c}",
            f"{x} - {a} = {c} or {x} - {b} = {c}",
        ),
        "M072": lambda a, b, c, d, x, y: (
            f"({x} - {a})({x} + {b}) = 0",
            f"{x} = -{a} or {x} = {b}",
        ),
        "M073": lambda a, b, c, d, x, y: (f"{x}^2 = {a * a}", f"{x} = {a}"),
        "M074": lambda a, b, c, d, x, y: (f"{x}^2 = {a * a}", f"{x} = {a * a}/2"),
        "M075": lambda a, b, c, d, x, y: (f"{x}({x} - {a}) = 0", f"{x} = {a}"),
        "M076": lambda a, b, c, d, x, y: (
            f"{x}^2 - {a + b}{x} + {a * b} = 0",
            f"{x} = (-{a + b} +- sqrt({(a + b) ** 2} - {4 * a * b}))/2",
        ),
        "M078": lambda a, b, c, d, x, y: (f"{x}^2 + {2 * a}{x} = {c}", f"({x} + {a})^2 = {c}"),
        "M079": lambda a, b, c, d, x, y: (
            f"{x}^2 + {2 * a}{x} = {c}",
            f"({x} + {2 * a})^2 = {c + 4 * a * a}",
        ),
        "M080": lambda a, b, c, d, x, y: (f"{x}^2 + {a}{x} = {c}", f"{x}^2 + {a}{x} + {c} = 0"),
        # --- factoring
        "M081": lambda a, b, c, d, x, y: (
            f"({x} + {a})({x} + {b})",
            f"{x}^2 + {a + b}{x} + {a + b}",
        ),
        "M082": lambda a, b, c, d, x, y: (
            f"{x}^2 + {a + b}{x} + {a * b}",
            f"({x} + 1)({x} + {a * b})",
        ),
        "M083": lambda a, b, c, d, x, y: (
            f"{x}^2 - {a + b}{x} + {a * b}",
            f"({x} + {a})({x} + {b})",
        ),
        "M084": lambda a, b, c, d, x, y: (f"{x}^2 - {a * a}", f"({x} - {a})^2"),
        "M085": lambda a, b, c, d, x, y: (f"{x}^2 + {a * a}", f"({x} + {a})({x} - {a})"),
        "M086": lambda a, b, c, d, x, y: (f"{2 * a}{x} + {3 * a}", f"{a}(2{x} + {3 * a})"),
        "M087": lambda a, b, c, d, x, y: (f"{a}{x} + {a}", f"{a}({x})"),
        "M088": lambda a, b, c, d, x, y: (f"{x}^2 - {a}{x}", f"{x}({x} + {a})"),
        "M089": lambda a, b, c, d, x, y: (
            f"{a}{x}^2 + {a * b + 1}{x} + {b}",
            f"({x} + {b})({x} + 1)",
        ),
        # --- radicals
        "M090": lambda a, b, c, d, x, y: (f"sqrt({a * a} + {b * b})", f"{a} + {b}"),
        "M091": lambda a, b, c, d, x, y: (f"sqrt({a}) * sqrt({b})", f"sqrt({a + b})"),
        "M092": lambda a, b, c, d, x, y: (f"sqrt({x}^2)", f"{x}"),
        "M094": lambda a, b, c, d, x, y: (f"sqrt({4 * a * a})", f"{2 * a * a}"),
        "M095": lambda a, b, c, d, x, y: (f"1/sqrt({a})", f"sqrt({a})/1"),
        "M096": lambda a, b, c, d, x, y: (f"sqrt({25 * a})", f"5*sqrt({5 * a})"),
        "M097": lambda a, b, c, d, x, y: (f"sqrt({x}) = {a}", f"{x} = {a}"),
        "M098": lambda a, b, c, d, x, y: (
            f"{a}*sqrt({b}) * {c}*sqrt({d})",
            f"{a * c}*sqrt({b + d})",
        ),
        # --- absolute value
        "M099": lambda a, b, c, d, x, y: (f"abs({x} - {a}) = {b}", f"{x} - {a} = {b}"),
        "M100": lambda a, b, c, d, x, y: (f"abs({x}) = -{a}", f"{x} = {a}"),
        "M101": lambda a, b, c, d, x, y: (f"abs({a} + (-{a + b}))", f"abs({a}) + abs(-{a + b})"),
        "M102": lambda a, b, c, d, x, y: (
            f"abs({x} - {a}) = {b}",
            f"{x} - {a} = {b} or {x} + {a} = {b}",
        ),
        "M103": lambda a, b, c, d, x, y: (f"abs(-{a})", f"-{a}"),
        "M104": lambda a, b, c, d, x, y: (f"abs({x} - {a})", f"{x} - {a}"),
        # --- rational expressions
        "M113": lambda a, b, c, d, x, y: (f"({x} + {a})/({x} + {b})", f"{a}/{b}"),
        "M114": lambda a, b, c, d, x, y: (f"1/({x} + {a})", f"1/{x} + 1/{a}"),
        "M115": lambda a, b, c, d, x, y: (f"({a}{x} + {a * b})/{a}", f"{x} + {a * b}"),
        "M116": lambda a, b, c, d, x, y: (f"1/{x} + 1/{y}", f"2/({x} + {y})"),
        "M117": lambda a, b, c, d, x, y: (f"{x}/{x}^2", f"{x}"),
        # M118 has no rule: its wrong step is `implies` for SymPy (a hand-written query covers it)
        "M119": lambda a, b, c, d, x, y: (
            f"1/{x} + 1/({x} + {a})",
            f"({x} + {a})/({x}({x} + {a})) + 1/({x}({x} + {a}))",
        ),
    }


RULES = _rules()
LETTERS = ("x", "y", "n", "t", "k")
MAX_DRAWS = 40


def draw(rule_id: str, rng: random.Random) -> Pair | None:
    """One (previous line, wrong line) for a rule, or None if no draw gave a really wrong line."""
    rule = RULES[rule_id]
    for _ in range(MAX_DRAWS):
        a, b, c, d = (rng.randint(2, 9) for _ in range(4))
        x = rng.choice(LETTERS)
        y = rng.choice([letter for letter in LETTERS if letter != x])
        previous, wrong = rule(a, b, c, d, x, y)
        if step_relation(previous, wrong) == "not_valid":
            return previous, wrong
    return None
