"""Tests for the unified RowSpec panel registry."""

from __future__ import annotations

import inspect
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock

import pygame
import pytest

from cleave.config_schema.editor import (
    DEFAULT_EDITOR_PREVIEW_QUALITY,
    DEFAULT_NOTIFICATION_DISPLAY_SEC,
    DEFAULT_HELP_SIDE,
    DEFAULT_NAVIGATOR_SIDE,
    DEFAULT_UI_SCALE,
    UI_SCALE_MAX,
    UI_SCALE_MIN,
    notification_display_label,
)
from cleave.config_schema.layers import hard_cut_enabled_display
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.shell_layout import navigator_row_px
from cleave.viz.theme import (
    set_ui_scale_percent,
    ui_scale_generation,
    ui_scale_percent,
)
from cleave.viz.row_spec import (
    HEADER_ROW_KINDS,
    REPEAT_ROW_KINDS,
    ROW_SPECS,
    TRACK_SUB_ROW_KINDS,
    RowPresentStyle,
    apply_field_horizontal,
    apply_field_toggle_enabled,
    apply_field_toggle_solo,
    apply_field_nav_button,
    format_row_markers,
    format_row_position,
    format_row_value,
    row_dynamic_panel_label,
    row_blocked_by_section_lock,
    row_is_pinned,
    row_is_two_line,
    row_navigable_when_section_locked,
    row_panel_label,
    row_spec,
    row_triggers_layer_delete,
    section_lock_blocks_mutation,
    section_locked,
)
from cleave.viz.tuning_view_state import (
    FadeBlock,
    FadeSideBlock,
    OverlaysBlock,
    PostFxBlock,
    TimelineBlock,
    SettingsBlock,
    TimelineFadeGroupBlock,
)
from tests.cleave.viz.test_controls import (
    _keydown,
    _make_controls,
    _make_controls_with_manager,
)
from tests.cleave.viz.test_overlay import _minimal_view_state
from tests.support.config import TEST_LAYER_STEMS
from tests.support.viz import (
    make_overlay_card_block,
    make_track_block,
    noop_layer_bindings,
)


def _track_lock_state(locked: bool) -> SimpleNamespace:
    return SimpleNamespace(tracks={"layer_1": SimpleNamespace(locked=locked)})

_EXPECTED_REPEAT_ROW_KINDS = frozenset(
    {
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
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
        RowKind.OVERLAY_CARD_POSITION,
        RowKind.OVERLAY_CARD_ANIMATION_TYPE,
        RowKind.OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION,
        RowKind.OVERLAY_CARD_TITLE_FONT_SIZE,
        RowKind.OVERLAY_CARD_TITLE_FONT,
        RowKind.OVERLAY_CARD_TITLE_MARGIN_BOTTOM,
        RowKind.OVERLAY_CARD_BODY_FONT_SIZE,
        RowKind.OVERLAY_CARD_BODY_FONT,
        RowKind.OVERLAY_CARD_OPACITY,
        RowKind.OVERLAY_CARD_BACKGROUND_MARGIN,
        RowKind.OVERLAY_CARD_BACKGROUND_PADDING,
        RowKind.OVERLAY_CARD_BORDER_WIDTH,
        RowKind.OVERLAY_CARD_TIME,
        RowKind.OVERLAY_CARD_DISPLAY_TIME,
        RowKind.POST_FX_FADE_IN_START,
        RowKind.POST_FX_FADE_IN_END,
        RowKind.POST_FX_FADE_IN_TYPE,
        RowKind.POST_FX_FADE_OUT_START,
        RowKind.POST_FX_FADE_OUT_END,
        RowKind.POST_FX_FADE_OUT_TYPE,
        RowKind.POST_FX_HIGHLIGHT_ROLLOFF_MODE,
        RowKind.POST_FX_HIGHLIGHT_ROLLOFF_CURVE,
        RowKind.POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD,
        RowKind.POST_FX_HIGHLIGHT_ROLLOFF_CEILING,
        RowKind.POST_FX_HIGHLIGHT_ROLLOFF_STRENGTH,
        RowKind.POST_FX_HIGHLIGHT_ROLLOFF_SOFTNESS,
        RowKind.POST_FX_HIGHLIGHT_ROLLOFF_DESATURATION,
        RowKind.POST_FX_CHROMA_BOOST_MODE,
        RowKind.POST_FX_CHROMA_BOOST_VARIANT,
        RowKind.POST_FX_CHROMA_BOOST_AMOUNT,
        RowKind.PATTERN_MASK_TYPE,
        RowKind.PATTERN_MASK_DENSITY,
        RowKind.PATTERN_MASK_FEATHER,
        RowKind.PATTERN_MASK_INVERT,
        RowKind.PATTERN_MASK_TRANSITION,
        RowKind.PATTERN_MASK_SEED,
        RowKind.SETTINGS_PREVIEW_QUALITY,
        RowKind.SETTINGS_NAVIGATOR_SIDE,
        RowKind.SETTINGS_HELP_SIDE,
        RowKind.SETTINGS_UI_SCALE,
        RowKind.SETTINGS_UI_NOTIFICATION_DISPLAY,
        RowKind.SETTINGS_UI_NAVIGATOR_HEIGHT,
        RowKind.SETTINGS_RESIDUAL_LATENCY_MS,
        RowKind.PROJECT_RENDER_QUALITY,
        RowKind.PROJECT_RESOLUTION_WIDTH,
        RowKind.PROJECT_RESOLUTION_HEIGHT,
        RowKind.PROJECT_RENDER_FPS,
        RowKind.PROJECT_RENDER_START,
        RowKind.PROJECT_RENDER_END,
        RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY,
        RowKind.PROJECT_COMPOSITOR_HDR,
        RowKind.TIMELINE_BAR_PHASE,
        RowKind.TIMELINE_HARD_CUTS,
        RowKind.TIMELINE_HARD_CUT_FADE_IN,
        RowKind.TIMELINE_HARD_CUT_FADE_OUT,
        RowKind.TIMELINE_HARD_CUT_CROSSFADE,
        RowKind.TIMELINE_SOFT_CUTS,
        RowKind.TIMELINE_SOFT_CUT_FADE_IN,
        RowKind.TIMELINE_SOFT_CUT_FADE_OUT,
        RowKind.TIMELINE_SOFT_CUT_CROSSFADE,
        RowKind.POST_FX_LIMITER_THRESHOLD,
        RowKind.POST_FX_LIMITER_RATIO,
        RowKind.POST_FX_LIMITER_RELEASE,
    }
)


