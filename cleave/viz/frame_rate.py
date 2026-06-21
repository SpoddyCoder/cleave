"""Wall-clock frame rate measurement for the live visualizer."""

from __future__ import annotations

import time


def format_fps_display(fps: float) -> str:
    return f"FPS: {fps:.1f}"


class FrameRateMeter:
    """Track achieved FPS from full main-loop iterations."""

    def __init__(self, *, smoothing: float = 0.1) -> None:
        self._smoothing = smoothing
        self._frame_start: float | None = None
        self._fps: float | None = None

    def begin_frame(self) -> None:
        self._frame_start = time.perf_counter()

    def end_frame(self) -> float | None:
        start = self._frame_start
        if start is None:
            return self._fps
        dt = time.perf_counter() - start
        self._frame_start = None
        if dt <= 0:
            return self._fps
        instant = 1.0 / dt
        if self._fps is None:
            self._fps = instant
        else:
            self._fps += self._smoothing * (instant - self._fps)
        return self._fps

    @property
    def fps(self) -> float | None:
        return self._fps
