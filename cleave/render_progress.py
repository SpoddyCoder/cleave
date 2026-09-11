"""Machine-readable progress lines for ``cleave render`` (editor subprocess)."""

from __future__ import annotations

import os

RENDER_PROGRESS_ENV = "CLEAVE_RENDER_PROGRESS"
RENDER_PROGRESS_PREFIX = "CLEAVE_RENDER_PROGRESS"


def clamp_render_fraction(fraction: float) -> float:
    return max(0.0, min(1.0, float(fraction)))


def format_render_progress_line(fraction: float) -> str:
    return f"{RENDER_PROGRESS_PREFIX} {clamp_render_fraction(fraction):.4f}"


def parse_render_progress_line(line: str) -> float | None:
    text = line.strip()
    prefix = RENDER_PROGRESS_PREFIX + " "
    if not text.startswith(prefix):
        return None
    try:
        return clamp_render_fraction(float(text[len(prefix) :]))
    except ValueError:
        return None


def render_progress_env_enabled() -> bool:
    return os.environ.get(RENDER_PROGRESS_ENV) == "1"
