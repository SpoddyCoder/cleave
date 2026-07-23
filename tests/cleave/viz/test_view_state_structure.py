"""Tests for TuningViewStateBuilder structure signature and cache."""

from __future__ import annotations

from pathlib import Path

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
    presets_header = RowDescriptor(RowKind.TIMELINE_PRESETS_HEADER)
    preset_character = RowDescriptor(RowKind.TIMELINE_PRESET_CHARACTER)
    preset_crescendo = RowDescriptor(RowKind.TIMELINE_PRESET_CRESCENDO)
    preset_density = RowDescriptor(RowKind.TIMELINE_PRESET_DENSITY)
    presets_apply = RowDescriptor(RowKind.TIMELINE_PRESETS)
    reset = RowDescriptor(RowKind.TIMELINE_RESET)
    beat_bar_header = RowDescriptor(RowKind.TIMELINE_BEAT_BAR_GRID_HEADER)
    bar_phase = RowDescriptor(RowKind.TIMELINE_BAR_PHASE)
    bar_grid = RowDescriptor(RowKind.TIMELINE_BAR_GRID)
    placement_snap = RowDescriptor(RowKind.TIMELINE_PLACEMENT_SNAP)
    snap_grid = RowDescriptor(RowKind.TIMELINE_SNAP_TO_GRID)
    snap_markers = RowDescriptor(RowKind.TIMELINE_SNAP_TO_SONG_MARKERS)
    fades_header = RowDescriptor(RowKind.TIMELINE_FADES_HEADER)
    song_marker_fades = RowDescriptor(RowKind.TIMELINE_SONG_MARKER_FADES)
    song_marker_fade_in = RowDescriptor(RowKind.TIMELINE_SONG_MARKER_FADE_IN)
    song_marker_fade_out = RowDescriptor(RowKind.TIMELINE_SONG_MARKER_FADE_OUT)
    standard_cue_fades = RowDescriptor(RowKind.TIMELINE_STANDARD_CUE_FADES)
    standard_cue_fade_in = RowDescriptor(RowKind.TIMELINE_STANDARD_CUE_FADE_IN)
    standard_cue_fade_out = RowDescriptor(RowKind.TIMELINE_STANDARD_CUE_FADE_OUT)
    markers_header = RowDescriptor(RowKind.SONG_MARKERS_HEADER)
    assert presets_header not in view_closed.layout.rows
    assert presets_apply not in view_closed.layout.rows
    assert reset not in view_closed.layout.rows
    assert beat_bar_header not in view_closed.layout.rows
    assert bar_phase not in view_closed.layout.rows
    assert bar_grid not in view_closed.layout.rows
    assert placement_snap not in view_closed.layout.rows
    assert snap_grid not in view_closed.layout.rows
    assert snap_markers not in view_closed.layout.rows
    assert fades_header not in view_closed.layout.rows
    assert markers_header not in view_closed.layout.rows

    session.timeline.panel_open = True
    view_open = builder.build(paused=False)
    assert view_open.layout is not view_closed.layout
    assert presets_header in view_open.layout.rows
    assert preset_character not in view_open.layout.rows
    assert preset_crescendo not in view_open.layout.rows
    assert preset_density not in view_open.layout.rows
    assert presets_apply not in view_open.layout.rows
    assert reset in view_open.layout.rows
    assert beat_bar_header in view_open.layout.rows
    assert bar_phase not in view_open.layout.rows
    assert bar_grid not in view_open.layout.rows
    assert placement_snap not in view_open.layout.rows
    assert snap_grid not in view_open.layout.rows
    assert snap_markers not in view_open.layout.rows
    assert fades_header in view_open.layout.rows
    assert song_marker_fades not in view_open.layout.rows
    assert markers_header in view_open.layout.rows
    markers_idx = view_open.layout.rows.index(markers_header)
    beat_bar_idx = view_open.layout.rows.index(beat_bar_header)
    fades_idx = view_open.layout.rows.index(fades_header)
    presets_header_idx = view_open.layout.rows.index(presets_header)
    reset_idx = view_open.layout.rows.index(reset)
    assert beat_bar_idx == markers_idx + 1
    assert fades_idx == beat_bar_idx + 1
    assert presets_header_idx == fades_idx + 1
    assert reset_idx == presets_header_idx + 1

    session.song_markers.expanded = True
    view_markers_expanded = builder.build(paused=False)
    assert snap_markers in view_markers_expanded.layout.rows
    markers_idx = view_markers_expanded.layout.rows.index(markers_header)
    snap_markers_idx = view_markers_expanded.layout.rows.index(snap_markers)
    beat_bar_idx = view_markers_expanded.layout.rows.index(beat_bar_header)
    assert snap_markers_idx == markers_idx + 1
    assert beat_bar_idx == snap_markers_idx + 1

    session.timeline.beat_bar_grid_expanded = True
    view_beat_expanded = builder.build(paused=False)
    assert view_beat_expanded.layout is not view_open.layout
    beat_bar_idx = view_beat_expanded.layout.rows.index(beat_bar_header)
    bar_phase_idx = view_beat_expanded.layout.rows.index(bar_phase)
    bar_grid_idx = view_beat_expanded.layout.rows.index(bar_grid)
    placement_snap_idx = view_beat_expanded.layout.rows.index(placement_snap)
    snap_grid_idx = view_beat_expanded.layout.rows.index(snap_grid)
    fades_idx = view_beat_expanded.layout.rows.index(fades_header)
    assert placement_snap_idx == beat_bar_idx + 1
    assert bar_grid_idx == placement_snap_idx + 1
    assert bar_phase_idx == bar_grid_idx + 1
    assert snap_grid_idx == bar_phase_idx + 1
    assert fades_idx == snap_grid_idx + 1
    assert song_marker_fades not in view_beat_expanded.layout.rows
    assert standard_cue_fades not in view_beat_expanded.layout.rows
    assert view_beat_expanded.layout.rows.index(presets_header) == fades_idx + 1
    assert view_beat_expanded.layout.rows.index(reset) == fades_idx + 2

    session.timeline.fades_expanded = True
    view_fades_expanded = builder.build(paused=False)
    assert view_fades_expanded.layout is not view_beat_expanded.layout
    fades_idx = view_fades_expanded.layout.rows.index(fades_header)
    assert view_fades_expanded.layout.rows.index(song_marker_fades) == fades_idx + 1
    assert view_fades_expanded.layout.rows.index(standard_cue_fades) == fades_idx + 2
    assert song_marker_fade_in not in view_fades_expanded.layout.rows
    assert standard_cue_fade_in not in view_fades_expanded.layout.rows
    assert view_fades_expanded.layout.rows.index(presets_header) == fades_idx + 3

    session.timeline.song_marker_fades.enabled = True
    session.timeline.standard_cue_fades.enabled = True
    view_fades_enabled = builder.build(paused=False)
    assert view_fades_enabled.layout is not view_fades_expanded.layout
    fades_idx = view_fades_enabled.layout.rows.index(fades_header)
    assert view_fades_enabled.layout.rows.index(song_marker_fades) == fades_idx + 1
    assert view_fades_enabled.layout.rows.index(song_marker_fade_in) == fades_idx + 2
    assert view_fades_enabled.layout.rows.index(song_marker_fade_out) == fades_idx + 3
    assert view_fades_enabled.layout.rows.index(standard_cue_fades) == fades_idx + 4
    assert view_fades_enabled.layout.rows.index(standard_cue_fade_in) == fades_idx + 5
    assert view_fades_enabled.layout.rows.index(standard_cue_fade_out) == fades_idx + 6
    assert view_fades_enabled.layout.rows.index(presets_header) == fades_idx + 7

    session.timeline.timeline_presets_expanded = True
    view_presets_expanded = builder.build(paused=False)
    assert view_presets_expanded.layout is not view_fades_enabled.layout
    presets_header_idx = view_presets_expanded.layout.rows.index(presets_header)
    assert view_presets_expanded.layout.rows.index(preset_character) == (
        presets_header_idx + 1
    )
    assert view_presets_expanded.layout.rows.index(preset_crescendo) == (
        presets_header_idx + 2
    )
    assert view_presets_expanded.layout.rows.index(preset_density) == (
        presets_header_idx + 3
    )
    assert view_presets_expanded.layout.rows.index(presets_apply) == (
        presets_header_idx + 4
    )
    assert view_presets_expanded.layout.rows.index(reset) == presets_header_idx + 5

    session.timeline.timeline_presets_expanded = False
    view_presets_collapsed = builder.build(paused=False)
    assert view_presets_collapsed.layout is not view_presets_expanded.layout
    assert preset_character not in view_presets_collapsed.layout.rows
    assert preset_crescendo not in view_presets_collapsed.layout.rows
    assert preset_density not in view_presets_collapsed.layout.rows
    assert presets_apply not in view_presets_collapsed.layout.rows
    assert presets_header in view_presets_collapsed.layout.rows

    session.timeline.panel_open = False
    view_closed_again = builder.build(paused=False)
    assert view_closed_again.layout is not view_open.layout
    assert presets_header not in view_closed_again.layout.rows
    assert presets_apply not in view_closed_again.layout.rows
    assert reset not in view_closed_again.layout.rows
    assert fades_header not in view_closed_again.layout.rows
    assert bar_phase not in view_closed_again.layout.rows
    assert bar_grid not in view_closed_again.layout.rows
    assert placement_snap not in view_closed_again.layout.rows
    assert snap_grid not in view_closed_again.layout.rows
    assert snap_markers not in view_closed_again.layout.rows
    assert markers_header not in view_closed_again.layout.rows


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


