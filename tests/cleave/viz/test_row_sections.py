"""Tests for expandable section composition in row_sections."""

from __future__ import annotations

from cleave.effects.registry import effect_roster
from cleave.viz.row_sections import (
    RENDER_OVERLAYS_SECTION,
    RENDER_OVERLAY_OPENING_CARD_SECTION,
    RENDER_OVERLAY_SECTION_KINDS,
    RENDER_POST_FX_SECTION,
    TRACK_SECTION,
    append_expand_section_rows,
    expand_section_expanded,
    section_header_from_section_tree,
    sub_row_expand_visible,
)
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import section_header_descriptor
from cleave.viz.tuning_view_state import (
    RenderOverlaysBlock,
    RenderPostFxBlock,
    SettingsBlock,
    TrackBlock,
)
from tests.cleave.viz.test_overlay import _minimal_view_state
from tests.support.viz import make_overlay_card_block, make_track_block


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


def _track_row_kinds(**overrides: object) -> list[RowKind]:
    state = _minimal_view_state(tracks={"layer_1": _track_block(**overrides)})
    rows: list[RowDescriptor] = []
    append_expand_section_rows(rows, TRACK_SECTION, state, "layer_1")
    return [row.kind for row in rows]


def test_track_layout_trigger_off_hides_switching_rows() -> None:
    kinds = _track_row_kinds(
        preset_switching="off",
        preset_switching_trigger="off",
    )
    assert RowKind.TRACK_PRESET_SWITCHING in kinds
    assert RowKind.TRACK_PRESET_SWITCHING_TRIGGER in kinds
    assert RowKind.TRACK_PRESET_DURATION not in kinds
    assert RowKind.TRACK_PRESET_START_CLEAN not in kinds
    assert RowKind.TRACK_PRESET_LIST not in kinds


def test_track_layout_conditional_rows_when_predicates_pass() -> None:
    timer_kinds = _track_row_kinds(
        preset_switching="on",
        preset_switching_trigger="timer",
    )
    assert RowKind.TRACK_PRESET_DURATION in timer_kinds
    assert RowKind.TRACK_PRESET_SWITCHING_TRIGGER in timer_kinds
    assert RowKind.TRACK_PRESET_START_CLEAN in timer_kinds
    assert RowKind.TRACK_PRESET_LIST in timer_kinds
    assert RowKind.TRACK_PRESET_LIST_ADD in timer_kinds
    assert RowKind.TRACK_PRESET_LIST_POPULATE in timer_kinds
    assert RowKind.TRACK_SOFT_CUT_DURATION not in timer_kinds
    assert RowKind.TRACK_HARD_CUT_ENABLED not in timer_kinds

    projectm_kinds = _track_row_kinds(
        preset_switching="on",
        preset_switching_trigger="projectm",
        hard_cut_enabled=True,
    )
    assert RowKind.TRACK_PRESET_DURATION in projectm_kinds
    assert RowKind.TRACK_SOFT_CUT_DURATION in projectm_kinds
    assert RowKind.TRACK_EASTER_EGG in projectm_kinds
    assert RowKind.TRACK_HARD_CUT_ENABLED in projectm_kinds
    assert RowKind.TRACK_HARD_CUT_DURATION in projectm_kinds
    assert RowKind.TRACK_HARD_CUT_SENSITIVITY in projectm_kinds
    assert RowKind.TRACK_PRESET_LIST in projectm_kinds

    timeline_kinds = _track_row_kinds(
        preset_switching="on",
        preset_switching_trigger="timeline",
    )
    assert RowKind.TRACK_PRESET_SWITCHING_TRIGGER in timeline_kinds
    assert RowKind.TRACK_PRESET_DURATION not in timeline_kinds
    assert RowKind.TRACK_SOFT_CUT_DURATION not in timeline_kinds
    assert RowKind.TRACK_EASTER_EGG not in timeline_kinds
    assert RowKind.TRACK_HARD_CUT_ENABLED not in timeline_kinds
    assert RowKind.TRACK_PRESET_START_CLEAN in timeline_kinds
    assert RowKind.TRACK_PRESET_LIST in timeline_kinds
    assert RowKind.TRACK_PRESET_LIST_POPULATE in timeline_kinds
    assert RowKind.TRACK_PRESET_LIST_ADD in timeline_kinds


