"""Live render post-FX sync handlers for tuning controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RenderPostFxBindings:
    on_highlight_rolloff_apply_mode_change: Callable[[str, str], None] | None = None
    is_paused: Callable[[], bool] | None = None
