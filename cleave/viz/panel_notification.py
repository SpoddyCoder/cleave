"""Pinned header notification timing for the live tuning panel."""

from __future__ import annotations

import time

NOTIFICATION_DURATION_SEC = 5.0


class PanelNotificationHost:
    """Single-slot notification state with monotonic expiry."""

    def __init__(self) -> None:
        self._message: str | None = None
        self._deadline = 0.0

    def show(self, message: str) -> None:
        now = time.monotonic()
        self._message = message
        self._deadline = now + NOTIFICATION_DURATION_SEC

    def clear_expired(self) -> None:
        if self._message is not None and time.monotonic() >= self._deadline:
            self._message = None

    def active(self) -> tuple[str | None, float]:
        if self._message is None:
            return None, 0.0
        remaining = max(0.0, self._deadline - time.monotonic())
        if remaining <= 0:
            return None, 0.0
        return self._message, remaining
