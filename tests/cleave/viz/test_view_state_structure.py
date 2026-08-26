"""Tests for TuningViewStateBuilder structure signature and cache."""

from __future__ import annotations

from pathlib import Path

from cleave.viz.row_kinds import RowDescriptor, RowKind
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
    preset_density = RowDescriptor(RowKind.TIMELINE_PRESET_DENSITY)
    preset_cue_snap = RowDescriptor(RowKind.TIMELINE_PRESET_CUE_SNAP)
    preset_song_marker_snap = RowDescriptor(RowKind.TIMELINE_PRESET_SONG_MARKER_SNAP)
    preset_timeline_cuts = RowDescriptor(RowKind.TIMELINE_PRESET_TIMELINE_CUTS)
    preset_repopulate = RowDescriptor(RowKind.TIMELINE_PRESET_REPOPULATE)
    preset_conductor = RowDescriptor(RowKind.TIMELINE_PRESET_CONDUCTOR)
    preset_mode = RowDescriptor(RowKind.TIMELINE_PRESET_MODE)
    presets_apply = RowDescriptor(RowKind.TIMELINE_PRESETS)
    reset = RowDescriptor(RowKind.TIMELINE_RESET)
    beat_bar_header = RowDescriptor(RowKind.TIMELINE_BEAT_BAR_GRID_HEADER)
    bar_phase = RowDescriptor(RowKind.TIMELINE_BAR_PHASE)
    bar_grid = RowDescriptor(RowKind.TIMELINE_BAR_GRID)
    placement_snap = RowDescriptor(RowKind.TIMELINE_PLACEMENT_SNAP)
    snap_cues_header = RowDescriptor(RowKind.TIMELINE_SNAP_CUES_HEADER)
    snap_beats = RowDescriptor(RowKind.TIMELINE_SNAP_TO_BEATS)
    snap_bars = RowDescriptor(RowKind.TIMELINE_SNAP_TO_BARS)
    snap_markers = RowDescriptor(RowKind.TIMELINE_SNAP_TO_SONG_MARKERS)
    cuts_header = RowDescriptor(RowKind.TIMELINE_CUTS_HEADER)
    hard_cut_fades = RowDescriptor(RowKind.TIMELINE_HARD_CUTS)
    hard_cut_fade_in = RowDescriptor(RowKind.TIMELINE_HARD_CUT_FADE_IN)
    hard_cut_fade_out = RowDescriptor(RowKind.TIMELINE_HARD_CUT_FADE_OUT)
    hard_cut_crossfade = RowDescriptor(RowKind.TIMELINE_HARD_CUT_CROSSFADE)
    soft_cut_fades = RowDescriptor(RowKind.TIMELINE_SOFT_CUTS)
    soft_cut_fade_in = RowDescriptor(RowKind.TIMELINE_SOFT_CUT_FADE_IN)
    soft_cut_fade_out = RowDescriptor(RowKind.TIMELINE_SOFT_CUT_FADE_OUT)
    soft_cut_crossfade = RowDescriptor(RowKind.TIMELINE_SOFT_CUT_CROSSFADE)
    apply_soft_cuts = RowDescriptor(RowKind.TIMELINE_APPLY_SOFT_CUTS)
    apply_hard_cuts = RowDescriptor(RowKind.TIMELINE_APPLY_HARD_CUTS)
    limiter_header = RowDescriptor(RowKind.TIMELINE_VISUAL_LIMITER_HEADER)
    limiter_enabled = RowDescriptor(RowKind.TIMELINE_VISUAL_LIMITER_ENABLED)
    limiter_threshold = RowDescriptor(RowKind.TIMELINE_VISUAL_LIMITER_THRESHOLD)
    limiter_ratio = RowDescriptor(RowKind.TIMELINE_VISUAL_LIMITER_RATIO)
    limiter_release = RowDescriptor(RowKind.TIMELINE_VISUAL_LIMITER_RELEASE)
    markers_header = RowDescriptor(RowKind.SONG_MARKERS_HEADER)
    assert presets_header not in view_closed.layout.rows
    assert presets_apply not in view_closed.layout.rows
    assert reset not in view_closed.layout.rows
    assert beat_bar_header not in view_closed.layout.rows
    assert bar_phase not in view_closed.layout.rows
    assert bar_grid not in view_closed.layout.rows
    assert placement_snap not in view_closed.layout.rows
    assert snap_cues_header not in view_closed.layout.rows
    assert snap_beats not in view_closed.layout.rows
    assert snap_bars not in view_closed.layout.rows
    assert snap_markers not in view_closed.layout.rows
    assert cuts_header not in view_closed.layout.rows
    assert limiter_header not in view_closed.layout.rows
    assert markers_header not in view_closed.layout.rows

    session.timeline.panel_open = True
    view_open = builder.build(paused=False)
    assert view_open.layout is not view_closed.layout
    assert presets_header in view_open.layout.rows
    assert preset_character not in view_open.layout.rows
    assert preset_density not in view_open.layout.rows
    assert preset_cue_snap not in view_open.layout.rows
    assert preset_song_marker_snap not in view_open.layout.rows
    assert preset_timeline_cuts not in view_open.layout.rows
    assert preset_repopulate not in view_open.layout.rows
    assert preset_conductor not in view_open.layout.rows
    assert preset_mode not in view_open.layout.rows
    assert presets_apply not in view_open.layout.rows
    assert reset in view_open.layout.rows
    assert beat_bar_header in view_open.layout.rows
    assert bar_phase not in view_open.layout.rows
    assert bar_grid not in view_open.layout.rows
    assert placement_snap not in view_open.layout.rows
    assert snap_cues_header in view_open.layout.rows
    assert snap_beats not in view_open.layout.rows
    assert snap_bars not in view_open.layout.rows
    assert snap_markers not in view_open.layout.rows
    assert cuts_header in view_open.layout.rows
    assert hard_cut_fades not in view_open.layout.rows
    assert limiter_header in view_open.layout.rows
    assert limiter_enabled not in view_open.layout.rows
    assert limiter_threshold not in view_open.layout.rows
    assert limiter_ratio not in view_open.layout.rows
    assert limiter_release not in view_open.layout.rows
    assert markers_header in view_open.layout.rows
    markers_idx = view_open.layout.rows.index(markers_header)
    beat_bar_idx = view_open.layout.rows.index(beat_bar_header)
    snap_cues_idx = view_open.layout.rows.index(snap_cues_header)
    cuts_idx = view_open.layout.rows.index(cuts_header)
    presets_header_idx = view_open.layout.rows.index(presets_header)
    limiter_header_idx = view_open.layout.rows.index(limiter_header)
    reset_idx = view_open.layout.rows.index(reset)
    assert beat_bar_idx == markers_idx + 1
    assert snap_cues_idx == beat_bar_idx + 1
    assert cuts_idx == snap_cues_idx + 1
    assert presets_header_idx == cuts_idx + 1
    assert limiter_header_idx == presets_header_idx + 1
    assert reset_idx == limiter_header_idx + 1

    session.song_markers.expanded = True
    view_markers_expanded = builder.build(paused=False)
    assert snap_markers not in view_markers_expanded.layout.rows
    markers_idx = view_markers_expanded.layout.rows.index(markers_header)
    beat_bar_idx = view_markers_expanded.layout.rows.index(beat_bar_header)
    assert beat_bar_idx == markers_idx + 1

    session.timeline.beat_bar_grid_expanded = True
    view_beat_expanded = builder.build(paused=False)
    assert view_beat_expanded.layout is not view_open.layout
    beat_bar_idx = view_beat_expanded.layout.rows.index(beat_bar_header)
    bar_phase_idx = view_beat_expanded.layout.rows.index(bar_phase)
    bar_grid_idx = view_beat_expanded.layout.rows.index(bar_grid)
    placement_snap_idx = view_beat_expanded.layout.rows.index(placement_snap)
    snap_cues_idx = view_beat_expanded.layout.rows.index(snap_cues_header)
    cuts_idx = view_beat_expanded.layout.rows.index(cuts_header)
    assert placement_snap_idx == beat_bar_idx + 1
    assert bar_grid_idx == placement_snap_idx + 1
    assert bar_phase_idx == bar_grid_idx + 1
    assert snap_cues_idx == bar_phase_idx + 1
    assert cuts_idx == snap_cues_idx + 1
    assert snap_beats not in view_beat_expanded.layout.rows
    assert snap_bars not in view_beat_expanded.layout.rows
    assert snap_markers not in view_beat_expanded.layout.rows
    assert hard_cut_fades not in view_beat_expanded.layout.rows
    assert soft_cut_fades not in view_beat_expanded.layout.rows
    assert view_beat_expanded.layout.rows.index(presets_header) == cuts_idx + 1
    assert view_beat_expanded.layout.rows.index(limiter_header) == cuts_idx + 2
    assert view_beat_expanded.layout.rows.index(reset) == cuts_idx + 3

    session.timeline.snap_cues_expanded = True
    view_snap_expanded = builder.build(paused=False)
    assert view_snap_expanded.layout is not view_beat_expanded.layout
    snap_cues_idx = view_snap_expanded.layout.rows.index(snap_cues_header)
    snap_beats_idx = view_snap_expanded.layout.rows.index(snap_beats)
    snap_bars_idx = view_snap_expanded.layout.rows.index(snap_bars)
    snap_markers_idx = view_snap_expanded.layout.rows.index(snap_markers)
    cuts_idx = view_snap_expanded.layout.rows.index(cuts_header)
    assert snap_beats_idx == snap_cues_idx + 1
    assert snap_bars_idx == snap_beats_idx + 1
    assert snap_markers_idx == snap_bars_idx + 1
    assert cuts_idx == snap_markers_idx + 1

    session.timeline.cuts_expanded = True
    view_cuts_expanded = builder.build(paused=False)
    assert view_cuts_expanded.layout is not view_snap_expanded.layout
    cuts_idx = view_cuts_expanded.layout.rows.index(cuts_header)
    assert view_cuts_expanded.layout.rows.index(hard_cut_fades) == cuts_idx + 1
    assert view_cuts_expanded.layout.rows.index(soft_cut_fades) == cuts_idx + 2
    assert view_cuts_expanded.layout.rows.index(apply_soft_cuts) == cuts_idx + 3
    assert view_cuts_expanded.layout.rows.index(apply_hard_cuts) == cuts_idx + 4
    assert hard_cut_fade_in not in view_cuts_expanded.layout.rows
    assert soft_cut_fade_in not in view_cuts_expanded.layout.rows
    assert view_cuts_expanded.layout.rows.index(presets_header) == cuts_idx + 5

    session.timeline.hard_cut_fades.enabled = True
    session.timeline.soft_cut_fades.enabled = True
    view_cuts_enabled = builder.build(paused=False)
    assert view_cuts_enabled.layout is not view_cuts_expanded.layout
    cuts_idx = view_cuts_enabled.layout.rows.index(cuts_header)
    assert view_cuts_enabled.layout.rows.index(hard_cut_fades) == cuts_idx + 1
    assert view_cuts_enabled.layout.rows.index(hard_cut_fade_in) == cuts_idx + 2
    assert view_cuts_enabled.layout.rows.index(hard_cut_fade_out) == cuts_idx + 3
    assert view_cuts_enabled.layout.rows.index(hard_cut_crossfade) == cuts_idx + 4
    assert view_cuts_enabled.layout.rows.index(soft_cut_fades) == cuts_idx + 5
    assert view_cuts_enabled.layout.rows.index(soft_cut_fade_in) == cuts_idx + 6
    assert view_cuts_enabled.layout.rows.index(soft_cut_fade_out) == cuts_idx + 7
    assert view_cuts_enabled.layout.rows.index(soft_cut_crossfade) == cuts_idx + 8
    assert view_cuts_enabled.layout.rows.index(apply_soft_cuts) == cuts_idx + 9
    assert view_cuts_enabled.layout.rows.index(apply_hard_cuts) == cuts_idx + 10
    assert view_cuts_enabled.layout.rows.index(presets_header) == cuts_idx + 11

    session.timeline.timeline_presets_expanded = True
    view_presets_expanded = builder.build(paused=False)
    assert view_presets_expanded.layout is not view_cuts_enabled.layout
    presets_header_idx = view_presets_expanded.layout.rows.index(presets_header)
    assert view_presets_expanded.layout.rows.index(preset_character) == (
        presets_header_idx + 1
    )
    assert view_presets_expanded.layout.rows.index(preset_density) == (
        presets_header_idx + 2
    )
    assert view_presets_expanded.layout.rows.index(preset_cue_snap) == (
        presets_header_idx + 3
    )
    assert view_presets_expanded.layout.rows.index(preset_song_marker_snap) == (
        presets_header_idx + 4
    )
    assert view_presets_expanded.layout.rows.index(preset_timeline_cuts) == (
        presets_header_idx + 5
    )
    assert view_presets_expanded.layout.rows.index(preset_repopulate) == (
        presets_header_idx + 6
    )
    assert view_presets_expanded.layout.rows.index(preset_conductor) == (
        presets_header_idx + 7
    )
    assert view_presets_expanded.layout.rows.index(preset_mode) == (
        presets_header_idx + 8
    )
    assert view_presets_expanded.layout.rows.index(presets_apply) == (
        presets_header_idx + 9
    )
    assert view_presets_expanded.layout.rows.index(limiter_header) == (
        presets_header_idx + 10
    )
    assert view_presets_expanded.layout.rows.index(reset) == presets_header_idx + 11

    session.timeline.visual_limiter_expanded = True
    view_limiter_expanded = builder.build(paused=False)
    assert view_limiter_expanded.layout is not view_presets_expanded.layout
    limiter_header_idx = view_limiter_expanded.layout.rows.index(limiter_header)
    assert view_limiter_expanded.layout.rows.index(limiter_enabled) == (
        limiter_header_idx + 1
    )
    assert view_limiter_expanded.layout.rows.index(limiter_threshold) == (
        limiter_header_idx + 2
    )
    assert view_limiter_expanded.layout.rows.index(limiter_ratio) == (
        limiter_header_idx + 3
    )
    assert view_limiter_expanded.layout.rows.index(limiter_release) == (
        limiter_header_idx + 4
    )
    assert view_limiter_expanded.layout.rows.index(reset) == limiter_header_idx + 5

    session.timeline.limiter.enabled = False
    view_limiter_disabled = builder.build(paused=False)
    assert view_limiter_disabled.layout is not view_limiter_expanded.layout
    limiter_header_idx = view_limiter_disabled.layout.rows.index(limiter_header)
    assert view_limiter_disabled.layout.rows.index(limiter_enabled) == (
        limiter_header_idx + 1
    )
    assert limiter_threshold not in view_limiter_disabled.layout.rows
    assert limiter_ratio not in view_limiter_disabled.layout.rows
    assert limiter_release not in view_limiter_disabled.layout.rows
    assert view_limiter_disabled.layout.rows.index(reset) == limiter_header_idx + 2

    session.timeline.timeline_presets_expanded = False
    view_presets_collapsed = builder.build(paused=False)
    assert view_presets_collapsed.layout is not view_presets_expanded.layout
    assert preset_character not in view_presets_collapsed.layout.rows
    assert preset_density not in view_presets_collapsed.layout.rows
    assert preset_cue_snap not in view_presets_collapsed.layout.rows
    assert preset_song_marker_snap not in view_presets_collapsed.layout.rows
    assert preset_timeline_cuts not in view_presets_collapsed.layout.rows
    assert preset_repopulate not in view_presets_collapsed.layout.rows
    assert preset_conductor not in view_presets_collapsed.layout.rows
    assert preset_mode not in view_presets_collapsed.layout.rows
    assert presets_apply not in view_presets_collapsed.layout.rows
    assert presets_header in view_presets_collapsed.layout.rows

    session.timeline.panel_open = False
    view_closed_again = builder.build(paused=False)
    assert view_closed_again.layout is not view_open.layout
    assert presets_header not in view_closed_again.layout.rows
    assert presets_apply not in view_closed_again.layout.rows
    assert reset not in view_closed_again.layout.rows
    assert cuts_header not in view_closed_again.layout.rows
    assert bar_phase not in view_closed_again.layout.rows
    assert bar_grid not in view_closed_again.layout.rows
    assert placement_snap not in view_closed_again.layout.rows
    assert snap_beats not in view_closed_again.layout.rows
    assert snap_bars not in view_closed_again.layout.rows
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
    session.render_overlays.opening_card.animation.type = "fade"
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.render_overlays.opening_card.animation.type = "slide"
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_builder_rebuilds_layout_when_animation_type_changes() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.render_overlays.expanded = True
    session.render_overlays.opening_card.expanded = True
    session.render_overlays.opening_card.animation_expanded = True
    session.render_overlays.opening_card.animation.type = "fade"
    view_fade = controls.build_view_state(paused=False)
    kinds_fade = [row.kind for row in view_fade.layout.rows]
    assert RowKind.RENDER_OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION not in kinds_fade

    session.render_overlays.opening_card.animation.type = "slide"
    view_slide = controls.build_view_state(paused=False)
    kinds_slide = [row.kind for row in view_slide.layout.rows]
    assert RowKind.RENDER_OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION in kinds_slide


