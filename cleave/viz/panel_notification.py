"""Pinned header notification timing for the live tuning panel."""

from __future__ import annotations

import math
import time
from typing import NamedTuple

from cleave.easing import ease_out_cubic, smoothstep

NOTIFICATION_ATTENTION_SWIPE_IN_SEC = 0.25
NOTIFICATION_ATTENTION_HOLD_SEC = 1.0
NOTIFICATION_ATTENTION_SWIPE_OUT_SEC = 0.25

NOTIFICATION_ATTENTION_DURATION_SEC = (
    NOTIFICATION_ATTENTION_SWIPE_IN_SEC
    + NOTIFICATION_ATTENTION_HOLD_SEC
    + NOTIFICATION_ATTENTION_SWIPE_OUT_SEC
)


# A title too wide for its row scrolls to its end while the attention bar is
# up: it waits once the bar has swiped in, scrolls at a reading pace, pauses
# on the last words, and snaps back to the start when the bar slides off. The
# bar holds for as long as that takes.
ATTENTION_SCROLL_LEAD_SEC = 0.75
ATTENTION_SCROLL_CHARS_PER_SEC = 12.0
ATTENTION_SCROLL_MIN_SEC = 0.75
ATTENTION_SCROLL_END_PAUSE_SEC = 1.25


class NotificationAttention(NamedTuple):
    """Visual attention state for a warning/error notification row."""

    phase: str
    """swipe_in | hold | swipe_out | settled"""

    fill_progress: float
    """0..1 how much of the accent bar is present."""

    fill_from_left: bool
    """True while the bar grows from the left; False while it slides off right."""

    text_on_fill: bool
    """True when text should be black on the accent fill."""


class PanelNotificationActive(NamedTuple):
    """Active notification lines for the tuning panel header."""

    persistent_message: str | None
    persistent_elapsed_sec: float
    message: str | None
    remaining_sec: float
    elapsed_sec: float


def notification_attention(
    elapsed_sec: float, *, hold_sec: float = NOTIFICATION_ATTENTION_HOLD_SEC
) -> NotificationAttention:
    """Return swipe/hold visuals for *elapsed_sec* since the notification appeared."""
    t = max(0.0, elapsed_sec)
    swipe_in = NOTIFICATION_ATTENTION_SWIPE_IN_SEC
    hold = hold_sec
    swipe_out = NOTIFICATION_ATTENTION_SWIPE_OUT_SEC

    if t < swipe_in:
        u = 0.0 if swipe_in <= 0.0 else t / swipe_in
        return NotificationAttention(
            phase="swipe_in",
            fill_progress=ease_out_cubic(u),
            fill_from_left=True,
            text_on_fill=True,
        )
    if t < swipe_in + hold:
        return NotificationAttention(
            phase="hold",
            fill_progress=1.0,
            fill_from_left=True,
            text_on_fill=True,
        )
    if t < swipe_in + hold + swipe_out:
        u = 0.0 if swipe_out <= 0.0 else (t - swipe_in - hold) / swipe_out
        fill_progress = 1.0 - ease_out_cubic(u)
        return NotificationAttention(
            phase="swipe_out",
            fill_progress=fill_progress,
            fill_from_left=False,
            # Keep black text while the accent bar still covers most of the row.
            text_on_fill=fill_progress >= 0.45,
        )
    return NotificationAttention(
        phase="settled",
        fill_progress=0.0,
        fill_from_left=False,
        text_on_fill=False,
    )


def attention_scroll_sec(overflow_px: float, char_px: float) -> float:
    """Seconds to scroll *overflow_px* at reading pace; 0 when the text fits."""
    if overflow_px <= 0.0:
        return 0.0
    chars = overflow_px / max(1.0, char_px)
    return max(ATTENTION_SCROLL_MIN_SEC, chars / ATTENTION_SCROLL_CHARS_PER_SEC)


def attention_scroll_hold_sec(scroll_sec: float) -> float:
    """Bar hold that fits the lead, a *scroll_sec* scroll, and the end pause."""
    if scroll_sec <= 0.0:
        return NOTIFICATION_ATTENTION_HOLD_SEC
    return ATTENTION_SCROLL_LEAD_SEC + scroll_sec + ATTENTION_SCROLL_END_PAUSE_SEC


