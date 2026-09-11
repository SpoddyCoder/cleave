"""Session-only project render job defaults and output path.

These knobs are live overlay state, not viz YAML. Offline ``cleave render``
reads the same output-path rule so the panel path matches the CLI default.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Literal

ProjectRenderQuality = Literal["normal", "high", "viz"]

PROJECT_RENDER_QUALITIES: tuple[ProjectRenderQuality, ...] = (
    "normal",
    "high",
    "viz",
)

PROJECT_RENDER_QUALITY_HELP_ENTRIES: tuple[tuple[str, str], ...] = (
    ("normal", "full resolution; default encode preset."),
    ("high", "full resolution; slower encode for best quality."),
    ("viz", "preview-quality layer scale (faster, matches live preview)."),
)

DEFAULT_PROJECT_RENDER_QUALITY: ProjectRenderQuality = "normal"
DEFAULT_PROJECT_RENDER_START_SEC = 0
DEFAULT_PROJECT_RENDER_OUTPUT_LABEL = "renders/render.mp4"


def project_render_duration_ceil_sec(duration_sec: float) -> int:
    return max(1, math.ceil(duration_sec))


def resolved_project_render_end_sec(
    end_sec: int | None, duration_sec: float
) -> int:
    if end_sec is None:
        return project_render_duration_ceil_sec(duration_sec)
    return end_sec


def default_project_render_path(
    project_dir: Path,
    name: str,
    *,
    start_sec: int,
    end_sec: int,
    duration_sec: float,
) -> Path:
    """Default MP4 path under ``<project>/renders/``.

    Full-song jobs use ``<name>.mp4``. A trimmed start or end adds
    ``_<start>-<end>s`` before the extension.
    """
    duration_ceil = project_render_duration_ceil_sec(duration_sec)
    if start_sec > 0 or end_sec < duration_ceil:
        filename = f"{name}_{start_sec}-{end_sec}s.mp4"
    else:
        filename = f"{name}.mp4"
    return project_dir / "renders" / filename
