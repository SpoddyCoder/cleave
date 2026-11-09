"""Mouse gestures on the timeline strip: focus a row, select a cue, seek, scrub.

The strip is a pygame texture, so hits come from the overlay's last compose
(``TimelineOverlay.hit_at``). Every action goes through ``TimelineControls``,
the same paths the strip keys use.
"""

from __future__ import annotations

from typing import Protocol

from cleave.viz.session import TuningSession
from cleave.viz.timeline_overlay import StripHit


class StripGeometry(Protocol):
    def hit_at(self, x: float, y: float) -> StripHit | None: ...

    def time_at_x(self, x: float) -> float | None: ...


class StripActions(Protocol):
    def focus_row(self, row: int) -> None: ...

    def select_cue_near(self, slot: str, t_sec: float, tolerance_sec: float) -> bool: ...

    def seek_to(self, t_sec: float) -> None: ...


class TimelinePointer:
    """Left-button press, drag, and release on the open strip."""

    def __init__(
        self,
        geometry: StripGeometry,
        actions: StripActions,
        session: TuningSession,
    ) -> None:
        self._geometry = geometry
        self._actions = actions
        self._session = session
        self._scrubbing = False
        self._pending_t: float | None = None

    @property
    def scrubbing(self) -> bool:
        return self._scrubbing

    def press(self, x: float, y: float) -> bool:
        """Handle a left press. False when the point misses the ruler and rows."""
        self.cancel()
        hit = self._geometry.hit_at(x, y)
        if hit is None:
            return False
        if hit.row is not None:
            self._actions.focus_row(hit.row)
            if hit.t_sec is None:
                return True
            z_order = self._session.layer_z_order
            if hit.row < len(z_order) and self._actions.select_cue_near(
                z_order[hit.row], hit.t_sec, hit.cue_tolerance_sec
            ):
                return True
        if hit.t_sec is None:
            return True
        self._actions.seek_to(hit.t_sec)
        self._scrubbing = True
        return True

    def motion(self, x: float) -> None:
        if not self._scrubbing:
            return
        t_sec = self._geometry.time_at_x(x)
        if t_sec is not None:
            self._pending_t = t_sec

    def release(self) -> None:
        if not self._scrubbing:
            return
        self.tick()
        self._scrubbing = False

    def cancel(self) -> None:
        """Stop a scrub without applying a pending target."""
        self._scrubbing = False
        self._pending_t = None

    def tick(self) -> None:
        """Apply the latest scrub target once per frame."""
        if not self._session.timeline.panel_open:
            self.cancel()
            return
        if self._pending_t is None:
            return
        t_sec = self._pending_t
        self._pending_t = None
        self._actions.seek_to(t_sec)
