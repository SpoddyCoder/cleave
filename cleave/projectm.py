"""ctypes wrapper for libprojectM."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from collections import deque
from collections.abc import Callable
from ctypes import (
    CFUNCTYPE,
    POINTER,
    byref,
    c_bool,
    c_char_p,
    c_double,
    c_float,
    c_int32,
    c_size_t,
    c_uint,
    c_uint8,
    c_uint32,
    c_void_p,
)
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cleave.config import DEFAULT_BEAT_SENSITIVITY, clamp_beat_sensitivity

PROJECTM_MONO = 1
PROJECTM_STEREO = 2

_lib: ctypes.CDLL | None = None
_log_callback: CFUNCTYPE | None = None
_log_message_queue: deque[str] = deque()

PROJECTM_LOG_LEVEL_DEBUG = 2
PROJECTM_LOG_LEVEL_WARN = 4
PROJECTM_LOG_LEVEL_ERROR = 5
PROJECTM_LOG_LEVEL_FATAL = 6

PresetSwitchFailedEvent = CFUNCTYPE(None, c_char_p, c_char_p, c_void_p)
LogCallback = CFUNCTYPE(None, c_char_p, c_int32, c_void_p)


class ProjectmTextureLoadData(ctypes.Structure):
    _fields_ = [
        ("data", POINTER(c_uint8)),
        ("width", c_uint32),
        ("height", c_uint32),
        ("channels", c_uint32),
        ("texture_id", c_uint32),
    ]


TextureLoadEvent = CFUNCTYPE(None, c_char_p, POINTER(ProjectmTextureLoadData), c_void_p)


@dataclass(frozen=True)
class PresetLoadFailure:
    filename: str
    message: str
    exhausted: bool = False


class ProjectMLibraryError(OSError):
    """libprojectM shared library not found or failed to load."""


_PKG_CONFIG_NAMES = ("projectM-4", "libprojectM")


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
                if (
                    lib.startswith("-l")
                    and "projectM" in lib
                    and "playlist" not in lib
                ):
                    candidates.append(str(base / f"lib{lib[2:]}.so"))
        if candidates:
            return candidates
    return []


def _library_candidates() -> list[str]:
    candidates: list[str] = []
    env_path = os.environ.get("PROJECTM_LIB")
    if env_path:
        candidates.append(env_path)
    candidates.extend(_pkg_config_candidates())
    local_lib = Path.home() / ".local/lib"
    candidates.extend(
        [
            str(local_lib / "libprojectM-4.so"),
            "/usr/local/lib/libprojectM-4.so",
            "/usr/lib/x86_64-linux-gnu/libprojectM-4.so",
            "libprojectM-4.so",
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
    "projectm_create",
    "projectm_destroy",
    "projectm_set_window_size",
    "projectm_load_preset_file",
    "projectm_set_preset_locked",
    "projectm_get_preset_locked",
    "projectm_set_texture_search_paths",
    "projectm_pcm_add_float",
    "projectm_pcm_get_max_samples",
    "projectm_opengl_render_frame_fbo",
    "projectm_set_beat_sensitivity",
    "projectm_get_beat_sensitivity",
    "projectm_set_fps",
    "projectm_set_frame_time",
    "projectm_set_hard_cut_enabled",
    "projectm_set_soft_cut_duration",
    "projectm_set_preset_duration",
    "projectm_set_hard_cut_duration",
    "projectm_set_hard_cut_sensitivity",
    "projectm_set_easter_egg",
    "projectm_set_preset_start_clean",
)


def _bind_functions(lib: ctypes.CDLL, path: str) -> None:
    missing = [name for name in _REQUIRED_SYMBOLS if not hasattr(lib, name)]
    if missing:
        raise ProjectMLibraryError(
            f"libprojectM at {path} is missing symbols (need 4.2+): {', '.join(missing)}"
        )

    lib.projectm_create.argtypes = []
    lib.projectm_create.restype = c_void_p

    lib.projectm_destroy.argtypes = [c_void_p]
    lib.projectm_destroy.restype = None

    lib.projectm_set_window_size.argtypes = [c_void_p, c_size_t, c_size_t]
    lib.projectm_set_window_size.restype = None

    lib.projectm_load_preset_file.argtypes = [c_void_p, c_char_p, c_bool]
    lib.projectm_load_preset_file.restype = None

    lib.projectm_set_preset_locked.argtypes = [c_void_p, c_bool]
    lib.projectm_set_preset_locked.restype = None

    lib.projectm_get_preset_locked.argtypes = [c_void_p]
    lib.projectm_get_preset_locked.restype = c_bool

    lib.projectm_set_texture_search_paths.argtypes = [
        c_void_p,
        POINTER(c_char_p),
        c_size_t,
    ]
    lib.projectm_set_texture_search_paths.restype = None

    lib.projectm_pcm_add_float.argtypes = [
        c_void_p,
        POINTER(c_float),
        c_uint,
        c_int32,
    ]
    lib.projectm_pcm_add_float.restype = None

    lib.projectm_pcm_get_max_samples.argtypes = []
    lib.projectm_pcm_get_max_samples.restype = c_uint

    lib.projectm_opengl_render_frame_fbo.argtypes = [c_void_p, c_uint32]
    lib.projectm_opengl_render_frame_fbo.restype = None

    lib.projectm_set_beat_sensitivity.argtypes = [c_void_p, c_float]
    lib.projectm_set_beat_sensitivity.restype = None

    lib.projectm_get_beat_sensitivity.argtypes = [c_void_p]
    lib.projectm_get_beat_sensitivity.restype = c_float

    lib.projectm_set_fps.argtypes = [c_void_p, c_int32]
    lib.projectm_set_fps.restype = None

    lib.projectm_set_frame_time.argtypes = [c_void_p, c_double]
    lib.projectm_set_frame_time.restype = None

    lib.projectm_set_hard_cut_enabled.argtypes = [c_void_p, c_bool]
    lib.projectm_set_hard_cut_enabled.restype = None

    lib.projectm_set_soft_cut_duration.argtypes = [c_void_p, c_double]
    lib.projectm_set_soft_cut_duration.restype = None

    lib.projectm_set_preset_duration.argtypes = [c_void_p, c_double]
    lib.projectm_set_preset_duration.restype = None

    lib.projectm_set_hard_cut_duration.argtypes = [c_void_p, c_double]
    lib.projectm_set_hard_cut_duration.restype = None

    lib.projectm_set_hard_cut_sensitivity.argtypes = [c_void_p, c_float]
    lib.projectm_set_hard_cut_sensitivity.restype = None

    lib.projectm_set_easter_egg.argtypes = [c_void_p, c_float]
    lib.projectm_set_easter_egg.restype = None

    lib.projectm_set_preset_start_clean.argtypes = [c_void_p, c_bool]
    lib.projectm_set_preset_start_clean.restype = None

    _bind_optional_functions(lib)


def _bind_optional_functions(lib: ctypes.CDLL) -> None:
    if hasattr(lib, "projectm_set_preset_switch_failed_event_callback"):
        lib.projectm_set_preset_switch_failed_event_callback.argtypes = [
            c_void_p,
            PresetSwitchFailedEvent,
            c_void_p,
        ]
        lib.projectm_set_preset_switch_failed_event_callback.restype = None

    if hasattr(lib, "projectm_set_texture_load_event_callback"):
        lib.projectm_set_texture_load_event_callback.argtypes = [
            c_void_p,
            TextureLoadEvent,
            c_void_p,
        ]
        lib.projectm_set_texture_load_event_callback.restype = None

    if hasattr(lib, "projectm_set_log_callback"):
        lib.projectm_set_log_callback.argtypes = [
            LogCallback,
            c_bool,
            c_void_p,
        ]
        lib.projectm_set_log_callback.restype = None

    if hasattr(lib, "projectm_set_log_level"):
        lib.projectm_set_log_level.argtypes = [c_int32, c_bool]
        lib.projectm_set_log_level.restype = None

    if hasattr(lib, "projectm_get_version_components"):
        lib.projectm_get_version_components.argtypes = [
            POINTER(c_int32),
            POINTER(c_int32),
            POINTER(c_int32),
        ]
        lib.projectm_get_version_components.restype = None

    if hasattr(lib, "projectm_get_version_string"):
        lib.projectm_get_version_string.argtypes = []
        lib.projectm_get_version_string.restype = c_char_p

    if hasattr(lib, "projectm_get_vcs_version_string"):
        lib.projectm_get_vcs_version_string.argtypes = []
        lib.projectm_get_vcs_version_string.restype = c_char_p

    if hasattr(lib, "projectm_free_string"):
        lib.projectm_free_string.argtypes = [c_void_p]
        lib.projectm_free_string.restype = None


def _decode_lib_string(ptr: c_char_p) -> str | None:
    if not ptr:
        return None
    return ctypes.string_at(ptr).decode("utf-8")


def _free_lib_string(lib: ctypes.CDLL, ptr: c_char_p) -> None:
    if ptr and hasattr(lib, "projectm_free_string"):
        lib.projectm_free_string(ptr)


def _handle_log_message(message: str, level: int) -> None:
    stripped = message.strip()
    if not stripped:
        return
    if level >= PROJECTM_LOG_LEVEL_WARN:
        _log_message_queue.append(stripped)
    if os.environ.get("CLEAVE_PROJECTM_LOG") == "1":
        print(stripped, file=sys.stderr)


def drain_log_messages() -> list[str]:
    """Pop queued Warning+ libprojectM log lines (FIFO)."""
    messages = list(_log_message_queue)
    _log_message_queue.clear()
    return messages


def _setup_logging(lib: ctypes.CDLL) -> None:
    global _log_callback
    if not hasattr(lib, "projectm_set_log_callback"):
        return

    def _on_log(message: bytes, level: int, _user_data: c_void_p) -> None:
        if not message:
            return
        _handle_log_message(message.decode("utf-8", errors="replace"), level)

    _log_callback = LogCallback(_on_log)
    lib.projectm_set_log_callback(_log_callback, c_bool(False), c_void_p())
    if hasattr(lib, "projectm_set_log_level"):
        log_level = (
            PROJECTM_LOG_LEVEL_DEBUG
            if os.environ.get("CLEAVE_PROJECTM_LOG") == "1"
            else PROJECTM_LOG_LEVEL_WARN
        )
        lib.projectm_set_log_level(c_int32(log_level), c_bool(False))


def _get_lib() -> ctypes.CDLL:
    global _lib
    if _lib is not None:
        return _lib

    errors: list[str] = []
    for path in _library_candidates():
        try:
            loaded = ctypes.CDLL(path)
            _bind_functions(loaded, path)
        except (OSError, ProjectMLibraryError) as exc:
            errors.append(f"{path}: {exc}")
            continue
        _setup_logging(loaded)
        _lib = loaded
        return loaded

    tried = "\n  ".join(errors) if errors else "(no paths tried)"
    raise ProjectMLibraryError(
        "libprojectM shared library not found. Set PROJECTM_LIB or install libprojectM.\n"
        f"Tried:\n  {tried}"
    )


class ProjectM:
    """Context-manager-friendly wrapper around a libprojectM instance."""

    def __init__(self) -> None:
        lib = _get_lib()
        handle = lib.projectm_create()
        if not handle:
            raise RuntimeError(
                "projectm_create returned NULL; ensure an OpenGL context exists and is current"
            )
        self._handle = handle
        self._texture_path_storage: list[bytes] = []
        self._beat_sensitivity = DEFAULT_BEAT_SENSITIVITY
        self._pcm_channels = 1
        self._failure_queue: deque[PresetLoadFailure] = deque()
        self._switch_failed_callback: PresetSwitchFailedEvent | None = None
        self.set_preset_switch_failed_handler(self._enqueue_preset_failure)

    @property
    def handle(self) -> c_void_p:
        return self._handle

    def destroy(self) -> None:
        if self._handle:
            _get_lib().projectm_destroy(self._handle)
            self._handle = c_void_p()

    def __enter__(self) -> ProjectM:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.destroy()

    def set_window_size(self, width: int, height: int) -> None:
        _get_lib().projectm_set_window_size(
            self._handle, c_size_t(width), c_size_t(height)
        )

    def load_preset(self, path: Path | str, smooth: bool = False) -> None:
        encoded = os.fspath(path).encode("utf-8")
        _get_lib().projectm_load_preset_file(self._handle, encoded, smooth)

    def lock_preset(self, locked: bool = True) -> None:
        _get_lib().projectm_set_preset_locked(self._handle, locked)

    def set_texture_paths(self, paths: list[str | Path]) -> None:
        encoded = [os.fspath(p).encode("utf-8") for p in paths]
        self._texture_path_storage = encoded
        if encoded:
            arr = (c_char_p * len(encoded))(*encoded)
            _get_lib().projectm_set_texture_search_paths(
                self._handle, arr, c_size_t(len(encoded))
            )
        else:
            _get_lib().projectm_set_texture_search_paths(
                self._handle, POINTER(c_char_p)(), c_size_t(0)
            )

    def feed_pcm(self, samples: np.ndarray, *, channels: int = 1) -> None:
        if samples.size == 0:
            return
        self._pcm_channels = channels
        arr = np.ascontiguousarray(samples, dtype=np.float32).ravel()
        scale = self._beat_sensitivity
        if scale != 1.0:
            arr = arr * scale
            arr = np.ascontiguousarray(arr, dtype=np.float32)
        lib = _get_lib()
        max_n = int(lib.projectm_pcm_get_max_samples())
        if max_n <= 0:
            max_n = len(arr)
        step = max_n
        if channels == 2:
            step = max_n - (max_n % 2)
            if step <= 0:
                step = 2
        channel_type = PROJECTM_MONO if channels == 1 else PROJECTM_STEREO
        for offset in range(0, len(arr), step):
            chunk = arr[offset : offset + step]
            if channels == 2:
                chunk = chunk[: len(chunk) - (len(chunk) % 2)]
                if chunk.size == 0:
                    continue
                count = len(chunk) // 2
            else:
                count = len(chunk)
            data = chunk.ctypes.data_as(POINTER(c_float))
            lib.projectm_pcm_add_float(
                self._handle, data, c_uint(count), c_int32(channel_type)
            )

    def flush_pcm(self) -> None:
        n = int(_get_lib().projectm_pcm_get_max_samples())
        if n <= 0:
            return
        channels = self._pcm_channels
        if channels == 2:
            n = n - (n % 2)
        self.feed_pcm(np.zeros(n, dtype=np.float32), channels=channels)

    def render_to_fbo(self, fbo_id: int) -> None:
        _get_lib().projectm_opengl_render_frame_fbo(
            self._handle, c_uint32(fbo_id)
        )

    def set_beat_sensitivity(self, val: float) -> None:
        sensitivity = clamp_beat_sensitivity(val)
        self._beat_sensitivity = sensitivity
        _get_lib().projectm_set_beat_sensitivity(self._handle, c_float(sensitivity))

    def get_beat_sensitivity(self) -> float:
        return self._beat_sensitivity

    def set_frame_time(self, t_sec: float) -> None:
        _get_lib().projectm_set_frame_time(self._handle, c_double(t_sec))

    def set_fps(self, fps: int) -> None:
        _get_lib().projectm_set_fps(self._handle, c_int32(fps))

    def set_hard_cut_enabled(self, enabled: bool) -> None:
        _get_lib().projectm_set_hard_cut_enabled(self._handle, c_bool(enabled))

    def set_soft_cut_duration(self, seconds: float) -> None:
        _get_lib().projectm_set_soft_cut_duration(self._handle, c_double(seconds))

    def set_preset_duration(self, seconds: float) -> None:
        _get_lib().projectm_set_preset_duration(self._handle, c_double(seconds))

    def set_hard_cut_duration(self, seconds: float) -> None:
        _get_lib().projectm_set_hard_cut_duration(self._handle, c_double(seconds))

    def set_hard_cut_sensitivity(self, value: float) -> None:
        _get_lib().projectm_set_hard_cut_sensitivity(self._handle, c_float(value))

    def set_easter_egg(self, value: float) -> None:
        _get_lib().projectm_set_easter_egg(self._handle, c_float(value))

    def set_preset_start_clean(self, enabled: bool) -> None:
        _get_lib().projectm_set_preset_start_clean(self._handle, c_bool(enabled))

    def _enqueue_preset_failure(
        self,
        filename: str,
        message: str,
        *,
        exhausted: bool = False,
    ) -> None:
        self._failure_queue.append(
            PresetLoadFailure(
                filename=filename,
                message=message,
                exhausted=exhausted,
            )
        )

    def set_preset_switch_failed_handler(
        self, callback: Callable[[str, str], None]
    ) -> None:
        lib = _get_lib()
        if not hasattr(lib, "projectm_set_preset_switch_failed_event_callback"):
            return

        def _on_failed(
            filename: bytes, message: bytes, _user_data: c_void_p
        ) -> None:
            callback(
                filename.decode("utf-8") if filename else "",
                message.decode("utf-8") if message else "",
            )

        self._switch_failed_callback = PresetSwitchFailedEvent(_on_failed)
        lib.projectm_set_preset_switch_failed_event_callback(
            self._handle, self._switch_failed_callback, c_void_p()
        )

    def clear_preset_switch_failed_handler(self) -> None:
        lib = _get_lib()
        if hasattr(lib, "projectm_set_preset_switch_failed_event_callback"):
            lib.projectm_set_preset_switch_failed_event_callback(
                self._handle, PresetSwitchFailedEvent(), c_void_p()
            )
        self._switch_failed_callback = None

    def drain_preset_failures(self) -> list[PresetLoadFailure]:
        failures = list(self._failure_queue)
        self._failure_queue.clear()
        return failures

    def version_info(self) -> dict[str, int | str]:
        lib = _get_lib()
        info: dict[str, int | str] = {}
        if hasattr(lib, "projectm_get_version_components"):
            major = c_int32()
            minor = c_int32()
            patch = c_int32()
            lib.projectm_get_version_components(
                byref(major), byref(minor), byref(patch)
            )
            info["major"] = major.value
            info["minor"] = minor.value
            info["patch"] = patch.value
        if hasattr(lib, "projectm_get_version_string"):
            ptr = lib.projectm_get_version_string()
            try:
                version = _decode_lib_string(ptr)
                if version is not None:
                    info["version"] = version
            finally:
                _free_lib_string(lib, ptr)
        if hasattr(lib, "projectm_get_vcs_version_string"):
            ptr = lib.projectm_get_vcs_version_string()
            try:
                vcs = _decode_lib_string(ptr)
                if vcs is not None:
                    info["vcs"] = vcs
            finally:
                _free_lib_string(lib, ptr)
        return info
