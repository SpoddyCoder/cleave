"""Inspector row model: page rows, headings, and conditional rows."""

from __future__ import annotations

import pytest

from cleave.effects.registry import effect_roster
from cleave.viz.focus_nav import MainFocus
from cleave.viz.inspector import build_inspector_rows
from cleave.timeline import SlotCue
from cleave.viz.navigator import (
    LAYER_PAGE_MILKDROP_PRESET,
    layer_node_id,
    layer_page_node_id,
    timeline_row_node_id,
)
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_present_renderers import inspector_field_colors
from cleave.viz.row_sections import SECTION_SWITCH_KINDS
from cleave.viz.row_spec import format_row_value, row_available, row_label
from cleave.viz.theme import DISABLED, VALUE, LOCKED
from cleave.viz.tuning_view_state import (
    SettingsBlock,
    TimelineBlock,
    TuningViewState,
)
from tests.support.config import TEST_LAYER_STEMS
from tests.support.viz import make_track_block


def _view_state() -> TuningViewState:
    return TuningViewState(
        layer_z_order=(),
        tracks={},
        paused=False,
        position_sec=0.0,
        focus_cursor=MainFocus(RowDescriptor(RowKind.OVERLAYS_HEADER)),
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
    ("settings", "project", "render", "unknown"),
)
def test_parents_and_unknown_ids_have_no_rows(node_id: str) -> None:
    assert build_inspector_rows(_view_state(), node_id) == ()


@pytest.mark.parametrize(
    ("node_id", "kinds"),
    (
        (
            "overlay",
            (
                RowKind.OVERLAYS_ENABLED,
                RowKind.OVERLAYS_SOLO,
                RowKind.OVERLAYS_LOCKED,
            ),
        ),
        ("post_fx", (RowKind.POST_FX_ENABLED, RowKind.POST_FX_LOCKED)),
        ("timeline", (RowKind.TIMELINE_ENABLED, RowKind.TIMELINE_LOCKED)),
    ),
)
def test_root_pages_list_only_their_switches(
    node_id: str, kinds: tuple[RowKind, ...]
) -> None:
    rows = build_inspector_rows(_view_state(), node_id)
    fields = tuple(row for row in rows if not row.command_ids and not row.divider)
    assert tuple(row.descriptor.kind for row in fields) == kinds
    assert all(row.navigable for row in rows if not row.divider)


def test_layer_page_opens_with_its_switches() -> None:
    state = _layer_view(("layer_1",))
    slot = "layer_1"
    rows = build_inspector_rows(state, layer_node_id(slot))
    assert tuple(row.descriptor for row in rows[:3]) == (
        RowDescriptor(RowKind.TRACK_ENABLED, slot=slot),
        RowDescriptor(RowKind.TRACK_SOLO, slot=slot),
        RowDescriptor(RowKind.TRACK_LOCKED, slot=slot),
    )
    for page in ("preset_switching", "compositing", "effects"):
        kinds = {
            row.descriptor.kind
            for row in build_inspector_rows(state, layer_page_node_id(slot, page))
            if row.descriptor is not None
        }
        assert not kinds & SECTION_SWITCH_KINDS


@pytest.mark.parametrize("card", ("opening_card", "closing_card"))
def test_card_pages_open_with_their_own_enabled_row(card: str) -> None:
    rows = build_inspector_rows(_view_state(), f"overlay.{card}")
    assert rows[0].descriptor == RowDescriptor(RowKind.OVERLAY_CARD_ENABLED, card=card)
    switches = [
        row
        for row in rows
        if row.descriptor is not None
        and row.descriptor.kind in SECTION_SWITCH_KINDS
    ]
    assert switches == [rows[0]]


def test_pattern_mask_page_opens_with_its_switches() -> None:
    rows = build_inspector_rows(_view_state(), "pattern_mask")
    assert tuple(row.descriptor.kind for row in rows) == (
        RowKind.PATTERN_MASK_ENABLED,
        RowKind.PATTERN_MASK_LOCKED,
    )


