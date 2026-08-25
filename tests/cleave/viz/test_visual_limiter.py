"""Pure logic tests for the feed-forward visual limiter (no GL)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from cleave.config_schema.layers import DEFAULT_LAYER_SLOTS
from cleave.cue_roles import CueRole
from cleave.preset_playlist import PresetPlaylist
from cleave.timeline import SlotCue, TimelineLane, empty_lane
from cleave.viz.layer import StemLayer
from cleave.viz.layer_pipeline import apply_effect_modifiers
from cleave.viz.session import LayerRuntime, TimelineRuntime, TuningSession
from cleave.viz.visual_limiter import (
    ATTACK_TC,
    DEFAULT_RATIO,
    DEFAULT_RELEASE_TC,
    DEFAULT_THRESHOLD,
    GRID_HEIGHT,
    GRID_WIDTH,
    HotLayerRef,
    LimiterFrameState,
    VisualLimiterParams,
    VisualLimiterState,
    apply_visual_limiter_gains,
    busyness,
    collect_hot_layers,
    compensated_busyness,
    distribute_gain,
    layer_gain_from_target,
    metrics_from_grid,
    priority_weight,
    read_luma_grid,
    role_rank,
    reset_if_seek,
    target_bus_gain,
    update_limiter_state,
    visual_limiter_active,
)
from tests.support.config import TEST_LAYER_STEMS

_OVER = DEFAULT_THRESHOLD + 0.10
_UNDER = DEFAULT_THRESHOLD - 0.10
_SAMPLE_GAIN = 0.6


def _playlist(slot: str) -> PresetPlaylist:
    current_dir = Path(f"/tmp/presets/{slot}")
    return PresetPlaylist(
        current_dir=current_dir,
        paths=(current_dir / "preset.milk",),
        index=0,
    )


def _session(*, timeline_enabled: bool = True) -> TuningSession:
    return TuningSession(
        layer_z_order=list(DEFAULT_LAYER_SLOTS),
        timeline=TimelineRuntime(enabled=timeline_enabled, lanes={}),
        layers={
            slot: LayerRuntime(
                playlist=_playlist(slot),
                browse_floor=Path(f"/tmp/presets/{slot}"),
                stem=TEST_LAYER_STEMS[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
        },
    )


def _hot(
    slot: str,
    *,
    role: CueRole | None = "pulse",
    level: float = 1.0,
    z_index: int = 0,
) -> HotLayerRef:
    return HotLayerRef(
        slot=slot,
        role_rank=role_rank(role),
        timeline_level=level,
        z_index=z_index,
    )


def _stem(slot: str, *, timeline_level: float = 1.0) -> StemLayer:
    return StemLayer(
        slot=slot,
        pm=MagicMock(),
        fbo=MagicMock(enabled=timeline_level > 0.0),
        playlist=_playlist(slot),
        timeline_level=timeline_level,
    )


def _drive(
    state: VisualLimiterState,
    *,
    mean_luma: float,
    t_sec: float,
    hot: list[HotLayerRef],
    mean_abs_delta: float = 0.0,
    params: VisualLimiterParams | None = None,
) -> None:
    update_limiter_state(
        state,
        mean_luma=mean_luma,
        mean_abs_delta=mean_abs_delta,
        t_sec=t_sec,
        hot=hot,
        params=params,
    )


def test_unset_role_ranks_as_pulse() -> None:
    assert role_rank(None) == role_rank("pulse")


def test_priority_weight_favors_bed_over_lead() -> None:
    assert priority_weight(role_rank("bed")) > priority_weight(role_rank("lead"))


def test_layer_gain_from_target_spreads_by_weight() -> None:
    target = 0.6
    assert layer_gain_from_target(target, 1.0) == pytest.approx(0.6)
    assert layer_gain_from_target(target, 0.15) == pytest.approx(0.94)


def test_target_bus_gain_below_threshold_is_unity() -> None:
    assert target_bus_gain(0.5, threshold=0.65, ratio=3.0) == pytest.approx(1.0)


def test_target_bus_gain_higher_ratio_reduces_more() -> None:
    envelope = 0.85
    gentle = target_bus_gain(envelope, threshold=0.65, ratio=2.0)
    aggressive = target_bus_gain(envelope, threshold=0.65, ratio=8.0)
    assert gentle < 1.0
    assert aggressive < gentle


def test_compensated_busyness_undoes_applied_gains() -> None:
    raw = 0.5
    gains = {"layer_1": 0.5, "layer_2": 0.5}
    assert compensated_busyness(raw, gains) == pytest.approx(1.0)


def test_envelope_attacks_on_sustained_high_busyness() -> None:
    state = VisualLimiterState()
    hot = [_hot("layer_1", role="bed")]
    params = VisualLimiterParams(release_tc=1.0)
    unducked = _OVER

    _drive(state, mean_luma=unducked, t_sec=0.0, hot=hot, params=params)
    assert state.envelope == pytest.approx(0.0)

    _drive(state, mean_luma=unducked, t_sec=ATTACK_TC * 0.5, hot=hot, params=params)
    assert 0.0 < state.envelope < unducked

    for step in range(20):
        t = ATTACK_TC + step * 0.05
        avg_gain = (
            sum(state.gains.values()) / len(state.gains) if state.gains else 1.0
        )
        _drive(
            state,
            mean_luma=unducked * avg_gain,
            t_sec=t,
            hot=hot,
            params=params,
        )
    assert state.envelope > DEFAULT_THRESHOLD
    assert state.gain_for("layer_1") < 1.0


def test_envelope_releases_when_busyness_drops() -> None:
    state = VisualLimiterState()
    hot = [_hot("layer_1", role="bed")]
    params = VisualLimiterParams(release_tc=0.3)

    for step in range(30):
        _drive(
            state,
            mean_luma=_OVER,
            t_sec=step * 0.05,
            hot=hot,
            params=params,
        )
    peak_envelope = state.envelope
    assert peak_envelope > DEFAULT_THRESHOLD
    assert state.gain_for("layer_1") < 1.0

    for step in range(40):
        _drive(
            state,
            mean_luma=_UNDER,
            t_sec=1.5 + step * 0.05,
            hot=hot,
            params=params,
        )
    assert state.envelope < peak_envelope
    assert state.gain_for("layer_1") == pytest.approx(1.0, abs=0.05)


def test_gain_compensation_stabilizes_under_feedback() -> None:
    state = VisualLimiterState()
    hot = [_hot("layer_1", role="bed")]
    params = VisualLimiterParams(release_tc=DEFAULT_RELEASE_TC)
    unducked = _OVER

    for step in range(80):
        t = step * 0.05
        avg_gain = (
            sum(state.gains.values()) / len(state.gains) if state.gains else 1.0
        )
        measured_luma = unducked * avg_gain
        _drive(state, mean_luma=measured_luma, t_sec=t, hot=hot, params=params)

    assert state.envelope > DEFAULT_THRESHOLD
    final_gain = state.gain_for("layer_1")
    for step in range(10):
        t = 4.0 + step * 0.05
        avg_gain = (
            sum(state.gains.values()) / len(state.gains) if state.gains else 1.0
        )
        measured_luma = unducked * avg_gain
        _drive(state, mean_luma=measured_luma, t_sec=t, hot=hot, params=params)
        assert abs(state.gain_for("layer_1") - final_gain) < 0.08
        final_gain = state.gain_for("layer_1")


def test_distribute_gain_bed_ducks_more_than_lead() -> None:
    state = VisualLimiterState()
    hot = [
        _hot("layer_1", role="bed", z_index=0),
        _hot("layer_2", role="lead", z_index=1),
    ]
    distribute_gain(state, hot, 0.6)
    assert state.gain_for("layer_1") == pytest.approx(0.6)
    assert state.gain_for("layer_2") == pytest.approx(0.94)


def test_seek_clears_state() -> None:
    state = VisualLimiterState()
    hot = [_hot("layer_1", role="bed")]

    state.last_t_sec = 10.0
    for step in range(20):
        _drive(state, mean_luma=_OVER, t_sec=10.0 + step * 0.05, hot=hot)
    assert state.gain_for("layer_1") < 1.0
    state.prev_luma = np.zeros((2, 2), dtype=np.float32)

    assert reset_if_seek(state, 1.0) is True
    assert state.gains == {}
    assert state.prev_luma is None
    assert state.envelope == pytest.approx(0.0)
    assert state.last_t_sec == pytest.approx(1.0)
    assert state.controller_t_sec is None

    _drive(state, mean_luma=_UNDER, t_sec=1.0, hot=hot)
    assert state.gains == {}


def test_busyness_includes_delta_weight() -> None:
    assert busyness(0.2, 0.1) > busyness(0.2, 0.0)


def test_collect_hot_layers_uses_role_and_level() -> None:
    session = _session(timeline_enabled=True)
    session.timeline.lanes = {
        "layer_1": TimelineLane(
            baseline=0.0,
            cues=[SlotCue(t=0.0, level=1.0, role="lead")],
        ),
        "layer_2": TimelineLane(
            baseline=0.0,
            cues=[SlotCue(t=0.0, level=0.5, role="bed")],
        ),
        "layer_3": empty_lane(),
        "layer_4": empty_lane(),
    }
    layers = {
        "layer_1": _stem("layer_1", timeline_level=1.0),
        "layer_2": _stem("layer_2", timeline_level=0.5),
        "layer_3": _stem("layer_3", timeline_level=0.0),
        "layer_4": _stem("layer_4", timeline_level=0.0),
    }
    hot = collect_hot_layers(LimiterFrameState.from_session(session), layers, 1.0)
    assert [h.slot for h in hot] == ["layer_1", "layer_2"]


def test_apply_effect_modifiers_includes_limiter_gain() -> None:
    session = _session(timeline_enabled=False)
    layer = _stem("layer_1", timeline_level=0.5)
    layer.limiter_gain = _SAMPLE_GAIN
    effect_runtime = MagicMock()
    mod = MagicMock(
        opacity=0.8,
        flash_alpha=0.0,
        bloom_strength=0.0,
        hue_rgb=(1.0, 1.0, 1.0),
        hue_mix=0.0,
        grit_strength=0.0,
        aberration_px=0.0,
    )
    effect_runtime.modifiers.return_value = {
        slot: mod for slot in session.layer_z_order
    }
    apply_effect_modifiers(
        session,
        {"layer_1": layer},
        effect_runtime,
        None,
        0.0,
        update=False,
    )
    assert layer.fbo.opacity == pytest.approx(0.8 * 0.5 * _SAMPLE_GAIN)


def test_visual_limiter_inactive_when_disabled() -> None:
    session = _session(timeline_enabled=True)
    assert visual_limiter_active(LimiterFrameState.from_session(session)) is True
    session.timeline.limiter.enabled = False
    assert visual_limiter_active(LimiterFrameState.from_session(session)) is False


def test_apply_visual_limiter_gains_resets_when_disabled() -> None:
    session = _session(timeline_enabled=True)
    session.timeline.limiter.enabled = False
    state = VisualLimiterState()
    state.gains["layer_1"] = _SAMPLE_GAIN
    layer = _stem("layer_1", timeline_level=1.0)
    layer.limiter_gain = _SAMPLE_GAIN
    runtime = MagicMock()
    runtime.visual_limiter = state
    runtime.seed.session = session
    runtime.layers_by_slot = {"layer_1": layer}
    apply_visual_limiter_gains(runtime)
    assert state.gains == {}
    assert layer.limiter_gain == pytest.approx(1.0)


def test_update_limiter_state_uses_session_params() -> None:
    state = VisualLimiterState()
    hot = [_hot("layer_1", role="bed")]
    params = VisualLimiterParams(threshold=0.80, ratio=3.0, release_tc=0.45)

    _drive(state, mean_luma=0.70, t_sec=0.0, hot=hot, params=params)
    assert state.gains == {}

    for step in range(30):
        _drive(
            state,
            mean_luma=0.90,
            t_sec=0.05 + step * 0.05,
            hot=hot,
            params=params,
        )
    assert state.gain_for("layer_1") < 1.0


def test_read_luma_grid_delegates_to_post_process() -> None:
    compositor = MagicMock(content_texture_id=9, content_width=1280, content_height=720)
    post_process = MagicMock()
    expected = np.full((GRID_HEIGHT, GRID_WIDTH), 0.42, dtype=np.float32)
    post_process.read_luma_grid.return_value = expected

    grid = read_luma_grid(compositor, post_process)

    post_process.read_luma_grid.assert_called_once_with(
        9,
        1280,
        720,
        grid_width=GRID_WIDTH,
        grid_height=GRID_HEIGHT,
    )
    assert grid is expected


def test_metrics_from_grid_tracks_mean_and_delta() -> None:
    state = VisualLimiterState()
    grid_a = np.full((2, 2), 0.2, dtype=np.float32)
    mean_luma, mean_delta = metrics_from_grid(state, grid_a)
    assert mean_luma == pytest.approx(0.2)
    assert mean_delta == pytest.approx(0.0)

    grid_b = np.full((2, 2), 0.4, dtype=np.float32)
    mean_luma, mean_delta = metrics_from_grid(state, grid_b)
    assert mean_luma == pytest.approx(0.4)
    assert mean_delta == pytest.approx(0.2)
