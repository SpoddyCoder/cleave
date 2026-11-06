"""Tests for inspector page composition in row_sections."""

from __future__ import annotations

from cleave.effects.registry import effect_roster
from cleave.viz.inspector import build_inspector_rows
from cleave.viz.navigator import layer_node_id, layer_page_node_id
from cleave.viz.row_kinds import RowKind
from cleave.viz.row_sections import (
    OVERLAY_OPENING_CARD_SECTION,
    OVERLAY_SECTION_KINDS,
    TIMELINE_PRESETS_SECTION,
)
from cleave.viz.tuning_view_state import TrackBlock
from tests.cleave.viz.test_overlay import _minimal_view_state
from tests.support.viz import make_track_block


def _track_block(**overrides: object) -> TrackBlock:
    base = dict(
        stem="drums",
        preset_dir_label="dir",
        preset_label="preset.milk",
        blend_mode="black-key",
        opacity_pct=50,
        beat_sensitivity=1.0,
        effects={},
        preset_switching="on",
        preset_switching_trigger="timer",
        hard_cut_enabled=True,
    )
    base.update(overrides)
    return make_track_block(**base)  # type: ignore[arg-type]


def _page_kinds(node_id: str, **overrides: object) -> list[RowKind]:
    state = _minimal_view_state(tracks={"layer_1": _track_block(**overrides)})
    return [
        row.descriptor.kind
        for row in build_inspector_rows(state, node_id)
        if row.descriptor is not None
    ]


def _switching_kinds(**overrides: object) -> list[RowKind]:
    return _page_kinds(
        layer_page_node_id("layer_1", "preset_switching"), **overrides
    )


def test_layer_page_holds_only_its_own_rows() -> None:
    assert _page_kinds(layer_node_id("layer_1")) == [
        RowKind.TRACK_ENABLED,
        RowKind.TRACK_SOLO,
        RowKind.TRACK_LOCKED,
        RowKind.TRACK_STEM,
        RowKind.TRACK_BEAT,
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
    ]


def test_preset_switching_trigger_off_hides_switching_rows() -> None:
    kinds = _switching_kinds(
        preset_switching="off",
        preset_switching_trigger="off",
    )
    assert kinds == [RowKind.TRACK_PRESET_SWITCHING_TRIGGER]


def test_preset_switching_conditional_rows_when_predicates_pass() -> None:
    timer_kinds = _switching_kinds(preset_switching_trigger="timer")
    assert RowKind.TRACK_PRESET_DURATION in timer_kinds
    assert RowKind.TRACK_PRESET_START_CLEAN in timer_kinds
    assert RowKind.TRACK_PRESET_LIST in timer_kinds
    assert RowKind.TRACK_PRESET_LIST_ADD in timer_kinds
    assert RowKind.TRACK_PRESET_LIST_POPULATE in timer_kinds
    assert RowKind.TRACK_SOFT_CUT_DURATION not in timer_kinds
    assert RowKind.TRACK_HARD_CUT_ENABLED not in timer_kinds

    timeline_kinds = _switching_kinds(preset_switching_trigger="timeline")
    assert RowKind.TRACK_PRESET_DURATION not in timeline_kinds
    assert RowKind.TRACK_SOFT_CUT_DURATION not in timeline_kinds
    assert RowKind.TRACK_EASTER_EGG not in timeline_kinds
    assert RowKind.TRACK_PRESET_START_CLEAN in timeline_kinds
    assert RowKind.TRACK_PRESET_LIST_POPULATE in timeline_kinds


def test_preset_switching_hard_cut_rows_follow_hard_cut_enabled() -> None:
    hard_cut_off = _switching_kinds(
        preset_switching_trigger="projectm",
        hard_cut_enabled=False,
    )
    assert RowKind.TRACK_HARD_CUT_ENABLED in hard_cut_off
    assert RowKind.TRACK_HARD_CUT_DURATION not in hard_cut_off


def test_preset_switching_row_order() -> None:
    assert _switching_kinds(
        preset_switching_trigger="projectm",
        hard_cut_enabled=True,
        preset_list=["a.milk", "b.milk"],
    ) == [
        RowKind.TRACK_PRESET_SWITCHING_TRIGGER,
        RowKind.TRACK_PRESET_DURATION,
        RowKind.TRACK_EASTER_EGG,
        RowKind.TRACK_SOFT_CUT_DURATION,
        RowKind.TRACK_HARD_CUT_ENABLED,
        RowKind.TRACK_HARD_CUT_DURATION,
        RowKind.TRACK_HARD_CUT_SENSITIVITY,
        RowKind.TRACK_PRESET_START_CLEAN,
        RowKind.TRACK_PRESET_LIST,
        RowKind.TRACK_PRESET_LIST_ITEM,
        RowKind.TRACK_PRESET_LIST_ITEM,
        RowKind.TRACK_PRESET_LIST_ADD,
        RowKind.TRACK_PRESET_LIST_POPULATE,
    ]


