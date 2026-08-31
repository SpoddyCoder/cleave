"""Tests for the unified RowSpec panel registry."""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import pygame

from cleave.config_schema.editor import ui_fade_display
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import (
    ACTION_ROW_KINDS,
    HEADER_ROW_KINDS,
    LABELED_SUB_ROW_KINDS,
    REPEAT_ROW_KINDS,
    ROW_SPECS,
    TRACK_EFFECT_SUB_ROW_KINDS,
    TRACK_SUB_ROW_KINDS,
    RowPresentStyle,
    apply_field_horizontal,
    composite_header_prefix_part,
    composite_header_suffix_part,
    expand_subheader_prefix,
    expandable_row_kinds,
    format_row_value,
    full_line_prefix,
    labeled_row_prefix,
    row_blocked_by_section_lock,
    row_composite_header_display_text,
    row_dynamic_labeled_display_text,
    row_dynamic_labeled_prefix,
    row_expand_subheader_display_text,
    row_is_pinned,
    row_labeled_display_text,
    row_navigable_when_section_locked,
    row_panel_label,
    row_spec,
    row_triggers_layer_delete,
    section_lock_blocks_mutation,
    section_locked,
    tree_branch_leading_spaces,
    tree_branch_prefix,
)
from cleave.viz.tuning_view_state import (
    RenderOverlaysBlock,
    RenderPostFxBlock,
    SettingsBlock,
)
from tests.cleave.viz.test_controls import (
    _keydown,
    _make_controls,
    _make_controls_with_manager,
)
from tests.cleave.viz.test_overlay import _minimal_view_state
from tests.support.config import TEST_LAYER_STEMS
from tests.support.viz import make_overlay_card_block, make_track_block, noop_layer_bindings


def _track_lock_state(locked: bool) -> SimpleNamespace:
    return SimpleNamespace(tracks={"layer_1": SimpleNamespace(locked=locked)})

_EXPECTED_REPEAT_ROW_KINDS = frozenset(
    {
        RowKind.TRANSPORT,
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_PRESET_SWITCHING,
        RowKind.TRACK_PRESET_SWITCHING_TRIGGER,
                        RowKind.TRACK_PRESET_DURATION,
        RowKind.TRACK_SOFT_CUT_DURATION,
        RowKind.TRACK_EASTER_EGG,
        RowKind.TRACK_PRESET_START_CLEAN,
                RowKind.TRACK_HARD_CUT_ENABLED,
        RowKind.TRACK_HARD_CUT_DURATION,
        RowKind.TRACK_HARD_CUT_SENSITIVITY,
        RowKind.TRACK_STEM,
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
        RowKind.TRACK_BEAT,
        RowKind.TRACK_EFFECT,
        RowKind.RENDER_OVERLAY_CARD_POSITION,
        RowKind.RENDER_OVERLAY_CARD_ANIMATION_TYPE,
        RowKind.RENDER_OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION,
        RowKind.RENDER_OVERLAY_CARD_TITLE_FONT_SIZE,
        RowKind.RENDER_OVERLAY_CARD_TITLE_FONT,
        RowKind.RENDER_OVERLAY_CARD_TITLE_MARGIN_BOTTOM,
        RowKind.RENDER_OVERLAY_CARD_BODY_FONT_SIZE,
        RowKind.RENDER_OVERLAY_CARD_BODY_FONT,
        RowKind.RENDER_OVERLAY_CARD_OPACITY,
        RowKind.RENDER_OVERLAY_CARD_BORDER_WIDTH,
        RowKind.RENDER_OVERLAY_CARD_TIME,
        RowKind.RENDER_OVERLAY_CARD_DISPLAY_TIME,
        RowKind.RENDER_POST_FX_FADE_IN,
        RowKind.RENDER_POST_FX_FADE_OUT,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_MODE,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CURVE,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CEILING,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_STRENGTH,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_SOFTNESS,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_DESATURATION,
        RowKind.RENDER_POST_FX_CHROMA_BOOST_MODE,
        RowKind.RENDER_POST_FX_CHROMA_BOOST_VARIANT,
        RowKind.RENDER_POST_FX_CHROMA_BOOST_AMOUNT,
        RowKind.RENDER_PATTERN_MASK_TYPE,
        RowKind.RENDER_PATTERN_MASK_DENSITY,
        RowKind.RENDER_PATTERN_MASK_FEATHER,
        RowKind.RENDER_PATTERN_MASK_INVERT,
        RowKind.RENDER_PATTERN_MASK_TRANSITION,
        RowKind.RENDER_PATTERN_MASK_SEED,
        RowKind.SETTINGS_PREVIEW_QUALITY,
        RowKind.SETTINGS_EDITOR_MODE,
        RowKind.SETTINGS_UI_WIDTH_MODE,
        RowKind.SETTINGS_UI_WIDTH,
        RowKind.SETTINGS_UI_FADE,
        RowKind.SETTINGS_RESIDUAL_LATENCY_MS,
        RowKind.TIMELINE_BAR_PHASE,
        RowKind.TIMELINE_HARD_CUTS,
        RowKind.TIMELINE_HARD_CUT_FADE_IN,
        RowKind.TIMELINE_HARD_CUT_FADE_OUT,
        RowKind.TIMELINE_HARD_CUT_CROSSFADE,
        RowKind.TIMELINE_SOFT_CUTS,
        RowKind.TIMELINE_SOFT_CUT_FADE_IN,
        RowKind.TIMELINE_SOFT_CUT_FADE_OUT,
        RowKind.TIMELINE_SOFT_CUT_CROSSFADE,
        RowKind.TIMELINE_VISUAL_LIMITER_THRESHOLD,
        RowKind.TIMELINE_VISUAL_LIMITER_RATIO,
        RowKind.TIMELINE_VISUAL_LIMITER_RELEASE,
    }
)


