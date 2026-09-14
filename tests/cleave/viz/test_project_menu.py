"""Project menu: config path child and Render Project submenu."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pygame
import pytest

from cleave.config_schema.editor import DEFAULT_BEAT_SENSITIVITY
from cleave.config_schema.project_render import (
    DEFAULT_PROJECT_RENDER_QUALITY,
    DEFAULT_RENDER_FPS,
    DEFAULT_RENDER_HEIGHT,
    DEFAULT_RENDER_WIDTH,
    default_project_render_path,
)
from cleave.viz.material_icons import FOLDER_GLYPH
from cleave.viz.modal import ModalKind, ModalLabeledLine
from cleave.viz.project_render_job import RenderJobStatus
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import (
    RowPresentStyle,
    format_row_value,
    labeled_row_prefix,
    row_composite_header_display_text,
    row_full_line_display_text,
    row_spec,
)
from cleave.viz.theme import ACTION, HIGHLIGHT, PRESET_ICON
from cleave.viz.tuning_panel_draw import _row_value_color
from cleave.viz.tuning_view_state import ProjectBlock, view_state_structure_signature
from tests.cleave.viz.test_controls import (
    _choose_modal_option,
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
    session.project.render.width = 1280
    session.project.render.height = 720
    session.project.render.fps = 24
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
    assert RowKind.PROJECT_MILKDROP_HEADER not in kinds
    assert RowKind.PROJECT_COMPOSITOR_HEADER not in kinds
    assert RowKind.PROJECT_RENDER_HEADER not in kinds

    _expand_project(controls)
    view = controls.build_view_state(paused=False)
    kinds = [row.kind for row in view.layout.rows]
    assert RowKind.CONFIG_HEADER in kinds
    assert RowKind.PROJECT_MILKDROP_HEADER in kinds
    assert RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY not in kinds
    assert RowKind.PROJECT_COMPOSITOR_HEADER in kinds
    assert RowKind.PROJECT_COMPOSITOR_HDR not in kinds
    assert RowKind.PROJECT_RENDER_HEADER in kinds
    assert RowKind.PROJECT_RENDER_QUALITY not in kinds


def test_project_render_children_omitted_until_expanded() -> None:
    controls = _make_controls(("layer_1",))
    _expand_project_render(controls)
    view = controls.build_view_state(paused=False)
    kinds = [row.kind for row in view.layout.rows]
    assert RowKind.PROJECT_RENDER_OUTPUT in kinds
    assert RowKind.PROJECT_RENDER_WIDTH in kinds
    assert RowKind.PROJECT_RENDER_HEIGHT in kinds
    assert RowKind.PROJECT_RENDER_FPS in kinds
    assert RowKind.PROJECT_RENDER_QUALITY in kinds
    assert RowKind.PROJECT_RENDER_START in kinds
    assert RowKind.PROJECT_RENDER_END in kinds
    assert RowKind.PROJECT_RENDER_ACTION in kinds


def test_project_milkdrop_children_omitted_until_expanded() -> None:
    controls = _make_controls(("layer_1",))
    _expand_project(controls)
    view = controls.build_view_state(paused=False)
    kinds = [row.kind for row in view.layout.rows]
    assert RowKind.PROJECT_MILKDROP_HEADER in kinds
    assert RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY not in kinds

    controls.session.project.milkdrop_expanded = True
    view = controls.build_view_state(paused=False)
    kinds = [row.kind for row in view.layout.rows]
    assert RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY in kinds
    beat_row = view.layout.find_by_kind(RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY)
    assert format_row_value(view, view.layout.descriptor(beat_row)) == (
        f"{DEFAULT_BEAT_SENSITIVITY:.2f}"
    )


def test_structure_signature_invalidates_on_project_compositor_expand() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    session.project.expanded = True
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.project.compositor_expanded = True
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before != sig_after


def test_structure_signature_stable_for_compositor_hdr() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    sig_before = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    session.project.compositor_hdr = False
    sig_after = view_state_structure_signature(
        session, config_save, notification_active=False
    )
    assert sig_before == sig_after


def test_project_compositor_children_omitted_until_expanded() -> None:
    controls = _make_controls(("layer_1",))
    _expand_project(controls)
    view = controls.build_view_state(paused=False)
    kinds = [row.kind for row in view.layout.rows]
    assert RowKind.PROJECT_COMPOSITOR_HEADER in kinds
    assert RowKind.PROJECT_COMPOSITOR_HDR not in kinds

    controls.session.project.compositor_expanded = True
    view = controls.build_view_state(paused=False)
    kinds = [row.kind for row in view.layout.rows]
    assert RowKind.PROJECT_COMPOSITOR_HDR in kinds
    hdr_row = view.layout.find_by_kind(RowKind.PROJECT_COMPOSITOR_HDR)
    assert format_row_value(view, view.layout.descriptor(hdr_row)) == "on"


def test_compositor_hdr_keyboard_toggles() -> None:
    controls = _make_controls(("layer_1",))
    _expand_project(controls)
    controls.session.project.compositor_expanded = True
    view = controls.build_view_state(paused=False)
    hdr_row = view.layout.find_by_kind(RowKind.PROJECT_COMPOSITOR_HDR)
    controls.focus_descriptor = view.layout.descriptor(hdr_row)
    assert controls.session.project.compositor_hdr is True
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.project.compositor_hdr is False
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.project.compositor_hdr is True


def test_compositor_hdr_toggle_resyncs_live_format() -> None:
    from unittest.mock import MagicMock

    from cleave.gl_color_format import RGBA8, RGBA16F

    controls = _make_controls(("layer_1",))
    compositor = MagicMock()
    post_process = MagicMock()
    controls._compositor = compositor
    controls._post_process = post_process
    controls.session.project.compositor_hdr = True
    controls.project.toggle_compositor_hdr()
    assert controls.session.project.compositor_hdr is False
    compositor.set_color_format.assert_called_with(RGBA8)
    post_process.set_color_format.assert_called_with(RGBA8)
    compositor.reset_mock()
    post_process.reset_mock()
    controls.project.toggle_compositor_hdr()
    compositor.set_color_format.assert_called_with(RGBA16F)
    post_process.set_color_format.assert_called_with(RGBA16F)


def test_compositor_header_is_expand_only() -> None:
    spec = row_spec(RowKind.PROJECT_COMPOSITOR_HEADER)
    assert spec.can_enable_disable is False
    assert spec.affordance == RowAffordance.EXPAND


def test_milkdrop_beat_sensitivity_keyboard_steps() -> None:
    controls = _make_controls(("layer_1",))
    _expand_project(controls)
    controls.session.project.milkdrop_expanded = True
    view = controls.build_view_state(paused=False)
    beat_row = view.layout.find_by_kind(RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY)
    controls.focus_descriptor = view.layout.descriptor(beat_row)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.project.milkdrop_beat_sensitivity == pytest.approx(
        DEFAULT_BEAT_SENSITIVITY + 0.1
    )
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert controls.session.project.milkdrop_beat_sensitivity == pytest.approx(
        DEFAULT_BEAT_SENSITIVITY + 0.6
    )
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.project.milkdrop_beat_sensitivity == pytest.approx(
        DEFAULT_BEAT_SENSITIVITY + 0.5
    )
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert controls.session.project.milkdrop_beat_sensitivity == pytest.approx(
        DEFAULT_BEAT_SENSITIVITY
    )


def test_project_render_defaults() -> None:
    controls = _make_controls(("layer_1",), duration_sec=120.0)
    _expand_project_render(controls)
    view = controls.build_view_state(paused=False)
    assert view.project.quality == DEFAULT_PROJECT_RENDER_QUALITY
    assert view.project.start_sec == 0
    assert view.project.end_sec == 120
    assert view.project.width == DEFAULT_RENDER_WIDTH
    assert view.project.height == DEFAULT_RENDER_HEIGHT
    assert view.project.fps == DEFAULT_RENDER_FPS
    assert view.project.output_label.endswith("renders/render.mp4")
    output_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_OUTPUT)
    assert format_row_value(
        view, view.layout.descriptor(output_row)
    ) == view.project.output_label
    quality_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_QUALITY)
    assert format_row_value(view, view.layout.descriptor(quality_row)) == "normal"
    width_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_WIDTH)
    assert format_row_value(view, view.layout.descriptor(width_row)) == str(
        DEFAULT_RENDER_WIDTH
    )
    height_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_HEIGHT)
    assert format_row_value(view, view.layout.descriptor(height_row)) == str(
        DEFAULT_RENDER_HEIGHT
    )
    fps_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_FPS)
    assert format_row_value(view, view.layout.descriptor(fps_row)) == str(
        DEFAULT_RENDER_FPS
    )
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
    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_MILKDROP_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.project.milkdrop_expanded is True
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.project.milkdrop_expanded is False
    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_COMPOSITOR_HEADER)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert controls.session.project.compositor_expanded is True
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert controls.session.project.compositor_expanded is False
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
    width = state.layout.find_by_kind(RowKind.PROJECT_RENDER_WIDTH)
    assert format_row_value(state, state.layout.descriptor(width)) == str(
        DEFAULT_RENDER_WIDTH
    )
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
    assert project_spec.header_glyph_color == PRESET_ICON


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


def test_width_height_fps_keyboard_steps() -> None:
    controls = _make_controls(("layer_1",))
    _expand_project_render(controls)
    view = controls.build_view_state(paused=False)
    width_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_WIDTH)
    height_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_HEIGHT)
    fps_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_FPS)
    render = controls.session.project.render

    controls.focus_descriptor = _desc(view, width_row)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert render.width == DEFAULT_RENDER_WIDTH + 10
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert render.width == DEFAULT_RENDER_WIDTH + 110

    controls.focus_descriptor = _desc(view, height_row)
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert render.height == DEFAULT_RENDER_HEIGHT - 10
    controls.handle_keydown(_keydown(pygame.K_LEFT, mod=pygame.KMOD_CTRL))
    assert render.height == DEFAULT_RENDER_HEIGHT - 110

    controls.focus_descriptor = _desc(view, fps_row)
    controls.handle_keydown(_keydown(pygame.K_RIGHT))
    assert render.fps == DEFAULT_RENDER_FPS + 1
    controls.handle_keydown(_keydown(pygame.K_RIGHT, mod=pygame.KMOD_CTRL))
    assert render.fps == DEFAULT_RENDER_FPS + 6
    controls.handle_keydown(_keydown(pygame.K_LEFT))
    assert render.fps == DEFAULT_RENDER_FPS + 5


class _ScriptedRenderJob:
    def __init__(self) -> None:
        self.fraction = 0.0
        self.aborted = False
        self._done = False
        self._ok = True
        self._error: str | None = None
        self.spec = None

    def poll(self) -> RenderJobStatus:
        return RenderJobStatus(
            done=self._done,
            ok=self._ok,
            fraction=self.fraction,
            error=self._error,
        )

    def finish(self, *, ok: bool = True, error: str | None = None) -> None:
        self._done = True
        self._ok = ok
        self.fraction = 1.0 if ok else self.fraction
        self._error = error

    def abort(self) -> None:
        self.aborted = True
        self.finish(ok=False, error="aborted")


def _focus_render_action(controls) -> None:
    _expand_project_render(controls)
    view = controls.build_view_state(paused=False)
    action_row = view.layout.find_by_kind(RowKind.PROJECT_RENDER_ACTION)
    controls.focus_descriptor = _desc(view, action_row)


def _wire_fake_job(controls, tmp_path: Path, job: _ScriptedRenderJob) -> Path:
    snap = tmp_path / "snap.yaml"
    snap.write_text("editor: {}\n")

    def start_job(spec) -> _ScriptedRenderJob:
        job.spec = spec
        return job

    controls.project_render._start_job = start_job
    controls.project_render._write_snapshot = lambda: snap
    return snap


def test_render_action_enter_opens_yes_cancel_modal() -> None:
    controls = _make_controls(("layer_1",), duration_sec=60.0)
    controls.session.project.render.quality = "high"
    controls.session.project.render.start_sec = 5
    controls.session.project.render.end_sec = 20
    _focus_render_action(controls)
    assert controls.handle_keydown(_keydown(pygame.K_RETURN)) is True
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.YES_NO
    assert modal_view.options == ("Yes", "Cancel")
    assert modal_view.message == "Render the project?"
    assert modal_view.labeled_lines == (
        ModalLabeledLine("output", "renders/render.mp4"),
        ModalLabeledLine("width", str(DEFAULT_RENDER_WIDTH)),
        ModalLabeledLine("height", str(DEFAULT_RENDER_HEIGHT)),
        ModalLabeledLine("fps", str(DEFAULT_RENDER_FPS)),
        ModalLabeledLine("quality", "high"),
        ModalLabeledLine("start", "5s"),
        ModalLabeledLine("end", "20s"),
    )


def test_render_action_cancel_does_not_start_job(tmp_path: Path) -> None:
    controls = _make_controls(("layer_1",), project_dir=tmp_path)
    job = _ScriptedRenderJob()
    _wire_fake_job(controls, tmp_path, job)
    _focus_render_action(controls)
    controls.handle_keydown(_keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "Cancel")
    assert controls.modal_host.view_state() is None
    assert job.spec is None
    assert not controls.project_render.busy


@patch("cleave.viz.render.validate_render_project")
def test_render_confirm_shows_progress_then_success(
    mock_validate, tmp_path: Path
) -> None:
    mock_validate.return_value = tmp_path
    controls = _make_controls(
        ("layer_1",), project_dir=tmp_path, duration_sec=60.0
    )
    job = _ScriptedRenderJob()
    _wire_fake_job(controls, tmp_path, job)
    _focus_render_action(controls)
    controls.handle_keydown(_keydown(pygame.K_RETURN))
    assert not controls.playback.paused
    _choose_modal_option(controls, "Yes")
    assert controls.playback.paused is True
    assert controls.project_render.busy is True
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.PROGRESS
    assert modal_view.message == "Rendering project..."
    assert modal_view.options == ()
    assert modal_view.progress_fraction == 0.0
    assert modal_view.labeled_lines == (
        ModalLabeledLine("output", "renders/render.mp4"),
        ModalLabeledLine("width", str(DEFAULT_RENDER_WIDTH)),
        ModalLabeledLine("height", str(DEFAULT_RENDER_HEIGHT)),
        ModalLabeledLine("fps", str(DEFAULT_RENDER_FPS)),
        ModalLabeledLine("quality", "normal"),
        ModalLabeledLine("start", "0s"),
        ModalLabeledLine("end", "60s"),
    )
    assert job.spec is not None
    assert job.spec.output_path == tmp_path / "renders" / "render.mp4"
    assert job.spec.start_sec == 0
    assert job.spec.end_sec == 60
    assert job.spec.width == DEFAULT_RENDER_WIDTH
    assert job.spec.height == DEFAULT_RENDER_HEIGHT
    assert job.spec.fps == DEFAULT_RENDER_FPS

    controls.handle_modal_keydown(_keydown(pygame.K_ESCAPE))
    assert controls.modal_host.view_state() is not None
    assert controls.modal_host.view_state().kind == ModalKind.PROGRESS

    job.fraction = 0.5
    controls.tick(0.016)
    assert controls.modal_host.view_state().progress_fraction == 0.5

    job.finish()
    controls.tick(0.016)
    assert controls.project_render.busy is False
    done = controls.modal_host.view_state()
    assert done is not None
    assert done.kind == ModalKind.CHOICE
    assert done.message == "Render complete"
    assert done.options == ("Ok",)
    assert done.labeled_lines == (
        ModalLabeledLine("output", "renders/render.mp4"),
    )
    assert controls.playback.paused is True
    _choose_modal_option(controls, "Ok")
    assert controls.modal_host.view_state() is None
    assert controls.playback.paused is False


@patch("cleave.viz.render.validate_render_project")
def test_render_confirm_failure_shows_error_modal(
    mock_validate, tmp_path: Path
) -> None:
    mock_validate.return_value = tmp_path
    controls = _make_controls(("layer_1",), project_dir=tmp_path)
    job = _ScriptedRenderJob()
    _wire_fake_job(controls, tmp_path, job)
    _focus_render_action(controls)
    controls.handle_keydown(_keydown(pygame.K_RETURN))
    _choose_modal_option(controls, "Yes")
    job.finish(ok=False, error="ffmpeg exited with status 1")
    controls.tick(0.016)
    view = controls.modal_host.view_state()
    assert view is not None
    assert view.kind == ModalKind.CHOICE
    assert view.message == "Render failed"
    assert view.labeled_lines == (
        ModalLabeledLine("error", "ffmpeg exited with status 1"),
    )

