"""Display-only LaTeX for tutor replies: backtick math becomes `$...$`, the rest is left alone."""

import pytest

from tutor.ui import render_math


@pytest.mark.parametrize(
    ("fragment", "latex"),
    [
        ("x^2 + 5x + 6 = 0", "x^{2}+5x+6=0"),
        ("x^(n+1)", "x^{n+1}"),
        ("2^-1", "2^{-1}"),
        ("sqrt(x^2 + 1)", r"\sqrt{x^{2}+1}"),
        ("abs(2x - 3)", r"\left|2x-3\right|"),
        ("2*3", r"2\cdot 3"),
        ("+-4", r"\pm 4"),
        ("(x + 1)/(x - 1)", r"\frac{x+1}{x-1}"),
        ("3/4", r"\frac{3}{4}"),
        ("(2x)^2/4", r"\frac{\left(2x\right)^{2}}{4}"),
        ("x <= 5", r"x\le 5"),
        ("x >= 5", r"x\ge 5"),
        ("x != 5", r"x\ne 5"),
        ("x = 2 or x = 3", r"x=2\text{ or }x=3"),
        ("3(x + 2)", r"3\left(x+2\right)"),
        ("0.5x", "0.5x"),
    ],
)
def test_a_math_fragment_becomes_inline_latex(fragment: str, latex: str) -> None:
    assert render_math(f"Look at `{fragment}`.") == f"Look at ${latex}$."


def test_nested_brackets_are_converted_inside_out() -> None:
    assert render_math("`sqrt((x + 1)/(x^2))`") == r"$\sqrt{\frac{x+1}{x^{2}}}$"


def test_the_form_is_kept_as_written_not_simplified() -> None:
    assert render_math("`x + 2 - 2`") == "$x+2-2$"


@pytest.mark.parametrize(
    "fragment", ["factor", "(x + 1", "x + 1)", "x²", "2^", "/3", "sqrt x", "x/-2", "a_1", "x$"]
)
def test_a_fragment_that_is_not_plain_math_keeps_its_backticks(fragment: str) -> None:
    assert render_math(f"See `{fragment}` here.") == f"See `{fragment}` here."


def test_a_dollar_sign_in_the_prose_is_escaped() -> None:
    assert render_math("It costs $5, so `2x = 5`.") == r"It costs \$5, so $2x=5$."


def test_prose_without_math_is_unchanged() -> None:
    text = "Good start! Which side did you change first?"
    assert render_math(text) == text