def test_pattern_mask_child_pages_split_the_settings() -> None:
    state = _view_state()
    state.pattern_mask.type = "plasma"
    assert _kinds(build_inspector_rows(state, "pattern_mask.pattern")) == [
        RowKind.PATTERN_MASK_TYPE,
        RowKind.PATTERN_MASK_DENSITY,
        RowKind.PATTERN_MASK_INVERT,
        RowKind.PATTERN_MASK_SEED,
    ]
    assert _kinds(build_inspector_rows(state, "pattern_mask.edges")) == [
        RowKind.PATTERN_MASK_FEATHER,
        RowKind.PATTERN_MASK_TRANSITION,
    ]


@pytest.mark.parametrize(
    "node_id",
    ("post_fx.fade", "timeline.song_markers"),
)
def test_child_pages_omit_the_root_switches(node_id: str) -> None:
    kinds = {
        row.descriptor.kind
        for row in build_inspector_rows(_view_state(), node_id)
        if row.descriptor is not None
    }
    assert not kinds & SECTION_SWITCH_KINDS


def test_settings_pages() -> None:
    state = _view_state()
    preview = build_inspector_rows(state, "settings.preview")
    assert _kinds(preview) == [
        RowKind.SETTINGS_PREVIEW_QUALITY,
        RowKind.SETTINGS_RESIDUAL_LATENCY_MS,
    ]
    assert preview[-1].command_ids == ("settings.measure_latency",)
    assert preview[-1].depth == 0
    assert _kinds(build_inspector_rows(state, "settings.ui")) == [
        RowKind.SETTINGS_UI_SCALE,
        RowKind.SETTINGS_UI_NOTIFICATION_DISPLAY,
        RowKind.SETTINGS_UI_NAVIGATOR_HEIGHT,
        RowKind.SETTINGS_NAVIGATOR_SIDE,
        RowKind.SETTINGS_HELP_SIDE,
    ]


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
    assert render[-1].command_ids == ("project.render",)


def test_page_header_is_never_a_row() -> None:
    state = _layer_view(("layer_1",))
    for node_id, header in (
        ("settings.ui", RowKind.SETTINGS_UI_HEADER),
        ("post_fx.fade", RowKind.POST_FX_FADE_HEADER),
        ("pattern_mask", RowKind.PATTERN_MASK_HEADER),
        ("overlay.opening_card", RowKind.OVERLAY_CARD_HEADER),
        (layer_node_id("layer_1"), RowKind.TRACK_HEADER),
    ):
        assert header not in _kinds(build_inspector_rows(state, node_id))


def test_headings_are_static_and_show_their_rows() -> None:
    state = _view_state()
    rows = build_inspector_rows(state, "post_fx.fade")

    assert _headings(rows) == [
        RowKind.POST_FX_FADE_IN_HEADER,
        RowKind.POST_FX_FADE_OUT_HEADER,
    ]
    assert all(not row.navigable for row in rows if row.is_heading)
    assert all(row.depth == 0 for row in rows if row.is_heading)
    assert all(row.depth == 1 for row in rows if not row.is_heading)
    assert RowKind.POST_FX_FADE_IN_START in _kinds(rows)
    assert RowKind.POST_FX_FADE_OUT_TYPE in _kinds(rows)


def test_card_page_has_headings_and_card_identity() -> None:
    state = _view_state()
    rows = build_inspector_rows(state, "overlay.opening_card")

    assert _headings(rows) == [
        RowKind.OVERLAY_CARD_ANIMATION_HEADER,
        RowKind.OVERLAY_CARD_TITLE_HEADER,
        RowKind.OVERLAY_CARD_BODY_HEADER,
    ]
    for kind in (
        RowKind.OVERLAY_CARD_POSITION,
        RowKind.OVERLAY_CARD_OPACITY,
        RowKind.OVERLAY_CARD_BORDER_COLOUR,
        RowKind.OVERLAY_CARD_TITLE_FONT,
        RowKind.OVERLAY_CARD_BODY_TEXT,
    ):
        assert kind in _kinds(rows)
    assert all(row.descriptor.card == "opening_card" for row in rows)
    closing = build_inspector_rows(state, "overlay.closing_card")
    assert all(row.descriptor.card == "closing_card" for row in closing)


