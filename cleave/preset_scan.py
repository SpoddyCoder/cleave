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
    FrameMetrics,
    PresetMetrics,
    peak_metrics,
    sample_frame_metrics,
)
from cleave.preset_scan_targets import PresetTarget, ScanTargets
from cleave.projectm import PresetLoadFailure, ProjectM
from cleave.stem_pcm import samples_per_frame

ProbeMode = Literal["quick", "slow"]
ScanMode = Literal["project", "bulk"]
PresetResultCategory = Literal["load_failed", "black", "dim", "washed_out", "ok"]

QUICK_PROBE_WARMUP_FRAMES = 15
QUICK_PROBE_WINDOW_FRAMES = 75
SLOW_PROBE_WARMUP_FRAMES = 90
SLOW_PROBE_WINDOW_FRAMES = 60
PROBE_FPS = 30
PROBE_FBO_WIDTH = 480
PROBE_FBO_HEIGHT = 270

COVERAGE_LUMA_MIN = 16
WASHED_COVERAGE_CUTOFF = 192

BLACK_MAX_LUMA = 1.0
BLACK_COVERAGE = 0.0005
DIM_MEAN_LUMA = 10.0
DIM_COVERAGE = 0.01
WASHED_MEAN_LUMA = 200.0
WASHED_COVERAGE = 0.95
BRIGHT_ON_BLACK_MAX = 100.0
BRIGHT_ON_BLACK_COVERAGE = 0.02

SCAN_THRESHOLDS: dict[str, float] = {
    "black_max_luma": BLACK_MAX_LUMA,
    "black_coverage": BLACK_COVERAGE,
    "dim_mean_luma": DIM_MEAN_LUMA,
    "dim_coverage": DIM_COVERAGE,
    "washed_mean_luma": WASHED_MEAN_LUMA,
    "washed_coverage": WASHED_COVERAGE,
    "bright_on_black_max": BRIGHT_ON_BLACK_MAX,
    "bright_on_black_coverage": BRIGHT_ON_BLACK_COVERAGE,
    "coverage_luma_min": float(COVERAGE_LUMA_MIN),
}

REPORT_FLUSH_EVERY = 10

QUARANTINE_CATEGORIES: frozenset[PresetResultCategory] = frozenset(
    ("load_failed", "black", "dim", "washed_out")
)


@dataclass(frozen=True)
class ProbeProfile:
    warmup_frames: int
    window_frames: int
    mode: ProbeMode

    @property
    def total_frames(self) -> int:
        return self.warmup_frames + self.window_frames


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
    probe_mode: ProbeMode
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
    probe_mode: ProbeMode
    results: tuple[PresetScanResult, ...]
    skip_paths: frozenset[Path]
    complete: bool


