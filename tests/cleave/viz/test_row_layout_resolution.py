"""Tests for RowLayout descriptor resolution helpers."""

from __future__ import annotations

import pytest

from cleave.viz.tuning_view_state import (
    RenderOverlayBlock,
    RenderPostFxBlock,
    SettingsBlock,
    TrackBlock,
    TuningViewState,
)
from cleave.viz.row_semantics import RowDescriptor, RowKind, section_header_descriptor
from tests.cleave.viz.test_overlay import _minimal_view_state


def test_find_descriptor_and_contains_descriptor() -> None:
    state = _minimal_view_state()
    desc = RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    assert state.layout.contains_descriptor(desc)
    assert state.layout.find_descriptor(desc) == state.layout.find("layer_1", RowKind.TRACK_HEADER)


def test_find_descriptor_raises_when_missing() -> None:
    state = _minimal_view_state()
    missing = RowDescriptor(RowKind.TRACK_EFFECT, slot="layer_1", effect_id="pulse", driver_slug="onset")
    assert not state.layout.contains_descriptor(missing)
    with pytest.raises(ValueError, match="descriptor not in layout"):
        state.layout.find_descriptor(missing)


def test_navigable_descriptors_matches_indices() -> None:
    state = _minimal_view_state(
        tracks={
            "layer_1": TrackBlock(
                stem="drums",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                expanded=True,
            )
        },
    )
    indices = state.layout.navigable_indices(state)
    descriptors = state.layout.navigable_descriptors(state)
    assert descriptors == [state.layout.descriptor(index) for index in indices]


def test_resolve_navigable_returns_descriptor_when_navigable() -> None:
    state = _minimal_view_state()
    transport = RowDescriptor(RowKind.TRANSPORT)
    assert state.layout.resolve_navigable(transport, state) == transport


def test_resolve_navigable_settings_render_mode_collapsed() -> None:
    state = _minimal_view_state(settings=SettingsBlock(expanded=False))
    render_mode = RowDescriptor(RowKind.SETTINGS_RENDER_MODE)
    assert render_mode not in state.layout.navigable_descriptors(state)
    assert state.layout.resolve_navigable(render_mode, state) == RowDescriptor(
        RowKind.SETTINGS_HEADER
    )


def test_resolve_navigable_track_sub_row_collapsed_block() -> None:
    state = _minimal_view_state()
    stem = RowDescriptor(RowKind.TRACK_STEM, slot="layer_1")
    assert stem not in state.layout.navigable_descriptors(state)
    assert state.layout.resolve_navigable(stem, state) == RowDescriptor(
        RowKind.TRACK_HEADER, slot="layer_1"
    )


def test_resolve_navigable_track_effect_collapsed_effects() -> None:
    state = _minimal_view_state(
        tracks={
            "layer_1": TrackBlock(
                stem="drums",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
                expanded=True,
                effects_expanded=False,
            )
        },
    )
    effect = RowDescriptor(
        RowKind.TRACK_EFFECT, slot="layer_1", effect_id="pulse", driver_slug="onset"
    )
    assert effect not in state.layout.rows
    assert state.layout.resolve_navigable(effect, state) == RowDescriptor(
        RowKind.TRACK_EFFECTS_HEADER, slot="layer_1"
    )


def test_resolve_navigable_render_overlay_sub_row_collapsed() -> None:
    state = _minimal_view_state(render_overlay=RenderOverlayBlock(expanded=False))
    opacity = RowDescriptor(RowKind.RENDER_OVERLAY_OPACITY)
    assert opacity not in state.layout.rows
    assert state.layout.resolve_navigable(opacity, state) == RowDescriptor(
        RowKind.RENDER_OVERLAY_HEADER
    )


def test_resolve_navigable_render_overlay_title_nested_collapsed() -> None:
    state = _minimal_view_state(
        render_overlay=RenderOverlayBlock(expanded=True, title_expanded=False),
    )
    font = RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_FONT)
    assert font not in state.layout.rows
    title_header = RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_HEADER)
    assert state.layout.resolve_navigable(font, state) == title_header


def test_resolve_navigable_render_post_fx_sub_row_collapsed() -> None:
    state = _minimal_view_state(render_post_fx=RenderPostFxBlock(expanded=False))
    fade_in = RowDescriptor(RowKind.RENDER_POST_FX_FADE_IN)
    assert fade_in not in state.layout.rows
    assert state.layout.resolve_navigable(fade_in, state) == RowDescriptor(
        RowKind.RENDER_POST_FX_HEADER
    )


def test_section_header_descriptor_mappings() -> None:
    assert section_header_descriptor(RowDescriptor(RowKind.SETTINGS_RENDER_MODE)) == RowDescriptor(
        RowKind.SETTINGS_HEADER
    )
    assert section_header_descriptor(
        RowDescriptor(RowKind.RENDER_OVERLAY_OPACITY)
    ) == RowDescriptor(RowKind.RENDER_OVERLAY_HEADER)
    assert section_header_descriptor(
        RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_FONT)
    ) == RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_HEADER)
    assert section_header_descriptor(
        RowDescriptor(RowKind.RENDER_OVERLAY_BODY_FONT)
    ) == RowDescriptor(RowKind.RENDER_OVERLAY_BODY_HEADER)
    assert section_header_descriptor(RowDescriptor(RowKind.RENDER_POST_FX_FADE_OUT)) == RowDescriptor(
        RowKind.RENDER_POST_FX_HEADER
    )
    assert section_header_descriptor(
        RowDescriptor(RowKind.TRACK_STEM, slot="layer_1")
    ) == RowDescriptor(RowKind.TRACK_HEADER, slot="layer_1")
    assert section_header_descriptor(
        RowDescriptor(
            RowKind.TRACK_EFFECT, slot="layer_1", effect_id="pulse", driver_slug="onset"
        )
    ) == RowDescriptor(RowKind.TRACK_EFFECTS_HEADER, slot="layer_1")
    assert section_header_descriptor(
        RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_SCOPE, slot="layer_1")
    ) == RowDescriptor(RowKind.TRACK_PRESET_SWITCHING, slot="layer_1")
    assert section_header_descriptor(
        RowDescriptor(RowKind.TRACK_PRESET_DURATION, slot="layer_1")
    ) == RowDescriptor(RowKind.TRACK_PRESET_SWITCHING, slot="layer_1")
