"""Render pattern-mask row mutations for live tuning."""

from __future__ import annotations

import random

from cleave.config_schema.render import (
    PATTERN_MASK_TRANSITION_STEP,
    PATTERN_MASK_TRANSITION_STEP_LARGE,
    PATTERN_MASK_TRANSITION_UNITS,
    PATTERN_MASK_TYPES,
    PatternMaskTransitionUnit,
    PatternMaskType,
    clamp_pattern_mask_density,
    clamp_pattern_mask_feather_pct,
    clamp_pattern_mask_transition,
    pattern_mask_transition_steps,
)
from cleave.choice import step_choice
from cleave.pattern_mask_transition import transition_seconds
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
        pm = self.session.pattern_mask
        pm.transition = clamp_pattern_mask_transition(transition, pm.transition_unit)

    def step_transition(self, *, forward: bool, large: bool) -> None:
        """The next length: one step of beats or bars, or 0.1s (1s when large)."""
        pm = self.session.pattern_mask
        steps = pattern_mask_transition_steps(pm.transition_unit)
        if steps is not None:
            index = steps.index(clamp_pattern_mask_transition(pm.transition, pm.transition_unit))
            index = max(0, min(len(steps) - 1, index + (1 if forward else -1)))
            pm.transition = steps[index]
            return
        step = PATTERN_MASK_TRANSITION_STEP_LARGE if large else PATTERN_MASK_TRANSITION_STEP
        self.set_transition(pm.transition + (step if forward else -step))

    def set_transition_unit(self, unit: PatternMaskTransitionUnit) -> None:
        """Count the transition in *unit*, keeping its length as near as it goes."""
        pm = self.session.pattern_mask
        if unit == pm.transition_unit:
            return
        tempo = self.session.song_tempo
        seconds = transition_seconds(pm.transition, pm.transition_unit, tempo)
        per_unit = transition_seconds(1.0, unit, tempo)
        pm.transition_unit = unit
        pm.transition = clamp_pattern_mask_transition(
            seconds / per_unit if per_unit > 0.0 else seconds, unit
        )

    def step_transition_unit(self, *, delta: int) -> None:
        pm = self.session.pattern_mask
        self.set_transition_unit(
            step_choice(PATTERN_MASK_TRANSITION_UNITS, pm.transition_unit, delta)
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
