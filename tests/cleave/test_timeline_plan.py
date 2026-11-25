"""The layers-mode planner: section shapes, intensity, weaving, and preset changes."""

from __future__ import annotations

import random
from itertools import product

import numpy as np
import pytest

from cleave.signals import Signals
from cleave.song_markers import SongMarker, resolve_sections, section_at
from cleave.timeline import lane_clips, lane_level_at, switching_clips
from cleave.timeline_presets.lanes import compose_layers_timeline
from cleave.timeline_presets.shapes import (
    LEVELS,
    layer_bounds,
    level_ranges,
    quantize,
    section_parts,
)

_DUR = 240.0
_BARS = [0.4 + 2.0 * i for i in range(120)]
_MARKERS = [
    SongMarker(16.4, "intro", "calm"),
    SongMarker(32.4, "verse"),
    SongMarker(64.4, "build", "calm"),
    SongMarker(80.4, "build"),
    SongMarker(96.4, "build", "intense"),
    SongMarker(112.4, "drop", "very intense"),
    SongMarker(144.4, "verse", "very calm"),
    SongMarker(160.4, "chorus", "intense"),
    SongMarker(192.4, "breakdown"),
    SongMarker(208.4, "outro"),
    SongMarker(224.4, "outro", "calm"),
]
_STEMS = ("drums", "bass", "vocals", "other")


def _signals() -> Signals:
    rate = 50.0
    t = np.arange(0.0, _DUR, 1.0 / rate)
    loud = 0.3 + 0.6 * ((t > 100) & (t < 200))
    wobble = 0.5 + 0.5 * np.sin(t / 7.0)
    return Signals(
        sample_rate_hz=rate,
        duration_sec=_DUR,
        path=__import__("pathlib").Path("."),
        stems={
            "drums": {"onset_strength": loud * wobble},
            "bass": {"rms": loud * (1.0 - wobble) + 0.05},
            "vocals": {"rms": 0.4 * wobble + 0.1},
            "other": {"rms": loud},
            "full_mix": {"rms": loud, "onset_strength": loud * 0.8},
        },
    )


_SIGNALS = _signals()


def _lanes(seed=1, n=4, density=0, conductor=True, markers=_MARKERS, bars=_BARS):
    slots = [f"layer_{i + 1}" for i in range(n)]
    kwargs: dict = {"bar_times": bars, "song_markers": markers, "density_bias": density}
    if conductor:
        kwargs["signals"] = _SIGNALS
        kwargs["slot_stems"] = {s: _STEMS[i % 4] for i, s in enumerate(slots)}
    return slots, compose_layers_timeline(slots, _DUR, random.Random(seed), **kwargs)


def _spans(lanes, slots):
    times = sorted({0.0} | {c.t for lane in lanes.values() for c in lane.cues})
    for a, b in zip(times, [*times[1:], _DUR]):
        levels = {s: lane_level_at(lanes[s], a, inherit=0.0) for s in slots}
        yield a, b, levels


_CASES = list(product(range(6), (1, 2, 4, 6, 8), (-2, 0, 2), (False, True)))


@pytest.mark.parametrize("seed,n,density,conductor", _CASES)
def test_brightness_rules(seed, n, density, conductor) -> None:
    slots, lanes = _lanes(seed, n, density, conductor)
    sections = resolve_sections(_MARKERS, _DUR)
    over = 0.0
    for a, b, levels in _spans(lanes, slots):
        on = sorted((v for v in levels.values() if v > 0), reverse=True)
        section = section_at(sections, 0.5 * (a + b))
        assert on, ("nothing on", a)
        # Never the whole stack of four flat out.
        assert sum(v >= 0.999 for v in on) < 4, (a, on)
        if section.intensity in ("normal", "intense", "very intense") and len(on) <= 2:
            # One or two layers: the brightest is at full.
            assert on[0] >= 0.999, (a, section, on)
        lo, hi = layer_bounds(section.intensity, n)
        # A swap may overlap by a bar or two.
        over = over + (b - a) if not lo <= len(on) <= hi else 0.0
        assert over <= 4.5, (a, section, on)


@pytest.mark.parametrize("seed,n", list(product(range(6), (2, 4, 8))))
def test_layers_never_rise_together_away_from_markers(seed, n) -> None:
    slots, lanes = _lanes(seed, n)
    markers = {0.0} | {m.time for m in _MARKERS}
    times = sorted({c.t for lane in lanes.values() for c in lane.cues})
    for t in times:
        rising = [
            s
            for s in slots
            if lane_level_at(lanes[s], t, inherit=0.0)
            > lane_level_at(lanes[s], t - 1e-4, inherit=0.0) + 1e-6
        ]
        assert len(rising) <= 1 or t in markers, (t, rising)


