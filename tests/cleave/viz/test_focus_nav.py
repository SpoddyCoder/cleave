"""Unit tests for unified focus ring navigation."""

from __future__ import annotations

import pygame

from cleave.viz.focus_nav import (
    MainFocus,
    TimelineFocus,
    build_focus_ring,
    move_focus,
    resolve_cursor,
    timeline_strip_in_ring,
)
from cleave.viz.tuning_view_state import RenderTimelineBlock, TuningViewState
from cleave.viz.row_kinds import RowDescriptor, RowKind
from tests.cleave.viz.test_controls import (
    _desc,
    _keydown,
    _make_controls,
)
from tests.cleave.viz.test_overlay import _minimal_view_state
from tests.support.viz import make_track_block


def _timeline_open_state(
    slots: tuple[str, ...] = ("layer_1", "layer_2"),
) -> TuningViewState:
    tracks = {
        slot: make_track_block(
            stem="drums",
            preset_dir_label="dir",
            preset_label="preset.milk",
            blend_mode="black-key",
            opacity_pct=50,
            beat_sensitivity=1.0,
            effects={},
        )
        for slot in slots
    }
    return _minimal_view_state(
        layer_z_order=slots,
        tracks=tracks,
        render_timeline=RenderTimelineBlock(enabled=True, expanded=True),
    )


def test_timeline_strip_in_ring_requires_open_layers() -> None:
    closed = _minimal_view_state(
        render_timeline=RenderTimelineBlock(enabled=True, expanded=False),
    )
    assert timeline_strip_in_ring(closed) is False

    disabled_open = _minimal_view_state(
        render_timeline=RenderTimelineBlock(enabled=False, expanded=True),
    )
    assert timeline_strip_in_ring(disabled_open) is True

    empty = _minimal_view_state(layer_z_order=())
    assert timeline_strip_in_ring(empty) is False

    open_state = _timeline_open_state()
    assert timeline_strip_in_ring(open_state) is True


def test_build_focus_ring_without_timeline_segment() -> None:
    state = _minimal_view_state()
    ring = build_focus_ring(state)
    expected = [
        MainFocus(descriptor)
        for descriptor in state.layout.navigable_descriptors(state)
    ]
    assert ring == expected
    assert all(isinstance(item, MainFocus) for item in ring)


def test_build_focus_ring_includes_timeline_rows_when_strip_active() -> None:
    slots = ("layer_1", "layer_2", "layer_3")
    state = _timeline_open_state(slots)
    ring = build_focus_ring(state)
    main_part = [
        MainFocus(descriptor)
        for descriptor in state.layout.navigable_descriptors(state)
    ]
    timeline_part = [TimelineFocus(row) for row in range(len(slots))]
    assert ring == main_part + timeline_part


def test_move_focus_down_from_last_timeline_row_wraps_to_first_leftover() -> None:
    slots = ("layer_1", "layer_2", "layer_3", "layer_4")
    state = _timeline_open_state(slots)
    first = state.layout.navigable_descriptors(state)[0]
    cursor = TimelineFocus(len(slots) - 1)

    result = move_focus(cursor, 1, state)

    assert isinstance(result, MainFocus)
    assert result.descriptor == first


def test_move_focus_up_from_first_leftover_wraps_to_last_timeline_row() -> None:
    slots = ("layer_1", "layer_2", "layer_3", "layer_4")
    state = _timeline_open_state(slots)
    cursor = MainFocus(state.layout.navigable_descriptors(state)[0])

    result = move_focus(cursor, -1, state)

    assert result == TimelineFocus(len(slots) - 1)


def test_resolve_cursor_maps_stale_main_descriptor() -> None:
    state = _minimal_view_state()
    ring = build_focus_ring(state)
    stale = MainFocus(RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY))

    resolved = resolve_cursor(stale, ring, state)

    assert isinstance(resolved, MainFocus)
    assert resolved.descriptor == state.layout.navigable_descriptors(state)[0]
    assert resolved in ring


def test_resolve_cursor_clamps_timeline_row_when_layer_count_shrinks() -> None:
    slots = ("layer_1", "layer_2")
    state = _timeline_open_state(slots)
    ring = build_focus_ring(state)
    stale = TimelineFocus(9)

    resolved = resolve_cursor(stale, ring, state)

    assert resolved == TimelineFocus(1)
    assert resolved in ring


def test_move_focus_steps_through_main_ring() -> None:
    state = _minimal_view_state(
        render_timeline=RenderTimelineBlock(enabled=True, expanded=True),
    )
    ring = build_focus_ring(state)
    assert len(ring) >= 3
    start = ring[1]
    assert move_focus(start, 1, state) == ring[2]
    assert move_focus(start, -1, state) == ring[0]
    assert move_focus(start, len(ring), state) == start


def test_up_from_first_leftover_wraps_to_last_timeline_row() -> None:
    slots = ("layer_1", "layer_2", "layer_3", "layer_4")
    controls = _make_controls(slots, timeline_enabled=True)
    controls.session.timeline.panel_open = True
    view = controls.build_view_state(paused=False)
    controls.focus_descriptor = view.layout.navigable_descriptors(view)[0]

    controls.handle_keydown(_keydown(pygame.K_UP))
    assert isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.focus_cursor.row == len(slots) - 1
