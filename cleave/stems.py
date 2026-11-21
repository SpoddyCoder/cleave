"""Stem types, labels, stem counts, and project wav paths (no analysis imports)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

from cleave.project import load_manifest, manifest_path, mix_path

StemCount = Literal[4, 6]
STEM_COUNTS: tuple[StemCount, ...] = (4, 6)
DEFAULT_STEM_COUNT: StemCount = 4

FOUR_STEM_NAMES = ("drums", "bass", "vocals", "other")
SIX_STEM_NAMES = ("drums", "bass", "vocals", "guitar", "piano", "other")
StemSource = Literal[
    "drums", "bass", "vocals", "guitar", "piano", "other", "full_mix"
]
STEM_SOURCES: tuple[StemSource, ...] = (
    "drums",
    "bass",
    "vocals",
    "guitar",
    "piano",
    "other",
    "full_mix",
)
BEAT_DETECTION_STEM_CHOICES = (
    "drums",
    "full-mix",
    "bass",
    "vocals",
    "guitar",
    "piano",
    "other",
)
STEMS_DIR = "stems"


def stem_names(count: StemCount) -> tuple[str, ...]:
    """Separated stem names for a *count*-stem project, in display order."""
    if count == 6:
        return SIX_STEM_NAMES
    if count == 4:
        return FOUR_STEM_NAMES
    raise ValueError(f"unsupported stem count {count!r}; expected 4 or 6")


def stem_sources(count: StemCount) -> tuple[StemSource, ...]:
    """Layer stem choices for a *count*-stem project: its stems plus ``full_mix``."""
    return (*cast(tuple[StemSource, ...], stem_names(count)), "full_mix")


def parse_stem_count(raw: object) -> StemCount:
    """Validate a stem count from the CLI or a file."""
    if raw in STEM_COUNTS and not isinstance(raw, bool):
        return cast(StemCount, raw)
    if isinstance(raw, str) and raw.strip() in ("4", "6"):
        return cast(StemCount, int(raw.strip()))
    raise ValueError(f"invalid stem count {raw!r}; expected 4 or 6")


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
    if cli_value not in BEAT_DETECTION_STEM_CHOICES:
        allowed = ", ".join(BEAT_DETECTION_STEM_CHOICES)
        raise ValueError(
            f"invalid beat detection stem {cli_value!r}; expected one of: {allowed}"
        )
    return cast(StemSource, cli_value.replace("-", "_"))


def project_stem_count(project_dir: Path) -> StemCount:
    """Stem count of *project_dir*, from the Demucs model in ``project.yaml``.

    A project with no manifest yet (not separated) reads as the default.
    """
    from cleave.model_weights import stem_count_for_model

    if not manifest_path(project_dir).is_file():
        return DEFAULT_STEM_COUNT
    return stem_count_for_model(load_manifest(project_dir).demucs_model)


def stems_dir(project_dir: Path) -> Path:
    """Return the stem wav directory inside a Cleave project."""
    return project_dir / STEMS_DIR


def stem_paths(
    project_dir: Path, count: StemCount | None = None
) -> dict[str, Path]:
    """Map stem names to wav paths under a Cleave project.

    *count* defaults to the project's own stem count.
    """
    if count is None:
        count = project_stem_count(project_dir)
    base = stems_dir(project_dir)
    return {name: base / f"{name}.wav" for name in stem_names(count)}


def beat_detection_audio_path(project_dir: Path, stem: StemSource) -> Path:
    """Return the wav path Beat This! should run on for *stem*."""
    if stem == "full_mix":
        return mix_path(project_dir)
    paths = stem_paths(project_dir)
    if stem not in paths:
        raise ValueError(
            f"beat detection stem {stem!r} is not in this project's stems"
        )
    return paths[stem]
