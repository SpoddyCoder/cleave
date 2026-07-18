"""Tests for timeline panel cache and GPU upload signatures."""

from __future__ import annotations

import pygame

from cleave.config_schema import MAX_LAYER_COUNT
from cleave.timeline import SlotCue, TimelineLane, canonicalize
from cleave.viz.overlay_upload import upload_plan_for_signature
from cleave.viz.timeline_overlay import TimelineOverlay, TimelineViewState, timeline_live_signature
from cleave.viz.timeline_panel_cache import (
    timeline_panel_max_dimensions,
    timeline_static_signature,
    timeline_upload_signature,
)
from tests.cleave.viz.test_timeline_overlay import _view_state


def _static_sig(state: TimelineViewState, *, panel_w: int = 1260, panel_h: int = 120) -> object:
    return timeline_static_signature(
        state,
        panel_w=panel_w,
        panel_h=panel_h,
        visibility=1.0,
    )


def test_static_signature_stable_for_same_state() -> None:
    state = _view_state()
    assert _static_sig(state) == _static_sig(state)


def _lane(
    baseline: bool | None,
    *transitions: tuple[float, bool],
) -> TimelineLane:
    cues = [SlotCue(t=t, visible=v) for t, v in transitions]
    return TimelineLane(baseline=baseline, cues=canonicalize(baseline, cues))


def test_static_signature_changes_on_cue_edit() -> None:
    base = _view_state()
    edited = _view_state(lanes={"layer_1": _lane(True, (10.0, False))})
    assert _static_sig(base) != _static_sig(edited)


def test_static_signature_changes_on_layer_add() -> None:
    four = _view_state()
    five = _view_state(
        layer_z_order=["layer_1", "layer_2", "layer_3", "layer_4", "layer_5"],
        defaults={f"layer_{i}": True for i in range(1, 6)},
    )
    assert _static_sig(four) != _static_sig(five, panel_h=200)


def test_static_signature_changes_on_focus_change() -> None:
    unfocused = _view_state(submenu_focused=False, focus_row=0)
    focused = _view_state(submenu_focused=True, focus_row=1)
    assert _static_sig(unfocused) != _static_sig(focused)


def test_static_signature_stable_for_playhead_when_not_recording() -> None:
    paused = _view_state(position_sec=0.0, recording=False)
    moved = _view_state(position_sec=12.5, recording=False)
    assert _static_sig(paused) == _static_sig(moved)


def test_static_signature_changes_on_playhead_while_recording() -> None:
    """Armed bars grow with playhead; static cache must invalidate."""
    at_start = _view_state(
        position_sec=10.0,
        recording=True,
        armed_slots={"layer_1"},
        record_start_sec=10.0,
        record_baseline={"layer_1": True},
    )
    advanced = _view_state(
        position_sec=15.0,
        recording=True,
        armed_slots={"layer_1"},
        record_start_sec=10.0,
        record_baseline={"layer_1": True},
    )
    assert _static_sig(at_start) != _static_sig(advanced)


def test_static_signature_changes_on_show_bar_grid() -> None:
    hidden = _view_state(show_bar_grid=False, bar_grid_times=(0.0, 4.0))
    shown = _view_state(show_bar_grid=True, bar_grid_times=(0.0, 4.0))
    assert _static_sig(hidden) != _static_sig(shown)


def test_static_signature_changes_on_bar_grid_times() -> None:
    phase0 = _view_state(show_bar_grid=True, bar_grid_times=(0.0, 4.0))
    phase1 = _view_state(show_bar_grid=True, bar_grid_times=(1.0, 5.0))
    assert _static_sig(phase0) != _static_sig(phase1)


def test_static_signature_changes_on_song_marker_times() -> None:
    empty = _view_state(song_marker_times=())
    with_markers = _view_state(song_marker_times=(10.0, 40.0))
    assert _static_sig(empty) != _static_sig(with_markers)
    moved = _view_state(song_marker_times=(12.0, 40.0))
    assert _static_sig(with_markers) != _static_sig(moved)


def test_static_signature_changes_on_selected_song_marker_index() -> None:
    none_selected = _view_state(
        song_marker_times=(10.0, 40.0),
        selected_song_marker_index=None,
    )
    first = _view_state(
        song_marker_times=(10.0, 40.0),
        selected_song_marker_index=0,
    )
    second = _view_state(
        song_marker_times=(10.0, 40.0),
        selected_song_marker_index=1,
    )
    assert _static_sig(none_selected) != _static_sig(first)
    assert _static_sig(first) != _static_sig(second)


def test_static_signature_changes_on_standard_cue_fades_enabled() -> None:
    disabled = _view_state(standard_cue_fades_enabled=False)
    enabled = _view_state(standard_cue_fades_enabled=True)
    assert _static_sig(disabled) != _static_sig(enabled)


