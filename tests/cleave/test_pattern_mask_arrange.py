"""Tests for the pattern-mask timeline arranger and Apply routing."""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import numpy as np

from cleave.extract import StemSource
from cleave.preset_playlist import PresetPlaylist
from cleave.signals import Signals
from cleave.song_markers import SongMarker
from cleave.timeline import LEVEL_EPS, TimelineLane, empty_lane, lane_level_at
from cleave.timeline_presets.arrange import PHRASE_BARS_MIN, PHRASE_BARS_MAX
from cleave.timeline_presets.pattern_mask_arrange import (
    SECTION_BARS_MAX,
    SECTION_BARS_MIN,
    compose_pattern_mask_timeline,
    partition_pattern_mask_sections,
)
from cleave.viz.modal import ModalHost
from cleave.viz.session import LayerRuntime, TimelineRuntime, TuningSession
from cleave.viz.timeline_preset_controls import TimelinePresetController
from tests.support.config import TEST_LAYER_STEMS

_DUR = 120.0
_BAR_SEC = 2.0
_BEAT_SEC = 0.5


def _slots(n: int) -> list[str]:
    return [f"layer_{i}" for i in range(1, n + 1)]


def _bar_times(duration_sec: float = _DUR, bar_sec: float = _BAR_SEC) -> list[float]:
    bars: list[float] = []
    t = 0.0
    while t < duration_sec - 1e-9:
        bars.append(t)
        t += bar_sec
    return bars


def _beat_times(duration_sec: float = _DUR, beat_sec: float = _BEAT_SEC) -> list[float]:
    beats: list[float] = []
    t = 0.0
    while t < duration_sec - 1e-9:
        beats.append(t)
        t += beat_sec
    return beats


def _compose(
    slots: list[str],
    *,
    seed: int = 0,
    duration_sec: float = _DUR,
    density_bias: int = 0,
    song_markers: list[SongMarker] | None = None,
    signals: Signals | None = None,
    slot_stems: dict[str, StemSource] | None = None,
) -> dict[str, TimelineLane]:
    return compose_pattern_mask_timeline(
        slots,
        duration_sec,
        random.Random(seed),
        _bar_times(duration_sec),
        song_marker_times=[m.time for m in (song_markers or ())],
        song_markers=song_markers or (),
        density_bias=density_bias,
        signals=signals,
        slot_stems=slot_stems,
        beat_times=_beat_times(duration_sec),
    )


def _level_at(
    lanes: dict[str, TimelineLane], slots: list[str], t: float
) -> dict[str, float]:
    return {
        slot: lane_level_at(lanes.get(slot) or empty_lane(), t, inherit=0.0)
        for slot in slots
    }


def _active_at(
    lanes: dict[str, TimelineLane], slots: list[str], t: float
) -> frozenset[str]:
    return frozenset(
        slot for slot, level in _level_at(lanes, slots, t).items() if level > LEVEL_EPS
    )


def _all_cue_times(lanes: dict[str, TimelineLane]) -> list[float]:
    return sorted({cue.t for lane in lanes.values() for cue in lane.cues})


def _sample_counts(
    lanes: dict[str, TimelineLane],
    slots: list[str],
    duration_sec: float,
    step: float = 0.5,
) -> list[int]:
    counts: list[int] = []
    t = 0.0
    while t <= duration_sec:
        counts.append(len(_active_at(lanes, slots, t)))
        t += step
    for t in _all_cue_times(lanes):
        counts.append(len(_active_at(lanes, slots, t)))
        counts.append(len(_active_at(lanes, slots, max(0.0, t - 1e-6))))
        counts.append(len(_active_at(lanes, slots, t + 1e-6)))
    return counts


def test_single_slot_stays_on() -> None:
    slots = _slots(1)
    lanes = _compose(slots, seed=3, duration_sec=30.0)
    assert set(lanes) == set(slots)
    for t in (0.0, 10.0, 29.9):
        assert _active_at(lanes, slots, t) == frozenset(slots)


