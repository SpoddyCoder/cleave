"""Preset scan probe profiles, classification, and JSON report types."""

from __future__ import annotations

import json
import math
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pygame
from OpenGL.GL import (
    GL_COLOR_ATTACHMENT0,
    GL_DEPTH_ATTACHMENT,
    GL_DEPTH_COMPONENT24,
    GL_FRAMEBUFFER,
    GL_FRAMEBUFFER_COMPLETE,
    GL_RENDERBUFFER,
    GL_RGBA,
    GL_RGBA8,
    GL_TEXTURE_2D,
    GL_UNSIGNED_BYTE,
    glBindFramebuffer,
    glBindRenderbuffer,
    glBindTexture,
    glCheckFramebufferStatus,
    glDeleteFramebuffers,
    glDeleteRenderbuffers,
    glDeleteTextures,
    glFramebufferRenderbuffer,
    glFramebufferTexture2D,
    glGenFramebuffers,
    glGenRenderbuffers,
    glGenTextures,
    glRenderbufferStorage,
    glTexImage2D,
)

from cleave.pcm_io import SAMPLE_RATE_HZ
from cleave.preset_scan_metrics import (
    LUMA_COVERAGE_CUTOFFS,
    WHITE_COVERAGE_CUTOFFS,
    FrameMetrics,
    PresetMetrics,
    peak_metrics,
    sample_frame_metrics,
    white_frame_fraction,
)
from cleave.preset_scan_targets import PresetTarget, ScanTargets
from cleave.projectm import PresetLoadFailure, ProjectM
from cleave.stem_pcm import samples_per_frame

ScanMode = Literal["project", "bulk"]
PresetResultCategory = Literal["load_failed", "black", "dim", "washed_out", "ok"]

PROBE_WARMUP_FRAMES = 15
PROBE_WINDOW_FRAMES = 75
PROBE_FPS = 30
PROBE_FBO_WIDTH = 480
PROBE_FBO_HEIGHT = 270

COVERAGE_LUMA_MIN = 16

WHITE_CHANNEL_MIN = 235
WHITE_AREA_FRAC = 0.6
MIN_WHITE_FRAME_FRAC = 0.3

BLACK_MAX_LUMA = 1.0
BLACK_COVERAGE = 0.0003

DIM_MEAN_LUMA = 15.0
DIM_COVERAGE = 0.25

VERY_SPARSE_DIM_MEAN = 5.15
VERY_SPARSE_DIM_MAX = 100.0
VERY_SPARSE_DIM_COV16 = 0.015

SPARSE_DIM_MEAN = 9.95
SPARSE_DIM_MAX = 80.0
SPARSE_DIM_COV16_MIN = 0.102
SPARSE_DIM_COV16_MAX = 0.128

CAPPED_DIM_MEAN = 22.0
CAPPED_DIM_MAX_LO = 50.0
CAPPED_DIM_MAX_HI = 111.0
CAPPED_DIM_COV16 = 0.9

BRIGHT_ON_BLACK_MAX = 25.0
BRIGHT_ON_BLACK_COVERAGE = 0.00025

DIM_BOB_COV_LO = 0.07
DIM_BOB_COV_HI = 0.13
DIM_BOB_MEAN_MID = 6.0
DIM_BOB_MEAN_HI = 10.0

WASHED_WHITE_AREA_FRAC_SOFT = 0.15
WASHED_MIN_WHITE_FRAME_FRAC_SOFT = 0.55
WASHED_MEAN_SOFT = 200.0
WASHED_MEAN_PEAK = 245.0
WASHED_COV16_MIN = 0.999
WASHED_COV192_PEAK = 0.95
WASHED_MAX_LO = 240.0
WASHED_MEAN_LO = 155.0
WASHED_MEAN_HI = 175.0
WASHED_COV192_LO = 0.05
WASHED_MAX_MID = 235.0
WASHED_MEAN_MID_LO = 170.0
WASHED_MEAN_MID_HI = 188.0
WASHED_COV192_MID = 0.28
WASHED_WHITE235_MID_MAX = 0.10

DEFER_LOAD_FAILED_MIN_COV16 = 0.9
BROKEN_SOFT_WHITE_MEAN_HI = 235.0

