"""Live render post-FX fade for the visualizer."""

from __future__ import annotations

from cleave.easing import fade_alpha


def live_frame_fade_alpha(
    t_sec: float,
    duration_sec: float,
    fade_in: float,
    fade_out: float,
    *,
    enabled: bool,
    solo: bool,
) -> float:
    if not enabled or solo:
        return 1.0
    return fade_alpha(t_sec, duration_sec, fade_in, fade_out)
