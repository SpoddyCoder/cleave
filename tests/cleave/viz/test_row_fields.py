"""Tests for row_fields panel manifest."""

from __future__ import annotations

import inspect

import pygame

from cleave.config_schema import ui_fade_display
from cleave.viz.row_fields import (
    ROW_FIELDS,
    RowPresentStyle,
    apply_field_horizontal,
    composite_header_prefix_part,
    composite_header_suffix_part,
    expand_subheader_prefix,
    format_row_value,
    full_line_prefix,
    labeled_row_prefix,
    row_composite_header_display_text,
    row_dynamic_labeled_display_text,
    row_dynamic_labeled_prefix,
    row_expand_subheader_display_text,
    row_field_def,
    row_full_line_display_text,
    row_kinds_requiring_fields,
    row_labeled_display_text,
    row_panel_label,
    tree_branch_prefix,
)
from cleave.viz.row_semantics import RowDescriptor, RowKind
from cleave.viz.tuning_view_state import (
    RenderOverlayBlock,
    RenderPostFxBlock,
    SettingsBlock,
    TrackBlock,
)
from tests.cleave.viz.test_controls import (
    _keydown,
    _make_controls,
    _make_controls_with_manager,
)
from tests.support.config import TEST_LAYER_STEMS
from tests.support.viz import noop_layer_bindings
from tests.cleave.viz.test_overlay import _minimal_view_state


def test_tree_branch_prefix() -> None:
    assert tree_branch_prefix(0) == ""
    assert tree_branch_prefix(1) == "└─ "
    assert tree_branch_prefix(2) == "  └─ "


def test_row_panel_label_settings_header() -> None:
    assert row_panel_label(RowKind.SETTINGS_HEADER) == "Editor Settings"


def test_labeled_row_prefix_settings_children() -> None:
    assert labeled_row_prefix(RowKind.SETTINGS_RENDER_MODE) == "└─ render mode: "
    assert labeled_row_prefix(RowKind.SETTINGS_UI_WIDTH_MODE) == "  └─ width mode: "
    assert labeled_row_prefix(RowKind.SETTINGS_UI_WIDTH) == "  └─ max width: "
    assert labeled_row_prefix(RowKind.SETTINGS_UI_FADE) == "  └─ auto-fade: "


def test_labeled_row_prefix_track_depths() -> None:
    assert labeled_row_prefix(RowKind.TRACK_STEM) == "└─ driving stem: "
    assert labeled_row_prefix(RowKind.TRACK_PRESET_SWITCHING_MODE) == "  └─ switching mode: "


def test_format_row_value_settings() -> None:
    state = _minimal_view_state(
        settings=SettingsBlock(
            render_mode="performance",
            ui_width_mode="fixed",
            ui_width=320,
            ui_fade=0.0,
        ),
    )
    assert (
        format_row_value(state, RowDescriptor(RowKind.SETTINGS_RENDER_MODE))
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
            "layer_1": TrackBlock(
                stem=TEST_LAYER_STEMS["layer_1"],
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="add",
                opacity_pct=75,
                beat_sensitivity=1.25,
                effects={},
                preset_switching="projectm",
                preset_duration=45.0,
            )
        },
        render_overlay=RenderOverlayBlock(position="top-left", opacity_pct=80),
        render_post_fx=RenderPostFxBlock(fade_in=2.5, fade_out=3.0),
    )
    slot_desc = RowDescriptor(RowKind.TRACK_BLEND, slot="layer_1")
    assert format_row_value(state, slot_desc) == "add"
    mode_desc = RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_MODE, slot="layer_1")
    assert format_row_value(state, mode_desc) == "projectM"
    duration_desc = RowDescriptor(RowKind.TRACK_PRESET_DURATION, slot="layer_1")
    assert format_row_value(state, duration_desc) == "45s"
    assert format_row_value(state, RowDescriptor(RowKind.RENDER_OVERLAY_POSITION)) == (
        "top-left"
    )
    assert (
        format_row_value(state, RowDescriptor(RowKind.RENDER_OVERLAY_OPACITY)) == "80%"
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
        settings=SettingsBlock(render_mode="balanced", ui_fade=11.0),
    )
    desc = RowDescriptor(RowKind.SETTINGS_RENDER_MODE)
    assert row_labeled_display_text(state, desc) == "└─ render mode: balanced"
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


def test_apply_field_horizontal_cycles_render_mode() -> None:
    controls = _make_controls()
    desc = RowDescriptor(RowKind.SETTINGS_RENDER_MODE)
    assert controls.cfg.visualizer.render_mode == "balanced"

    assert apply_field_horizontal(controls, desc, True, False) is True
    assert controls.cfg.visualizer.render_mode == "performance"

    apply_field_horizontal(controls, desc, False, False)
    assert controls.cfg.visualizer.render_mode == "balanced"