SCAN_THRESHOLDS: dict[str, float] = {
    "black_max_luma": BLACK_MAX_LUMA,
    "black_coverage": BLACK_COVERAGE,
    "dim_mean_luma": DIM_MEAN_LUMA,
    "dim_coverage": DIM_COVERAGE,
    "very_sparse_dim_mean": VERY_SPARSE_DIM_MEAN,
    "very_sparse_dim_max": VERY_SPARSE_DIM_MAX,
    "very_sparse_dim_cov16": VERY_SPARSE_DIM_COV16,
    "sparse_dim_mean": SPARSE_DIM_MEAN,
    "sparse_dim_max": SPARSE_DIM_MAX,
    "sparse_dim_cov16_min": SPARSE_DIM_COV16_MIN,
    "sparse_dim_cov16_max": SPARSE_DIM_COV16_MAX,
    "capped_dim_mean": CAPPED_DIM_MEAN,
    "capped_dim_max_lo": CAPPED_DIM_MAX_LO,
    "capped_dim_max_hi": CAPPED_DIM_MAX_HI,
    "capped_dim_cov16": CAPPED_DIM_COV16,
    "white_channel_min": float(WHITE_CHANNEL_MIN),
    "white_area_frac": WHITE_AREA_FRAC,
    "min_white_frame_frac": MIN_WHITE_FRAME_FRAC,
    "bright_on_black_max": BRIGHT_ON_BLACK_MAX,
    "bright_on_black_coverage": BRIGHT_ON_BLACK_COVERAGE,
    "coverage_luma_min": float(COVERAGE_LUMA_MIN),
    "dim_bob_cov_lo": DIM_BOB_COV_LO,
    "dim_bob_cov_hi": DIM_BOB_COV_HI,
    "dim_bob_mean_mid": DIM_BOB_MEAN_MID,
    "dim_bob_mean_hi": DIM_BOB_MEAN_HI,
    "white_area_frac_soft": WASHED_WHITE_AREA_FRAC_SOFT,
    "min_white_frame_frac_soft": WASHED_MIN_WHITE_FRAME_FRAC_SOFT,
    "washed_mean_soft": WASHED_MEAN_SOFT,
    "washed_mean_peak": WASHED_MEAN_PEAK,
    "washed_cov16_min": WASHED_COV16_MIN,
    "washed_cov192_peak": WASHED_COV192_PEAK,
    "washed_max_lo": WASHED_MAX_LO,
    "washed_mean_lo": WASHED_MEAN_LO,
    "washed_mean_hi": WASHED_MEAN_HI,
    "washed_cov192_lo": WASHED_COV192_LO,
    "washed_max_mid": WASHED_MAX_MID,
    "washed_mean_mid_lo": WASHED_MEAN_MID_LO,
    "washed_mean_mid_hi": WASHED_MEAN_MID_HI,
    "washed_cov192_mid": WASHED_COV192_MID,
    "washed_white235_mid_max": WASHED_WHITE235_MID_MAX,
}


def scan_thresholds() -> dict[str, float]:
    return dict(SCAN_THRESHOLDS)

REPORT_FLUSH_EVERY = 10

QUARANTINE_CATEGORIES: frozenset[PresetResultCategory] = frozenset(
    ("load_failed", "black", "dim", "washed_out")
)


@dataclass(frozen=True)
class ProbeProfile:
    warmup_frames: int
    window_frames: int

    @property
    def total_frames(self) -> int:
        return self.warmup_frames + self.window_frames


@dataclass(frozen=True)
class ProbePcm:
    channels: int = 1

    def chunk(self, frame_idx: int, n_samples: int) -> np.ndarray:
        return _synthetic_pcm_burst(frame_idx, n_samples)


@dataclass(frozen=True)
class PresetScanTimings:
    load_sec: float | None = None
    render_sec: float | None = None


@dataclass(frozen=True)
class PresetScanResult:
    path: Path
    result: PresetResultCategory
    layers: tuple[str, ...]
    error: str | None = None
    timings: PresetScanTimings | None = None
    luma: FrameMetrics | None = None


@dataclass(frozen=True)
class ScanReport:
    scan_mode: ScanMode
    project_dir: Path | None
    config_path: Path | None
    presets_dir: Path | None
    preset_root: Path | None
    texture_paths: tuple[Path, ...]
    layers: dict[str, list[str]]
    thresholds: dict[str, float]
    probe_frames: int
    probe_fps: int
    fbo_size: tuple[int, int]
    presets: tuple[PresetScanResult, ...]
    complete: bool = True


@dataclass(frozen=True)
class ResumeData:
    scan_mode: ScanMode
    results: tuple[PresetScanResult, ...]
    skip_paths: frozenset[Path]
    complete: bool


def build_probe_pcm() -> ProbePcm:
    return ProbePcm()


def probe_profile() -> ProbeProfile:
    return ProbeProfile(
        warmup_frames=PROBE_WARMUP_FRAMES,
        window_frames=PROBE_WINDOW_FRAMES,
    )


