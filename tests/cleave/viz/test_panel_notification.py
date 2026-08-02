"""Unit tests for PanelNotificationHost."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from cleave.viz.panel_notification import (
    NOTIFICATION_ATTENTION_DURATION_SEC,
    NOTIFICATION_ATTENTION_HOLD_SEC,
    NOTIFICATION_ATTENTION_SWIPE_IN_SEC,
    NOTIFICATION_DURATION_SEC,
    NOTIFICATION_TOTAL_DURATION_SEC,
    PanelNotificationHost,
    notification_attention,
)


def test_timed_notification_active_and_expiry() -> None:
    host = PanelNotificationHost()
    with patch.object(time, "monotonic", return_value=10.0):
        host.show("hello")
        active = host.active()
    assert active.persistent_message is None
    assert active.message == "hello"
    assert active.remaining_sec == NOTIFICATION_TOTAL_DURATION_SEC
    assert active.elapsed_sec == 0.0

    with patch.object(
        time, "monotonic", return_value=10.0 + NOTIFICATION_TOTAL_DURATION_SEC + 0.1
    ):
        host.clear_expired()
        active = host.active()
    assert active.message is None
    assert active.remaining_sec == 0.0


def test_persistent_and_timed_stack_in_active() -> None:
    host = PanelNotificationHost()
    with patch.object(time, "monotonic", return_value=50.0):
        host.set_persistent("No presets in bed roles folder")
        host.show("Saved")
        active = host.active()
    assert active.persistent_message == "No presets in bed roles folder"
    assert active.persistent_elapsed_sec == 0.0
    assert active.message == "Saved"
    assert active.remaining_sec > 0
    assert active.elapsed_sec == 0.0

    host.set_persistent(None)
    with patch.object(time, "monotonic", return_value=50.0):
        active = host.active()
    assert active.persistent_message is None
    assert active.message == "Saved"


def test_persistent_set_same_message_keeps_elapsed() -> None:
    host = PanelNotificationHost()
    with patch.object(time, "monotonic", return_value=10.0):
        host.set_persistent("err")
    with patch.object(time, "monotonic", return_value=12.5):
        host.set_persistent("err")
        active = host.active()
    assert active.persistent_elapsed_sec == 2.5


def test_notification_attention_phases() -> None:
    from cleave.viz.panel_notification import notification_attention_bucket

    mid_swipe_in = NOTIFICATION_ATTENTION_SWIPE_IN_SEC * 0.5
    visual = notification_attention(mid_swipe_in)
    assert visual.phase == "swipe_in"
    assert visual.fill_from_left is True
    assert visual.text_on_fill is True
    assert 0.0 < visual.fill_progress < 1.0

    hold_t = NOTIFICATION_ATTENTION_SWIPE_IN_SEC + NOTIFICATION_ATTENTION_HOLD_SEC * 0.5
    visual = notification_attention(hold_t)
    assert visual.phase == "hold"
    assert visual.fill_progress == 1.0
    assert visual.text_on_fill is True

    # Late swipe-in and hold can share fill_q=32; phase must still differ so the
    # panel redraws a true full-width fill instead of leaving a right-edge gap.
    late_swipe_in = NOTIFICATION_ATTENTION_SWIPE_IN_SEC - 1e-6
    assert notification_attention_bucket(late_swipe_in)[0] == "swipe_in"
    assert notification_attention_bucket(hold_t)[0] == "hold"
    assert notification_attention_bucket(late_swipe_in) != notification_attention_bucket(
        hold_t
    )

    swipe_out_t = NOTIFICATION_ATTENTION_SWIPE_IN_SEC + NOTIFICATION_ATTENTION_HOLD_SEC
    visual = notification_attention(swipe_out_t + 0.01)
    assert visual.phase == "swipe_out"
    assert visual.fill_from_left is False
    assert visual.text_on_fill is True
    assert visual.fill_progress < 1.0

    visual = notification_attention(NOTIFICATION_ATTENTION_DURATION_SEC - 0.01)
    assert visual.fill_from_left is False
    assert visual.text_on_fill is False
    assert visual.fill_progress < 0.45

    visual = notification_attention(NOTIFICATION_ATTENTION_DURATION_SEC + 0.01)
    assert visual.phase == "settled"
    assert visual.fill_progress == 0.0
    assert visual.text_on_fill is False


def test_settled_display_covers_notification_duration() -> None:
    host = PanelNotificationHost()
    with patch.object(time, "monotonic", return_value=100.0):
        host.show("warn")
    settled_start = 100.0 + NOTIFICATION_ATTENTION_DURATION_SEC
    with patch.object(time, "monotonic", return_value=settled_start):
        active = host.active()
    assert active.message == "warn"
    assert active.remaining_sec == pytest.approx(NOTIFICATION_DURATION_SEC)
    assert notification_attention(active.elapsed_sec).fill_progress == 0.0