def attention_scroll_offset(
    elapsed_sec: float, overflow_px: float, scroll_sec: float
) -> float:
    """Leftward text offset in pixels, *elapsed_sec* into the attention swipe.

    *overflow_px* is how far the text runs past its row, and *scroll_sec*
    comes from :func:`attention_scroll_sec`. The offset is 0 before the scroll
    starts and from the start of the swipe out on.
    """
    if overflow_px <= 0.0 or scroll_sec <= 0.0:
        return 0.0
    swipe_in = NOTIFICATION_ATTENTION_SWIPE_IN_SEC
    swipe_out_at = swipe_in + attention_scroll_hold_sec(scroll_sec)
    t = elapsed_sec - swipe_in - ATTENTION_SCROLL_LEAD_SEC
    if t <= 0.0 or elapsed_sec >= swipe_out_at:
        return 0.0
    return overflow_px * smoothstep(min(1.0, t / scroll_sec))


def notification_attention_bucket(elapsed_sec: float) -> tuple[str, int, bool, bool]:
    """Quantized attention signature for panel cache invalidation during swipes."""
    visual = notification_attention(elapsed_sec)
    fill_q = int(round(max(0.0, min(1.0, visual.fill_progress)) * 32.0))
    return visual.phase, fill_q, visual.fill_from_left, visual.text_on_fill


class AttentionClock:
    """Seconds since *key* last changed, for an attention swipe on new content."""

    def __init__(self) -> None:
        self._key: object = None
        self._since = 0.0

    def elapsed(self, key: object, now: float | None = None) -> float:
        if now is None:
            now = time.monotonic()
        if key != self._key:
            self._key = key
            self._since = now
        return max(0.0, now - self._since)


class PanelNotificationHost:
    """Notification state: optional persistent line plus one timed toast."""

    def __init__(self) -> None:
        self._message: str | None = None
        self._shown_at = 0.0
        self._deadline: float | None = 0.0
        self._persistent_message: str | None = None
        self._persistent_shown_at = 0.0

    def show(self, message: str, *, display_sec: float) -> None:
        now = time.monotonic()
        self._message = message
        self._shown_at = now
        self._apply_display_sec(display_sec, now=now)

    def set_display_sec(self, display_sec: float) -> None:
        """Retarget the active timed toast to *display_sec* from now."""
        if self._message is None:
            return
        self._apply_display_sec(display_sec)

    def _apply_display_sec(self, display_sec: float, *, now: float | None = None) -> None:
        if display_sec <= 0:
            self._deadline = None
            return
        if now is None:
            now = time.monotonic()
        self._deadline = now + float(display_sec)

    def dismiss_timed(self) -> None:
        self._message = None
        self._deadline = 0.0

    def set_persistent(self, message: str | None) -> None:
        if message == self._persistent_message:
            return
        self._persistent_message = message
        self._persistent_shown_at = time.monotonic() if message is not None else 0.0

    def clear_expired(self) -> None:
        if (
            self._message is not None
            and self._deadline is not None
            and time.monotonic() >= self._deadline
        ):
            self._message = None

    def active(self) -> PanelNotificationActive:
        now = time.monotonic()
        timed: str | None = None
        remaining = 0.0
        elapsed = 0.0
        if self._message is not None:
            if self._deadline is None:
                remaining = math.inf
                timed = self._message
                elapsed = max(0.0, now - self._shown_at)
            else:
                remaining = max(0.0, self._deadline - now)
                if remaining > 0:
                    timed = self._message
                    elapsed = max(0.0, now - self._shown_at)
                else:
                    remaining = 0.0
        persistent_elapsed = 0.0
        if self._persistent_message is not None:
            persistent_elapsed = max(0.0, now - self._persistent_shown_at)
        return PanelNotificationActive(
            persistent_message=self._persistent_message,
            persistent_elapsed_sec=persistent_elapsed,
            message=timed,
            remaining_sec=remaining,
            elapsed_sec=elapsed,
        )
