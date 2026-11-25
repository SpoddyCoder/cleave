"""Song sections in the layers arranger, and the build overlay."""

from __future__ import annotations

import random

import pytest

from cleave.song_markers import SongMarker, resolve_sections
from cleave.timeline import SlotCue, TimelineLane, lane_level_at, lane_role_at
from cleave.timeline_presets import ALL_BUILDERS
from cleave.timeline_presets.build import apply_build, resolve_build_windows
from cleave.timeline_presets.sections import (
    climax_section,
    fit_layers,
    layer_range,
)

_DUR = 180.0
_BARS = [i * 2.0 for i in range(90)]
_MARKERS = [
    SongMarker(0.0, "intro"),
    SongMarker(16.3, "verse"),
    SongMarker(40.0, "build"),
    SongMarker(56.0, "drop"),
    SongMarker(80.5, "breakdown"),
    SongMarker(96.0, "chorus"),
    SongMarker(130.0),
    SongMarker(150.0, "bridge"),
    SongMarker(166.0, "verse"),
]


def _slots(n: int) -> list[str]:
    return [f"layer_{i + 1}" for i in range(n)]


def _count(lanes, slots, t: float) -> int:
    return sum(lane_level_at(lanes[slot], t, inherit=0.0) > 0.0 for slot in slots)


@pytest.mark.parametrize("builder", ALL_BUILDERS)
@pytest.mark.parametrize("bars", [_BARS, []])
@pytest.mark.parametrize("n", [1, 2, 4, 8])
@pytest.mark.parametrize("bias", [-2, 0, 2])
def test_typed_sections_stay_in_range_from_their_start(builder, bars, n, bias) -> None:
    slots = _slots(n)
    for seed in range(3):
        lanes = builder(
            slots,
            _DUR,
            random.Random(seed),
            bar_times=bars,
            song_markers=_MARKERS,
            density_bias=bias,
        )
        for section in resolve_sections(_MARKERS, _DUR):
            if not section.typed:
                continue
            t = section.start
            while t < section.end - 1e-6:
                lo, hi = layer_range(section, t, n, bias)
                assert lo <= _count(lanes, slots, t) <= hi, (section, seed, t)
                t += 0.5


def test_outro_winds_down_to_one_layer() -> None:
    slots = _slots(4)
    markers = [SongMarker(140.0, "outro")]
    for builder in ALL_BUILDERS:
        lanes = builder(
            slots, _DUR, random.Random(1), bar_times=_BARS, song_markers=markers
        )
        assert _count(lanes, slots, 140.0) == 2
        assert _count(lanes, slots, 162.0) == 1
        assert _count(lanes, slots, 179.0) == 1


def test_drop_trades_layers_when_there_are_spares() -> None:
    slots = _slots(8)
    lanes = ALL_BUILDERS[0](
        slots,
        _DUR,
        random.Random(0),
        bar_times=_BARS,
        song_markers=[SongMarker(60.0, "drop"), SongMarker(90.0)],
    )
    changes = {
        cue.t for lane in lanes.values() for cue in lane.cues if 60.0 < cue.t < 90.0
    }
    assert len(changes) >= 3


def test_bridge_leaves_out_the_layer_leading_before_it() -> None:
    slots = _slots(4)
    markers = [SongMarker(40.0, "breakdown"), SongMarker(60.0, "bridge")]
    lanes = ALL_BUILDERS[0](
        slots, _DUR, random.Random(2), bar_times=_BARS, song_markers=markers
    )
    (before,) = [s for s in slots if lane_level_at(lanes[s], 59.0, inherit=0.0) > 0]
    assert all(
        lane_level_at(lanes[before], float(t), inherit=0.0) == 0.0
        for t in range(60, 180)
    )


def test_climax_is_the_last_drop_then_the_last_chorus() -> None:
    sections = resolve_sections(_MARKERS, _DUR)
    climax = climax_section(sections)
    assert climax is not None and climax.start == 56.0
    sections = resolve_sections(
        [SongMarker(10.0, "chorus"), SongMarker(50.0, "chorus")], _DUR
    )
    climax = climax_section(sections)
    assert climax is not None and climax.start == 50.0
    assert climax_section(resolve_sections([], _DUR)) is None