def _normalize_peak_metrics(
    peaks: FrameMetrics | dict[str, Any],
) -> tuple[float, float, dict[int, float]]:
    if isinstance(peaks, FrameMetrics):
        return peaks.max_luma, peaks.mean_luma, peaks.coverage

    if not isinstance(peaks, dict):
        raise TypeError("peaks must be FrameMetrics or a metrics dict")

    max_raw = peaks.get("max_luma", peaks.get("max"))
    mean_raw = peaks.get("mean_luma", peaks.get("mean"))
    if not isinstance(max_raw, (int, float)) or not isinstance(mean_raw, (int, float)):
        raise ValueError("peaks missing max_luma and mean_luma")

    coverage_raw = peaks.get("coverage")
    if not isinstance(coverage_raw, dict):
        raise ValueError("peaks missing coverage")

    coverage: dict[int, float] = {}
    for cutoff in LUMA_COVERAGE_CUTOFFS:
        value = coverage_raw.get(cutoff, coverage_raw.get(str(cutoff)))
        if not isinstance(value, (int, float)):
            raise ValueError(f"peaks missing coverage for cutoff {cutoff}")
        coverage[cutoff] = float(value)

    return float(max_raw), float(mean_raw), coverage


def _peak_white_coverage(
    peaks: FrameMetrics | dict[str, Any],
    cutoff: int,
) -> float:
    if isinstance(peaks, FrameMetrics):
        return peaks.white_coverage.get(cutoff, 0.0)

    if not isinstance(peaks, dict):
        raise TypeError("peaks must be FrameMetrics or a metrics dict")

    white_raw = peaks.get("white_coverage")
    if not isinstance(white_raw, dict):
        return 0.0

    value = white_raw.get(cutoff, white_raw.get(str(cutoff)))
    if not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _dim_bright_on_black_ok(
    *,
    max_luma: float,
    mean_luma: float,
    cov_min: float,
    th: dict[str, float],
) -> bool:
    if max_luma < th["bright_on_black_max"] or cov_min < th["bright_on_black_coverage"]:
        return False
    if "dim_bob_cov_lo" not in th:
        return True
    if cov_min < th["dim_bob_cov_lo"]:
        return True
    if mean_luma >= th["dim_bob_mean_hi"]:
        return True
    return th["dim_bob_cov_lo"] <= cov_min < th["dim_bob_cov_hi"] and mean_luma >= th[
        "dim_bob_mean_mid"
    ]


def _defer_load_failed(peaks: FrameMetrics | dict[str, Any], th: dict[str, float]) -> bool:
    try:
        max_luma, _, coverage = _normalize_peak_metrics(peaks)
    except (TypeError, ValueError):
        return False
    cov_min = coverage[int(th["coverage_luma_min"])]
    return (
        max_luma >= th["black_max_luma"]
        and cov_min >= DEFER_LOAD_FAILED_MIN_COV16
    )


def _broken_soft_white_black(
    peaks: FrameMetrics | dict[str, Any],
    frames: tuple[FrameMetrics, ...],
    th: dict[str, float],
) -> bool:
    _, mean_luma, _ = _normalize_peak_metrics(peaks)
    white_frac_hard = white_frame_fraction(
        frames,
        warmup_frames=0,
        window_frames=0,
        channel_min_cutoff=int(th["white_channel_min"]),
        area_frac=th["white_area_frac"],
    )
    if white_frac_hard >= th["min_white_frame_frac"]:
        return False
    white_frac_soft = white_frame_fraction(
        frames,
        warmup_frames=0,
        window_frames=0,
        channel_min_cutoff=int(th["white_channel_min"]),
        area_frac=th["white_area_frac_soft"],
    )
    return (
        white_frac_soft >= th["min_white_frame_frac_soft"]
        and th["washed_mean_soft"] <= mean_luma <= BROKEN_SOFT_WHITE_MEAN_HI
    )