def test_track_layout_omits_conditional_rows_when_predicates_fail() -> None:
    none_kinds = _track_row_kinds(
        preset_switching="off",
        preset_switching_trigger="off",
    )
    assert RowKind.TRACK_PRESET_DURATION not in none_kinds
    assert RowKind.TRACK_PRESET_LIST not in none_kinds
    assert RowKind.TRACK_PRESET_SWITCHING_TRIGGER in none_kinds
    assert RowKind.TRACK_PRESET_LIST_POPULATE not in none_kinds

    hard_cut_off = _track_row_kinds(
        preset_switching="on",
        preset_switching_trigger="projectm",
        hard_cut_enabled=False,
    )
    assert RowKind.TRACK_HARD_CUT_DURATION not in hard_cut_off
    assert RowKind.TRACK_HARD_CUT_ENABLED in hard_cut_off


def test_track_layout_effect_roster_when_expanded() -> None:
    kinds = _track_row_kinds()
    effect_rows = [kind for kind in kinds if kind == RowKind.TRACK_EFFECT]
    assert len(effect_rows) == len(effect_roster("drums"))


def test_track_layout_row_order_when_fully_expanded() -> None:
    kinds = _track_row_kinds(
        preset_switching_trigger="projectm",
        hard_cut_enabled=True,
        preset_list=["a.milk", "b.milk"],
    )
    effects_header = kinds.index(RowKind.TRACK_EFFECTS_HEADER)
    delete_idx = kinds.index(RowKind.LAYER_MANAGEMENT_DELETE)
    assert effects_header < delete_idx
    assert kinds[:effects_header + 1] == [
        RowKind.TRACK_HEADER,
        RowKind.TRACK_STEM,
        RowKind.TRACK_BEAT,
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_PRESET_SWITCHING,
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
        RowKind.TRACK_COMPOSITING_HEADER,
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
        RowKind.TRACK_EFFECTS_HEADER,
    ]
    assert kinds[delete_idx] == RowKind.LAYER_MANAGEMENT_DELETE
    assert all(kind == RowKind.TRACK_EFFECT for kind in kinds[effects_header + 1 : delete_idx])

def test_expand_section_respects_expanded_when_block_disabled() -> None:
    disabled_overlay = _minimal_view_state(
        render_overlays=RenderOverlaysBlock(
            opening_card=make_overlay_card_block(enabled=False)),
    )
    assert expand_section_expanded(disabled_overlay, RENDER_OVERLAYS_SECTION, None) is True
    opacity = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_OPACITY)
    assert sub_row_expand_visible(disabled_overlay, opacity) is True

    disabled_post_fx = _minimal_view_state(
        render_post_fx=RenderPostFxBlock(enabled=False),
    )
    assert expand_section_expanded(disabled_post_fx, RENDER_POST_FX_SECTION, None) is True


def test_sub_row_expand_visible_nested_sections() -> None:
    state = _minimal_view_state()
    opacity = RowDescriptor(
        RowKind.RENDER_OVERLAY_CARD_OPACITY, card="opening_card"
    )
    assert sub_row_expand_visible(state, opacity) is True
    title_font = RowDescriptor(
        RowKind.RENDER_OVERLAY_CARD_TITLE_FONT, card="opening_card"
    )
    assert sub_row_expand_visible(state, title_font) is True
    fade_start = RowDescriptor(RowKind.RENDER_POST_FX_FADE_IN_START)
    assert sub_row_expand_visible(state, fade_start) is True
    threshold = RowDescriptor(RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD)
    assert sub_row_expand_visible(state, threshold) is True


def test_section_omits_conditional_rows_when_predicate_fails() -> None:
    none_kinds = _track_row_kinds(
        preset_switching="off",
        preset_switching_trigger="off",
    )
    assert RowKind.TRACK_PRESET_DURATION not in none_kinds

    hard_cut_off = _track_row_kinds(
        preset_switching="on",
        preset_switching_trigger="projectm",
        hard_cut_enabled=False,
    )
    assert RowKind.TRACK_HARD_CUT_DURATION not in hard_cut_off