def test_structure_signature_invalidates_on_opening_card_expanded() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.render_overlays.expanded = True
    session.render_overlays.opening_card.expanded = False
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.render_overlays.opening_card.expanded = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_closing_card_animation_type() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.render_overlays.closing_card.animation.type = "fade"
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.render_overlays.closing_card.animation.type = "slide"
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



def test_structure_signature_invalidates_on_preset_switching_trigger() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.layers["layer_1"].preset_switching = "on"
    session.layers["layer_1"].preset_switching_trigger = "timer"
    sig_timer = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.layers["layer_1"].preset_switching_trigger = "projectm"
    sig_projectm = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_timer != sig_projectm
    session.layers["layer_1"].preset_switching_trigger = "timeline"
    sig_timeline = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_projectm != sig_timeline
    session.layers["layer_1"].preset_switching = "off"
    sig_off = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_timeline != sig_off


def test_structure_signature_invalidates_on_auto_preset_path() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    layer = session.layers["layer_1"]
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    layer.auto_preset_path = layer.playlist.paths[1].resolve()
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_builder_shows_auto_preset_in_file_row_only() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    layer = session.layers["layer_1"]
    layer.preset_switching = "on"
    root = controls._view_state.preset_root
    bed = root / "roles" / "bed"
    pulse = root / "roles" / "pulse"
    bed.mkdir(parents=True, exist_ok=True)
    pulse.mkdir(parents=True, exist_ok=True)
    bed_a = bed / "bed-a.milk"
    bed_b = bed / "bed-b.milk"
    pulse_a = pulse / "pulse-a.milk"
    for path in (bed_a, bed_b, pulse_a):
        path.write_text("milk", encoding="utf-8")

    view_browse = controls.build_view_state(paused=False)
    browse_dir_label = view_browse.tracks["layer_1"].preset_dir_label
    assert "roles/" not in browse_dir_label

    layer.auto_preset_path = bed_b.resolve()
    view_bed = controls.build_view_state(paused=False)
    assert view_bed.tracks["layer_1"].preset_dir_label == browse_dir_label
    assert view_bed.tracks["layer_1"].preset_label.startswith("bed-b.milk (2/2)")

    layer.auto_preset_path = pulse_a.resolve()
    view_pulse = controls.build_view_state(paused=False)
    assert view_pulse.tracks["layer_1"].preset_dir_label == browse_dir_label
    assert view_pulse.tracks["layer_1"].preset_label.startswith("pulse-a.milk (1/1)")
    # Browse playlist unchanged (config stays clean).
    assert layer.playlist.index == 0


