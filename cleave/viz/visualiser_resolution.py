"""Apply the project render size to the live visualiser once edits settle."""

from __future__ import annotations

from collections.abc import Callable

from cleave.viz.layer_preview_resolution import live_content_size
from cleave.viz.session import TuningSession

# Quiet time after the last render width/height change before the layer
# framebuffers are reallocated, so a held key does not reallocate every step.
VISUALISER_RESOLUTION_SETTLE_SEC = 0.25


class VisualiserResolutionSync:
    """Watch ``session.project.render`` size and reallocate the live framebuffers.

    Polling the session covers every source of change: stepping the Project >
    Render rows, revert, and editor-mode reloads.
    """

    def __init__(
        self,
        session: TuningSession,
        on_apply: Callable[[], None],
    ) -> None:
        self.session = session
        self._on_apply = on_apply
        self._applied = live_content_size(session)
        self._settle_sec: float | None = None
        self._pending: tuple[int, int] | None = None

    def tick(self, dt_sec: float) -> None:
        size = live_content_size(self.session)
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
        self._applied = size
        self._on_apply()
