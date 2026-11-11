"""Unit tests for PanelNotificationHost."""

from __future__ import annotations

import math
import time
from unittest.mock import patch

import pytest

from cleave.config_schema.editor import DEFAULT_NOTIFICATION_DISPLAY_SEC
from cleave.viz.panel_notification import (
    NOTIFICATION_ATTENTION_DURATION_SEC,
    NOTIFICATION_ATTENTION_HOLD_SEC,
    NOTIFICATION_ATTENTION_SWIPE_IN_SEC,
    PanelNotificationHost,
    notification_attention,
)


def test_timed_notification_active_and_expiry() -> None:
    host = PanelNotificationHost()
    with patch.object(time, "monotonic", return_value=10.0):
        host.show("hello", display_sec=DEFAULT_NOTIFICATION_DISPLAY_SEC)
        active = host.active()
    assert active.persistent_message is None
    assert active.message == "hello"
    assert active.remaining_sec == DEFAULT_NOTIFICATION_DISPLAY_SEC
    assert active.elapsed_sec == 0.0

    with patch.object(
        time,
        "monotonic",
        return_value=10.0 + DEFAULT_NOTIFICATION_DISPLAY_SEC + 0.1,
    ):
        host.clear_expired()
        active = host.active()
    assert active.message is None
    assert active.remaining_sec == 0.0


def test_until_dismissed_stays_until_dismissed() -> None:
    host = PanelNotificationHost()
    with patch.object(time, "monotonic", return_value=10.0):
        host.show("hello", display_sec=0)
        active = host.active()
    assert active.message == "hello"
    assert math.isinf(active.remaining_sec)

    with patch.object(time, "monotonic", return_value=10.0 + 10_000.0):
        host.clear_expired()
        active = host.active()
    assert active.message == "hello"
    assert math.isinf(active.remaining_sec)

    host.dismiss_timed()
    active = host.active()
    assert active.message is None
    assert active.remaining_sec == 0.0


def test_set_display_sec_retargets_active_toast() -> None:
    host = PanelNotificationHost()
    with patch.object(time, "monotonic", return_value=10.0):
        host.show("hello", display_sec=0)
        active = host.active()
    assert math.isinf(active.remaining_sec)

    with patch.object(time, "monotonic", return_value=12.0):
        host.set_display_sec(1)
        active = host.active()
    assert active.message == "hello"
    assert active.remaining_sec == pytest.approx(1.0)

    with patch.object(time, "monotonic", return_value=13.1):
        host.clear_expired()
        active = host.active()
    assert active.message is None


def test_set_display_sec_until_dismissed_clears_deadline() -> None:
    host = PanelNotificationHost()
    with patch.object(time, "monotonic", return_value=10.0):
        host.show("hello", display_sec=5)
        host.set_display_sec(0)
        active = host.active()
    assert active.message == "hello"
    assert math.isinf(active.remaining_sec)


def test_dismiss_timed_clears_before_deadline() -> None:
    host = PanelNotificationHost()
    with patch.object(time, "monotonic", return_value=10.0):
        host.show("hello", display_sec=20)
        host.dismiss_timed()
        active = host.active()
    assert active.message is None
    assert active.remaining_sec == 0.0


def test_persistent_and_timed_stack_in_active() -> None:
    host = PanelNotificationHost()
    with patch.object(time, "monotonic", return_value=50.0):
        host.set_persistent("No presets in bed roles folder")
        host.show("Saved", display_sec=DEFAULT_NOTIFICATION_DISPLAY_SEC)
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


def test_settled_display_covers_remaining_after_attention() -> None:
    host = PanelNotificationHost()
    with patch.object(time, "monotonic", return_value=100.0):
        host.show("warn", display_sec=DEFAULT_NOTIFICATION_DISPLAY_SEC)
    settled_start = 100.0 + NOTIFICATION_ATTENTION_DURATION_SEC
    with patch.object(time, "monotonic", return_value=settled_start):
        active = host.active()
    assert active.message == "warn"
    remaining = DEFAULT_NOTIFICATION_DISPLAY_SEC - NOTIFICATION_ATTENTION_DURATION_SEC
    assert active.remaining_sec == pytest.approx(remaining)
    assert notification_attention(active.elapsed_sec).fill_progress == 0.0


def test_attention_scroll_offset_waits_scrolls_pauses_and_snaps_back() -> None:
    from cleave.viz.panel_notification import (
        ATTENTION_SCROLL_END_PAUSE_SEC,
        ATTENTION_SCROLL_LEAD_SEC,
        attention_scroll_hold_sec,
        attention_scroll_offset,
        attention_scroll_sec,
    )

    scroll = attention_scroll_sec(40.0, 8.0)
    assert scroll > 0.0
    start = NOTIFICATION_ATTENTION_SWIPE_IN_SEC + ATTENTION_SCROLL_LEAD_SEC
    assert attention_scroll_offset(0.0, 40.0, scroll) == 0.0
    assert attention_scroll_offset(start, 40.0, scroll) == 0.0
    mid = attention_scroll_offset(start + scroll * 0.5, 40.0, scroll)
    assert 0.0 < mid < 40.0
    assert attention_scroll_offset(start + scroll, 40.0, scroll) == 40.0
    swipe_out_at = NOTIFICATION_ATTENTION_SWIPE_IN_SEC + attention_scroll_hold_sec(scroll)
    assert swipe_out_at == pytest.approx(start + scroll + ATTENTION_SCROLL_END_PAUSE_SEC)
    assert attention_scroll_offset(swipe_out_at - 0.01, 40.0, scroll) == 40.0
    assert attention_scroll_offset(swipe_out_at, 40.0, scroll) == 0.0


def test_attention_scroll_sec_scales_with_overflow() -> None:
    from cleave.viz.panel_notification import (
        ATTENTION_SCROLL_CHARS_PER_SEC,
        ATTENTION_SCROLL_MIN_SEC,
        attention_scroll_sec,
    )

    assert attention_scroll_sec(0.0, 8.0) == 0.0
    assert attention_scroll_sec(8.0, 8.0) == ATTENTION_SCROLL_MIN_SEC
    assert attention_scroll_sec(8.0 * 60, 8.0) == pytest.approx(
        60 / ATTENTION_SCROLL_CHARS_PER_SEC
    )


def test_attention_scroll_hold_defaults_when_text_fits() -> None:
    from cleave.viz.panel_notification import (
        attention_scroll_hold_sec,
        attention_scroll_offset,
    )

    assert attention_scroll_hold_sec(0.0) == NOTIFICATION_ATTENTION_HOLD_SEC
    assert attention_scroll_offset(0.6, 0.0, 0.0) == 0.0
    assert attention_scroll_offset(0.6, -12.0, 1.0) == 0.0


def test_notification_attention_custom_hold() -> None:
    hold = 3.0
    t = NOTIFICATION_ATTENTION_SWIPE_IN_SEC + 2.5
    assert notification_attention(t, hold_sec=hold).phase == "hold"
    assert notification_attention(t).phase == "settled"


def test_attention_clock_restarts_on_new_key() -> None:
    from cleave.viz.panel_notification import AttentionClock

    clock = AttentionClock()
    assert clock.elapsed("a", now=5.0) == 0.0
    assert clock.elapsed("a", now=6.5) == 1.5
    assert clock.elapsed("b", now=7.0) == 0.0
    assert clock.elapsed("b", now=7.25) == 0.25
