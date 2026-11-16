"""Tests for timeline panel cache and GPU upload signatures."""

from __future__ import annotations

import pygame

from cleave.config_schema.layers import MAX_LAYER_COUNT
from cleave.timeline import SlotCue, TimelineLane, canonicalize
from cleave.viz.overlay_upload import upload_plan_for_signature
from cleave.viz.timeline_overlay import TimelineOverlay
from cleave.viz.timeline_strip_live import live_flash_signature, timeline_live_signature
from cleave.viz.timeline_strip_state import TimelineViewState
from cleave.viz.timeline_panel_cache import (
    timeline_panel_max_dimensions,
    timeline_static_signature,
    timeline_upload_signature,
)
from tests.support.timeline import strip_view_state


def _static_sig(state: TimelineViewState, *, panel_w: int = 1260, panel_h: int = 120) -> object:
    return timeline_static_signature(
        state,
        panel_w=panel_w,
        panel_h=panel_h,
        visibility=1.0,
    )


def test_static_signature_stable_for_same_state() -> None:
    state = strip_view_state()
    assert _static_sig(state) == _static_sig(state)


def as_level(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return float(value)


def make_lane(baseline, *transitions) -> TimelineLane:
    base = as_level(baseline)
    cues = [SlotCue(t=t, level=float(as_level(level))) for t, level in transitions]
    return TimelineLane(baseline=base, cues=canonicalize(base, cues))


def test_static_signature_changes_on_cue_edit() -> None:
    base = strip_view_state()
    edited = strip_view_state(lanes={"layer_1": make_lane(True, (10.0, False))})
    assert _static_sig(base) != _static_sig(edited)


def test_static_signature_changes_on_layer_add() -> None:
    four = strip_view_state()
    five = strip_view_state(
        layer_z_order=["layer_1", "layer_2", "layer_3", "layer_4", "layer_5"],
        defaults={f"layer_{i}": 1.0 for i in range(1, 6)},
    )
    assert _static_sig(four) != _static_sig(five, panel_h=200)


def test_static_signature_changes_on_focus_change() -> None:
    unfocused = strip_view_state(submenu_focused=False, focus_row=0)
    focused = strip_view_state(submenu_focused=True, focus_row=1)
    assert _static_sig(unfocused) != _static_sig(focused)


def test_static_signature_stable_for_playhead_when_not_recording() -> None:
    paused = strip_view_state(position_sec=0.0, recording=False)
    moved = strip_view_state(position_sec=12.5, recording=False)
    assert _static_sig(paused) == _static_sig(moved)


def test_static_signature_changes_on_playhead_while_recording() -> None:
    """Armed bars grow with playhead; static cache must invalidate."""
    at_start = strip_view_state(
        position_sec=10.0,
        recording=True,
        armed_slots={"layer_1"},
        record_start_sec=10.0,
        record_baseline={"layer_1": 1.0},
    )
    advanced = strip_view_state(
        position_sec=15.0,
        recording=True,
        armed_slots={"layer_1"},
        record_start_sec=10.0,
        record_baseline={"layer_1": 1.0},
    )
    assert _static_sig(at_start) != _static_sig(advanced)


def test_static_signature_changes_on_show_bar_grid() -> None:
    hidden = strip_view_state(show_bar_grid=False, bar_grid_times=(0.0, 4.0))
    shown = strip_view_state(show_bar_grid=True, bar_grid_times=(0.0, 4.0))
    assert _static_sig(hidden) != _static_sig(shown)


def test_static_signature_changes_on_bar_grid_times() -> None:
    phase0 = strip_view_state(show_bar_grid=True, bar_grid_times=(0.0, 4.0))
    phase1 = strip_view_state(show_bar_grid=True, bar_grid_times=(1.0, 5.0))
    assert _static_sig(phase0) != _static_sig(phase1)


def test_static_signature_changes_on_song_marker_times() -> None:
    empty = strip_view_state(song_marker_times=())
    with_markers = strip_view_state(song_marker_times=(10.0, 40.0))
    assert _static_sig(empty) != _static_sig(with_markers)
    moved = strip_view_state(song_marker_times=(12.0, 40.0))
    assert _static_sig(with_markers) != _static_sig(moved)


def test_static_signature_changes_on_selected_song_marker_index() -> None:
    none_selected = strip_view_state(
        song_marker_times=(10.0, 40.0),
        selected_song_marker_index=None,
    )
    first = strip_view_state(
        song_marker_times=(10.0, 40.0),
        selected_song_marker_index=0,
    )
    second = strip_view_state(
        song_marker_times=(10.0, 40.0),
        selected_song_marker_index=1,
    )
    assert _static_sig(none_selected) != _static_sig(first)
    assert _static_sig(first) != _static_sig(second)


def test_static_signature_changes_on_selected_clip_t() -> None:
    none_selected = strip_view_state(
        lanes={"layer_1": make_lane(True, (10.0, False), (20.0, True))},
    )
    first = strip_view_state(
        lanes={"layer_1": make_lane(True, (10.0, False), (20.0, True))},
        selected_clip_t={"layer_1": 10.0},
    )
    second = strip_view_state(
        lanes={"layer_1": make_lane(True, (10.0, False), (20.0, True))},
        selected_clip_t={"layer_1": 20.0},
    )
    assert _static_sig(none_selected) != _static_sig(first)
    assert _static_sig(first) != _static_sig(second)


def test_static_signature_changes_on_cue_blend_and_role() -> None:
    level_only = strip_view_state(
        lanes={
            "layer_1": TimelineLane(
                baseline=0.0,
                cues=canonicalize(0.0, [SlotCue(t=10.0, level=1.0)]),
            )
        }
    )
    with_blend = strip_view_state(
        lanes={
            "layer_1": TimelineLane(
                baseline=0.0,
                cues=canonicalize(
                    0.0, [SlotCue(t=10.0, level=1.0, blend="add")]
                ),
            )
        }
    )
    with_role = strip_view_state(
        lanes={
            "layer_1": TimelineLane(
                baseline=0.0,
                cues=canonicalize(
                    0.0, [SlotCue(t=10.0, level=1.0, role="lead")]
                ),
            )
        }
    )
    assert _static_sig(level_only) != _static_sig(with_blend)
    assert _static_sig(level_only) != _static_sig(with_role)
    assert _static_sig(with_blend) != _static_sig(with_role)


def test_static_signature_changes_on_cue_cut() -> None:
    none_cut = strip_view_state(
        lanes={
            "layer_1": TimelineLane(
                baseline=0.0,
                cues=canonicalize(0.0, [SlotCue(t=10.0, level=1.0)]),
            )
        }
    )
    hard_cut = strip_view_state(
        lanes={
            "layer_1": TimelineLane(
                baseline=0.0,
                cues=canonicalize(
                    0.0, [SlotCue(t=10.0, level=1.0, cut="hard")]
                ),
            )
        }
    )
    soft_cut = strip_view_state(
        lanes={
            "layer_1": TimelineLane(
                baseline=0.0,
                cues=canonicalize(
                    0.0, [SlotCue(t=10.0, level=1.0, cut="soft")]
                ),
            )
        }
    )
    assert _static_sig(none_cut) != _static_sig(hard_cut)
    assert _static_sig(none_cut) != _static_sig(soft_cut)
    assert _static_sig(hard_cut) != _static_sig(soft_cut)


def test_static_signature_changes_on_soft_cut_fades_enabled() -> None:
    disabled = strip_view_state(soft_cut_fades_enabled=False)
    enabled = strip_view_state(soft_cut_fades_enabled=True)
    assert _static_sig(disabled) != _static_sig(enabled)


def test_static_signature_changes_on_hard_cut_fades_enabled() -> None:
    disabled = strip_view_state(hard_cut_fades_enabled=False)
    enabled = strip_view_state(hard_cut_fades_enabled=True)
    assert _static_sig(disabled) != _static_sig(enabled)


def test_static_signature_changes_on_soft_cut_fade_in() -> None:
    short = strip_view_state(soft_cut_fades_enabled=True, soft_cut_fade_in=2.0)
    long = strip_view_state(soft_cut_fades_enabled=True, soft_cut_fade_in=4.0)
    assert _static_sig(short) != _static_sig(long)


def test_static_signature_changes_on_hard_cut_fade_out() -> None:
    short = strip_view_state(hard_cut_fades_enabled=True, hard_cut_fade_out=2.0)
    long = strip_view_state(hard_cut_fades_enabled=True, hard_cut_fade_out=4.0)
    assert _static_sig(short) != _static_sig(long)


def test_static_signature_changes_on_hard_cut_crossfade() -> None:
    edge = strip_view_state(hard_cut_fades_enabled=True, hard_cut_crossfade=False)
    centered = strip_view_state(hard_cut_fades_enabled=True, hard_cut_crossfade=True)
    assert _static_sig(edge) != _static_sig(centered)


def test_static_signature_changes_on_soft_cut_crossfade() -> None:
    edge = strip_view_state(soft_cut_fades_enabled=True, soft_cut_crossfade=False)
    centered = strip_view_state(soft_cut_fades_enabled=True, soft_cut_crossfade=True)
    assert _static_sig(edge) != _static_sig(centered)


def test_compose_rebuilds_static_panel_when_recording_playhead_moves() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    kwargs = dict(viewport_width=1280, viewport_height=720)
    first_state = strip_view_state(
        position_sec=10.0,
        recording=True,
        armed_slots={"layer_1"},
        record_start_sec=10.0,
        record_baseline={"layer_1": 1.0},
    )
    first = overlay.compose_panel(first_state, **kwargs)
    assert first is not None
    cached_panel = overlay._cache.panel
    assert cached_panel is not None

    second_state = strip_view_state(
        position_sec=15.0,
        recording=True,
        armed_slots={"layer_1"},
        record_start_sec=10.0,
        record_baseline={"layer_1": 1.0},
    )
    second = overlay.compose_panel(second_state, **kwargs)
    assert second is not None
    assert overlay._cache.panel is not cached_panel


def test_live_signature_ignores_position_at_same_playhead_px() -> None:
    pygame.init()
    early = strip_view_state(position_sec=12.0)
    late = strip_view_state(position_sec=12.5)
    kwargs = dict(
        playhead_px=100, bar_left=80, bar_width=900, row_count=4, row_h=20, ticks_ms=0
    )
    assert timeline_live_signature(early, **kwargs) == timeline_live_signature(
        late, **kwargs
    )


def test_live_signature_changes_on_playhead_flash() -> None:
    pygame.init()
    state = strip_view_state(position_sec=10.0)
    kwargs = dict(playhead_px=100, bar_left=80, bar_width=900, row_count=4, row_h=20)
    bright = timeline_live_signature(state, ticks_ms=0, **kwargs)
    dim = timeline_live_signature(state, ticks_ms=400, **kwargs)
    assert bright != dim


def test_live_signature_changes_on_selected_clip_flash_phase(monkeypatch) -> None:
    pygame.init()
    from cleave.viz.timeline_strip_flash import SELECTED_CLIP_FLASH_HALF_MS

    overlay = TimelineOverlay()
    start = 10_000
    state = strip_view_state(
        position_sec=10.0,
        selected_clip_t={"layer_1": 10.0},
        selected_clip_flash_start_ms=start,
        lanes={"layer_1": make_lane(True, (10.0, False))},
    )
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: start)
    bright = live_flash_signature(state)
    monkeypatch.setattr(
        pygame.time, "get_ticks", lambda: start + SELECTED_CLIP_FLASH_HALF_MS
    )
    alt = live_flash_signature(state)
    assert bright
    assert bright != alt