def test_every_row_kind_has_spec() -> None:
    for kind in RowKind:
        assert kind in ROW_SPECS
        assert row_spec(kind) is ROW_SPECS[kind]


def test_header_row_kinds() -> None:
    assert HEADER_ROW_KINDS == frozenset(
        {
            RowKind.TRANSPORT,
            RowKind.CONFIG_HEADER,
            RowKind.SETTINGS_HEADER,
        }
    )


def test_action_row_kinds_match_affordance() -> None:
    assert ACTION_ROW_KINDS == frozenset(
        k for k, b in ROW_SPECS.items() if b.affordance == RowAffordance.ACTION
    )
    assert RowKind.LAYER_MANAGEMENT_ADD in ACTION_ROW_KINDS
    assert RowKind.CONFIG_HEADER in ACTION_ROW_KINDS
    assert RowKind.SETTINGS_EDITOR_MODE not in ACTION_ROW_KINDS


def test_row_is_pinned() -> None:
    assert row_is_pinned(RowKind.TRANSPORT) is True
    assert row_is_pinned(RowKind.CONFIG_HEADER) is True
    assert row_is_pinned(RowKind.SETTINGS_HEADER) is True
    assert row_is_pinned(RowKind.SETTINGS_PREVIEW_QUALITY) is True
    assert row_is_pinned(RowKind.SETTINGS_EDITOR_MODE) is True
    assert row_is_pinned(RowKind.SETTINGS_UI_HEADER) is True
    assert row_is_pinned(RowKind.SETTINGS_UI_FADE) is True
    assert row_is_pinned(RowKind.SETTINGS_UI_WIDTH_MODE) is True
    assert row_is_pinned(RowKind.SETTINGS_UI_WIDTH) is True
    assert row_is_pinned(RowKind.TRACK_HEADER) is False
    assert row_is_pinned(RowKind.RENDER_OVERLAYS_HEADER) is False


def test_repeat_row_kinds() -> None:
    assert REPEAT_ROW_KINDS == _EXPECTED_REPEAT_ROW_KINDS


def test_render_overlay_sub_headers_expand() -> None:
    title = row_spec(RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER)
    body = row_spec(RowKind.RENDER_OVERLAY_CARD_BODY_HEADER)
    assert title.affordance == RowAffordance.EXPAND
    assert title.is_sub_header is True
    assert body.affordance == RowAffordance.EXPAND
    assert body.is_sub_header is True


def test_track_effects_header_expands() -> None:
    behavior = row_spec(RowKind.TRACK_EFFECTS_HEADER)
    assert behavior.affordance == RowAffordance.EXPAND


def test_expandable_row_kinds() -> None:
    assert expandable_row_kinds() == frozenset(
        k for k, b in ROW_SPECS.items() if b.affordance == RowAffordance.EXPAND
    )


def test_parent_group_on_row_specs() -> None:
    assert row_spec(RowKind.TRACK_STEM).parent_group == "track"
    assert row_spec(RowKind.RENDER_OVERLAY_CARD_POSITION).parent_group == (
        "render_overlay"
    )
    assert row_spec(RowKind.RENDER_OVERLAY_CARD_TITLE_FONT).parent_group == (
        "render_overlay_title"
    )
    assert row_spec(RowKind.RENDER_OVERLAY_CARD_BODY_FONT).parent_group == (
        "render_overlay_body"
    )
    assert row_spec(RowKind.RENDER_POST_FX_FADE_IN).parent_group == "render_post_fx"
    assert row_spec(RowKind.SETTINGS_PREVIEW_QUALITY).parent_group == "settings"
    assert row_spec(RowKind.SETTINGS_UI_WIDTH_MODE).parent_group == "settings_ui"