def test_section_includes_conditional_rows_when_predicates_pass() -> None:
    projectm_kinds = _track_row_kinds(
        preset_switching="on",
        preset_switching_trigger="projectm",
        hard_cut_enabled=True,
    )
    assert RowKind.TRACK_PRESET_DURATION in projectm_kinds
    assert RowKind.TRACK_HARD_CUT_DURATION in projectm_kinds


def test_section_header_from_tree_preset_switching_submenu() -> None:
    trigger = RowDescriptor(
        RowKind.TRACK_PRESET_SWITCHING_TRIGGER, slot="layer_1"
    )
    assert section_header_from_section_tree(trigger) == RowDescriptor(
        RowKind.TRACK_PRESET_SWITCHING, slot="layer_1"
    )
    hard_cut = RowDescriptor(RowKind.TRACK_HARD_CUT_SENSITIVITY, slot="layer_1")
    assert section_header_from_section_tree(hard_cut) == RowDescriptor(
        RowKind.TRACK_PRESET_SWITCHING, slot="layer_1"
    )
    resume = RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_RESUME, slot="layer_1")
    assert section_header_from_section_tree(resume) == RowDescriptor(
        RowKind.TRACK_PRESET_SWITCHING, slot="layer_1"
    )


def test_section_header_descriptor_uses_tree_and_effect_fallback() -> None:
    assert section_header_descriptor(
        RowDescriptor(RowKind.TRACK_PRESET_DURATION, slot="layer_1")
    ) == RowDescriptor(RowKind.TRACK_PRESET_SWITCHING, slot="layer_1")
    assert section_header_descriptor(
        RowDescriptor(
            RowKind.TRACK_EFFECT, slot="layer_1", effect_id="pulse", driver_slug="onset"
        )
    ) == RowDescriptor(RowKind.TRACK_EFFECTS_HEADER, slot="layer_1")
    assert section_header_descriptor(
        RowDescriptor(RowKind.TRACK_BLEND, slot="layer_1")
    ) == RowDescriptor(RowKind.TRACK_COMPOSITING_HEADER, slot="layer_1")
    assert section_header_descriptor(
        RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")
    ) == RowDescriptor(RowKind.TRACK_COMPOSITING_HEADER, slot="layer_1")
    assert section_header_descriptor(
        RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_FONT)
    ) == RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER)
    assert section_header_descriptor(
        RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_COLOUR)
    ) == RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER)
    assert section_header_descriptor(
        RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_BACKGROUND_COLOUR)
    ) == RowDescriptor(RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER)
    assert section_header_descriptor(
        RowDescriptor(RowKind.SETTINGS_UI_FADE)
    ) == RowDescriptor(RowKind.SETTINGS_UI_HEADER)
    assert section_header_descriptor(
        RowDescriptor(RowKind.SETTINGS_UI_NOTIFICATION_DISPLAY)
    ) == RowDescriptor(RowKind.SETTINGS_UI_HEADER)
    assert section_header_descriptor(
        RowDescriptor(RowKind.SETTINGS_EDITOR_WINDOW_WIDTH)
    ) == RowDescriptor(RowKind.SETTINGS_EDITOR_WINDOW_HEADER)


