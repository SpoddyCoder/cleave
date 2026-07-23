"""Shared easing helpers for visual fades and transitions."""

from __future__ import annotations


def smoothstep(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3.0 - 2.0 * u)


def ease_out_cubic(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return 1.0 - (1.0 - u) ** 3


def ease_out_expo(u: float) -> float:
    u = max(0.0, min(1.0, u))
    if u >= 1.0:
        return 1.0
    if u <= 0.0:
        return 0.0
    return 1.0 - 2.0 ** (-10.0 * u)


def ease_out_back(u: float, *, overshoot: float = 1.525) -> float:
    """Ease-out back with configurable overshoot (default ~8%)."""
    u = max(0.0, min(1.0, u))
    c1 = overshoot
    c3 = c1 + 1.0
    return 1.0 + c3 * (u - 1.0) ** 3 + c1 * (u - 1.0) ** 2


def fade_alpha(
    t_sec: float, duration_sec: float, fade_in: float, fade_out: float
) -> float:
    """Return combined fade multiplier in [0, 1] using smoothstep easing."""
    alpha_in = 1.0
    if fade_in > 0.0:
        alpha_in = smoothstep(t_sec / fade_in) if t_sec < fade_in else 1.0

    alpha_out = 1.0
    if fade_out > 0.0:
        fade_start = duration_sec - fade_out
        if t_sec > fade_start:
            u = (duration_sec - t_sec) / fade_out
            alpha_out = smoothstep(u)

    return alpha_in * alpha_out
