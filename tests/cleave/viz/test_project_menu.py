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
from cleave.viz.commands import command_by_id
from cleave.viz.material_icons import FOLDER_GLYPH
from cleave.viz.modal import ModalKind, ModalLabeledLine
from cleave.viz.project_render_job import RenderJobStatus
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.shell_focus import InspectorGroupKey
from cleave.viz.row_spec import (
    RowPresentStyle,
    format_row_value,
    labeled_row_prefix,
    row_composite_header_display_text,
    row_spec,
)
from cleave.viz.theme import PRESET_ICON
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
from tests.support.viz import make_track_block, press_main_row


def test_structure_signature_stable_for_render_quality_and_range() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    sig_before = view_state_structure_signature(
        session, config_save)
    session.project.render.quality = "high"
    session.project.render.start_sec = 10
    session.project.render.end_sec = 20
    session.project.render.width = 1280
    session.project.render.height = 720
    session.project.render.fps = 24
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before == sig_after


def test_project_children_omitted_until_expanded() -> None:
    from cleave.viz.inspector import build_inspector_rows

    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    names = {row.kind.name for row in view.layout.rows}
    assert not any(name.startswith("PROJECT_") for name in names)
    rows = build_inspector_rows(view, "project", frozenset())
    kinds = [row.descriptor.kind for row in rows if row.descriptor is not None]
    assert RowKind.PROJECT_MILKDROP_HEADER in kinds
    assert RowKind.PROJECT_COMPOSITOR_HEADER in kinds
    assert RowKind.PROJECT_RENDER_HEADER in kinds
    collapsed = build_inspector_rows(
        view,
        "project",
        frozenset({InspectorGroupKey(RowKind.PROJECT_MILKDROP_HEADER)}),
    )
    collapsed_kinds = [
        row.descriptor.kind for row in collapsed if row.descriptor is not None
    ]
    assert RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY not in collapsed_kinds


def test_project_render_children_omitted_until_expanded() -> None:
    from cleave.viz.inspector import build_inspector_rows

    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    rows = build_inspector_rows(view, "project", frozenset())
    kinds = [row.descriptor.kind for row in rows if row.descriptor is not None]
    assert RowKind.PROJECT_RENDER_OUTPUT in kinds
    assert RowKind.PROJECT_RENDER_WIDTH in kinds
    assert RowKind.PROJECT_RENDER_HEIGHT in kinds
    assert RowKind.PROJECT_RENDER_FPS in kinds
    assert RowKind.PROJECT_RENDER_QUALITY in kinds
    assert RowKind.PROJECT_RENDER_START in kinds
    assert RowKind.PROJECT_RENDER_END in kinds


def test_project_milkdrop_children_omitted_until_expanded() -> None:
    from cleave.viz.inspector import build_inspector_rows

    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    hidden = build_inspector_rows(
        view,
        "project",
        frozenset({InspectorGroupKey(RowKind.PROJECT_MILKDROP_HEADER)}),
    )
    hidden_kinds = [
        row.descriptor.kind for row in hidden if row.descriptor is not None
    ]
    assert RowKind.PROJECT_MILKDROP_HEADER in hidden_kinds
    assert RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY not in hidden_kinds
    shown = build_inspector_rows(view, "project", frozenset())
    beat = next(
        row.descriptor
        for row in shown
        if row.descriptor is not None
        and row.descriptor.kind == RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY
    )
    assert format_row_value(view, beat) == f"{DEFAULT_BEAT_SENSITIVITY:.2f}"


def test_structure_signature_stable_for_compositor_hdr() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    sig_before = view_state_structure_signature(
        session, config_save)
    session.project.compositor_hdr = False
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before == sig_after


def test_project_compositor_children_omitted_until_expanded() -> None:
    from cleave.viz.inspector import build_inspector_rows

    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    shown = build_inspector_rows(view, "project", frozenset())
    hdr = next(
        row.descriptor
        for row in shown
        if row.descriptor is not None
        and row.descriptor.kind == RowKind.PROJECT_COMPOSITOR_HDR
    )
    assert format_row_value(view, hdr) == "on"


