"""Tests for TuningViewStateBuilder structure signature and cache."""

from __future__ import annotations

import json
from pathlib import Path

from cleave.viz.inspector import build_inspector_rows
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.tuning_view_state import view_state_structure_signature
from tests.cleave.viz.test_controls import _make_controls


def test_structure_signature_stable_for_fps_and_focus() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    sig_a = view_state_structure_signature(
        session, config_save)
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    sig_b = view_state_structure_signature(
        session, config_save)
    assert sig_a == sig_b

    assert view_state_structure_signature(
        session, config_save) == sig_a


def test_layer_expand_flags_absent_from_structure_signature() -> None:
    controls = _make_controls(("layer_1",))
    sig = view_state_structure_signature(
        controls.session, controls._config_save)
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
        session, config_save)
    session.layer_z_order = ["layer_1"]
    del session.layers["layer_2"]
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_preset_navigation() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    layer = session.layers["layer_1"]
    config_save = controls._config_save
    sig_before = view_state_structure_signature(
        session, config_save)
    layer.playlist.next()
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before != sig_after


def test_structure_signature_unchanged_when_notification_shows() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    sig_before = view_state_structure_signature(session, config_save)
    controls.show_notification("Saved")
    controls._notification_host.set_persistent("No presets in bed roles folder")
    sig_after = view_state_structure_signature(session, config_save)
    view_after = controls.build_view_state(paused=False)
    assert sig_before == sig_after
    assert view_after.notification_message == "Saved"
    assert (
        view_after.persistent_notification_message
        == "No presets in bed roles folder"
    )


def test_reused_structure_keeps_focus() -> None:
    controls = _make_controls(("layer_1",))
    controls.focus_descriptor = RowDescriptor(RowKind.TRACK_BLEND, slot="layer_1")
    view_a = controls.build_view_state(paused=False, fps=30.0)
    view_b = controls.build_view_state(paused=True, fps=60.0, position_sec=42.0)
    assert view_a.focus_descriptor == view_b.focus_descriptor
    assert view_a.focus_descriptor == RowDescriptor(RowKind.TRACK_BLEND, slot="layer_1")


def test_builder_patches_highlight_rolloff_curve_without_structure_rebuild() -> None:
    controls = _make_controls(("layer_1",))
    builder = controls._view_state
    session = controls.session
    session.post_fx.highlight_rolloff.curve = "rolloff"

    view_a = builder.build(paused=False)
    structure = builder._structure
    assert view_a.post_fx.highlight_rolloff.curve == "rolloff"

    session.post_fx.highlight_rolloff.curve = "smoothstep"
    view_b = builder.build(paused=False)
    assert builder._structure is structure
    assert view_b.post_fx.highlight_rolloff.curve == "smoothstep"


def test_structure_signature_ignores_timeline_panel_open() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.timeline.panel_open = False
    sig_before = view_state_structure_signature(
        session, config_save)
    session.timeline.panel_open = True
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before == sig_after
    timeline = json.loads(sig_after)["timeline"]
    for flag in (
        "panel_open",
        "beat_bar_grid_expanded",
        "cuts_expanded",
        "timeline_presets_expanded",
        "expanded",
    ):
        assert flag not in timeline



def test_structure_signature_invalidates_on_highlight_rolloff_mode() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.post_fx.highlight_rolloff.mode = "composite"
    sig_before = view_state_structure_signature(
        session, config_save)
    session.post_fx.highlight_rolloff.mode = "off"
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_animation_type() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.overlays.opening_card.animation.type = "fade"
    sig_before = view_state_structure_signature(
        session, config_save)
    session.overlays.opening_card.animation.type = "slide"
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before != sig_after


def _inspector_kinds(state, node_id: str) -> list[RowKind]:
    rows = build_inspector_rows(state, node_id)
    return [row.descriptor.kind for row in rows if row.descriptor is not None]


