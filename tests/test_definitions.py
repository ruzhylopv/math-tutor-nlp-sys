import pytest

from tutor.tools.algebra import definition_of, letters, step_relation

PROBLEM = "(x+1)^2 - 3(x+1) - 10 = 0"


def test_a_new_letter_set_to_an_expression_is_a_definition() -> None:
    assert definition_of("t = x + 1", PROBLEM, {}) == ("t", "x + 1")


def test_a_definition_may_use_an_earlier_one() -> None:
    assert definition_of("v = u + 1", "1/x + 1/x^2 = 6", {"u": "1/x"}) == ("v", "u + 1")


@pytest.mark.parametrize(
    ("line", "known"),
    [
        ("x = 4", {}),  # the problem's own letter: a step, not a definition
        ("t = 5", {}),  # no known letter on the right
        ("t = x + 1", {"t": "x - 1"}),  # already defined
        ("t = y + 1", {}),  # an unknown letter on the right
        ("x + 1 = t", {}),  # the letter must be on the left
        ("t = x + 1 or t = x", {}),  # one equation only
        ("t = t + x", {}),  # the letter on both sides
        ("2t = x + 1", {}),
        ("t is x plus one", {}),
    ],
)
def test_lines_that_are_not_definitions(line: str, known: dict[str, str]) -> None:
    assert definition_of(line, PROBLEM, known) is None


def test_no_definition_when_the_problem_does_not_parse() -> None:
    assert definition_of("t = x + 1", "Find the two numbers.", {}) is None


def test_defined_letters_are_substituted_before_comparing() -> None:
    assert step_relation(PROBLEM, "t^2 - 3t - 10 = 0", definitions={"t": "x + 1"}) == "equivalent"
    assert step_relation(PROBLEM, "t^2 - 3t + 10 = 0", definitions={"t": "x + 1"}) == "not_valid"
    # without the definition each line is solved in its own letter: the old step-1 bug
    assert step_relation(PROBLEM, "t^2 - 3t - 10 = 0") == "not_valid"


def test_substitution_follows_earlier_definitions() -> None:
    definitions = {"u": "1/x", "v": "u + 1"}
    assert step_relation("1/x + 1/x^2 = 6", "v^2 - v - 6 = 0", definitions=definitions) == (
        "equivalent"
    )


def test_letters() -> None:
    assert letters("t = 5 or t = -2") == {"t"}
    assert letters("not math at all") == frozenset()


def test_a_definition_with_a_unicode_minus_is_stored_parseable() -> None:
    assert definition_of("t = x − 1", PROBLEM, {}) == ("t", "x - 1")
    defs = {"t": "x - 1"}
    assert step_relation(PROBLEM, "(t+2)^2 - 3(t+2) - 10 = 0", definitions=defs) == "equivalent"
    assert step_relation(PROBLEM, "(t+2)^2 - 3(t+2) + 10 = 0", definitions=defs) == "not_valid"
