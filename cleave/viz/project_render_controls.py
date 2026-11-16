"""Settings, progress, and completion modals for Project > Render....

The Render dialog is the one place to set the render's fps, quality, and
range. Its fields edit draft values; Render writes them to the session and
starts the job, and Cancel leaves the session untouched.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cleave.config import CleaveConfig
from cleave.config_schema.project_render import (
    DEFAULT_PROJECT_RENDER_OUTPUT_LABEL,
    PROJECT_RENDER_QUALITIES,
    PROJECT_RENDER_QUALITY_HELP_ENTRIES,
    RENDER_FPS_MAX,
    RENDER_FPS_MIN,
    RENDER_FPS_STEP_LARGE,
    ProjectRenderQuality,
    clamp_render_fps,
    default_project_render_path,
    project_render_duration_ceil_sec,
    resolved_project_render_end_sec,
)
from cleave.choice import choice_index
from cleave.viz.modal import (
    FormField,
    FormSpec,
    FormValues,
    ModalHost,
    ModalLabeledLine,
)
from cleave.viz.playback import PlaybackState, toggle_pause
from cleave.viz.project_render_job import (
    ProjectRenderSpec,
    RenderJob,
    start_subprocess_render_job,
    write_render_snapshot,
)
from cleave.viz.session import TuningSession

_FORM_TITLE = "Render project"
_RANGE_STEP_LARGE_SEC = 10
_FORM_HELP = (
    "Renders the project to an MP4 video file in the project's renders directory.",
    "Fps is saved with the project. Quality, start, and end last until the editor closes.",
)
_FPS_OPTIONS = tuple(range(RENDER_FPS_MIN, RENDER_FPS_MAX + 1))
_PROGRESS_MESSAGE = "Rendering project..."
_SUCCESS_MESSAGE = "Render complete"
_FAILED_MESSAGE = "Render failed"


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


@dataclass(frozen=True)
class RenderDraft:
    """Render settings as the dialog's fields hold them."""

    fps: int
    quality: ProjectRenderQuality
    start_sec: int
    end_sec: int


def render_draft_from_values(values: FormValues) -> RenderDraft:
    """Draft from form option indices. Start counts from 0s, end from 1s."""
    return RenderDraft(
        fps=_FPS_OPTIONS[values["fps"]],
        quality=PROJECT_RENDER_QUALITIES[values["quality"]],
        start_sec=values["start"],
        end_sec=values["end"] + 1,
    )


def keep_render_range_ordered(field_id: str, values: FormValues) -> None:
    """Push the other end of the range so start stays before end."""
    start = values["start"]
    end_sec = values["end"] + 1
    if start < end_sec:
        return
    if field_id == "start":
        values["end"] = start
    else:
        values["start"] = end_sec - 1


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
    resolution = session.project.resolution
    end_sec = resolved_project_render_end_sec(render.end_sec, duration_sec)
    return (
        ModalLabeledLine("output", project_render_output_label(output_path)),
        ModalLabeledLine("width", str(resolution.width)),
        ModalLabeledLine("height", str(resolution.height)),
        ModalLabeledLine("fps", str(render.fps)),
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
        render = self.session.project.render
        resolution = self.session.project.resolution
        ceil = project_render_duration_ceil_sec(self.duration_sec)
        end_sec = resolved_project_render_end_sec(render.end_sec, self.duration_sec)
        start_sec = max(0, min(render.start_sec, ceil - 1))
        end_sec = max(start_sec + 1, min(end_sec, ceil))
        fps = clamp_render_fps(render.fps)
        self._modal.prompt_form(
            FormSpec(
                title=_FORM_TITLE,
                fields=(
                    FormField(
                        "fps",
                        "fps",
                        tuple(str(value) for value in _FPS_OPTIONS),
                        _FPS_OPTIONS.index(fps),
                        help=("Frames per second of the rendered video.",),
                        stepper=True,
                        large_step=RENDER_FPS_STEP_LARGE,
                    ),
                    FormField(
                        "quality",
                        "quality",
                        PROJECT_RENDER_QUALITIES,
                        choice_index(PROJECT_RENDER_QUALITIES, render.quality),
                        help=("Speed or quality for the render.",),
                        option_help=tuple(
                            text for _mode, text in PROJECT_RENDER_QUALITY_HELP_ENTRIES
                        ),
                    ),
                    FormField(
                        "start",
                        "start",
                        tuple(f"{sec}s" for sec in range(0, ceil)),
                        start_sec,
                        help=("Time in the song where the render starts, in seconds.",),
                        stepper=True,
                        large_step=_RANGE_STEP_LARGE_SEC,
                    ),
                    FormField(
                        "end",
                        "end",
                        tuple(f"{sec}s" for sec in range(1, ceil + 1)),
                        end_sec - 1,
                        help=("Time in the song where the render ends, in seconds.",),
                        stepper=True,
                        large_step=_RANGE_STEP_LARGE_SEC,
                    ),
                ),
                confirm_label="Render",
                on_confirm=self._confirm_values,
                body=f"{resolution.width} x {resolution.height}, from Project > Resolution.",
                info=self._output_info,
                help=_FORM_HELP,
                on_change=keep_render_range_ordered,
            )
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

    def _output_info(self, values: FormValues) -> str:
        draft = render_draft_from_values(values)
        if self._project_dir is None:
            return f"({DEFAULT_PROJECT_RENDER_OUTPUT_LABEL})"
        path = default_project_render_path(
            self._project_dir,
            self.cfg.project_slug,
            start_sec=draft.start_sec,
            end_sec=draft.end_sec,
            duration_sec=self.duration_sec,
        )
        return f"({project_render_output_label(path)})"

    def _confirm_values(self, values: FormValues) -> None:
        draft = render_draft_from_values(values)
        render = self.session.project.render
        render.fps = draft.fps
        render.quality = draft.quality
        render.start_sec = draft.start_sec
        ceil = project_render_duration_ceil_sec(self.duration_sec)
        render.end_sec = None if draft.end_sec >= ceil else draft.end_sec
        self._confirm()

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
        resolution = self.session.project.resolution
        end_sec = resolved_project_render_end_sec(render.end_sec, self.duration_sec)
        spec = ProjectRenderSpec(
            project_dir=project_dir,
            config_path=snapshot,
            output_path=output_path,
            quality=render.quality,
            start_sec=render.start_sec,
            end_sec=end_sec,
            width=resolution.width,
            height=resolution.height,
            fps=render.fps,
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
        self._modal.prompt_notice(
            _SUCCESS_MESSAGE,
            self._restore_playback,
            labeled_lines=(ModalLabeledLine("output", label),),
        )

    def _prompt_error(self, detail: str) -> None:
        line = " ".join(detail.split())
        if len(line) > 96:
            line = line[:95] + "..."
        self._modal.prompt_notice(
            _FAILED_MESSAGE,
            self._restore_playback,
            labeled_lines=(ModalLabeledLine("error", line or "unknown error"),),
        )
