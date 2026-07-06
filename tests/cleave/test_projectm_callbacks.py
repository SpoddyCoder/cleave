"""Tests for optional libprojectM callback bindings."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cleave.projectm import PresetLoadFailure, ProjectM


def _mock_lib_with_callbacks() -> MagicMock:
    lib = MagicMock()
    for name in (
        "projectm_set_preset_switch_failed_event_callback",
        "projectm_get_version_components",
        "projectm_get_version_string",
        "projectm_get_vcs_version_string",
        "projectm_free_string",
    ):
        setattr(lib, name, MagicMock())
    return lib


def test_switch_failed_handler_enqueues_and_drains() -> None:
    lib = _mock_lib_with_callbacks()
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    pm._failure_queue = __import__("collections").deque()
    pm._switch_failed_callback = None

    with patch("cleave.projectm._get_lib", return_value=lib):
        pm.set_preset_switch_failed_handler(pm._enqueue_preset_failure)
        callback = (
            lib.projectm_set_preset_switch_failed_event_callback.call_args.args[1]
        )
        callback(b"/tmp/bad.milk", b"parse error", None)

    failures = pm.drain_preset_failures()
    assert failures == [
        PresetLoadFailure(
            filename="/tmp/bad.milk", message="parse error", exhausted=False
        )
    ]
    assert pm.drain_preset_failures() == []


def test_clear_preset_switch_failed_handler() -> None:
    lib = _mock_lib_with_callbacks()
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    pm._failure_queue = __import__("collections").deque()
    pm._switch_failed_callback = MagicMock()

    with patch("cleave.projectm._get_lib", return_value=lib):
        pm.clear_preset_switch_failed_handler()

    lib.projectm_set_preset_switch_failed_event_callback.assert_called()
    assert pm._switch_failed_callback is None


def test_version_info_reads_components_and_strings() -> None:
    lib = _mock_lib_with_callbacks()
    lib.projectm_get_version_string.return_value = b"4.2.1"
    lib.projectm_get_vcs_version_string.return_value = b"abc123"

    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()

    with patch("cleave.projectm._get_lib", return_value=lib):
        info = pm.version_info()

    lib.projectm_get_version_components.assert_called_once()
    assert info["version"] == "4.2.1"
    assert info["vcs"] == "abc123"
    assert lib.projectm_free_string.call_count == 2


def test_enqueue_preset_failure_exhausted_flag() -> None:
    pm = ProjectM.__new__(ProjectM)
    pm._failure_queue = __import__("collections").deque()
    pm._enqueue_preset_failure("a.milk", "failed", exhausted=True)
    failures = pm.drain_preset_failures()
    assert failures[0].exhausted is True
