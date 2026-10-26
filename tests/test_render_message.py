import random

import pytest

from evals.builders.render_message import (
    notate,
    render_message,
    to_latex,
    to_spoken,
    to_unicode,
    typo,
)


@pytest.mark.parametrize(
    ("plain", "latex"),
    [
        ("x^2 + 1", "x^{2} + 1"),
        ("2^(x+1)", "2^{x+1}"),
        ("sqrt(x+4) = 3", "\\sqrt{x+4} = 3"),
        ("(x+1)/(2) = 3", "\\frac{x+1}{2} = 3"),
        ("3 * 4", "3 \\cdot 4"),
        ("(a + b)(a - b)", "(a + b)(a - b)"),
        ("x^-2", "x^{-2}"),
        ("x^2y", "x^{2}y"),
        ("a^2b^2", "a^{2}b^{2}"),
        ("3^2x", "3^{2}x"),
        ("x^2.5", "x^{2.5}"),
        ("(a)/(b)^2", "\\frac{a}{b^{2}}"),
    ],
)
def test_latex(plain: str, latex: str) -> None:
    assert to_latex(plain) == latex


def test_latex_with_an_unbalanced_bracket_does_not_fail() -> None:
    assert to_latex("(x + 1") == "(x + 1"


def test_unicode() -> None:
    assert to_unicode("x^2 + y^3") == "x² + y³"
    assert to_unicode("3 * 4") == "3 × 4"
    assert to_unicode("sqrt(x)") == "√(x)"
    assert to_unicode("a - b") == "a − b"
    assert to_unicode("x^2.5") == "x^2.5"  # a decimal exponent is not a square
    assert to_unicode("x^20") == "x^20"  # only the small powers have a character


def test_spoken() -> None:
    assert to_spoken("2x + 1 = 11") == "2x plus 1 equals 11"
    assert to_spoken("x^2 - 4") == "x squared minus 4"
    assert to_spoken("3 * 4") == "3 times 4"


def test_notate_wraps_latex_only() -> None:
    assert notate("x^2", "latex") == "$x^{2}$"
    assert notate("x^2", "latex", inline=False) == "x^{2}"
    assert notate("x^2", "ascii") == "x^2"


def test_typo_swaps_two_letters_of_a_long_word_and_leaves_the_rest() -> None:
    rng = random.Random(0)
    changed = typo("correctly", rng)
    assert changed != "correctly" and sorted(changed) == sorted("correctly")
    assert typo("then", rng) == "then"
    assert typo("x2y3z", rng) == "x2y3z"


def _render(**overrides: object) -> str:
    options: dict[str, object] = {
        "kind": "equation",
        "layout": "plain",
        "notation": "ascii",
        "chatty": False,
        "typos": False,
        "rng": random.Random(1),
    }
    options.update(overrides)
    return render_message("2x = 4", ["x = 2"], **options)  # type: ignore[arg-type]


def test_plain_layout_puts_the_problem_and_each_step_on_a_line() -> None:
    lines = _render().split("\n")
    assert len(lines) == 2 and lines[0].endswith("2x = 4") and lines[1] == "x = 2"


def test_numbered_layout_numbers_each_step() -> None:
    assert "1" in _render(layout="numbered").split("\n")[1]


def test_one_line_layout_has_a_single_line() -> None:
    assert "\n" not in _render(layout="one_line")


def test_connectors_layout_works_with_one_step() -> None:
    assert "x = 2" in _render(layout="connectors")


def test_no_problem_leaves_only_the_steps() -> None:
    message = render_message(
        None,
        ["x = 2", "y = 3"],
        kind="equation",
        layout="plain",
        notation="ascii",
        chatty=False,
        typos=False,
        rng=random.Random(1),
    )
    assert message == "x = 2\ny = 3"


def test_chatty_adds_a_frame_without_touching_the_math() -> None:
    lines = _render(chatty=True).split("\n")
    assert len(lines) == 4 and lines[2] == "x = 2"


def test_typos_never_change_math_tokens() -> None:
    for seed in range(30):
        message = _render(typos=True, chatty=True, rng=random.Random(seed))
        assert "x = 2" in message and "2x = 4" in message


def test_typos_never_change_the_spoken_operators() -> None:
    for seed in range(100):
        message = _render(notation="spoken", typos=True, chatty=True, rng=random.Random(seed))
        assert "2x equals 4" in message and "x equals 2" in message


def test_the_same_seed_gives_the_same_message() -> None:
    assert _render(chatty=True, typos=True) == _render(chatty=True, typos=True)
