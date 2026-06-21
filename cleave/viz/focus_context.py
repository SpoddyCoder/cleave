"""Shared focus and view-state access for tuning sub-controllers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from cleave.viz.overlay import TuningViewState
from cleave.viz.row_semantics import RowDescriptor


@dataclass(frozen=True)
class FocusContext:
    get_focus_descriptor: Callable[[], RowDescriptor]
    set_focus_descriptor: Callable[[RowDescriptor], None]
    build_view_state: Callable[..., TuningViewState]
    is_paused: Callable[[], bool]
