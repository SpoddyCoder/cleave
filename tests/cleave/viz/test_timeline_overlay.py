"""Tests for the bottom timeline strip overlay."""

from __future__ import annotations

import pygame

from cleave.extract import STEM_NAMES
from cleave.timeline import TimelineCue, stem_abbreviation
from cleave.viz.timeline_overlay import (
    TimelineOverlay,
    TimelineViewState,
    playhead_x,
    time_to_x,
    unique_cue_times,
    visibility_segments,
)


def _view_state(
    *,
    cues: list[TimelineCue] | None = None,
    defaults: dict[str, bool] | None = None,
    position_sec: float = 0.0,
    duration_sec: float = 100.0,
    focus_row: int = 0,
    armed_stems: set[str] | None = None,
    recording: bool = False,
    enabled: bool = True,
    layer_z_order: list[str] | None = None,
) -> TimelineViewState:
    return TimelineViewState(
        layer_z_order=list(layer_z_order or STEM_NAMES),
        cues=list(cues or []),
        defaults=dict(defaults or {stem: True for stem in STEM_NAMES}),
        position_sec=position_sec,
        duration_sec=duration_sec,
        focus_row=focus_row,
        armed_stems=set(armed_stems or ()),
        recording=recording,
        enabled=enabled,
    )


def test_visibility_segments_default_only() -> None:
    defaults = {"drums": True, "bass": False, "vocals": True, "other": True}
    segments = visibility_segments([], defaults, "bass", 60.0)
    assert segments == [(0.0, 60.0, False)]


def test_visibility_segments_from_cues() -> None:
    defaults = {stem: True for stem in STEM_NAMES}
    cues = [
        TimelineCue(t=10.0, layers={"drums": False}),
        TimelineCue(t=30.0, layers={"drums": True}),
    ]
    segments = visibility_segments(cues, defaults, "drums", 60.0)
    assert segments == [
        (0.0, 10.0, True),
        (10.0, 30.0, False),
        (30.0, 60.0, True),
    ]


def test_visibility_segments_other_stem_unchanged_across_unrelated_cue() -> None:
    defaults = {stem: True for stem in STEM_NAMES}
    cues = [TimelineCue(t=5.0, layers={"drums": False})]
    segments = visibility_segments(cues, defaults, "bass", 20.0)
    assert segments == [(0.0, 5.0, True), (5.0, 20.0, True)]


def test_unique_cue_times_clamps_to_duration() -> None:
    cues = [
        TimelineCue(t=-1.0, layers={"drums": False}),
        TimelineCue(t=5.0, layers={"bass": False}),
        TimelineCue(t=50.0, layers={"vocals": False}),
    ]
    assert unique_cue_times(cues, 10.0) == [5.0]


def test_stem_labels_use_abbreviations() -> None:
    assert stem_abbreviation("drums") == "D"
    assert stem_abbreviation("bass") == "B"
    assert stem_abbreviation("vocals") == "V"
    assert stem_abbreviation("other") == "O"


def test_playhead_x_at_known_position() -> None:
    bar_left = 40
    bar_width = 200
    duration = 100.0
    assert playhead_x(0.0, bar_left, bar_width, duration) == bar_left
    assert playhead_x(50.0, bar_left, bar_width, duration) == bar_left + 100
    assert playhead_x(100.0, bar_left, bar_width, duration) == bar_left + bar_width


def test_time_to_x_clamps_out_of_range() -> None:
    bar_left = 10
    bar_width = 90
    assert time_to_x(-5.0, bar_left, bar_width, 60.0) == bar_left
    assert time_to_x(120.0, bar_left, bar_width, 60.0) == bar_left + bar_width


def test_draw_does_not_crash() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(
        cues=[TimelineCue(t=25.0, layers={"drums": False})],
        position_sec=25.0,
        focus_row=1,
        armed_stems={"bass"},
        recording=True,
    )
    surface = pygame.Surface((1280, 720), pygame.SRCALPHA)
    overlay.draw(surface, state)

    panel = overlay.panel_rect
    assert panel is not None
    px, py, pw, ph = panel
    sw, sh = surface.get_size()
    assert px >= 0 and py >= 0
    assert px + pw <= sw and py + ph <= sh
    surface.subsurface(panel)


def test_draw_skipped_when_disabled() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(enabled=False)
    surface = pygame.Surface((640, 360), pygame.SRCALPHA)
    overlay.draw(surface, state)
    assert overlay.panel_rect is None


def test_armed_row_layout_recorded() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(armed_stems={"drums"}, layer_z_order=list(STEM_NAMES))
    surface = pygame.Surface((800, 400), pygame.SRCALPHA)
    overlay.draw(surface, state)

    drums_layout = next(row for row in overlay.row_layout if row[5] == "drums")
    row_index, x, y, w, h, stem = drums_layout
    assert stem == "drums"
    assert row_index == 0
    assert w > 0 and h > 0
    assert overlay.panel_rect is not None


def test_focus_row_index_matches_stem() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(focus_row=2, layer_z_order=list(STEM_NAMES))
    surface = pygame.Surface((800, 400), pygame.SRCALPHA)
    overlay.draw(surface, state)

    vocals_layout = next(row for row in overlay.row_layout if row[5] == "vocals")
    assert vocals_layout[0] == 2
    assert overlay.panel_rect is not None