def _washed_out_tiers(
    peaks: FrameMetrics | dict[str, Any],
    frames: tuple[FrameMetrics, ...],
    th: dict[str, float],
) -> bool:
    max_luma, mean_luma, coverage = _normalize_peak_metrics(peaks)
    cov16 = coverage[int(th["coverage_luma_min"])]
    cov192 = coverage.get(192, 0.0)
    white235 = _peak_white_coverage(peaks, int(th["white_channel_min"]))

    white_frac = white_frame_fraction(
        frames,
        warmup_frames=0,
        window_frames=0,
        channel_min_cutoff=int(th["white_channel_min"]),
        area_frac=th["white_area_frac"],
    )
    if white_frac >= th["min_white_frame_frac"]:
        return True

    white_frac_soft = white_frame_fraction(
        frames,
        warmup_frames=0,
        window_frames=0,
        channel_min_cutoff=int(th["white_channel_min"]),
        area_frac=th["white_area_frac_soft"],
    )
    if (
        white_frac_soft >= th["min_white_frame_frac_soft"]
        and mean_luma >= th["washed_mean_soft"]
    ):
        return True

    if (
        mean_luma >= th["washed_mean_peak"]
        and cov16 >= th["washed_cov16_min"]
        and cov192 >= th["washed_cov192_peak"]
    ):
        return True

    if (
        cov16 >= th["washed_cov16_min"]
        and max_luma >= th["washed_max_lo"]
        and th["washed_mean_lo"] <= mean_luma <= th["washed_mean_hi"]
        and cov192 >= th["washed_cov192_lo"]
    ):
        return True

    if (
        cov16 >= th["washed_cov16_min"]
        and max_luma >= th["washed_max_mid"]
        and th["washed_mean_mid_lo"] <= mean_luma <= th["washed_mean_mid_hi"]
        and cov192 >= th["washed_cov192_mid"]
        and white235 < th["washed_white235_mid_max"]
    ):
        return True

    return False


def classify_preset_result(
    failures: list[PresetLoadFailure],
    peaks: FrameMetrics | dict[str, Any],
    *,
    frames: tuple[FrameMetrics, ...] | None = None,
    thresholds: dict[str, float] | None = None,
) -> tuple[PresetResultCategory, str | None]:
    th = scan_thresholds()
    if thresholds is not None:
        th.update(thresholds)

    active_failures = failures
    if failures and _defer_load_failed(peaks, th):
        active_failures = []

    if active_failures:
        return "load_failed", active_failures[0].message

    if frames is not None:
        if "washed_mean_peak" in th:
            if _broken_soft_white_black(peaks, frames, th):
                return "black", None
        if "washed_mean_peak" in th:
            if _washed_out_tiers(peaks, frames, th):
                return "washed_out", None

    max_luma, mean_luma, coverage = _normalize_peak_metrics(peaks)
    cov_min = coverage[int(th["coverage_luma_min"])]

    if max_luma < th["black_max_luma"] or cov_min < th["black_coverage"]:
        if _dim_bright_on_black_ok(
            max_luma=max_luma,
            mean_luma=mean_luma,
            cov_min=cov_min,
            th=th,
        ):
            return "ok", None
        return "black", None

    if (
        mean_luma < th["very_sparse_dim_mean"]
        and max_luma >= th["very_sparse_dim_max"]
        and cov_min >= th["very_sparse_dim_cov16"]
    ):
        return "dim", None

    if (
        mean_luma < th["sparse_dim_mean"]
        and max_luma >= th["sparse_dim_max"]
        and th["sparse_dim_cov16_min"] <= cov_min < th["sparse_dim_cov16_max"]
    ):
        return "dim", None

    if (
        mean_luma < th["capped_dim_mean"]
        and th["capped_dim_max_lo"] <= max_luma < th["capped_dim_max_hi"]
        and cov_min >= th["capped_dim_cov16"]
    ):
        return "dim", None

    if mean_luma < th["dim_mean_luma"] and cov_min < th["dim_coverage"]:
        if _dim_bright_on_black_ok(
            max_luma=max_luma,
            mean_luma=mean_luma,
            cov_min=cov_min,
            th=th,
        ):
            return "ok", None
        return "dim", None

    return "ok", None


def build_scan_report(
    *,
    scan_mode: ScanMode,
    profile: ProbeProfile,
    targets: ScanTargets,
    results: list[PresetScanResult] | tuple[PresetScanResult, ...],
    project_dir: Path | None = None,
    config_path: Path | None = None,
    complete: bool = True,
) -> ScanReport:
    layers = {
        slot: [str(path) for path in paths]
        for slot, paths in sorted(targets.layer_sources.items())
    }
    return ScanReport(
        scan_mode=scan_mode,
        project_dir=project_dir.resolve() if project_dir is not None else None,
        config_path=config_path.resolve() if config_path is not None else None,
        presets_dir=(
            targets.presets_dir.resolve() if targets.presets_dir is not None else None
        ),
        preset_root=(
            targets.preset_root.resolve() if targets.preset_root is not None else None
        ),
        texture_paths=tuple(p.resolve() for p in targets.texture_paths),
        layers=layers,
        thresholds=scan_thresholds(),
        probe_frames=profile.total_frames,
        probe_fps=PROBE_FPS,
        fbo_size=(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT),
        presets=tuple(results),
        complete=complete,
    )