def test_every_row_kind_has_spec() -> None:
    for kind in RowKind:
        assert kind in ROW_SPECS
        assert row_spec(kind) is ROW_SPECS[kind]


def test_header_row_kinds() -> None:
    names = {kind.name for kind in HEADER_ROW_KINDS}
    assert "SETTINGS_HEADER" not in names
    assert "PROJECT_HEADER" not in names
    assert "TRANSPORT" not in names


def test_row_is_pinned() -> None:
    assert row_is_pinned(RowKind.PROJECT_RENDER_HEADER) is True
    assert row_is_pinned(RowKind.PROJECT_COMPOSITOR_HEADER) is True
    assert row_is_pinned(RowKind.PROJECT_COMPOSITOR_HDR) is True
    assert row_is_pinned(RowKind.PROJECT_RENDER_QUALITY) is True
    assert row_is_pinned(RowKind.SETTINGS_PREVIEW_QUALITY) is True
    assert row_is_pinned(RowKind.SETTINGS_EDITOR_WINDOW_HEADER) is True
    assert row_is_pinned(RowKind.SETTINGS_NAVIGATOR_SIDE) is True
    assert row_is_pinned(RowKind.SETTINGS_HELP_SIDE) is True
    assert row_is_pinned(RowKind.SETTINGS_UI_HEADER) is True
    assert row_is_pinned(RowKind.SETTINGS_UI_NOTIFICATION_DISPLAY) is True
    assert row_is_pinned(RowKind.SETTINGS_UI_NAVIGATOR_HEIGHT) is True
    assert row_is_pinned(RowKind.TRACK_HEADER) is False
    assert row_is_pinned(RowKind.OVERLAYS_HEADER) is False


def test_repeat_row_kinds() -> None:
    assert REPEAT_ROW_KINDS == _EXPECTED_REPEAT_ROW_KINDS


def test_overlay_title_text_is_locked_action() -> None:
    spec = row_spec(RowKind.OVERLAY_CARD_TITLE_TEXT)
    assert spec.affordance == RowAffordance.VALUE_TEXT
    assert spec.present_style == RowPresentStyle.LABELED_VALUE
    assert spec.apply_action is not None
    assert spec.blocked_by_section_lock is True
    assert spec.panel_label == "title text"
    assert spec.parent_group == "overlay_title"


def test_overlay_title_colour_is_locked_action() -> None:
    spec = row_spec(RowKind.OVERLAY_CARD_TITLE_COLOUR)
    assert spec.affordance == RowAffordance.VALUE_COLOUR
    assert spec.present_style == RowPresentStyle.LABELED_VALUE
    assert spec.apply_action is not None
    assert spec.blocked_by_section_lock is True
    assert spec.panel_label == "title colour"
    assert spec.parent_group == "overlay_title"


def test_overlay_remaining_colour_rows_are_locked_actions() -> None:
    for kind, label, group in (
        (
            RowKind.OVERLAY_CARD_TITLE_BACKGROUND_COLOUR,
            "title background",
            "overlay_title",
        ),
        (
            RowKind.OVERLAY_CARD_BODY_COLOUR,
            "body colour",
            "overlay_body",
        ),
        (
            RowKind.OVERLAY_CARD_BODY_BACKGROUND_COLOUR,
            "body background",
            "overlay_body",
        ),
        (
            RowKind.OVERLAY_CARD_BACKGROUND_COLOUR,
            "background colour",
            "overlay",
        ),
        (
            RowKind.OVERLAY_CARD_BORDER_COLOUR,
            "border colour",
            "overlay",
        ),
    ):
        spec = row_spec(kind)
        assert spec.affordance == RowAffordance.VALUE_COLOUR
        assert spec.present_style == RowPresentStyle.LABELED_VALUE
        assert spec.apply_action is not None
        assert spec.blocked_by_section_lock is True
        assert spec.panel_label == label
        assert spec.parent_group == group


def test_overlay_background_margin_and_padding_are_value_steps() -> None:
    for kind, label in (
        (RowKind.OVERLAY_CARD_BACKGROUND_MARGIN, "background margin"),
        (RowKind.OVERLAY_CARD_BACKGROUND_PADDING, "background padding"),
    ):
        spec = row_spec(kind)
        assert spec.affordance == RowAffordance.VALUE_STEP
        assert spec.present_style == RowPresentStyle.LABELED_VALUE
        assert spec.repeatable is True
        assert spec.format_value is not None
        assert spec.apply_horizontal is not None
        assert spec.panel_label == label
        assert spec.parent_group == "overlay"


def test_overlay_body_text_is_locked_action() -> None:
    spec = row_spec(RowKind.OVERLAY_CARD_BODY_TEXT)
    assert spec.affordance == RowAffordance.VALUE_TEXT
    assert spec.present_style == RowPresentStyle.LABELED_VALUE
    assert spec.apply_action is not None
    assert spec.blocked_by_section_lock is True
    assert spec.panel_label == "body text"
    assert spec.parent_group == "overlay_body"


