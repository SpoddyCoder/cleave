"""ctypes wrapper for libprojectM playlist library."""

from __future__ import annotations

import ctypes
import os
import subprocess
from collections.abc import Callable
from ctypes import CFUNCTYPE, POINTER, c_bool, c_char_p, c_int, c_uint32, c_void_p
from pathlib import Path

from cleave.projectm import ProjectM

_lib: ctypes.CDLL | None = None

DEFAULT_RETRY_COUNT = 500

# projectm_playlist_sort_predicate / projectm_playlist_sort_order (playlist_types.h)
SORT_PREDICATE_FULL_PATH = 0
SORT_PREDICATE_FILENAME_ONLY = 1
SORT_ORDER_ASCENDING = 0
SORT_ORDER_DESCENDING = 1


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

PresetSwitchedEvent = CFUNCTYPE(None, c_bool, c_uint32, c_void_p)
PresetSwitchFailedEvent = CFUNCTYPE(None, c_char_p, c_char_p, c_void_p)


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

    if hasattr(lib, "projectm_playlist_set_preset_switched_event_callback"):
        lib.projectm_playlist_set_preset_switched_event_callback.argtypes = [
            c_void_p,
            c_void_p,
            c_void_p,
        ]
        lib.projectm_playlist_set_preset_switched_event_callback.restype = None

    if hasattr(lib, "projectm_playlist_set_preset_switch_failed_event_callback"):
        lib.projectm_playlist_set_preset_switch_failed_event_callback.argtypes = [
            c_void_p,
            c_void_p,
            c_void_p,
        ]
        lib.projectm_playlist_set_preset_switch_failed_event_callback.restype = None

    if hasattr(lib, "projectm_playlist_play_next"):
        lib.projectm_playlist_play_next.argtypes = [c_void_p, c_bool]
        lib.projectm_playlist_play_next.restype = c_uint32

    if hasattr(lib, "projectm_playlist_get_retry_count"):
        lib.projectm_playlist_get_retry_count.argtypes = [c_void_p]
        lib.projectm_playlist_get_retry_count.restype = c_uint32

    if hasattr(lib, "projectm_playlist_set_retry_count"):
        lib.projectm_playlist_set_retry_count.argtypes = [c_void_p, c_uint32]
        lib.projectm_playlist_set_retry_count.restype = None

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

    if hasattr(lib, "projectm_playlist_add_preset"):
        lib.projectm_playlist_add_preset.argtypes = [
            c_void_p,
            c_char_p,
            c_bool,
        ]
        lib.projectm_playlist_add_preset.restype = c_bool

    if hasattr(lib, "projectm_playlist_add_presets"):
        lib.projectm_playlist_add_presets.argtypes = [
            c_void_p,
            POINTER(c_char_p),
            c_uint32,
            c_bool,
        ]
        lib.projectm_playlist_add_presets.restype = c_uint32

    if hasattr(lib, "projectm_playlist_sort"):
        lib.projectm_playlist_sort.argtypes = [
            c_void_p,
            c_uint32,
            c_uint32,
            c_int,
            c_int,
        ]
        lib.projectm_playlist_sort.restype = None


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
        self._preset_switched_callback: PresetSwitchedEvent | None = None
        self._switch_failed_callback: PresetSwitchFailedEvent | None = None
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
            self.set_retry_count(DEFAULT_RETRY_COUNT)
            self._install_callbacks()

    def _clear_callbacks(self) -> None:
        lib = _get_lib()
        if self._handle:
            if hasattr(lib, "projectm_playlist_set_preset_switched_event_callback"):
                lib.projectm_playlist_set_preset_switched_event_callback(
                    self._handle, c_void_p(), c_void_p()
                )
            if hasattr(
                lib, "projectm_playlist_set_preset_switch_failed_event_callback"
            ):
                lib.projectm_playlist_set_preset_switch_failed_event_callback(
                    self._handle, c_void_p(), c_void_p()
                )
        self._preset_switched_callback = None
        self._switch_failed_callback = None

    def _notify_preset_loaded(self, path: Path) -> None:
        if self._on_preset_loaded is not None:
            self._on_preset_loaded(path)

    def _install_callbacks(self) -> None:
        lib = _get_lib()
        pm = self._pm
        if pm is None:
            return

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

        if hasattr(lib, "projectm_playlist_set_preset_switch_failed_event_callback"):
            def _on_switch_failed(
                filename: bytes, message: bytes, _user_data: c_void_p
            ) -> None:
                pm._enqueue_preset_failure(
                    filename.decode("utf-8") if filename else "",
                    message.decode("utf-8") if message else "",
                    exhausted=True,
                )

            self._switch_failed_callback = PresetSwitchFailedEvent(_on_switch_failed)
            lib.projectm_playlist_set_preset_switch_failed_event_callback(
                self._handle, self._switch_failed_callback, c_void_p()
            )

    def play_next(self, *, hard_cut: bool = False) -> int:
        lib = _get_lib()
        if not hasattr(lib, "projectm_playlist_play_next"):
            return 0
        return int(
            lib.projectm_playlist_play_next(self._handle, c_bool(hard_cut))
        )

    def get_retry_count(self) -> int:
        lib = _get_lib()
        if not hasattr(lib, "projectm_playlist_get_retry_count"):
            return DEFAULT_RETRY_COUNT
        return int(lib.projectm_playlist_get_retry_count(self._handle))

    def set_retry_count(self, count: int) -> None:
        lib = _get_lib()
        if not hasattr(lib, "projectm_playlist_set_retry_count"):
            return
        lib.projectm_playlist_set_retry_count(
            self._handle, c_uint32(count)
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

    def add_presets(
        self,
        paths: list[Path | str],
        *,
        allow_duplicates: bool = False,
    ) -> int:
        lib = _get_lib()
        if not paths:
            return 0
        if hasattr(lib, "projectm_playlist_add_presets"):
            encoded = [os.fspath(path).encode("utf-8") for path in paths]
            array = (c_char_p * len(encoded))(*encoded)
            return int(
                lib.projectm_playlist_add_presets(
                    self._handle,
                    array,
                    c_uint32(len(encoded)),
                    c_bool(allow_duplicates),
                )
            )
        if not hasattr(lib, "projectm_playlist_add_preset"):
            return 0
        added = 0
        for path in paths:
            encoded = os.fspath(path).encode("utf-8")
            if lib.projectm_playlist_add_preset(
                self._handle, encoded, c_bool(allow_duplicates)
            ):
                added += 1
        return added

    def set_shuffle(self, enabled: bool) -> None:
        _get_lib().projectm_playlist_set_shuffle(self._handle, c_bool(enabled))

    def sort(
        self,
        *,
        start_index: int = 0,
        count: int | None = None,
        predicate: int = SORT_PREDICATE_FILENAME_ONLY,
        order: int = SORT_ORDER_ASCENDING,
    ) -> None:
        """Sort playlist items to match Cleave browse order (alphabetical filename)."""
        lib = _get_lib()
        if not hasattr(lib, "projectm_playlist_sort"):
            return
        if count is None:
            count = self.size()
        lib.projectm_playlist_sort(
            self._handle,
            c_uint32(start_index),
            c_uint32(count),
            c_int(predicate),
            c_int(order),
        )

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
