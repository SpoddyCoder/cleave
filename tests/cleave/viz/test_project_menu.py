"""Project menu: ProjectM, Compositor, and Resolution pages, and the Render dialog."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pygame
import pytest

# Load the submodule so patch() targets it, not the package's lazy render().
import cleave.viz.render  # noqa: F401
from cleave.config_schema.editor import DEFAULT_BEAT_SENSITIVITY
from cleave.config_schema.project_render import DEFAULT_RENDER_FPS
from cleave.config_schema.project_resolution import (
    DEFAULT_RESOLUTION_HEIGHT,
    DEFAULT_RESOLUTION_WIDTH,
)
from cleave.viz.commands import command_by_id
from cleave.viz.modal import ModalKind, ModalLabeledLine
from cleave.viz.project_render_job import RenderJobStatus
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import format_row_value, row_spec
from cleave.viz.tuning_view_state import view_state_structure_signature
from tests.cleave.viz.test_controls import (
    _choose_modal_option,
    _keydown,
    _make_controls,
)
from tests.support.viz import press_main_row


def test_structure_signature_stable_for_render_quality_and_range() -> None:
    controls = _make_controls(("layer_1",))
    session = controls.session
    config_save = controls._config_save
    sig_before = view_state_structure_signature(
        session, config_save)
    session.project.render.quality = "high"
    session.project.render.start_sec = 10
    session.project.render.end_sec = 20
    session.project.resolution.width = 1280
    session.project.resolution.height = 720
    session.project.render.fps = 24
    sig_after = view_state_structure_signature(
        session, config_save)
    assert sig_before == sig_after


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


def test_compositor_page_shows_hdr() -> None:
    from cleave.viz.inspector import build_inspector_rows

    controls = _make_controls(("layer_1",))
    view = controls.build_view_state(paused=False)
    shown = build_inspector_rows(view, "project.compositor")
    hdr = next(
        row.descriptor
        for row in shown
        if row.descriptor is not None
        and row.descriptor.kind == RowKind.PROJECT_COMPOSITOR_HDR
    )
    assert format_row_value(view, hdr) == "on"


def test_compositor_hdr_keyboard_left_off_right_on() -> None:
    controls = _make_controls(("layer_1",))
    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_COMPOSITOR_HDR)
    assert controls.session.project.compositor_hdr is True
    press_main_row(controls, _keydown(pygame.K_RIGHT))
    assert controls.session.project.compositor_hdr is True
    press_main_row(controls, _keydown(pygame.K_LEFT))
    assert controls.session.project.compositor_hdr is False
    press_main_row(controls, _keydown(pygame.K_LEFT))
    assert controls.session.project.compositor_hdr is False
    press_main_row(controls, _keydown(pygame.K_RIGHT))
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
    controls.project.set_compositor_hdr(False)
    assert controls.session.project.compositor_hdr is False
    compositor.set_color_format.assert_called_with(RGBA8)
    post_process.set_color_format.assert_called_with(RGBA8)
    compositor.reset_mock()
    post_process.reset_mock()
    controls.project.set_compositor_hdr(True)
    compositor.set_color_format.assert_called_with(RGBA16F)
    post_process.set_color_format.assert_called_with(RGBA16F)


def test_compositor_header_has_no_toggles() -> None:
    spec = row_spec(RowKind.PROJECT_COMPOSITOR_HEADER)
    assert spec.toggle_enabled is None
    assert spec.toggle_solo is None
    assert spec.affordance == RowAffordance.HEADING


def test_milkdrop_beat_sensitivity_keyboard_steps() -> None:
    controls = _make_controls(("layer_1",))
    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY)
    press_main_row(controls, _keydown(pygame.K_RIGHT))
    assert controls.session.project.milkdrop_beat_sensitivity == pytest.approx(
        DEFAULT_BEAT_SENSITIVITY + 0.1
    )
    press_main_row(controls, _keydown(pygame.K_PAGEUP))
    assert controls.session.project.milkdrop_beat_sensitivity == pytest.approx(
        DEFAULT_BEAT_SENSITIVITY + 0.6
    )
    press_main_row(controls, _keydown(pygame.K_LEFT))
    assert controls.session.project.milkdrop_beat_sensitivity == pytest.approx(
        DEFAULT_BEAT_SENSITIVITY + 0.5
    )
    press_main_row(controls, _keydown(pygame.K_PAGEDOWN))
    assert controls.session.project.milkdrop_beat_sensitivity == pytest.approx(
        DEFAULT_BEAT_SENSITIVITY
    )


def test_resolution_rows_show_defaults() -> None:
    view = _make_controls(("layer_1",)).build_view_state(paused=False)
    assert format_row_value(
        view, RowDescriptor(RowKind.PROJECT_RESOLUTION_WIDTH)
    ) == str(DEFAULT_RESOLUTION_WIDTH)
    assert format_row_value(
        view, RowDescriptor(RowKind.PROJECT_RESOLUTION_HEIGHT)
    ) == str(DEFAULT_RESOLUTION_HEIGHT)
    assert row_spec(RowKind.PROJECT_RESOLUTION_HEADER).panel_label == "Resolution"


def test_width_height_keyboard_steps() -> None:
    controls = _make_controls(("layer_1",))
    resolution = controls.session.project.resolution

    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_RESOLUTION_WIDTH)
    press_main_row(controls, _keydown(pygame.K_RIGHT))
    assert resolution.width == DEFAULT_RESOLUTION_WIDTH + 10
    press_main_row(controls, _keydown(pygame.K_PAGEUP))
    assert resolution.width == DEFAULT_RESOLUTION_WIDTH + 110

    controls.focus_descriptor = RowDescriptor(RowKind.PROJECT_RESOLUTION_HEIGHT)
    press_main_row(controls, _keydown(pygame.K_LEFT))
    assert resolution.height == DEFAULT_RESOLUTION_HEIGHT - 10
    press_main_row(controls, _keydown(pygame.K_PAGEDOWN))
    assert resolution.height == DEFAULT_RESOLUTION_HEIGHT - 110


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


def _form_row(controls, label: str) -> tuple[int, object]:
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    for index, row in enumerate(modal_view.form_rows):
        if row.label == label:
            return index, row
    raise AssertionError(f"no form field {label!r}")


def _form_value(controls, label: str) -> str:
    _index, row = _form_row(controls, label)
    return row.options[row.value]


def _focus_form_row(controls, label: str) -> None:
    index, _row = _form_row(controls, label)
    controls.modal_host.focus_form_row(index)


def test_render_dialog_shows_current_settings() -> None:
    controls = _make_controls(("layer_1",), duration_sec=60.0)
    controls.session.project.render.quality = "high"
    controls.session.project.render.start_sec = 5
    controls.session.project.render.end_sec = 20
    _prompt_project_render(controls)
    modal_view = controls.modal_host.view_state()
    assert modal_view is not None
    assert modal_view.kind == ModalKind.FORM
    assert modal_view.message == "Render project"
    assert modal_view.options == ("Render", "Cancel")
    assert modal_view.body == (
        f"{DEFAULT_RESOLUTION_WIDTH} x {DEFAULT_RESOLUTION_HEIGHT}, "
        "from Project > Resolution."
    )
    assert [row.label for row in modal_view.form_rows] == [
        "fps",
        "quality",
        "start",
        "end",
    ]
    assert [row.stepper for row in modal_view.form_rows] == [True, False, True, True]
    assert _form_value(controls, "fps") == str(DEFAULT_RENDER_FPS)
    assert _form_value(controls, "quality") == "high"
    assert _form_value(controls, "start") == "5s"
    assert _form_value(controls, "end") == "20s"


def test_render_dialog_info_names_the_draft_output(tmp_path: Path) -> None:
    controls = _make_controls(("layer_1",), project_dir=tmp_path, duration_sec=60.0)
    _prompt_project_render(controls)
    assert controls.modal_host.view_state().form_info == "(renders/render.mp4)"
    _focus_form_row(controls, "start")
    controls.handle_modal_keydown(_keydown(pygame.K_PAGEUP))
    assert controls.modal_host.view_state().form_info == "(renders/render_10-60s.mp4)"


def test_render_dialog_steps_fps_and_range() -> None:
    controls = _make_controls(("layer_1",), duration_sec=60.0)
    _prompt_project_render(controls)
    _focus_form_row(controls, "fps")
    controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    assert _form_value(controls, "fps") == str(DEFAULT_RENDER_FPS + 1)
    controls.handle_modal_keydown(_keydown(pygame.K_PAGEDOWN))
    assert _form_value(controls, "fps") == str(DEFAULT_RENDER_FPS - 4)
    _focus_form_row(controls, "end")
    controls.handle_modal_keydown(_keydown(pygame.K_LEFT))
    assert _form_value(controls, "end") == "59s"
    controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    assert _form_value(controls, "end") == "60s"


def test_render_dialog_keeps_start_before_end() -> None:
    controls = _make_controls(("layer_1",), duration_sec=60.0)
    controls.session.project.render.start_sec = 10
    controls.session.project.render.end_sec = 15
    _prompt_project_render(controls)
    _focus_form_row(controls, "start")
    controls.handle_modal_keydown(_keydown(pygame.K_PAGEUP))
    assert _form_value(controls, "start") == "20s"
    assert _form_value(controls, "end") == "21s"
    _focus_form_row(controls, "end")
    for _ in range(25):
        controls.handle_modal_keydown(_keydown(pygame.K_LEFT))
    assert _form_value(controls, "end") == "1s"
    assert _form_value(controls, "start") == "0s"


def test_render_dialog_cancel_leaves_session_untouched() -> None:
    controls = _make_controls(("layer_1",), duration_sec=60.0)
    render = controls.session.project.render
    _prompt_project_render(controls)
    _focus_form_row(controls, "fps")
    controls.handle_modal_keydown(_keydown(pygame.K_PAGEUP))
    _focus_form_row(controls, "quality")
    controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    _choose_modal_option(controls, "Cancel")
    assert render.fps == DEFAULT_RENDER_FPS
    assert render.quality == "normal"
    assert not controls.config_dirty


@patch("cleave.viz.render.validate_render_project")
def test_render_dialog_confirm_writes_settings(mock_validate, tmp_path: Path) -> None:
    mock_validate.return_value = tmp_path
    controls = _make_controls(("layer_1",), project_dir=tmp_path, duration_sec=60.0)
    job = _ScriptedRenderJob()
    _wire_fake_job(controls, tmp_path, job)
    render = controls.session.project.render
    _prompt_project_render(controls)
    _focus_form_row(controls, "fps")
    controls.handle_modal_keydown(_keydown(pygame.K_PAGEUP))
    _focus_form_row(controls, "quality")
    controls.handle_modal_keydown(_keydown(pygame.K_RIGHT))
    _focus_form_row(controls, "start")
    controls.handle_modal_keydown(_keydown(pygame.K_PAGEUP))
    _choose_modal_option(controls, "Render")
    assert render.fps == DEFAULT_RENDER_FPS + 5
    assert render.quality == "high"
    assert render.start_sec == 10
    assert render.end_sec is None
    assert controls.config_dirty
    assert job.spec is not None
    assert job.spec.fps == DEFAULT_RENDER_FPS + 5
    assert job.spec.quality == "high"
    assert job.spec.start_sec == 10
    assert job.spec.end_sec == 60
    assert job.spec.output_path == tmp_path / "renders" / "render_10-60s.mp4"


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
    _choose_modal_option(controls, "Render")
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
        ModalLabeledLine("width", str(DEFAULT_RESOLUTION_WIDTH)),
        ModalLabeledLine("height", str(DEFAULT_RESOLUTION_HEIGHT)),
        ModalLabeledLine("fps", str(DEFAULT_RENDER_FPS)),
        ModalLabeledLine("quality", "normal"),
        ModalLabeledLine("start", "0s"),
        ModalLabeledLine("end", "60s"),
    )
    assert job.spec is not None
    assert job.spec.output_path == tmp_path / "renders" / "render.mp4"
    assert job.spec.start_sec == 0
    assert job.spec.end_sec == 60
    assert job.spec.width == DEFAULT_RESOLUTION_WIDTH
    assert job.spec.height == DEFAULT_RESOLUTION_HEIGHT
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
    assert done.kind == ModalKind.CONFIRM
    assert done.message == "Render complete"
    assert done.options == ("OK",)
    assert done.labeled_lines == (
        ModalLabeledLine("output", "renders/render.mp4"),
    )
    assert controls.playback.paused is True
    _choose_modal_option(controls, "OK")
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
    _choose_modal_option(controls, "Render")
    job.finish(ok=False, error="ffmpeg exited with status 1")
    controls.tick(0.016)
    view = controls.modal_host.view_state()
    assert view is not None
    assert view.kind == ModalKind.CONFIRM
    assert view.message == "Render failed"
    assert view.labeled_lines == (
        ModalLabeledLine("error", "ffmpeg exited with status 1"),
    )

