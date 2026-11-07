"""SDL window calls pygame 2 does not expose: minimum size and window flags.

Binds through ctypes to the SDL2 library pygame already loaded. On Windows
``SDL2.dll`` is already in the process, so loading it by name returns that
module. Elsewhere the library sits in ``pygame.libs`` next to the package.
When the library or the window cannot be found, every call is a no-op.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import functools
import glob
import os
import sys

SDL_WINDOW_FULLSCREEN = 0x00000001
SDL_WINDOW_MINIMIZED = 0x00000040
SDL_WINDOW_MAXIMIZED = 0x00000080
SDL_WINDOW_FULLSCREEN_DESKTOP = SDL_WINDOW_FULLSCREEN | 0x00001000


def _sdl_library_candidates() -> list[str]:
    import pygame

    package_dir = os.path.dirname(pygame.__file__)
    if sys.platform == "win32":
        # The bare name resolves to the module pygame already loaded.
        return ["SDL2.dll", os.path.join(package_dir, "SDL2.dll")]
    patterns = (
        os.path.join(package_dir, os.pardir, "pygame.libs", "libSDL2-2*.so*"),
        os.path.join(package_dir, ".dylibs", "libSDL2*.dylib"),
        os.path.join(package_dir, "libSDL2*"),
    )
    found: list[str] = []
    for pattern in patterns:
        found.extend(sorted(glob.glob(pattern)))
    system = ctypes.util.find_library("SDL2")
    if system:
        found.append(system)
    return found


@functools.cache
def _sdl() -> ctypes.CDLL | None:
    for candidate in _sdl_library_candidates():
        try:
            lib = ctypes.CDLL(candidate)
        except OSError:
            continue
        try:
            lib.SDL_GL_GetCurrentWindow.restype = ctypes.c_void_p
            lib.SDL_GL_GetCurrentWindow.argtypes = []
            lib.SDL_SetWindowMinimumSize.restype = None
            lib.SDL_SetWindowMinimumSize.argtypes = [
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.c_int,
            ]
            lib.SDL_GetWindowFlags.restype = ctypes.c_uint32
            lib.SDL_GetWindowFlags.argtypes = [ctypes.c_void_p]
        except AttributeError:
            continue
        return lib
    return None


def _current_window() -> tuple[ctypes.CDLL, int] | None:
    lib = _sdl()
    if lib is None:
        return None
    window = lib.SDL_GL_GetCurrentWindow()
    if not window:
        return None
    return lib, window


def set_minimum_size(width: int, height: int) -> bool:
    """Stop the GL window shrinking below *width* x *height*. False when unavailable."""
    found = _current_window()
    if found is None:
        return False
    lib, window = found
    lib.SDL_SetWindowMinimumSize(window, max(1, int(width)), max(1, int(height)))
    return True


def window_flags() -> int | None:
    """SDL flags of the GL window, or None when unavailable."""
    found = _current_window()
    if found is None:
        return None
    lib, window = found
    return int(lib.SDL_GetWindowFlags(window))
