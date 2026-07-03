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
from cleave.viz.tuning_view_state import RenderTimelineBlock, TrackBlock, TuningViewState
from cleave.viz.row_semantics import RowDescriptor, RowKind
from tests.cleave.viz.test_controls import (
    _desc,
    _keydown,
    _make_controls,
)
from tests.cleave.viz.test_overlay import _minimal_view_state


def _timeline_open_state(
    slots: tuple[str, ...] = ("layer_1", "layer_2"),
) -> TuningViewState:
    tracks = {
        slot: TrackBlock(
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


def test_timeline_strip_in_ring_requires_open_enabled_layers() -> None:
    closed = _minimal_view_state(
        render_timeline=RenderTimelineBlock(enabled=True, expanded=False),
    )
    assert timeline_strip_in_ring(closed) is False

    disabled = _minimal_view_state(
        render_timeline=RenderTimelineBlock(enabled=False, expanded=True),
    )
    assert timeline_strip_in_ring(disabled) is False

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


def test_move_focus_down_from_last_timeline_row_wraps_to_settings() -> None:
    slots = ("layer_1", "layer_2", "layer_3", "layer_4")
    state = _timeline_open_state(slots)
    settings = RowDescriptor(RowKind.SETTINGS_HEADER)
    cursor = TimelineFocus(len(slots) - 1)

    result = move_focus(cursor, 1, state)

    assert isinstance(result, MainFocus)
    assert result.descriptor == settings


def test_move_focus_up_from_settings_wraps_to_last_timeline_row() -> None:
    slots = ("layer_1", "layer_2", "layer_3", "layer_4")
    state = _timeline_open_state(slots)
    cursor = MainFocus(RowDescriptor(RowKind.SETTINGS_HEADER))

    result = move_focus(cursor, -1, state)

    assert result == TimelineFocus(len(slots) - 1)


def test_resolve_cursor_maps_stale_main_descriptor() -> None:
    state = _minimal_view_state()
    ring = build_focus_ring(state)
    stale = MainFocus(RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY))

    resolved = resolve_cursor(stale, ring, state)

    assert isinstance(resolved, MainFocus)
    assert resolved.descriptor == RowDescriptor(RowKind.SETTINGS_HEADER)
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
    state = _minimal_view_state()
    ring = build_focus_ring(state)
    start = ring[3]
    assert move_focus(start, 1, state) == ring[4]
    assert move_focus(start, -1, state) == ring[2]
    assert move_focus(start, len(ring), state) == start


def test_bug2_up_from_transport_reaches_settings_when_timeline_open() -> None:
    slots = ("layer_1", "layer_2", "layer_3", "layer_4")
    controls = _make_controls(slots, timeline_enabled=True)
    controls.session.timeline.panel_open = True
    view = controls.build_view_state(paused=False)
    transport_row = view.layout.find_by_kind(RowKind.TRANSPORT)
    settings_row = view.layout.find_by_kind(RowKind.SETTINGS_HEADER)
    controls.focus_descriptor = _desc(view, transport_row)

    controls.handle_keydown(_keydown(pygame.K_UP))
    assert not isinstance(controls.focus_cursor, TimelineFocus)

    controls.handle_keydown(_keydown(pygame.K_UP))
    assert controls.focus_descriptor == _desc(view, settings_row)

    controls.handle_keydown(_keydown(pygame.K_UP))
    assert isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.focus_cursor.row == len(slots) - 1
