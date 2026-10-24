"""Tests for TuningViewStateBuilder structure signature and cache."""

from __future__ import annotations

import json
from pathlib import Path

from cleave.viz.inspector import build_inspector_rows
from cleave.viz.navigator import overlay_card_node_id
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


def test_layer_expand_flags_absent_from_structure_signature() -> None:
    controls = _make_controls(("layer_1",))
    sig = view_state_structure_signature(
        controls.session, controls._config_save, notification_active=False
    )
    layer = json.loads(sig)["layers"]["layer_1"]
    for flag in (
        "expanded",
        "effects_expanded",
        "compositing_expanded",
        "preset_list_expanded",
        "preset_switching_expanded",
    ):
        assert flag not in layer


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


def test_structure_signature_ignores_timeline_panel_open() -> None:
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
    assert sig_before == sig_after



def test_layout_rows_omit_timeline_and_song_markers() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.timeline.panel_open = True
    session.song_markers.times = [1.0, 8.0]
    session.timeline.hard_cut_fades.enabled = True
    session.timeline.soft_cut_fades.enabled = True
    view = controls.build_view_state(paused=False)
    kinds = {row.kind for row in view.layout.rows}
    forbidden = {
        RowKind.RENDER_TIMELINE_HEADER,
        RowKind.SONG_MARKERS_HEADER,
        RowKind.SONG_MARKER_ITEM,
        RowKind.TIMELINE_PRESETS_HEADER,
        RowKind.TIMELINE_BEAT_BAR_GRID_HEADER,
        RowKind.TIMELINE_CUTS_HEADER,
        RowKind.TIMELINE_SNAP_TO_SONG_MARKERS,
        RowKind.TIMELINE_PRESET_CHARACTER,
        RowKind.TIMELINE_HARD_CUTS,
    }
    assert kinds.isdisjoint(forbidden)
    assert kinds <= {RowKind.PANEL_NOTIFICATION}

    session.timeline.panel_open = False
    closed = controls.build_view_state(paused=False)
    assert {row.kind for row in closed.layout.rows} == kinds

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


def _inspector_kinds(state, node_id: str) -> list[RowKind]:
    rows = build_inspector_rows(state, node_id, frozenset())
    return [row.descriptor.kind for row in rows if row.descriptor is not None]


def test_builder_rebuilds_layout_when_animation_type_changes() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.render_overlays.opening_card.animation.type = "fade"
    view_fade = controls.build_view_state(paused=False)
    node = overlay_card_node_id("opening_card")
    fade_page = _inspector_kinds(view_fade, node)
    assert RowKind.RENDER_OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION not in fade_page
    assert RowKind.RENDER_OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION not in {
        row.kind for row in view_fade.layout.rows
    }

    session.render_overlays.opening_card.animation.type = "slide"
    view_slide = controls.build_view_state(paused=False)
    slide_page = _inspector_kinds(view_slide, node)
    assert RowKind.RENDER_OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION in slide_page
    assert RowKind.RENDER_OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION not in {
        row.kind for row in view_slide.layout.rows
    }
    assert view_slide.layout is not view_fade.layout


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
    session.render_post_fx.highlight_rolloff.mode = "composite"
    builder = controls._view_state

    view_on = builder.build(paused=False)
    on_page = _inspector_kinds(view_on, "render.post_fx")
    assert RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD in on_page
    assert RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD not in {
        row.kind for row in view_on.layout.rows
    }

    session.render_post_fx.highlight_rolloff.mode = "off"
    view_off = builder.build(paused=False)
    assert view_off.layout is not view_on.layout
    assert RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD not in _inspector_kinds(
        view_off, "render.post_fx"
    )



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
    session.layers["layer_1"].preset_switching_trigger = "off"
    sig_off = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_timeline != sig_off


def test_structure_signature_invalidates_on_hard_cut_enabled() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    layer = session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "projectm"
    layer.hard_cut_enabled = True
    sig_on = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    layer.hard_cut_enabled = False
    sig_off = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_on != sig_off