@pytest.mark.parametrize("seed,n", list(product(range(6), (1, 2, 4, 8))))
def test_held_layers_change_presets(seed, n) -> None:
    slots, lanes = _lanes(seed, n)
    for slot in slots:
        lane = lanes[slot]
        starts = sorted(
            {c.t for c in lane.cues if c.recast}
            | {c.start for c in switching_clips(lane_clips(lane, inherit=0.0, duration_sec=_DUR))}
        )
        for a, b in zip(starts, starts[1:]):
            held = lane_level_at(lane, a, inherit=0.0) > 0 and all(
                c.level > 0 for c in lane.cues if a < c.t < b
            )
            if held:
                assert b - a <= 48.0, (slot, a, b)
    # Every marker inside a song changes at least one held layer's preset.
    if n > 1:
        recasts = {round(c.t, 6) for lane in lanes.values() for c in lane.cues if c.recast}
        entries = {
            round(clip.start, 6)
            for lane in lanes.values()
            for clip in switching_clips(lane_clips(lane, inherit=0.0, duration_sec=_DUR))
        }
        for marker in _MARKERS:
            assert round(marker.time, 6) in recasts | entries, marker


def test_a_build_rises_across_its_whole_run() -> None:
    slots, lanes = _lanes(3, 4, conductor=False)

    def weight(t: float) -> float:
        return sum(lane_level_at(lanes[s], t, inherit=0.0) for s in slots)

    # Calm, then normal, then intense: lighter in the calm part, fullest at the end.
    assert weight(70.0) < weight(90.0) < weight(110.0)
    assert sum(lane_level_at(lanes[s], 111.0, inherit=0.0) > 0 for s in slots) == 4


def test_runs_join_back_to_back_markers() -> None:
    parts = section_parts(resolve_sections(_MARKERS, _DUR))
    builds = [p for p in parts if p.section.section_type == "build"]
    assert [p.first for p in builds] == [True, False, False]
    assert {(p.run_start, p.run_end) for p in builds} == {(64.4, 112.4)}
    plain = [p for p in parts if p.section.section_type == "standard"]
    assert all(p.first for p in plain)


def test_the_opening_is_arranged_like_any_plain_section() -> None:
    slots, lanes = _lanes(2, 4)
    counts = {
        sum(lane_level_at(lanes[s], t, inherit=0.0) > 0 for s in slots)
        for t in (1.0, 8.0, 15.0)
    }
    assert max(counts) >= 2


def test_same_seed_same_timeline() -> None:
    assert _lanes(5)[1] == _lanes(5)[1]


@pytest.mark.parametrize("markers,bars", [([], _BARS), (_MARKERS, []), ([], [])])
def test_without_markers_or_bars(markers, bars) -> None:
    slots, lanes = _lanes(1, 4, markers=markers, bars=bars)
    for a, b, levels in _spans(lanes, slots):
        assert any(v > 0 for v in levels.values()), a


def test_without_the_conductor_layers_keep_their_blends() -> None:
    _slots, lanes = _lanes(1, 4, conductor=False)
    assert all(c.role is None and c.blend is None for lane in lanes.values() for c in lane.cues)


def test_conductor_casts_one_lead_and_accents_a_chorus() -> None:
    slots, lanes = _lanes(1, 4)
    for a, _b, levels in _spans(lanes, slots):
        roles = [
            c.role
            for s in slots
            if levels[s] > 0
            for c in [max((c for c in lanes[s].cues if c.t <= a), key=lambda c: c.t)]
        ]
        assert roles.count("lead") <= 1, (a, roles)
    accents = [c.t for lane in lanes.values() for c in lane.cues if c.role == "accent"]
    assert any(abs(t - 160.4) < 1e-6 or abs(t - 112.4) < 1e-6 for t in accents)


def test_level_tables_match_their_layer_bounds() -> None:
    for intensity, table in LEVELS.items():
        for count, ranges in table.items():
            assert len(ranges) == count
            assert all(0.0 < lo <= hi <= 1.0 for lo, hi in ranges)
            assert [hi for _lo, hi in ranges] == sorted((hi for _lo, hi in ranges), reverse=True)
        lo, hi = layer_bounds(intensity, 4)
        assert min(table) <= lo and hi <= max(table)
    # A count a table lacks takes its nearest, with extra ranks below it.
    assert len(level_ranges("calm", 4)) == 4
    assert level_ranges("intense", 1) == ((1.0, 1.0),)
    assert quantize(0.62) == pytest.approx(0.6)
    assert quantize(0.0) == pytest.approx(0.05)


def test_an_unused_layer_is_off_not_inherited() -> None:
    _slots, lanes = _lanes(1, 8, markers=[SongMarker(0.0, "intro", "very calm")])
    assert all(lane.baseline == 0.0 for lane in lanes.values())
