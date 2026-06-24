"""Tests for cleave.projectm_playlist ctypes bindings."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cleave.projectm import ProjectM
from cleave.projectm_playlist import (
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
        "projectm_playlist_set_preset_load_event_callback",
    ):
        setattr(lib, name, MagicMock())
    lib.projectm_playlist_create.return_value = MagicMock()
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


def test_connect_installs_instant_load_callback() -> None:
    lib = _mock_lib()
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    pm.load_preset = MagicMock()

    with patch("cleave.projectm_playlist._get_lib", return_value=lib):
        playlist = ProjectMPlaylist.create()
        playlist.connect(pm)

    lib.projectm_playlist_set_preset_load_event_callback.assert_called()
    install_call = lib.projectm_playlist_set_preset_load_event_callback.call_args
    callback = install_call.args[1]
    assert callback is not None
    assert callback(0, b"/tmp/a.milk", True, None) is True
    pm.load_preset.assert_called_once_with("/tmp/a.milk", smooth=False)


def test_instant_load_callback_ignores_hard_cut_flag() -> None:
    lib = _mock_lib()
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    pm.load_preset = MagicMock()

    with patch("cleave.projectm_playlist._get_lib", return_value=lib):
        playlist = ProjectMPlaylist.create()
        playlist.connect(pm)

    callback = lib.projectm_playlist_set_preset_load_event_callback.call_args.args[1]
    callback(1, b"/tmp/b.milk", False, None)
    pm.load_preset.assert_called_once_with("/tmp/b.milk", smooth=False)


def test_destroy_clears_preset_load_callback() -> None:
    lib = _mock_lib()
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    with patch("cleave.projectm_playlist._get_lib", return_value=lib):
        playlist = ProjectMPlaylist.create()
        playlist.connect(pm)
        playlist.destroy()

    clear_call = lib.projectm_playlist_set_preset_load_event_callback.call_args_list[-1]
    assert not clear_call.args[1]
