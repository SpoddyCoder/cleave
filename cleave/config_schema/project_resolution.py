"""Project resolution defaults, clamps, and steps.

Width and height persist in ``project.yaml`` under ``resolution:``. They set
the offline render output size and the live preview content size and shape.
"""

from __future__ import annotations

DEFAULT_RESOLUTION_WIDTH = 1920
DEFAULT_RESOLUTION_HEIGHT = 1080
RESOLUTION_WIDTH_MIN = 320
RESOLUTION_HEIGHT_MIN = 240
RESOLUTION_STEP = 10
RESOLUTION_STEP_LARGE = 100


def clamp_resolution_width(value: int | float) -> int:
    return max(RESOLUTION_WIDTH_MIN, int(round(value)))


def clamp_resolution_height(value: int | float) -> int:
    return max(RESOLUTION_HEIGHT_MIN, int(round(value)))
