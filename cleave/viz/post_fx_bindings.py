"""Live render post-FX sync handlers for tuning controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class PostFxBindings:
    on_highlight_rolloff_per_layer_change: Callable[[bool], None] | None = None
    on_chroma_boost_per_layer_change: Callable[[bool], None] | None = None
    is_paused: Callable[[], bool] | None = None
