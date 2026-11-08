"""Render pattern-mask row mutations for live tuning."""

from __future__ import annotations

import random

from cleave.config_schema.render import (
    PATTERN_MASK_TYPES,
    PatternMaskType,
    clamp_pattern_mask_density,
    clamp_pattern_mask_feather_pct,
    clamp_pattern_mask_transition,
)
from cleave.choice import step_choice
from cleave.viz.session import TuningSession


class PatternMaskControls:
    """Mutations for render pattern-mask rows."""

    def __init__(self, session: TuningSession) -> None:
        self.session = session

    def set_enabled(self, enabled: bool) -> None:
        pm = self.session.pattern_mask
        if pm.enabled == enabled:
            return
        pm.enabled = enabled

    def set_density(self, density: float) -> None:
        self.session.pattern_mask.density = clamp_pattern_mask_density(density)

    def set_invert(self, invert: bool) -> None:
        self.session.pattern_mask.invert = bool(invert)

    def set_transition(self, transition: float) -> None:
        self.session.pattern_mask.transition = clamp_pattern_mask_transition(
            transition
        )

    def step_invert(self, *, forward: bool) -> None:
        self.session.pattern_mask.invert = forward

    def step_type(self, *, delta: int) -> None:
        pm = self.session.pattern_mask
        pm.type = step_choice(PATTERN_MASK_TYPES, pm.type, delta)

    def set_type(self, mask_type: PatternMaskType) -> None:
        if mask_type not in PATTERN_MASK_TYPES:
            raise ValueError(f"unknown pattern mask type: {mask_type!r}")
        self.session.pattern_mask.type = mask_type

    def set_feather_pct(self, feather_pct: int) -> None:
        self.session.pattern_mask.feather_pct = clamp_pattern_mask_feather_pct(
            feather_pct
        )

    def set_seed(self, seed: int) -> None:
        self.session.pattern_mask.seed = int(seed)

    def respin_seed(self) -> None:
        self.session.pattern_mask.seed = random.randint(0, 2_147_483_647)

    def toggle_locked(self) -> None:
        pm = self.session.pattern_mask
        pm.locked = not pm.locked