def test_track_sub_row_kinds() -> None:
    assert TRACK_SUB_ROW_KINDS == frozenset(
        {
            RowKind.TRACK_PRESET_DIR,
            RowKind.TRACK_PRESET,
            RowKind.TRACK_PRESET_SWITCHING,
            RowKind.TRACK_PRESET_SWITCHING_TRIGGER,
            RowKind.TRACK_PRESET_LIST,
            RowKind.TRACK_PRESET_LIST_ITEM,
            RowKind.TRACK_PRESET_LIST_ADD,
            RowKind.TRACK_PRESET_LIST_POPULATE,
            RowKind.TRACK_PRESET_DURATION,
            RowKind.TRACK_SOFT_CUT_DURATION,
            RowKind.TRACK_EASTER_EGG,
            RowKind.TRACK_PRESET_START_CLEAN,
            RowKind.TRACK_HARD_CUT_ENABLED,
            RowKind.TRACK_HARD_CUT_DURATION,
            RowKind.TRACK_HARD_CUT_SENSITIVITY,
            RowKind.TRACK_STEM,
            RowKind.TRACK_BLEND,
            RowKind.TRACK_OPACITY,
            RowKind.TRACK_BEAT,
            RowKind.TRACK_EFFECTS_HEADER,
            RowKind.TRACK_EFFECT,
            RowKind.LAYER_MANAGEMENT_DELETE,
        }
    )


def test_track_effect_sub_row_kinds() -> None:
    assert TRACK_EFFECT_SUB_ROW_KINDS == frozenset({RowKind.TRACK_EFFECT})


def test_locked_navigable_sub_row_kinds() -> None:
    navigable = frozenset(
        k for k in TRACK_SUB_ROW_KINDS if row_navigable_when_section_locked(k)
    )
    assert navigable == frozenset(
        {
            RowKind.TRACK_PRESET_LIST,
            RowKind.TRACK_EFFECTS_HEADER,
            RowKind.LAYER_MANAGEMENT_DELETE,
        }
    )


def test_track_value_rows_blocked_by_section_lock() -> None:
    blocked = frozenset(
        k for k in TRACK_SUB_ROW_KINDS if row_blocked_by_section_lock(k)
    )
    assert blocked == frozenset(
        {
            RowKind.TRACK_PRESET_DIR,
            RowKind.TRACK_PRESET,
            RowKind.TRACK_PRESET_SWITCHING,
            RowKind.TRACK_PRESET_SWITCHING_TRIGGER,
            RowKind.TRACK_PRESET_DURATION,
            RowKind.TRACK_SOFT_CUT_DURATION,
            RowKind.TRACK_EASTER_EGG,
            RowKind.TRACK_PRESET_START_CLEAN,
            RowKind.TRACK_HARD_CUT_ENABLED,
            RowKind.TRACK_HARD_CUT_DURATION,
            RowKind.TRACK_HARD_CUT_SENSITIVITY,
            RowKind.TRACK_STEM,
            RowKind.TRACK_BLEND,
            RowKind.TRACK_OPACITY,
            RowKind.TRACK_BEAT,
            RowKind.TRACK_EFFECT,
            RowKind.TRACK_PRESET_LIST_ITEM,
            RowKind.TRACK_PRESET_LIST_ADD,
            RowKind.TRACK_PRESET_LIST_POPULATE,
        }
    )
    for kind in blocked:
        desc = RowDescriptor(kind, slot="layer_1")
        assert section_lock_blocks_mutation(_track_lock_state(True), desc) is True
        assert section_lock_blocks_mutation(_track_lock_state(False), desc) is False


def test_only_effects_header_navigable_when_section_locked() -> None:
    navigable_when_locked = {
        RowKind.TRACK_PRESET_LIST,
        RowKind.TRACK_EFFECTS_HEADER,
        RowKind.LAYER_MANAGEMENT_DELETE,
    }
    for kind in TRACK_SUB_ROW_KINDS:
        assert row_navigable_when_section_locked(kind) == (kind in navigable_when_locked)


def test_labeled_sub_row_kinds_exclude_headers() -> None:
    assert LABELED_SUB_ROW_KINDS.isdisjoint(HEADER_ROW_KINDS)
    for kind in LABELED_SUB_ROW_KINDS:
        behavior = row_spec(kind)
        assert behavior.affordance in {
            RowAffordance.VALUE_STEP,
            RowAffordance.PATH_DIR,
            RowAffordance.PATH_PRESET,
        }
        assert not behavior.is_header


def test_preset_list_actions_are_action_rows() -> None:
    for kind in (
        RowKind.TRACK_PRESET_LIST_POPULATE,
        RowKind.TRACK_PRESET_LIST_ADD,
    ):
        assert kind in ACTION_ROW_KINDS
        assert kind not in LABELED_SUB_ROW_KINDS
        assert row_spec(kind).affordance == RowAffordance.ACTION


def _render_lock_state(
    *, overlay: bool = False, post_fx: bool = False, timeline: bool = False
) -> SimpleNamespace:
    return SimpleNamespace(
        render_overlays=SimpleNamespace(locked=overlay),
        render_post_fx=SimpleNamespace(locked=post_fx),
        render_timeline=SimpleNamespace(locked=timeline),
    )


