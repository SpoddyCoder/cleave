"""Transport bar actions: play and pause, rewind and forward, the clock, and the bar.

The shell host draws the bar and reports pointer gestures here. A drag steps
from where it started, so a seek that has not reached the audible clock yet
does not shorten the next step.
"""

from __future__ import annotations

import bisect
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum

from cleave.viz.inline_edit import InlineEditController
from cleave.viz.playback import PlaybackState, current_sec, format_mmss, toggle_pause

# One drag step moves the clock this many seconds, or one bar.
TIME_DRAG_STEP_SEC = 1.0

# One click on rewind or forward moves the playhead this many seconds.
TRANSPORT_STEP_SEC = 10.0

# Holding rewind or forward this long starts a fast seek instead of a step.
HOLD_DELAY_SEC = 0.35
# The fast seek starts at this many song seconds per second held...
HOLD_START_RATE = 8.0
# ...and speeds up evenly to this rate over HOLD_RAMP_SEC.
HOLD_MAX_RATE = 60.0
HOLD_RAMP_SEC = 4.0
# A fast seek moves the playhead at most this often, so audio is not flushed every frame.
HOLD_SEEK_INTERVAL_SEC = 0.1

TIME_ENTRY_ERROR = "Enter a time as M:SS or seconds"


class TransportField(Enum):
    """An interactive part of the transport bar. Also the inline edit target."""

    PLAY = "play"
    REWIND = "rewind"
    FORWARD = "forward"
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


def hold_seek_distance(seeking_sec: float) -> float:
    """Song seconds a fast seek covers after *seeking_sec* of seeking.

    The rate climbs evenly from ``HOLD_START_RATE`` to ``HOLD_MAX_RATE`` over
    ``HOLD_RAMP_SEC``, then holds.
    """
    t = max(0.0, seeking_sec)
    climb = HOLD_MAX_RATE - HOLD_START_RATE
    if t <= HOLD_RAMP_SEC:
        return HOLD_START_RATE * t + climb * t * t / (2.0 * HOLD_RAMP_SEC)
    ramp = HOLD_START_RATE * HOLD_RAMP_SEC + climb * HOLD_RAMP_SEC * 0.5
    return ramp + HOLD_MAX_RATE * (t - HOLD_RAMP_SEC)


@dataclass
class _HoldSeek:
    """A rewind or forward button being held down."""

    forward: bool
    origin_sec: float
    held_sec: float = 0.0
    since_seek_sec: float = 0.0
    last_target: float | None = None


def hold_paused(
    playback: PlaybackState, pause_toggle: Callable[[], None]
) -> Callable[[], None]:
    """Pause playback; the returned call resumes it if this call paused it."""
    resume = not playback.paused
    if resume:
        pause_toggle()

    def restore() -> None:
        if resume and playback.paused:
            pause_toggle()

    return restore


class TransportControls:
    """Pause, seek, and bar jumps from the transport bar."""

    def __init__(
        self,
        playback: PlaybackState,
        duration_sec: float,
        bar_times: Callable[[], Sequence[float]],
        inline_edit: InlineEditController,
        seek_to: Callable[[float], None],
    ) -> None:
        self._playback = playback
        self._duration_sec = duration_sec
        self._bar_times = bar_times
        self._inline_edit = inline_edit
        self._seek_to = seek_to
        self._drag_field: TransportField | None = None
        self._drag_origin = 0.0
        self._drag_steps = 0
        self._hold: _HoldSeek | None = None

    @property
    def has_bars(self) -> bool:
        return bool(self._bar_times())

    @property
    def bar_times(self) -> Sequence[float]:
        """The bar grid at the current bar phase."""
        return self._bar_times()

    def toggle_pause(self) -> None:
        toggle_pause(self._playback, self._duration_sec)

    def step(self, forward: bool) -> None:
        """Seek ``TRANSPORT_STEP_SEC`` forward or back from the playhead."""
        delta = TRANSPORT_STEP_SEC if forward else -TRANSPORT_STEP_SEC
        self._seek_to(max(0.0, min(self._duration_sec, self.position_sec() + delta)))

    def jump(self, forward: bool) -> None:
        """Seek to the end of the song, or back to its start."""
        self._seek_to(self._duration_sec if forward else 0.0)

    def begin_hold(self, forward: bool) -> None:
        """Start timing a press on rewind or forward, from the current playhead."""
        self._hold = _HoldSeek(forward, self.position_sec())

    def hold_tick(self, dt_sec: float) -> None:
        """Advance a held button; past ``HOLD_DELAY_SEC`` it fast seeks."""
        hold = self._hold
        if hold is None:
            return
        hold.held_sec += max(0.0, dt_sec)
        seeking = hold.held_sec - HOLD_DELAY_SEC
        if seeking <= 0.0:
            return
        hold.since_seek_sec += max(0.0, dt_sec)
        if hold.last_target is not None and hold.since_seek_sec < HOLD_SEEK_INTERVAL_SEC:
            return
        hold.since_seek_sec = 0.0
        distance = hold_seek_distance(seeking)
        target = hold.origin_sec + (distance if hold.forward else -distance)
        target = max(0.0, min(self._duration_sec, target))
        if target != hold.last_target:
            hold.last_target = target
            self._seek_to(target)

    @property
    def hold_seeking(self) -> bool:
        """True once a held button has passed ``HOLD_DELAY_SEC``, so its release is not a click."""
        return self._hold is not None and self._hold.held_sec > HOLD_DELAY_SEC

    def end_hold(self) -> None:
        self._hold = None

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
            float(bar_at(position, self._bar_times()))
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
        bars = self._bar_times()
        if not bars:
            return
        index = max(0, min(bar - 1, len(bars) - 1))
        self._seek_to(bars[index])

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
            count = len(self._bar_times())
            self._inline_edit.begin_text(
                field,
                str(bar_at(position, self._bar_times())),
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
        bar = parse_bar_text(text, len(self._bar_times()))
        if bar is not None:
            self.seek_bar(bar)


def _validate_time(text: str) -> str | None:
    return None if parse_clock_text(text) is not None else TIME_ENTRY_ERROR
