"""Tests for row interaction semantics."""

from __future__ import annotations

from cleave.viz.row_semantics import (
    HEADER_ROW_KINDS,
    LABELED_SUB_ROW_KINDS,
    REPEAT_ROW_KINDS,
    ROW_BEHAVIORS,
    TRACK_EFFECT_SUB_ROW_KINDS,
    TRACK_SUB_ROW_KINDS,
    RowAffordance,
    RowKind,
    expandable_row_kinds,
    layer_lock_blocks_mutation,
    row_blocked_by_layer_lock,
    row_behavior,
    row_is_pinned,
    row_navigable_when_layer_locked,
    row_triggers_layer_delete,
)

_EXPECTED_REPEAT_ROW_KINDS = frozenset(
    {
        RowKind.TRANSPORT,
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_PRESET_SWITCHING_MODE,
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
        RowKind.RENDER_OVERLAY_POSITION,
        RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE,
        RowKind.RENDER_OVERLAY_TITLE_FONT,
        RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
        RowKind.RENDER_OVERLAY_BODY_FONT_SIZE,
        RowKind.RENDER_OVERLAY_BODY_FONT,
        RowKind.RENDER_OVERLAY_OPACITY,
        RowKind.RENDER_OVERLAY_BORDER_WIDTH,
        RowKind.RENDER_OVERLAY_START_DELAY,
        RowKind.RENDER_OVERLAY_DISPLAY_TIME,
        RowKind.RENDER_POST_FX_FADE_IN,
        RowKind.RENDER_POST_FX_FADE_OUT,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_ENABLED,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_MODE,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CEILING,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_STRENGTH,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_SOFTNESS,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_DESATURATION,
        RowKind.SETTINGS_RENDER_MODE,
        RowKind.SETTINGS_UI_WIDTH_MODE,
        RowKind.SETTINGS_UI_WIDTH,
        RowKind.SETTINGS_UI_FADE,
    }
)


def test_every_row_kind_has_behavior() -> None:
    for kind in RowKind:
        assert kind in ROW_BEHAVIORS
        assert row_behavior(kind) is ROW_BEHAVIORS[kind]


def test_header_row_kinds() -> None:
    assert HEADER_ROW_KINDS == frozenset(
        {
            RowKind.TRANSPORT,
            RowKind.CONFIG_HEADER,
            RowKind.SETTINGS_HEADER,
        }
    )


def test_row_is_pinned() -> None:
    assert row_is_pinned(RowKind.TRANSPORT) is True
    assert row_is_pinned(RowKind.CONFIG_HEADER) is True
    assert row_is_pinned(RowKind.SETTINGS_HEADER) is True
    assert row_is_pinned(RowKind.SETTINGS_RENDER_MODE) is True
    assert row_is_pinned(RowKind.SETTINGS_UI_HEADER) is True
    assert row_is_pinned(RowKind.SETTINGS_UI_FADE) is True
    assert row_is_pinned(RowKind.SETTINGS_UI_WIDTH_MODE) is True
    assert row_is_pinned(RowKind.SETTINGS_UI_WIDTH) is True
    assert row_is_pinned(RowKind.TRACK_HEADER) is False
    assert row_is_pinned(RowKind.RENDER_OVERLAY_HEADER) is False


def test_repeat_row_kinds() -> None:
    assert REPEAT_ROW_KINDS == _EXPECTED_REPEAT_ROW_KINDS


def test_render_overlay_sub_headers_expand() -> None:
    title = row_behavior(RowKind.RENDER_OVERLAY_TITLE_HEADER)
    body = row_behavior(RowKind.RENDER_OVERLAY_BODY_HEADER)
    assert title.affordance == RowAffordance.EXPAND
    assert title.is_sub_header is True
    assert body.affordance == RowAffordance.EXPAND
    assert body.is_sub_header is True


def test_track_effects_header_expands() -> None:
    behavior = row_behavior(RowKind.TRACK_EFFECTS_HEADER)
    assert behavior.affordance == RowAffordance.EXPAND


def test_expandable_row_kinds() -> None:
    assert expandable_row_kinds() == frozenset(
        k for k, b in ROW_BEHAVIORS.items() if b.affordance == RowAffordance.EXPAND
    )


