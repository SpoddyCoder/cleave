"""Wall-clock frame rate measurement for the live visualizer."""

from __future__ import annotations

import time

from cleave.stem_pcm import LIVE_PROJECTM_FPS

LIVE_PROJECTM_FPS_FLOOR = 48


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


class ProjectMFpsGovernor:
    """Smooth projectM target FPS independently of UI-loaded display measurement."""

    def __init__(
        self,
        *,
        nominal_fps: int = LIVE_PROJECTM_FPS,
        floor_fps: int = LIVE_PROJECTM_FPS_FLOOR,
        rise_alpha: float = 0.15,
        fall_alpha: float = 0.03,
    ) -> None:
        self._nominal_fps = nominal_fps
        self._floor_fps = floor_fps
        self._rise_alpha = rise_alpha
        self._fall_alpha = fall_alpha
        self._target_fps = float(nominal_fps)
        self._applied_fps: int | None = None

    @property
    def target_fps(self) -> int:
        return round(self._target_fps)

    def observe(self, measured_fps: float | None) -> None:
        if measured_fps is None:
            return
        alpha = (
            self._rise_alpha
            if measured_fps >= self._target_fps
            else self._fall_alpha
        )
        self._target_fps += alpha * (measured_fps - self._target_fps)
        self._target_fps = max(
            self._floor_fps, min(self._nominal_fps, self._target_fps)
        )

    def apply_if_changed(self, layers) -> bool:
        target = self.target_fps
        if target == self._applied_fps:
            return False
        from cleave.viz.layer_pipeline import LayerFramePipeline

        LayerFramePipeline.set_projectm_fps(layers, target)
        self._applied_fps = target
        return True
