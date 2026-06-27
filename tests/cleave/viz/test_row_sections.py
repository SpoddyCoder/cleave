"""Tests for expandable section composition in row_sections."""

from __future__ import annotations

from cleave.viz.row_layout import row_draw_visible
from cleave.viz.row_sections import (
    RENDER_OVERLAY_SECTION_KINDS,
    section_header_from_section_tree,
    sub_row_expand_visible,
)
from cleave.viz.row_semantics import RowDescriptor, RowKind, section_header_descriptor
from cleave.viz.tuning_view_state import (
    RenderOverlayBlock,
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
        preset_switching_expanded=True,
        hard_cut_enabled=True,
    )
    base.update(overrides)
    return TrackBlock(**base)  # type: ignore[arg-type]


def test_sub_row_expand_visible_nested_sections() -> None:
    collapsed_settings = _minimal_view_state(settings=SettingsBlock(expanded=False))
    render_mode = RowDescriptor(RowKind.SETTINGS_RENDER_MODE)
    assert sub_row_expand_visible(collapsed_settings, render_mode) is False

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
    scope = RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_SCOPE, slot="layer_1")
    assert section_header_from_section_tree(scope) == RowDescriptor(
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


def test_render_overlay_section_kinds_from_tree() -> None:
    assert RowKind.RENDER_OVERLAY_HEADER in RENDER_OVERLAY_SECTION_KINDS
    assert RowKind.RENDER_OVERLAY_TITLE_FONT in RENDER_OVERLAY_SECTION_KINDS
    assert RowKind.RENDER_OVERLAY_BODY_FONT in RENDER_OVERLAY_SECTION_KINDS
