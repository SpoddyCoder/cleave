"""Tests for cleave.timeline_presets.accent."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pytest

from cleave.cue_roles import CUE_ROLE_BLEND
from cleave.stems import StemSource
from cleave.signals import Signals
from cleave.song_markers import SongMarker
from cleave.timeline import (
    LEVEL_QUANTUM,
    SlotCue,
    TimelineLane,
    lane_level_at,
    lane_role_at,
)
from cleave.timeline_presets.accent import (
    ACCENT_MAX_SEC,
    accent_window,
    apply_accent,
    dimmed_support_level,
    resolve_accent_times,
)
from cleave.timeline_presets.motifs import MIN_SWITCH_GAP_SEC

_SR = 100.0
_DUR = 40.0
_N = int(_DUR * _SR)
_SLOTS = ("layer_1", "layer_2", "layer_3", "layer_4")


def _slot_stems() -> dict[str, StemSource]:
    return {
        "layer_1": "drums",
        "layer_2": "bass",
        "layer_3": "vocals",
        "layer_4": "other",
    }


def _const(value: float) -> np.ndarray:
    return np.full(_N, value, dtype=np.float64)


def _spike_at(t_sec: float, *, quiet: float = 0.05, loud: float = 1.0) -> np.ndarray:
    arr = _const(quiet)
    i = int(t_sec * _SR)
    width = max(1, int(0.2 * _SR))
    arr[max(0, i - width) : min(_N, i + width)] = loud
    return arr


def _make_signals(
    *,
    drums: np.ndarray | None = None,
    bass: np.ndarray | None = None,
    vocals: np.ndarray | None = None,
    other: np.ndarray | None = None,
) -> Signals:
    return Signals(
        sample_rate_hz=_SR,
        duration_sec=_DUR,
        path=Path("."),
        stems={
            "drums": {
                "onset_strength": drums if drums is not None else _const(0.1)
            },
            "bass": {
                "rms": bass if bass is not None else _const(0.1),
                "sub_bass": _const(0.1),
                "mid_bass": _const(0.1),
            },
            "vocals": {
                "rms": vocals if vocals is not None else _const(0.1),
                "pitch_hz": _const(0.0),
            },
            "other": {
                "spectral_centroid": _const(1000.0),
                "rms": other if other is not None else _const(0.1),
            },
            "full_mix": {
                "onset_strength": _const(0.2),
                "rms": _const(0.3),
            },
        },
    )


def _steady_lanes(
    slots: tuple[str, ...] = _SLOTS,
    *,
    level: float = 0.5,
    role: str = "bed",
) -> dict[str, TimelineLane]:
    blend = CUE_ROLE_BLEND[role]  # type: ignore[index]
    return {
        slot: TimelineLane(
            baseline=0.0,
            cues=[
                SlotCue(
                    t=0.0,
                    level=level,
                    blend=blend,
                    role=role,  # type: ignore[arg-type]
                    cut="none",
                )
            ],
        )
        for slot in slots
    }


def _apply(
    lanes: dict[str, TimelineLane],
    markers: list[SongMarker],
    *,
    signals: Signals | None = None,
    duration_sec: float = _DUR,
) -> dict[str, TimelineLane]:
    return apply_accent(
        lanes,
        list(_SLOTS),
        duration_sec=duration_sec,
        song_markers=markers,
        signals=signals if signals is not None else _make_signals(),
        slot_stems=_slot_stems(),
        density_bias=0,
        rng=random.Random(0),
    )


def test_resolve_accent_times_standard_only() -> None:
    markers = [
        SongMarker(0.0, "standard"),
        SongMarker(8.0, "standard"),
        SongMarker(12.0, "begin"),
        SongMarker(16.0, "sustain"),
        SongMarker(20.0, "crescendo"),
        SongMarker(24.0, "standard"),
        SongMarker(40.0, "standard"),
    ]
    assert resolve_accent_times(markers, _DUR) == [8.0, 24.0]


def test_accent_window_spans_to_next_marker() -> None:
    markers = [
        SongMarker(8.0, "standard"),
        SongMarker(12.0, "begin"),
        SongMarker(24.0, "standard"),
    ]
    window = accent_window(8.0, markers, _DUR)
    assert window is not None
    t_start, t_end = window
    assert t_start == pytest.approx(8.0)
    assert t_end == pytest.approx(12.0)

    # No later marker: span to song end, still capped.
    solo = [SongMarker(30.0, "standard")]
    window2 = accent_window(30.0, solo, _DUR)
    assert window2 is not None
    assert window2[0] == pytest.approx(30.0)
    assert window2[1] == pytest.approx(_DUR)


def test_accent_window_caps_long_section() -> None:
    markers = [
        SongMarker(5.0, "standard"),
        SongMarker(35.0, "crescendo"),
    ]
    window = accent_window(5.0, markers, _DUR)
    assert window is not None
    t_start, t_end = window
    assert t_start == pytest.approx(5.0)
    assert t_end == pytest.approx(5.0 + ACCENT_MAX_SEC)
    assert t_end < 35.0 - 1e-9


def test_apply_accent_inserts_at_standard_markers() -> None:
    markers = [
        SongMarker(8.0, "standard"),
        SongMarker(12.0, "begin"),
        SongMarker(16.0, "sustain"),
        SongMarker(20.0, "crescendo"),
        SongMarker(24.0, "standard"),
    ]
    lanes = _steady_lanes()
    after = _apply(lanes, markers)
    assert after is not lanes

    accent_starts = sorted(
        cue.t
        for lane in after.values()
        for cue in lane.cues
        if cue.role == "accent"
    )
    assert accent_starts == pytest.approx([8.0, 24.0])
    for cue in (c for lane in after.values() for c in lane.cues if c.role == "accent"):
        assert cue.level == pytest.approx(1.0)
        assert cue.blend == CUE_ROLE_BLEND["accent"]


def test_apply_accent_spans_section_until_next_marker() -> None:
    markers = [
        SongMarker(8.0, "standard"),
        SongMarker(18.0, "begin"),
    ]
    after = _apply(_steady_lanes(level=0.5), markers)
    accent_slot = next(
        slot
        for slot, lane in after.items()
        for cue in lane.cues
        if cue.role == "accent"
    )
    assert lane_role_at(after[accent_slot], 8.0) == "accent"
    assert lane_role_at(after[accent_slot], 17.9) == "accent"
    assert lane_level_at(after[accent_slot], 18.0, inherit=0.0) == pytest.approx(0.5)
    assert lane_role_at(after[accent_slot], 18.0) == "bed"


def test_apply_accent_caps_long_section_with_restore() -> None:
    markers = [
        SongMarker(5.0, "standard"),
        SongMarker(35.0, "crescendo"),
    ]
    prior = 0.5
    after = _apply(_steady_lanes(level=prior), markers)
    accent_slot = next(
        slot
        for slot, lane in after.items()
        for cue in lane.cues
        if cue.role == "accent"
    )
    t_end = 5.0 + ACCENT_MAX_SEC
    assert lane_role_at(after[accent_slot], 5.0) == "accent"
    assert lane_role_at(after[accent_slot], t_end - 0.01) == "accent"
    assert lane_level_at(after[accent_slot], t_end, inherit=0.0) == pytest.approx(
        prior
    )
    assert lane_role_at(after[accent_slot], t_end) == "bed"
    # Leftover of the section after the cap is not a second accent.
    leftover_accents = [
        cue.t
        for cue in after[accent_slot].cues
        if cue.role == "accent" and cue.t > t_end + 1e-9
    ]
    assert leftover_accents == []
    assert lane_role_at(after[accent_slot], 30.0) == "bed"


def test_apply_accent_dims_supporting_layer() -> None:
    markers = [SongMarker(10.0, "standard"), SongMarker(25.0, "begin")]
    prior = 0.75
    after = _apply(_steady_lanes(level=prior, role="lead"), markers)
    accent_slot = next(
        slot
        for slot, lane in after.items()
        for cue in lane.cues
        if cue.role == "accent"
    )
    dimmed = dimmed_support_level(prior)
    assert dimmed == pytest.approx(prior - LEVEL_QUANTUM)

    dim_slots = [
        slot
        for slot in _SLOTS
        if slot != accent_slot
        and lane_level_at(after[slot], 10.0, inherit=0.0) == pytest.approx(dimmed)
    ]
    assert len(dim_slots) == 1
    dim_slot = dim_slots[0]
    assert lane_role_at(after[dim_slot], 10.0) == "lead"
    assert lane_level_at(after[dim_slot], 25.0, inherit=0.0) == pytest.approx(prior)
    assert lane_role_at(after[dim_slot], 25.0) == "lead"
    # Accent slot itself is not dimmed.
    assert lane_level_at(after[accent_slot], 10.0, inherit=0.0) == pytest.approx(1.0)


def test_apply_accent_noop_without_standard_markers() -> None:
    markers = [
        SongMarker(8.0, "begin"),
        SongMarker(12.0, "sustain"),
        SongMarker(20.0, "crescendo"),
    ]
    lanes = _steady_lanes()
    after = _apply(lanes, markers)
    assert after is lanes


def test_apply_accent_respects_min_gap() -> None:
    # Two standards closer than MIN_SWITCH_GAP_SEC: only the first fires.
    markers = [
        SongMarker(8.0, "standard"),
        SongMarker(8.0 + MIN_SWITCH_GAP_SEC * 0.5, "standard"),
        SongMarker(8.0 + MIN_SWITCH_GAP_SEC + 1.0, "standard"),
    ]
    after = _apply(_steady_lanes(), markers)
    accent_starts = sorted(
        cue.t
        for lane in after.values()
        for cue in lane.cues
        if cue.role == "accent"
    )
    assert accent_starts == pytest.approx([8.0, 8.0 + MIN_SWITCH_GAP_SEC + 1.0])


def test_apply_accent_picks_loudest_slot() -> None:
    marker_t = 10.0
    signals = _make_signals(
        drums=_const(0.1),
        bass=_const(0.1),
        vocals=_spike_at(marker_t, quiet=0.05, loud=1.0),
        other=_const(0.1),
    )
    markers = [SongMarker(marker_t, "standard")]
    after = _apply(_steady_lanes(level=0.25), markers, signals=signals)

    accent_slots = [
        slot
        for slot, lane in after.items()
        for cue in lane.cues
        if cue.role == "accent"
    ]
    assert accent_slots == ["layer_3"]
    assert lane_role_at(after["layer_3"], marker_t) == "accent"
    assert lane_level_at(after["layer_3"], marker_t, inherit=0.0) == pytest.approx(
        1.0
    )


def test_apply_accent_returns_to_prior_level() -> None:
    marker_t = 10.0
    prior = 0.5
    markers = [SongMarker(marker_t, "standard"), SongMarker(22.0, "begin")]
    lanes = _steady_lanes(level=prior, role="lead")
    after = _apply(lanes, markers)
    window = accent_window(marker_t, markers, _DUR)
    assert window is not None
    _t_start, t_end = window
    assert t_end == pytest.approx(22.0)

    accent_slot = next(
        slot
        for slot, lane in after.items()
        for cue in lane.cues
        if cue.role == "accent"
    )
    assert lane_level_at(after[accent_slot], marker_t, inherit=0.0) == pytest.approx(
        1.0
    )
    assert lane_role_at(after[accent_slot], marker_t) == "accent"
    assert lane_level_at(after[accent_slot], t_end, inherit=0.0) == pytest.approx(
        prior
    )
    assert lane_role_at(after[accent_slot], t_end) == "lead"