def test_builder_shows_off_root_auto_preset_without_crashing(
    tmp_path: Path,
) -> None:
    """Playing an off-root preset copy must not break directory display."""
    controls = _make_controls(("layer_1",))
    session = controls.session
    layer = session.layers["layer_1"]
    layer.preset_switching = "on"
    browse_dir_label = controls.build_view_state(paused=False).tracks[
        "layer_1"
    ].preset_dir_label

    user_dir = tmp_path / "presets"
    user_dir.mkdir()
    playing = user_dir / "copied.milk"
    playing.write_text("milk", encoding="utf-8")
    layer.auto_preset_path = playing.resolve()

    view = controls.build_view_state(paused=False)
    assert view.tracks["layer_1"].preset_dir_label == browse_dir_label
    assert view.tracks["layer_1"].preset_label.startswith("copied.milk")


def test_structure_signature_invalidates_on_persistent_notification() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    sig_inactive = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    sig_persistent = view_state_structure_signature(
        session,
        config_save,
        notification_active=False,
        persistent_notification_active=True,
    )
    assert sig_inactive != sig_persistent
    sig_both = view_state_structure_signature(
        session,
        config_save,
        notification_active=True,
        persistent_notification_active=True,
    )
    assert sig_persistent != sig_both



def test_timeline_mode_row_set_unchanged_when_timeline_enabled_toggles() -> None:
    """Dimming when timeline is disabled does not add or remove preset-switching rows."""
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.layers["layer_1"].expanded = True
    session.layers["layer_1"].preset_switching = "on"
    session.timeline.enabled = True
    builder = controls._view_state
    kinds_on = [desc.kind for desc in builder.build(paused=False).layout.rows]
    session.timeline.enabled = False
    kinds_off = [desc.kind for desc in builder.build(paused=False).layout.rows]
    assert kinds_on == kinds_off



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


