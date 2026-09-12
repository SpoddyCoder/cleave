"""Confirm, progress, and completion modals for Render Project."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cleave.config import CleaveConfig
from cleave.config_schema.project_render import (
    DEFAULT_PROJECT_RENDER_OUTPUT_LABEL,
    default_project_render_path,
    resolved_project_render_end_sec,
)
from cleave.viz.modal import ModalHost, ModalLabeledLine, ModalOption
from cleave.viz.playback import PlaybackState, toggle_pause
from cleave.viz.project_render_job import (
    ProjectRenderSpec,
    RenderJob,
    start_subprocess_render_job,
    write_render_snapshot,
)
from cleave.viz.session import TuningSession

_CANCEL_LABEL = "Cancel"
_CONFIRM_TITLE = "Render the project?"
_PROGRESS_MESSAGE = "Rendering project..."
_SUCCESS_MESSAGE = "Render complete"
_FAILED_MESSAGE = "Render failed"
_OK_LABEL = "OK"


def project_render_output_path(
    session: TuningSession,
    *,
    duration_sec: float,
    project_dir: Path,
    project_slug: str,
) -> Path:
    render = session.project.render
    end_sec = resolved_project_render_end_sec(render.end_sec, duration_sec)
    return default_project_render_path(
        project_dir,
        project_slug,
        start_sec=render.start_sec,
        end_sec=end_sec,
        duration_sec=duration_sec,
    )


def project_render_output_label(path: Path) -> str:
    if path.parent.name == "renders":
        return f"renders/{path.name}"
    return path.name


def project_render_labeled_lines(
    session: TuningSession,
    *,
    duration_sec: float,
    output_path: Path,
) -> tuple[ModalLabeledLine, ...]:
    render = session.project.render
    end_sec = resolved_project_render_end_sec(render.end_sec, duration_sec)
    return (
        ModalLabeledLine("output", project_render_output_label(output_path)),
        ModalLabeledLine("quality", render.quality),
        ModalLabeledLine("start", f"{render.start_sec}s"),
        ModalLabeledLine("end", f"{end_sec}s"),
    )


class ProjectRenderController:
    """Prompt for and run an offline project render from the tuning panel."""

    def __init__(
        self,
        session: TuningSession,
        cfg: CleaveConfig,
        modal_host: ModalHost,
        *,
        duration_sec: float,
        playback: PlaybackState,
        project_dir: Path | None = None,
        start_job: Callable[[ProjectRenderSpec], RenderJob] | None = None,
        write_snapshot: Callable[[], Path] | None = None,
    ) -> None:
        self.session = session
        self.cfg = cfg
        self.duration_sec = duration_sec
        self._modal = modal_host
        self._playback = playback
        self._project_dir = project_dir
        self._start_job = start_job or start_subprocess_render_job
        self._write_snapshot = write_snapshot or (
            lambda: write_render_snapshot(self.cfg, self.session)
        )
        self._job: RenderJob | None = None
        self._snapshot_path: Path | None = None
        self._output_path: Path | None = None
        self._resume_playback = False

    @property
    def busy(self) -> bool:
        return self._job is not None

    def prompt(self) -> None:
        if self.busy:
            return
        output_path = self._resolved_output_path()
        if output_path is None:
            output_path = Path(DEFAULT_PROJECT_RENDER_OUTPUT_LABEL)
        self._modal.prompt_yes_no(
            _CONFIRM_TITLE,
            on_confirm=self._confirm,
            on_cancel=lambda: None,
            cancel_label=_CANCEL_LABEL,
            labeled_lines=project_render_labeled_lines(
                self.session,
                duration_sec=self.duration_sec,
                output_path=output_path,
            ),
        )

    def tick(self) -> None:
        if self._job is None:
            return
        status = self._job.poll()
        if not status.done:
            self._modal.update_progress(status.fraction)
            return
        ok = status.ok
        error = status.error
        output_path = self._output_path
        self._finish_job()
        if ok and output_path is not None:
            self._prompt_success(output_path)
            return
        self._prompt_error(error or "Render failed.")

    def abort(self) -> None:
        if self._job is None:
            return
        self._job.abort()
        self._finish_job()
        self._restore_playback()
        if self._modal.active:
            self._modal.dismiss()

    def _confirm(self) -> None:
        project_dir = self._project_dir
        output_path = self._resolved_output_path()
        if project_dir is None or output_path is None:
            self._prompt_error("No project directory.")
            return
        from cleave.viz.render import validate_render_project

        try:
            validate_render_project(project_dir)
        except (FileNotFoundError, ValueError) as exc:
            self._prompt_error(str(exc))
            return
        try:
            snapshot = self._write_snapshot()
        except Exception as exc:
            self._prompt_error(str(exc) or "Could not write render snapshot.")
            return
        render = self.session.project.render
        end_sec = resolved_project_render_end_sec(render.end_sec, self.duration_sec)
        spec = ProjectRenderSpec(
            project_dir=project_dir,
            config_path=snapshot,
            output_path=output_path,
            quality=render.quality,
            start_sec=render.start_sec,
            end_sec=end_sec,
        )
        self._snapshot_path = snapshot
        self._output_path = output_path
        self._pause_playback()
        self._job = self._start_job(spec)
        self._modal.prompt_progress(
            _PROGRESS_MESSAGE,
            labeled_lines=project_render_labeled_lines(
                self.session,
                duration_sec=self.duration_sec,
                output_path=output_path,
            ),
            fraction=0.0,
        )
        self.tick()

    def _resolved_output_path(self) -> Path | None:
        if self._project_dir is None:
            return None
        return project_render_output_path(
            self.session,
            duration_sec=self.duration_sec,
            project_dir=self._project_dir,
            project_slug=self.cfg.project_slug,
        )

    def _finish_job(self) -> None:
        self._job = None
        if self._snapshot_path is not None:
            try:
                self._snapshot_path.unlink(missing_ok=True)
            except OSError:
                pass
            self._snapshot_path = None

    def _pause_playback(self) -> None:
        self._resume_playback = not self._playback.paused
        if self._resume_playback:
            toggle_pause(self._playback, self.duration_sec)

    def _restore_playback(self) -> None:
        if self._resume_playback and self._playback.paused:
            toggle_pause(self._playback, self.duration_sec)
        self._resume_playback = False

    def _prompt_success(self, output_path: Path) -> None:
        label = project_render_output_label(output_path)
        self._modal.prompt_choice(
            _SUCCESS_MESSAGE,
            [ModalOption(_OK_LABEL, self._restore_playback)],
            labeled_lines=(ModalLabeledLine("output", label),),
        )

    def _prompt_error(self, detail: str) -> None:
        line = " ".join(detail.split())
        if len(line) > 96:
            line = line[:95] + "..."
        self._modal.prompt_choice(
            _FAILED_MESSAGE,
            [ModalOption(_OK_LABEL, self._restore_playback)],
            labeled_lines=(ModalLabeledLine("error", line or "unknown error"),),
        )