def test_structure_signature_invalidates_on_animation_type() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.render_overlay.animation.type = "fade"
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.render_overlay.animation.type = "slide"
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_builder_rebuilds_layout_when_animation_type_changes() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.render_overlay.expanded = True
    session.render_overlay.animation_expanded = True
    session.render_overlay.animation.type = "fade"
    view_fade = controls.build_view_state(paused=False)
    kinds_fade = [row.kind for row in view_fade.layout.rows]
    assert RowKind.RENDER_OVERLAY_ANIMATION_SLIDE_DIRECTION not in kinds_fade

    session.render_overlay.animation.type = "slide"
    view_slide = controls.build_view_state(paused=False)
    kinds_slide = [row.kind for row in view_slide.layout.rows]
    assert RowKind.RENDER_OVERLAY_ANIMATION_SLIDE_DIRECTION in kinds_slide


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


def test_structure_signature_invalidates_on_preset_switching_timeline_mode() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.layers["layer_1"].preset_switching = "projectm"
    sig_projectm = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.layers["layer_1"].preset_switching = "timeline"
    sig_timeline = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_projectm != sig_timeline
    session.layers["layer_1"].preset_switching = "none"
    sig_none = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_timeline != sig_none


def test_timeline_preset_switching_hides_projectm_only_rows() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.layers["layer_1"].expanded = True
    session.layers["layer_1"].preset_switching = "timeline"
    builder = controls._view_state
    view = builder.build(paused=False)
    slot = "layer_1"
    assert RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_ROTATION_SET, slot=slot) in (
        view.layout.rows
    )
    assert RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_SHUFFLE, slot=slot) in (
        view.layout.rows
    )
    assert RowDescriptor(RowKind.TRACK_PRESET_START_CLEAN, slot=slot) in view.layout.rows
    assert RowDescriptor(RowKind.TRACK_PRESET_DURATION, slot=slot) not in view.layout.rows
    assert RowDescriptor(RowKind.TRACK_EASTER_EGG, slot=slot) not in view.layout.rows
    assert RowDescriptor(RowKind.TRACK_SOFT_CUT_DURATION, slot=slot) not in (
        view.layout.rows
    )
    assert RowDescriptor(RowKind.TRACK_HARD_CUT_ENABLED, slot=slot) not in (
        view.layout.rows
    )


