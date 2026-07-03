"""Tests for cleave.projectm_playlist ctypes bindings."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cleave.projectm import ProjectM
from cleave.projectm_playlist import (
    DEFAULT_RETRY_COUNT,
    ProjectMPlaylist,
    ProjectMPlaylistLibraryError,
    _bind_functions,
)


def _mock_lib() -> MagicMock:
    lib = MagicMock()
    for name in (
        "projectm_playlist_create",
        "projectm_playlist_destroy",
        "projectm_playlist_connect",
        "projectm_playlist_add_path",
        "projectm_playlist_set_shuffle",
        "projectm_playlist_set_preset_switched_event_callback",
        "projectm_playlist_set_preset_switch_failed_event_callback",
        "projectm_playlist_play_next",
        "projectm_playlist_get_retry_count",
        "projectm_playlist_set_retry_count",
        "projectm_playlist_size",
        "projectm_playlist_get_position",
        "projectm_playlist_set_position",
        "projectm_playlist_item",
        "projectm_playlist_free_string",
    ):
        setattr(lib, name, MagicMock())
    lib.projectm_playlist_create.return_value = MagicMock()
    lib.projectm_playlist_play_next.return_value = 2
    lib.projectm_playlist_get_retry_count.return_value = DEFAULT_RETRY_COUNT
    return lib


def test_bind_functions_requires_symbols() -> None:
    lib = MagicMock(spec=[])
    with pytest.raises(ProjectMPlaylistLibraryError, match="missing symbols"):
        _bind_functions(lib, "/tmp/lib.so")


def test_create_connect_add_path_set_shuffle_destroy() -> None:
    lib = _mock_lib()
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()

    with patch("cleave.projectm_playlist._get_lib", return_value=lib):
        playlist = ProjectMPlaylist.create()
        playlist.connect(pm)
        playlist.add_path("/tmp/presets", recurse=False, allow_duplicates=False)
        playlist.set_shuffle(False)
        playlist.destroy()

    lib.projectm_playlist_create.assert_called_once()
    connect_calls = lib.projectm_playlist_connect.call_args_list
    assert any(call.args[1] == pm.handle for call in connect_calls)
    lib.projectm_playlist_add_path.assert_called_once()
    lib.projectm_playlist_set_shuffle.assert_called_once()
    lib.projectm_playlist_destroy.assert_called_once()


def test_destroy_disconnects_before_free() -> None:
    lib = _mock_lib()
    with patch("cleave.projectm_playlist._get_lib", return_value=lib):
        playlist = ProjectMPlaylist.create()
        playlist.destroy()

    lib.projectm_playlist_connect.assert_called()
    lib.projectm_playlist_destroy.assert_called_once()


def test_connect_does_not_install_preset_load_callback() -> None:
    lib = _mock_lib()
    lib.projectm_playlist_set_preset_load_event_callback = MagicMock()
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    pm._enqueue_preset_failure = MagicMock()

    with patch("cleave.projectm_playlist._get_lib", return_value=lib):
        playlist = ProjectMPlaylist.create()
        playlist.connect(pm, on_preset_loaded=lambda _path: None)

    lib.projectm_playlist_set_preset_load_event_callback.assert_not_called()
    lib.projectm_playlist_set_preset_switched_event_callback.assert_called()
    lib.projectm_playlist_set_preset_switch_failed_event_callback.assert_called()
    lib.projectm_playlist_set_retry_count.assert_called_once()
    retry_args = lib.projectm_playlist_set_retry_count.call_args.args
    assert retry_args[0] == playlist.handle
    assert retry_args[1].value == DEFAULT_RETRY_COUNT


def test_preset_switched_callback_notifies_on_preset_loaded() -> None:
    lib = _mock_lib()
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    pm._enqueue_preset_failure = MagicMock()
    loaded_paths: list[str] = []

    with patch("cleave.projectm_playlist._get_lib", return_value=lib):
        playlist = ProjectMPlaylist.create()
        playlist.connect(
            pm, on_preset_loaded=lambda path: loaded_paths.append(str(path))
        )
        with patch.object(playlist, "item", return_value=Path("/tmp/c.milk")):
            switched = (
                lib.projectm_playlist_set_preset_switched_event_callback.call_args.args[
                    1
                ]
            )
            switched(True, 2, None)

    assert loaded_paths == ["/tmp/c.milk"]


def test_switch_failed_callback_enqueues_exhausted_failure() -> None:
    lib = _mock_lib()
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    pm._enqueue_preset_failure = MagicMock()

    with patch("cleave.projectm_playlist._get_lib", return_value=lib):
        playlist = ProjectMPlaylist.create()
        playlist.connect(pm)
        failed = (
            lib.projectm_playlist_set_preset_switch_failed_event_callback.call_args.args[
                1
            ]
        )
        failed(b"/tmp/bad.milk", b"too many retries", None)

    pm._enqueue_preset_failure.assert_called_once_with(
        "/tmp/bad.milk",
        "too many retries",
        exhausted=True,
    )


def test_play_next_and_retry_count() -> None:
    lib = _mock_lib()
    with patch("cleave.projectm_playlist._get_lib", return_value=lib):
        playlist = ProjectMPlaylist.create()
        assert playlist.play_next(hard_cut=True) == 2
        lib.projectm_playlist_play_next.assert_called_once()
        playlist.set_retry_count(250)
        lib.projectm_playlist_set_retry_count.assert_called()
        lib.projectm_playlist_get_retry_count.return_value = 250
        assert playlist.get_retry_count() == 250


def test_destroy_clears_callbacks() -> None:
    lib = _mock_lib()
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    pm._enqueue_preset_failure = MagicMock()
    with patch("cleave.projectm_playlist._get_lib", return_value=lib):
        playlist = ProjectMPlaylist.create()
        playlist.connect(pm)
        playlist.destroy()

    clear_switched = (
        lib.projectm_playlist_set_preset_switched_event_callback.call_args_list[-1]
    )
    assert not clear_switched.args[1]
    clear_failed = (
        lib.projectm_playlist_set_preset_switch_failed_event_callback.call_args_list[-1]
    )
    assert not clear_failed.args[1]


def test_item_roundtrip_with_real_library(tmp_path: Path) -> None:
    preset = tmp_path / "sample.milk"
    preset.write_text("[preset00]\n", encoding="utf-8")

    try:
        playlist = ProjectMPlaylist.create()
    except ProjectMPlaylistLibraryError:
        pytest.skip("libprojectM playlist library unavailable")

    try:
        playlist.add_path(tmp_path, recurse=False, allow_duplicates=False)
        assert playlist.size() == 1
        assert playlist.item(0) == preset
        assert playlist.item(0) == preset
    finally:
        playlist.destroy()