def test_structure_signature_invalidates_on_timeline_levels_expanded() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.timeline.cuts_expanded = False
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.timeline.cuts_expanded = True
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


def test_structure_signature_invalidates_on_pattern_mask_expanded() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.render_pattern_mask.expanded = False
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.render_pattern_mask.expanded = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_pattern_mask_type() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.render_pattern_mask.type = "strips"
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.render_pattern_mask.type = "plasma"
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_pattern_mask_seed_row_only_for_plasma() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.render_pattern_mask.expanded = True
    session.render_pattern_mask.type = "strips"
    builder = controls._view_state

    view_strips = builder.build(paused=False)
    seed = RowDescriptor(RowKind.RENDER_PATTERN_MASK_SEED)
    feather = RowDescriptor(RowKind.RENDER_PATTERN_MASK_FEATHER)
    assert feather in view_strips.layout.rows
    assert seed not in view_strips.layout.rows

    session.render_pattern_mask.type = "plasma"
    view_plasma = builder.build(paused=False)
    assert view_plasma.layout is not view_strips.layout
    assert seed in view_plasma.layout.rows
    assert feather in view_plasma.layout.rows


def test_structure_signature_invalidates_on_hard_cut_fades_enabled() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.timeline.hard_cut_fades.enabled = False
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.timeline.hard_cut_fades.enabled = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_soft_cut_fades_enabled() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.timeline.soft_cut_fades.enabled = False
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.timeline.soft_cut_fades.enabled = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_visual_limiter_expanded() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.timeline.visual_limiter_expanded = False
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.timeline.visual_limiter_expanded = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_visual_limiter_enabled() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.timeline.limiter.enabled = True
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.timeline.limiter.enabled = False
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
    beat_bar = RowDescriptor(RowKind.TIMELINE_BEAT_BAR_GRID_HEADER)
    assert view.layout.rows.index(beat_bar) == header_idx + len(items) + 1
    assert RowDescriptor(RowKind.TIMELINE_SNAP_TO_SONG_MARKERS) not in view.layout.rows

    session.song_markers.expanded = False
    view_collapsed = builder.build(paused=False)
    assert header in view_collapsed.layout.rows
    assert not any(
        desc.kind == RowKind.SONG_MARKER_ITEM for desc in view_collapsed.layout.rows
    )


