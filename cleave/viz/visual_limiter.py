"""Feed-forward visual limiter: proportional compressor on stacked layer opacity.

When enabled, measures post-composite busyness (mean luma + frame delta) after
the HDR display shoulder, runs a gain-compensated envelope follower with
ratio-based gain reduction, and multiplies ``StemLayer.limiter_gain`` into
opacity. Detection is always composite busyness. Cue roles weight which hot
layers absorb the cut when the timeline is on; with the timeline off every
enabled composited layer ducks at the pulse weight. Persisted knobs live under
``render.post_fx.limiter``. The Post FX master and solo do not gate this path.
Attack and delta weight stay fixed module constants.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from cleave.config_schema.render import (
    DEFAULT_VISUAL_LIMITER_RATIO,
    DEFAULT_VISUAL_LIMITER_RELEASE,
    DEFAULT_VISUAL_LIMITER_THRESHOLD,
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
    from cleave.viz.session import (
        TimelineRuntime,
        TuningSession,
        VisualLimiterRuntime,
    )

# Busyness = mean_luma + DELTA_WEIGHT * mean_abs_delta (both in [0, 1]).
DEFAULT_THRESHOLD = DEFAULT_VISUAL_LIMITER_THRESHOLD
DEFAULT_RATIO = DEFAULT_VISUAL_LIMITER_RATIO
DEFAULT_RELEASE_TC = DEFAULT_VISUAL_LIMITER_RELEASE
DELTA_WEIGHT = 0.85
ATTACK_TC = 0.08
GAIN_FLOOR = 0.10
SEEK_JUMP_SEC = 0.25
GRID_WIDTH = 32
GRID_HEIGHT = 18

# Lower rank absorbs more reduction: bed < accent < pulse < lead.
_ROLE_RANK: dict[CueRole, int] = {
    "bed": 0,
    "accent": 1,
    "pulse": 2,
    "lead": 3,
}
_DEFAULT_ROLE_RANK = _ROLE_RANK["pulse"]
_PRIORITY_WEIGHT_BY_RANK: tuple[float, ...] = (1.0, 0.7, 0.4, 0.15)


@dataclass(frozen=True)
class LimiterFrameState:
    timeline: TimelineRuntime
    limiter: VisualLimiterRuntime
    solo_slot: str | None
    editor_mode: str
    layer_z_order: Sequence[str]

    @classmethod
    def from_session(cls, session: TuningSession) -> LimiterFrameState:
        return cls(
            timeline=session.timeline,
            limiter=session.render_post_fx.limiter,
            solo_slot=session.solo_slot,
            editor_mode=session.settings.editor_mode,
            layer_z_order=session.layer_z_order,
        )


@dataclass(frozen=True)
class VisualLimiterParams:
    threshold: float = DEFAULT_THRESHOLD
    ratio: float = DEFAULT_RATIO
    release_tc: float = DEFAULT_RELEASE_TC

    @classmethod
    def from_runtime(cls, limiter: VisualLimiterRuntime) -> VisualLimiterParams:
        return cls(
            threshold=float(limiter.threshold),
            ratio=float(limiter.ratio),
            release_tc=float(limiter.release),
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
    envelope: float = 0.0
    last_t_sec: float | None = None
    controller_t_sec: float | None = None

    def reset(self) -> None:
        self.prev_luma = None
        self.gains.clear()
        self.envelope = 0.0
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


def visual_limiter_active(frame: LimiterFrameState) -> bool:
    """True when the limiter may duck layers.

    Composite busyness is the signal whether or not the timeline is enabled.
    Preset curation, solo, recording, and timeline preview stay idle. The Post
    FX master and post-FX solo do not gate this.
    """
    if is_preset_curation_mode(frame.editor_mode):
        return False
    if frame.solo_slot is not None:
        return False
    if not frame.limiter.enabled:
        return False
    tl = frame.timeline
    if tl.recording or tl.preview_active:
        return False
    return True


def role_rank(role: CueRole | None) -> int:
    if role is None:
        return _DEFAULT_ROLE_RANK
    return _ROLE_RANK.get(role, _DEFAULT_ROLE_RANK)


def priority_weight(role_rank_value: int) -> float:
    if 0 <= role_rank_value < len(_PRIORITY_WEIGHT_BY_RANK):
        return _PRIORITY_WEIGHT_BY_RANK[role_rank_value]
    return _PRIORITY_WEIGHT_BY_RANK[_DEFAULT_ROLE_RANK]


def busyness(mean_luma: float, mean_abs_delta: float) -> float:
    return float(mean_luma) + DELTA_WEIGHT * float(mean_abs_delta)


def compensated_busyness(
    raw_busyness: float,
    gains: dict[str, float],
) -> float:
    if not gains:
        return raw_busyness
    avg_gain = sum(gains.values()) / len(gains)
    return raw_busyness / max(avg_gain, GAIN_FLOOR)


def target_bus_gain(envelope: float, *, threshold: float, ratio: float) -> float:
    if envelope <= threshold + LEVEL_EPS:
        return 1.0
    over_db = 20.0 * math.log10(envelope / threshold)
    reduce_db = over_db * (1.0 - 1.0 / ratio)
    gain = 10.0 ** (-reduce_db / 20.0)
    return max(gain, GAIN_FLOOR)


def layer_gain_from_target(target_gain: float, weight: float) -> float:
    return 1.0 - weight * (1.0 - target_gain)


def distribute_gain(
    state: VisualLimiterState,
    hot: list[HotLayerRef],
    target_gain: float,
) -> None:
    hot_slots = {layer.slot for layer in hot}
    for slot in list(state.gains):
        if slot not in hot_slots:
            del state.gains[slot]

    if target_gain >= 1.0 - LEVEL_EPS:
        state.gains.clear()
        return

    for layer in hot:
        weight = priority_weight(layer.role_rank)
        gain = layer_gain_from_target(target_gain, weight)
        if gain >= 1.0 - LEVEL_EPS:
            state.gains.pop(layer.slot, None)
        else:
            state.gains[layer.slot] = gain


def _pre_limiter_opacity(layer: StemLayer) -> float:
    """Opacity before limiter gain, so a ducked layer stays in the hot set."""
    gain = float(layer.limiter_gain)
    opacity = float(layer.fbo.opacity)
    if gain > LEVEL_EPS:
        return opacity / gain
    return opacity


def collect_hot_layers(
    frame: LimiterFrameState,
    layers_by_slot: dict[str, StemLayer],
    t_sec: float,
) -> list[HotLayerRef]:
    """Layers that absorb gain reduction.

    Timeline on: slots whose timeline level drives opacity and level is above
    ``LEVEL_EPS``, weighted by the lane role at the playhead (unset is pulse).
    Timeline off: enabled composited layers, all at the pulse weight. Disabled
    or zero-contribution layers stay out so they do not dilute gain compensation.
    """
    hot: list[HotLayerRef] = []
    timeline_on = frame.timeline.enabled
    for z_index, slot in enumerate(frame.layer_z_order):
        layer = layers_by_slot.get(slot)
        if layer is None:
            continue
        if timeline_on:
            if not timeline_levels_apply(frame, slot):
                continue
            if layer.timeline_level <= LEVEL_EPS:
                continue
            lane = frame.timeline.lanes.get(slot) or empty_lane()
            role = lane_role_at(lane, t_sec)
            level = float(layer.timeline_level)
        else:
            if not layer.fbo.enabled:
                continue
            if _pre_limiter_opacity(layer) <= LEVEL_EPS:
                continue
            role = None
            level = 1.0
        hot.append(
            HotLayerRef(
                slot=slot,
                role_rank=role_rank(role),
                timeline_level=level,
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


def _envelope_coeff(dt: float, time_constant: float) -> float:
    if dt <= LEVEL_EPS or time_constant <= LEVEL_EPS:
        return 0.0
    return 1.0 - math.exp(-dt / time_constant)


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
    raw = busyness(mean_luma, mean_abs_delta)
    compensated = compensated_busyness(raw, state.gains)

    if compensated > state.envelope:
        coeff = _envelope_coeff(dt, ATTACK_TC)
    else:
        coeff = _envelope_coeff(dt, knobs.release_tc)
    state.envelope += coeff * (compensated - state.envelope)

    target_gain = target_bus_gain(
        state.envelope,
        threshold=knobs.threshold,
        ratio=knobs.ratio,
    )
    distribute_gain(state, hot, target_gain)


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
    frame = LimiterFrameState.from_session(runtime.seed.session)
    if blank_visualizers or not visual_limiter_active(frame):
        state.reset()
        state.clear_layer_gains(runtime.layers_by_slot)
        return
    state.apply_to_layers(runtime.layers_by_slot)


def observe_frame_busyness(
    core: VisualizerCore,
    t_sec: float,
    frame: LimiterFrameState,
    *,
    blank_visualizers: bool = False,
) -> None:
    """Sample content FBO and update limiter state for the next frame."""
    if blank_visualizers or not visual_limiter_active(frame):
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
    hot = collect_hot_layers(frame, core.layers_by_slot, t_sec)
    update_limiter_state(
        state,
        mean_luma=mean_luma,
        mean_abs_delta=mean_abs_delta,
        t_sec=t_sec,
        hot=hot,
        params=VisualLimiterParams.from_runtime(frame.limiter),
    )