def test_timeline_mode_row_set_unchanged_when_timeline_enabled_toggles() -> None:
    """Dimming when timeline is disabled does not add or remove preset-switching rows."""
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.layers["layer_1"].expanded = True
    session.layers["layer_1"].preset_switching = "timeline"
    session.timeline.enabled = True
    builder = controls._view_state
    kinds_on = [desc.kind for desc in builder.build(paused=False).layout.rows]
    session.timeline.enabled = False
    kinds_off = [desc.kind for desc in builder.build(paused=False).layout.rows]
    assert kinds_on == kinds_off


def test_builder_updates_shuffle_display_when_shuffle_changes() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.layers["layer_1"].preset_switching = "projectm"
    session.layers["layer_1"].expanded = True
    builder = controls._view_state

    view_off = builder.build(paused=False)
    shuffle_row = RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_SHUFFLE, slot="layer_1")
    seed_row = RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_SEED, slot="layer_1")
    assert shuffle_row in view_off.layout.rows
    assert seed_row not in view_off.layout.rows
    assert view_off.tracks["layer_1"].preset_switching_shuffle is False

    session.layers["layer_1"].preset_switching_shuffle = True
    view_on = builder.build(paused=False)
    assert shuffle_row in view_on.layout.rows
    assert seed_row in view_on.layout.rows
    assert view_on.tracks["layer_1"].preset_switching_shuffle is True
    shuffle_idx = view_on.layout.rows.index(shuffle_row)
    seed_idx = view_on.layout.rows.index(seed_row)
    assert seed_idx == shuffle_idx + 1


def test_minimal_view_state_still_builds_layout() -> None:
    state = _minimal_view_state()
    assert state.layout is not None
    assert state.layout_frame is not None
    assert len(state.layout.rows) > 0


