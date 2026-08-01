"""Pinned header notification timing for the live tuning panel."""

from __future__ import annotations

import time
from typing import NamedTuple

NOTIFICATION_DURATION_SEC = 5.0


class PanelNotificationActive(NamedTuple):
    """Active notification lines for the tuning panel header."""

    persistent_message: str | None
    message: str | None
    remaining_sec: float


class PanelNotificationHost:
    """Notification state: optional persistent line plus one timed toast."""

    def __init__(self) -> None:
        self._message: str | None = None
        self._deadline = 0.0
        self._persistent_message: str | None = None

    def show(self, message: str) -> None:
        now = time.monotonic()
        self._message = message
        self._deadline = now + NOTIFICATION_DURATION_SEC

    def set_persistent(self, message: str | None) -> None:
        self._persistent_message = message

    def clear_expired(self) -> None:
        if self._message is not None and time.monotonic() >= self._deadline:
            self._message = None

    def active(self) -> PanelNotificationActive:
        timed: str | None = None
        remaining = 0.0
        if self._message is not None:
            remaining = max(0.0, self._deadline - time.monotonic())
            if remaining > 0:
                timed = self._message
            else:
                remaining = 0.0
        return PanelNotificationActive(
            persistent_message=self._persistent_message,
            message=timed,
            remaining_sec=remaining,
        )