def test_parent_group_on_row_specs() -> None:
    assert row_spec(RowKind.TRACK_STEM).parent_group == "track"
    assert row_spec(RowKind.OVERLAY_CARD_POSITION).parent_group == (
        "overlay"
    )
    assert row_spec(RowKind.OVERLAY_CARD_TITLE_FONT).parent_group == (
        "overlay_title"
    )
    assert row_spec(RowKind.OVERLAY_CARD_TITLE_TEXT).parent_group == (
        "overlay_title"
    )
    assert row_spec(RowKind.OVERLAY_CARD_TITLE_COLOUR).parent_group == (
        "overlay_title"
    )
    assert row_spec(RowKind.OVERLAY_CARD_TITLE_BACKGROUND_COLOUR).parent_group == (
        "overlay_title"
    )
    assert row_spec(RowKind.OVERLAY_CARD_BODY_FONT).parent_group == (
        "overlay_body"
    )
    assert row_spec(RowKind.OVERLAY_CARD_BODY_TEXT).parent_group == (
        "overlay_body"
    )
    assert row_spec(RowKind.OVERLAY_CARD_BODY_COLOUR).parent_group == (
        "overlay_body"
    )
    assert row_spec(RowKind.OVERLAY_CARD_BODY_BACKGROUND_COLOUR).parent_group == (
        "overlay_body"
    )
    assert row_spec(RowKind.OVERLAY_CARD_BACKGROUND_COLOUR).parent_group == (
        "overlay"
    )
    assert row_spec(RowKind.OVERLAY_CARD_BACKGROUND_MARGIN).parent_group == (
        "overlay"
    )
    assert row_spec(RowKind.OVERLAY_CARD_BACKGROUND_PADDING).parent_group == (
        "overlay"
    )
    assert row_spec(RowKind.OVERLAY_CARD_BORDER_COLOUR).parent_group == (
        "overlay"
    )
    assert row_spec(RowKind.POST_FX_FADE_HEADER).parent_group == "post_fx"
    assert row_spec(RowKind.POST_FX_FADE_IN_HEADER).parent_group == (
        "post_fx_fade"
    )
    assert row_spec(RowKind.POST_FX_FADE_IN_START).parent_group == (
        "post_fx_fade_in"
    )
    assert row_spec(RowKind.POST_FX_FADE_OUT_HEADER).parent_group == (
        "post_fx_fade"
    )
    assert row_spec(RowKind.POST_FX_FADE_OUT_END).parent_group == (
        "post_fx_fade_out"
    )
    assert row_spec(RowKind.SETTINGS_PREVIEW_QUALITY).parent_group == (
        "settings_editor_window"
    )
    assert row_spec(RowKind.SETTINGS_EDITOR_WINDOW_HEADER).parent_group == "settings"
    assert row_spec(RowKind.SETTINGS_NAVIGATOR_SIDE).parent_group == (
        "settings_editor_window"
    )
    assert row_spec(RowKind.SETTINGS_HELP_SIDE).parent_group == (
        "settings_editor_window"
    )
    assert row_spec(RowKind.LAYER_MANAGEMENT_COUNT).navigable is False
    assert row_spec(RowKind.LAYER_MANAGEMENT_COUNT).affordance == (
        RowAffordance.DISPLAY
    )


def test_track_sub_row_kinds() -> None:
    assert TRACK_SUB_ROW_KINDS == frozenset(
        {
            RowKind.TRACK_ENABLED,
            RowKind.TRACK_SOLO,
            RowKind.TRACK_LOCKED,
            RowKind.TRACK_PRESET_DIR,
            RowKind.TRACK_PRESET,
            RowKind.TRACK_PRESET_SWITCHING,
            RowKind.TRACK_PRESET_SWITCHING_TRIGGER,
            RowKind.TRACK_PRESET_SWITCHING_RESUME,
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
            RowKind.TRACK_COMPOSITING_HEADER,
            RowKind.TRACK_EFFECTS_HEADER,
            RowKind.TRACK_EFFECT,
            RowKind.LAYER_MANAGEMENT_DELETE,
        }
    )


def test_locked_navigable_sub_row_kinds() -> None:
    navigable = frozenset(
        k for k in TRACK_SUB_ROW_KINDS if row_navigable_when_section_locked(k)
    )
    assert navigable == frozenset(
        {
            RowKind.TRACK_PRESET_SWITCHING,
            RowKind.TRACK_PRESET_LIST,
            RowKind.TRACK_COMPOSITING_HEADER,
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
            RowKind.TRACK_ENABLED,
            RowKind.TRACK_PRESET_DIR,
            RowKind.TRACK_PRESET,
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
            RowKind.TRACK_PRESET_SWITCHING_RESUME,
        }
    )
    for kind in blocked:
        desc = RowDescriptor(kind, slot="layer_1")
        assert section_lock_blocks_mutation(_track_lock_state(True), desc) is True
        assert section_lock_blocks_mutation(_track_lock_state(False), desc) is False


def test_only_effects_header_navigable_when_section_locked() -> None:
    navigable_when_locked = {
        RowKind.TRACK_PRESET_SWITCHING,
        RowKind.TRACK_PRESET_LIST,
        RowKind.TRACK_COMPOSITING_HEADER,
        RowKind.TRACK_EFFECTS_HEADER,
        RowKind.LAYER_MANAGEMENT_DELETE,
    }
    for kind in TRACK_SUB_ROW_KINDS:
        assert row_navigable_when_section_locked(kind) == (kind in navigable_when_locked)


def test_preset_list_actions_are_action_rows() -> None:
    for kind in (
        RowKind.TRACK_PRESET_LIST_POPULATE,
        RowKind.TRACK_PRESET_LIST_ADD,
        RowKind.TRACK_PRESET_SWITCHING_RESUME,
    ):
        assert row_spec(kind).affordance == RowAffordance.COMMAND


