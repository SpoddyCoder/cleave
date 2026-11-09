"""Stop SDL's audio callback without holding the GIL.

pygame's ``AudioDevice.pause()`` and ``close()`` call SDL with the GIL held.
SDL runs the Python callback under the device lock, and the callback needs
the GIL. If the main thread pauses or closes while the callback is waiting
for the GIL, both threads wait forever.

``ctypes`` releases the GIL for the length of a foreign call, so pausing
through it lets a pending callback finish. SDL checks the paused flag and
runs the callback under the same device lock, so once the pause returns the
callback never runs again and ``AudioDevice.close()`` is safe.
"""

from __future__ import annotations

import ctypes
import glob
import os
from typing import Protocol

import pygame

SDL_INIT_AUDIO = 0x00000010


class _HasDeviceId(Protocol):
    @property
    def deviceid(self) -> int: ...


def _sdl_library_candidates() -> list[str]:
    """SDL2 libraries pygame ships, for Linux, Windows, and macOS wheels."""
    pkg_dir = os.path.dirname(pygame.__file__)
    patterns = (
        os.path.join(pkg_dir, os.pardir, "pygame.libs", "libSDL2-*.so*"),
        os.path.join(pkg_dir, "SDL2.dll"),
        os.path.join(pkg_dir, ".dylibs", "libSDL2*.dylib"),
    )
    found: list[str] = []
    for pattern in patterns:
        found.extend(sorted(glob.glob(pattern)))
    return found


_sdl_lib: ctypes.CDLL | None = None


def _sdl_library() -> ctypes.CDLL | None:
    """The SDL2 instance pygame loaded, or None when it can't be found.

    Opening the same path returns the already loaded library. A different
    copy would not have the audio subsystem running, so ``SDL_WasInit``
    rejects it. Only a hit is cached, so a lookup before audio starts
    doesn't stick.
    """
    global _sdl_lib
    if _sdl_lib is not None:
        return _sdl_lib
    for path in _sdl_library_candidates():
        try:
            lib = ctypes.CDLL(path)
            was_init = lib.SDL_WasInit
            pause = lib.SDL_PauseAudioDevice
        except (OSError, AttributeError):
            continue
        was_init.argtypes = [ctypes.c_uint32]
        was_init.restype = ctypes.c_uint32
        if not was_init(SDL_INIT_AUDIO) & SDL_INIT_AUDIO:
            continue
        pause.argtypes = [ctypes.c_uint32, ctypes.c_int]
        pause.restype = None
        _sdl_lib = lib
        return lib
    return None


def pause_device_without_gil(device: _HasDeviceId) -> bool:
    """Pause *device* with the GIL released. False when SDL isn't reachable.

    After a True return SDL never calls the device's callback again.
    """
    lib = _sdl_library()
    if lib is None:
        return False
    lib.SDL_PauseAudioDevice(int(device.deviceid), 1)
    return True