def test_structure_signature_invalidates_on_switching_paused() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    layer = session.layers["layer_1"]
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    layer.switching_paused = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_builder_mirrors_switching_paused_into_layout() -> None:
    from unittest.mock import MagicMock

    from cleave.viz.layer import StemLayer

    controls = _make_controls(("layer_1",))
    session = controls.session
    layer = session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    stem = MagicMock(spec=StemLayer)
    stem.switching_paused = False
    stem.auto_preset_path = None
    stem.preset_rotation = None
    stem.projectm_playlist = None
    stem.playlist = layer.playlist
    controls._view_state._layers_by_slot = {"layer_1": stem}

    from cleave.viz.inspector import build_inspector_rows
    from cleave.viz.navigator import layer_node_id

    def inspector_kinds(view: object) -> set[RowKind]:
        rows = build_inspector_rows(view, layer_node_id("layer_1"), frozenset())
        return {
            row.descriptor.kind
            for row in rows
            if row.descriptor is not None
        }

    hidden = controls.build_view_state(paused=False)
    assert RowKind.TRACK_PRESET_SWITCHING_RESUME not in inspector_kinds(hidden)
    assert session.layers["layer_1"].switching_paused is False

    stem.switching_paused = True
    shown = controls.build_view_state(paused=False)
    assert session.layers["layer_1"].switching_paused is True
    assert RowKind.TRACK_PRESET_SWITCHING_RESUME in inspector_kinds(shown)


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


def test_builder_syncs_playing_list_preset_from_projectm_position() -> None:
    from unittest.mock import MagicMock

    from cleave.viz.layer import StemLayer

    controls = _make_controls(("layer_1",))
    session = controls.session
    layer = session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "projectm"
    a = Path("/tmp/presets/list-a.milk").resolve()
    b = Path("/tmp/presets/list-b.milk").resolve()
    layer.preset_list = [str(a), str(b)]
    layer.auto_preset_path = a

    stem = MagicMock(spec=StemLayer)
    stem.switching_paused = False
    stem.auto_preset_path = a
    stem.preset_rotation = None
    playlist = MagicMock()
    playlist.get_position.return_value = 1
    playlist.item.side_effect = lambda index: (a, b)[index]
    stem.projectm_playlist = playlist
    controls._view_state._layers_by_slot = {"layer_1": stem}

    view = controls.build_view_state(paused=False)
    assert session.layers["layer_1"].auto_preset_path == b
    assert view.tracks["layer_1"].active_preset_list_index == 1


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
    """Dimming when timeline is disabled does not add or remove leftover rows."""
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.layers["layer_1"].preset_switching = "on"
    session.layers["layer_1"].preset_switching_trigger = "timer"
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
    assert state.layout.rows == ()


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
    builder = controls._view_state

    for mask_type in ("strips", "bars", "radial", "checker"):
        session.render_pattern_mask.type = mask_type
        view = builder.build(paused=False)
        page = _inspector_kinds(view, "render.pattern_mask")
        assert RowKind.RENDER_PATTERN_MASK_FEATHER in page
        assert RowKind.RENDER_PATTERN_MASK_SEED not in page
        assert RowKind.RENDER_PATTERN_MASK_SEED not in {
            row.kind for row in view.layout.rows
        }

    session.render_pattern_mask.type = "plasma"
    view_plasma = builder.build(paused=False)
    plasma = _inspector_kinds(view_plasma, "render.pattern_mask")
    assert RowKind.RENDER_PATTERN_MASK_SEED in plasma
    assert RowKind.RENDER_PATTERN_MASK_FEATHER in plasma
    assert RowKind.RENDER_PATTERN_MASK_SEED not in {
        row.kind for row in view_plasma.layout.rows
    }


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


def test_structure_signature_invalidates_on_visual_limiter_enabled() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.render_post_fx.limiter.enabled = True
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.render_post_fx.limiter.enabled = False
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_leftover_layout_omits_settings_project_and_transport() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    names = {row.kind.name for row in view.layout.rows}
    assert "TRANSPORT" not in names
    assert not any(name.startswith("SETTINGS_") or name.startswith("PROJECT_") for name in names)
    sig = view_state_structure_signature(
        controls.session, controls._config_save, notification_active=False
    )
    payload = json.loads(sig)
    assert payload["settings"] == {"editor_mode": controls.session.settings.editor_mode}
    assert payload["project"] == {}
    for flag in (
        "editor_window_expanded",
        "ui_expanded",
        "latency_compensation_expanded",
        "milkdrop_expanded",
        "compositor_expanded",
        "render_expanded",
        "title_expanded",
        "body_expanded",
        "animation_expanded",
        "highlight_rolloff_expanded",
        "chroma_boost_expanded",
        "limiter_expanded",
    ):
        assert flag not in sig