def test_render_value_children_blocked_by_section_lock() -> None:
    assert row_blocked_by_section_lock(RowKind.RENDER_OVERLAY_CARD_POSITION) is True
    assert row_blocked_by_section_lock(RowKind.RENDER_OVERLAY_CARD_TITLE_FONT) is True
    assert row_blocked_by_section_lock(RowKind.RENDER_POST_FX_FADE_IN) is True
    assert row_blocked_by_section_lock(RowKind.RENDER_POST_FX_CHROMA_BOOST_AMOUNT) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_PRESETS) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_PRESET_CHARACTER) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_PRESET_DENSITY) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_PRESET_CUE_SNAP) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_PRESET_SONG_MARKER_SNAP) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_PRESET_TIMELINE_CUTS) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_PRESET_REPOPULATE) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_PRESET_CONDUCTOR) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_PRESET_MODE) is True
    assert row_blocked_by_section_lock(RowKind.TRACK_PRESET_LIST_POPULATE) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_BAR_PHASE) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_SNAP_TO_BEATS) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_SNAP_TO_BARS) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_SNAP_TO_SONG_MARKERS) is True
    assert row_blocked_by_section_lock(RowKind.SONG_MARKER_ITEM) is True
    assert row_blocked_by_section_lock(RowKind.SONG_MARKERS_HEADER) is False
    assert row_blocked_by_section_lock(RowKind.TIMELINE_SNAP_CUES_HEADER) is False
    assert row_blocked_by_section_lock(RowKind.TIMELINE_PRESETS_HEADER) is False


def test_render_headers_navigable_when_section_locked() -> None:
    for kind in (
        RowKind.RENDER_OVERLAYS_HEADER,
        RowKind.RENDER_POST_FX_HEADER,
        RowKind.RENDER_TIMELINE_HEADER,
        RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER,
        RowKind.RENDER_POST_FX_CHROMA_BOOST_HEADER,
        RowKind.SONG_MARKERS_HEADER,
        RowKind.TIMELINE_SNAP_CUES_HEADER,
        RowKind.TIMELINE_PRESETS_HEADER,
    ):
        assert row_navigable_when_section_locked(kind) is True
    assert row_navigable_when_section_locked(RowKind.RENDER_OVERLAY_CARD_POSITION) is False
    assert row_navigable_when_section_locked(RowKind.TIMELINE_PRESETS) is False
    assert row_navigable_when_section_locked(RowKind.TIMELINE_PRESET_CHARACTER) is False
    assert row_navigable_when_section_locked(RowKind.TIMELINE_SNAP_TO_SONG_MARKERS) is False
    assert row_navigable_when_section_locked(RowKind.SONG_MARKER_ITEM) is False


def test_section_locked_resolves_render_sections() -> None:
    overlay_desc = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_POSITION)
    post_fx_desc = RowDescriptor(RowKind.RENDER_POST_FX_FADE_IN)
    timeline_desc = RowDescriptor(RowKind.TIMELINE_PRESETS)
    assert section_locked(_render_lock_state(overlay=True), overlay_desc) is True
    assert section_locked(_render_lock_state(), overlay_desc) is False
    assert section_locked(_render_lock_state(post_fx=True), post_fx_desc) is True
    assert section_locked(_render_lock_state(timeline=True), timeline_desc) is True


def test_section_locked_reads_session_timeline_attribute() -> None:
    session_like = SimpleNamespace(
        render_overlays=SimpleNamespace(locked=False),
        render_post_fx=SimpleNamespace(locked=False),
        timeline=SimpleNamespace(locked=True),
    )
    assert section_locked(session_like, RowDescriptor(RowKind.TIMELINE_PRESETS)) is True


