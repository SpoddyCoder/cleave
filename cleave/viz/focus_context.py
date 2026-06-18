"""Shared focus and view-state access for tuning sub-controllers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from cleave.viz.overlay import TuningViewState


@dataclass(frozen=True)
class FocusContext:
    get_focus_index: Callable[[], int]
    set_focus_index: Callable[[int], None]
    build_view_state: Callable[..., TuningViewState]
    is_paused: Callable[[], bool]