@pytest.mark.parametrize("builder", ALL_BUILDERS)
def test_climax_past_the_last_detected_bar(builder) -> None:
    slots = _slots(4)
    bars = [t for t in _BARS if t < 150.0]
    for markers in (
        [SongMarker(100.0, "chorus"), SongMarker(160.0, "drop")],
        [SongMarker(100.0), SongMarker(160.0, "drop"), SongMarker(170.0, "verse")],
    ):
        lanes = builder(
            slots, _DUR, random.Random(0), bar_times=bars, song_markers=markers
        )
        assert _count(lanes, slots, 160.0) == 4
        assert _count(lanes, slots, 169.0) == 4


def test_climax_before_the_first_detected_bar() -> None:
    slots = _slots(4)
    bars = [t for t in _BARS if t > 40.0]
    markers = [SongMarker(10.0, "drop"), SongMarker(30.0)]
    for builder in ALL_BUILDERS:
        lanes = builder(
            slots, _DUR, random.Random(0), bar_times=bars, song_markers=markers
        )
        assert _count(lanes, slots, 10.0) == 4


def test_fit_layers_avoids_until_it_would_run_short() -> None:
    order = _slots(3)
    avoid = frozenset({"layer_1"})
    fitted = fit_layers(frozenset({"layer_1"}), 1, 2, order, {}, {}, avoid=avoid)
    assert fitted and "layer_1" not in fitted
    assert fit_layers(frozenset(), 3, 3, order, {}, {}, avoid=avoid) == set(order)


def test_build_windows_hold_the_last_bar() -> None:
    markers = [SongMarker(40.0, "build"), SongMarker(56.0, "drop")]
    (window,) = resolve_build_windows(markers, _DUR, _BARS)
    assert (window.t_start, window.t_full, window.t_end) == (40.0, 54.0, 56.0)
    # A marker just past a bar line holds the bar before it.
    (window,) = resolve_build_windows(
        [SongMarker(40.0, "build"), SongMarker(56.3, "drop")], _DUR, _BARS
    )
    assert window.t_full == 54.0
    # The build may open or close the song, and needs no bars.
    (window,) = resolve_build_windows([SongMarker(0.0, "build")], _DUR)
    assert 0.0 < window.t_full < window.t_end == _DUR


def test_build_rewrites_only_its_section() -> None:
    slots = _slots(4)
    lanes = {
        "layer_1": TimelineLane(
            0.0,
            [
                SlotCue(0.0, 1.0, role="lead", blend="black-key"),
                SlotCue(48.0, 0.0),
                SlotCue(70.0, 0.5, role="bed", blend="black-key"),
            ],
        ),
        "layer_2": TimelineLane(
            0.0, [SlotCue(0.0, 1.0, role="pulse", blend="black-key")]
        ),
        "layer_3": TimelineLane(0.0, []),
        "layer_4": TimelineLane(0.0, []),
    }
    markers = [
        SongMarker(40.0, "build"),
        SongMarker(48.0, "build"),
        SongMarker(60.0, "drop"),
    ]
    after = apply_build(
        lanes,
        slots,
        duration_sec=_DUR,
        bar_times=_BARS,
        song_markers=markers,
        rng=random.Random(3),
    )
    for t in [*range(0, 40), *range(60, 180)]:
        for slot in slots:
            assert lane_level_at(after[slot], t, inherit=0.0) == lane_level_at(
                lanes[slot], t, inherit=0.0
            )
            if lane_level_at(lanes[slot], t, inherit=0.0) > 0:
                assert lane_role_at(after[slot], t) == lane_role_at(lanes[slot], t)
    assert _count(after, slots, 40.0) == 1
    assert _count(after, slots, 47.9) == 4
    assert _count(after, slots, 48.0) == 1
    assert _count(after, slots, 59.9) == 4


def test_apply_build_without_builds_returns_the_lanes() -> None:
    lanes = {"layer_1": TimelineLane(0.0, [])}
    assert (
        apply_build(
            lanes,
            ["layer_1"],
            duration_sec=_DUR,
            bar_times=_BARS,
            song_markers=[SongMarker(10.0, "drop")],
            rng=random.Random(0),
        )
        is lanes
    )