def test_section_locked_ignored_in_preset_curation() -> None:
    state = SimpleNamespace(
        settings=SimpleNamespace(editor_mode="preset_curation"),
        tracks={"layer_1": SimpleNamespace(locked=True)},
        render_overlays=SimpleNamespace(locked=True),
        render_post_fx=SimpleNamespace(locked=True),
        render_timeline=SimpleNamespace(locked=True),
    )
    assert (
        section_locked(state, RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1"))
        is False
    )
    assert (
        section_locked(state, RowDescriptor(RowKind.RENDER_OVERLAY_CARD_POSITION)) is False
    )


def test_row_triggers_layer_delete_for_track_rows_only() -> None:
    assert row_triggers_layer_delete(RowKind.TRACK_HEADER) is True
    assert row_triggers_layer_delete(RowKind.LAYER_MANAGEMENT_DELETE) is True
    assert row_triggers_layer_delete(RowKind.LAYER_MANAGEMENT_ADD) is False
    assert row_triggers_layer_delete(RowKind.TRANSPORT) is False


def test_tree_branch_prefix() -> None:
    assert tree_branch_prefix(0) == ""
    assert tree_branch_prefix(1) == "└─ "
    assert tree_branch_prefix(2) == "  └─ "
    assert tree_branch_prefix(3) == "    └─ "


def test_tree_branch_leading_spaces() -> None:
    assert tree_branch_leading_spaces(0) == ""
    assert tree_branch_leading_spaces(1) == ""
    assert tree_branch_leading_spaces(2) == "  "
    assert tree_branch_leading_spaces(3) == "    "


def test_row_panel_label_settings_header() -> None:
    assert row_panel_label(RowKind.SETTINGS_HEADER) == "Editor Settings"


def test_labeled_row_prefix_settings_children() -> None:
    assert labeled_row_prefix(RowKind.SETTINGS_PREVIEW_QUALITY) == "└─ preview quality: "
    assert labeled_row_prefix(RowKind.SETTINGS_UI_WIDTH_MODE) == "  └─ width mode: "
    assert labeled_row_prefix(RowKind.SETTINGS_UI_WIDTH) == "  └─ max width: "
    assert labeled_row_prefix(RowKind.SETTINGS_UI_FADE) == "  └─ auto-fade: "


def test_labeled_row_prefix_track_depths() -> None:
    assert labeled_row_prefix(RowKind.TRACK_STEM) == "└─ driving stem: "
    assert labeled_row_prefix(RowKind.TRACK_PRESET_SWITCHING_TRIGGER) == "  └─ trigger: "


def test_format_row_value_settings() -> None:
    state = _minimal_view_state(
        settings=SettingsBlock(
            preview_quality="performance",
            ui_width_mode="fixed",
            ui_width=320,
            ui_fade=0.0,
        ),
    )
    assert (
        format_row_value(state, RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY))
        == "performance"
    )
    assert (
        format_row_value(state, RowDescriptor(RowKind.SETTINGS_UI_WIDTH_MODE))
        == "fixed"
    )
    assert format_row_value(state, RowDescriptor(RowKind.SETTINGS_UI_WIDTH)) == "320"
    assert (
        format_row_value(state, RowDescriptor(RowKind.SETTINGS_UI_FADE))
        == ui_fade_display(0.0)
    )


def test_format_row_value_track_and_render() -> None:
    state = _minimal_view_state(
        tracks={
            "layer_1": make_track_block(
                stem=TEST_LAYER_STEMS["layer_1"],
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="add",
                opacity_pct=75,
                beat_sensitivity=1.25,
                effects={},
                preset_switching="on",
                preset_duration=45.0,
            )
        },
        render_overlays=RenderOverlaysBlock(
            opening_card=make_overlay_card_block(
                position="top-left", opacity_pct=80
            ),
        ),
        render_post_fx=RenderPostFxBlock(fade_in=2.5, fade_out=3.0),
    )
    slot_desc = RowDescriptor(RowKind.TRACK_BLEND, slot="layer_1")
    assert format_row_value(state, slot_desc) == "add"
    mode_desc = RowDescriptor(RowKind.TRACK_PRESET_SWITCHING, slot="layer_1")
    assert format_row_value(state, mode_desc) == "on"
    duration_desc = RowDescriptor(RowKind.TRACK_PRESET_DURATION, slot="layer_1")
    assert format_row_value(state, duration_desc) == "45s"
    assert format_row_value(
        state,
        RowDescriptor(RowKind.RENDER_OVERLAY_CARD_POSITION, card="opening_card"),
    ) == (
        "top-left"
    )
    assert (
        format_row_value(
            state,
            RowDescriptor(RowKind.RENDER_OVERLAY_CARD_OPACITY, card="opening_card"),
        )
        == "80%"
    )
    assert format_row_value(state, RowDescriptor(RowKind.RENDER_POST_FX_FADE_IN)) == (
        "2.5s"
    )
    assert format_row_value(
        state, RowDescriptor(RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD)
    ) == "78%"
    assert format_row_value(
        state, RowDescriptor(RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_MODE)
    ) == "composite"


def test_row_labeled_display_text_settings() -> None:
    state = _minimal_view_state(
        settings=SettingsBlock(preview_quality="balanced", ui_fade=11.0),
    )
    desc = RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY)
    assert row_labeled_display_text(state, desc) == "└─ preview quality: balanced"
    fade_desc = RowDescriptor(RowKind.SETTINGS_UI_FADE)
    assert row_labeled_display_text(state, fade_desc) == "  └─ auto-fade: 11s"


def test_apply_field_horizontal_unknown_kind_returns_false() -> None:
    controls = _make_controls()
    assert (
        apply_field_horizontal(
            controls, RowDescriptor(RowKind.RENDER_SECTION_GAP), True, False
        )
        is False
    )


def test_apply_field_horizontal_cycles_preview_quality() -> None:
    controls = _make_controls()
    desc = RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY)
    assert controls.cfg.editor.preview_quality == "balanced"

    assert apply_field_horizontal(controls, desc, True, False) is True
    assert controls.cfg.editor.preview_quality == "performance"

    apply_field_horizontal(controls, desc, False, False)
    assert controls.cfg.editor.preview_quality == "balanced"


