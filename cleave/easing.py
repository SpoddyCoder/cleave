"""Shared easing helpers for visual fades and transitions."""

from __future__ import annotations

from collections.abc import Callable


def linear(u: float) -> float:
    return max(0.0, min(1.0, u))


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


FADE_CURVE_FNS: dict[str, Callable[[float], float]] = {
    "linear": linear,
    "smoothstep": smoothstep,
    "ease_out_cubic": ease_out_cubic,
    "ease_out_expo": ease_out_expo,
}


def fade_ramp_alpha(elapsed: float, start: float, end: float, curve: str) -> float:
    """Rising 0 -> 1 ramp between start and end seconds."""
    if end <= start:
        return 1.0 if elapsed >= start else 0.0
    if elapsed < start:
        return 0.0
    if elapsed >= end:
        return 1.0
    u = (elapsed - start) / (end - start)
    fn = FADE_CURVE_FNS.get(curve, smoothstep)
    return fn(u)


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