def scan_report_summary(report: ScanReport) -> dict[str, int]:
    counts: dict[str, int] = {
        "total": len(report.presets),
        "load_failed": 0,
        "black": 0,
        "dim": 0,
        "washed_out": 0,
        "ok": 0,
    }
    for preset in report.presets:
        counts[preset.result] += 1
    return counts


def scan_report_to_dict(report: ScanReport) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "scan_mode": report.scan_mode,
        "project_dir": _path_to_str(report.project_dir),
        "config_path": _path_to_str(report.config_path),
        "presets_dir": _path_to_str(report.presets_dir),
        "preset_root": _path_to_str(report.preset_root),
        "texture_paths": [str(path) for path in report.texture_paths],
        "layers": report.layers,
        "thresholds": report.thresholds,
        "probe_frames": report.probe_frames,
        "probe_fps": report.probe_fps,
        "fbo_size": list(report.fbo_size),
        "presets": [_preset_result_to_dict(preset) for preset in report.presets],
        "summary": scan_report_summary(report),
        "complete": report.complete,
    }
    return payload


def write_scan_report(path: Path, report: ScanReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(scan_report_to_dict(report), fh, indent=2)
            fh.write("\n")
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def existing_report_status(path: Path) -> tuple[int, bool]:
    """Return preset count and completion flag from an on-disk report."""
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"resume report not found: {resolved}")

    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON: {exc}") from exc
    except OSError as exc:
        raise ValueError(str(exc)) from exc

    if not isinstance(raw, dict):
        raise ValueError("report root must be a JSON object")

    presets_raw = raw.get("presets")
    if not isinstance(presets_raw, list):
        raise ValueError("missing presets array")

    complete = raw.get("complete", True)
    return len(presets_raw), bool(complete)


def load_resume_results(path: Path) -> ResumeData:
    """Load prior scan results and skip paths from a report JSON file."""
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"resume report not found: {resolved}")

    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON: {exc}") from exc
    except OSError as exc:
        raise ValueError(str(exc)) from exc

    if not isinstance(raw, dict):
        raise ValueError("report root must be a JSON object")

    scan_mode = raw.get("scan_mode")
    if scan_mode not in ("project", "bulk"):
        raise ValueError("missing or invalid scan_mode")

    presets_raw = raw.get("presets")
    if not isinstance(presets_raw, list):
        raise ValueError("missing presets array")

    results: list[PresetScanResult] = []
    skip_paths: set[Path] = set()
    for index, entry in enumerate(presets_raw):
        try:
            result = _preset_result_from_dict(entry)
        except ValueError as exc:
            raise ValueError(f"invalid preset entry at index {index}: {exc}") from exc
        results.append(result)
        skip_paths.add(result.path.resolve())

    complete = bool(raw.get("complete", True))

    return ResumeData(
        scan_mode=scan_mode,
        results=tuple(results),
        skip_paths=frozenset(skip_paths),
        complete=complete,
    )


def validate_quarantine_dir(
    quarantine_dir: Path,
    scanned_dirs: tuple[Path, ...],
) -> Path:
    """Resolve and create *quarantine_dir*; reject paths inside scanned preset dirs."""
    resolved = quarantine_dir.expanduser().resolve()
    if resolved.exists() and not resolved.is_dir():
        raise ValueError(f"--quarantine target is not a directory: {resolved}")

    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ValueError(f"cannot create quarantine directory {resolved}: {exc}") from exc

    for scanned in scanned_dirs:
        scanned_resolved = scanned.expanduser().resolve()
        if _path_is_inside_or_equal(resolved, scanned_resolved):
            raise ValueError(
                "--quarantine directory must be outside the scanned presets directory"
            )

    return resolved


def delete_presets(
    results: list[PresetScanResult] | tuple[PresetScanResult, ...],
) -> list[Path]:
    """Delete preset files flagged in *results* (QUARANTINE_CATEGORIES only)."""
    deleted: list[Path] = []
    for result in results:
        if result.result not in QUARANTINE_CATEGORIES:
            continue
        path = result.path
        if not path.is_file():
            continue
        path.unlink()
        deleted.append(path)
    return deleted


def quarantine_presets(
    results: list[PresetScanResult] | tuple[PresetScanResult, ...],
    quarantine_dir: Path,
) -> list[tuple[Path, Path]]:
    """Move failed presets into *quarantine_dir* (flat layout, suffix on collision)."""
    moves: list[tuple[Path, Path]] = []
    for result in results:
        if result.result not in QUARANTINE_CATEGORIES:
            continue
        src = result.path
        if not src.is_file():
            continue
        dst = _unique_quarantine_path(quarantine_dir, src.name)
        shutil.move(str(src), str(dst))
        moves.append((src, dst))
    return moves


