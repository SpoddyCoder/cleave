"""Tests for expandable section composition in row_sections."""

from __future__ import annotations

from cleave.effects.registry import effect_roster
from cleave.viz.row_layout import row_draw_visible
from cleave.viz.row_sections import (
    RENDER_OVERLAY_SECTION,
    RENDER_OVERLAY_SECTION_KINDS,
    RENDER_POST_FX_SECTION,
    append_track_section_rows,
    expand_section_expanded,
    section_header_from_section_tree,
    sub_row_expand_visible,
)
from cleave.viz.row_semantics import RowDescriptor, RowKind, section_header_descriptor
from cleave.viz.tuning_view_state import (
    HighlightRolloffBlock,
    RenderOverlayBlock,
    RenderPostFxBlock,
    SettingsBlock,
    TrackBlock,
)
from tests.cleave.viz.test_overlay import _minimal_view_state


def _track_block(**overrides: object) -> TrackBlock:
    base = dict(
        stem="drums",
        preset_dir_label="dir",
        preset_label="preset.milk",
        blend_mode="black-key",
        opacity_pct=50,
        beat_sensitivity=1.0,
        effects={},
        expanded=True,
        preset_switching="projectm",
        hard_cut_enabled=True,
    )
    base.update(overrides)
    return TrackBlock(**base)  # type: ignore[arg-type]


def _track_row_kinds(**overrides: object) -> list[RowKind]:
    state = _minimal_view_state(tracks={"layer_1": _track_block(**overrides)})
    rows: list[RowDescriptor] = []
    append_track_section_rows(rows, state, "layer_1")
    return [row.kind for row in rows]


def test_track_layout_collapsed_layer() -> None:
    assert _track_row_kinds(expanded=False) == [RowKind.TRACK_HEADER]


def test_track_layout_collapsed_preset_switching() -> None:
    kinds = _track_row_kinds(preset_switching="none")
    assert RowKind.TRACK_PRESET_SWITCHING in kinds
    assert RowKind.TRACK_PRESET_SWITCHING_ROTATION_SET not in kinds
    assert RowKind.TRACK_PRESET_DURATION not in kinds


def test_track_layout_collapsed_effects() -> None:
    kinds = _track_row_kinds(effects_expanded=False)
    assert RowKind.TRACK_EFFECTS_HEADER in kinds
    assert RowKind.TRACK_EFFECT not in kinds


def test_track_layout_conditional_rows_when_predicates_pass() -> None:
    kinds = _track_row_kinds(
        preset_switching="projectm",
        hard_cut_enabled=True,
        effects_expanded=False,
    )
    assert RowKind.TRACK_PRESET_DURATION in kinds
    assert RowKind.TRACK_PRESET_SWITCHING_SHUFFLE in kinds
    assert RowKind.TRACK_HARD_CUT_DURATION in kinds

    user_defined_kinds = _track_row_kinds(
        preset_switching="projectm",
        preset_switching_rotation_set="user_defined",
        hard_cut_enabled=True,
        effects_expanded=False,
    )
    assert RowKind.TRACK_SOFT_CUT_DURATION in user_defined_kinds
    assert RowKind.TRACK_PRESET_SWITCHING_SHUFFLE in user_defined_kinds
    assert RowKind.TRACK_HARD_CUT_ENABLED in user_defined_kinds
    assert RowKind.TRACK_HARD_CUT_DURATION in user_defined_kinds
    assert RowKind.TRACK_PRESET_SWITCHING_ROTATION_SET in user_defined_kinds
    assert RowKind.TRACK_USER_PRESETS in user_defined_kinds


def test_track_layout_omits_conditional_rows_when_predicates_fail() -> None:
    none_kinds = _track_row_kinds(preset_switching="none")
    assert RowKind.TRACK_PRESET_DURATION not in none_kinds
    assert RowKind.TRACK_PRESET_SWITCHING_SHUFFLE not in none_kinds

    hard_cut_off = _track_row_kinds(hard_cut_enabled=False)
    assert RowKind.TRACK_HARD_CUT_DURATION not in hard_cut_off


def test_track_layout_effect_roster_when_expanded() -> None:
    kinds = _track_row_kinds(effects_expanded=True)
    effect_rows = [kind for kind in kinds if kind == RowKind.TRACK_EFFECT]
    assert len(effect_rows) == len(effect_roster("drums"))


def test_track_layout_row_order_when_fully_expanded() -> None:
    kinds = _track_row_kinds(effects_expanded=True)
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
        RowKind.TRACK_PRESET_SWITCHING_ROTATION_SET,
        RowKind.TRACK_PRESET_SWITCHING_SHUFFLE,
        RowKind.TRACK_PRESET_DURATION,
        RowKind.TRACK_EASTER_EGG,
        RowKind.TRACK_SOFT_CUT_DURATION,
        RowKind.TRACK_PRESET_START_CLEAN,
        RowKind.TRACK_HARD_CUT_ENABLED,
        RowKind.TRACK_HARD_CUT_DURATION,
        RowKind.TRACK_HARD_CUT_SENSITIVITY,
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
        RowKind.TRACK_EFFECTS_HEADER,
    ]
    assert kinds[delete_idx] == RowKind.LAYER_MANAGEMENT_DELETE
    assert all(kind == RowKind.TRACK_EFFECT for kind in kinds[effects_header + 1 : delete_idx])