def test_empty_slots_or_duration_returns_empty() -> None:
    assert compose_pattern_mask_timeline([], 30.0, random.Random(0), [0.0, 2.0]) == {}
    assert compose_pattern_mask_timeline(_slots(4), 0.0, random.Random(0), [0.0]) == {}


def test_overlap_when_add_then_remove() -> None:
    slots = _slots(4)
    found = False
    for seed in range(20):
        lanes = _compose(slots, seed=seed)
        times = [t for t in _all_cue_times(lanes) if t > 1e-9]
        for i, t_on in enumerate(times[:-1]):
            prev = _active_at(lanes, slots, t_on - 1e-6)
            active_on = _active_at(lanes, slots, t_on + 1e-6)
            added = active_on - prev
            if not added:
                continue
            for t_off in times[i + 1 :]:
                if not (0.05 < (t_off - t_on) <= 3.0):
                    continue
                active_mid = _active_at(lanes, slots, (t_on + t_off) * 0.5)
                after = _active_at(lanes, slots, t_off + 1e-6)
                removed = active_mid - after
                if added <= active_mid and (removed - added):
                    found = True
                    break
            if found:
                break
        if found:
            break
    assert found, "expected a 1-2 beat window where an added layer overlaps a departing one"


def test_count_distribution_two_three_mode() -> None:
    slots = _slots(4)
    histogram: Counter[int] = Counter()
    for seed in range(30):
        lanes = _compose(slots, seed=seed)
        for n in _sample_counts(lanes, slots, _DUR):
            histogram[n] += 1
            assert n >= 2, f"active count {n} dropped below 2"
            assert n <= 4
    two_three = histogram[2] + histogram[3]
    assert two_three > histogram[4]
    assert histogram[2] > 0 and histogram[3] > 0
    mode = max((2, 3, 4), key=lambda k: histogram[k])
    assert mode in (2, 3)


def test_five_plus_rare_without_crescendo() -> None:
    slots = _slots(6)
    histogram: Counter[int] = Counter()
    for seed in range(20):
        lanes = _compose(slots, seed=seed)
        for n in _sample_counts(lanes, slots, _DUR, step=1.0):
            histogram[n] += 1
            assert n >= 2
    five_plus = sum(histogram[k] for k in histogram if k >= 5)
    two_three = histogram[2] + histogram[3]
    assert five_plus < two_three * 0.35


def test_role_bias_lead_then_accent_then_pulse_bed() -> None:
    slots = _slots(4)
    roles: Counter[str] = Counter()
    for seed in range(25):
        lanes = _compose(slots, seed=seed)
        for lane in lanes.values():
            for cue in lane.cues:
                if cue.level > LEVEL_EPS and cue.role is not None:
                    roles[cue.role] += 1
    assert roles["lead"] > roles["accent"] > roles["pulse"] > roles["bed"]
    assert roles["bed"] > 0


def test_active_levels_are_full() -> None:
    slots = _slots(4)
    lanes = _compose(slots, seed=7)
    for t in _all_cue_times(lanes) + [0.0, 60.0]:
        for level in _level_at(lanes, slots, t).values():
            if level > LEVEL_EPS:
                assert abs(level - 1.0) <= LEVEL_EPS


def _envelope(duration_sec: float, sr: float, quiet: float, loud: float) -> np.ndarray:
    n = int(duration_sec * sr)
    arr = np.empty(n, dtype=np.float64)
    mid = n // 2
    arr[:mid] = quiet
    arr[mid:] = loud
    return arr


