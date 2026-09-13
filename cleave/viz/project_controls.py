"""Project menu mutations for live tuning."""

from __future__ import annotations

from collections.abc import Callable

from cleave.config_schema.editor import clamp_beat_sensitivity
from cleave.config_schema.project_render import (
    PROJECT_RENDER_QUALITIES,
    RENDER_FPS_STEP,
    RENDER_FPS_STEP_LARGE,
    RENDER_SIZE_STEP,
    RENDER_SIZE_STEP_LARGE,
    clamp_render_fps,
    clamp_render_height,
    clamp_render_width,
    project_render_duration_ceil_sec,
    resolved_project_render_end_sec,
)
from cleave.viz.session import TuningSession

_BEAT_SENSITIVITY_STEP = 0.1
_BEAT_SENSITIVITY_CTRL_STEP = 0.5


class ProjectControls:
    """Mutations for Project header, Milkdrop, Compositor, and Render Project rows."""

    def __init__(
        self,
        session: TuningSession,
        *,
        duration_sec: float,
        on_compositor_format_changed: Callable[[], None] | None = None,
    ) -> None:
        self.session = session
        self.duration_sec = duration_sec
        self._on_compositor_format_changed = on_compositor_format_changed

    def set_expanded(self, expanded: bool) -> None:
        project = self.session.project
        if project.expanded == expanded:
            return
        project.expanded = expanded

    def set_render_expanded(self, expanded: bool) -> None:
        render = self.session.project.render
        if render.expanded == expanded:
            return
        render.expanded = expanded

    def set_milkdrop_expanded(self, expanded: bool) -> None:
        project = self.session.project
        if project.milkdrop_expanded == expanded:
            return
        project.milkdrop_expanded = expanded

    def set_compositor_expanded(self, expanded: bool) -> None:
        project = self.session.project
        if project.compositor_expanded == expanded:
            return
        project.compositor_expanded = expanded

    def adjust_milkdrop_beat_sensitivity(self, *, forward: bool, ctrl: bool) -> None:
        step = _BEAT_SENSITIVITY_CTRL_STEP if ctrl else _BEAT_SENSITIVITY_STEP
        delta = step if forward else -step
        project = self.session.project
        project.milkdrop_beat_sensitivity = clamp_beat_sensitivity(
            project.milkdrop_beat_sensitivity + delta
        )

    def toggle_compositor_hdr(self) -> None:
        project = self.session.project
        project.compositor_hdr = not project.compositor_hdr
        if self._on_compositor_format_changed is not None:
            self._on_compositor_format_changed()

    def cycle_quality(self, *, forward: bool) -> None:
        modes = PROJECT_RENDER_QUALITIES
        render = self.session.project.render
        try:
            index = modes.index(render.quality)
        except ValueError:
            index = 0
        if forward:
            render.quality = modes[(index + 1) % len(modes)]
        else:
            render.quality = modes[(index - 1) % len(modes)]

    def adjust_start(self, *, forward: bool, ctrl: bool) -> None:
        step = 10 if ctrl else 1
        delta = step if forward else -step
        render = self.session.project.render
        end = resolved_project_render_end_sec(render.end_sec, self.duration_sec)
        render.start_sec = max(0, min(render.start_sec + delta, end - 1))

    def adjust_end(self, *, forward: bool, ctrl: bool) -> None:
        step = 10 if ctrl else 1
        delta = step if forward else -step
        render = self.session.project.render
        current = resolved_project_render_end_sec(render.end_sec, self.duration_sec)
        ceil = project_render_duration_ceil_sec(self.duration_sec)
        new_end = max(render.start_sec + 1, min(current + delta, ceil))
        render.end_sec = None if new_end == ceil else new_end

    def adjust_width(self, *, forward: bool, ctrl: bool) -> None:
        step = RENDER_SIZE_STEP_LARGE if ctrl else RENDER_SIZE_STEP
        delta = step if forward else -step
        render = self.session.project.render
        render.width = clamp_render_width(render.width + delta)

    def adjust_height(self, *, forward: bool, ctrl: bool) -> None:
        step = RENDER_SIZE_STEP_LARGE if ctrl else RENDER_SIZE_STEP
        delta = step if forward else -step
        render = self.session.project.render
        render.height = clamp_render_height(render.height + delta)

    def adjust_fps(self, *, forward: bool, ctrl: bool) -> None:
        step = RENDER_FPS_STEP_LARGE if ctrl else RENDER_FPS_STEP
        delta = step if forward else -step
        render = self.session.project.render
        render.fps = clamp_render_fps(render.fps + delta)
