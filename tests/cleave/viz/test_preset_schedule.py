"""What each row shows of its presets, and timer slices as clips."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cleave.timeline import SlotCue, TimelineLane, clip_at, lane_clips
from cleave.viz.clip_presets import CONTINUES_GLYPH
from cleave.viz.preset_schedule import (
    PROJECTM_LABEL,
    RowPresets,
    bake_timer_slices,
    label_at,
    row_labels,
    timer_slices,
)
from cleave.viz.preset_switching import clip_switch_at
from tests.support.preset_list import entries
from tests.support.viz import make_controls

A, B, C = entries("/p/a.milk", "/p/b.milk", "/p/c.milk")
LANE = TimelineLane(
    baseline=0.0,
    cues=[
        SlotCue(t=5.0, level=0.5, role="lead", cut="soft"),
        SlotCue(t=48.0, level=0.0, cut="hard"),
        SlotCue(t=52.0, level=1.0),
        SlotCue(t=70.0, level=0.6),
        SlotCue(t=95.0, level=0.0),
    ],
)


def _clips(lane=LANE):
    return lane_clips(lane, inherit=1.0, duration_sec=100.0)


@pytest.mark.parametrize("listing", [[A], [A, B], [A, B, C], [A, A, B]])
@pytest.mark.parametrize("period", [5.0, 7.3, 20.0, 300.0])
def test_slices_match_timer_playback(listing, period) -> None:
    slices = timer_slices(_clips(), period, listing)
    for step in range(1000):
        t = step / 10.0 + 0.01
        part = next((s for s in slices if s.start <= t < s.end), None)
        if clip_at(_clips(), t) is None:
            assert part is None
        else:
            expected = listing[math.floor(t / period) % len(listing)]
            assert part is not None and part.entry.file == expected.file


def test_a_clip_opening_inside_a_shown_slice_continues() -> None:
    texts = [
        (lab.start, lab.text)
        for lab in row_labels(
            _clips(), RowPresets("timer", 60.0, (A, B)), timeline_enabled=True
        )
    ]
    assert texts == [
        (5.0, "a"),
        (52.0, CONTINUES_GLYPH),
        (60.0, "b"),
        (70.0, CONTINUES_GLYPH),
    ]


def test_a_preset_that_played_another_in_the_gap_is_named_again() -> None:
    lane = TimelineLane(
        baseline=0.0,
        cues=[
            SlotCue(t=0.0, level=1.0),
            SlotCue(t=10.0, level=0.0),
            SlotCue(t=20.0, level=1.0),
        ],
    )
    labels = row_labels(
        _clips(lane), RowPresets("timer", 10.0, (A, B)), timeline_enabled=True
    )
    assert labels[1].start == 20.0 and labels[1].text == "a"


@pytest.mark.parametrize(
    ("presets", "first"),
    [
        (RowPresets("off", layer_preset="x.milk"), "x"),
        (RowPresets("projectm", entries=(A,)), PROJECTM_LABEL),
    ],
)
def test_never_and_projectm_name_the_first_clip_only(presets, first) -> None:
    labels = row_labels(_clips(), presets, timeline_enabled=True)
    assert [lab.text for lab in labels] == [first, CONTINUES_GLYPH, CONTINUES_GLYPH]
    assert row_labels(_clips(), presets, timeline_enabled=False) == []


@pytest.mark.parametrize("trigger", ["timer", "projectm"])
def test_an_empty_list_names_nothing(trigger) -> None:
    assert row_labels(_clips(), RowPresets(trigger, 10.0), timeline_enabled=True) == []


def test_each_clip_marks_empty_clips_apart_from_continuing_ones() -> None:
    lane = TimelineLane(
        baseline=0.0,
        cues=[
            SlotCue(t=0.0, level=1.0, preset=A),
            SlotCue(t=10.0, level=1.0, anchor=True),
            SlotCue(t=20.0, level=1.0, recast=True),
        ],
    )
    labels = row_labels(_clips(lane), RowPresets("timeline"), timeline_enabled=False)
    assert [lab.text for lab in labels] == ["a", CONTINUES_GLYPH, CONTINUES_GLYPH]
    assert [lab.empty for lab in labels] == [False, False, True]
    assert label_at(labels, 25.0) is labels[2]


@pytest.mark.parametrize("period", [5.0, 7.0, 20.0, 47.9, 300.0])
def test_baking_keeps_the_look_and_plays_what_the_timer_played(period) -> None:
    controls = make_controls(("layer_1",), duration_sec=100.0)
    session = controls.session
    layer = session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    layer.preset_duration = period
    layer.preset_list = [A, B, C]
    session.timeline.enabled = True
    session.timeline.lanes["layer_1"] = replace(LANE, cues=list(LANE.cues))
    bake_timer_slices(session, "layer_1", 100.0)
    layer.preset_switching_trigger = "timeline"
    after = _clips(session.timeline.lanes["layer_1"])
    for step in range(1000):
        t = step / 10.0 + 0.01
        old, new = clip_at(_clips(), t), clip_at(after, t)
        assert (old is None) == (new is None)
        if old is None or new is None:
            continue
        assert (old.level, old.blend, old.role) == (new.level, new.blend, new.role)
        edge = min(t - old.start, old.end - t)
        if edge > 0.6:
            expected = [A, B, C][math.floor(t / period) % 3].file
            assert clip_switch_at(session, "layer_1", t)[1] == expected, t
    assert after[0].cut_in == "soft"
    assert next(c for c in after if c.end == 48.0).cut_out == "hard"


@pytest.mark.parametrize("trigger", ["off", "timer", "projectm", "timeline"])
def test_the_strip_draws_names_and_redraws_when_they_change(trigger) -> None:
    import pygame

    from cleave.viz.timeline_overlay import TimelineOverlay
    from cleave.viz.timeline_panel_cache import timeline_static_signature
    from cleave.viz.timeline_strip_state import TimelineViewState

    def state(presets: RowPresets) -> TimelineViewState:
        return TimelineViewState(
            layer_z_order=["layer_1"],
            lanes={"layer_1": LANE},
            defaults={"layer_1": 1.0},
            position_sec=0.0,
            duration_sec=100.0,
            focus_row=0,
            monitor_visible={"layer_1": True},
            slot_stems={"layer_1": "drums"},
            enabled=True,
            presets={"layer_1": presets},
        )

    def signature(presets: RowPresets):
        return timeline_static_signature(
            state(presets), panel_w=800, panel_h=120, visibility=1.0
        )

    base = RowPresets(trigger, 20.0, (A, B), "x.milk")
    for other in (
        replace(base, period=30.0),
        replace(base, entries=(B, A)),
        replace(base, layer_preset="y.milk"),
    ):
        assert signature(base) != signature(other)

    pygame.font.init()

    def pixels(presets: RowPresets, *, enabled: bool = True) -> bytes:
        surface = pygame.Surface((1280, 400), pygame.SRCALPHA)
        view = state(presets)
        view.enabled = enabled
        TimelineOverlay().draw(surface, view)
        return pygame.image.tobytes(surface, "RGBA")

    unnamed = RowPresets(trigger)
    if trigger != "timeline":
        assert pixels(base) != pixels(unnamed)
        assert pixels(base, enabled=False) == pixels(unnamed, enabled=False)
    else:
        # These clips hold no preset: the red hooked arrow shows either way.
        assert pixels(base) != pixels(RowPresets("off"))