def test_conditional_rows_follow_predicates() -> None:
    state = _view_state()
    assert state.pattern_mask.type != "plasma"
    assert RowKind.PATTERN_MASK_SEED not in _kinds(
        build_inspector_rows(state, "pattern_mask.pattern")
    )
    state.pattern_mask.type = "plasma"
    assert RowKind.PATTERN_MASK_SEED in _kinds(
        build_inspector_rows(state, "pattern_mask.pattern")
    )

    card = _kinds(build_inspector_rows(state, "overlay.opening_card"))
    assert state.overlays.opening_card.runtime.animation.type == "fade"
    assert RowKind.OVERLAY_CARD_ANIMATION_TYPE in card
    assert RowKind.OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION not in card

    assert state.post_fx.chroma_boost.mode == "off"
    assert _kinds(build_inspector_rows(state, "post_fx.chroma_boost")) == [
        RowKind.POST_FX_CHROMA_BOOST_MODE
    ]


def test_beat_bar_grid_page() -> None:
    rows = build_inspector_rows(_view_state(), "timeline.grid")
    assert _kinds(rows) == [
        RowKind.TIMELINE_PLACEMENT_SNAP,
        RowKind.TIMELINE_BAR_GRID,
        RowKind.TIMELINE_BAR_PHASE,
    ]
    assert rows[-1].command_ids == ("timeline.snap_cues",)


def test_timeline_page_ends_with_generate_and_reset() -> None:
    rows = build_inspector_rows(_view_state(), "timeline")
    assert rows[-1].command_ids == ("timeline.generate", "timeline.reset")
    assert all(not row.command_ids for row in rows[:-1])


def test_cue_fades_page_ends_with_set_cut_type() -> None:
    rows = build_inspector_rows(_view_state(), "timeline.cue_fades")
    assert rows[-1].command_ids == ("timeline.set_cut_type",)


def test_cue_fades_page_follows_enabled_flags() -> None:
    state = _view_state()
    assert _kinds(build_inspector_rows(state, "timeline.cue_fades")) == [
        RowKind.TIMELINE_HARD_CUTS,
        RowKind.TIMELINE_SOFT_CUTS,
    ]
    state.timeline.hard_cut_fades.enabled = True
    state.timeline.soft_cut_fades.enabled = True
    kinds = _kinds(build_inspector_rows(state, "timeline.cue_fades"))
    hard_idx = kinds.index(RowKind.TIMELINE_HARD_CUTS)
    assert kinds[hard_idx : hard_idx + 4] == [
        RowKind.TIMELINE_HARD_CUTS,
        RowKind.TIMELINE_HARD_CUT_FADE_IN,
        RowKind.TIMELINE_HARD_CUT_FADE_OUT,
        RowKind.TIMELINE_HARD_CUT_CROSSFADE,
    ]
    soft_idx = kinds.index(RowKind.TIMELINE_SOFT_CUTS)
    assert kinds[soft_idx : soft_idx + 4] == [
        RowKind.TIMELINE_SOFT_CUTS,
        RowKind.TIMELINE_SOFT_CUT_FADE_IN,
        RowKind.TIMELINE_SOFT_CUT_FADE_OUT,
        RowKind.TIMELINE_SOFT_CUT_CROSSFADE,
    ]


def test_song_markers_page_is_snap_and_marker_rows() -> None:
    state = _view_state()
    state.timeline.song_marker_times = (1.0, 4.0, 9.0)
    rows = build_inspector_rows(state, "timeline.song_markers")
    kinds = _kinds(rows)

    assert rows[-1].command_ids == ("timeline.snap_to_markers",)
    assert rows[-2].divider
    assert all(not row.command_ids for row in rows[:-1])
    markers = [
        row.descriptor
        for row in rows[:-2]
        if row.descriptor.kind is RowKind.SONG_MARKER_ITEM
    ]
    assert [desc.marker_index for desc in markers] == [0, 1, 2]
    assert all(row.depth == 0 for row in rows)


