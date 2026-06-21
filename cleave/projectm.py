"""ctypes wrapper for libprojectM."""

from __future__ import annotations

import ctypes
import os
import subprocess
from ctypes import (
    POINTER,
    c_bool,
    c_char_p,
    c_double,
    c_float,
    c_int32,
    c_size_t,
    c_uint,
    c_uint32,
    c_void_p,
)
from pathlib import Path

import numpy as np

from cleave.config import DEFAULT_BEAT_SENSITIVITY, clamp_beat_sensitivity

PROJECTM_MONO = 1
PROJECTM_STEREO = 2

_lib: ctypes.CDLL | None = None


class ProjectMLibraryError(OSError):
    """libprojectM shared library not found or failed to load."""


def _pkg_config_candidates() -> list[str]:
    try:
        libdirs = subprocess.run(
            ["pkg-config", "--libs-only-L", "libprojectM"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        libnames = subprocess.run(
            ["pkg-config", "--libs-only-l", "libprojectM"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    candidates: list[str] = []
    for entry in libdirs:
        if not entry.startswith("-L"):
            continue
        base = Path(entry[2:])
        for lib in libnames:
            if lib.startswith("-l"):
                candidates.append(str(base / f"lib{lib[2:]}.so"))
    return candidates


def _library_candidates() -> list[str]:
    candidates: list[str] = []
    env_path = os.environ.get("PROJECTM_LIB")
    if env_path:
        candidates.append(env_path)
    candidates.extend(_pkg_config_candidates())
    candidates.extend(
        [
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