def test_compositor_hdr_keyboard_toggles() -> None:
    controls = _make_controls(("layer_1",))
    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_COMPOSITOR_HDR)
    assert controls.session.project.compositor_hdr is True
    press_main_row(controls, _keydown(pygame.K_RIGHT))
    assert controls.session.project.compositor_hdr is False
    press_main_row(controls, _keydown(pygame.K_LEFT))
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
    assert spec.toggle_enabled is None
    assert spec.toggle_solo is None
    assert spec.affordance == RowAffordance.EXPAND


def test_milkdrop_beat_sensitivity_keyboard_steps() -> None:
    controls = _make_controls(("layer_1",))
    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY)
    press_main_row(controls, _keydown(pygame.K_RIGHT))
    assert controls.session.project.milkdrop_beat_sensitivity == pytest.approx(
        DEFAULT_BEAT_SENSITIVITY + 0.1
    )
    press_main_row(controls, _keydown(pygame.K_PAGEDOWN))
    assert controls.session.project.milkdrop_beat_sensitivity == pytest.approx(
        DEFAULT_BEAT_SENSITIVITY + 0.6
    )
    press_main_row(controls, _keydown(pygame.K_LEFT))
    assert controls.session.project.milkdrop_beat_sensitivity == pytest.approx(
        DEFAULT_BEAT_SENSITIVITY + 0.5
    )
    press_main_row(controls, _keydown(pygame.K_PAGEUP))
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
    assert format_row_value(
        view, RowDescriptor(RowKind.PROJECT_RENDER_OUTPUT)
    ) == view.project.output_label
    assert format_row_value(
        view, RowDescriptor(RowKind.PROJECT_RENDER_QUALITY)
    ) == "normal"
    assert format_row_value(
        view, RowDescriptor(RowKind.PROJECT_RENDER_WIDTH)
    ) == str(DEFAULT_RENDER_WIDTH)
    assert format_row_value(
        view, RowDescriptor(RowKind.PROJECT_RENDER_HEIGHT)
    ) == str(DEFAULT_RENDER_HEIGHT)
    assert format_row_value(
        view, RowDescriptor(RowKind.PROJECT_RENDER_FPS)
    ) == str(DEFAULT_RENDER_FPS)
    assert format_row_value(
        view, RowDescriptor(RowKind.PROJECT_RENDER_START)
    ) == "0s"
    assert format_row_value(
        view, RowDescriptor(RowKind.PROJECT_RENDER_END)
    ) == "120s"


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

    controls.project.adjust_start(forward=True, large=False)
    assert render.start_sec == 1
    controls.project.adjust_start(forward=True, large=True)
    assert render.start_sec == 11

    controls.project.adjust_end(forward=False, large=False)
    assert render.end_sec == 59
    controls.project.adjust_end(forward=False, large=True)
    assert render.end_sec == 49

    render.start_sec = 48
    controls.project.adjust_start(forward=True, large=True)
    assert render.start_sec == 48
    controls.project.adjust_end(forward=True, large=True)
    assert render.end_sec == 59
    controls.project.adjust_end(forward=True, large=False)
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


def test_enter_on_headers_toggles_expand() -> None:
    from cleave.viz.shell_focus import ShellRegion

    controls = _make_controls(("layer_1",))
    controls.shell_focus.region = ShellRegion.INSPECTOR
    controls.shell_focus.selected_id = "project"
    controls.shell_focus.inspector_cursor = RowDescriptor(
        RowKind.PROJECT_MILKDROP_HEADER
    )
    controls.inspector.handle_keydown(_keydown(pygame.K_RETURN))
    milkdrop = InspectorGroupKey(RowKind.PROJECT_MILKDROP_HEADER)
    assert milkdrop in controls.shell_focus.collapsed
    controls.inspector.handle_keydown(_keydown(pygame.K_RETURN))
    assert milkdrop not in controls.shell_focus.collapsed