def probe_profile(*, slow: bool = False) -> ProbeProfile:
    if slow:
        return ProbeProfile(
            warmup_frames=SLOW_PROBE_WARMUP_FRAMES,
            window_frames=SLOW_PROBE_WINDOW_FRAMES,
            mode="slow",
        )
    return ProbeProfile(
        warmup_frames=QUICK_PROBE_WARMUP_FRAMES,
        window_frames=QUICK_PROBE_WINDOW_FRAMES,
        mode="quick",
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


def classify_preset_result(
    failures: list[PresetLoadFailure],
    peaks: FrameMetrics | dict[str, Any],
    *,
    thresholds: dict[str, float] | None = None,
) -> tuple[PresetResultCategory, str | None]:
    if failures:
        return "load_failed", failures[0].message

    th = dict(SCAN_THRESHOLDS)
    if thresholds is not None:
        th.update(thresholds)

    black_max_luma = th["black_max_luma"]
    black_coverage = th["black_coverage"]
    dim_mean_luma = th["dim_mean_luma"]
    dim_coverage = th["dim_coverage"]
    washed_mean_luma = th["washed_mean_luma"]
    washed_coverage = th["washed_coverage"]
    bright_on_black_max = th["bright_on_black_max"]
    bright_on_black_coverage = th["bright_on_black_coverage"]
    coverage_luma_min = int(th["coverage_luma_min"])
    washed_coverage_cutoff = WASHED_COVERAGE_CUTOFF

    max_luma, mean_luma, coverage = _normalize_peak_metrics(peaks)
    cov_min = coverage[coverage_luma_min]
    cov_washed = coverage[washed_coverage_cutoff]

    if mean_luma >= washed_mean_luma and cov_washed >= washed_coverage:
        return "washed_out", None

    if max_luma < black_max_luma or cov_min < black_coverage:
        return "black", None

    if mean_luma < dim_mean_luma and cov_min < dim_coverage:
        if (
            max_luma >= bright_on_black_max
            and cov_min >= bright_on_black_coverage
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
        probe_mode=profile.mode,
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
        thresholds=dict(SCAN_THRESHOLDS),
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
    return {
        "scan_mode": report.scan_mode,
        "probe_mode": report.probe_mode,
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

    probe_mode = raw.get("probe_mode")
    if probe_mode not in ("quick", "slow"):
        raise ValueError("missing or invalid probe_mode")

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
        probe_mode=probe_mode,
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


def run_scan(
    targets: ScanTargets,
    *,
    slow: bool = False,
    texture_paths: tuple[Path, ...] | None = None,
    report_sink: Callable[[list[PresetScanResult], bool], None] | None = None,
    skip_paths: frozenset[Path] | None = None,
) -> list[PresetScanResult]:
    """Probe each preset in *targets* with a hidden GL context and one ProjectM."""
    profile = probe_profile(slow=slow)
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

    pm: ProjectM | None = None
    fbo: _ProbeFbo | None = None
    results: list[PresetScanResult] = []
    skip = skip_paths or frozenset()
    total = len(targets.presets)
    skip_count = len(skip)
    probed = 0
    resumed_announced = False
    try:
        pm = ProjectM()
        pm.set_window_size(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT)
        pm.set_fps(PROBE_FPS)
        pm.set_hard_cut_enabled(False)
        pm.set_texture_paths(texture_strs)

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
            result = _probe_preset(
                pm,
                fbo,
                target,
                profile=profile,
                n_pcm=n_pcm,
                frame_dt=frame_dt,
            )
            results.append(result)
            probed += 1
            if report_sink is not None and probed % REPORT_FLUSH_EVERY == 0:
                report_sink(results, False)

        if report_sink is not None:
            report_sink(results, True)
    except KeyboardInterrupt:
        if report_sink is not None:
            report_sink(results, False)
        raise
    finally:
        if fbo is not None:
            fbo.destroy()
        if pm is not None:
            pm.destroy()
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
        pm.feed_pcm(_synthetic_pcm_burst(frame_idx, n_pcm))
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
        pm.feed_pcm(_synthetic_pcm_burst(frame_idx, n_pcm))
        fbo.bind()
        pm.render_to_fbo(fbo.fbo_id)
        frame_metrics.append(
            sample_frame_metrics(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT)
        )

    render_sec = time.perf_counter() - render_started
    peaks = peak_metrics(
        frame_metrics,
        warmup_frames=profile.warmup_frames,
        window_frames=profile.window_frames,
    )
    failures = pm.drain_preset_failures()
    category, error = classify_preset_result(failures, peaks)

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

    return FrameMetrics(
        max_luma=float(max_raw),
        mean_luma=float(mean_raw),
        coverage=coverage,
    )


def _scan_luma_to_dict(luma: FrameMetrics) -> dict[str, Any]:
    return {
        "max": luma.max_luma,
        "mean": luma.mean_luma,
        "coverage": {
            str(cutoff): luma.coverage[cutoff] for cutoff in LUMA_COVERAGE_CUTOFFS
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
