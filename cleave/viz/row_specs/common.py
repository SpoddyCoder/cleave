"""Shared row-spec helpers used by more than one domain module."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, TypeVar

from cleave.choice import choice_index
from cleave.viz.row_kinds import RowDescriptor
from cleave.viz.row_spec import ChoiceJump, RowChoice
from cleave.viz.tuning_view_state import TuningViewState

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

T = TypeVar("T")


def on_off_text(value: bool) -> str:
    return "on" if value else "off"


def lock_text(locked: bool) -> str:
    return "locked" if locked else "unlocked"


def noop_horizontal(
    _controls: TuningControls,
    _desc: RowDescriptor,
    _forward: bool,
    _large: bool,
) -> None:
    return


def bool_choice(
    value: Callable[[TuningViewState, RowDescriptor], bool],
    display: Callable[[bool], str] = on_off_text,
) -> RowChoice:
    """Two options, false then true, so Right turns the value on."""
    return RowChoice(
        labels=lambda: (display(False), display(True)),
        index=lambda state, desc: int(bool(value(state, desc))),
    )


def options_choice(
    options: Callable[[], Sequence[T]] | Sequence[T],
    value: Callable[[TuningViewState, RowDescriptor], T],
    display: Callable[[T], str] = str,
    *,
    jump: ChoiceJump | None = None,
) -> RowChoice:
    """One of ``options`` (a sequence, or a function for a list found at run time)."""

    def resolved() -> Sequence[T]:
        return options() if callable(options) else options

    return RowChoice(
        labels=lambda: tuple(display(o) for o in resolved()),
        index=lambda state, desc: choice_index(resolved(), value(state, desc)),
        jump=jump,
    )
