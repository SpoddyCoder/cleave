"""Size the live visualiser to what it shows, once edits and resizes settle."""

from __future__ import annotations

from collections.abc import Callable

from cleave.config import CleaveConfig
from cleave.viz.layer_preview_resolution import (
    live_content_size,
    session_project_size,
)
from cleave.viz.session import TuningSession

# Quiet time after the last size change before the framebuffers are
# reallocated, so a held key or a window drag does not reallocate every step.
VISUALISER_RESOLUTION_SETTLE_SEC = 0.25


class VisualiserResolutionSync:
    """Watch the project resolution, draw size and preview quality.

    The live content size is the project aspect fitted to the visualiser's
    on-screen rect (``live_content_size``). Polling covers every source of
    change: the Project > Resolution rows, revert, editor-mode reloads, window
    and column resizes, and the preview quality setting.

    The first draw size is applied at once; later changes wait for
    ``VISUALISER_RESOLUTION_SETTLE_SEC`` of quiet.
    """

    def __init__(
        self,
        session: TuningSession,
        cfg: CleaveConfig,
        on_apply: Callable[[tuple[int, int]], None],
    ) -> None:
        self.session = session
        self.cfg = cfg
        self._on_apply = on_apply
        self._draw_size: tuple[int, int] | None = None
        self._draw_size_seen = False
        self._applied = self.target_size()
        self._settle_sec: float | None = None
        self._pending: tuple[int, int] | None = None

    @property
    def applied_size(self) -> tuple[int, int]:
        return self._applied

    def note_draw_rect(self, rect: tuple[int, int, int, int] | None) -> None:
        """Record the visualiser rect for this frame (None: no shell)."""
        self._draw_size = None if rect is None else (int(rect[2]), int(rect[3]))

    def target_size(self) -> tuple[int, int]:
        return live_content_size(
            session_project_size(self.session),
            self._draw_size,
            self.cfg.editor.preview_quality,
        )

    def tick(self, dt_sec: float) -> None:
        size = self.target_size()
        if not self._draw_size_seen and self._draw_size is not None:
            self._draw_size_seen = True
            self._settle_sec = None
            self._pending = size
            self._apply(size)
            return
        if size != self._pending:
            self._pending = size
            self._settle_sec = (
                None if size == self._applied else VISUALISER_RESOLUTION_SETTLE_SEC
            )
            return
        if self._settle_sec is None:
            return
        self._settle_sec -= max(0.0, dt_sec)
        if self._settle_sec > 0.0:
            return
        self._settle_sec = None
        self._apply(size)

    def _apply(self, size: tuple[int, int]) -> None:
        if size == self._applied:
            return
        self._applied = size
        self._on_apply(size)
