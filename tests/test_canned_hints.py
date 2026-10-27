import re

import pytest

from tutor.tools.canned_hints import MAX_LEVEL, canned_hint


def test_every_level_has_its_own_hint() -> None:
    assert len({canned_hint(level) for level in range(1, MAX_LEVEL + 1)}) == MAX_LEVEL


def test_a_level_outside_the_range_is_clamped() -> None:
    assert canned_hint(0) == canned_hint(1) == canned_hint(-3)
    assert canned_hint(9) == canned_hint(MAX_LEVEL)


@pytest.mark.parametrize("level", range(1, MAX_LEVEL + 1))
def test_a_canned_hint_has_no_math_that_could_leak(level: int) -> None:
    assert not re.search(r"[0-9=^`]", canned_hint(level))
