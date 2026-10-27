import pytest

from tutor.tools.leakage import find_leaks

EQUATION = "3(x + 2) = 15"
SQUARE = "(x - 5)^2"


def test_a_hint_that_states_the_solution_leaks() -> None:
    assert find_leaks("So `x = 3` is the answer.", EQUATION, EQUATION)
    assert find_leaks("so 3 = x", EQUATION, EQUATION) == []  # bare, not in a fragment or x = n form
    assert find_leaks("So x = 3, right?", EQUATION, EQUATION)  # bare assignment in the prose


def test_a_number_that_is_not_a_solution_does_not_leak() -> None:
    assert find_leaks("At `x = 4` the two lines differ.", EQUATION, EQUATION) == []
    assert find_leaks("Try x = 2 in both lines.", EQUATION, EQUATION) == []


def test_the_expanded_or_factored_form_leaks() -> None:
    assert find_leaks("Next you get `3x + 6 = 15`.", EQUATION, EQUATION)
    assert find_leaks("It becomes `x^2 - 10x + 25`.", SQUARE, SQUARE)
    assert find_leaks("It is `(x - 5)(x - 5)`.", "x^2 - 10x + 25", "x^2 - 10x + 25")  # factored
    assert find_leaks("Write `(x - 5)^2`.", "x^2 - 10x + 25", "x^2 - 10x + 25")


def test_quoting_the_students_own_line_is_fine() -> None:
    assert find_leaks("In `3(x + 2) = 15` what does the 3 multiply?", EQUATION, EQUATION) == []
    assert find_leaks("Look at `(x - 5)^2` again.", SQUARE, SQUARE) == []


def test_a_wrong_form_or_a_general_rule_is_fine() -> None:
    assert find_leaks("You wrote `x^2 - 25`.", SQUARE, SQUARE) == []
    assert find_leaks("Recall `(a + b)^2 = a^2 + 2ab + b^2`.", SQUARE, SQUARE) == []


def test_the_form_comes_from_the_line_before_too() -> None:
    assert find_leaks(
        "Then `2x + 6`.", "2(x + 3) = 10", "2(x + 1) + 4"
    )  # expand of the line before
    assert find_leaks("Then `2x + 6`.", "x = 1", "2(x + 3)")


def test_the_reasons_are_reported_once() -> None:
    reasons = find_leaks("`x = 3` and again `x = 3`", EQUATION, EQUATION)
    assert len(reasons) == 1 and "x = 3" in reasons[0]


@pytest.mark.parametrize("text", ["", "no math here", "`not math at all !!`", "`x +`"])
def test_text_without_readable_math_does_not_leak(text: str) -> None:
    assert find_leaks(text, EQUATION, EQUATION) == []


def test_an_unparsable_problem_does_not_crash() -> None:
    assert find_leaks("`x = 3`", "solve it please", "also prose") == []
