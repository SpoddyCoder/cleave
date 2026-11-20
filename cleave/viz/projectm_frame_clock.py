"""Monotonic projectM frame clock (seconds since first frame).

libprojectM's ``projectm_set_frame_time`` expects a non-decreasing render clock,
not song playhead time. Feeding transport seconds freezes Milkdrop presets on
seek-backward until the playhead catches up again.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProjectMFrameClock:
    """Accumulates positive dt while unpaused; ignores seeks and transport jumps."""

    seconds: float = 0.0
    started: bool = False

    def advance(self, dt_sec: float, *, paused: bool) -> float:
        """Return the time to pass to ``projectm_set_frame_time`` this frame."""
        if paused:
            return self.seconds
        if not self.started:
            self.started = True
            self.seconds = 0.0
            return self.seconds
        if dt_sec > 0.0:
            self.seconds += dt_sec
        return self.seconds

    def skip(self, seconds: float) -> None:
        """Move the clock forward by `seconds`, paused or not.

        A paused frame that warms up a newly loaded preset renders projectM
        frames ahead of the held time; skipping keeps every layer's next
        frame time at or after them.
        """
        if self.started and seconds > 0.0:
            self.seconds += seconds