def scanned_preset_dirs(targets: ScanTargets) -> tuple[Path, ...]:
    """Directories whose preset files are included in *targets*."""
    dirs: set[Path] = set()
    if targets.presets_dir is not None:
        dirs.add(targets.presets_dir.resolve())
    for paths in targets.layer_sources.values():
        for path in paths:
            if path.is_dir():
                dirs.add(path.resolve())
            else:
                dirs.add(path.parent.resolve())
    return tuple(sorted(dirs))


def _configure_probe_projectm(pm: ProjectM, texture_strs: list[str]) -> None:
    pm.set_window_size(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT)
    pm.set_fps(PROBE_FPS)
    pm.set_hard_cut_enabled(False)
    pm.set_texture_paths(texture_strs)


def run_scan(
    targets: ScanTargets,
    *,
    texture_paths: tuple[Path, ...] | None = None,
    report_sink: Callable[[list[PresetScanResult], bool], None] | None = None,
    skip_paths: frozenset[Path] | None = None,
) -> list[PresetScanResult]:
    """Probe each preset in *targets* with a hidden GL context and a fresh ProjectM."""
    profile = probe_profile()
    probe_pcm = build_probe_pcm()
    paths = texture_paths if texture_paths is not None else targets.texture_paths
    texture_strs = [str(path) for path in paths]

    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    pygame.init()
    try:
        pygame.display.set_mode(
            (PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT),
            pygame.OPENGL | pygame.HIDDEN,
        )
    except pygame.error as exc:
        pygame.quit()
        raise RuntimeError(f"failed to open OpenGL context: {exc}") from exc

    fbo: _ProbeFbo | None = None
    results: list[PresetScanResult] = []
    skip = skip_paths or frozenset()
    total = len(targets.presets)
    skip_count = len(skip)
    probed = 0
    resumed_announced = False
    try:
        fbo = _ProbeFbo(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT)
        n_pcm = samples_per_frame(PROBE_FPS)
        frame_dt = 1.0 / PROBE_FPS

        for index, target in enumerate(targets.presets, start=1):
            if target.path.resolve() in skip:
                continue
            if skip_count and not resumed_announced:
                _progress(f"Resuming: {skip_count} done")
                resumed_announced = True
            _progress(f"Scanning {index}/{total} {target.path}...")
            pm = ProjectM()
            try:
                _configure_probe_projectm(pm, texture_strs)
                result = _probe_preset(
                    pm,
                    fbo,
                    target,
                    profile=profile,
                    pcm=probe_pcm,
                    n_pcm=n_pcm,
                    frame_dt=frame_dt,
                )
                results.append(result)
                probed += 1
                if report_sink is not None and probed % REPORT_FLUSH_EVERY == 0:
                    report_sink(results, False)
            finally:
                pm.destroy()

        if report_sink is not None:
            report_sink(results, True)
    except KeyboardInterrupt:
        if report_sink is not None:
            report_sink(results, False)
        raise
    finally:
        if fbo is not None:
            fbo.destroy()
        pygame.quit()

    return results


def _progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def probe_preset_metrics(
    pm: ProjectM,
    fbo: _ProbeFbo,
    preset_path: Path,
    *,
    profile: ProbeProfile,
    pcm: ProbePcm,
    n_pcm: int,
    frame_dt: float,
) -> PresetMetrics:
    """Render *preset_path* with clean boot and return per-frame luma metrics."""
    pm.drain_preset_failures()
    pm.set_preset_start_clean(True)
    pm.load_preset(preset_path, smooth=False)
    pm.set_preset_start_clean(False)
    pm.lock_preset(True)

    frame_metrics: list[FrameMetrics] = []
    for frame_idx in range(profile.total_frames):
        t_sec = frame_idx * frame_dt
        pm.set_frame_time(t_sec)
        pm.feed_pcm(pcm.chunk(frame_idx, n_pcm), channels=pcm.channels)
        fbo.bind()
        pm.render_to_fbo(fbo.fbo_id)
        frame_metrics.append(
            sample_frame_metrics(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT)
        )

    failures = pm.drain_preset_failures()
    return PresetMetrics(
        path=preset_path,
        load_failed=bool(failures),
        error=failures[0].message if failures else None,
        fps=PROBE_FPS,
        frames=tuple(frame_metrics),
    )