def test_upload_plan_skip_when_paused_and_unchanged(monkeypatch) -> None:
    pygame.init()
    # Playhead blink is in the live signature. Pin the clock so two composes
    # of an unchanged paused view stay on one flash phase and skip the upload.
    monkeypatch.setattr(pygame.time, "get_ticks", lambda: 1_000)
    overlay = TimelineOverlay()
    state = strip_view_state(position_sec=30.0)
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
    first = overlay.compose_panel(strip_view_state(position_sec=0.0), **kwargs)
    assert first is not None

    cache = overlay._cache
    cache.gpu.last_signature = first.upload_signature
    cache.gpu.last_texture_id = 1
    cache.gpu.capacity = first.capacity

    second = overlay.compose_panel(strip_view_state(position_sec=25.0), **kwargs)
    assert second is not None
    assert second.upload_plan.mode == "partial"
    assert second.upload_plan.dirty_rects


def test_timeline_panel_max_dimensions_uses_max_layer_count() -> None:
    pygame.init()
    w, h = timeline_panel_max_dimensions(1280, 720)
    overlay = TimelineOverlay()
    max_rows = strip_view_state(
        layer_z_order=[f"layer_{i}" for i in range(1, MAX_LAYER_COUNT + 1)],
        defaults={f"layer_{i}": True for i in range(1, MAX_LAYER_COUNT + 1)},
    )
    composed = overlay.compose_panel(max_rows, viewport_width=1280, viewport_height=720)
    assert composed is not None
    assert composed.capacity == (w, h)
    assert composed.upload_surface.get_height() <= h


