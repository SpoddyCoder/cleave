"""Mouse gestures on the timeline strip: transport, arm, select, seek, scrub, zoom.

The corner buttons above the row labels play/pause and record. A press on
the ruler seeks and a held drag scrubs. A press on a layer row focuses it
and selects a nearby cue without moving the playhead; a double-click on a
row seeks, and holding the second press scrubs. A double-click on a row's
label (layer number and stem) arms it, and a press on its monitor eye
toggles the layer's visibility as its number key does (an overridden row,
or an armed row while recording). A right-click on a row focuses it and
returns that row's context menu (``timeline_context_menu``).

The wheel zooms the visible window about the time under the pointer, and
Shift+wheel or a sideways wheel pans it. While zoomed, a left drag on a row
or a middle drag on the ruler or a row pans, and the scrollbar under the rows
drags the window along the song (a press on its track centres it there).

The strip is a pygame texture, so hits come from the overlay's last compose
(``TimelineOverlay.hit_at``). Every action goes through ``TimelineControls``,
the same paths the strip keys use.
"""

from __future__ import annotations

import time
from typing import Callable, Literal, Protocol

from cleave.viz.context_menu import ContextMenuProvider
from cleave.viz.session import TuningSession
from cleave.viz.timeline_context_menu import TimelineRowMenuActions, timeline_row_menu
from cleave.viz.timeline_overlay import StripHit, StripTarget
from cleave.viz.timeline_view import (
    WHEEL_PAN_FRACTION,
    WHEEL_ZOOM_FACTOR,
    StripView,
)


# Same window and slack as ImGui's double-click defaults.
DOUBLE_CLICK_SEC: float = 0.30
DOUBLE_CLICK_PX: float = 6.0
# A held row press pans once the pointer moves this far sideways.
PAN_DRAG_PX: float = 4.0
# ImGui button indices, as ``imgui_host.mouse_button`` returns them.
LEFT_BUTTON: int = 0
RIGHT_BUTTON: int = 1
MIDDLE_BUTTON: int = 2
_SCROLLBAR_TARGETS = ("scroll_thumb", "scroll_track")


class StripGeometry(Protocol):
    def hit_at(self, x: float, y: float) -> StripHit | None: ...

    def time_at_x(self, x: float) -> float | None: ...

    def view_sec_per_px(self) -> float: ...

    def scrollbar_sec_per_px(self) -> float: ...

    def row_label_rect(self, row: int) -> tuple[int, int, int, int] | None: ...


class StripActions(TimelineRowMenuActions, Protocol):
    duration_sec: float

    def focus_row(self, row: int) -> None: ...

    def select_cue_near(self, slot: str, t_sec: float, tolerance_sec: float) -> bool: ...

    def seek_to(self, t_sec: float) -> None: ...

    def toggle_transport(self) -> None: ...

    def toggle_record(self) -> None: ...

    def toggle_arm_row(self, row: int) -> None: ...

    def toggle_row_visibility(self, row: int) -> None: ...

    def strip_target_pressable(self, target: str, row: int | None) -> bool: ...