def _probe_preset(
    pm: ProjectM,
    fbo: _ProbeFbo,
    target: PresetTarget,
    *,
    profile: ProbeProfile,
    pcm: ProbePcm,
    n_pcm: int,
    frame_dt: float,
) -> PresetScanResult:
    load_started = time.perf_counter()
    pm.drain_preset_failures()
    pm.set_preset_start_clean(True)
    pm.load_preset(target.path, smooth=False)
    pm.set_preset_start_clean(False)
    pm.lock_preset(True)
    load_sec = time.perf_counter() - load_started

    render_started = time.perf_counter()
    frame_metrics: list[FrameMetrics] = []

    for frame_idx in range(profile.total_frames):
        t_sec = frame_idx * frame_dt
        pm.set_frame_time(t_sec)
        pm.feed_pcm(pcm.chunk(frame_idx, n_pcm), channels=pcm.channels)
        fbo.bind()
        pm.render_to_fbo(fbo.fbo_id)
        frame_metrics.append(
            sample_frame_metrics(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT)
        )

    render_sec = time.perf_counter() - render_started
    warmup = profile.warmup_frames
    window = profile.window_frames
    window_frames = tuple(frame_metrics[warmup : warmup + window])
    peaks = peak_metrics(
        frame_metrics,
        warmup_frames=warmup,
        window_frames=window,
    )
    failures = pm.drain_preset_failures()
    category, error = classify_preset_result(
        failures,
        peaks,
        frames=window_frames,
    )

    return PresetScanResult(
        path=target.path,
        result=category,
        layers=target.layers,
        error=error,
        timings=PresetScanTimings(load_sec=load_sec, render_sec=render_sec),
        luma=peaks,
    )


def _synthetic_pcm_burst(frame_idx: int, n_samples: int) -> np.ndarray:
    """Mono PCM with energy every frame (sine plus light noise, never silence)."""
    if n_samples <= 0:
        return np.zeros(1, dtype=np.float32)

    t = np.arange(n_samples, dtype=np.float32) / SAMPLE_RATE_HZ
    freq = 440.0 + float(frame_idx % 7) * 55.0
    phase = float(frame_idx) * 0.41
    sine = (0.65 * np.sin(2.0 * math.pi * freq * t + phase)).astype(np.float32)
    rng = np.random.default_rng(frame_idx)
    noise = 0.12 * rng.standard_normal(n_samples).astype(np.float32)
    return np.clip(sine + noise, -1.0, 1.0).astype(np.float32)


def _gl_name(gen_fn, count: int = 1) -> int:
    names = gen_fn(count)
    try:
        return int(names[0])
    except (TypeError, IndexError):
        return int(names)


def create_probe_fbo(width: int, height: int) -> _ProbeFbo:
    """Create a minimal RGBA FBO for preset scan probes."""
    return _ProbeFbo(width, height)


