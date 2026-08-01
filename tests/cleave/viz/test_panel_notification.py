"""Unit tests for PanelNotificationHost."""

from __future__ import annotations

import time
from unittest.mock import patch

from cleave.viz.panel_notification import (
    NOTIFICATION_DURATION_SEC,
    PanelNotificationHost,
)


def test_timed_notification_active_and_expiry() -> None:
    host = PanelNotificationHost()
    with patch.object(time, "monotonic", return_value=10.0):
        host.show("hello")
        active = host.active()
    assert active.persistent_message is None
    assert active.message == "hello"
    assert active.remaining_sec == NOTIFICATION_DURATION_SEC

    with patch.object(
        time, "monotonic", return_value=10.0 + NOTIFICATION_DURATION_SEC + 0.1
    ):
        host.clear_expired()
        active = host.active()
    assert active.message is None
    assert active.remaining_sec == 0.0


def test_persistent_and_timed_stack_in_active() -> None:
    host = PanelNotificationHost()
    host.set_persistent("No presets in bed roles folder")
    with patch.object(time, "monotonic", return_value=50.0):
        host.show("Saved")
        active = host.active()
    assert active.persistent_message == "No presets in bed roles folder"
    assert active.message == "Saved"
    assert active.remaining_sec > 0

    host.set_persistent(None)
    with patch.object(time, "monotonic", return_value=50.0):
        active = host.active()
    assert active.persistent_message is None
    assert active.message == "Saved"
