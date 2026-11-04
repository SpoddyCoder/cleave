"""Inspector row model: page rows, headings, and conditional rows."""

from __future__ import annotations

import pytest

from cleave.effects.registry import effect_roster
from cleave.viz.focus_nav import MainFocus
from cleave.viz.inspector import build_inspector_rows
from cleave.viz.navigator import layer_node_id, layer_page_node_id
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_present_renderers import inspector_field_colors
from cleave.viz.row_spec import format_row_value
from cleave.viz.theme import ACTION, LOCKED
from cleave.viz.tuning_view_state import SettingsBlock, TuningViewState
from tests.support.config import TEST_LAYER_STEMS
from tests.support.viz import make_track_block


def _view_state() -> TuningViewState:
    return TuningViewState(
        layer_z_order=(),
        tracks={},
        paused=False,
        position_sec=0.0,
        focus_cursor=MainFocus(RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)),
        move_mode_slot=None,
    )


def _kinds(rows: tuple) -> list[RowKind]:
    return [
        row.descriptor.kind
        for row in rows
        if row.descriptor is not None and not row.is_heading
    ]


def _headings(rows: tuple) -> list[RowKind]:
    return [row.descriptor.kind for row in rows if row.is_heading]


def _layer_view(
    slots: tuple[str, ...],
    *,
    editor_mode: str = "visualizer",
    trigger: str = "off",
    preset_list: list[str] | None = None,
) -> TuningViewState:
    tracks = {
        slot: make_track_block(
            stem=TEST_LAYER_STEMS.get(slot, "drums"),
            preset_switching_trigger=trigger,
            preset_list=list(preset_list or []),
        )
        for slot in slots
    }
    return TuningViewState(
        layer_z_order=slots,
        tracks=tracks,
        paused=False,
        position_sec=0.0,
        focus_cursor=MainFocus(RowDescriptor(RowKind.TRACK_HEADER, slot=slots[0])),
        move_mode_slot=None,
        settings=SettingsBlock(editor_mode=editor_mode),
    )


@pytest.mark.parametrize(
    "node_id",
    ("settings", "project", "overlay", "post_fx", "timeline", "render", "unknown"),
)
def test_parents_and_unknown_ids_have_no_rows(node_id: str) -> None:
    assert build_inspector_rows(_view_state(), node_id) == ()


def test_settings_pages() -> None:
    state = _view_state()
    window = build_inspector_rows(state, "settings.editor_window")
    assert _kinds(window)[0] == RowKind.SETTINGS_PREVIEW_QUALITY
    assert RowKind.SETTINGS_NAVIGATOR_SIDE in _kinds(window)
    assert _kinds(build_inspector_rows(state, "settings.ui")) == [
        RowKind.SETTINGS_UI_NOTIFICATION_DISPLAY
    ]
    latency = build_inspector_rows(state, "settings.latency")
    assert _kinds(latency) == [RowKind.SETTINGS_RESIDUAL_LATENCY_MS]
    assert latency[-1].command_id == "settings.measure_latency"
    assert latency[-1].depth == 0


def test_project_pages() -> None:
    state = _view_state()
    assert _kinds(build_inspector_rows(state, "project.projectm")) == [
        RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY
    ]
    assert _kinds(build_inspector_rows(state, "project.compositor")) == [
        RowKind.PROJECT_COMPOSITOR_HDR
    ]
    render = build_inspector_rows(state, "project.render")
    assert _kinds(render)[0] == RowKind.PROJECT_RENDER_OUTPUT
    assert render[-1].command_id == "project.render"


def test_page_header_is_never_a_row() -> None:
    state = _layer_view(("layer_1",))
    for node_id, header in (
        ("settings.ui", RowKind.SETTINGS_UI_HEADER),
        ("post_fx.fade", RowKind.RENDER_POST_FX_FADE_HEADER),
        ("pattern_mask", RowKind.RENDER_PATTERN_MASK_HEADER),
        ("timeline.preset", RowKind.TIMELINE_PRESETS_HEADER),
        ("overlay.opening_card", RowKind.RENDER_OVERLAY_CARD_HEADER),
        (layer_node_id("layer_1"), RowKind.TRACK_HEADER),
    ):
        assert header not in _kinds(build_inspector_rows(state, node_id))


def test_headings_are_static_and_show_their_rows() -> None:
    state = _view_state()
    rows = build_inspector_rows(state, "post_fx.fade")

    assert _headings(rows) == [
        RowKind.RENDER_POST_FX_FADE_IN_HEADER,
        RowKind.RENDER_POST_FX_FADE_OUT_HEADER,
    ]
    assert all(not row.navigable for row in rows if row.is_heading)
    assert all(row.depth == 0 for row in rows if row.is_heading)
    assert all(row.depth == 1 for row in rows if not row.is_heading)
    assert RowKind.RENDER_POST_FX_FADE_IN_START in _kinds(rows)
    assert RowKind.RENDER_POST_FX_FADE_OUT_TYPE in _kinds(rows)


