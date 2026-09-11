"""Project menu mutations for live tuning."""

from __future__ import annotations

from cleave.config_schema.project_render import (
    PROJECT_RENDER_QUALITIES,
    project_render_duration_ceil_sec,
    resolved_project_render_end_sec,
)
from cleave.viz.session import TuningSession


class ProjectControls:
    """Mutations for the Project header and Render Project rows."""

    def __init__(self, session: TuningSession, *, duration_sec: float) -> None:
        self.session = session
        self.duration_sec = duration_sec

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