def test_render_overlay_section_kinds_from_tree() -> None:
    assert RowKind.RENDER_OVERLAYS_HEADER in RENDER_OVERLAY_SECTION_KINDS
    assert RowKind.RENDER_OVERLAY_CARD_TITLE_FONT in RENDER_OVERLAY_SECTION_KINDS
    assert RowKind.RENDER_OVERLAY_CARD_TITLE_TEXT in RENDER_OVERLAY_SECTION_KINDS
    assert RowKind.RENDER_OVERLAY_CARD_TITLE_COLOUR in RENDER_OVERLAY_SECTION_KINDS
    assert RowKind.RENDER_OVERLAY_CARD_TITLE_BACKGROUND_COLOUR in (
        RENDER_OVERLAY_SECTION_KINDS
    )
    assert RowKind.RENDER_OVERLAY_CARD_BODY_FONT in RENDER_OVERLAY_SECTION_KINDS
    assert RowKind.RENDER_OVERLAY_CARD_BODY_TEXT in RENDER_OVERLAY_SECTION_KINDS
    assert RowKind.RENDER_OVERLAY_CARD_BODY_COLOUR in RENDER_OVERLAY_SECTION_KINDS
    assert RowKind.RENDER_OVERLAY_CARD_BODY_BACKGROUND_COLOUR in (
        RENDER_OVERLAY_SECTION_KINDS
    )
    assert RowKind.RENDER_OVERLAY_CARD_BACKGROUND_COLOUR in RENDER_OVERLAY_SECTION_KINDS
    assert RowKind.RENDER_OVERLAY_CARD_BACKGROUND_MARGIN in RENDER_OVERLAY_SECTION_KINDS
    assert RowKind.RENDER_OVERLAY_CARD_BACKGROUND_PADDING in RENDER_OVERLAY_SECTION_KINDS
    assert RowKind.RENDER_OVERLAY_CARD_BORDER_COLOUR in RENDER_OVERLAY_SECTION_KINDS


def test_render_overlay_title_colour_follows_title_text() -> None:
    title_section = next(
        node.expand
        for node in RENDER_OVERLAY_OPENING_CARD_SECTION.children
        if node.expand is not None
        and node.expand.header_kind == RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER
    )
    assert title_section.children[0].leaf_kind == RowKind.RENDER_OVERLAY_CARD_TITLE_TEXT
    assert title_section.children[1].leaf_kind == (
        RowKind.RENDER_OVERLAY_CARD_TITLE_COLOUR
    )
    assert title_section.children[2].leaf_kind == (
        RowKind.RENDER_OVERLAY_CARD_TITLE_BACKGROUND_COLOUR
    )


def test_render_overlay_body_colour_follows_body_text() -> None:
    body_section = next(
        node.expand
        for node in RENDER_OVERLAY_OPENING_CARD_SECTION.children
        if node.expand is not None
        and node.expand.header_kind == RowKind.RENDER_OVERLAY_CARD_BODY_HEADER
    )
    assert body_section.children[0].leaf_kind == RowKind.RENDER_OVERLAY_CARD_BODY_TEXT
    assert body_section.children[1].leaf_kind == RowKind.RENDER_OVERLAY_CARD_BODY_COLOUR
    assert body_section.children[2].leaf_kind == (
        RowKind.RENDER_OVERLAY_CARD_BODY_BACKGROUND_COLOUR
    )


def test_render_overlay_card_colours_follow_opacity_and_border() -> None:
    leaf_kinds = [
        child.leaf_kind for child in RENDER_OVERLAY_OPENING_CARD_SECTION.children
    ]
    opacity = leaf_kinds.index(RowKind.RENDER_OVERLAY_CARD_OPACITY)
    background = leaf_kinds.index(RowKind.RENDER_OVERLAY_CARD_BACKGROUND_COLOUR)
    margin = leaf_kinds.index(RowKind.RENDER_OVERLAY_CARD_BACKGROUND_MARGIN)
    padding = leaf_kinds.index(RowKind.RENDER_OVERLAY_CARD_BACKGROUND_PADDING)
    border_width = leaf_kinds.index(RowKind.RENDER_OVERLAY_CARD_BORDER_WIDTH)
    border_colour = leaf_kinds.index(RowKind.RENDER_OVERLAY_CARD_BORDER_COLOUR)
    assert opacity < background < margin < padding < border_width < border_colour


def test_render_overlay_body_text_is_first_body_child() -> None:
    body_section = next(
        node.expand
        for node in RENDER_OVERLAY_OPENING_CARD_SECTION.children
        if node.expand is not None
        and node.expand.header_kind == RowKind.RENDER_OVERLAY_CARD_BODY_HEADER
    )
    assert body_section.children[0].leaf_kind == RowKind.RENDER_OVERLAY_CARD_BODY_TEXT
