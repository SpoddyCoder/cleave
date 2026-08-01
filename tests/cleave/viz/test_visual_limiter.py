"""Pure logic tests for the closed-loop visual limiter (no GL)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from cleave.config_schema import DEFAULT_LAYER_SLOTS
from cleave.cue_roles import CueRole
from cleave.preset_playlist import PresetPlaylist
from cleave.timeline import SlotCue, TimelineLane, empty_lane
from cleave.viz.layer import StemLayer
from cleave.viz.layer_pipeline import apply_effect_modifiers
from cleave.viz.session import LayerRuntime, TimelineRuntime, TuningSession
from cleave.viz.visual_limiter import (
    ATTACK_SEC,
    DUCK_GAIN,
    GRID_HEIGHT,
    GRID_WIDTH,
    RELEASE_RAMP_SEC,
    RELEASE_SEC,
    THRESHOLD_OFF,
    THRESHOLD_ON,
    HotLayerRef,
    VisualLimiterParams,
    VisualLimiterState,
    apply_visual_limiter_gains,
    busyness,
    collect_hot_layers,
    metrics_from_grid,
    pick_victim,
    read_luma_grid,
    role_rank,
    reset_if_seek,
    update_limiter_state,
    visual_limiter_active,
)
from tests.support.config import TEST_LAYER_STEMS

_OVER = THRESHOLD_ON + 0.01
_UNDER = THRESHOLD_OFF - 0.01


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
) -> None:
    update_limiter_state(
        state,
        mean_luma=mean_luma,
        mean_abs_delta=mean_abs_delta,
        t_sec=t_sec,
        hot=hot,
    )


def _fully_duck(
    state: VisualLimiterState,
    hot: list[HotLayerRef],
    *,
    t0: float = 0.0,
) -> float:
    """Advance playhead through a full attack; return final t_sec."""
    _drive(state, mean_luma=_OVER, t_sec=t0, hot=hot)
    t1 = t0 + ATTACK_SEC + 0.01
    _drive(state, mean_luma=_OVER, t_sec=t1, hot=hot)
    return t1


def test_pick_victim_prefers_bed_over_lead() -> None:
    hot = [
        _hot("layer_1", role="lead", z_index=0),
        _hot("layer_2", role="bed", z_index=1),
    ]
    assert pick_victim(hot, {}) == "layer_2"


def test_unset_role_ranks_as_pulse() -> None:
    assert role_rank(None) == role_rank("pulse")
    hot = [
        _hot("layer_1", role="lead", z_index=0),
        _hot("layer_2", role=None, z_index=1),
        _hot("layer_3", role="bed", z_index=2),
    ]
    assert pick_victim(hot, {}) == "layer_3"
    assert pick_victim(hot, {"layer_3": DUCK_GAIN}) == "layer_2"


def test_tie_break_level_then_z_order() -> None:
    hot = [
        _hot("layer_1", role="pulse", level=1.0, z_index=0),
        _hot("layer_2", role="pulse", level=0.5, z_index=1),
    ]
    assert pick_victim(hot, {}) == "layer_2"

    hot_same_level = [
        _hot("layer_1", role="pulse", level=1.0, z_index=0),
        _hot("layer_2", role="pulse", level=1.0, z_index=1),
    ]
    assert pick_victim(hot_same_level, {}) == "layer_1"


def test_attack_ramps_over_playhead_time() -> None:
    state = VisualLimiterState()
    hot = [_hot("layer_1", role="bed")]

    _drive(state, mean_luma=_OVER, t_sec=0.0, hot=hot)
    assert state.gain_for("layer_1") == pytest.approx(1.0)

    _drive(state, mean_luma=_OVER, t_sec=ATTACK_SEC * 0.5, hot=hot)
    mid = state.gain_for("layer_1")
    assert DUCK_GAIN < mid < 1.0

    _drive(state, mean_luma=_OVER, t_sec=ATTACK_SEC + 0.01, hot=hot)
    assert state.gain_for("layer_1") == pytest.approx(DUCK_GAIN)


def test_hysteresis_holds_until_release_ramp() -> None:
    state = VisualLimiterState()
    hot = [_hot("layer_1", role="bed"), _hot("layer_2", role="lead")]
    t = _fully_duck(state, hot)
    assert state.gain_for("layer_1") == pytest.approx(DUCK_GAIN)

    under_start = t + 0.1
    _drive(state, mean_luma=_UNDER, t_sec=under_start, hot=hot)
    assert state.gain_for("layer_1") == pytest.approx(DUCK_GAIN)

    _drive(
        state,
        mean_luma=_UNDER,
        t_sec=under_start + RELEASE_SEC * 0.5,
        hot=hot,
    )
    assert state.gain_for("layer_1") == pytest.approx(DUCK_GAIN)

    # Cross the hold with a small dt so the first release step is partial.
    hold_end = under_start + RELEASE_SEC
    _drive(state, mean_luma=_UNDER, t_sec=hold_end - 0.01, hot=hot)
    _drive(state, mean_luma=_UNDER, t_sec=hold_end + 0.02, hot=hot)
    mid_gain = state.gain_for("layer_1")
    assert DUCK_GAIN < mid_gain < 1.0

    _drive(
        state,
        mean_luma=_UNDER,
        t_sec=hold_end + RELEASE_RAMP_SEC + 0.01,
        hot=hot,
    )
    assert state.gain_for("layer_1") == pytest.approx(1.0)


def test_between_thresholds_cancels_release() -> None:
    state = VisualLimiterState()
    hot = [_hot("layer_1", role="bed")]
    mid = (THRESHOLD_ON + THRESHOLD_OFF) / 2.0
    t = _fully_duck(state, hot)

    under_start = t + 0.1
    _drive(state, mean_luma=_UNDER, t_sec=under_start, hot=hot)
    _drive(state, mean_luma=mid, t_sec=under_start + 0.1, hot=hot)
    _drive(
        state,
        mean_luma=_UNDER,
        t_sec=under_start + 0.1 + RELEASE_SEC + RELEASE_RAMP_SEC + 0.01,
        hot=hot,
    )
    # Release timer restarted after the mid-band cancel; one under tick is not
    # enough hold time, so the duck remains.
    assert state.gain_for("layer_1") == pytest.approx(DUCK_GAIN)


def test_seek_clears_ducks() -> None:
    state = VisualLimiterState()
    hot = [_hot("layer_1", role="bed")]

    state.last_t_sec = 10.0
    _fully_duck(state, hot, t0=10.0)
    assert state.gain_for("layer_1") == pytest.approx(DUCK_GAIN)
    state.prev_luma = np.zeros((2, 2), dtype=np.float32)

    assert reset_if_seek(state, 1.0) is True
    assert state.gains == {}
    assert state.prev_luma is None
    assert state.last_t_sec == pytest.approx(1.0)
    assert state.controller_t_sec is None

    # Quiet frame after seek: no release hold inherited from the prior duck.
    _drive(state, mean_luma=_UNDER, t_sec=1.0, hot=hot)
    assert state.gains == {}


def test_cascading_ducks_next_victim() -> None:
    state = VisualLimiterState()
    hot = [
        _hot("layer_1", role="bed", z_index=0),
        _hot("layer_2", role="accent", z_index=1),
    ]
    t = _fully_duck(state, hot)
    assert state.gain_for("layer_1") == pytest.approx(DUCK_GAIN)
    assert state.gain_for("layer_2") == pytest.approx(1.0)

    t = _fully_duck(state, hot, t0=t)
    assert state.gain_for("layer_1") == pytest.approx(DUCK_GAIN)
    assert state.gain_for("layer_2") == pytest.approx(DUCK_GAIN)


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
    hot = collect_hot_layers(session, layers, 1.0)
    assert [h.slot for h in hot] == ["layer_1", "layer_2"]
    assert pick_victim(hot, {}) == "layer_2"


def test_apply_effect_modifiers_includes_limiter_gain() -> None:
    session = _session(timeline_enabled=False)
    layer = _stem("layer_1", timeline_level=0.5)
    layer.limiter_gain = DUCK_GAIN
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
    assert layer.fbo.opacity == pytest.approx(0.8 * 0.5 * DUCK_GAIN)


def test_thresholds_leave_hysteresis_gap() -> None:
    assert THRESHOLD_OFF < THRESHOLD_ON
    assert THRESHOLD_ON - THRESHOLD_OFF >= 0.15
    assert DUCK_GAIN > 0.25


def test_visual_limiter_inactive_when_disabled() -> None:
    session = _session(timeline_enabled=True)
    assert visual_limiter_active(session) is True
    session.timeline.limiter.enabled = False
    assert visual_limiter_active(session) is False


def test_apply_visual_limiter_gains_resets_when_disabled() -> None:
    session = _session(timeline_enabled=True)
    session.timeline.limiter.enabled = False
    state = VisualLimiterState()
    state.gains["layer_1"] = DUCK_GAIN
    layer = _stem("layer_1", timeline_level=1.0)
    layer.limiter_gain = DUCK_GAIN
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
    params = VisualLimiterParams(
        threshold_on=0.80,
        threshold_off=0.63,
        release_ramp_sec=0.45,
        release_sec=0.75,
    )
    update_limiter_state(
        state,
        mean_luma=0.70,
        mean_abs_delta=0.0,
        t_sec=0.0,
        hot=hot,
        params=params,
    )
    assert state.gains == {}
    update_limiter_state(
        state,
        mean_luma=0.81,
        mean_abs_delta=0.0,
        t_sec=ATTACK_SEC + 0.01,
        hot=hot,
        params=params,
    )
    assert state.gain_for("layer_1") == pytest.approx(DUCK_GAIN)


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
