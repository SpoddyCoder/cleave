"""Interpolated, latency-aware transport clock (pure math, no SDL).

Anchors to a consumed PCM frame and wall time, then interpolates with
``time.perf_counter()`` between audio-callback reanchors. Exposes file
(decode) and audible (latency-corrected) positions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


MAX_RESIDUAL_LATENCY_SEC = 2.0


@dataclass
class TransportClock:
    """Smooth file-relative transport position between discrete PCM anchors."""

    anchor_frame: int = 0
    anchor_wall_time: float = 0.0
    sample_rate: int = 44100
    latency_frames: int = 0
    residual_latency_sec: float = 0.0
    paused: bool = False
    total_frames: int = 0
    max_ahead_frames: int = 0

    def reanchor(self, frame: int, wall_time: float | None = None) -> None:
        self.anchor_frame = frame
        self.anchor_wall_time = (
            time.perf_counter() if wall_time is None else wall_time
        )

    def set_paused(self, paused: bool, wall_time: float | None = None) -> None:
        now = time.perf_counter() if wall_time is None else wall_time
        if paused:
            if not self.paused:
                self.anchor_frame = int(self.file_position_frames(now))
                self.anchor_wall_time = now
                self.paused = True
            return
        if self.paused:
            self.reanchor(self.anchor_frame, now)
            self.paused = False

    def set_latency_frames(self, n: int) -> None:
        self.latency_frames = max(0, int(n))

    def set_residual_latency_sec(self, sec: float) -> None:
        self.residual_latency_sec = max(0.0, min(float(sec), MAX_RESIDUAL_LATENCY_SEC))

    def file_position_frames(self, now: float | None = None) -> float:
        if self.paused:
            return float(self.anchor_frame)
        t = time.perf_counter() if now is None else now
        pos = self.anchor_frame + (t - self.anchor_wall_time) * self.sample_rate
        max_pos = min(
            float(self.total_frames),
            float(self.anchor_frame + self.max_ahead_frames),
        )
        return max(0.0, min(pos, max_pos))

    def file_position_sec(self, now: float | None = None) -> float:
        if self.sample_rate <= 0:
            return 0.0
        return self.file_position_frames(now) / self.sample_rate

    def audible_position_zero_residual_latency_sec(self, now: float | None = None) -> float:
        if self.sample_rate <= 0:
            return 0.0
        file_frames = self.file_position_frames(now)
        audible_frames = max(0.0, file_frames - float(self.latency_frames))
        return audible_frames / self.sample_rate

    def audible_position_sec(self, now: float | None = None) -> float:
        if self.sample_rate <= 0:
            return 0.0
        file_frames = self.file_position_frames(now)
        total_latency_frames = (
            float(self.latency_frames) + self.residual_latency_sec * self.sample_rate
        )
        audible_frames = max(0.0, file_frames - total_latency_frames)
        return audible_frames / self.sample_rate