class _ProbeFbo:
    """Minimal RGBA FBO for raw projectM probe output."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._texture_id = _gl_name(glGenTextures)
        self._depth_rbo_id = _gl_name(glGenRenderbuffers)
        self.fbo_id = _gl_name(glGenFramebuffers)

        glBindTexture(GL_TEXTURE_2D, self._texture_id)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA8,
            width,
            height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            None,
        )
        glBindRenderbuffer(GL_RENDERBUFFER, self._depth_rbo_id)
        glRenderbufferStorage(
            GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, width, height
        )

        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo_id)
        glFramebufferTexture2D(
            GL_FRAMEBUFFER,
            GL_COLOR_ATTACHMENT0,
            GL_TEXTURE_2D,
            self._texture_id,
            0,
        )
        glFramebufferRenderbuffer(
            GL_FRAMEBUFFER,
            GL_DEPTH_ATTACHMENT,
            GL_RENDERBUFFER,
            self._depth_rbo_id,
        )
        status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glBindRenderbuffer(GL_RENDERBUFFER, 0)
        glBindTexture(GL_TEXTURE_2D, 0)
        if status != GL_FRAMEBUFFER_COMPLETE:
            self.destroy()
            raise RuntimeError(
                f"probe FBO incomplete ({width}x{height}): status 0x{status:x}"
            )

    def bind(self) -> None:
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo_id)

    def destroy(self) -> None:
        if self._texture_id:
            glDeleteTextures(1, [self._texture_id])
            self._texture_id = 0
        if self._depth_rbo_id:
            glDeleteRenderbuffers(1, [self._depth_rbo_id])
            self._depth_rbo_id = 0
        if self.fbo_id:
            glDeleteFramebuffers(1, [self.fbo_id])
            self.fbo_id = 0


def _path_to_str(path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path)


def _path_is_inside_or_equal(child: Path, parent: Path) -> bool:
    child_resolved = child.resolve()
    parent_resolved = parent.resolve()
    if child_resolved == parent_resolved:
        return True
    try:
        child_resolved.relative_to(parent_resolved)
    except ValueError:
        return False
    return True


def _unique_quarantine_path(quarantine_dir: Path, filename: str) -> Path:
    candidate = quarantine_dir / filename
    if not candidate.exists():
        return candidate
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    index = 1
    while True:
        candidate = quarantine_dir / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _preset_result_from_dict(entry: Any) -> PresetScanResult:
    if not isinstance(entry, dict):
        raise ValueError("expected a JSON object")

    path_raw = entry.get("path")
    if not isinstance(path_raw, str) or not path_raw:
        raise ValueError("missing path")

    result_raw = entry.get("result")
    if result_raw not in ("load_failed", "black", "dim", "washed_out", "ok"):
        raise ValueError("missing or invalid result")

    layers_raw = entry.get("layers", [])
    if not isinstance(layers_raw, list) or not all(
        isinstance(layer, str) for layer in layers_raw
    ):
        raise ValueError("layers must be a string array")

    error_raw = entry.get("error")
    error = error_raw if isinstance(error_raw, str) else None

    timings: PresetScanTimings | None = None
    timings_raw = entry.get("timings")
    if timings_raw is not None:
        if not isinstance(timings_raw, dict):
            raise ValueError("timings must be an object")
        load_sec = timings_raw.get("load_sec")
        render_sec = timings_raw.get("render_sec")
        timings = PresetScanTimings(
            load_sec=float(load_sec) if load_sec is not None else None,
            render_sec=float(render_sec) if render_sec is not None else None,
        )

    luma = _scan_luma_from_dict(entry.get("luma"))

    return PresetScanResult(
        path=Path(path_raw).resolve(),
        result=result_raw,
        layers=tuple(layers_raw),
        error=error,
        timings=timings,
        luma=luma,
    )


def _scan_luma_from_dict(data: Any) -> FrameMetrics | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ValueError("luma must be an object")

    max_raw = data.get("max")
    mean_raw = data.get("mean")
    if not isinstance(max_raw, (int, float)) or not isinstance(mean_raw, (int, float)):
        raise ValueError("luma missing max or mean")

    coverage_raw = data.get("coverage")
    if not isinstance(coverage_raw, dict):
        raise ValueError("luma missing coverage object")

    coverage: dict[int, float] = {}
    for cutoff in LUMA_COVERAGE_CUTOFFS:
        value = coverage_raw.get(str(cutoff), coverage_raw.get(cutoff))
        if not isinstance(value, (int, float)):
            raise ValueError(f"luma missing coverage for cutoff {cutoff}")
        coverage[cutoff] = float(value)

    white_coverage_raw = data.get("white_coverage")
    white_coverage: dict[int, float] = {
        cutoff: 0.0 for cutoff in WHITE_COVERAGE_CUTOFFS
    }
    if white_coverage_raw is not None:
        if not isinstance(white_coverage_raw, dict):
            raise ValueError("luma white_coverage must be an object")
        for cutoff in WHITE_COVERAGE_CUTOFFS:
            value = white_coverage_raw.get(str(cutoff), white_coverage_raw.get(cutoff))
            if isinstance(value, (int, float)):
                white_coverage[cutoff] = float(value)

    return FrameMetrics(
        max_luma=float(max_raw),
        mean_luma=float(mean_raw),
        coverage=coverage,
        white_coverage=white_coverage,
    )


def _scan_luma_to_dict(luma: FrameMetrics) -> dict[str, Any]:
    return {
        "max": luma.max_luma,
        "mean": luma.mean_luma,
        "coverage": {
            str(cutoff): luma.coverage[cutoff] for cutoff in LUMA_COVERAGE_CUTOFFS
        },
        "white_coverage": {
            str(cutoff): luma.white_coverage[cutoff]
            for cutoff in WHITE_COVERAGE_CUTOFFS
        },
    }


def _preset_result_to_dict(preset: PresetScanResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": str(preset.path),
        "result": preset.result,
        "layers": list(preset.layers),
    }
    if preset.error is not None:
        payload["error"] = preset.error
    if preset.timings is not None:
        timings: dict[str, float] = {}
        if preset.timings.load_sec is not None:
            timings["load_sec"] = preset.timings.load_sec
        if preset.timings.render_sec is not None:
            timings["render_sec"] = preset.timings.render_sec
        if timings:
            payload["timings"] = timings
    if preset.luma is not None:
        payload["luma"] = _scan_luma_to_dict(preset.luma)
    return payload
