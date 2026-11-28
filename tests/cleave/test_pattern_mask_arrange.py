"""Tests for the pattern-mask timeline arranger and Apply routing."""

from __future__ import annotations

import random
from pathlib import Path
from unittest.mock import patch

import numpy as np

from cleave.stems import StemSource
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
from cleave.timeline_presets.mask_options import TimelinePresetMaskChanges
from cleave.timeline_presets.pattern_mask_arrange import (
    compose_pattern_mask_timeline,
    mask_layer_range,
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
    transition_duration: float = 1.0,
    changes: TimelinePresetMaskChanges = "normal",
) -> dict[str, TimelineLane]:
    return compose_pattern_mask_timeline(
        slots,
        duration_sec,
        random.Random(seed),
        _bar_times(duration_sec),
        song_markers=song_markers or (),
        density_bias=density_bias,
        signals=signals,
        slot_stems=slot_stems,
        beat_times=_beat_times(duration_sec),
        transition_duration=transition_duration,
        changes=changes,
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


def _change_times(lanes: dict[str, TimelineLane]) -> list[float]:
    """Times the set of layers on changes: the wipes."""
    return sorted({cue.t for lane in lanes.values() for cue in lane.cues if not cue.recast})


def _changes_between(lanes: dict[str, TimelineLane], t0: float, t1: float) -> int:
    return sum(1 for t in _change_times(lanes) if t0 < t < t1)


_SONG = [
    SongMarker(0.0, "intro", "calm"),
    SongMarker(16.0, "verse"),
    SongMarker(32.0, "build"),
    SongMarker(40.0, "build", "intense"),
    SongMarker(48.0, "drop", "very intense"),
    SongMarker(64.0, "breakdown", "very calm"),
    SongMarker(80.0, "bridge"),
    SongMarker(88.0, "chorus", "intense"),
    SongMarker(104.0, "outro"),
]



def test_single_slot_stays_on() -> None:
    slots = _slots(1)
    lanes = _compose(slots)
    assert _active_at(lanes, slots, 0.0) == frozenset(slots)
    assert _active_at(lanes, slots, _DUR - 1.0) == frozenset(slots)


def test_empty_slots_or_duration_returns_empty() -> None:
    assert _compose([]) == {}
    assert _compose(_slots(3), duration_sec=0.0) == {}


def test_layer_range_drops_to_one_only_when_calm() -> None:
    for intensity in ("very calm", "calm", "normal", "intense", "very intense"):
        floor = 1 if intensity in ("very calm", "calm") else 2
        for n in range(3, 9):
            for bias in range(-2, 3):
                lo, hi = mask_layer_range(intensity, n, bias)  # type: ignore[arg-type]
                assert floor <= lo <= hi <= n
    assert mask_layer_range("calm", 4) == (1, 3)
    assert mask_layer_range("very calm", 2) == (1, 2)
    # Only intense sections may show every layer.
    assert mask_layer_range("normal", 3)[1] == 2
    assert mask_layer_range("very intense", 4)[1] == 4
    assert mask_layer_range("very intense", 8)[0] > mask_layer_range("very intense", 4)[0]


def test_two_or_more_layers_on_outside_calm_sections() -> None:
    for n in (3, 4, 6, 8):
        slots = _slots(n)
        for seed in range(6):
            lanes = _compose(slots, seed=seed)
            assert min(_sample_counts(lanes, slots, _DUR)) >= 2, (n, seed)
            lanes = _compose(slots, seed=seed, song_markers=_SONG)
            # The drop: very intense, straight after a build.
            counts = [len(_active_at(lanes, slots, 48.0 + 0.25 * i + 0.01)) for i in range(64)]
            assert min(counts) >= 2, (n, seed)


def test_a_calm_section_sometimes_shows_one_layer() -> None:
    slots = _slots(4)
    for kind in ("intro", "breakdown", "outro"):
        counts: list[int] = []
        for seed in range(10):
            lanes = _compose(
                slots,
                seed=seed,
                song_markers=[SongMarker(0.0), SongMarker(16.0, kind, "calm"), SongMarker(80.0)],
            )
            counts += [len(_active_at(lanes, slots, 16.0 + 0.25 * i + 0.01)) for i in range(256)]
        assert 1 in counts, kind
        assert any(n >= 2 for n in counts), kind


def test_two_layers_take_turns() -> None:
    slots = _slots(2)
    lanes = _compose(slots, seed=1)
    counts = _sample_counts(lanes, slots, _DUR)
    assert min(counts) >= 1
    assert len(_change_times(lanes)) > 5


def test_normal_sections_leave_a_layer_out() -> None:
    slots = _slots(4)
    for seed in range(6):
        lanes = _compose(slots, seed=seed)
        assert max(_sample_counts(lanes, slots, _DUR)) <= 3, seed


def test_active_levels_are_full() -> None:
    slots = _slots(4)
    lanes = _compose(slots, seed=3, song_markers=_SONG)
    for lane in lanes.values():
        for cue in lane.cues:
            assert cue.level <= LEVEL_EPS or abs(cue.level - 1.0) <= LEVEL_EPS


def test_every_marker_changes_the_layers() -> None:
    slots = _slots(4)
    for seed in range(10):
        lanes = _compose(slots, seed=seed, song_markers=_SONG)
        for marker in _SONG[1:]:
            before = _active_at(lanes, slots, marker.time - 1e-3)
            after = _active_at(lanes, slots, marker.time + 1e-3)
            assert before != after, (seed, marker)


def test_wipes_have_room_to_play_out() -> None:
    slots = _slots(4)
    for transition in (0.5, 1.0, 2.0):
        for seed in range(6):
            lanes = _compose(
                slots, seed=seed, song_markers=_SONG, transition_duration=transition
            )
            times = _change_times(lanes)
            gaps = [b - a for a, b in zip(times, times[1:])]
            assert min(gaps) >= transition + _BEAT_SEC - 1e-6, (transition, seed)


def test_intensity_sets_how_often_layers_change() -> None:
    slots = _slots(4)
    calm = loud = 0
    for seed in range(8):
        lanes = _compose(
            slots,
            seed=seed,
            song_markers=[SongMarker(0.0, intensity="very calm"), SongMarker(60.0, intensity="very intense")],
        )
        calm += _changes_between(lanes, 0.0, 60.0)
        loud += _changes_between(lanes, 60.0, _DUR)
    assert loud > 2 * calm
    assert calm > 0


def test_layer_changes_option_scales_the_pace() -> None:
    slots = _slots(4)
    totals = {}
    for changes in ("fewer", "normal", "more"):
        totals[changes] = sum(
            len(_change_times(_compose(slots, seed=seed, changes=changes)))  # type: ignore[arg-type]
            for seed in range(8)
        )
    # Each step is a clear change, not a nudge.
    assert 2 * totals["fewer"] < totals["normal"]
    assert 1.3 * totals["normal"] < totals["more"]


def test_a_build_starts_sparser_than_a_plain_section_and_ends_busier() -> None:
    slots = _slots(4)
    build_start = build_end = plain_start = plain_end = 0
    for seed in range(8):
        # A 32-bar section after an opening, so neither starts the song.
        for kind in ("build", None):
            lanes = _compose(
                slots,
                seed=seed,
                song_markers=[SongMarker(0.0), SongMarker(8.0, kind), SongMarker(72.0)],
            )
            start = _changes_between(lanes, 8.0, 24.0)
            end = _changes_between(lanes, 56.0, 72.0)
            if kind == "build":
                build_start, build_end = build_start + start, build_end + end
            else:
                plain_start, plain_end = plain_start + start, plain_end + end
    assert build_start < plain_start
    assert build_end > plain_end


def test_a_build_rises_across_its_markers_to_every_layer() -> None:
    slots = _slots(4)
    early = late = 0
    for seed in range(10):
        lanes = _compose(slots, seed=seed, song_markers=_SONG)
        counts = [len(_active_at(lanes, slots, 32.0 + 0.25 * i + 0.01)) for i in range(64)]
        assert counts == sorted(counts), seed
        # Every layer only on its last bar.
        assert counts[-1] == 4 and counts[-9] < 4, seed
        early += _changes_between(lanes, 32.0, 40.0)
        late += _changes_between(lanes, 40.0, 48.0)
    # Changes come faster as it goes.
    assert late > early


def test_drop_and_chorus_open_with_a_big_change() -> None:
    slots = _slots(6)
    for seed in range(10):
        lanes = _compose(slots, seed=seed, song_markers=_SONG)
        for t in (48.0, 88.0):
            before = _active_at(lanes, slots, t - 1e-3)
            after = _active_at(lanes, slots, t + 1e-3)
            assert len(after ^ before) >= 2, (seed, t)


def test_bridge_brings_in_layers_that_were_out() -> None:
    slots = _slots(6)
    for seed in range(10):
        lanes = _compose(slots, seed=seed, song_markers=_SONG)
        before = _active_at(lanes, slots, 80.0 - 1e-3)
        after = _active_at(lanes, slots, 80.0 + 1e-3)
        assert len(after - before) >= min(len(after), 6 - len(before)), seed


def test_breakdown_holds_the_fewest() -> None:
    slots = _slots(4)
    for seed in range(10):
        lanes = _compose(slots, seed=seed, song_markers=_SONG)
        counts = [len(_active_at(lanes, slots, 64.0 + 0.25 * i + 0.01)) for i in range(64)]
        assert sum(n <= 2 for n in counts) >= 0.75 * len(counts), seed


def test_an_outro_only_thins_out() -> None:
    slots = _slots(4)
    for seed in range(10):
        lanes = _compose(slots, seed=seed, song_markers=_SONG)
        counts = [len(_active_at(lanes, slots, 104.0 + 0.25 * i + 0.01)) for i in range(60)]
        assert counts == sorted(counts, reverse=True), seed


def test_continuing_slot_recast_is_on_transition() -> None:
    slots = _slots(4)
    fade_off = TimelineFadeGroup(enabled=False)
    found = 0
    for seed in range(20):
        lanes = _compose(slots, seed=seed, song_markers=_SONG)
        for slot, lane in lanes.items():
            pairs = lane_on_transition_cues(
                lane, hard_cut_fades=fade_off, soft_cut_fades=fade_off
            )
            on_transition_times = {cue.t for _t, cue in pairs if cue.recast}
            for cue in lane.cues:
                if not cue.recast:
                    continue
                assert abs(cue.level - 1.0) <= LEVEL_EPS
                assert lane_level_at(lane, cue.t - 1e-6, inherit=0.0) > LEVEL_EPS
                assert slot in _active_at(lanes, slots, cue.t + 1e-6)
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


def _roles(lanes: dict[str, TimelineLane]) -> set[str | None]:
    return {cue.role for lane in lanes.values() for cue in lane.cues if cue.level > LEVEL_EPS}


_SLOT_STEMS: dict[str, StemSource] = {
    "layer_1": "drums",
    "layer_2": "bass",
    "layer_3": "vocals",
    "layer_4": "other",
}


def test_conductor_biases_busy_stems() -> None:
    slots = _slots(4)
    signals = _make_signals()
    drums_first = vocals_first = drums_second = vocals_second = 0.0
    mid = _DUR * 0.5
    for seed in range(8):
        lanes = _compose(slots, seed=seed, signals=signals, slot_stems=_SLOT_STEMS)
        drums_first += _airtime(lanes, "layer_1", 0.0, mid)
        vocals_first += _airtime(lanes, "layer_3", 0.0, mid)
        drums_second += _airtime(lanes, "layer_1", mid, _DUR)
        vocals_second += _airtime(lanes, "layer_3", mid, _DUR)
    assert drums_first > vocals_first
    assert vocals_second > drums_second


def test_roles_only_with_the_conductor() -> None:
    slots = _slots(4)
    assert _roles(_compose(slots, seed=2)) == {None}
    with_conductor = _compose(
        slots, seed=2, signals=_make_signals(), slot_stems=_SLOT_STEMS
    )
    assert "lead" in _roles(with_conductor)


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
    session.pattern_mask.type = "radial"
    session.timeline.timeline_preset_mask_changes = "more"
    controller, notes = _controller(session)
    fake = {slot: TimelineLane(baseline=0.0, cues=[]) for slot in slots}
    with (
        patch(
            "cleave.viz.timeline_preset_controls.compose_pattern_mask_timeline",
            return_value=fake,
        ) as mock_pm,
        patch(
            "cleave.viz.timeline_preset_controls.compose_layers_timeline"
        ) as mock_layers,
    ):
        controller._apply(_DUR)
    mock_pm.assert_called_once()
    kwargs = mock_pm.call_args.kwargs
    assert "song_markers" in kwargs
    assert "beat_times" in kwargs
    # The Pattern Mask page's default transition: 1 beat, at 120 bpm.
    assert kwargs["transition_duration"] == 0.5
    assert kwargs["changes"] == "more"
    mock_layers.assert_not_called()
    assert session.pattern_mask.enabled is True
    # keep leaves the Pattern Mask page's pattern.
    assert session.pattern_mask.type == "radial"
    assert session.pattern_mask.transition == 1.0
    assert session.pattern_mask.transition_unit == "beats"
    assert notes == ["Generated pattern mask timeline"]


def test_apply_pattern_mask_sets_the_pattern_and_keeps_the_transition() -> None:
    slots = ("layer_1", "layer_2", "layer_3")
    session = _session(slots, mode="pattern_mask")
    session.timeline.timeline_preset_mask_pattern = "checker"
    session.pattern_mask.transition_unit = "bars"
    session.pattern_mask.transition = 1.0
    controller, _notes = _controller(session)
    with patch(
        "cleave.viz.timeline_preset_controls.compose_pattern_mask_timeline",
        return_value={slot: TimelineLane(baseline=0.0, cues=[]) for slot in slots},
    ) as mock_pm:
        controller._apply(_DUR)
    assert session.pattern_mask.type == "checker"
    assert (session.pattern_mask.transition_unit, session.pattern_mask.transition) == ("bars", 1.0)
    assert mock_pm.call_args.kwargs["transition_duration"] == _BAR_SEC


def test_pattern_mask_mode_leaves_layer_opacity() -> None:
    slots = ("layer_1", "layer_2", "layer_3")
    session = _session(slots, mode="pattern_mask")
    session.timeline.timeline_preset_full_opacity = True
    for slot in slots:
        session.layers[slot].opacity_pct = 50
    controller, _notes = _controller(session)
    controller._apply(_DUR)
    assert all(session.layers[slot].opacity_pct == 50 for slot in slots)


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
        controller._apply(_DUR)
    kwargs = mock_pm.call_args.kwargs
    assert kwargs["signals"] is signals
    assert kwargs["slot_stems"] == {
        "layer_1": "drums",
        "layer_2": "bass",
        "layer_3": "vocals",
        "layer_4": "other",
    }


def test_apply_layers_mode_uses_the_planner() -> None:
    slots = ("layer_1", "layer_2", "layer_3", "layer_4")
    session = _session(slots, mode="layers")
    session.pattern_mask.enabled = False
    session.pattern_mask.transition = 0.0
    controller, notes = _controller(session)
    captured: dict = {}

    def _fake_builder(slot_list, duration_sec, rng, **kwargs):
        captured["kwargs"] = kwargs
        return {slot: TimelineLane(baseline=0.0, cues=[]) for slot in slot_list}

    with (
        patch(
            "cleave.viz.timeline_preset_controls.compose_layers_timeline",
            side_effect=_fake_builder,
        ),
        patch(
            "cleave.viz.timeline_preset_controls.compose_pattern_mask_timeline"
        ) as mock_pm,
    ):
        controller._apply(_DUR)
    mock_pm.assert_not_called()
    assert "bar_times" in captured["kwargs"]
    assert session.pattern_mask.enabled is False
    assert session.pattern_mask.transition == 0.0
    assert notes == ["Generated timeline"]
