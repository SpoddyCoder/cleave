"""Tests for libprojectM log capture and panel notification drain."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cleave.projectm import (
    PROJECTM_LOG_LEVEL_DEBUG,
    PROJECTM_LOG_LEVEL_ERROR,
    PROJECTM_LOG_LEVEL_WARN,
    _handle_log_message,
    drain_log_messages,
)
from cleave.projectm_health import (
    PROJECTM_LOG_NOTIFICATION_PREFIX,
    ProjectMLogNotifyTracker,
    drain_projectm_log_notifications,
)


@pytest.fixture(autouse=True)
def _clear_log_queue() -> None:
    drain_log_messages()


def test_handle_log_message_queues_warn_and_above() -> None:
    _handle_log_message("  missing texture  ", PROJECTM_LOG_LEVEL_WARN)
    _handle_log_message("shader failed", PROJECTM_LOG_LEVEL_ERROR)
    assert drain_log_messages() == ["missing texture", "shader failed"]


def test_handle_log_message_ignores_debug() -> None:
    _handle_log_message("trace detail", PROJECTM_LOG_LEVEL_DEBUG)
    assert drain_log_messages() == []


def test_handle_log_message_skips_blank() -> None:
    _handle_log_message("   \n  ", PROJECTM_LOG_LEVEL_WARN)
    assert drain_log_messages() == []


def test_drain_projectm_log_notifications_prefixes_and_dedupes() -> None:
    _handle_log_message("[TextureManager] Failed to find worms", PROJECTM_LOG_LEVEL_WARN)
    _handle_log_message("[TextureManager] Failed to find worms", PROJECTM_LOG_LEVEL_WARN)
    tracker = ProjectMLogNotifyTracker()
    notify = MagicMock()

    drain_projectm_log_notifications(on_notification=notify, log_notify_tracker=tracker)
    notify.assert_called_once_with(
        f"{PROJECTM_LOG_NOTIFICATION_PREFIX}[TextureManager] Failed to find worms"
    )

    notify.reset_mock()
    drain_projectm_log_notifications(on_notification=notify, log_notify_tracker=tracker)
    notify.assert_not_called()


def test_drain_projectm_log_notifications_prints_stderr_when_no_sink(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _handle_log_message("recoverable error", PROJECTM_LOG_LEVEL_ERROR)
    drain_projectm_log_notifications(on_notification=None)
    captured = capsys.readouterr()
    assert captured.err == "projectM: recoverable error\n"


def test_drain_projectm_log_notifications_drains_multiple_unique_messages() -> None:
    _handle_log_message("first warn", PROJECTM_LOG_LEVEL_WARN)
    _handle_log_message("second warn", PROJECTM_LOG_LEVEL_WARN)
    notify = MagicMock()
    tracker = ProjectMLogNotifyTracker()

    drain_projectm_log_notifications(on_notification=notify, log_notify_tracker=tracker)

    assert notify.call_count == 2
    notify.assert_any_call(f"{PROJECTM_LOG_NOTIFICATION_PREFIX}first warn")
    notify.assert_any_call(f"{PROJECTM_LOG_NOTIFICATION_PREFIX}second warn")


def test_handle_log_message_debug_stderr_only_with_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLEAVE_PROJECTM_LOG", "1")
    with patch("cleave.projectm.print") as print_mock:
        _handle_log_message("debug line", PROJECTM_LOG_LEVEL_DEBUG)
    print_mock.assert_called_once()
    assert drain_log_messages() == []
