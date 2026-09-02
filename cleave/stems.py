"""Stem types, labels, and project wav paths (no analysis imports)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from cleave.project import mix_path

STEM_NAMES = ("drums", "bass", "vocals", "other")
StemSource = Literal["drums", "bass", "vocals", "other", "full_mix"]
STEM_SOURCES: tuple[StemSource, ...] = (
    "drums",
    "bass",
    "vocals",
    "other",
    "full_mix",
)
BEAT_DETECTION_STEM_CHOICES = ("drums", "full-mix", "bass", "vocals", "other")
_CLI_BEAT_DETECTION_STEM: dict[str, StemSource] = {
    "drums": "drums",
    "full-mix": "full_mix",
    "bass": "bass",
    "vocals": "vocals",
    "other": "other",
}
STEMS_DIR = "stems"


def stem_overlay_header(stem: StemSource) -> str:
    if stem == "full_mix":
        return "MIX"
    return stem.upper()


def stem_control_label(stem: StemSource) -> str:
    if stem == "full_mix":
        return "full-mix"
    return stem


def parse_beat_detection_stem(cli_value: str) -> StemSource:
    """Map a CLI ``--beat-detection-stem`` value to an internal :data:`StemSource`."""
    try:
        return _CLI_BEAT_DETECTION_STEM[cli_value]
    except KeyError:
        allowed = ", ".join(BEAT_DETECTION_STEM_CHOICES)
        raise ValueError(
            f"invalid beat detection stem {cli_value!r}; expected one of: {allowed}"
        ) from None


def stems_dir(project_dir: Path) -> Path:
    """Return the stem wav directory inside a Cleave project."""
    return project_dir / STEMS_DIR


def stem_paths(project_dir: Path) -> dict[str, Path]:
    """Map stem names to wav paths under a Cleave project."""
    base = stems_dir(project_dir)
    return {name: base / f"{name}.wav" for name in STEM_NAMES}


def beat_detection_audio_path(project_dir: Path, stem: StemSource) -> Path:
    """Return the wav path Beat This! should run on for *stem*."""
    if stem == "full_mix":
        return mix_path(project_dir)
    return stem_paths(project_dir)[stem]