def test_builder_rebuilds_layout_when_animation_type_changes() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.overlays.opening_card.animation.type = "fade"
    view_fade = controls.build_view_state(paused=False)
    node = "overlay.opening_card"
    fade_page = _inspector_kinds(view_fade, node)
    assert RowKind.OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION not in fade_page
    fade_structure = controls._view_state._structure

    session.overlays.opening_card.animation.type = "slide"
    view_slide = controls.build_view_state(paused=False)
    slide_page = _inspector_kinds(view_slide, node)
    assert RowKind.OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION in slide_page
    assert controls._view_state._structure is not fade_structure


def test_structure_signature_invalidates_on_closing_card_animation_type() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.overlays.closing_card.animation.type = "fade"
    sig_before = view_state_structure_signature(
        session, config_save)
    session.overlays.closing_card.animation.type = "slide"
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_chroma_boost_mode() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.post_fx.chroma_boost.mode = "composite"
    sig_before = view_state_structure_signature(
        session, config_save)
    session.post_fx.chroma_boost.mode = "off"
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before != sig_after


def test_builder_rebuilds_layout_when_highlight_rolloff_mode_changes() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    session.post_fx.highlight_rolloff.mode = "composite"
    builder = controls._view_state

    view_on = builder.build(paused=False)
    on_page = _inspector_kinds(view_on, "post_fx.highlight_rolloff")
    assert RowKind.POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD in on_page
    on_structure = builder._structure

    session.post_fx.highlight_rolloff.mode = "off"
    view_off = builder.build(paused=False)
    assert builder._structure is not on_structure
    assert RowKind.POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD not in _inspector_kinds(
        view_off, "post_fx"
    )



def test_structure_signature_invalidates_on_preset_switching_trigger() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.layers["layer_1"].preset_switching = "on"
    session.layers["layer_1"].preset_switching_trigger = "timer"
    sig_timer = view_state_structure_signature(
        session, config_save)
    session.layers["layer_1"].preset_switching_trigger = "projectm"
    sig_projectm = view_state_structure_signature(
        session, config_save)
    assert sig_timer != sig_projectm
    session.layers["layer_1"].preset_switching_trigger = "timeline"
    sig_timeline = view_state_structure_signature(
        session, config_save)
    assert sig_projectm != sig_timeline
    session.layers["layer_1"].preset_switching = "off"
    session.layers["layer_1"].preset_switching_trigger = "off"
    sig_off = view_state_structure_signature(
        session, config_save)
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
        session, config_save)
    layer.hard_cut_enabled = False
    sig_off = view_state_structure_signature(
        session, config_save)
    assert sig_on != sig_off


def test_structure_signature_invalidates_on_switching_paused() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    layer = session.layers["layer_1"]
    sig_before = view_state_structure_signature(
        session, config_save)
    layer.switching_paused = True
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before != sig_after


def test_builder_mirrors_switching_paused_into_inspector() -> None:
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
    from cleave.viz.navigator import layer_page_node_id

    def inspector_commands(view: object) -> set[str]:
        rows = build_inspector_rows(
            view, layer_page_node_id("layer_1", "milkdrop_preset")
        )
        return {command for row in rows for command in row.command_ids}

    hidden = controls.build_view_state(paused=False)
    assert "layers.resume_switching" not in inspector_commands(hidden)
    assert session.layers["layer_1"].switching_paused is False

    stem.switching_paused = True
    shown = controls.build_view_state(paused=False)
    assert session.layers["layer_1"].switching_paused is True
    assert "layers.resume_switching" in inspector_commands(shown)


def test_structure_signature_invalidates_on_auto_preset_path() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    layer = session.layers["layer_1"]
    sig_before = view_state_structure_signature(
        session, config_save)
    layer.auto_preset_path = layer.playlist.paths[1].resolve()
    sig_after = view_state_structure_signature(
        session, config_save)
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
    assert view_bed.tracks["layer_1"].preset_label == "bed-b.milk"
    assert view_bed.tracks["layer_1"].preset_position == "2/2"

    layer.auto_preset_path = pulse_a.resolve()
    view_pulse = controls.build_view_state(paused=False)
    assert view_pulse.tracks["layer_1"].preset_dir_label == browse_dir_label
    assert view_pulse.tracks["layer_1"].preset_label == "pulse-a.milk"
    assert view_pulse.tracks["layer_1"].preset_position == "1/1"
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





