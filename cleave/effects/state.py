"""Neutral per-layer state consumed by EffectRuntime."""

from __future__ import annotations

from typing import Protocol


class LayerEffectState(Protocol):
    stem: str
    effects: dict[str, dict[str, int]]
    opacity_pct: int
