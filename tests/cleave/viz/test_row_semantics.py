"""Tests for row interaction semantics."""

from __future__ import annotations

from types import SimpleNamespace

from cleave.viz.row_semantics import (
    HEADER_ROW_KINDS,
    LABELED_SUB_ROW_KINDS,
    REPEAT_ROW_KINDS,
    ROW_BEHAVIORS,
    TRACK_EFFECT_SUB_ROW_KINDS,
    TRACK_SUB_ROW_KINDS,
    RowAffordance,
    RowDescriptor,
    RowKind,
    expandable_row_kinds,
    row_blocked_by_section_lock,
    row_behavior,
    row_is_pinned,
    row_navigable_when_section_locked,
    row_triggers_layer_delete,
    section_lock_blocks_mutation,
)


def _track_lock_state(locked: bool) -> SimpleNamespace:
    return SimpleNamespace(tracks={"layer_1": SimpleNamespace(locked=locked)})

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
        RowKind.TRACK_PRESET_SWITCHING_SHUFFLE,
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
        RowKind.SETTINGS_PREVIEW_QUALITY,
        RowKind.SETTINGS_UI_WIDTH_MODE,
        RowKind.SETTINGS_UI_WIDTH,
        RowKind.SETTINGS_UI_FADE,
        RowKind.TIMELINE_BAR_PHASE,
        RowKind.TIMELINE_SNAP_MARKER_PROXIMITY,
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
    assert row_is_pinned(RowKind.SETTINGS_PREVIEW_QUALITY) is True
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
    assert row_behavior(RowKind.SETTINGS_PREVIEW_QUALITY).parent_group == "settings"
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
            RowKind.TRACK_PRESET_SWITCHING_SHUFFLE,
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
            RowKind.TRACK_PRESET_SWITCHING,
            RowKind.TRACK_USER_PRESETS,
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
            RowKind.TRACK_PRESET_SWITCHING_MODE,
            RowKind.TRACK_PRESET_SWITCHING_SCOPE,
            RowKind.TRACK_PRESET_SWITCHING_SHUFFLE,
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
        desc = RowDescriptor(kind, slot="layer_1")
        assert section_lock_blocks_mutation(_track_lock_state(True), desc) is True
        assert section_lock_blocks_mutation(_track_lock_state(False), desc) is False


def test_only_effects_header_navigable_when_section_locked() -> None:
    navigable_when_locked = {
        RowKind.TRACK_PRESET_SWITCHING,
        RowKind.TRACK_USER_PRESETS,
        RowKind.TRACK_EFFECTS_HEADER,
        RowKind.LAYER_MANAGEMENT_DELETE,
    }
    for kind in TRACK_SUB_ROW_KINDS:
        assert row_navigable_when_section_locked(kind) == (kind in navigable_when_locked)


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


def _render_lock_state(
    *, overlay: bool = False, post_fx: bool = False, timeline: bool = False
) -> SimpleNamespace:
    return SimpleNamespace(
        render_overlay=SimpleNamespace(locked=overlay),
        render_post_fx=SimpleNamespace(locked=post_fx),
        render_timeline=SimpleNamespace(locked=timeline),
    )


def test_render_value_children_blocked_by_section_lock() -> None:
    assert row_blocked_by_section_lock(RowKind.RENDER_OVERLAY_POSITION) is True
    assert row_blocked_by_section_lock(RowKind.RENDER_OVERLAY_TITLE_FONT) is True
    assert row_blocked_by_section_lock(RowKind.RENDER_POST_FX_FADE_IN) is True
    assert row_blocked_by_section_lock(RowKind.RENDER_POST_FX_CHROMA_BOOST_AMOUNT) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_PRESETS) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_BAR_PHASE) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_SNAP_TO_BARS) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_SNAP_MARKER_PROXIMITY) is True
    assert row_blocked_by_section_lock(RowKind.TIMELINE_SNAP_TO_SONG_MARKERS) is True
    assert row_blocked_by_section_lock(RowKind.SONG_MARKER_ITEM) is True
    assert row_blocked_by_section_lock(RowKind.SONG_MARKERS_HEADER) is False


def test_render_headers_navigable_when_section_locked() -> None:
    for kind in (
        RowKind.RENDER_OVERLAY_HEADER,
        RowKind.RENDER_POST_FX_HEADER,
        RowKind.RENDER_TIMELINE_HEADER,
        RowKind.RENDER_OVERLAY_TITLE_HEADER,
        RowKind.RENDER_POST_FX_CHROMA_BOOST_HEADER,
        RowKind.SONG_MARKERS_HEADER,
    ):
        assert row_navigable_when_section_locked(kind) is True
    assert row_navigable_when_section_locked(RowKind.RENDER_OVERLAY_POSITION) is False
    assert row_navigable_when_section_locked(RowKind.TIMELINE_PRESETS) is False
    assert row_navigable_when_section_locked(RowKind.SONG_MARKER_ITEM) is False


def test_section_locked_resolves_render_sections() -> None:
    overlay_desc = RowDescriptor(RowKind.RENDER_OVERLAY_POSITION)
    post_fx_desc = RowDescriptor(RowKind.RENDER_POST_FX_FADE_IN)
    timeline_desc = RowDescriptor(RowKind.TIMELINE_PRESETS)
    from cleave.viz.row_semantics import section_locked

    assert section_locked(_render_lock_state(overlay=True), overlay_desc) is True
    assert section_locked(_render_lock_state(), overlay_desc) is False
    assert section_locked(_render_lock_state(post_fx=True), post_fx_desc) is True
    assert section_locked(_render_lock_state(timeline=True), timeline_desc) is True


def test_section_locked_reads_session_timeline_attribute() -> None:
    from cleave.viz.row_semantics import section_locked

    session_like = SimpleNamespace(
        render_overlay=SimpleNamespace(locked=False),
        render_post_fx=SimpleNamespace(locked=False),
        timeline=SimpleNamespace(locked=True),
    )
    assert section_locked(session_like, RowDescriptor(RowKind.TIMELINE_PRESETS)) is True


def test_row_triggers_layer_delete_for_track_rows_only() -> None:
    assert row_triggers_layer_delete(RowKind.TRACK_HEADER) is True
    assert row_triggers_layer_delete(RowKind.LAYER_MANAGEMENT_DELETE) is True
    assert row_triggers_layer_delete(RowKind.LAYER_MANAGEMENT_ADD) is False
    assert row_triggers_layer_delete(RowKind.TRANSPORT) is False
