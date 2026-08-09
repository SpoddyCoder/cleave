"""Render pattern-mask row mutations for live tuning."""

from __future__ import annotations

import random

from cleave.config_schema import (
    PATTERN_MASK_MODES,
    PATTERN_MASK_TYPES,
    PatternMaskMode,
    PatternMaskType,
    clamp_pattern_mask_density,
)
from cleave.pattern_mask import cycle_pattern_mask_invert, cycle_pattern_mask_mode
from cleave.viz.session import TuningSession


class RenderPatternMaskControls:
    """Mutations for render pattern-mask rows."""

    def __init__(self, session: TuningSession) -> None:
        self.session = session

    def set_expanded(self, expanded: bool) -> None:
        pm = self.session.render_pattern_mask
        if pm.expanded == expanded:
            return
        pm.expanded = expanded

    def set_enabled(self, enabled: bool) -> None:
        pm = self.session.render_pattern_mask
        if pm.enabled == enabled:
            return
        pm.enabled = enabled
        if not enabled:
            pm.expanded = False

    def set_density(self, density: float) -> None:
        self.session.render_pattern_mask.density = clamp_pattern_mask_density(density)

    def set_invert(self, invert: bool) -> None:
        self.session.render_pattern_mask.invert = bool(invert)

    def cycle_invert(self, *, forward: bool) -> None:
        pm = self.session.render_pattern_mask
        pm.invert = cycle_pattern_mask_invert(pm.invert, forward=forward)

    def cycle_type(self, *, forward: bool) -> None:
        options = PATTERN_MASK_TYPES
        pm = self.session.render_pattern_mask
        try:
            index = options.index(pm.type)
        except ValueError:
            index = 0
        delta = 1 if forward else -1
        pm.type = options[(index + delta) % len(options)]

    def set_type(self, mask_type: PatternMaskType) -> None:
        if mask_type not in PATTERN_MASK_TYPES:
            raise ValueError(f"unknown pattern mask type: {mask_type!r}")
        self.session.render_pattern_mask.type = mask_type

    def cycle_mode(self, *, forward: bool) -> None:
        pm = self.session.render_pattern_mask
        pm.mode = cycle_pattern_mask_mode(pm.mode, forward=forward)  # type: ignore[assignment]

    def set_mode(self, mode: PatternMaskMode) -> None:
        if mode not in PATTERN_MASK_MODES:
            raise ValueError(f"unknown pattern mask mode: {mode!r}")
        self.session.render_pattern_mask.mode = mode

    def set_seed(self, seed: int) -> None:
        self.session.render_pattern_mask.seed = int(seed)

    def respin_seed(self) -> None:
        self.session.render_pattern_mask.seed = random.randint(0, 2_147_483_647)

    def toggle_locked(self) -> None:
        pm = self.session.render_pattern_mask
        pm.locked = not pm.locked