def test_apply_field_horizontal_preview_quality_calls_preview_resolutions() -> None:
    controls, layer_manager = _make_controls_with_manager()
    desc = RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY)

    apply_field_horizontal(controls, desc, True, False)

    layer_manager.apply_preview_resolutions.assert_called_once()


def test_apply_field_horizontal_track_blend() -> None:
    controls = _make_controls(("layer_1",))
    desc = RowDescriptor(RowKind.TRACK_BLEND, slot="layer_1")
    before = controls.session.layers["layer_1"].blend_mode

    assert apply_field_horizontal(controls, desc, True, False) is True
    assert controls.session.layers["layer_1"].blend_mode != before


def test_apply_field_horizontal_render_overlay_opacity() -> None:
    controls = _make_controls()
    desc = RowDescriptor(RowKind.RENDER_OVERLAY_CARD_OPACITY, card="opening_card")
    before = controls.session.render_overlays.opening_card.opacity_pct

    assert apply_field_horizontal(controls, desc, True, False) is True
    assert controls.session.render_overlays.opening_card.opacity_pct == before + 1


def test_overlay_cards_share_kinds_and_isolate_runtime() -> None:
    controls = _make_controls()
    controls.session.render_overlays.expanded = True
    controls.session.render_overlays.opening_card.expanded = True
    controls.session.render_overlays.closing_card.expanded = True
    view = controls.build_view_state(paused=False)
    opening_pos = view.layout.find_by_kind(
        RowKind.RENDER_OVERLAY_CARD_POSITION, card="opening_card"
    )
    closing_pos = view.layout.find_by_kind(
        RowKind.RENDER_OVERLAY_CARD_POSITION, card="closing_card"
    )
    opening_desc = view.layout.descriptor(opening_pos)
    closing_desc = view.layout.descriptor(closing_pos)
    assert opening_desc.kind == RowKind.RENDER_OVERLAY_CARD_POSITION
    assert closing_desc.kind == RowKind.RENDER_OVERLAY_CARD_POSITION
    assert opening_desc.card == "opening_card"
    assert closing_desc.card == "closing_card"
    assert opening_pos != closing_pos
    navigable = view.layout.navigable_indices(view)
    assert opening_pos in navigable
    assert closing_pos in navigable

    opening_before = controls.session.render_overlays.opening_card.position
    closing_before = controls.session.render_overlays.closing_card.position
    assert apply_field_horizontal(controls, opening_desc, True, False) is True
    assert controls.session.render_overlays.opening_card.position != opening_before
    assert controls.session.render_overlays.closing_card.position == closing_before
    assert apply_field_horizontal(controls, closing_desc, True, False) is True
    assert controls.session.render_overlays.closing_card.position != closing_before


def test_apply_field_horizontal_adjusts_ui_fade() -> None:
    controls = _make_controls()
    desc = RowDescriptor(RowKind.SETTINGS_UI_FADE)
    assert controls.cfg.editor.ui_fade == 10.0

    apply_field_horizontal(controls, desc, True, False)
    assert controls.cfg.editor.ui_fade == 11.0

    apply_field_horizontal(controls, desc, False, True)
    assert controls.cfg.editor.ui_fade == 6.0


def test_apply_field_horizontal_via_controls_keydown() -> None:
    controls = _make_controls()
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    view = controls.build_view_state(paused=False)
    ui_header = view.layout.find_by_kind(RowKind.SETTINGS_UI_HEADER)
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_UI_WIDTH_MODE)

    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.ui_width_mode == "fixed"


def test_expand_subheader_prefix_preset_switching() -> None:
    assert (
        expand_subheader_prefix(RowKind.TRACK_PRESET_SWITCHING)
        == "└─ preset switching"
    )
    assert expand_subheader_prefix(RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER) == (
        "  └─ title "
    )
    assert (
        expand_subheader_prefix(RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_HEADER)
        == "└─ highlight rolloff "
    )
    assert expand_subheader_prefix(RowKind.SETTINGS_UI_HEADER) == "└─ UI "


def test_row_expand_subheader_display_text() -> None:
    state = _minimal_view_state()
    desc = RowDescriptor(RowKind.TRACK_PRESET_SWITCHING, slot="layer_1")
    assert (
        row_expand_subheader_display_text(state, desc)
        == "└─ preset switching: off ▶"
    )


def test_song_markers_expand_subheader_includes_count() -> None:
    from cleave.viz.tuning_view_state import RenderTimelineBlock

    state = _minimal_view_state(
        render_timeline=RenderTimelineBlock(
            expanded=True,
            song_markers_expanded=False,
            song_marker_times=(1.0, 2.0, 3.0, 4.0),
        )
    )
    desc = RowDescriptor(RowKind.SONG_MARKERS_HEADER)
    assert row_expand_subheader_display_text(state, desc) == "└─ song markers (4) ▶"


