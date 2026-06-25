"""ctypes wrapper for libprojectM playlist library."""

from __future__ import annotations

import ctypes
import os
import subprocess
from collections.abc import Callable
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
PresetSwitchedEvent = CFUNCTYPE(None, c_bool, c_uint32, c_void_p)


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

    if hasattr(lib, "projectm_playlist_set_preset_switched_event_callback"):
        lib.projectm_playlist_set_preset_switched_event_callback.argtypes = [
            c_void_p,
            c_void_p,
            c_void_p,
        ]
        lib.projectm_playlist_set_preset_switched_event_callback.restype = None

    if hasattr(lib, "projectm_playlist_size"):
        lib.projectm_playlist_size.argtypes = [c_void_p]
        lib.projectm_playlist_size.restype = c_uint32

    if hasattr(lib, "projectm_playlist_get_position"):
        lib.projectm_playlist_get_position.argtypes = [c_void_p]
        lib.projectm_playlist_get_position.restype = c_uint32

    if hasattr(lib, "projectm_playlist_set_position"):
        lib.projectm_playlist_set_position.argtypes = [
            c_void_p,
            c_uint32,
            c_bool,
        ]
        lib.projectm_playlist_set_position.restype = c_uint32

    if hasattr(lib, "projectm_playlist_item"):
        lib.projectm_playlist_item.argtypes = [c_void_p, c_uint32]
        # Return the heap pointer; c_char_p would copy and break free_string().
        lib.projectm_playlist_item.restype = c_void_p

    if hasattr(lib, "projectm_playlist_free_string"):
        lib.projectm_playlist_free_string.argtypes = [c_void_p]
        lib.projectm_playlist_free_string.restype = None


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
        self._preset_switched_callback: PresetSwitchedEvent | None = None
        self._on_preset_loaded: Callable[[Path], None] | None = None

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

    def connect(
        self,
        pm: ProjectM | None,
        *,
        on_preset_loaded: Callable[[Path], None] | None = None,
    ) -> None:
        self._clear_callbacks()
        if on_preset_loaded is not None:
            self._on_preset_loaded = on_preset_loaded
        pm_handle = pm.handle if pm is not None else c_void_p()
        _get_lib().projectm_playlist_connect(self._handle, pm_handle)
        self._pm = pm
        if pm is not None:
            self._install_callbacks()

    def _clear_callbacks(self) -> None:
        lib = _get_lib()
        if self._handle:
            if hasattr(lib, "projectm_playlist_set_preset_load_event_callback"):
                lib.projectm_playlist_set_preset_load_event_callback(
                    self._handle, c_void_p(), c_void_p()
                )
            if hasattr(lib, "projectm_playlist_set_preset_switched_event_callback"):
                lib.projectm_playlist_set_preset_switched_event_callback(
                    self._handle, c_void_p(), c_void_p()
                )
        self._preset_load_callback = None
        self._preset_switched_callback = None

    def _notify_preset_loaded(self, path: Path) -> None:
        if self._on_preset_loaded is not None:
            self._on_preset_loaded(path)

    def _install_callbacks(self) -> None:
        lib = _get_lib()
        pm = self._pm
        if pm is None:
            return

        if hasattr(lib, "projectm_playlist_set_preset_load_event_callback"):
            def _on_preset_load(
                _index: int, filename: bytes, hard_cut: bool, _user_data: c_void_p
            ) -> bool:
                if filename:
                    decoded = filename.decode("utf-8")
                    pm.load_preset(decoded, smooth=not hard_cut)
                    self._notify_preset_loaded(Path(decoded))
                return True

            self._preset_load_callback = PresetLoadEvent(_on_preset_load)
            lib.projectm_playlist_set_preset_load_event_callback(
                self._handle, self._preset_load_callback, c_void_p()
            )

        if hasattr(lib, "projectm_playlist_set_preset_switched_event_callback"):
            playlist = self

            def _on_preset_switched(
                _is_hard_cut: bool, index: int, _user_data: c_void_p
            ) -> None:
                item = playlist.item(index)
                if item is not None:
                    playlist._notify_preset_loaded(item)

            self._preset_switched_callback = PresetSwitchedEvent(_on_preset_switched)
            lib.projectm_playlist_set_preset_switched_event_callback(
                self._handle, self._preset_switched_callback, c_void_p()
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

    def size(self) -> int:
        lib = _get_lib()
        if not hasattr(lib, "projectm_playlist_size"):
            return 0
        return int(lib.projectm_playlist_size(self._handle))

    def get_position(self) -> int:
        lib = _get_lib()
        if not hasattr(lib, "projectm_playlist_get_position"):
            return 0
        return int(lib.projectm_playlist_get_position(self._handle))

    def set_position(self, index: int, *, hard_cut: bool = True) -> int:
        lib = _get_lib()
        if not hasattr(lib, "projectm_playlist_set_position"):
            return 0
        return int(
            lib.projectm_playlist_set_position(
                self._handle, c_uint32(index), c_bool(hard_cut)
            )
        )

    def item(self, index: int) -> Path | None:
        lib = _get_lib()
        if not hasattr(lib, "projectm_playlist_item"):
            return None
        raw_ptr = lib.projectm_playlist_item(self._handle, c_uint32(index))
        if not raw_ptr:
            return None
        try:
            return Path(ctypes.string_at(raw_ptr).decode("utf-8"))
        finally:
            if hasattr(lib, "projectm_playlist_free_string"):
                lib.projectm_playlist_free_string(raw_ptr)

    def destroy(self) -> None:
        if self._handle:
            self._clear_callbacks()
            _get_lib().projectm_playlist_connect(self._handle, c_void_p())
            _get_lib().projectm_playlist_destroy(self._handle)
            self._handle = c_void_p()
            self._pm = None
            self._on_preset_loaded = None

    def __enter__(self) -> ProjectMPlaylist:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.destroy()