def _render_lock_state(
    *, overlay: bool = False, post_fx: bool = False, timeline: bool = False
) -> SimpleNamespace:
    return SimpleNamespace(
        overlays=SimpleNamespace(locked=overlay),
        post_fx=SimpleNamespace(locked=post_fx),
        timeline=SimpleNamespace(locked=timeline),
    )


def test_render_value_children_blocked_by_section_lock() -> None:
    assert row_blocked_by_section_lock(RowKind.OVERLAY_CARD_POSITION) is True
    assert row_blocked_by_section_lock(RowKind.OVERLAY_CARD_TITLE_FONT) is True
    assert row_blocked_by_section_lock(RowKind.OVERLAY_CARD_TITLE_TEXT) is True
    assert row_blocked_by_section_lock(RowKind.OVERLAY_CARD_TITLE_COLOUR) is True
    assert row_blocked_by_section_lock(
        RowKind.OVERLAY_CARD_TITLE_BACKGROUND_COLOUR
    ) is True
    assert row_blocked_by_section_lock(RowKind.OVERLAY_CARD_BODY_TEXT) is True
    assert row_blocked_by_section_lock(RowKind.OVERLAY_CARD_BODY_COLOUR) is True
    assert row_blocked_by_section_lock(
        RowKind.OVERLAY_CARD_BODY_BACKGROUND_COLOUR
    ) is True
    assert row_blocked_by_section_lock(
        RowKind.OVERLAY_CARD_BACKGROUND_COLOUR
    ) is True
    assert row_blocked_by_section_lock(
        RowKind.OVERLAY_CARD_BACKGROUND_MARGIN
    ) is True
    assert row_blocked_by_section_lock(
        RowKind.OVERLAY_CARD_BACKGROUND_PADDING
    ) is True
    assert row_blocked_by_section_lock(RowKind.OVERLAY_CARD_BORDER_COLOUR) is True
    assert row_blocked_by_section_lock(RowKind.POST_FX_FADE_IN_START) is True
    assert row_blocked_by_section_lock(RowKind.POST_FX_CHROMA_BOOST_AMOUNT) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_GENERATE) is True
    assert row_blocked_by_section_lock(RowKind.TRACK_PRESET_LIST_POPULATE) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_BAR_PHASE) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_SNAP_CUES) is True
    assert row_blocked_by_section_lock(RowKind.SONG_MARKER_ITEM) is True
    assert row_blocked_by_section_lock(RowKind.SONG_MARKERS_HEADER) is False
    assert row_blocked_by_section_lock(RowKind.TIMELINE_BEAT_BAR_GRID_HEADER) is False


def test_render_headers_navigable_when_section_locked() -> None:
    for kind in (
        RowKind.OVERLAYS_HEADER,
        RowKind.POST_FX_HEADER,
        RowKind.TIMELINE_HEADER,
        RowKind.OVERLAY_CARD_TITLE_HEADER,
        RowKind.POST_FX_CHROMA_BOOST_HEADER,
        RowKind.SONG_MARKERS_HEADER,
        RowKind.TIMELINE_BEAT_BAR_GRID_HEADER,
    ):
        assert row_navigable_when_section_locked(kind) is True
    assert row_navigable_when_section_locked(RowKind.OVERLAY_CARD_POSITION) is False
    assert row_navigable_when_section_locked(RowKind.TIMELINE_GENERATE) is False
    assert row_navigable_when_section_locked(RowKind.SONG_MARKER_ITEM) is False


def test_section_locked_resolves_render_sections() -> None:
    overlay_desc = RowDescriptor(RowKind.OVERLAY_CARD_POSITION)
    post_fx_desc = RowDescriptor(RowKind.POST_FX_FADE_IN_START)
    timeline_desc = RowDescriptor(RowKind.TIMELINE_GENERATE)
    assert section_locked(_render_lock_state(overlay=True), overlay_desc) is True
    assert section_locked(_render_lock_state(), overlay_desc) is False
    assert section_locked(_render_lock_state(post_fx=True), post_fx_desc) is True
    assert section_locked(_render_lock_state(timeline=True), timeline_desc) is True


def test_section_locked_reads_session_timeline_attribute() -> None:
    session_like = SimpleNamespace(
        overlays=SimpleNamespace(locked=False),
        post_fx=SimpleNamespace(locked=False),
        timeline=SimpleNamespace(locked=True),
    )
    assert section_locked(session_like, RowDescriptor(RowKind.TIMELINE_GENERATE)) is True


