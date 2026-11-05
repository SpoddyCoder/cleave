"""Shared row-spec helpers used by more than one domain module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.viz.row_kinds import RowDescriptor

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls


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
