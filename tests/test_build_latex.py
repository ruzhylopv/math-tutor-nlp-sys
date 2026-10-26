import pytest

from evals.builders.latex import latex_to_text


@pytest.mark.parametrize(
    ("latex", "plain"),
    [
        ("2x^2 +9x - 35", "2x^2 +9x - 35"),
        ("x^{2}", "x^(2)"),
        (r"\frac{1}{2}x", "((1)/(2))x"),
        (r"\dfrac{a+1}{b}", "((a+1)/(b))"),
        (r"\sqrt{x+7}", "sqrt(x+7)"),
        (r"2\cdot 3", "2 * 3"),
        (r"\left(x+1\right)^2", "(x+1)^2"),
        (r"\boxed{-30}", "(-30)"),
        (r"3x\,+\,2", "3x + 2"),
        (r"\frac{\sqrt{2}}{3}", "((sqrt(2))/(3))"),
    ],
)
def test_supported_latex_is_converted(latex: str, plain: str) -> None:
    assert latex_to_text(latex) == plain


@pytest.mark.parametrize(
    "latex",
    [r"\text{so}", r"x \pm 2", r"\pi r^2", r"x \le 3", r"\sqrt[3]{8}", r"\frac{1}{", "x}", ""],
)
def test_unsupported_latex_is_dropped_not_guessed(latex: str) -> None:
    assert latex_to_text(latex) is None