def test_compositing_and_effect_pages() -> None:
    assert _page_kinds(layer_page_node_id("layer_1", "compositing")) == [
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
    ]
    assert _page_kinds(layer_page_node_id("layer_1", "effects")) == [
        RowKind.TRACK_EFFECT
    ] * len(effect_roster("drums"))


def test_overlay_section_kinds_from_tree() -> None:
    assert RowKind.OVERLAYS_HEADER in OVERLAY_SECTION_KINDS
    assert RowKind.OVERLAY_CARD_TITLE_FONT in OVERLAY_SECTION_KINDS
    assert RowKind.OVERLAY_CARD_TITLE_TEXT in OVERLAY_SECTION_KINDS
    assert RowKind.OVERLAY_CARD_TITLE_COLOUR in OVERLAY_SECTION_KINDS
    assert RowKind.OVERLAY_CARD_TITLE_BACKGROUND_COLOUR in (
        OVERLAY_SECTION_KINDS
    )
    assert RowKind.OVERLAY_CARD_BODY_FONT in OVERLAY_SECTION_KINDS
    assert RowKind.OVERLAY_CARD_BODY_TEXT in OVERLAY_SECTION_KINDS
    assert RowKind.OVERLAY_CARD_BODY_COLOUR in OVERLAY_SECTION_KINDS
    assert RowKind.OVERLAY_CARD_BODY_BACKGROUND_COLOUR in (
        OVERLAY_SECTION_KINDS
    )
    assert RowKind.OVERLAY_CARD_BACKGROUND_COLOUR in OVERLAY_SECTION_KINDS
    assert RowKind.OVERLAY_CARD_BACKGROUND_MARGIN in OVERLAY_SECTION_KINDS
    assert RowKind.OVERLAY_CARD_BACKGROUND_PADDING in OVERLAY_SECTION_KINDS
    assert RowKind.OVERLAY_CARD_BORDER_COLOUR in OVERLAY_SECTION_KINDS


def test_overlay_title_colour_follows_title_text() -> None:
    title_section = next(
        node.subsection
        for node in OVERLAY_OPENING_CARD_SECTION.children
        if node.subsection is not None
        and node.subsection.header_kind == RowKind.OVERLAY_CARD_TITLE_HEADER
    )
    assert title_section.children[0].leaf_kind == RowKind.OVERLAY_CARD_TITLE_TEXT
    assert title_section.children[1].leaf_kind == (
        RowKind.OVERLAY_CARD_TITLE_COLOUR
    )
    assert title_section.children[2].leaf_kind == (
        RowKind.OVERLAY_CARD_TITLE_BACKGROUND_COLOUR
    )


def test_overlay_body_colour_follows_body_text() -> None:
    body_section = next(
        node.subsection
        for node in OVERLAY_OPENING_CARD_SECTION.children
        if node.subsection is not None
        and node.subsection.header_kind == RowKind.OVERLAY_CARD_BODY_HEADER
    )
    assert body_section.children[0].leaf_kind == RowKind.OVERLAY_CARD_BODY_TEXT
    assert body_section.children[1].leaf_kind == RowKind.OVERLAY_CARD_BODY_COLOUR
    assert body_section.children[2].leaf_kind == (
        RowKind.OVERLAY_CARD_BODY_BACKGROUND_COLOUR
    )


def test_overlay_card_colours_follow_opacity_and_border() -> None:
    leaf_kinds = [
        child.leaf_kind for child in OVERLAY_OPENING_CARD_SECTION.children
    ]
    opacity = leaf_kinds.index(RowKind.OVERLAY_CARD_OPACITY)
    background = leaf_kinds.index(RowKind.OVERLAY_CARD_BACKGROUND_COLOUR)
    margin = leaf_kinds.index(RowKind.OVERLAY_CARD_BACKGROUND_MARGIN)
    padding = leaf_kinds.index(RowKind.OVERLAY_CARD_BACKGROUND_PADDING)
    border_width = leaf_kinds.index(RowKind.OVERLAY_CARD_BORDER_WIDTH)
    border_colour = leaf_kinds.index(RowKind.OVERLAY_CARD_BORDER_COLOUR)
    assert opacity < background < margin < padding < border_width < border_colour


def test_overlay_body_text_is_first_body_child() -> None:
    body_section = next(
        node.subsection
        for node in OVERLAY_OPENING_CARD_SECTION.children
        if node.subsection is not None
        and node.subsection.header_kind == RowKind.OVERLAY_CARD_BODY_HEADER
    )
    assert body_section.children[0].leaf_kind == RowKind.OVERLAY_CARD_BODY_TEXT


def test_timeline_reset_follows_presets_section() -> None:
    leaves = tuple(
        child.leaf_kind
        for child in TIMELINE_PRESETS_SECTION.children
        if child.leaf_kind is not None
    )
    assert leaves[-2:] == (RowKind.TIMELINE_PRESETS, RowKind.TIMELINE_RESET)