def test_structure_signature_invalidates_on_song_marker_count() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    sig_before = view_state_structure_signature(
        session, config_save)
    session.song_markers.times = [10.0, 20.0]
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before != sig_after




def test_structure_signature_invalidates_on_pattern_mask_type() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.pattern_mask.type = "strips"
    sig_before = view_state_structure_signature(
        session, config_save)
    session.pattern_mask.type = "plasma"
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before != sig_after


def test_pattern_mask_seed_row_only_for_plasma() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    builder = controls._view_state

    for mask_type in ("strips", "bars", "radial", "checker"):
        session.pattern_mask.type = mask_type
        view = builder.build(paused=False)
        page = _inspector_kinds(view, "pattern_mask.pattern")
        assert RowKind.PATTERN_MASK_DENSITY in page
        assert RowKind.PATTERN_MASK_SEED not in page

    session.pattern_mask.type = "plasma"
    view_plasma = builder.build(paused=False)
    plasma = _inspector_kinds(view_plasma, "pattern_mask.pattern")
    assert RowKind.PATTERN_MASK_SEED in plasma
    assert RowKind.PATTERN_MASK_DENSITY in plasma


def test_structure_signature_invalidates_on_hard_cut_fades_enabled() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.timeline.hard_cut_fades.enabled = False
    sig_before = view_state_structure_signature(
        session, config_save)
    session.timeline.hard_cut_fades.enabled = True
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_soft_cut_fades_enabled() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.timeline.soft_cut_fades.enabled = False
    sig_before = view_state_structure_signature(
        session, config_save)
    session.timeline.soft_cut_fades.enabled = True
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_visual_limiter_enabled() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.post_fx.limiter.enabled = True
    sig_before = view_state_structure_signature(
        session, config_save)
    session.post_fx.limiter.enabled = False
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before != sig_after


def test_structure_signature_omits_expand_flags() -> None:
    controls = _make_controls(("layer_1",))
    sig = view_state_structure_signature(
        controls.session, controls._config_save)
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


def test_song_marker_items_stay_on_the_inspector() -> None:
    from cleave.viz.inspector import build_inspector_rows

    controls = _make_controls(("layer_1",))
    session = controls.session
    session.timeline.panel_open = True
    session.song_markers.times = [8.0, 32.5, 64.0]
    view = controls.build_view_state(paused=False)
    rows = build_inspector_rows(view, "timeline.song_markers")
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
    library = controls.library
    layer = session.layers["layer_1"]
    current = layer.playlist.current
    assert current is not None
    current.parent.mkdir(parents=True, exist_ok=True)
    current.write_text("current milk", encoding="utf-8")
    user_path = Path("/tmp/projects/my-track/user.milk")
    user_path.parent.mkdir(parents=True, exist_ok=True)
    user_path.write_text("milk", encoding="utf-8")
    layer.preset_list = [str(user_path)]

    sig_before = view_state_structure_signature(
        session, config_save)
    view_before = controls.build_view_state(paused=False)
    block_before = view_before.tracks["layer_1"]
    assert block_before.preset_label == "preset-0.milk"
    assert block_before.preset_position == "1/3"
    assert block_before.preset_markers == ""
    assert block_before.preset_list_labels == ["user.milk"]

    library.set_favourite(current, True)
    library.set_favourite(user_path, True)
    library.set_blacklisted(user_path, True)

    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before == sig_after

    view_after = controls.build_view_state(paused=False)
    block_after = view_after.tracks["layer_1"]
    assert block_after.preset_label == "preset-0.milk"
    assert block_after.preset_markers == "[F]"
    # List entries never show [L]: they are in the list by definition.
    assert block_after.preset_list_labels == ["user.milk"]
    assert block_after.preset_list_markers == ["[F] [B]"]