def test_structure_signature_invalidates_on_snap_cues_expanded() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.timeline.snap_cues_expanded = False
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.timeline.snap_cues_expanded = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_builder_appends_curation_markers_without_structure_change() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    index = controls._view_state._curation_index
    layer = session.layers["layer_1"]
    user_path = Path("/tmp/projects/my-track/user.milk")
    user_path.parent.mkdir(parents=True, exist_ok=True)
    user_path.write_text("milk", encoding="utf-8")
    layer.preset_list = [str(user_path)]

    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    view_before = controls.build_view_state(paused=False)
    block_before = view_before.tracks["layer_1"]
    assert block_before.preset_label == "preset-0.milk (1/3)"
    assert block_before.preset_list_labels == ["user.milk"]

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
    assert block_after.preset_list_labels == ["user.milk [FB]"]


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
    layer_2.preset_list = [str(other_path)]

    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    view_u = controls.build_view_state(paused=False)
    assert view_u.tracks["layer_1"].preset_label == f"{current_name} (1/3) [U]"
    assert view_u.tracks["layer_2"].preset_list_labels == [current_name]

    index.mark_favourite(current_name)
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before == sig_after

    view_fu = controls.build_view_state(paused=False)
    assert view_fu.tracks["layer_1"].preset_label == f"{current_name} (1/3) [FU]"
    assert view_fu.tracks["layer_2"].preset_list_labels == [f"{current_name} [F]"]


