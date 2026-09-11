"""Project menu: config path child and Render Project submenu."""

from __future__ import annotations

from pathlib import Path

import pygame

from cleave.config_schema.project_render import (
    DEFAULT_PROJECT_RENDER_QUALITY,
    default_project_render_path,
)
from cleave.viz.material_icons import FOLDER_GLYPH
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import (
    RowPresentStyle,
    format_row_value,
    labeled_row_prefix,
    row_composite_header_display_text,
    row_full_line_display_text,
    row_spec,
)
from cleave.viz.theme import ACTION, HIGHLIGHT
from cleave.viz.tuning_panel_draw import _row_value_color
from cleave.viz.tuning_view_state import ProjectBlock, view_state_structure_signature
from tests.cleave.viz.test_controls import (
    _desc,
    _expand_project,
    _expand_project_render,
    _keydown,
    _make_controls,
)
from tests.cleave.viz.test_overlay import _minimal_view_state
from tests.support.viz import make_track_block


def test_structure_signature_invalidates_on_project_expand() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.project.expanded = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_invalidates_on_project_render_expand() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.project.expanded = True
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.project.render.expanded = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_stable_for_render_quality_and_range() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.project.render.quality = "high"
    session.project.render.start_sec = 10
    session.project.render.end_sec = 20
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before == sig_after


def test_project_children_omitted_until_expanded() -> None:
    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    kinds = [row.kind for row in view.layout.rows]
    assert RowKind.PROJECT_HEADER in kinds
    assert RowKind.CONFIG_HEADER not in kinds
    assert RowKind.PROJECT_RENDER_HEADER not in kinds

    _expand_project(controls)
    view = controls.build_view_state(paused=False)
    kinds = [row.kind for row in view.layout.rows]
    assert RowKind.CONFIG_HEADER in kinds
    assert RowKind.PROJECT_RENDER_HEADER in kinds
    assert RowKind.PROJECT_RENDER_QUALITY not in kinds


def test_project_render_children_omitted_until_expanded() -> None:
    controls = _make_controls(("layer_1",))
    _expand_project_render(controls)
    view = controls.build_view_state(paused=False)
    kinds = [row.kind for row in view.layout.rows]
    assert RowKind.PROJECT_RENDER_OUTPUT in kinds
    assert RowKind.PROJECT_RENDER_QUALITY in kinds
    assert RowKind.PROJECT_RENDER_START in kinds
    assert RowKind.PROJECT_RENDER_END in kinds
    assert RowKind.PROJECT_RENDER_ACTION in kinds


def test_project_render_defaults() -> None:
    controls = _make_controls(("layer_1",), duration_sec=120.0)
    _expand_project_render(controls)
    view = controls.build_view_state(paused=False)
    assert view.project.quality == DEFAULT_PROJECT_RENDER_QUALITY
    assert view.project.start_sec == 0
    assert view.project.end_sec == 120
    assert view.project.output_label.endswith("renders/render.mp4")
    output_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_OUTPUT)
    assert format_row_value(
        view, view.layout.descriptor(output_row)
    ) == view.project.output_label
    quality_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_QUALITY)
    assert format_row_value(view, view.layout.descriptor(quality_row)) == "normal"
    start_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_START)
    assert format_row_value(view, view.layout.descriptor(start_row)) == "0s"
    end_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_END)
    assert format_row_value(view, view.layout.descriptor(end_row)) == "120s"


def test_cycle_quality_does_not_mark_dirty() -> None:
    controls = _make_controls(("layer_1",))
    assert not controls.config_dirty
    controls.project.cycle_quality(forward=True)
    assert controls.session.project.render.quality == "high"
    controls.project.cycle_quality(forward=True)
    assert controls.session.project.render.quality == "viz"
    controls.project.cycle_quality(forward=True)
    assert controls.session.project.render.quality == "normal"
    controls.project.cycle_quality(forward=False)
    assert controls.session.project.render.quality == "viz"
    assert not controls.config_dirty


def test_adjust_start_and_end_steps_and_clamps() -> None:
    controls = _make_controls(("layer_1",), duration_sec=60.0)
    render = controls.session.project.render
    assert render.start_sec == 0
    assert render.end_sec is None

    controls.project.adjust_start(forward=True, ctrl=False)
    assert render.start_sec == 1
    controls.project.adjust_start(forward=True, ctrl=True)
    assert render.start_sec == 11

    controls.project.adjust_end(forward=False, ctrl=False)
    assert render.end_sec == 59
    controls.project.adjust_end(forward=False, ctrl=True)
    assert render.end_sec == 49

    render.start_sec = 48
    controls.project.adjust_start(forward=True, ctrl=True)
    assert render.start_sec == 48
    controls.project.adjust_end(forward=True, ctrl=True)
    assert render.end_sec == 59
    controls.project.adjust_end(forward=True, ctrl=False)
    assert render.end_sec is None
    assert not controls.config_dirty