def test_layout_omits_track_timeline_and_song_marker_rows() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    view = controls.build_view_state(paused=False)
    kinds = {row.kind for row in view.layout.rows}
    names = {kind.name for kind in kinds}
    assert not any(name.startswith("TRACK_") for name in names)
    assert RowKind.LAYER_MANAGEMENT_ADD not in kinds
    assert RowKind.RENDER_SECTION_GAP not in kinds
    assert RowKind.RENDER_OVERLAYS_HEADER not in kinds
    assert RowKind.RENDER_POST_FX_HEADER not in kinds
    assert RowKind.RENDER_PATTERN_MASK_HEADER not in kinds
    assert RowKind.RENDER_TIMELINE_HEADER not in kinds
    assert RowKind.SONG_MARKERS_HEADER not in kinds
    assert RowKind.SONG_MARKER_ITEM not in kinds

    session = controls.session
    session.timeline.panel_open = True
    session.song_markers.times = [1.0]
    open_view = controls.build_view_state(paused=False)
    open_kinds = {row.kind for row in open_view.layout.rows}
    assert RowKind.SONG_MARKERS_HEADER not in open_kinds
    assert RowKind.SONG_MARKER_ITEM not in open_kinds
    assert RowKind.TIMELINE_BEAT_BAR_GRID_HEADER not in open_kinds
    assert RowKind.RENDER_TIMELINE_HEADER not in open_kinds
    assert not any(
        row.kind.name.startswith("TRACK_") for row in open_view.layout.rows
    )

def test_curation_leftover_layout_is_notifications_only() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.settings.editor_mode = "preset_curation"
    view = controls.build_view_state(paused=False)
    assert all(row.kind == RowKind.PANEL_NOTIFICATION for row in view.layout.rows)

    controls.show_notification("Saved")
    toasted = controls.build_view_state(paused=False)
    assert toasted.layout.rows
    assert all(
        row.kind == RowKind.PANEL_NOTIFICATION for row in toasted.layout.rows
    )
    assert not any(row.kind.name.startswith("TRACK_") for row in toasted.layout.rows)
    assert RowKind.LAYER_MANAGEMENT_ADD not in {
        row.kind for row in toasted.layout.rows
    }
    assert RowKind.RENDER_OVERLAYS_HEADER not in {
        row.kind for row in toasted.layout.rows
    }


def test_song_marker_items_stay_on_the_inspector() -> None:
    from cleave.viz.inspector import build_inspector_rows

    controls = _make_controls(("layer_1",))
    session = controls.session
    session.timeline.panel_open = True
    session.song_markers.times = [8.0, 32.5, 64.0]
    view = controls.build_view_state(paused=False)
    layout_kinds = {row.kind for row in view.layout.rows}
    assert RowKind.SONG_MARKERS_HEADER not in layout_kinds
    assert RowKind.SONG_MARKER_ITEM not in layout_kinds
    rows = build_inspector_rows(view, "song_markers", frozenset(), frozenset())
    items = [
        row.descriptor
        for row in rows
        if row.descriptor is not None
        and row.descriptor.kind == RowKind.SONG_MARKER_ITEM
    ]
    assert [desc.marker_index for desc in items] == [0, 1, 2]

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


def test_session_mutation_visible_on_next_view_state() -> None:
    controls = _make_controls(("layer_1",))
    runtime = controls.session.layers["layer_1"]
    first = controls.build_view_state(paused=False)
    assert first.tracks["layer_1"].runtime is runtime
    runtime.opacity_pct = 22
    second = controls.build_view_state(paused=False)
    assert second.tracks["layer_1"].runtime is runtime
    assert second.tracks["layer_1"].runtime.opacity_pct == 22