def test_section_locked_ignored_in_preset_curation() -> None:
    state = SimpleNamespace(
        settings=SimpleNamespace(editor_mode="preset_curation"),
        tracks={"layer_1": SimpleNamespace(locked=True)},
        overlays=SimpleNamespace(locked=True),
        post_fx=SimpleNamespace(locked=True),
        timeline=SimpleNamespace(locked=True),
    )
    assert (
        section_locked(state, RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1"))
        is False
    )
    assert (
        section_locked(state, RowDescriptor(RowKind.OVERLAY_CARD_POSITION)) is False
    )


def test_row_triggers_layer_delete_for_track_rows_only() -> None:
    assert row_triggers_layer_delete(RowKind.TRACK_HEADER) is True
    assert row_triggers_layer_delete(RowKind.LAYER_MANAGEMENT_DELETE) is True
    assert row_triggers_layer_delete(RowKind.LAYER_MANAGEMENT_ADD) is False
    assert row_triggers_layer_delete(RowKind.OVERLAYS_HEADER) is False


def test_row_panel_label_names_a_track_effect() -> None:
    desc = RowDescriptor(
        RowKind.TRACK_EFFECT,
        slot="layer_1",
        effect_id="kaleido",
        driver_slug="kick",
    )

    assert row_panel_label(desc.kind, desc) == "kaleido (kick)"


def test_row_panel_label_settings_header() -> None:
    assert row_panel_label(RowKind.PROJECT_MILKDROP_HEADER) == "ProjectM"
    assert row_panel_label(RowKind.PROJECT_COMPOSITOR_HEADER) == "Compositor"
    assert row_panel_label(RowKind.PROJECT_RESOLUTION_HEADER) == "Resolution"
    assert row_panel_label(RowKind.PROJECT_RENDER_HEADER) == "Render"


def test_format_row_value_settings() -> None:
    state = _minimal_view_state(
        settings=SettingsBlock(
            preview_quality="performance",
            navigator_side="right",
            help_side="left",
            notification_display_sec=0,
            navigator_height=240,
        ),
    )
    assert (
        format_row_value(state, RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY))
        == "performance"
    )
    assert (
        format_row_value(state, RowDescriptor(RowKind.SETTINGS_NAVIGATOR_SIDE))
        == "right"
    )
    assert (
        format_row_value(state, RowDescriptor(RowKind.SETTINGS_HELP_SIDE))
        == "left"
    )
    assert (
        format_row_value(state, RowDescriptor(RowKind.SETTINGS_UI_NOTIFICATION_DISPLAY))
        == notification_display_label(0)
    )
    assert (
        format_row_value(state, RowDescriptor(RowKind.SETTINGS_UI_NAVIGATOR_HEIGHT))
        == "240 px"
    )
    scaled = _minimal_view_state(settings=SettingsBlock(ui_scale=120))
    assert (
        format_row_value(scaled, RowDescriptor(RowKind.SETTINGS_UI_SCALE))
        == "120%"
    )
    fit = _minimal_view_state(settings=SettingsBlock(navigator_height=0))
    assert (
        format_row_value(fit, RowDescriptor(RowKind.SETTINGS_UI_NAVIGATOR_HEIGHT))
        == "fit to rows"
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
                preset_switching_trigger="timer",
                preset_duration=45.0,
            )
        },
        overlays=OverlaysBlock(
            opening_card=make_overlay_card_block(
                position="top-left", opacity_pct=80, title_content="A\nB\rC",
                body_content="X\nY\rZ", title_colour=(255, 0, 0),
                title_background_colour=(0, 255, 0),
                body_colour=(0, 0, 255),
                body_background_colour=None,
                background_colour=(1, 2, 3),
                border_colour=(4, 5, 6),
                background_margin=40,
                background_padding=20)),
        post_fx=PostFxBlock(
            fade=FadeBlock(fade_in=FadeSideBlock(start=2.5))),
    )
    slot_desc = RowDescriptor(RowKind.TRACK_BLEND, slot="layer_1")
    assert format_row_value(state, slot_desc) == "add"
    mode_desc = RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_TRIGGER, slot="layer_1")
    assert format_row_value(state, mode_desc) == "timer"
    duration_desc = RowDescriptor(RowKind.TRACK_PRESET_DURATION, slot="layer_1")
    assert format_row_value(state, duration_desc) == "45s"
    assert format_row_value(
        state,
        RowDescriptor(RowKind.OVERLAY_CARD_POSITION, card="opening_card"),
    ) == (
        "top-left"
    )
    assert format_row_value(
        state,
        RowDescriptor(RowKind.OVERLAY_CARD_TITLE_TEXT, card="opening_card"),
    ) == "A B C"
    assert format_row_value(
        state,
        RowDescriptor(RowKind.OVERLAY_CARD_TITLE_COLOUR, card="opening_card"),
    ) == "#ff0000"
    assert format_row_value(
        state,
        RowDescriptor(
            RowKind.OVERLAY_CARD_TITLE_BACKGROUND_COLOUR, card="opening_card"
        ),
    ) == "#00ff00"
    assert format_row_value(
        state,
        RowDescriptor(RowKind.OVERLAY_CARD_BODY_TEXT, card="opening_card"),
    ) == "X Y Z"
    assert format_row_value(
        state,
        RowDescriptor(RowKind.OVERLAY_CARD_BODY_COLOUR, card="opening_card"),
    ) == "#0000ff"
    assert format_row_value(
        state,
        RowDescriptor(
            RowKind.OVERLAY_CARD_BODY_BACKGROUND_COLOUR, card="opening_card"
        ),
    ) == "none"
    assert format_row_value(
        state,
        RowDescriptor(
            RowKind.OVERLAY_CARD_BACKGROUND_COLOUR, card="opening_card"
        ),
    ) == "#010203"
    assert format_row_value(
        state,
        RowDescriptor(RowKind.OVERLAY_CARD_BORDER_COLOUR, card="opening_card"),
    ) == "#040506"
    assert format_row_value(
        state,
        RowDescriptor(
            RowKind.OVERLAY_CARD_BACKGROUND_MARGIN, card="opening_card"
        ),
    ) == "40px"
    assert format_row_value(
        state,
        RowDescriptor(
            RowKind.OVERLAY_CARD_BACKGROUND_PADDING, card="opening_card"
        ),
    ) == "20px"
    assert (
        format_row_value(
            state,
            RowDescriptor(RowKind.OVERLAY_CARD_OPACITY, card="opening_card"),
        )
        == "80%"
    )
    assert format_row_value(
        state, RowDescriptor(RowKind.POST_FX_FADE_IN_START)
    ) == ("2.5s")
    assert format_row_value(
        state, RowDescriptor(RowKind.POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD)
    ) == "78%"
    assert format_row_value(
        state, RowDescriptor(RowKind.POST_FX_HIGHLIGHT_ROLLOFF_MODE)
    ) == "composite"


