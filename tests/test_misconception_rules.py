import random

import pytest

from evals.builders.misconception_rules import RULES, draw, draw_wrapped
from tutor.tools.algebra import step_relation
from tutor.tools.catalogue import load_catalogue

CATALOGUE = {entry.id: entry for entry in load_catalogue()}


def test_every_rule_belongs_to_a_catalogue_entry() -> None:
    assert set(RULES) <= set(CATALOGUE)
    assert len(RULES) >= 80


@pytest.mark.parametrize("rule_id", sorted(RULES))
def test_a_rule_gives_a_really_wrong_line(rule_id: str) -> None:
    pair = draw(rule_id, random.Random(f"test:{rule_id}"))
    assert pair is not None, rule_id
    previous, wrong = pair
    assert step_relation(previous, wrong) == "not_valid"


@pytest.mark.parametrize("rule_id", ["M010", "M037", "M073", "M099"])
def test_draws_are_reproducible_and_vary(rule_id: str) -> None:
    first = [draw(rule_id, random.Random(f"{rule_id}:{i}")) for i in range(6)]
    again = [draw(rule_id, random.Random(f"{rule_id}:{i}")) for i in range(6)]
    assert first == again
    assert len({pair for pair in first if pair}) > 1


def test_draws_do_not_copy_the_catalogues_example_text() -> None:
    copies = 0
    for rule_id in RULES:
        pair = draw(rule_id, random.Random(f"copy:{rule_id}"))
        assert pair is not None
        if f"{pair[0]} -> {pair[1]}" == CATALOGUE[rule_id].example:
            copies += 1
    assert copies <= len(RULES) // 10  # tiny rules (x * x -> 2x) can match the example by chance


def test_a_rule_that_never_gives_a_wrong_line_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(RULES, "M001", lambda a, b, c, d, x, y: ("1 + 1", "2"))
    assert draw("M001", random.Random(0)) is None


@pytest.mark.parametrize("rule_id", sorted(RULES))
def test_a_wrapped_draw_is_really_wrong_or_not_wrappable(rule_id: str) -> None:
    pair = draw_wrapped(rule_id, random.Random(f"wrap:{rule_id}"))
    if pair is not None:
        assert step_relation(*pair) == "not_valid"
        assert pair != draw(rule_id, random.Random(f"wrap:{rule_id}"))


def test_wrapped_lines_sit_in_a_larger_expression_with_the_same_context() -> None:
    previous, wrong = draw_wrapped("M037", random.Random(1)) or ("", "")
    assert previous != "" and previous.endswith(")") or "(" in previous
    assert len(previous) > len("(x + 3)^2") - 2
    equation = draw_wrapped("M003", random.Random(1))
    assert equation is not None and equation[0].count("=") == 1 and "+" in equation[0].split("=")[0]


@pytest.mark.parametrize("rule_id", ["M071", "M076", "M072", "M102"])
def test_lines_with_or_or_plus_minus_are_not_wrapped(rule_id: str) -> None:
    assert draw_wrapped(rule_id, random.Random(2)) is None


def test_the_numbers_of_a_draw_are_never_equal_where_a_rule_uses_two() -> None:
    for i in range(30):
        previous, _ = draw("M071", random.Random(i)) or ("", "")
        assert (
            previous.split(")(")[0].split("- ")[-1]
            != previous.split(")(")[1].split("-")[1].split(")")[0].strip()
        )