class TimelinePointer:
    """Press, drag, release, and wheel on the open strip."""

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
        self._over_ruler = False
        self._over_scrollbar = False
        self._pending_t: float | None = None
        # Held drag that moves the window: a pan, or the scrollbar thumb.
        self._drag: Literal["pan", "thumb"] | None = None
        self._drag_x = 0.0
        self._drag_start_sec = 0.0
        self._drag_sec_per_px = 0.0
        # X of a held row press that has not yet moved far enough to pan.
        self._pan_pending_x: float | None = None
        # Last row press: (time, x, y, row, target), for double-click detection.
        self._last_row_press: (
            tuple[float, float, float, int, StripTarget | None] | None
        ) = None

    @property
    def scrubbing(self) -> bool:
        return self._scrubbing

    @property
    def panning(self) -> bool:
        """True while a drag on the ruler or rows moves the window."""
        return self._drag == "pan"

    @property
    def scrollbar_active(self) -> bool:
        """True while the thumb is dragged, or the pointer rests on a scrollbar that can move."""
        return self._drag == "thumb" or (
            self._drag is None and self._over_scrollbar and self._view.zoomed
        )

    @property
    def _view(self) -> StripView:
        return self._session.timeline.strip_view

    @property
    def over_ruler(self) -> bool:
        """True while the pointer rests on the time scale, clear of the buttons."""
        return self._over_ruler

    @property
    def hover_pressable(self) -> bool:
        """True while the hovered control would act on a press.

        Read each frame: an eye stops acting when playback starts, and
        record when the timeline locks, with no mouse motion.
        """
        hover = self._session.timeline.strip_hover
        if hover is None:
            return False
        target, row = hover
        return self._actions.strip_target_pressable(target, row)

    def context_row_at(self, x: float, y: float) -> int | None:
        """Layer row under a screen point, for a right-click menu, or None."""
        hit = self._geometry.hit_at(x, y)
        if hit is None or hit.row is None:
            return None
        if self._actions.row_slot(hit.row) is None:
            return None
        return hit.row

    def row_menu(self, row: int) -> ContextMenuProvider:
        """Focus *row* and return its context menu."""
        self._last_row_press = None
        self._actions.focus_row(row)
        return timeline_row_menu(self._actions, self._session, row)

    def row_menu_anchor(self, row: int) -> tuple[float, float] | None:
        """Screen point under *row*'s label, where a keyboard-opened menu hangs."""
        rect = self._geometry.row_label_rect(row)
        if rect is None:
            return None
        x, y, _w, h = rect
        return (float(x), float(y + h))

    def press(self, x: float, y: float, button: int = LEFT_BUTTON) -> bool:
        """Handle a left or middle press. False when the point misses the strip."""
        self.cancel()
        hit = self._geometry.hit_at(x, y)
        if hit is None:
            self._last_row_press = None
            return False
        if button == MIDDLE_BUTTON:
            self._last_row_press = None
            if hit.target is None and hit.t_sec is not None:
                self._begin_pan(x)
            return True
        if button != LEFT_BUTTON:
            return False
        if hit.row is None:
            self._last_row_press = None
            if hit.target == "play":
                self._actions.toggle_transport()
            elif hit.target == "record":
                self._actions.toggle_record()
            elif hit.target in _SCROLLBAR_TARGETS:
                if hit.target == "scroll_track" and hit.t_sec is not None:
                    self._view.centre_on(hit.t_sec, self._actions.duration_sec)
                self._begin_thumb_drag(x)
            elif hit.t_sec is not None:
                self._start_scrub(hit.t_sec)
            return True
        if hit.target == "eye":
            self._last_row_press = None
            self._actions.toggle_row_visibility(hit.row)
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
        if self._view.zoomed:
            self._pan_pending_x = x
        return True

    def _begin_pan(self, x: float) -> None:
        """Hold the time under *x* under the pointer. Nothing to pan at full zoom."""
        self._pan_pending_x = None
        if not self._view.zoomed:
            return
        self._begin_drag("pan", x, self._geometry.view_sec_per_px())

    def _begin_thumb_drag(self, x: float) -> None:
        if not self._view.zoomed:
            return
        self._begin_drag("thumb", x, self._geometry.scrollbar_sec_per_px())

    def _begin_drag(
        self, kind: Literal["pan", "thumb"], x: float, sec_per_px: float
    ) -> None:
        view = self._view
        self._drag = kind
        self._drag_x = x
        self._drag_start_sec = view.window(self._actions.duration_sec)[0]
        self._drag_sec_per_px = sec_per_px
        view.held = True

    def _drag_to(self, x: float) -> None:
        delta_sec = (x - self._drag_x) * self._drag_sec_per_px
        # A pan drags the content; the thumb drags the window.
        if self._drag == "pan":
            delta_sec = -delta_sec
        self._view.pan_to(
            self._drag_start_sec + delta_sec, self._actions.duration_sec
        )

    def wheel(self, x: float, dx: float, dy: float, *, shift: bool = False) -> None:
        """Zoom about the time under *x*; Shift or a sideways wheel pans."""
        if self._drag is not None or self._scrubbing:
            return
        anchor = self._geometry.time_at_x(x)
        if anchor is None:
            return
        view = self._view
        duration = self._actions.duration_sec
        # Shift+wheel up pans toward the song start, as a sideways scroll does.
        pan_notches = dx - dy if shift else dx
        if pan_notches:
            start, end = view.window(duration)
            view.pan_by(pan_notches * WHEEL_PAN_FRACTION * (end - start), duration)
        if dy and not shift:
            view.zoom_at(anchor, WHEEL_ZOOM_FACTOR**dy, duration)

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
        self._view.held = True

    def motion(self, x: float, y: float) -> None:
        if self._scrubbing:
            t_sec = self._geometry.time_at_x(x)
            if t_sec is not None:
                self._pending_t = t_sec
            return
        pending_x = self._pan_pending_x
        if pending_x is not None and abs(x - pending_x) >= PAN_DRAG_PX:
            self._last_row_press = None
            self._begin_pan(pending_x)
        if self._drag is not None:
            self._drag_to(x)
            return
        self._update_hover(x, y)

    def release(self) -> None:
        if self._scrubbing:
            self.tick()
        self.cancel()

    def _update_hover(self, x: float, y: float) -> None:
        hit = self._geometry.hit_at(x, y)
        self._over_scrollbar = hit is not None and hit.target in _SCROLLBAR_TARGETS
        hover = (
            (hit.target, hit.row)
            if hit is not None and hit.target and not self._over_scrollbar
            else None
        )
        self._session.timeline.strip_hover = hover
        self._over_ruler = (
            hit is not None
            and hit.row is None
            and hit.target is None
            and hit.t_sec is not None
        )

    def clear_hover(self) -> None:
        self._session.timeline.strip_hover = None
        self._over_ruler = False
        self._over_scrollbar = False

    def cancel(self) -> None:
        """Stop a scrub or drag without applying a pending scrub target."""
        self._scrubbing = False
        self._pending_t = None
        self._drag = None
        self._pan_pending_x = None
        self._view.held = False

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