def test_apply_field_horizontal_display_row_is_not_editable() -> None:
    controls = _make_controls()
    assert (
        apply_field_horizontal(
            controls,
            RowDescriptor(RowKind.LAYER_MANAGEMENT_COUNT),
            True,
            False,
        )
        is False
    )


def test_apply_field_horizontal_unknown_kind_returns_false() -> None:
    controls = _make_controls()
    assert (
        apply_field_horizontal(
            controls, RowDescriptor(RowKind.LAYER_MANAGEMENT_COUNT), True, False
        )
        is False
    )


def test_apply_field_horizontal_cycles_column_sides() -> None:
    controls = _make_controls()
    navigator = RowDescriptor(RowKind.SETTINGS_NAVIGATOR_SIDE)
    help_side = RowDescriptor(RowKind.SETTINGS_HELP_SIDE)
    assert controls.cfg.editor.navigator_side == DEFAULT_NAVIGATOR_SIDE
    assert controls.cfg.editor.help_side == DEFAULT_HELP_SIDE

    assert apply_field_horizontal(controls, navigator, True, False) is True
    assert controls.cfg.editor.navigator_side == "right"
    assert controls.cfg.editor.help_side == DEFAULT_HELP_SIDE

    apply_field_horizontal(controls, navigator, False, False)
    assert controls.cfg.editor.navigator_side == DEFAULT_NAVIGATOR_SIDE

    assert apply_field_horizontal(controls, help_side, False, False) is True
    assert controls.cfg.editor.help_side == "left"
    assert controls.cfg.editor.navigator_side == DEFAULT_NAVIGATOR_SIDE


def test_apply_field_horizontal_cycles_preview_quality() -> None:
    controls = _make_controls()
    desc = RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY)
    assert controls.cfg.editor.preview_quality == DEFAULT_EDITOR_PREVIEW_QUALITY

    assert apply_field_horizontal(controls, desc, True, False) is True
    assert controls.cfg.editor.preview_quality == "balanced"

    apply_field_horizontal(controls, desc, False, False)
    assert controls.cfg.editor.preview_quality == DEFAULT_EDITOR_PREVIEW_QUALITY


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


def test_apply_field_horizontal_overlay_opacity() -> None:
    controls = _make_controls()
    desc = RowDescriptor(RowKind.OVERLAY_CARD_OPACITY, card="opening_card")
    before = controls.session.overlays.opening_card.opacity_pct

    assert apply_field_horizontal(controls, desc, True, False) is True
    assert controls.session.overlays.opening_card.opacity_pct == before + 1


def test_apply_field_horizontal_overlay_background_margin() -> None:
    controls = _make_controls()
    desc = RowDescriptor(
        RowKind.OVERLAY_CARD_BACKGROUND_MARGIN, card="opening_card"
    )
    before = controls.session.overlays.opening_card.background_margin

    assert apply_field_horizontal(controls, desc, True, False) is True
    assert (
        controls.session.overlays.opening_card.background_margin == before + 1
    )
    assert apply_field_horizontal(controls, desc, True, True) is True
    assert (
        controls.session.overlays.opening_card.background_margin == before + 11
    )
    controls.session.overlays.opening_card.background_margin = 0
    assert apply_field_horizontal(controls, desc, False, False) is True
    assert controls.session.overlays.opening_card.background_margin == 0


def test_apply_field_horizontal_overlay_background_padding() -> None:
    controls = _make_controls()
    desc = RowDescriptor(
        RowKind.OVERLAY_CARD_BACKGROUND_PADDING, card="opening_card"
    )
    before = controls.session.overlays.opening_card.background_padding

    assert apply_field_horizontal(controls, desc, True, False) is True
    assert (
        controls.session.overlays.opening_card.background_padding == before + 1
    )


def test_overlay_cards_share_kinds_and_isolate_runtime() -> None:
    from cleave.viz.inspector import build_inspector_rows

    controls = _make_controls()
    view = controls.build_view_state(paused=False)
    opening_desc = RowDescriptor(
        RowKind.OVERLAY_CARD_POSITION, card="opening_card"
    )
    closing_desc = RowDescriptor(
        RowKind.OVERLAY_CARD_POSITION, card="closing_card"
    )
    assert opening_desc.kind == RowKind.OVERLAY_CARD_POSITION
    assert closing_desc.kind == RowKind.OVERLAY_CARD_POSITION
    assert opening_desc.card == "opening_card"
    assert closing_desc.card == "closing_card"
    assert opening_desc != closing_desc
    cards = {
        row.descriptor.card
        for node_id in ("overlay.opening_card", "overlay.closing_card")
        for row in build_inspector_rows(view, node_id)
        if row.descriptor.kind is RowKind.OVERLAY_CARD_POSITION
    }
    assert cards == {"opening_card", "closing_card"}

    opening_before = controls.session.overlays.opening_card.position
    closing_before = controls.session.overlays.closing_card.position
    assert apply_field_horizontal(controls, opening_desc, True, False) is True
    assert controls.session.overlays.opening_card.position != opening_before
    assert controls.session.overlays.closing_card.position == closing_before
    assert apply_field_horizontal(controls, closing_desc, True, False) is True
    assert controls.session.overlays.closing_card.position != closing_before


def test_apply_field_horizontal_adjusts_notification_display() -> None:
    controls = _make_controls()
    desc = RowDescriptor(RowKind.SETTINGS_UI_NOTIFICATION_DISPLAY)
    assert (
        controls.cfg.editor.notification_display_sec
        == DEFAULT_NOTIFICATION_DISPLAY_SEC
    )

    apply_field_horizontal(controls, desc, True, False)
    assert (
        controls.cfg.editor.notification_display_sec
        == DEFAULT_NOTIFICATION_DISPLAY_SEC + 1
    )

    apply_field_horizontal(controls, desc, False, True)
    assert (
        controls.cfg.editor.notification_display_sec
        == DEFAULT_NOTIFICATION_DISPLAY_SEC + 1 - 5
    )