def test_builder_caches_preset_list_base_labels(monkeypatch) -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    layer = session.layers["layer_1"]
    user_path = Path("/tmp/projects/my-track/user.milk")
    user_path.parent.mkdir(parents=True, exist_ok=True)
    user_path.write_text("milk", encoding="utf-8")
    layer.preset_list = [str(user_path)]

    calls: list[int] = []
    original = __import__(
        "cleave.viz.user_presets", fromlist=["preset_list_display_names"]
    ).preset_list_display_names

    def counting_display_names(paths: list[str]) -> list[str]:
        calls.append(1)
        return original(paths)

    monkeypatch.setattr(
        "cleave.viz.tuning_view_state.preset_list_display_names",
        counting_display_names,
    )

    view_first = controls.build_view_state(paused=False)
    view_second = controls.build_view_state(paused=False)
    assert view_first.tracks["layer_1"].preset_list_labels == ["user.milk"]
    assert view_second.tracks["layer_1"].preset_list_labels == ["user.milk"]
    assert calls == [1]

    index = controls._view_state._curation_index
    index.mark_favourite(user_path.name)
    view_marked = controls.build_view_state(paused=False)
    assert view_marked.tracks["layer_1"].preset_list_labels == ["user.milk [F]"]
    assert calls == [1]