def test_structure_signature_invalidates_on_song_marker_count() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.song_markers.times = [10.0, 20.0]
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_song_markers_expanded() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.song_markers.expanded = False
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.song_markers.expanded = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_beat_bar_grid_expanded() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.timeline.beat_bar_grid_expanded = False
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.timeline.beat_bar_grid_expanded = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_timeline_fades_expanded() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.timeline.fades_expanded = False
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.timeline.fades_expanded = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_timeline_presets_expanded() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.timeline.timeline_presets_expanded = False
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.timeline.timeline_presets_expanded = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_song_marker_fades_enabled() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.timeline.song_marker_fades.enabled = False
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.timeline.song_marker_fades.enabled = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_standard_cue_fades_enabled() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.timeline.standard_cue_fades.enabled = False
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.timeline.standard_cue_fades.enabled = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_latency_compensation_expanded() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.settings.latency_compensation_expanded = False
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.settings.latency_compensation_expanded = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_row_layout_includes_song_marker_items_when_expanded() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.timeline.panel_open = True
    session.song_markers.times = [8.0, 32.5, 64.0]
    session.song_markers.expanded = True
    builder = controls._view_state

    view = builder.build(paused=False)
    header = RowDescriptor(RowKind.SONG_MARKERS_HEADER)
    assert header in view.layout.rows
    items = [
        desc
        for desc in view.layout.rows
        if desc.kind == RowKind.SONG_MARKER_ITEM
    ]
    assert len(items) == 3
    assert [desc.marker_index for desc in items] == [0, 1, 2]
    header_idx = view.layout.rows.index(header)
    assert view.layout.rows.index(items[0]) == header_idx + 1
    snap_row = RowDescriptor(RowKind.TIMELINE_SNAP_TO_SONG_MARKERS)
    assert snap_row in view.layout.rows
    assert view.layout.rows.index(snap_row) == header_idx + len(items) + 1

    session.song_markers.expanded = False
    view_collapsed = builder.build(paused=False)
    assert header in view_collapsed.layout.rows
    assert not any(
        desc.kind == RowKind.SONG_MARKER_ITEM for desc in view_collapsed.layout.rows
    )
    assert snap_row not in view_collapsed.layout.rows


def test_builder_appends_curation_markers_without_structure_change() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    index = controls._view_state._curation_index
    layer = session.layers["layer_1"]
    user_path = Path("/tmp/projects/my-track/user.milk")
    user_path.parent.mkdir(parents=True, exist_ok=True)
    user_path.write_text("milk", encoding="utf-8")
    layer.user_presets = [str(user_path)]

    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    view_before = controls.build_view_state(paused=False)
    block_before = view_before.tracks["layer_1"]
    assert block_before.preset_label == "preset-0.milk (1/3)"
    assert block_before.user_preset_labels == ["user.milk"]

    current_name = layer.playlist.current.name
    assert current_name is not None
    index.mark_favourite(current_name)
    index.mark_favourite(user_path.name)
    index.mark_blacklisted(user_path.name)

    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before == sig_after

    view_after = controls.build_view_state(paused=False)
    block_after = view_after.tracks["layer_1"]
    assert block_after.preset_label == "preset-0.milk (1/3) [F]"
    # User-preset rows never append U; F/B only in single-bracket form.
    assert block_after.user_preset_labels == ["user.milk [FB]"]


def test_builder_appends_user_defined_marker_on_track_preset() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    session = controls.session
    config_save = controls._config_save
    index = controls._view_state._curation_index
    layer_1 = session.layers["layer_1"]
    layer_2 = session.layers["layer_2"]
    current = layer_1.playlist.current
    assert current is not None
    current_name = current.name
    assert current_name is not None

    # Basename listed on another layer still marks TRACK_PRESET with U.
    other_path = Path("/tmp/projects/my-track") / current_name
    other_path.parent.mkdir(parents=True, exist_ok=True)
    other_path.write_text("milk", encoding="utf-8")
    layer_2.user_presets = [str(other_path)]

    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    view_u = controls.build_view_state(paused=False)
    assert view_u.tracks["layer_1"].preset_label == f"{current_name} (1/3) [U]"
    assert view_u.tracks["layer_2"].user_preset_labels == [current_name]

    index.mark_favourite(current_name)
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before == sig_after

    view_fu = controls.build_view_state(paused=False)
    assert view_fu.tracks["layer_1"].preset_label == f"{current_name} (1/3) [FU]"
    assert view_fu.tracks["layer_2"].user_preset_labels == [f"{current_name} [F]"]