def test_locked_blocks_still_build() -> None:
    state = _view_state()
    state.overlays.locked = True
    state.post_fx.locked = True
    state.pattern_mask.locked = True

    position = next(
        row.descriptor
        for row in build_inspector_rows(state, "overlay.opening_card")
        if row.descriptor.kind is RowKind.OVERLAY_CARD_POSITION
    )
    assert inspector_field_colors(state, position) == (LOCKED, LOCKED)

    fade_start = next(
        row.descriptor
        for row in build_inspector_rows(state, "post_fx.fade")
        if row.descriptor.kind is RowKind.POST_FX_FADE_IN_START
    )
    assert inspector_field_colors(state, fade_start) == (LOCKED, LOCKED)

    density = next(
        row.descriptor
        for row in build_inspector_rows(state, "pattern_mask.pattern")
        if row.descriptor.kind is RowKind.PATTERN_MASK_DENSITY
    )
    assert inspector_field_colors(state, density) == (LOCKED, LOCKED)


def test_layer_page_keeps_direct_rows_and_delete() -> None:
    state = _layer_view(("layer_1",))
    rows = build_inspector_rows(state, layer_node_id("layer_1"))
    assert _kinds(rows) == [
        RowKind.TRACK_ENABLED,
        RowKind.TRACK_SOLO,
        RowKind.TRACK_LOCKED,
        RowKind.TRACK_STEM,
    ]
    assert rows[-1].command_ids == ("layers.delete",)
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
        state, layer_page_node_id("layer_1", "preset_list")
    )
    assert _headings(rows) == []
    items = [
        row.descriptor
        for row in rows
        if row.descriptor is not None
        and row.descriptor.kind is RowKind.TRACK_PRESET_LIST_ITEM
    ]
    assert [(desc.slot, desc.preset_index) for desc in items] == [
        ("layer_1", 0),
        ("layer_1", 1),
    ]
    assert rows[-1].command_ids == ("layers.populate_presets",)


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
    assert label == VALUE
    assert value != LOCKED
    rows = build_inspector_rows(state, layer_node_id("layer_1"))
    assert any(row.navigable and "layers.delete" in row.command_ids for row in rows)


def test_layers_root_count_and_curation_omits_add() -> None:
    state = _layer_view(("layer_1", "layer_2"))
    rows = build_inspector_rows(state, "layers")
    assert _kinds(rows) == [RowKind.LAYER_MANAGEMENT_COUNT]
    assert rows[1].divider and rows[1].navigable is False
    assert rows[2].command_ids == ("layers.add",)
    assert rows[2].navigable is True
    count = rows[0]
    assert count.navigable is False
    assert count.is_heading is False
    assert format_row_value(state, count.descriptor) == "2 of 8 layers"

    state.settings.editor_mode = "preset_curation"
    curation_rows = build_inspector_rows(state, "layers")
    assert _kinds(curation_rows) == [RowKind.LAYER_MANAGEMENT_COUNT]
    assert all("layers.add" not in row.command_ids for row in curation_rows)
    assert _kinds(build_inspector_rows(state, layer_node_id("layer_1"))) == [
        RowKind.TRACK_STEM,
        RowKind.TRACK_BEAT,
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
    ]


@pytest.mark.parametrize("page", (None, "presets"))
def test_layer_missing_from_view_state_has_no_rows(page: str | None) -> None:
    state = _layer_view(("layer_1",))
    node_id = (
        layer_node_id("layer_6")
        if page is None
        else layer_page_node_id("layer_6", page)
    )
    assert build_inspector_rows(state, node_id) == ()