def test_apply_field_horizontal_render_mode_calls_preview_resolutions() -> None:
    controls, layer_manager = _make_controls_with_manager()
    desc = RowDescriptor(RowKind.SETTINGS_RENDER_MODE)

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
    desc = RowDescriptor(RowKind.RENDER_OVERLAY_OPACITY)
    before = controls.session.render_overlay.opacity_pct

    assert apply_field_horizontal(controls, desc, True, False) is True
    assert controls.session.render_overlay.opacity_pct == before + 1


def test_apply_field_horizontal_adjusts_ui_fade() -> None:
    controls = _make_controls()
    desc = RowDescriptor(RowKind.SETTINGS_UI_FADE)
    assert controls.cfg.visualizer.ui_fade == 10.0

    apply_field_horizontal(controls, desc, True, False)
    assert controls.cfg.visualizer.ui_fade == 11.0

    apply_field_horizontal(controls, desc, False, True)
    assert controls.cfg.visualizer.ui_fade == 6.0


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
    assert controls.cfg.visualizer.ui_width_mode == "fixed"


def test_expand_subheader_prefix_preset_switching() -> None:
    assert (
        expand_subheader_prefix(RowKind.TRACK_PRESET_SWITCHING)
        == "└─ preset switching "
    )
    assert expand_subheader_prefix(RowKind.RENDER_OVERLAY_TITLE_HEADER) == "└─ title "
    assert (
        expand_subheader_prefix(RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_HEADER)
        == "└─ highlight rolloff "
    )
    assert expand_subheader_prefix(RowKind.SETTINGS_UI_HEADER) == "└─ UI "


def test_row_expand_subheader_display_text() -> None:
    state = _minimal_view_state()
    desc = RowDescriptor(RowKind.TRACK_PRESET_SWITCHING, slot="layer_1")
    assert row_expand_subheader_display_text(state, desc) == "└─ preset switching ▶"


def test_composite_header_render_overlay_metadata() -> None:
    field = row_field_def(RowKind.RENDER_OVERLAY_HEADER)
    assert field.present_style == RowPresentStyle.COMPOSITE_HEADER
    assert field.header_prefix == "Render: "
    assert field.header_suffix == "OVERLAY"

    state = _minimal_view_state()
    desc = RowDescriptor(RowKind.RENDER_OVERLAY_HEADER)
    assert composite_header_prefix_part(state, desc) == "Render: "
    assert composite_header_suffix_part(state, desc) == "OVERLAY"
    assert row_composite_header_display_text(state, desc) == "Render: OVERLAY ▶"


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


def test_row_fields_count() -> None:
        assert len(ROW_FIELDS) == 62


def test_row_kinds_requiring_fields_registry_complete() -> None:
    required = row_kinds_requiring_fields()
    assert required == frozenset(ROW_FIELDS.keys())
    assert RowKind.RENDER_SECTION_GAP not in ROW_FIELDS


def test_row_field_apply_horizontal_signatures_match_field_mutator() -> None:
    mismatches: list[str] = []
    for kind, field in ROW_FIELDS.items():
        handler = field.apply_horizontal
        if handler is None:
            continue
        param_count = len(inspect.signature(handler).parameters)
        if param_count != 5:
            mismatches.append(
                f"{kind.name} ({handler.__name__}): {param_count} params, expected 5"
            )
    assert not mismatches, "FieldMutator arity mismatches:\n" + "\n".join(mismatches)


def test_format_row_value_path_icon() -> None:
    state = _minimal_view_state(
        active_config_label="projects/demo/cleave-viz.yaml",
        tracks={
            "layer_1": TrackBlock(
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
            "layer_1": TrackBlock(
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


def test_apply_field_horizontal_transport_seeks() -> None:
    from cleave.viz.controls import SEEK_LONG, SEEK_SHORT

    controls = _make_controls()
    controls.duration_sec = 120.0
    seeks: list[float] = []
    controls._layer_bindings = noop_layer_bindings(
        on_seek=lambda delta: seeks.append(delta)
    )
    desc = RowDescriptor(RowKind.TRANSPORT)

    apply_field_horizontal(controls, desc, True, False)
    apply_field_horizontal(controls, desc, False, False)
    apply_field_horizontal(controls, desc, True, True)
    apply_field_horizontal(controls, desc, False, True)

    assert seeks == [SEEK_SHORT, -SEEK_SHORT, SEEK_LONG, -SEEK_LONG]
