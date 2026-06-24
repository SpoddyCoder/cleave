"""ctypes wrapper for libprojectM playlist library."""

from __future__ import annotations

import ctypes
import os
import subprocess
from ctypes import CFUNCTYPE, c_bool, c_char_p, c_uint32, c_void_p
from pathlib import Path

from cleave.projectm import ProjectM

_lib: ctypes.CDLL | None = None


class ProjectMPlaylistLibraryError(OSError):
    """libprojectM playlist shared library not found or failed to load."""


_PKG_CONFIG_NAMES = ("projectM-4-playlist", "libprojectM-playlist")


def _pkg_config_candidates() -> list[str]:
    for pkg_name in _PKG_CONFIG_NAMES:
        try:
            libdirs = subprocess.run(
                ["pkg-config", "--libs-only-L", pkg_name],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.split()
            libnames = subprocess.run(
                ["pkg-config", "--libs-only-l", pkg_name],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.split()
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue

        candidates: list[str] = []
        for entry in libdirs:
            if not entry.startswith("-L"):
                continue
            base = Path(entry[2:])
            for lib in libnames:
                if lib.startswith("-l") and "playlist" in lib:
                    candidates.append(str(base / f"lib{lib[2:]}.so"))
        if candidates:
            return candidates
    return []


def _library_candidates() -> list[str]:
    candidates: list[str] = []
    env_path = os.environ.get("PROJECTM_PLAYLIST_LIB")
    if env_path:
        candidates.append(env_path)
    candidates.extend(_pkg_config_candidates())
    local_lib = Path.home() / ".local/lib"
    candidates.extend(
        [
            str(local_lib / "libprojectM-4-playlist.so"),
            "/usr/local/lib/libprojectM-4-playlist.so",
            "/usr/lib/x86_64-linux-gnu/libprojectM-4-playlist.so",
            "libprojectM-4-playlist.so",
            str(local_lib / "libprojectM-4-playlist-4.so"),
            "/usr/local/lib/libprojectM-4-playlist-4.so",
            "/usr/lib/x86_64-linux-gnu/libprojectM-4-playlist-4.so",
            "libprojectM-4-playlist-4.so",
        ]
    )

    seen: set[str] = set()
    ordered: list[str] = []
    for path in candidates:
        if path not in seen:
            seen.add(path)
            ordered.append(path)
    return ordered


_REQUIRED_SYMBOLS = (
    "projectm_playlist_create",
    "projectm_playlist_destroy",
    "projectm_playlist_connect",
    "projectm_playlist_add_path",
    "projectm_playlist_set_shuffle",
)

PresetLoadEvent = CFUNCTYPE(c_bool, c_uint32, c_char_p, c_bool, c_void_p)


def _bind_functions(lib: ctypes.CDLL, path: str) -> None:
    missing = [name for name in _REQUIRED_SYMBOLS if not hasattr(lib, name)]
    if missing:
        raise ProjectMPlaylistLibraryError(
            "libprojectM playlist at "
            f"{path} is missing symbols: {', '.join(missing)}"
        )

    lib.projectm_playlist_create.argtypes = [c_void_p]
    lib.projectm_playlist_create.restype = c_void_p

    lib.projectm_playlist_destroy.argtypes = [c_void_p]
    lib.projectm_playlist_destroy.restype = None

    lib.projectm_playlist_connect.argtypes = [c_void_p, c_void_p]
    lib.projectm_playlist_connect.restype = None

    lib.projectm_playlist_add_path.argtypes = [
        c_void_p,
        c_char_p,
        c_bool,
        c_bool,
    ]
    lib.projectm_playlist_add_path.restype = None

    lib.projectm_playlist_set_shuffle.argtypes = [c_void_p, c_bool]
    lib.projectm_playlist_set_shuffle.restype = None

    if hasattr(lib, "projectm_playlist_set_preset_load_event_callback"):
        lib.projectm_playlist_set_preset_load_event_callback.argtypes = [
            c_void_p,
            c_void_p,
            c_void_p,
        ]
        lib.projectm_playlist_set_preset_load_event_callback.restype = None


def _get_lib() -> ctypes.CDLL:
    global _lib
    if _lib is not None:
        return _lib

    errors: list[str] = []
    for path in _library_candidates():
        try:
            loaded = ctypes.CDLL(path)
            _bind_functions(loaded, path)
        except (OSError, ProjectMPlaylistLibraryError) as exc:
            errors.append(f"{path}: {exc}")
            continue
        _lib = loaded
        return loaded

    tried = "\n  ".join(errors) if errors else "(no paths tried)"
    raise ProjectMPlaylistLibraryError(
        "libprojectM playlist shared library not found. "
        "Set PROJECTM_PLAYLIST_LIB or install libprojectM playlist.\n"
        f"Tried:\n  {tried}"
    )


class ProjectMPlaylist:
    """Context-manager-friendly wrapper around a libprojectM playlist instance."""

    def __init__(self, handle: c_void_p, *, pm: ProjectM | None = None) -> None:
        self._handle = handle
        self._pm = pm
        self._preset_load_callback: PresetLoadEvent | None = None

    @classmethod
    def create(cls, pm: ProjectM | None = None) -> ProjectMPlaylist:
        lib = _get_lib()
        pm_handle = pm.handle if pm is not None else c_void_p()
        handle = lib.projectm_playlist_create(pm_handle)
        if not handle:
            raise RuntimeError("projectm_playlist_create returned NULL")
        return cls(handle, pm=pm)

    @property
    def handle(self) -> c_void_p:
        return self._handle

    def connect(self, pm: ProjectM | None) -> None:
        self._clear_instant_load_callback()
        pm_handle = pm.handle if pm is not None else c_void_p()
        _get_lib().projectm_playlist_connect(self._handle, pm_handle)
        self._pm = pm
        if pm is not None:
            self._install_instant_load_callback()

    def _clear_instant_load_callback(self) -> None:
        lib = _get_lib()
        if not hasattr(lib, "projectm_playlist_set_preset_load_event_callback"):
            return
        if self._handle:
            lib.projectm_playlist_set_preset_load_event_callback(
                self._handle, c_void_p(), c_void_p()
            )
        self._preset_load_callback = None

    def _install_instant_load_callback(self) -> None:
        lib = _get_lib()
        if not hasattr(lib, "projectm_playlist_set_preset_load_event_callback"):
            return
        pm = self._pm
        if pm is None:
            return

        def _on_preset_load(
            _index: int, filename: bytes, _hard_cut: bool, _user_data: c_void_p
        ) -> bool:
            if filename:
                pm.load_preset(filename.decode("utf-8"), smooth=False)
            return True

        self._preset_load_callback = PresetLoadEvent(_on_preset_load)
        lib.projectm_playlist_set_preset_load_event_callback(
            self._handle, self._preset_load_callback, c_void_p()
        )

    def add_path(
        self,
        path: Path | str,
        *,
        recurse: bool = False,
        allow_duplicates: bool = False,
    ) -> None:
        encoded = os.fspath(path).encode("utf-8")
        _get_lib().projectm_playlist_add_path(
            self._handle,
            encoded,
            c_bool(recurse),
            c_bool(allow_duplicates),
        )

    def set_shuffle(self, enabled: bool) -> None:
        _get_lib().projectm_playlist_set_shuffle(self._handle, c_bool(enabled))

    def destroy(self) -> None:
        if self._handle:
            self._clear_instant_load_callback()
            _get_lib().projectm_playlist_connect(self._handle, c_void_p())
            _get_lib().projectm_playlist_destroy(self._handle)
            self._handle = c_void_p()
            self._pm = None

    def __enter__(self) -> ProjectMPlaylist:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.destroy()