def _make_signals(duration_sec: float = _DUR) -> Signals:
    sr = 50.0
    drums = _envelope(duration_sec, sr, 0.9, 0.05)
    vocals = _envelope(duration_sec, sr, 0.05, 0.9)
    bass = np.full(int(duration_sec * sr), 0.2, dtype=np.float64)
    other = np.full(int(duration_sec * sr), 0.15, dtype=np.float64)
    mix = _envelope(duration_sec, sr, 0.3, 1.0)
    return Signals(
        sample_rate_hz=sr,
        duration_sec=duration_sec,
        path=Path("."),
        stems={
            "drums": {"onset_strength": drums},
            "bass": {"rms": bass, "sub_bass": bass, "mid_bass": bass},
            "vocals": {"rms": vocals, "pitch_hz": vocals},
            "other": {"spectral_centroid": other * 1000.0, "rms": other},
            "full_mix": {"onset_strength": mix, "rms": mix},
        },
    )


def _airtime(
    lanes: dict[str, TimelineLane],
    slot: str,
    t0: float,
    t1: float,
    step: float = 0.25,
) -> float:
    on = 0.0
    t = t0
    while t < t1:
        if lane_level_at(lanes[slot], t, inherit=0.0) > LEVEL_EPS:
            on += step
        t += step
    return on


def test_conductor_biases_busy_stems() -> None:
    slots = _slots(4)
    slot_stems: dict[str, StemSource] = {
        "layer_1": "drums",
        "layer_2": "bass",
        "layer_3": "vocals",
        "layer_4": "other",
    }
    signals = _make_signals()
    drums_first = 0.0
    vocals_first = 0.0
    drums_second = 0.0
    vocals_second = 0.0
    mid = _DUR * 0.5
    for seed in range(8):
        lanes = _compose(
            slots,
            seed=seed,
            signals=signals,
            slot_stems=slot_stems,
        )
        drums_first += _airtime(lanes, "layer_1", 0.0, mid)
        vocals_first += _airtime(lanes, "layer_3", 0.0, mid)
        drums_second += _airtime(lanes, "layer_1", mid, _DUR)
        vocals_second += _airtime(lanes, "layer_3", mid, _DUR)
    assert drums_first > vocals_first
    assert vocals_second > drums_second


def test_sections_shorter_than_layers_phrases() -> None:
    bars = _bar_times()
    rng = random.Random(4)
    sections = partition_pattern_mask_sections(bars, _DUR, rng, ())
    assert sections
    bar_counts = [
        sum(1 for b in bars if start <= b < end) for start, end in sections
    ]
    core = bar_counts[:-1]
    assert core
    assert all(SECTION_BARS_MIN <= n <= SECTION_BARS_MAX for n in core)
    assert sum(core) / len(core) < PHRASE_BARS_MIN
    assert SECTION_BARS_MAX < PHRASE_BARS_MAX


def test_song_markers_start_sections() -> None:
    bars = _bar_times(60.0)
    markers = [12.0, 36.0]
    sections = partition_pattern_mask_sections(
        bars, 60.0, random.Random(0), markers
    )
    starts = [start for start, _end in sections]
    assert 12.0 in starts
    assert 36.0 in starts


def _playlist(slot: str) -> PresetPlaylist:
    current_dir = Path(f"/tmp/presets/{slot}")
    return PresetPlaylist(
        current_dir=current_dir,
        paths=(current_dir / "preset-0.milk",),
        index=0,
    )


def _session(slots: tuple[str, ...], *, mode: str) -> TuningSession:
    session = TuningSession(
        layer_z_order=list(slots),
        layers={
            slot: LayerRuntime(
                playlist=_playlist(slot),
                browse_floor=Path(f"/tmp/presets/{slot}"),
                stem=TEST_LAYER_STEMS.get(slot, "drums"),
            )
            for slot in slots
        },
        timeline=TimelineRuntime(enabled=False),
    )
    session.timeline.timeline_preset_mode = mode  # type: ignore[assignment]
    session.timeline.timeline_preset_kind = "breathing"
    return session


