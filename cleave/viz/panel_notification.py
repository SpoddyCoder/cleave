"""Pinned header notification timing for the live tuning panel."""

from __future__ import annotations

import time
from typing import NamedTuple

from cleave.easing import ease_out_cubic

# Settled accent-text display after the attention swipe.
NOTIFICATION_DURATION_SEC = 5.0
NOTIFICATION_ATTENTION_SWIPE_IN_SEC = 0.25
NOTIFICATION_ATTENTION_HOLD_SEC = 1.0
NOTIFICATION_ATTENTION_SWIPE_OUT_SEC = 0.25

NOTIFICATION_ATTENTION_DURATION_SEC = (
    NOTIFICATION_ATTENTION_SWIPE_IN_SEC
    + NOTIFICATION_ATTENTION_HOLD_SEC
    + NOTIFICATION_ATTENTION_SWIPE_OUT_SEC
)
NOTIFICATION_TOTAL_DURATION_SEC = (
    NOTIFICATION_ATTENTION_DURATION_SEC + NOTIFICATION_DURATION_SEC
)


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


def notification_attention(elapsed_sec: float) -> NotificationAttention:
    """Return swipe/hold visuals for *elapsed_sec* since the notification appeared."""
    t = max(0.0, elapsed_sec)
    swipe_in = NOTIFICATION_ATTENTION_SWIPE_IN_SEC
    hold = NOTIFICATION_ATTENTION_HOLD_SEC
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


def notification_attention_bucket(elapsed_sec: float) -> tuple[str, int, bool, bool]:
    """Quantized attention signature for panel cache invalidation during swipes."""
    visual = notification_attention(elapsed_sec)
    fill_q = int(round(max(0.0, min(1.0, visual.fill_progress)) * 32.0))
    return visual.phase, fill_q, visual.fill_from_left, visual.text_on_fill


class PanelNotificationHost:
    """Notification state: optional persistent line plus one timed toast."""

    def __init__(self) -> None:
        self._message: str | None = None
        self._shown_at = 0.0
        self._deadline = 0.0
        self._persistent_message: str | None = None
        self._persistent_shown_at = 0.0

    def show(self, message: str) -> None:
        now = time.monotonic()
        self._message = message
        self._shown_at = now
        self._deadline = now + NOTIFICATION_TOTAL_DURATION_SEC

    def set_persistent(self, message: str | None) -> None:
        if message == self._persistent_message:
            return
        self._persistent_message = message
        self._persistent_shown_at = time.monotonic() if message is not None else 0.0

    def clear_expired(self) -> None:
        if self._message is not None and time.monotonic() >= self._deadline:
            self._message = None

    def active(self) -> PanelNotificationActive:
        now = time.monotonic()
        timed: str | None = None
        remaining = 0.0
        elapsed = 0.0
        if self._message is not None:
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
