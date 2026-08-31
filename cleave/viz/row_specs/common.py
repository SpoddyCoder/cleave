"""Shared row-spec helpers used by more than one domain module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.viz.row_kinds import RowDescriptor
from cleave.viz.row_sections import apply_expand_toggle

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls


def apply_expand_subheader(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    apply_expand_toggle(
        controls, desc.kind, desc.slot, forward, card=desc.card
    )


def noop_horizontal(
    _controls: TuningControls,
    _desc: RowDescriptor,
    _forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    return