def test_card_page_has_headings_and_card_identity() -> None:
    state = _view_state()
    rows = build_inspector_rows(state, "overlay.opening_card")

    assert _headings(rows) == [
        RowKind.RENDER_OVERLAY_CARD_ANIMATION_HEADER,
        RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER,
        RowKind.RENDER_OVERLAY_CARD_BODY_HEADER,
    ]
    for kind in (
        RowKind.RENDER_OVERLAY_CARD_POSITION,
        RowKind.RENDER_OVERLAY_CARD_OPACITY,
        RowKind.RENDER_OVERLAY_CARD_BORDER_COLOUR,
        RowKind.RENDER_OVERLAY_CARD_TITLE_FONT,
        RowKind.RENDER_OVERLAY_CARD_BODY_TEXT,
    ):
        assert kind in _kinds(rows)
    assert all(row.descriptor.card == "opening_card" for row in rows)
    closing = build_inspector_rows(state, "overlay.closing_card")
    assert all(row.descriptor.card == "closing_card" for row in closing)


def test_conditional_rows_follow_predicates() -> None:
    state = _view_state()
    assert state.render_pattern_mask.type != "plasma"
    assert RowKind.RENDER_PATTERN_MASK_SEED not in _kinds(
        build_inspector_rows(state, "pattern_mask")
    )
    state.render_pattern_mask.type = "plasma"
    assert RowKind.RENDER_PATTERN_MASK_SEED in _kinds(
        build_inspector_rows(state, "pattern_mask")
    )

    card = _kinds(build_inspector_rows(state, "overlay.opening_card"))
    assert state.render_overlays.opening_card.runtime.animation.type == "fade"
    assert RowKind.RENDER_OVERLAY_CARD_ANIMATION_TYPE in card
    assert RowKind.RENDER_OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION not in card

    assert state.render_post_fx.chroma_boost.mode == "off"
    assert _kinds(build_inspector_rows(state, "post_fx.chroma_boost")) == [
        RowKind.RENDER_POST_FX_CHROMA_BOOST_MODE
    ]


def test_beat_bar_grid_page() -> None:
    rows = build_inspector_rows(_view_state(), "timeline.grid")
    assert _kinds(rows) == [
        RowKind.TIMELINE_PLACEMENT_SNAP,
        RowKind.TIMELINE_BAR_GRID,
        RowKind.TIMELINE_BAR_PHASE,
    ]
    assert rows[-1].command_id == "timeline.snap_cues"


def test_timeline_preset_page_ends_with_commands() -> None:
    rows = build_inspector_rows(_view_state(), "timeline.preset")
    assert [row.command_id for row in rows[-2:]] == [
        "timeline.apply_preset",
        "timeline.reset",
    ]
    assert all(row.command_id is None for row in rows[:-2])


def test_cue_fades_page_follows_enabled_flags() -> None:
    state = _view_state()
    assert _kinds(build_inspector_rows(state, "timeline.cue_fades")) == [
        RowKind.TIMELINE_HARD_CUTS,
        RowKind.TIMELINE_SOFT_CUTS,
    ]
    state.render_timeline.hard_cut_fades.enabled = True
    state.render_timeline.soft_cut_fades.enabled = True
    kinds = _kinds(build_inspector_rows(state, "timeline.cue_fades"))
    hard_idx = kinds.index(RowKind.TIMELINE_HARD_CUTS)
    assert kinds[hard_idx : hard_idx + 6] == [
        RowKind.TIMELINE_HARD_CUTS,
        RowKind.TIMELINE_HARD_CUT_FADE_IN,
        RowKind.TIMELINE_HARD_CUT_FADE_OUT,
        RowKind.TIMELINE_HARD_CUT_CROSSFADE,
        RowKind.TIMELINE_APPLY_HARD_CUTS,
        RowKind.TIMELINE_REMOVE_HARD_CUTS,
    ]
    soft_idx = kinds.index(RowKind.TIMELINE_SOFT_CUTS)
    assert kinds[soft_idx : soft_idx + 6] == [
        RowKind.TIMELINE_SOFT_CUTS,
        RowKind.TIMELINE_SOFT_CUT_FADE_IN,
        RowKind.TIMELINE_SOFT_CUT_FADE_OUT,
        RowKind.TIMELINE_SOFT_CUT_CROSSFADE,
        RowKind.TIMELINE_APPLY_SOFT_CUTS,
        RowKind.TIMELINE_REMOVE_SOFT_CUTS,
    ]