def test_left_right_on_headers_toggles_expand() -> None:
    from cleave.viz.shell_focus import ShellRegion

    controls = _make_controls(("layer_1",))
    controls.shell_focus.region = ShellRegion.INSPECTOR
    controls.shell_focus.selected_id = "project"
    controls.shell_focus.inspector_cursor = RowDescriptor(
        RowKind.PROJECT_MILKDROP_HEADER
    )
    controls.inspector.handle_keydown(_keydown(pygame.K_RIGHT))
    milkdrop = InspectorGroupKey(RowKind.PROJECT_MILKDROP_HEADER)
    assert milkdrop in controls.shell_focus.collapsed
    controls.inspector.handle_keydown(_keydown(pygame.K_LEFT))
    assert milkdrop not in controls.shell_focus.collapsed


def test_minimal_view_render_labels() -> None:
    state = _minimal_view_state(
        project=ProjectBlock(
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
    quality = RowDescriptor(RowKind.PROJECT_RENDER_QUALITY)
    assert format_row_value(state, quality) == "high"
    width = RowDescriptor(RowKind.PROJECT_RENDER_WIDTH)
    assert format_row_value(state, width) == str(DEFAULT_RENDER_WIDTH)
    output = RowDescriptor(RowKind.PROJECT_RENDER_OUTPUT)
    assert format_row_value(state, output) == "renders/demo_5-40s.mp4"


def test_render_output_row_is_read_only() -> None:
    spec = row_spec(RowKind.PROJECT_RENDER_OUTPUT)
    assert spec.affordance == RowAffordance.DISPLAY
    assert spec.apply_horizontal is None
    assert spec.present_style == RowPresentStyle.PATH_ICON
    project_spec = row_spec(RowKind.PROJECT_RENDER_HEADER)
    assert project_spec.panel_label == "Render Project"


def test_start_end_keyboard_steps() -> None:
    controls = _make_controls(("layer_1",), duration_sec=60.0)
    render = controls.session.project.render

    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_RENDER_START)
    press_main_row(controls, _keydown(pygame.K_RIGHT))
    assert render.start_sec == 1
    press_main_row(controls, _keydown(pygame.K_PAGEDOWN))
    assert render.start_sec == 11

    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_RENDER_END)
    press_main_row(controls, _keydown(pygame.K_LEFT))
    assert render.end_sec == 59
    press_main_row(controls, _keydown(pygame.K_PAGEUP))
    assert render.end_sec == 49


def test_width_height_fps_keyboard_steps() -> None:
    controls = _make_controls(("layer_1",))
    render = controls.session.project.render

    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_RENDER_WIDTH)
    press_main_row(controls, _keydown(pygame.K_RIGHT))
    assert render.width == DEFAULT_RENDER_WIDTH + 10
    press_main_row(controls, _keydown(pygame.K_PAGEDOWN))
    assert render.width == DEFAULT_RENDER_WIDTH + 110

    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_RENDER_HEIGHT)
    press_main_row(controls, _keydown(pygame.K_LEFT))
    assert render.height == DEFAULT_RENDER_HEIGHT - 10
    press_main_row(controls, _keydown(pygame.K_PAGEUP))
    assert render.height == DEFAULT_RENDER_HEIGHT - 110

    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_RENDER_FPS)
    press_main_row(controls, _keydown(pygame.K_RIGHT))
    assert render.fps == DEFAULT_RENDER_FPS + 1
    press_main_row(controls, _keydown(pygame.K_PAGEDOWN))
    assert render.fps == DEFAULT_RENDER_FPS + 6
    press_main_row(controls, _keydown(pygame.K_LEFT))
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


def _prompt_project_render(controls) -> None:
    command_by_id("project.render").run(controls)


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
    _prompt_project_render(controls)
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
    _prompt_project_render(controls)
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
    _prompt_project_render(controls)
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
    _prompt_project_render(controls)
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