def test_builder_marks_current_preset_in_this_layers_preset_list() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    session = controls.session
    config_save = controls._config_save
    library = controls.library
    layer_1 = session.layers["layer_1"]
    layer_2 = session.layers["layer_2"]
    current = layer_1.playlist.current
    assert current is not None
    current.parent.mkdir(parents=True, exist_ok=True)
    current.write_text("milk", encoding="utf-8")
    current_name = current.name

    listed = Path("/tmp/projects/my-track") / current_name
    listed.parent.mkdir(parents=True, exist_ok=True)
    listed.write_text("milk", encoding="utf-8")

    # Listed on another layer only: no [L] here.
    layer_2.preset_list = [str(listed)]
    view = controls.build_view_state(paused=False)
    assert view.tracks["layer_1"].preset_markers == ""
    assert view.tracks["layer_2"].preset_list_markers == [""]

    layer_1.preset_list = [str(listed)]
    sig_before = view_state_structure_signature(session, config_save)
    view = controls.build_view_state(paused=False)
    assert view.tracks["layer_1"].preset_label == current_name
    assert view.tracks["layer_1"].preset_markers == "[L]"

    library.set_favourite(current, True)
    assert view_state_structure_signature(session, config_save) == sig_before
    view = controls.build_view_state(paused=False)
    assert view.tracks["layer_1"].preset_markers == "[F] [L]"
    assert view.tracks["layer_1"].preset_list_markers == ["[F]"]

    session.settings.editor_mode = "preset_curation"
    view = controls.build_view_state(paused=False)
    assert view.tracks["layer_1"].preset_markers == "[F]"


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

    controls.library.set_favourite(user_path, True)
    view_marked = controls.build_view_state(paused=False)
    assert view_marked.tracks["layer_1"].preset_list_labels == ["user.milk"]
    assert view_marked.tracks["layer_1"].preset_list_markers == ["[F]"]
    assert calls == [1]


def test_structure_signature_invalidates_on_preset_list_change() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    layer = session.layers["layer_1"]
    sig_before = view_state_structure_signature(
        session, config_save)
    layer.preset_list = ["/tmp/a.milk"]
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before != sig_after


def test_structure_signature_uses_digest_not_full_paths() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    layer = session.layers["layer_1"]
    long_path = "/tmp/projects/my-track/very-long-directory-name/preset.milk"
    layer.preset_list = [long_path]
    sig = view_state_structure_signature(
        session, controls._config_save)
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
        session, config_save)
    sig_b = view_state_structure_signature(
        session, config_save)
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


def test_structure_signature_invalidates_on_selected_cue_kind() -> None:
    from cleave.timeline import SlotCue, TimelineLane

    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    tl = session.timeline
    tl.lanes["layer_1"] = TimelineLane(
        baseline=0.0,
        cues=[SlotCue(t=10.0, level=1.0), SlotCue(t=20.0, level=0.0)],
    )
    none = view_state_structure_signature(session, config_save)
    tl.selected_cue_t["layer_1"] = 10.0
    start = view_state_structure_signature(session, config_save)
    tl.selected_cue_t["layer_1"] = 20.0
    end = view_state_structure_signature(session, config_save)
    assert len({none, start, end}) == 3


def test_preset_position_counts_within_browsed_collection(tmp_path: Path) -> None:
    from cleave.preset_playlist import playlist_at_collection

    controls = _make_controls(("layer_1",))
    library = controls.library
    pack = tmp_path / "pack"
    pack.mkdir()
    for name in ("a", "b", "c"):
        (pack / f"{name}.milk").write_text(name, encoding="utf-8")
    library.index(tmp_path)
    fav = (pack / "b.milk").resolve()
    library.set_favourite(fav, True)
    library.set_role(fav, "pulse")
    library.set_blacklisted((pack / "c.milk").resolve(), True)
    layer = controls.session.layers["layer_1"]

    for collection in ("favourites", "pulse", "blacklisted"):
        layer.playlist = playlist_at_collection(
            collection, current_dir=pack, catalog=library
        )
        layer.auto_preset_path = layer.playlist.current
        controls._view_state._structure = None
        block = controls.build_view_state(paused=False).tracks["layer_1"]
        assert block.preset_position == "1/1", collection