def test_static_signature_changes_on_song_marker_fades_enabled() -> None:
    disabled = _view_state(song_marker_fades_enabled=False)
    enabled = _view_state(song_marker_fades_enabled=True)
    assert _static_sig(disabled) != _static_sig(enabled)


def test_static_signature_changes_on_standard_cue_fade_in() -> None:
    short = _view_state(standard_cue_fades_enabled=True, standard_cue_fade_in=2.0)
    long = _view_state(standard_cue_fades_enabled=True, standard_cue_fade_in=4.0)
    assert _static_sig(short) != _static_sig(long)


def test_static_signature_changes_on_song_marker_fade_out() -> None:
    short = _view_state(song_marker_fades_enabled=True, song_marker_fade_out=2.0)
    long = _view_state(song_marker_fades_enabled=True, song_marker_fade_out=4.0)
    assert _static_sig(short) != _static_sig(long)


def test_compose_rebuilds_static_panel_when_recording_playhead_moves() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    kwargs = dict(viewport_width=1280, viewport_height=720)
    first_state = _view_state(
        position_sec=10.0,
        recording=True,
        armed_slots={"layer_1"},
        record_start_sec=10.0,
        record_baseline={"layer_1": True},
    )
    first = overlay.compose_panel(first_state, **kwargs)
    assert first is not None
    cached_panel = overlay._cache.panel
    assert cached_panel is not None

    second_state = _view_state(
        position_sec=15.0,
        recording=True,
        armed_slots={"layer_1"},
        record_start_sec=10.0,
        record_baseline={"layer_1": True},
    )
    second = overlay.compose_panel(second_state, **kwargs)
    assert second is not None
    assert overlay._cache.panel is not cached_panel


def test_live_signature_changes_on_position_sec() -> None:
    pygame.init()
    paused = _view_state(position_sec=0.0)
    moved = _view_state(position_sec=12.5)
    kwargs = dict(playhead_px=100, bar_left=80, bar_width=900, row_count=4, row_h=20)
    assert timeline_live_signature(paused, **kwargs) != timeline_live_signature(
        moved, **kwargs
    )


def test_live_signature_changes_on_playhead_flash() -> None:
    pygame.init()
    state = _view_state(position_sec=10.0)
    kwargs = dict(playhead_px=100, bar_left=80, bar_width=900, row_count=4, row_h=20)
    bright = timeline_live_signature(state, ticks_ms=0, **kwargs)
    dim = timeline_live_signature(state, ticks_ms=400, **kwargs)
    assert bright != dim


def test_upload_plan_skip_when_paused_and_unchanged() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = _view_state(position_sec=30.0)
    first = overlay.compose_panel(state, viewport_width=1280, viewport_height=720)
    assert first is not None

    cache = overlay._cache
    cache.gpu.last_signature = first.upload_signature
    cache.gpu.last_texture_id = 1
    cache.gpu.capacity = first.capacity

    second = overlay.compose_panel(state, viewport_width=1280, viewport_height=720)
    assert second is not None
    assert second.upload_plan.mode == "skip"


def test_upload_plan_partial_when_position_moves() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    kwargs = dict(viewport_width=1280, viewport_height=720)
    first = overlay.compose_panel(_view_state(position_sec=0.0), **kwargs)
    assert first is not None

    cache = overlay._cache
    cache.gpu.last_signature = first.upload_signature
    cache.gpu.last_texture_id = 1
    cache.gpu.capacity = first.capacity

    second = overlay.compose_panel(_view_state(position_sec=25.0), **kwargs)
    assert second is not None
    assert second.upload_plan.mode == "partial"
    assert second.upload_plan.dirty_rects


def test_timeline_panel_max_dimensions_uses_max_layer_count() -> None:
    pygame.init()
    w, h = timeline_panel_max_dimensions(1280, 720)
    overlay = TimelineOverlay()
    max_rows = _view_state(
        layer_z_order=[f"layer_{i}" for i in range(1, MAX_LAYER_COUNT + 1)],
        defaults={f"layer_{i}": True for i in range(1, MAX_LAYER_COUNT + 1)},
    )
    composed = overlay.compose_panel(max_rows, viewport_width=1280, viewport_height=720)
    assert composed is not None
    assert composed.capacity == (w, h)
    assert composed.upload_surface.get_height() <= h


def test_upload_signature_pairs_static_and_live() -> None:
    state = _view_state(position_sec=5.0)
    static = _static_sig(state)
    live = timeline_live_signature(
        state,
        playhead_px=120,
        bar_left=80,
        bar_width=900,
        row_count=len(state.layer_z_order),
        row_h=20,
    )
    screen_rect = (10, 500, 1260, 150)
    sig = timeline_upload_signature(static, screen_rect, live)
    assert sig.active_size == (1260, 150)
    assert sig.content_hash == (static, live)
    plan = upload_plan_for_signature(sig, sig)
    assert plan.mode == "skip"
