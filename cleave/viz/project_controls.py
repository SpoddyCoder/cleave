"""Project menu mutations for live tuning."""

from __future__ import annotations

from collections.abc import Callable

from cleave.config_schema.editor import clamp_beat_sensitivity
from cleave.config_schema.project_resolution import (
    RESOLUTION_STEP,
    RESOLUTION_STEP_LARGE,
    clamp_resolution_height,
    clamp_resolution_width,
)
from cleave.viz.session import TuningSession

_BEAT_SENSITIVITY_STEP = 0.1
_BEAT_SENSITIVITY_LARGE_STEP = 0.5


class ProjectControls:
    """Mutations for Project header, Milkdrop, Compositor, and Resolution rows."""

    def __init__(
        self,
        session: TuningSession,
        *,
        on_compositor_format_changed: Callable[[], None] | None = None,
    ) -> None:
        self.session = session
        self._on_compositor_format_changed = on_compositor_format_changed

    def adjust_milkdrop_beat_sensitivity(self, *, forward: bool, large: bool) -> None:
        step = _BEAT_SENSITIVITY_LARGE_STEP if large else _BEAT_SENSITIVITY_STEP
        delta = step if forward else -step
        project = self.session.project
        project.milkdrop_beat_sensitivity = clamp_beat_sensitivity(
            project.milkdrop_beat_sensitivity + delta
        )

    def set_compositor_hdr(self, enabled: bool) -> None:
        project = self.session.project
        if project.compositor_hdr == enabled:
            return
        project.compositor_hdr = enabled
        if self._on_compositor_format_changed is not None:
            self._on_compositor_format_changed()

    def adjust_width(self, *, forward: bool, large: bool) -> None:
        step = RESOLUTION_STEP_LARGE if large else RESOLUTION_STEP
        delta = step if forward else -step
        resolution = self.session.project.resolution
        resolution.width = clamp_resolution_width(resolution.width + delta)

    def adjust_height(self, *, forward: bool, large: bool) -> None:
        step = RESOLUTION_STEP_LARGE if large else RESOLUTION_STEP
        delta = step if forward else -step
        resolution = self.session.project.resolution
        resolution.height = clamp_resolution_height(resolution.height + delta)