def test_expand_section_respects_expanded_when_block_disabled() -> None:
    disabled_overlay = _minimal_view_state(
        render_overlay=RenderOverlayBlock(enabled=False, expanded=True),
    )
    assert expand_section_expanded(disabled_overlay, RENDER_OVERLAY_SECTION, None) is True
    opacity = RowDescriptor(RowKind.RENDER_OVERLAY_OPACITY)
    assert sub_row_expand_visible(disabled_overlay, opacity) is True

    disabled_post_fx = _minimal_view_state(
        render_post_fx=RenderPostFxBlock(enabled=False, expanded=True),
    )
    assert expand_section_expanded(disabled_post_fx, RENDER_POST_FX_SECTION, None) is True


def test_sub_row_expand_visible_nested_sections() -> None:
    collapsed_settings = _minimal_view_state(settings=SettingsBlock(expanded=False))
    render_mode = RowDescriptor(RowKind.SETTINGS_PREVIEW_QUALITY)
    assert sub_row_expand_visible(collapsed_settings, render_mode) is False

    settings_only = _minimal_view_state(settings=SettingsBlock(expanded=True, ui_expanded=False))
    ui_width = RowDescriptor(RowKind.SETTINGS_UI_WIDTH)
    assert sub_row_expand_visible(settings_only, ui_width) is False

    collapsed_overlay = _minimal_view_state(
        render_overlay=RenderOverlayBlock(expanded=False),
    )
    opacity = RowDescriptor(RowKind.RENDER_OVERLAY_OPACITY)
    assert sub_row_expand_visible(collapsed_overlay, opacity) is False

    title_collapsed = _minimal_view_state(
        render_overlay=RenderOverlayBlock(expanded=True, title_expanded=False),
    )
    title_font = RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_FONT)
    assert sub_row_expand_visible(title_collapsed, title_font) is False

    highlight_collapsed = _minimal_view_state(
        render_post_fx=RenderPostFxBlock(
            expanded=True,
            highlight_rolloff=HighlightRolloffBlock(expanded=False),
        ),
    )
    threshold = RowDescriptor(RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD)
    assert sub_row_expand_visible(highlight_collapsed, threshold) is False

    layer_collapsed = _minimal_view_state(
        tracks={"layer_1": _track_block(expanded=False)},
    )
    stem = RowDescriptor(RowKind.TRACK_STEM, slot="layer_1")
    assert sub_row_expand_visible(layer_collapsed, stem) is False


def test_layout_omits_conditional_rows_when_predicate_fails() -> None:
    none_mode = _minimal_view_state(
        tracks={"layer_1": _track_block(preset_switching="none")},
    )
    duration = RowDescriptor(RowKind.TRACK_PRESET_DURATION, slot="layer_1")
    assert duration not in none_mode.layout.rows

    hard_cut_off = _minimal_view_state(
        tracks={"layer_1": _track_block(hard_cut_enabled=False)},
    )
    hard_cut_min = RowDescriptor(RowKind.TRACK_HARD_CUT_DURATION, slot="layer_1")
    assert hard_cut_min not in hard_cut_off.layout.rows


def test_layout_includes_conditional_rows_when_predicates_pass() -> None:
    projectm = _minimal_view_state(tracks={"layer_1": _track_block()})
    duration = RowDescriptor(RowKind.TRACK_PRESET_DURATION, slot="layer_1")
    hard_cut_min = RowDescriptor(RowKind.TRACK_HARD_CUT_DURATION, slot="layer_1")
    assert duration in projectm.layout.rows
    assert hard_cut_min in projectm.layout.rows
    assert row_draw_visible(projectm, duration) is True
    assert row_draw_visible(projectm, hard_cut_min) is True


def test_section_header_from_tree_preset_switching_submenu() -> None:
    rotation_set = RowDescriptor(
        RowKind.TRACK_PRESET_SWITCHING_ROTATION_SET, slot="layer_1"
    )
    assert section_header_from_section_tree(rotation_set) == RowDescriptor(
        RowKind.TRACK_PRESET_SWITCHING, slot="layer_1"
    )
    hard_cut = RowDescriptor(RowKind.TRACK_HARD_CUT_SENSITIVITY, slot="layer_1")
    assert section_header_from_section_tree(hard_cut) == RowDescriptor(
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
        RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_FONT)
    ) == RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_HEADER)
    assert section_header_descriptor(
        RowDescriptor(RowKind.SETTINGS_UI_FADE)
    ) == RowDescriptor(RowKind.SETTINGS_UI_HEADER)


def test_render_overlay_section_kinds_from_tree() -> None:
    assert RowKind.RENDER_OVERLAY_HEADER in RENDER_OVERLAY_SECTION_KINDS
    assert RowKind.RENDER_OVERLAY_TITLE_FONT in RENDER_OVERLAY_SECTION_KINDS
    assert RowKind.RENDER_OVERLAY_BODY_FONT in RENDER_OVERLAY_SECTION_KINDS