def test_composite_header_render_overlay_metadata() -> None:
    field = row_spec(RowKind.RENDER_OVERLAYS_HEADER)
    assert field.present_style == RowPresentStyle.COMPOSITE_HEADER
    assert field.header_prefix == "Render: "
    assert field.header_suffix == "OVERLAYS"

    state = _minimal_view_state()
    desc = RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
    assert composite_header_prefix_part(state, desc) == "Render: "
    assert composite_header_suffix_part(state, desc) == "OVERLAYS"
    assert row_composite_header_display_text(state, desc) == "Render: OVERLAYS ▶"


def test_preset_list_populate_is_full_line_action() -> None:
    field = row_spec(RowKind.TRACK_PRESET_LIST_POPULATE)
    assert field.present_style == RowPresentStyle.FULL_LINE
    assert field.panel_label == "populate presets"
    add_field = row_spec(RowKind.TRACK_PRESET_LIST_ADD)
    assert add_field.present_style == RowPresentStyle.FULL_LINE
    assert add_field.panel_label == "add current preset"


def test_preset_list_add_populate_share_list_item_tree_chrome() -> None:
    """FULL_LINE actions nest under the preset list header like list items."""
    from cleave.viz.row_sections import row_tree_indent_depth

    item_depth = row_tree_indent_depth(RowKind.TRACK_PRESET_LIST_ITEM)
    branch = tree_branch_prefix(item_depth)
    assert branch == "    └─ "
    assert full_line_prefix(RowKind.TRACK_PRESET_LIST_ADD) == (
        branch + "add current preset"
    )
    populate_depth = row_tree_indent_depth(RowKind.TRACK_PRESET_LIST_POPULATE)
    populate_branch = tree_branch_prefix(populate_depth)
    assert full_line_prefix(RowKind.TRACK_PRESET_LIST_POPULATE) == (
        populate_branch + "populate presets"
    )
    assert labeled_row_prefix(RowKind.TRACK_PRESET_LIST_ITEM).startswith(branch)


def test_apply_field_horizontal_expand_subheader_when_layer_locked() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].locked = True
    desc = RowDescriptor(RowKind.TRACK_EFFECTS_HEADER, slot="layer_1")
    assert controls.session.layers["layer_1"].effects_expanded is False

    assert apply_field_horizontal(controls, desc, True, False, False) is True
    assert controls.session.layers["layer_1"].effects_expanded is True


def test_apply_field_horizontal_track_header_solo_and_expand() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    desc = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")

    assert apply_field_horizontal(controls, desc, True, False, True) is True
    assert controls.session.solo_slot == "layer_1"

    apply_field_horizontal(controls, desc, False, False, True)
    assert controls.session.solo_slot is None

    apply_field_horizontal(controls, desc, False, False, False)
    assert controls.session.layers["layer_1"].expanded is False
    apply_field_horizontal(controls, desc, True, False, False)
    assert controls.session.layers["layer_1"].expanded is True


def test_row_specs_total_over_row_kind() -> None:
    assert set(ROW_SPECS) == set(RowKind)
    assert len(ROW_SPECS) == len(RowKind)


def test_spacer_kind_is_registered() -> None:
    assert RowKind.RENDER_SECTION_GAP in ROW_SPECS


def test_row_spec_apply_horizontal_signatures_match_field_mutator() -> None:
    mismatches: list[str] = []
    for kind, field in ROW_SPECS.items():
        handler = field.apply_horizontal
        if handler is None:
            continue
        param_count = len(inspect.signature(handler).parameters)
        if param_count != 5:
            mismatches.append(
                f"{kind.name} ({handler.__name__}): {param_count} params, expected 5"
            )
    assert not mismatches, "RowSpec apply_horizontal arity mismatches:\n" + "\n".join(mismatches)


def test_format_row_value_path_icon() -> None:
    state = _minimal_view_state(
        active_config_label="projects/demo/cleave-viz.yaml",
        tracks={
            "layer_1": make_track_block(
                stem=TEST_LAYER_STEMS["layer_1"],
                preset_dir_label="presets/wave",
                preset_label="foo.milk",
                blend_mode="add",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
            )
        },
    )
    assert (
        format_row_value(state, RowDescriptor(RowKind.CONFIG_HEADER))
        == "projects/demo/cleave-viz.yaml"
    )
    slot_desc = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    assert format_row_value(state, slot_desc) == "presets/wave"
    preset_desc = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    assert format_row_value(state, preset_desc) == "foo.milk"


def test_track_effect_dynamic_label_and_prefix() -> None:
    state = _minimal_view_state(
        tracks={
            "layer_1": make_track_block(
                stem=TEST_LAYER_STEMS["layer_1"],
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="add",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={"pulse": {"onset": 35}},
            )
        },
    )
    desc = RowDescriptor(
        RowKind.TRACK_EFFECT, slot="layer_1", effect_id="pulse", driver_slug="onset"
    )
    assert row_dynamic_labeled_prefix(desc) == "  └─ pulse (onset): "
    assert row_dynamic_labeled_display_text(state, desc) == "  └─ pulse (onset): 35%"


