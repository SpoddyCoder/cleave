"""Visible time window of the timeline strip: zoom, pan, and playhead follow.

The strip maps ``window(duration_sec)`` onto its bar width. ``span_sec`` of
None shows the whole song. Pure state and arithmetic, no pygame.
"""

from __future__ import annotations

from dataclasses import dataclass

# Shortest window the strip zooms in to.
MIN_VIEW_SPAN_SEC: float = 1.0
# Window scale per wheel notch.
WHEEL_ZOOM_FACTOR: float = 1.25
# Share of the window a wheel notch pans.
WHEEL_PAN_FRACTION: float = 0.1
# Where the playhead lands, from the left, when playback pages the window.
FOLLOW_LEAD_FRACTION: float = 0.1

_EPS: float = 1e-9


@dataclass
class StripView:
    start_sec: float = 0.0
    span_sec: float | None = None
    # A pan, scrollbar drag, or scrub is held; the window does not follow.
    held: bool = False
    # Playhead position at the last ``follow_playhead``.
    followed_sec: float | None = None

    @property
    def zoomed(self) -> bool:
        return self.span_sec is not None

    def window(self, duration_sec: float) -> tuple[float, float]:
        """Visible ``(start, end)`` in song seconds, inside ``[0, duration_sec]``."""
        if duration_sec <= 0:
            return (0.0, 0.0)
        if self.span_sec is None or self.span_sec >= duration_sec:
            return (0.0, float(duration_sec))
        span = max(_EPS, float(self.span_sec))
        start = max(0.0, min(float(self.start_sec), duration_sec - span))
        return (start, start + span)

    def reset(self) -> None:
        self.start_sec = 0.0
        self.span_sec = None

    def zoom_at(self, anchor_sec: float, factor: float, duration_sec: float) -> None:
        """Scale the window by *factor* (above 1 zooms in) about *anchor_sec*.

        The anchor keeps its place across the bar. Zooming out to the whole
        song clears the window.
        """
        if duration_sec <= 0 or factor <= 0:
            return
        start, end = self.window(duration_sec)
        span = end - start
        if span <= 0:
            return
        min_span = min(MIN_VIEW_SPAN_SEC, duration_sec)
        new_span = max(min_span, min(duration_sec, span / factor))
        if new_span >= duration_sec - _EPS:
            self.reset()
            return
        anchor = max(start, min(end, float(anchor_sec)))
        fraction = (anchor - start) / span
        self.span_sec = new_span
        self.pan_to(anchor - fraction * new_span, duration_sec)

    def pan_to(self, start_sec: float, duration_sec: float) -> None:
        """Move the window so it starts at *start_sec*, clamped to the song."""
        if self.span_sec is None or duration_sec <= 0:
            return
        if self.span_sec >= duration_sec:
            self.reset()
            return
        self.start_sec = max(0.0, min(float(start_sec), duration_sec - self.span_sec))

    def pan_by(self, delta_sec: float, duration_sec: float) -> None:
        start, _end = self.window(duration_sec)
        self.pan_to(start + delta_sec, duration_sec)

    def centre_on(self, t_sec: float, duration_sec: float) -> None:
        start, end = self.window(duration_sec)
        self.pan_to(t_sec - (end - start) / 2.0, duration_sec)

    def follow_playhead(
        self, position_sec: float, duration_sec: float, *, paused: bool
    ) -> None:
        """Keep a moving playhead in a zoomed window. Call once per frame.

        Playback that runs off the window it was in pages the window forward.
        A paused seek to a time outside the window recentres on it. A window
        panned away from a playing playhead stays put, and nothing moves while
        a gesture is held.
        """
        previous = self.followed_sec
        self.followed_sec = position_sec
        if self.held or self.span_sec is None or previous is None:
            return
        if position_sec == previous:
            return
        start, end = self.window(duration_sec)
        if start <= position_sec <= end:
            return
        if paused:
            self.centre_on(position_sec, duration_sec)
            return
        if not start <= previous <= end:
            return
        if position_sec > end:
            self.pan_to(
                position_sec - FOLLOW_LEAD_FRACTION * (end - start), duration_sec
            )
        else:
            self.centre_on(position_sec, duration_sec)