def test_apply_field_horizontal_steps_navigator_height_from_drawn() -> None:
    controls = _make_controls()
    desc = RowDescriptor(RowKind.SETTINGS_UI_NAVIGATOR_HEIGHT)
    row = navigator_row_px()
    band = 600
    controls.settings.note_shell_stack(200, band)
    assert controls.cfg.editor.navigator_height == 0

    apply_field_horizontal(controls, desc, True, False)
    assert controls.cfg.editor.navigator_height == 210
    apply_field_horizontal(controls, desc, True, True)
    assert controls.cfg.editor.navigator_height == 260

    for _ in range(40):
        apply_field_horizontal(controls, desc, True, True)
    assert controls.cfg.editor.navigator_height == band - row

    controls.cfg.editor = replace(controls.cfg.editor, navigator_height=row + 5)
    apply_field_horizontal(controls, desc, False, False)
    assert controls.cfg.editor.navigator_height == row
    apply_field_horizontal(controls, desc, False, False)
    assert controls.cfg.editor.navigator_height == 0


def test_apply_field_horizontal_steps_ui_scale_and_applies_live() -> None:
    controls = _make_controls()
    desc = RowDescriptor(RowKind.SETTINGS_UI_SCALE)
    generation = ui_scale_generation()
    try:
        apply_field_horizontal(controls, desc, True, False)
        assert controls.cfg.editor.ui_scale == DEFAULT_UI_SCALE + 10
        assert ui_scale_percent() == DEFAULT_UI_SCALE + 10
        assert ui_scale_generation() == generation + 1
        apply_field_horizontal(controls, desc, True, True)
        assert controls.cfg.editor.ui_scale == DEFAULT_UI_SCALE + 60
        for _ in range(10):
            apply_field_horizontal(controls, desc, True, True)
        assert controls.cfg.editor.ui_scale == UI_SCALE_MAX
        for _ in range(20):
            apply_field_horizontal(controls, desc, False, True)
        assert controls.cfg.editor.ui_scale == UI_SCALE_MIN
    finally:
        set_ui_scale_percent(DEFAULT_UI_SCALE)


def test_apply_field_horizontal_via_controls_keydown() -> None:
    from tests.support.viz import press_main_row

    controls = _make_controls()
    controls.focus_descriptor = RowDescriptor(RowKind.SETTINGS_NAVIGATOR_SIDE)
    before = controls.cfg.editor.navigator_side

    press_main_row(controls, _keydown(pygame.K_RIGHT))
    assert controls.cfg.editor.navigator_side != before


def test_format_row_value_timeline_cuts() -> None:
    state = _minimal_view_state(
        timeline=TimelineBlock(
            hard_cut_fades=TimelineFadeGroupBlock(
                enabled=True, fade_in=1.5, fade_out=2.5, crossfade=True
            ),
            soft_cut_fades=TimelineFadeGroupBlock(
                enabled=False, fade_in=0.5, fade_out=3.0, crossfade=False
            ),
        )
    )
    assert format_row_value(
        state, RowDescriptor(RowKind.TIMELINE_HARD_CUTS)
    ) == hard_cut_enabled_display(True)
    assert format_row_value(
        state, RowDescriptor(RowKind.TIMELINE_SOFT_CUTS)
    ) == hard_cut_enabled_display(False)
    assert (
        format_row_value(state, RowDescriptor(RowKind.TIMELINE_HARD_CUT_FADE_IN))
        == "1.5s"
    )
    assert (
        format_row_value(state, RowDescriptor(RowKind.TIMELINE_SOFT_CUT_FADE_OUT))
        == "3.0s"
    )


def test_preset_list_populate_is_full_line_action() -> None:
    field = row_spec(RowKind.TRACK_PRESET_LIST_POPULATE)
    assert field.present_style == RowPresentStyle.FULL_LINE
    assert field.panel_label == "Populate..."
    add_field = row_spec(RowKind.TRACK_PRESET_LIST_ADD)
    assert add_field.present_style == RowPresentStyle.FULL_LINE
    assert add_field.panel_label == "+ Add current"


def test_resume_switching_row_only_while_paused() -> None:
    from cleave.viz.inspector import build_inspector_rows
    from cleave.viz.navigator import layer_node_id

    spec = row_spec(RowKind.TRACK_PRESET_SWITCHING_RESUME)
    assert spec.affordance == RowAffordance.COMMAND
    assert spec.panel_label == "Resume"
    assert spec.blocked_by_section_lock is True
    assert spec.parent_group == "track"

    def kinds(*, paused: bool) -> list[RowKind]:
        state = _minimal_view_state(
            tracks={
                "layer_1": make_track_block(
                    stem=TEST_LAYER_STEMS["layer_1"],
                    preset_dir_label="dir",
                    preset_label="preset.milk",
                    blend_mode="add",
                    opacity_pct=50,
                    beat_sensitivity=1.0,
                    effects={},
                    preset_switching="on",
                    preset_switching_trigger="timer",
                    preset_list=["/tmp/a.milk"],
                    switching_paused=paused,
                )
            }
        )
        rows = build_inspector_rows(state, layer_node_id("layer_1"))
        return rows

    def resume_index(rows) -> int | None:
        for index, row in enumerate(rows):
            if row.command_ids == ("layers.resume_switching",):
                return index
        return None

    assert resume_index(kinds(paused=False)) is None
    shown = kinds(paused=True)
    index = resume_index(shown)
    assert index is not None
    assert shown[index].status == "Switching paused"
    assert shown[index - 1].descriptor.kind is RowKind.TRACK_PRESET