def test_full_line_delete_layer_prefix() -> None:
    assert full_line_prefix(RowKind.LAYER_MANAGEMENT_DELETE) == "└─ Delete Layer"
    assert row_panel_label(RowKind.LAYER_MANAGEMENT_ADD) == "Add Layer"


def test_apply_field_horizontal_visual_limiter_enabled() -> None:
    controls = _make_controls(timeline_enabled=True)
    controls.session.timeline.limiter.enabled = True
    desc = RowDescriptor(RowKind.TIMELINE_VISUAL_LIMITER_ENABLED)

    apply_field_horizontal(controls, desc, False, False)
    assert controls.session.timeline.limiter.enabled is False

    apply_field_horizontal(controls, desc, True, False)
    assert controls.session.timeline.limiter.enabled is True


def test_apply_field_horizontal_visual_limiter_header_expands() -> None:
    controls = _make_controls(timeline_enabled=True)
    controls.session.timeline.visual_limiter_expanded = False
    desc = RowDescriptor(RowKind.TIMELINE_VISUAL_LIMITER_HEADER)

    apply_field_horizontal(controls, desc, True, False)
    assert controls.session.timeline.visual_limiter_expanded is True
    assert controls.session.timeline.limiter.enabled is True

    apply_field_horizontal(controls, desc, False, False)
    assert controls.session.timeline.visual_limiter_expanded is False
    assert controls.session.timeline.limiter.enabled is True


def test_apply_field_horizontal_transport_seeks() -> None:
    from cleave.viz.controls import SEEK_LONG, SEEK_SHORT, SEEK_TINY

    controls = _make_controls()
    controls.duration_sec = 120.0
    seeks: list[float] = []
    controls._layer_bindings = noop_layer_bindings(
        on_seek=lambda delta: seeks.append(delta)
    )
    desc = RowDescriptor(RowKind.TRANSPORT)

    apply_field_horizontal(controls, desc, True, False)
    apply_field_horizontal(controls, desc, False, False)
    apply_field_horizontal(controls, desc, True, False, True)
    apply_field_horizontal(controls, desc, False, False, True)
    apply_field_horizontal(controls, desc, True, True)
    apply_field_horizontal(controls, desc, False, True)

    assert seeks == [
        SEEK_SHORT,
        -SEEK_SHORT,
        SEEK_TINY,
        -SEEK_TINY,
        SEEK_LONG,
        -SEEK_LONG,
    ]


class _RecordingControls:
    """Stub that records private attribute access from RowSpec callbacks."""

    def __init__(self, accessed_private: list[str] | None = None) -> None:
        object.__setattr__(
            self, "_accessed_private", accessed_private if accessed_private is not None else []
        )

    def __getattr__(self, name: str) -> _RecordingControls:
        if name.startswith("_") and not name.startswith("__"):
            self._accessed_private.append(name)
        child = _RecordingControls(self._accessed_private)
        object.__setattr__(self, name, child)
        return child

    def __setattr__(self, name: str, value: object) -> None:
        if name.startswith("_") and not name.startswith("__"):
            self._accessed_private.append(name)
        object.__setattr__(self, name, value)

    def __bool__(self) -> bool:
        return True

    def __call__(self, *args: object, **kwargs: object) -> _RecordingControls:
        del args, kwargs
        return self

    def __getitem__(self, key: object) -> _RecordingControls:
        del key
        return self

    def __setitem__(self, key: object, value: object) -> None:
        del key, value

    def get(self, *args: object, **kwargs: object) -> _RecordingControls:
        del args, kwargs
        return self

    def __len__(self) -> int:
        return 0

    def __iter__(self):
        return iter(())

    def __contains__(self, item: object) -> bool:
        del item
        return False

    def __int__(self) -> int:
        return 0

    def __float__(self) -> float:
        return 0.0

    def __index__(self) -> int:
        return 0

    def __add__(self, other: object) -> object:
        return 0 if not isinstance(other, _RecordingControls) else other

    def __radd__(self, other: object) -> object:
        return other

    def __sub__(self, other: object) -> object:
        del other
        return 0

    def __rsub__(self, other: object) -> object:
        return other


def test_row_spec_callbacks_use_public_controls_api() -> None:
    accessed: list[str] = []
    controls = _RecordingControls(accessed)
    for kind, field in ROW_SPECS.items():
        if field.apply_horizontal is None:
            continue
        desc = RowDescriptor(
            kind,
            slot="layer_1",
            card="opening_card",
            effect_id="pulse",
            driver_slug="onset",
            marker_index=0,
            preset_index=0,
        )
        for forward, ctrl, shift in (
            (True, False, False),
            (True, True, False),
            (True, False, True),
        ):
            try:
                field.apply_horizontal(controls, desc, forward, ctrl, shift)
            except Exception:
                continue
    assert accessed == []