def test_structure_signature_invalidates_on_preset_list_change() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    layer = session.layers["layer_1"]
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    layer.preset_list = ["/tmp/a.milk"]
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_uses_digest_not_full_paths() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    layer = session.layers["layer_1"]
    long_path = "/tmp/projects/my-track/very-long-directory-name/preset.milk"
    layer.preset_list = [long_path]
    sig = view_state_structure_signature(
        session, controls._config_save, notification_active=False
    )
    assert long_path not in sig
    assert '"digest"' in sig
    assert '"len":1' in sig.replace(" ", "")


def test_structure_signature_stable_for_long_preset_list() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    layer = session.layers["layer_1"]
    layer.preset_list = [f"/tmp/preset-{i}.milk" for i in range(40)]
    sig_a = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    sig_b = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_a == sig_b


def test_builder_caches_labels_across_idle_builds(monkeypatch) -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    layer = session.layers["layer_1"]
    layer.preset_list = [f"/tmp/preset-{i}.milk" for i in range(40)]
    layer.preset_list_expanded = False

    calls: list[int] = []
    original = __import__(
        "cleave.viz.user_presets", fromlist=["preset_list_display_names"]
    ).preset_list_display_names

    def counting_display_names(paths: list[str]) -> list[str]:
        calls.append(1)
        return original(paths)

    monkeypatch.setattr(
        "cleave.viz.tuning_view_state.preset_list_display_names",
        counting_display_names,
    )

    controls.build_view_state(paused=False)
    controls.build_view_state(paused=False)
    assert calls == [1]


def test_collapsed_preset_list_omits_item_rows() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    layer = session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_list = [f"/tmp/preset-{i}.milk" for i in range(5)]
    layer.preset_list_expanded = False
    view = controls.build_view_state(paused=False)
    kinds = {desc.kind for desc in view.layout.rows}
    assert RowKind.TRACK_PRESET_LIST in kinds
    assert RowKind.TRACK_PRESET_LIST_ITEM not in kinds
    assert RowKind.TRACK_PRESET_LIST_ADD not in kinds


def test_session_mutation_visible_on_next_view_state() -> None:
    controls = _make_controls(("layer_1",))
    runtime = controls.session.layers["layer_1"]
    first = controls.build_view_state(paused=False)
    assert first.tracks["layer_1"].runtime is runtime
    runtime.opacity_pct = 22
    second = controls.build_view_state(paused=False)
    assert second.tracks["layer_1"].runtime is runtime
    assert second.tracks["layer_1"].runtime.opacity_pct == 22