def test_apply_field_horizontal_track_header_solo_and_expand() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    desc = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")

    assert apply_field_toggle_solo(controls, desc) is True
    assert controls.session.solo_slot == "layer_1"

    apply_field_toggle_solo(controls, desc)
    assert controls.session.solo_slot is None

    apply_field_toggle_enabled(controls, desc)
    assert controls.session.layers["layer_1"].enabled is False


def test_row_specs_total_over_row_kind() -> None:
    assert set(ROW_SPECS) == set(RowKind)
    assert len(ROW_SPECS) == len(RowKind)


def test_row_spec_apply_horizontal_signatures_match_field_mutator() -> None:
    mismatches: list[str] = []
    for kind, field in ROW_SPECS.items():
        handler = field.apply_horizontal
        if handler is None:
            continue
        param_count = len(inspect.signature(handler).parameters)
        if param_count != 4:
            mismatches.append(
                f"{kind.name} ({handler.__name__}): {param_count} params, expected 4"
            )
    assert not mismatches, "RowSpec apply_horizontal arity mismatches:\n" + "\n".join(mismatches)


def test_row_spec_toggle_mutators_match_action_mutator() -> None:
    mismatches: list[str] = []
    for kind, field in ROW_SPECS.items():
        for attr in ("toggle_enabled", "toggle_solo"):
            handler = getattr(field, attr)
            if handler is None:
                continue
            param_count = len(inspect.signature(handler).parameters)
            if param_count != 2:
                mismatches.append(
                    f"{kind.name}.{attr} ({handler.__name__}): "
                    f"{param_count} params, expected 2"
                )
    assert not mismatches, "RowSpec toggle mutator arity mismatches:\n" + "\n".join(
        mismatches
    )


def test_format_row_value_path_icon() -> None:
    state = _minimal_view_state(
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
        format_row_value(state, RowDescriptor(RowKind.PROJECT_RENDER_OUTPUT))
        == state.project.output_label
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
    assert row_dynamic_panel_label(desc) == "pulse (onset)"
    assert format_row_value(state, desc) == "35%"


def test_apply_field_horizontal_visual_limiter_enabled() -> None:
    controls = _make_controls()
    controls.session.post_fx.limiter.enabled = True
    desc = RowDescriptor(RowKind.POST_FX_LIMITER_ENABLED)

    apply_field_horizontal(controls, desc, False, False)
    assert controls.session.post_fx.limiter.enabled is False

    apply_field_horizontal(controls, desc, True, False)
    assert controls.session.post_fx.limiter.enabled is True


def test_apply_field_horizontal_visual_limiter_header_expands() -> None:
    controls = _make_controls()
    desc = RowDescriptor(RowKind.POST_FX_LIMITER_HEADER)

    apply_field_horizontal(controls, desc, True, False)
    assert controls.session.post_fx.limiter.enabled is True

    apply_field_horizontal(controls, desc, False, False)
    assert controls.session.post_fx.limiter.enabled is True


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
        for forward, large in (
            (True, False),
            (True, True),
        ):
            try:
                field.apply_horizontal(controls, desc, forward, large)
            except Exception:
                continue
    assert accessed == []


def test_two_line_rows_are_the_preset_path_rows() -> None:
    assert {kind for kind in RowKind if row_is_two_line(kind)} == {
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_PRESET_LIST_ITEM,
    }


def test_preset_dir_buttons_follow_the_available_moves() -> None:
    desc = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    block = SimpleNamespace(preset_dir_can_go_up=True, preset_dir_can_go_down=False)
    state = SimpleNamespace(tracks={"layer_1": block})
    up, down = row_spec(RowKind.TRACK_PRESET_DIR).nav_buttons
    assert up.available(state, desc) is True
    assert down.available(state, desc) is False


def test_nav_buttons_move_up_and_down_the_tree() -> None:
    controls = _make_controls(("layer_1",))
    controls.layer_mutations = MagicMock()
    desc = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")

    assert apply_field_nav_button(controls, desc, 0) is True
    controls.layer_mutations.parent_directory.assert_called_once_with("layer_1")
    assert apply_field_nav_button(controls, desc, 1) is True
    controls.layer_mutations.enter_directory.assert_called_once_with("layer_1")


def test_section_lock_blocks_nav_buttons() -> None:
    controls = _make_controls(("layer_1",))
    controls.layer_mutations = MagicMock()
    controls.session.layers["layer_1"].locked = True
    desc = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")

    assert apply_field_nav_button(controls, desc, 0) is False
    controls.layer_mutations.parent_directory.assert_not_called()


def test_preset_list_item_has_no_side_arrows() -> None:
    assert row_spec(RowKind.TRACK_PRESET_LIST_ITEM).apply_horizontal is None


def test_two_line_row_splits_value_position_and_markers() -> None:
    block = SimpleNamespace(
        preset_dir_label="packs/wave/",
        preset_dir_position="2/5",
        preset_label="foo.milk",
        preset_position="3/9",
        preset_markers="[F] [R:B]",
        preset_list_labels=["a.milk", "b.milk"],
        preset_list_markers=["", "[B]"],
    )
    state = SimpleNamespace(tracks={"layer_1": block})

    directory = RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")
    assert format_row_value(state, directory) == "packs/wave/"
    assert format_row_position(state, directory) == "2/5"
    assert format_row_markers(state, directory) == ""

    preset = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    assert format_row_value(state, preset) == "foo.milk"
    assert format_row_position(state, preset) == "3/9"
    assert format_row_markers(state, preset) == "[F] [R:B]"

    item = RowDescriptor(
        RowKind.TRACK_PRESET_LIST_ITEM, slot="layer_1", preset_index=1
    )
    assert format_row_value(state, item) == "b.milk"
    assert format_row_position(state, item) == "2/2"
    assert format_row_markers(state, item) == "[B]"
