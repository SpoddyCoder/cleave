"""Transport bar actions: play and pause, the clock, and the bar number.

The shell host draws the bar and reports pointer gestures here. A drag steps
from where it started, so a seek that has not reached the audible clock yet
does not shorten the next step.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable, Sequence
from enum import Enum

from cleave.viz.inline_edit import InlineEditController
from cleave.viz.playback import PlaybackState, current_sec, format_mmss, toggle_pause

# One drag step moves the clock this many seconds, or one bar.
TIME_DRAG_STEP_SEC = 1.0

TIME_ENTRY_ERROR = "Enter a time as M:SS or seconds"


class TransportField(Enum):
    """An interactive part of the transport bar. Also the inline edit target."""

    PLAY = "play"
    TIME = "time"
    BAR = "bar"


def parse_clock_text(text: str) -> float | None:
    """Seconds from ``SS``, ``M:SS``, or ``H:MM:SS``, each part may be decimal.

    Every part after the first must be below 60. Returns None when the text
    is not a time.
    """
    parts = text.strip().split(":")
    if not parts or len(parts) > 3:
        return None
    total = 0.0
    for index, part in enumerate(parts):
        try:
            value = float(part)
        except ValueError:
            return None
        if value < 0.0 or value != value:
            return None
        if index and value >= 60.0:
            return None
        total = total * 60.0 + value
    return total


def bar_at(position_sec: float, downbeat_times: Sequence[float]) -> int:
    """1-based bar at *position_sec*. Before the first downbeat is bar 1."""
    return max(1, bisect.bisect_right(downbeat_times, position_sec))


def bar_entry_error(bar_count: int) -> str:
    return f"Enter a bar from 1 to {bar_count}"


def parse_bar_text(text: str, bar_count: int) -> int | None:
    """A bar number in ``1..bar_count``, or None."""
    try:
        bar = int(text.strip())
    except ValueError:
        return None
    if 1 <= bar <= bar_count:
        return bar
    return None


class TransportControls:
    """Pause, seek, and bar jumps from the transport bar."""

    def __init__(
        self,
        playback: PlaybackState,
        duration_sec: float,
        downbeat_times: Sequence[float],
        inline_edit: InlineEditController,
        seek_to: Callable[[float], None],
    ) -> None:
        self._playback = playback
        self._duration_sec = duration_sec
        self._downbeats = tuple(downbeat_times)
        self._inline_edit = inline_edit
        self._seek_to = seek_to
        self._drag_field: TransportField | None = None
        self._drag_origin = 0.0
        self._drag_steps = 0

    @property
    def has_bars(self) -> bool:
        return bool(self._downbeats)

    def toggle_pause(self) -> None:
        toggle_pause(self._playback, self._duration_sec)

    def position_sec(self) -> float:
        return current_sec(self._playback, self._duration_sec)

    def begin_drag(self, field: TransportField) -> None:
        """Anchor a drag on the clock or the bar at the current playhead."""
        if field is TransportField.BAR and not self.has_bars:
            self._drag_field = None
            return
        position = self.position_sec()
        self._drag_field = field
        self._drag_steps = 0
        self._drag_origin = (
            float(bar_at(position, self._downbeats))
            if field is TransportField.BAR
            else position
        )

    def drag_step(self, field: TransportField, steps: int) -> None:
        """Move the drag *steps* further from its anchor and seek there."""
        if self._drag_field is not field or steps == 0:
            return
        self._drag_steps += steps
        if field is TransportField.BAR:
            self.seek_bar(int(self._drag_origin) + self._drag_steps)
        else:
            self._seek_to(self._drag_origin + self._drag_steps * TIME_DRAG_STEP_SEC)

    def end_drag(self) -> None:
        self._drag_field = None
        self._drag_steps = 0

    def seek_bar(self, bar: int) -> None:
        """Seek to the downbeat that starts *bar*, clamped to the grid."""
        if not self._downbeats:
            return
        index = max(0, min(bar - 1, len(self._downbeats) - 1))
        self._seek_to(self._downbeats[index])

    def begin_entry(self, field: TransportField) -> None:
        """Open a text field on the clock or the bar, filled with its value."""
        position = self.position_sec()
        if field is TransportField.TIME:
            self._inline_edit.begin_text(
                field,
                format_mmss(position),
                self._commit_time,
                validate=_validate_time,
            )
        elif field is TransportField.BAR and self.has_bars:
            count = len(self._downbeats)
            self._inline_edit.begin_text(
                field,
                str(bar_at(position, self._downbeats)),
                self._commit_bar,
                validate=lambda text: (
                    None
                    if parse_bar_text(text, count) is not None
                    else bar_entry_error(count)
                ),
            )

    def _commit_time(self, text: str) -> None:
        seconds = parse_clock_text(text)
        if seconds is not None:
            self._seek_to(seconds)

    def _commit_bar(self, text: str) -> None:
        bar = parse_bar_text(text, len(self._downbeats))
        if bar is not None:
            self.seek_bar(bar)


def _validate_time(text: str) -> str | None:
    return None if parse_clock_text(text) is not None else TIME_ENTRY_ERROR
