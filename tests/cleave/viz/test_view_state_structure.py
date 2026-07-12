"""Tests for TuningViewStateBuilder structure signature and cache."""

from __future__ import annotations

from cleave.viz.row_semantics import RowDescriptor, RowKind
from cleave.viz.tuning_view_state import view_state_structure_signature
from tests.cleave.viz.test_controls import _make_controls
from tests.cleave.viz.test_overlay import _minimal_view_state


def test_structure_signature_stable_for_fps_and_focus() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    sig_a = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    sig_b = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_a == sig_b

    view_a = controls.build_view_state(paused=False, fps=30.0)
    view_b = controls.build_view_state(paused=False, fps=60.0)
    assert view_state_structure_signature(
        session, config_save, notification_active=False
    ) == sig_a
    assert view_a.layout is view_b.layout


def test_structure_signature_invalidates_on_expand() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.layers["layer_1"].expanded = False
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_layer_z_order() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    session = controls.session
    config_save = controls._config_save
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.layer_z_order = ["layer_1"]
    del session.layers["layer_2"]
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_preset_navigation() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    layer = session.layers["layer_1"]
    config_save = controls._config_save
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    layer.playlist.next()
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_notification() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    sig_inactive = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    sig_active = view_state_structure_signature(
        session, config_save, notification_active=True
    )
    assert sig_inactive != sig_active


def test_reused_structure_produces_identical_row_list_and_focus() -> None:
    controls = _make_controls(("layer_1",))
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_BLEND, slot="layer_1")
    view_a = controls.build_view_state(paused=False, fps=30.0)
    view_b = controls.build_view_state(paused=True, fps=60.0, position_sec=42.0)
    assert view_a.layout is view_b.layout
    assert view_a.layout.rows == view_b.layout.rows
    assert view_a.focus_index == view_b.focus_index


def test_builder_skips_layout_rebuild_when_structure_unchanged() -> None:
    controls = _make_controls(("layer_1",))
    builder = controls._view_state
    view_a = builder.build(paused=False)
    layout_a = view_a.layout
    view_b = builder.build(paused=True, position_sec=10.0, fps=55.0)
    assert view_b.layout is layout_a


def test_builder_patches_highlight_rolloff_curve_without_structure_rebuild() -> None:
    controls = _make_controls(("layer_1",))
    builder = controls._view_state
    session = controls.session
    session.render_post_fx.highlight_rolloff.curve = "rolloff"

    view_a = builder.build(paused=False)
    layout_a = view_a.layout
    assert view_a.render_post_fx.highlight_rolloff.curve == "rolloff"

    session.render_post_fx.highlight_rolloff.curve = "smoothstep"
    view_b = builder.build(paused=False)
    assert view_b.layout is layout_a
    assert view_b.render_post_fx.highlight_rolloff.curve == "smoothstep"


def test_structure_signature_invalidates_on_timeline_panel_open() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.timeline.panel_open = False
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.timeline.panel_open = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_builder_rebuilds_layout_when_timeline_panel_open_changes() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.timeline.panel_open = False
    builder = controls._view_state

    view_closed = builder.build(paused=False)
    presets = RowDescriptor(RowKind.TIMELINE_PRESETS)
    bar_phase = RowDescriptor(RowKind.TIMELINE_BAR_PHASE)
    bar_grid = RowDescriptor(RowKind.TIMELINE_BAR_GRID)
    snap_beats = RowDescriptor(RowKind.TIMELINE_SNAP_TO_BEATS)
    snap_bars = RowDescriptor(RowKind.TIMELINE_SNAP_TO_BARS)
    assert presets not in view_closed.layout.rows
    assert bar_phase not in view_closed.layout.rows
    assert bar_grid not in view_closed.layout.rows
    assert snap_beats not in view_closed.layout.rows
    assert snap_bars not in view_closed.layout.rows

    session.timeline.panel_open = True
    view_open = builder.build(paused=False)
    assert view_open.layout is not view_closed.layout
    assert presets in view_open.layout.rows
    assert bar_phase in view_open.layout.rows
    assert bar_grid in view_open.layout.rows
    assert snap_beats in view_open.layout.rows
    assert snap_bars in view_open.layout.rows
    presets_idx = view_open.layout.rows.index(presets)
    bar_phase_idx = view_open.layout.rows.index(bar_phase)
    bar_grid_idx = view_open.layout.rows.index(bar_grid)
    snap_beats_idx = view_open.layout.rows.index(snap_beats)
    snap_bars_idx = view_open.layout.rows.index(snap_bars)
    assert bar_phase_idx == presets_idx + 1
    assert bar_grid_idx == bar_phase_idx + 1
    assert snap_beats_idx == bar_grid_idx + 1
    assert snap_bars_idx == snap_beats_idx + 1

    session.timeline.panel_open = False
    view_closed_again = builder.build(paused=False)
    assert view_closed_again.layout is not view_open.layout
    assert presets not in view_closed_again.layout.rows
    assert bar_phase not in view_closed_again.layout.rows
    assert bar_grid not in view_closed_again.layout.rows
    assert snap_beats not in view_closed_again.layout.rows
    assert snap_bars not in view_closed_again.layout.rows


def test_structure_signature_invalidates_on_highlight_rolloff_mode() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.render_post_fx.highlight_rolloff.mode = "composite"
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.render_post_fx.highlight_rolloff.mode = "off"
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_chroma_boost_mode() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.render_post_fx.chroma_boost.mode = "composite"
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.render_post_fx.chroma_boost.mode = "off"
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_builder_rebuilds_layout_when_highlight_rolloff_mode_changes() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.render_post_fx.expanded = True
    session.render_post_fx.highlight_rolloff_expanded = True
    session.render_post_fx.highlight_rolloff.mode = "composite"
    builder = controls._view_state

    view_on = builder.build(paused=False)
    threshold = RowDescriptor(RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD)
    assert threshold in view_on.layout.rows

    session.render_post_fx.highlight_rolloff.mode = "off"
    view_off = builder.build(paused=False)
    assert view_off.layout is not view_on.layout
    assert threshold not in view_off.layout.rows


def test_structure_signature_invalidates_on_preset_switching_shuffle() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.layers["layer_1"].preset_switching = "projectm"
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.layers["layer_1"].preset_switching_shuffle = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_builder_updates_shuffle_display_when_shuffle_changes() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.layers["layer_1"].preset_switching = "projectm"
    session.layers["layer_1"].preset_switching_expanded = True
    session.layers["layer_1"].expanded = True
    builder = controls._view_state

    view_off = builder.build(paused=False)
    shuffle_row = RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_SHUFFLE, slot="layer_1")
    assert shuffle_row in view_off.layout.rows
    assert view_off.tracks["layer_1"].preset_switching_shuffle is False

    session.layers["layer_1"].preset_switching_shuffle = True
    view_on = builder.build(paused=False)
    assert shuffle_row in view_on.layout.rows
    assert view_on.tracks["layer_1"].preset_switching_shuffle is True


def test_minimal_view_state_still_builds_layout() -> None:
    state = _minimal_view_state()
    assert state.layout is not None
    assert state.layout_frame is not None
    assert len(state.layout.rows) > 0