@pytest.mark.parametrize(
    "node_id",
    (
        "settings.preview",
        "project.render",
        "timeline",
        "timeline.grid",
        "timeline.cue_fades",
        "timeline.song_markers",
        "layers",
    ),
)
def test_buttons_sit_at_page_bottom_under_one_divider(node_id: str) -> None:
    state = _layer_view(("layer_1",))
    state.timeline.song_marker_times = (1.0, 4.0)
    rows = build_inspector_rows(state, node_id)
    first_command = next(i for i, row in enumerate(rows) if row.command_ids)
    assert rows[first_command - 1].divider
    assert sum(row.divider for row in rows) == 1
    assert all(row.command_ids and row.depth == 0 for row in rows[first_command:])


def test_paused_switching_button_moves_below_preset_fields() -> None:
    slot = "layer_1"
    state = _layer_view((slot,), trigger="timer")
    state.tracks[slot].runtime.switching_paused = True
    rows = build_inspector_rows(
        state, layer_page_node_id(slot, LAYER_PAGE_MILKDROP_PRESET)
    )
    assert [row.command_ids for row in rows[-2:]] == [
        ("layers.add_current_preset",),
        ("layers.resume_switching",),
    ]
    assert rows[-3].divider
    assert rows[-1].status == "Switching paused"



_CUE_KINDS = [
    RowKind.TIMELINE_CUE_TIME,
    RowKind.TIMELINE_CUE_OPACITY,
    RowKind.TIMELINE_CUE_CUT,
    RowKind.TIMELINE_CUE_BLEND,
    RowKind.TIMELINE_CUE_ROLE,
]


def _cue_page(state: TuningViewState, slot: str) -> tuple[str, list[RowKind], list[str]]:
    """Heading label, shown cue row kinds, and their values."""
    rows = build_inspector_rows(state, timeline_row_node_id(slot))
    heading = next(row.descriptor for row in rows if row.is_heading)
    kinds = _kinds(rows)
    values = [format_row_value(state, RowDescriptor(k, slot=slot)) for k in kinds]
    return row_label(state, heading), kinds, values


def _cue_view() -> TuningViewState:
    state = _layer_view(("layer_1", "layer_2", "layer_3"))
    state.timeline = TimelineBlock(
        selected_cues={
            "layer_1": SlotCue(t=65.0, level=0.25, blend="add", role="lead", cut="soft"),
            "layer_2": SlotCue(t=5.0, level=0.0, cut="hard"),
        }
    )
    return state


def test_timeline_row_page_hides_cue_rows_with_no_cue_selected() -> None:
    assert _cue_page(_cue_view(), "layer_3") == ("no cue selected", [], [])


def test_timeline_row_page_shows_every_field_of_a_start_cue() -> None:
    state = _cue_view()
    assert _cue_page(state, "layer_1") == (
        "start cue",
        _CUE_KINDS,
        ["01:05", "25%", "soft", "add", "lead"],
    )
    rows = build_inspector_rows(state, timeline_row_node_id("layer_1"))
    assert all(row.descriptor.slot == "layer_1" for row in rows)
    assert all(row.navigable for row in rows if not row.is_heading)
    _label, value = inspector_field_colors(
        state, RowDescriptor(RowKind.TIMELINE_CUE_TIME, slot="layer_1")
    )
    assert value == VALUE


def test_timeline_row_page_shows_time_and_cut_of_an_end_cue() -> None:
    assert _cue_page(_cue_view(), "layer_2") == (
        "end cue",
        [RowKind.TIMELINE_CUE_TIME, RowKind.TIMELINE_CUE_CUT],
        ["00:05", "hard"],
    )


def test_timeline_cue_rows_are_unavailable_while_recording() -> None:
    state = _cue_view()
    state.timeline_recording = True
    desc = RowDescriptor(RowKind.TIMELINE_CUE_OPACITY, slot="layer_1")
    assert row_available(state, desc) is False
    _label, value = inspector_field_colors(state, desc)
    assert value == DISABLED


def test_timeline_row_page_for_a_missing_layer_is_empty() -> None:
    state = _layer_view(("layer_1",))
    assert build_inspector_rows(state, timeline_row_node_id("gone")) == ()