def test_upload_signature_pairs_static_and_live() -> None:
    state = strip_view_state(position_sec=5.0)
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


def test_static_signature_changes_with_the_view_window() -> None:
    from dataclasses import replace

    state = strip_view_state(position_sec=5.0)
    whole = _static_sig(state)
    zoomed = _static_sig(replace(state, view_start_sec=10.0, view_end_sec=30.0))
    panned = _static_sig(replace(state, view_start_sec=20.0, view_end_sec=40.0))
    assert whole != zoomed
    assert zoomed != panned


def test_taller_band_grows_rows_and_keeps_icons_nominal() -> None:
    pygame.init()
    overlay = TimelineOverlay()
    state = strip_view_state(
        layer_z_order=["layer_1", "layer_2"],
        defaults={"layer_1": True, "layer_2": True},
    )
    fit = overlay.compose_panel(state, viewport_width=1280, viewport_height=720)
    assert fit is not None
    fit_layout = overlay.layout
    tall = overlay.compose_panel(
        state,
        viewport_width=1280,
        viewport_height=720,
        timeline_rect=(0, 320, 1280, 400),
    )
    assert tall is not None
    layout = overlay.layout
    assert layout.row_h > fit_layout.row_h
    assert layout.icon_h == fit_layout.row_h
    assert layout.slot_w == fit_layout.slot_w
    assert layout.panel_y + layout.panel_h == 720
    assert layout.panel_y - layout.badge_reserve >= 320
