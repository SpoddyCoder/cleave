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
from cleave.timeline import (
    LEVEL_EPS,
    TimelineFadeGroup,
    TimelineLane,
    empty_lane,
    lane_level_at,
    lane_on_transition_cues,
)
from cleave.timeline_presets.arrange import PHRASE_BARS_MIN, PHRASE_BARS_MAX
from cleave.timeline_presets.pattern_mask_arrange import (
    SECTION_BARS_MAX,
    SECTION_LONG_BARS_MAX,
    SECTION_LONG_BARS_MIN,
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
    transition_duration: float = 0.0,
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
        transition_duration=transition_duration,
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


def _slot_set_change_times(
    lanes: dict[str, TimelineLane], slots: list[str]
) -> list[float]:
    times = sorted({0.0, *_all_cue_times(lanes)})
    changes: list[float] = []
    prev: frozenset[str] | None = None
    for t in times:
        active = _active_at(lanes, slots, t + 1e-6 if t > 0.0 else 0.0)
        if prev is not None and active != prev:
            changes.append(t)
        prev = active
    return changes


def _mutation_events(
    lanes: dict[str, TimelineLane], slots: list[str]
) -> list[tuple[float, frozenset[str], frozenset[str]]]:
    events: list[tuple[float, frozenset[str], frozenset[str]]] = []
    for t in _slot_set_change_times(lanes, slots):
        prev = _active_at(lanes, slots, t - 1e-6)
        after = _active_at(lanes, slots, t + 1e-6)
        events.append((t, after - prev, prev - after))
    return events


def _isolated_add_remove_times(
    lanes: dict[str, TimelineLane], slots: list[str]
) -> list[tuple[float, frozenset[str], frozenset[str]]]:
    events = _mutation_events(lanes, slots)
    isolated: list[tuple[float, frozenset[str], frozenset[str]]] = []
    for index, (t, added, removed) in enumerate(events):
        if added and removed:
            continue
        if added and not removed:
            if index + 1 < len(events):
                _t2, added2, removed2 = events[index + 1]
                if removed2 and not added2 and added.isdisjoint(removed2):
                    continue
            isolated.append((t, added, removed))
            continue
        if removed and not added:
            if index > 0:
                _t1, added1, removed1 = events[index - 1]
                if added1 and not removed1 and added1.isdisjoint(removed):
                    continue
            isolated.append((t, added, removed))
    return isolated


def _overlap_pairs(
    lanes: dict[str, TimelineLane], slots: list[str]
) -> list[tuple[float, float]]:
    events = _mutation_events(lanes, slots)
    pairs: list[tuple[float, float]] = []
    for index, (t_on, added, removed) in enumerate(events):
        if not added or removed:
            continue
        for t_off, added2, removed2 in events[index + 1 :]:
            if added2:
                break
            if removed2 and added.isdisjoint(removed2):
                mid = _active_at(lanes, slots, (t_on + t_off) * 0.5)
                if added <= mid:
                    pairs.append((t_on, t_off))
                break
    return pairs


def test_overlap_when_add_then_remove() -> None:
    """With no wipe duration, 1-2 beat add-then-remove windows still appear."""
    slots = _slots(4)
    found = False
    for seed in range(20):
        lanes = _compose(slots, seed=seed, transition_duration=0.0)
        if _overlap_pairs(lanes, slots):
            found = True
            break
    assert found, "expected a 1-2 beat window where an added layer overlaps a departing one"


def test_transition_duration_keeps_consecutive_changes_apart() -> None:
    """Add-then-remove overlap stays at least one wipe; isolated gaps may be closer."""
    slots = _slots(4)
    duration = 1.0
    for seed in range(20):
        lanes = _compose(slots, seed=seed, transition_duration=duration)
        for t_on, t_off in _overlap_pairs(lanes, slots):
            assert t_off - t_on >= duration - 1e-9, (
                f"seed={seed} overlap {t_off - t_on:.4f}s inside transition_duration"
            )


def test_transition_duration_overlap_has_wipe_plus_hold() -> None:
    slots = _slots(4)
    duration = 1.0
    hold = _BEAT_SEC
    saw_overlap = False
    for seed in range(30):
        lanes = _compose(slots, seed=seed, transition_duration=duration)
        for t_on, t_off in _overlap_pairs(lanes, slots):
            saw_overlap = True
            assert t_off - t_on >= duration + hold - 1e-9, (
                f"seed={seed} overlap {t_off - t_on:.4f}s shorter than "
                f"transition plus one beat"
            )
    assert saw_overlap, "expected at least one add-then-remove that still fits"


def test_isolated_add_remove_times_ignore_transition_duration() -> None:
    slots = _slots(4)
    for seed in range(12):
        zero = _compose(slots, seed=seed, transition_duration=0.0)
        wipe = _compose(slots, seed=seed, transition_duration=1.0)
        assert _isolated_add_remove_times(zero, slots) == _isolated_add_remove_times(
            wipe, slots
        )


def test_count_distribution_two_three_mode() -> None:
    slots = _slots(4)
    histogram: Counter[int] = Counter()
    for seed in range(30):
        lanes = _compose(slots, seed=seed)
        for n in _sample_counts(lanes, slots, _DUR):
            histogram[n] += 1
            assert n >= 1, f"active count {n} dropped below 1"
            assert n <= 4
    two_three = histogram[2] + histogram[3]
    assert two_three > histogram[4]
    assert two_three > histogram[1]
    assert histogram[2] > 0 and histogram[3] > 0
    mode = max((1, 2, 3, 4), key=lambda k: histogram[k])
    assert mode in (2, 3)


def test_five_plus_rare_without_crescendo() -> None:
    slots = _slots(6)
    histogram: Counter[int] = Counter()
    for seed in range(20):
        lanes = _compose(slots, seed=seed)
        for n in _sample_counts(lanes, slots, _DUR, step=1.0):
            histogram[n] += 1
            assert n >= 1
    five_plus = sum(histogram[k] for k in histogram if k >= 5)
    two_three = histogram[2] + histogram[3]
    assert two_three > histogram[1]
    assert five_plus < two_three * 0.35


def test_unmarked_one_layer_is_rare_minority() -> None:
    slots = _slots(4)
    ones = 0
    total = 0
    saw_one = False
    for seed in range(30):
        lanes = _compose(slots, seed=seed)
        counts = _sample_counts(lanes, slots, _DUR)
        if 1 in counts:
            saw_one = True
        ones += sum(1 for n in counts if n == 1)
        total += len(counts)
    assert saw_one, "expected at least one 1-layer sample across unmarked seeds"
    assert ones < total * 0.5, "1-layer samples should be the minority"


def test_interior_markers_change_slot_set_at_marker_time() -> None:
    slots = _slots(4)
    markers = [
        SongMarker(12.0, "standard"),
        SongMarker(36.0, "sustain"),
        SongMarker(60.0, "diminuendo"),
    ]
    for seed in range(15):
        lanes = _compose(slots, seed=seed, song_markers=markers)
        changes = _slot_set_change_times(lanes, slots)
        for marker in markers:
            prev = _active_at(lanes, slots, marker.time - 1e-6)
            after = _active_at(lanes, slots, marker.time + 1e-6)
            assert prev != after, (
                f"seed={seed} marker {marker.marker_type}@{marker.time} "
                "had no slot-set change"
            )
            assert any(abs(t - marker.time) <= 1e-6 for t in changes), (
                f"seed={seed} marker {marker.time} mutation was not on the marker"
            )


def test_begin_section_starts_at_one_layer() -> None:
    slots = _slots(4)
    markers = [SongMarker(16.0, "begin"), SongMarker(48.0, "crescendo")]
    for seed in range(15):
        lanes = _compose(slots, seed=seed, song_markers=markers)
        assert len(_active_at(lanes, slots, 16.0 + 1e-6)) == 1, f"seed={seed}"


def test_crescendo_drops_from_multiple_to_one() -> None:
    slots = _slots(4)
    markers = [SongMarker(20.0, "begin"), SongMarker(40.0, "crescendo")]
    for seed in range(15):
        lanes = _compose(slots, seed=seed, song_markers=markers)
        before = _active_at(lanes, slots, 40.0 - 1e-6)
        after = _active_at(lanes, slots, 40.0 + 1e-6)
        assert len(before) >= 2, f"seed={seed} pre-crescendo count {len(before)}"
        assert len(after) == 1, f"seed={seed} crescendo count {len(after)}"
        changes = _slot_set_change_times(lanes, slots)
        assert any(abs(t - 40.0) <= 1e-6 for t in changes), f"seed={seed}"


def test_role_bias_lead_then_pulse_then_accent_bed() -> None:
    slots = _slots(4)
    roles: Counter[str] = Counter()
    for seed in range(25):
        lanes = _compose(slots, seed=seed)
        for lane in lanes.values():
            for cue in lane.cues:
                if cue.level > LEVEL_EPS and cue.role is not None:
                    roles[cue.role] += 1
    assert roles["lead"] > roles["pulse"] > roles["accent"] > roles["bed"]
    assert roles["bed"] > 0


def test_active_levels_are_full() -> None:
    slots = _slots(4)
    lanes = _compose(slots, seed=7)
    for t in _all_cue_times(lanes) + [0.0, 60.0]:
        for level in _level_at(lanes, slots, t).values():
            if level > LEVEL_EPS:
                assert abs(level - 1.0) <= LEVEL_EPS


def test_continuing_slot_recast_is_on_transition() -> None:
    slots = _slots(4)
    fade_off = TimelineFadeGroup(enabled=False)
    found = 0
    for seed in range(40):
        lanes = _compose(slots, seed=seed)
        for slot, lane in lanes.items():
            pairs = lane_on_transition_cues(
                lane, hard_cut_fades=fade_off, soft_cut_fades=fade_off
            )
            on_transition_times = {cue.t for _t, cue in pairs if cue.recast}
            for cue in lane.cues:
                if not cue.recast:
                    continue
                assert abs(cue.level - 1.0) <= LEVEL_EPS
                prev = lane_level_at(lane, cue.t - 1e-6, inherit=0.0)
                after = lane_level_at(lane, cue.t + 1e-6, inherit=0.0)
                assert prev > LEVEL_EPS
                assert after > LEVEL_EPS
                assert slot in _active_at(lanes, slots, cue.t - 1e-6)
                assert slot in _active_at(lanes, slots, cue.t + 1e-6)
                cues_at_t = [
                    other
                    for other_lane in lanes.values()
                    for other in other_lane.cues
                    if abs(other.t - cue.t) <= 1e-9
                ]
                if cues_at_t and all(other.recast for other in cues_at_t):
                    assert _active_at(lanes, slots, cue.t - 1e-6) == _active_at(
                        lanes, slots, cue.t + 1e-6
                    )
                assert cue.t in on_transition_times
                found += 1
    assert found > 0, "expected recast cues on continuing slots"


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


def _section_bar_counts(
    sections: list[tuple[float, float]], bars: list[float]
) -> list[int]:
    return [sum(1 for b in bars if start <= b < end) for start, end in sections]


def test_sections_shorter_than_layers_phrases() -> None:
    bars = _bar_times()
    rng = random.Random(4)
    sections = partition_pattern_mask_sections(bars, _DUR, rng, ())
    assert sections
    bar_counts = _section_bar_counts(sections, bars)
    core = bar_counts[:-1]
    assert core
    short = sum(1 for n in core if n <= 2)
    assert short > len(core) - short
    assert sum(1 for n in bar_counts if SECTION_LONG_BARS_MIN <= n <= SECTION_LONG_BARS_MAX) <= 1
    assert sum(core) / len(core) < PHRASE_BARS_MIN
    assert SECTION_BARS_MAX < PHRASE_BARS_MAX
    for seed in range(40):
        seeded = partition_pattern_mask_sections(
            bars, _DUR, random.Random(seed), ()
        )
        counts = _section_bar_counts(seeded, bars)
        long_n = sum(
            1
            for n in counts
            if SECTION_LONG_BARS_MIN <= n <= SECTION_LONG_BARS_MAX
        )
        assert long_n <= 1, f"seed={seed} had {long_n} long sections"


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
    assert kwargs["transition_duration"] == 1.0
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