def test_parent_group_on_row_behaviors() -> None:
    assert row_behavior(RowKind.TRACK_STEM).parent_group == "track"
    assert row_behavior(RowKind.RENDER_OVERLAY_POSITION).parent_group == "render_overlay"
    assert row_behavior(RowKind.RENDER_OVERLAY_TITLE_FONT).parent_group == "render_overlay_title"
    assert row_behavior(RowKind.RENDER_OVERLAY_BODY_FONT).parent_group == "render_overlay_body"
    assert row_behavior(RowKind.RENDER_POST_FX_FADE_IN).parent_group == "render_post_fx"
    assert row_behavior(RowKind.SETTINGS_RENDER_MODE).parent_group == "settings"
    assert row_behavior(RowKind.SETTINGS_UI_WIDTH_MODE).parent_group == "settings_ui"


def test_track_sub_row_kinds() -> None:
    assert TRACK_SUB_ROW_KINDS == frozenset(
        {
            RowKind.TRACK_PRESET_DIR,
            RowKind.TRACK_PRESET,
            RowKind.TRACK_PRESET_SWITCHING,
            RowKind.TRACK_PRESET_SWITCHING_MODE,
            RowKind.TRACK_USER_PRESETS,
            RowKind.TRACK_USER_PRESET_ITEM,
            RowKind.TRACK_USER_PRESET_ADD,
            RowKind.TRACK_PRESET_SWITCHING_SCOPE,
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
        k for k in TRACK_SUB_ROW_KINDS if row_navigable_when_layer_locked(k)
    )
    assert navigable == frozenset(
        {
            RowKind.TRACK_PRESET_SWITCHING,
            RowKind.TRACK_USER_PRESETS,
            RowKind.TRACK_EFFECTS_HEADER,
            RowKind.LAYER_MANAGEMENT_DELETE,
        }
    )


def test_track_value_rows_blocked_by_layer_lock() -> None:
    blocked = frozenset(
        k for k in TRACK_SUB_ROW_KINDS if row_blocked_by_layer_lock(k)
    )
    assert blocked == frozenset(
        {
            RowKind.TRACK_PRESET_DIR,
            RowKind.TRACK_PRESET,
            RowKind.TRACK_PRESET_SWITCHING_MODE,
            RowKind.TRACK_PRESET_SWITCHING_SCOPE,
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
            RowKind.TRACK_USER_PRESET_ITEM,
            RowKind.TRACK_USER_PRESET_ADD,
        }
    )
    for kind in blocked:
        assert layer_lock_blocks_mutation(kind, locked=True) is True
        assert layer_lock_blocks_mutation(kind, locked=False) is False


def test_only_effects_header_navigable_when_layer_locked() -> None:
    navigable_when_locked = {
        RowKind.TRACK_PRESET_SWITCHING,
        RowKind.TRACK_USER_PRESETS,
        RowKind.TRACK_EFFECTS_HEADER,
        RowKind.LAYER_MANAGEMENT_DELETE,
    }
    for kind in TRACK_SUB_ROW_KINDS:
        assert row_navigable_when_layer_locked(kind) == (kind in navigable_when_locked)


def test_labeled_sub_row_kinds_exclude_headers() -> None:
    assert LABELED_SUB_ROW_KINDS.isdisjoint(HEADER_ROW_KINDS)
    for kind in LABELED_SUB_ROW_KINDS:
        behavior = row_behavior(kind)
        assert behavior.affordance in {
            RowAffordance.VALUE_STEP,
            RowAffordance.PATH_DIR,
            RowAffordance.PATH_PRESET,
        }
        assert not behavior.is_header


def test_row_triggers_layer_delete_for_track_rows_only() -> None:
    assert row_triggers_layer_delete(RowKind.TRACK_HEADER) is True
    assert row_triggers_layer_delete(RowKind.LAYER_MANAGEMENT_DELETE) is True
    assert row_triggers_layer_delete(RowKind.LAYER_MANAGEMENT_ADD) is False
    assert row_triggers_layer_delete(RowKind.TRANSPORT) is False
