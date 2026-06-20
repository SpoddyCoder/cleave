"""Tests for row interaction semantics."""

from __future__ import annotations

from cleave.viz.row_semantics import (
    HEADER_ROW_KINDS,
    LABELED_SUB_ROW_KINDS,
    RENDER_OVERLAY_ALL_SUB_ROW_KINDS,
    RENDER_OVERLAY_BODY_NESTED_KINDS,
    RENDER_OVERLAY_SUB_ROW_KINDS,
    RENDER_OVERLAY_TITLE_NESTED_KINDS,
    RENDER_POST_FX_SUB_ROW_KINDS,
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
    row_navigable_when_layer_locked,
)

_EXPECTED_REPEAT_ROW_KINDS = frozenset(
    {
        RowKind.TRANSPORT,
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
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
        }
    )


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


def test_parent_group_frozensets_match_row_behaviors() -> None:
    for group, expected in (
        ("track", TRACK_SUB_ROW_KINDS),
        ("render_overlay", RENDER_OVERLAY_SUB_ROW_KINDS),
        ("render_overlay_title", RENDER_OVERLAY_TITLE_NESTED_KINDS),
        ("render_overlay_body", RENDER_OVERLAY_BODY_NESTED_KINDS),
        ("render_post_fx", RENDER_POST_FX_SUB_ROW_KINDS),
    ):
        derived = frozenset(
            k for k, b in ROW_BEHAVIORS.items() if b.parent_group == group
        )
        assert derived == expected


def test_track_sub_row_kinds() -> None:
    assert TRACK_SUB_ROW_KINDS == frozenset(
        {
            RowKind.TRACK_PRESET_DIR,
            RowKind.TRACK_PRESET,
            RowKind.TRACK_STEM,
            RowKind.TRACK_BLEND,
            RowKind.TRACK_OPACITY,
            RowKind.TRACK_BEAT,
            RowKind.TRACK_EFFECTS_HEADER,
            RowKind.TRACK_EFFECT,
        }
    )


def test_track_effect_sub_row_kinds() -> None:
    assert TRACK_EFFECT_SUB_ROW_KINDS == frozenset({RowKind.TRACK_EFFECT})


def test_render_overlay_sub_row_kinds() -> None:
    assert RENDER_OVERLAY_SUB_ROW_KINDS == frozenset(
        {
            RowKind.RENDER_OVERLAY_POSITION,
            RowKind.RENDER_OVERLAY_OPACITY,
            RowKind.RENDER_OVERLAY_BORDER_WIDTH,
            RowKind.RENDER_OVERLAY_START_DELAY,
            RowKind.RENDER_OVERLAY_DISPLAY_TIME,
            RowKind.RENDER_OVERLAY_TITLE_HEADER,
            RowKind.RENDER_OVERLAY_BODY_HEADER,
        }
    )


def test_render_overlay_nested_kinds() -> None:
    assert RENDER_OVERLAY_TITLE_NESTED_KINDS == frozenset(
        {
            RowKind.RENDER_OVERLAY_TITLE_FONT,
            RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE,
            RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
        }
    )
    assert RENDER_OVERLAY_BODY_NESTED_KINDS == frozenset(
        {
            RowKind.RENDER_OVERLAY_BODY_FONT,
            RowKind.RENDER_OVERLAY_BODY_FONT_SIZE,
        }
    )


def test_render_overlay_all_sub_row_kinds() -> None:
    assert RENDER_OVERLAY_ALL_SUB_ROW_KINDS == (
        RENDER_OVERLAY_SUB_ROW_KINDS
        | RENDER_OVERLAY_TITLE_NESTED_KINDS
        | RENDER_OVERLAY_BODY_NESTED_KINDS
    )


def test_render_post_fx_sub_row_kinds() -> None:
    assert RENDER_POST_FX_SUB_ROW_KINDS == frozenset(
        {
            RowKind.RENDER_POST_FX_FADE_IN,
            RowKind.RENDER_POST_FX_FADE_OUT,
        }
    )


def test_locked_navigable_sub_row_kinds() -> None:
    navigable = frozenset(
        k for k in TRACK_SUB_ROW_KINDS if row_navigable_when_layer_locked(k)
    )
    assert navigable == frozenset({RowKind.TRACK_EFFECTS_HEADER})


def test_track_value_rows_blocked_by_layer_lock() -> None:
    blocked = frozenset(
        k for k in TRACK_SUB_ROW_KINDS if row_blocked_by_layer_lock(k)
    )
    assert blocked == frozenset(
        {
            RowKind.TRACK_PRESET_DIR,
            RowKind.TRACK_PRESET,
            RowKind.TRACK_STEM,
            RowKind.TRACK_BLEND,
            RowKind.TRACK_OPACITY,
            RowKind.TRACK_BEAT,
            RowKind.TRACK_EFFECT,
        }
    )
    for kind in blocked:
        assert layer_lock_blocks_mutation(kind, locked=True) is True
        assert layer_lock_blocks_mutation(kind, locked=False) is False


def test_only_effects_header_navigable_when_layer_locked() -> None:
    for kind in TRACK_SUB_ROW_KINDS:
        if kind == RowKind.TRACK_EFFECTS_HEADER:
            assert row_navigable_when_layer_locked(kind) is True
        else:
            assert row_navigable_when_layer_locked(kind) is False


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
