"""Choosing one value from a fixed list of options.

Every choice clamps at its ends. Ordered lists run low to high, so a forward
step means more. ``choice_kind`` picks how a choice is shown from its option
count alone.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import TypeVar

T = TypeVar("T")

# Choices with this many options or fewer show as segments; more show as a combo.
SEGMENT_MAX_OPTIONS = 3


class ChoiceKind(Enum):
    SEGMENT = "segment"
    COMBO = "combo"


def choice_kind(option_count: int) -> ChoiceKind:
    if option_count <= SEGMENT_MAX_OPTIONS:
        return ChoiceKind.SEGMENT
    return ChoiceKind.COMBO


def choice_index(options: Sequence[T], current: T) -> int:
    """Index of ``current``. An unknown value counts as the first option."""
    try:
        return list(options).index(current)
    except ValueError:
        return 0


def step_index(index: int, count: int, delta: int) -> int:
    """``index`` moved by ``delta``, clamped to ``0 .. count - 1``."""
    if count <= 0:
        return 0
    return max(0, min(count - 1, index + delta))


def step_choice(options: Sequence[T], current: T, delta: int) -> T:
    """The option ``delta`` places from ``current``, stopping at either end."""
    return options[step_index(choice_index(options, current), len(options), delta)]


def at_start(options: Sequence[T], current: T) -> bool:
    return choice_index(options, current) == 0


def at_end(options: Sequence[T], current: T) -> bool:
    return choice_index(options, current) >= len(options) - 1