def test_output_path_uses_project_renders_dir_and_range_suffix(
    tmp_path: Path,
) -> None:
    controls = _make_controls(
        ("layer_1",), project_dir=tmp_path, duration_sec=60.0
    )
    _expand_project_render(controls)
    view = controls.build_view_state(paused=False)
    assert view.project.output_label == (tmp_path / "renders" / "render.mp4").as_posix()

    controls.session.project.render.start_sec = 10
    controls.session.project.render.end_sec = 20
    view = controls.build_view_state(paused=False)
    expected = default_project_render_path(
        tmp_path, "render", start_sec=10, end_sec=20, duration_sec=60.0
    )
    assert view.project.output_label == expected.as_posix()
    assert view.project.output_label.endswith("render_10-20s.mp4")


def test_render_action_is_green_button_with_enter_icon() -> None:
    controls = _make_controls(("layer_1",))
    _expand_project_render(controls)
    view = controls.build_view_state(paused=False)
    action_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_ACTION)
    spec = row_spec(RowKind.PROJECT_RENDER_ACTION)
    assert spec.shows_enter_icon is True
    assert _row_value_color(view, action_row) == ACTION
    view.focus_descriptor = view.layout.descriptor(action_row)
    assert _row_value_color(view, action_row) == HIGHLIGHT
    controls.focus_descriptor = _desc(view, action_row)
    assert controls.handle_keydown(_keydown(pygame.K_RETURN)) is True


def test_left_right_on_headers_toggles_expand() -> None:
    controls = _make_controls(("layer_1",))
    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.project.expanded is True
    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_RENDER_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.project.render.expanded is True
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.project.render.expanded is False
    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_HEADER)
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.project.expanded is False


def test_minimal_view_render_labels() -> None:
    state = _minimal_view_state(
        project=ProjectBlock(
            expanded=True,
            render_expanded=True,
            quality="high",
            start_sec=5,
            end_sec=40,
            output_label="renders/demo_5-40s.mp4",
        ),
        tracks={
            "layer_1": make_track_block(
                stem="drums",
                preset_dir_label="dir",
                preset_label="preset.milk",
                blend_mode="black-key",
                opacity_pct=50,
                beat_sensitivity=1.0,
                effects={},
            )
        },
    )
    assert labeled_row_prefix(RowKind.PROJECT_RENDER_QUALITY) == "  └─ quality: "
    quality = state.layout.find_by_kind(RowKind.PROJECT_RENDER_QUALITY)
    assert format_row_value(state, state.layout.descriptor(quality)) == "high"
    output = state.layout.find_by_kind(RowKind.PROJECT_RENDER_OUTPUT)
    assert (
        format_row_value(state, state.layout.descriptor(output))
        == "renders/demo_5-40s.mp4"
    )
    action = state.layout.find_by_kind(RowKind.PROJECT_RENDER_ACTION)
    assert (
        row_full_line_display_text(state, state.layout.descriptor(action))
        == "  └─ render the project"
    )
    project = state.layout.find_by_kind(RowKind.PROJECT_HEADER)
    assert (
        row_composite_header_display_text(state, state.layout.descriptor(project))
        == "Project ▼"
    )


def test_render_output_row_is_read_only() -> None:
    spec = row_spec(RowKind.PROJECT_RENDER_OUTPUT)
    assert spec.affordance == RowAffordance.DISPLAY
    assert spec.apply_horizontal is None
    assert spec.present_style == RowPresentStyle.PATH_ICON
    project_spec = row_spec(RowKind.PROJECT_HEADER)
    assert project_spec.header_glyph == FOLDER_GLYPH


def test_start_end_keyboard_steps() -> None:
    controls = _make_controls(("layer_1",), duration_sec=60.0)
    _expand_project_render(controls)
    view = controls.build_view_state(paused=False)
    start_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_START)
    end_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_END)
    render = controls.session.project.render

    controls.focus_descriptor = _desc(view, start_row)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert render.start_sec == 1
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert render.start_sec == 11

    controls.focus_descriptor = _desc(view, end_row)
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert render.end_sec == 59
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert render.end_sec == 49