def test_song_markers_page_is_snap_and_marker_rows() -> None:
    state = _view_state()
    state.render_timeline.song_marker_times = (1.0, 4.0, 9.0)
    rows = build_inspector_rows(state, "timeline.song_markers")
    kinds = _kinds(rows)

    assert kinds[0] == RowKind.TIMELINE_SNAP_TO_SONG_MARKERS
    assert all(row.command_id is None for row in rows)
    markers = [
        row.descriptor
        for row in rows
        if row.descriptor.kind is RowKind.SONG_MARKER_ITEM
    ]
    assert [desc.marker_index for desc in markers] == [0, 1, 2]
    assert all(row.depth == 0 for row in rows)


def test_locked_blocks_still_build() -> None:
    state = _view_state()
    state.render_overlays.locked = True
    state.render_post_fx.locked = True
    state.render_pattern_mask.locked = True

    position = next(
        row.descriptor
        for row in build_inspector_rows(state, "overlay.opening_card")
        if row.descriptor.kind is RowKind.RENDER_OVERLAY_CARD_POSITION
    )
    assert inspector_field_colors(state, position) == (LOCKED, LOCKED)

    fade_start = next(
        row.descriptor
        for row in build_inspector_rows(state, "post_fx.fade")
        if row.descriptor.kind is RowKind.RENDER_POST_FX_FADE_IN_START
    )
    assert inspector_field_colors(state, fade_start) == (LOCKED, LOCKED)

    density = next(
        row.descriptor
        for row in build_inspector_rows(state, "pattern_mask")
        if row.descriptor.kind is RowKind.RENDER_PATTERN_MASK_DENSITY
    )
    assert inspector_field_colors(state, density) == (LOCKED, LOCKED)


def test_layer_page_keeps_direct_rows_and_delete() -> None:
    state = _layer_view(("layer_1",))
    rows = build_inspector_rows(state, layer_node_id("layer_1"))
    assert _kinds(rows) == [
        RowKind.TRACK_STEM,
        RowKind.TRACK_BEAT,
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
    ]
    assert rows[-1].command_id == "layers.delete"
    assert rows[-1].navigable is True


def test_dynamic_effect_and_preset_rows_keep_slot_identity() -> None:
    state = _layer_view(
        ("layer_1",),
        trigger="timer",
        preset_list=["/tmp/a.milk", "/tmp/b.milk"],
    )
    effects = [
        row.descriptor
        for row in build_inspector_rows(
            state, layer_page_node_id("layer_1", "effects")
        )
    ]
    roster = effect_roster(state.tracks["layer_1"].runtime.stem)
    assert [(desc.effect_id, desc.driver_slug, desc.slot) for desc in effects] == [
        (item.effect_id, item.driver_slug, "layer_1") for item in roster
    ]

    rows = build_inspector_rows(
        state, layer_page_node_id("layer_1", "preset_switching")
    )
    assert _headings(rows) == [RowKind.TRACK_PRESET_LIST]
    items = [
        row.descriptor
        for row in rows
        if row.descriptor.kind is RowKind.TRACK_PRESET_LIST_ITEM
    ]
    assert [(desc.slot, desc.preset_index) for desc in items] == [
        ("layer_1", 0),
        ("layer_1", 1),
    ]
    assert RowKind.TRACK_PRESET_LIST_ADD in _kinds(rows)
    assert RowKind.TRACK_PRESET_LIST_POPULATE in _kinds(rows)


def test_section_lock_inspector_field_colors() -> None:
    state = _layer_view(("layer_1", "layer_2"))
    state.tracks["layer_1"].runtime.locked = True
    state.focus_cursor = MainFocus(
        RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")
    )
    opacity = RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")
    delete = RowDescriptor(RowKind.LAYER_MANAGEMENT_DELETE, slot="layer_1")
    assert inspector_field_colors(state, opacity) == (LOCKED, LOCKED)
    label, value = inspector_field_colors(state, delete)
    assert label == ACTION
    assert value != LOCKED
    rows = build_inspector_rows(state, layer_node_id("layer_1"))
    assert any(row.navigable and row.command_id == "layers.delete" for row in rows)


def test_layers_root_count_and_curation_omits_add() -> None:
    state = _layer_view(("layer_1", "layer_2"))
    rows = build_inspector_rows(state, "layers")
    assert _kinds(rows) == [RowKind.LAYER_MANAGEMENT_COUNT]
    assert rows[1].command_id == "layers.add"
    assert rows[1].navigable is True
    count = rows[0]
    assert count.navigable is False
    assert count.is_heading is False
    assert format_row_value(state, count.descriptor) == "2 of 8 layers"

    state.settings.editor_mode = "preset_curation"
    curation_rows = build_inspector_rows(state, "layers")
    assert _kinds(curation_rows) == [RowKind.LAYER_MANAGEMENT_COUNT]
    assert all(row.command_id != "layers.add" for row in curation_rows)
    assert _kinds(build_inspector_rows(state, layer_node_id("layer_1"))) == [
        RowKind.TRACK_STEM,
        RowKind.TRACK_BEAT,
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
    ]
