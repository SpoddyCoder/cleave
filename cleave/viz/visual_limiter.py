"""Closed-loop visual limiter: duck lowest-priority hot layers when busy.

When enabled and timeline levels apply, measures post-composite busyness
(mean luma + frame delta) after the HDR display shoulder, decides ducks for
the next frame, and multiplies ``StemLayer.limiter_gain`` into opacity.
Persisted knobs live under ``timeline.limiter``; attack / duck / delta stay
fixed module constants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from cleave.config_schema import (
    DEFAULT_VISUAL_LIMITER_RELEASE,
    DEFAULT_VISUAL_LIMITER_THRESHOLD,
    visual_limiter_release_hold_sec,
    visual_limiter_threshold_off,
)
from cleave.cue_roles import CueRole
from cleave.timeline import LEVEL_EPS, empty_lane, lane_role_at
from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.layer_visibility import timeline_levels_apply

if TYPE_CHECKING:
    from cleave.gl_compositor import GlCompositor
    from cleave.gl_post_process import GlPostProcess
    from cleave.viz.app import VisualizerCore
    from cleave.viz.layer import StemLayer
    from cleave.viz.session import TuningSession, VisualLimiterRuntime

# Busyness = mean_luma + DELTA_WEIGHT * mean_abs_delta (both in [0, 1]).
# ON / OFF / release defaults match schema; runtime values come from session.
THRESHOLD_ON = DEFAULT_VISUAL_LIMITER_THRESHOLD
THRESHOLD_OFF = visual_limiter_threshold_off(THRESHOLD_ON)
DELTA_WEIGHT = 0.85
DUCK_GAIN = 0.50
RELEASE_RAMP_SEC = DEFAULT_VISUAL_LIMITER_RELEASE
RELEASE_SEC = visual_limiter_release_hold_sec(RELEASE_RAMP_SEC)
ATTACK_SEC = 0.15
SEEK_JUMP_SEC = 0.25
GRID_WIDTH = 32
GRID_HEIGHT = 18

# Lower rank is ducked first: bed < accent < pulse < lead.
_ROLE_RANK: dict[CueRole, int] = {
    "bed": 0,
    "accent": 1,
    "pulse": 2,
    "lead": 3,
}
_DEFAULT_ROLE_RANK = _ROLE_RANK["pulse"]


@dataclass(frozen=True)
class VisualLimiterParams:
    threshold_on: float = THRESHOLD_ON
    threshold_off: float = THRESHOLD_OFF
    release_ramp_sec: float = RELEASE_RAMP_SEC
    release_sec: float = RELEASE_SEC

    @classmethod
    def from_runtime(cls, limiter: VisualLimiterRuntime) -> VisualLimiterParams:
        ramp = float(limiter.release)
        return cls(
            threshold_on=float(limiter.threshold),
            threshold_off=visual_limiter_threshold_off(limiter.threshold),
            release_ramp_sec=ramp,
            release_sec=visual_limiter_release_hold_sec(ramp),
        )


@dataclass(frozen=True)
class HotLayerRef:
    slot: str
    role_rank: int
    timeline_level: float
    z_index: int


@dataclass
class VisualLimiterState:
    prev_luma: np.ndarray | None = None
    gains: dict[str, float] = field(default_factory=dict)
    under_off_since: float | None = None
    last_t_sec: float | None = None
    controller_t_sec: float | None = None

    def reset(self) -> None:
        self.prev_luma = None
        self.gains.clear()
        self.under_off_since = None
        self.last_t_sec = None
        self.controller_t_sec = None

    def gain_for(self, slot: str) -> float:
        return self.gains.get(slot, 1.0)

    def apply_to_layers(self, layers_by_slot: dict[str, StemLayer]) -> None:
        for slot, layer in layers_by_slot.items():
            layer.limiter_gain = self.gain_for(slot)

    def clear_layer_gains(self, layers_by_slot: dict[str, StemLayer]) -> None:
        for layer in layers_by_slot.values():
            layer.limiter_gain = 1.0


def visual_limiter_active(session: TuningSession) -> bool:
    """True when the limiter may duck layers (timeline levels driving opacity)."""
    if is_preset_curation_mode(session):
        return False
    if session.solo_slot is not None:
        return False
    tl = session.timeline
    if not tl.enabled:
        return False
    if not tl.limiter.enabled:
        return False
    if tl.recording or tl.preview_active:
        return False
    return True


def role_rank(role: CueRole | None) -> int:
    if role is None:
        return _DEFAULT_ROLE_RANK
    return _ROLE_RANK.get(role, _DEFAULT_ROLE_RANK)


def busyness(mean_luma: float, mean_abs_delta: float) -> float:
    return float(mean_luma) + DELTA_WEIGHT * float(mean_abs_delta)


def pick_victim(
    hot: list[HotLayerRef],
    gains: dict[str, float],
) -> str | None:
    """Lowest-priority hot layer still above the duck floor."""
    candidates = [
        layer
        for layer in hot
        if gains.get(layer.slot, 1.0) > DUCK_GAIN + LEVEL_EPS
    ]
    if not candidates:
        return None
    chosen = min(
        candidates,
        key=lambda layer: (layer.role_rank, layer.timeline_level, layer.z_index),
    )
    return chosen.slot


def collect_hot_layers(
    session: TuningSession,
    layers_by_slot: dict[str, StemLayer],
    t_sec: float,
) -> list[HotLayerRef]:
    hot: list[HotLayerRef] = []
    for z_index, slot in enumerate(session.layer_z_order):
        if not timeline_levels_apply(session, slot):
            continue
        layer = layers_by_slot.get(slot)
        if layer is None or layer.timeline_level <= LEVEL_EPS:
            continue
        lane = session.timeline.lanes.get(slot) or empty_lane()
        role = lane_role_at(lane, t_sec)
        hot.append(
            HotLayerRef(
                slot=slot,
                role_rank=role_rank(role),
                timeline_level=float(layer.timeline_level),
                z_index=z_index,
            )
        )
    return hot


def reset_if_seek(state: VisualLimiterState, t_sec: float) -> bool:
    """Clear limiter memory on large playhead jumps. Returns True when reset."""
    jumped = (
        state.last_t_sec is not None
        and abs(t_sec - state.last_t_sec) > SEEK_JUMP_SEC
    )
    if jumped:
        state.reset()
    state.last_t_sec = t_sec
    return jumped


def _playhead_dt(state: VisualLimiterState, t_sec: float) -> float:
    prev = state.controller_t_sec
    state.controller_t_sec = t_sec
    if prev is None:
        return 0.0
    return max(0.0, t_sec - prev)


def _ramp_gain_toward(current: float, target: float, dt: float, duration_sec: float) -> float:
    """Move ``current`` toward ``target`` over ``duration_sec`` of playhead time."""
    if duration_sec <= LEVEL_EPS or dt <= LEVEL_EPS:
        return current
    span = abs(1.0 - DUCK_GAIN)
    if span <= LEVEL_EPS:
        return target
    step = span * (dt / duration_sec)
    if current > target:
        return max(target, current - step)
    return min(target, current + step)


def _ramp_release(
    state: VisualLimiterState, dt: float, *, release_ramp_sec: float
) -> None:
    finished: list[str] = []
    for slot, gain in state.gains.items():
        new_gain = _ramp_gain_toward(gain, 1.0, dt, release_ramp_sec)
        if new_gain >= 1.0 - LEVEL_EPS:
            finished.append(slot)
        else:
            state.gains[slot] = new_gain
    for slot in finished:
        del state.gains[slot]
    if not state.gains:
        state.under_off_since = None


def update_limiter_state(
    state: VisualLimiterState,
    *,
    mean_luma: float,
    mean_abs_delta: float,
    t_sec: float,
    hot: list[HotLayerRef],
    params: VisualLimiterParams | None = None,
) -> None:
    """Pure controller step from measured busyness and hot-layer refs."""
    knobs = params if params is not None else VisualLimiterParams()
    dt = _playhead_dt(state, t_sec)
    score = busyness(mean_luma, mean_abs_delta)
    if score > knobs.threshold_on:
        state.under_off_since = None
        victim = pick_victim(hot, state.gains)
        if victim is not None:
            current = state.gains.get(victim, 1.0)
            new_gain = _ramp_gain_toward(current, DUCK_GAIN, dt, ATTACK_SEC)
            if new_gain < 1.0 - LEVEL_EPS:
                state.gains[victim] = new_gain
        return

    if score < knobs.threshold_off:
        if state.under_off_since is None:
            state.under_off_since = t_sec
        elif t_sec - state.under_off_since >= knobs.release_sec:
            _ramp_release(state, dt, release_ramp_sec=knobs.release_ramp_sec)
        return

    state.under_off_since = None


def read_luma_grid(
    compositor: GlCompositor,
    post_process: GlPostProcess,
    *,
    grid_width: int = GRID_WIDTH,
    grid_height: int = GRID_HEIGHT,
) -> np.ndarray:
    """Downsampled display-referred luma grid from the content FBO."""
    return post_process.read_luma_grid(
        compositor.content_texture_id,
        compositor.content_width,
        compositor.content_height,
        grid_width=grid_width,
        grid_height=grid_height,
    )


def metrics_from_grid(
    state: VisualLimiterState,
    luma_grid: np.ndarray,
) -> tuple[float, float]:
    mean_luma = float(np.mean(luma_grid))
    if state.prev_luma is None or state.prev_luma.shape != luma_grid.shape:
        mean_abs_delta = 0.0
    else:
        mean_abs_delta = float(np.mean(np.abs(luma_grid - state.prev_luma)))
    state.prev_luma = np.array(luma_grid, dtype=np.float32, copy=True)
    return mean_luma, mean_abs_delta


def apply_visual_limiter_gains(
    runtime: VisualizerCore,
    *,
    blank_visualizers: bool = False,
) -> None:
    """Write limiter gains onto layers before opacity is applied this frame."""
    state = runtime.visual_limiter
    if not isinstance(state, VisualLimiterState):
        return
    session = runtime.seed.session
    if blank_visualizers or not visual_limiter_active(session):
        state.reset()
        state.clear_layer_gains(runtime.layers_by_slot)
        return
    state.apply_to_layers(runtime.layers_by_slot)


def observe_frame_busyness(
    core: VisualizerCore,
    t_sec: float,
    session: TuningSession,
    *,
    blank_visualizers: bool = False,
) -> None:
    """Sample content FBO and update limiter state for the next frame."""
    if blank_visualizers or not visual_limiter_active(session):
        return
    state = core.visual_limiter
    if not isinstance(state, VisualLimiterState):
        return
    width = core.compositor.content_width
    height = core.compositor.content_height
    if not isinstance(width, int) or not isinstance(height, int):
        return
    if width <= 0 or height <= 0:
        return
    reset_if_seek(state, t_sec)
    luma_grid = read_luma_grid(core.compositor, core.post_process)
    mean_luma, mean_abs_delta = metrics_from_grid(state, luma_grid)
    hot = collect_hot_layers(session, core.layers_by_slot, t_sec)
    update_limiter_state(
        state,
        mean_luma=mean_luma,
        mean_abs_delta=mean_abs_delta,
        t_sec=t_sec,
        hot=hot,
        params=VisualLimiterParams.from_runtime(session.timeline.limiter),
    )
