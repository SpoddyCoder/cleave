"""Mouse gestures on the timeline strip: transport, arm, select, seek, scrub.

The corner buttons above the row labels play/pause and record. A press on
the ruler seeks and a held drag scrubs. A press on a layer row focuses it
and selects a nearby cue without moving the playhead; a double-click on a
row seeks, and holding the second press scrubs. A double-click on a row's
label (layer number and stem) arms it.

The strip is a pygame texture, so hits come from the overlay's last compose
(``TimelineOverlay.hit_at``). Every action goes through ``TimelineControls``,
the same paths the strip keys use.
"""

from __future__ import annotations

import time
from typing import Callable, Protocol

from cleave.viz.session import TuningSession
from cleave.viz.timeline_overlay import StripHit, StripTarget


# Same window and slack as ImGui's double-click defaults.
DOUBLE_CLICK_SEC: float = 0.30
DOUBLE_CLICK_PX: float = 6.0


class StripGeometry(Protocol):
    def hit_at(self, x: float, y: float) -> StripHit | None: ...

    def time_at_x(self, x: float) -> float | None: ...


class StripActions(Protocol):
    def focus_row(self, row: int) -> None: ...

    def select_cue_near(self, slot: str, t_sec: float, tolerance_sec: float) -> bool: ...

    def seek_to(self, t_sec: float) -> None: ...

    def toggle_transport(self) -> None: ...

    def toggle_record(self) -> None: ...

    def toggle_arm_row(self, row: int) -> None: ...


class TimelinePointer:
    """Left-button press, drag, and release on the open strip."""

    def __init__(
        self,
        geometry: StripGeometry,
        actions: StripActions,
        session: TuningSession,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._geometry = geometry
        self._actions = actions
        self._session = session
        self._clock = clock
        self._scrubbing = False
        self._pending_t: float | None = None
        # Last row press: (time, x, y, row, target), for double-click detection.
        self._last_row_press: (
            tuple[float, float, float, int, StripTarget | None] | None
        ) = None

    @property
    def scrubbing(self) -> bool:
        return self._scrubbing

    def press(self, x: float, y: float) -> bool:
        """Handle a left press. False when the point misses the ruler and rows."""
        self.cancel()
        hit = self._geometry.hit_at(x, y)
        if hit is None:
            self._last_row_press = None
            return False
        if hit.row is None:
            self._last_row_press = None
            if hit.target == "play":
                self._actions.toggle_transport()
            elif hit.target == "record":
                self._actions.toggle_record()
            elif hit.t_sec is not None:
                self._start_scrub(hit.t_sec)
            return True
        now = self._clock()
        double = self._is_double_click(now, x, y, hit.row, hit.target)
        if hit.target == "label":
            if double:
                self._last_row_press = None
                self._actions.toggle_arm_row(hit.row)
            else:
                self._actions.focus_row(hit.row)
                self._last_row_press = (now, x, y, hit.row, hit.target)
            return True
        self._actions.focus_row(hit.row)
        if hit.t_sec is None:
            self._last_row_press = None
            return True
        if double:
            self._last_row_press = None
            self._start_scrub(hit.t_sec)
            return True
        self._last_row_press = (now, x, y, hit.row, hit.target)
        z_order = self._session.layer_z_order
        if hit.row < len(z_order):
            self._actions.select_cue_near(z_order[hit.row], hit.t_sec, hit.cue_tolerance_sec)
        return True

    def _is_double_click(
        self, now: float, x: float, y: float, row: int, target: StripTarget | None
    ) -> bool:
        last = self._last_row_press
        if last is None:
            return False
        last_t, last_x, last_y, last_row, last_target = last
        return (
            row == last_row
            and target == last_target
            and now - last_t <= DOUBLE_CLICK_SEC
            and abs(x - last_x) <= DOUBLE_CLICK_PX
            and abs(y - last_y) <= DOUBLE_CLICK_PX
        )

    def _start_scrub(self, t_sec: float) -> None:
        self._actions.seek_to(t_sec)
        self._scrubbing = True

    def motion(self, x: float, y: float) -> None:
        if not self._scrubbing:
            self._update_hover(x, y)
            return
        t_sec = self._geometry.time_at_x(x)
        if t_sec is not None:
            self._pending_t = t_sec

    def release(self) -> None:
        if not self._scrubbing:
            return
        self.tick()
        self._scrubbing = False

    def _update_hover(self, x: float, y: float) -> None:
        hit = self._geometry.hit_at(x, y)
        hover = (hit.target, hit.row) if hit is not None and hit.target else None
        self._session.timeline.strip_hover = hover

    def clear_hover(self) -> None:
        self._session.timeline.strip_hover = None

    def cancel(self) -> None:
        """Stop a scrub without applying a pending target."""
        self._scrubbing = False
        self._pending_t = None

    def tick(self) -> None:
        """Apply the latest scrub target once per frame."""
        if not self._session.timeline.panel_open:
            self.cancel()
            self.clear_hover()
            return
        if self._pending_t is None:
            return
        t_sec = self._pending_t
        self._pending_t = None
        self._actions.seek_to(t_sec)