def _controller(
    session: TuningSession, *, signals: Signals | None = None
) -> tuple[TimelinePresetController, list[str]]:
    notes: list[str] = []
    controller = TimelinePresetController(
        session,
        ModalHost(),
        beat_times=tuple(_beat_times()),
        bar_times=tuple(_bar_times()),
        signals=signals,
        on_notification=notes.append,
    )
    return controller, notes


def test_apply_pattern_mask_calls_builder_and_enables_mask() -> None:
    slots = ("layer_1", "layer_2", "layer_3", "layer_4")
    session = _session(slots, mode="pattern_mask")
    controller, notes = _controller(session)
    fake = {slot: TimelineLane(baseline=0.0, cues=[]) for slot in slots}
    with (
        patch(
            "cleave.viz.timeline_preset_controls.compose_pattern_mask_timeline",
            return_value=fake,
        ) as mock_pm,
        patch("cleave.viz.timeline_preset_controls.apply_crescendo") as mock_cresc,
        patch("cleave.viz.timeline_preset_controls.apply_accent") as mock_accent,
        patch(
            "cleave.viz.timeline_preset_controls.build_breathing_cues"
        ) as mock_breath,
    ):
        controller._apply("breathing", _DUR)
    mock_pm.assert_called_once()
    kwargs = mock_pm.call_args.kwargs
    assert "song_markers" in kwargs
    assert "beat_times" in kwargs
    mock_cresc.assert_not_called()
    mock_accent.assert_not_called()
    mock_breath.assert_not_called()
    assert session.render_pattern_mask.enabled is True
    assert session.render_pattern_mask.type == "strips"
    assert session.render_pattern_mask.feather_pct == 0
    assert session.render_pattern_mask.transition == 1.0
    assert notes == ["Applied pattern mask timeline"]


def test_apply_pattern_mask_passes_conductor_kwargs() -> None:
    slots = ("layer_1", "layer_2", "layer_3", "layer_4")
    session = _session(slots, mode="pattern_mask")
    session.timeline.timeline_preset_conductor = True
    signals = _make_signals()
    controller, _notes = _controller(session, signals=signals)
    fake = {slot: TimelineLane(baseline=0.0, cues=[]) for slot in slots}
    with patch(
        "cleave.viz.timeline_preset_controls.compose_pattern_mask_timeline",
        return_value=fake,
    ) as mock_pm:
        controller._apply("breathing", _DUR)
    kwargs = mock_pm.call_args.kwargs
    assert kwargs["signals"] is signals
    assert kwargs["slot_stems"] == {
        "layer_1": "drums",
        "layer_2": "bass",
        "layer_3": "vocals",
        "layer_4": "other",
    }


def test_apply_layers_mode_uses_character_builder() -> None:
    slots = ("layer_1", "layer_2", "layer_3", "layer_4")
    session = _session(slots, mode="layers")
    session.render_pattern_mask.enabled = False
    session.render_pattern_mask.transition = 0.0
    controller, notes = _controller(session)
    captured: dict = {}

    def _fake_builder(slot_list, duration_sec, rng, **kwargs):
        captured["kwargs"] = kwargs
        return {slot: TimelineLane(baseline=0.0, cues=[]) for slot in slot_list}

    with (
        patch.dict(
            "cleave.viz.timeline_preset_controls._KIND_BUILDERS",
            {"breathing": (_fake_builder, "Applied Breathing timeline preset")},
        ),
        patch(
            "cleave.viz.timeline_preset_controls.compose_pattern_mask_timeline"
        ) as mock_pm,
        patch(
            "cleave.viz.timeline_preset_controls.apply_crescendo",
            side_effect=lambda lanes, *args, **kwargs: lanes,
        ) as mock_cresc,
    ):
        controller._apply("breathing", _DUR)
    mock_pm.assert_not_called()
    mock_cresc.assert_called_once()
    assert "bar_times" in captured["kwargs"]
    assert session.render_pattern_mask.enabled is False
    assert session.render_pattern_mask.transition == 0.0
    assert notes == ["Applied Breathing timeline preset"]
