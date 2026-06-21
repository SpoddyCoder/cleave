"""Shared focus and view-state access for tuning sub-controllers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from cleave.viz.focus_nav import FocusCursor
from cleave.viz.overlay import TuningViewState


@dataclass(frozen=True)
class FocusContext:
    get_focus_cursor: Callable[[], FocusCursor]
    set_focus_cursor: Callable[[FocusCursor], None]
    build_view_state: Callable[..., TuningViewState]
    is_paused: Callable[[], bool]
