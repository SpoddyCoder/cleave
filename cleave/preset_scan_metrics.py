"""Per-frame luma metrics and cache serialization for preset scan probes."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ProbeMode = Literal["quick", "slow"]

import numpy as np
from OpenGL.GL import GL_RGBA, GL_UNSIGNED_BYTE, glReadPixels

LUMA_COVERAGE_CUTOFFS: tuple[int, ...] = (8, 16, 32, 64, 128, 192)
WHITE_COVERAGE_CUTOFFS: tuple[int, ...] = (224, 235, 245)
METRICS_CACHE_VERSION = 3
SUPPORTED_METRICS_CACHE_VERSIONS: frozenset[int] = frozenset((3,))

_LUMA_R = 0.2126
_LUMA_G = 0.7152
_LUMA_B = 0.0722


@dataclass(frozen=True)
class FrameMetrics:
    max_luma: float
    mean_luma: float
    coverage: dict[int, float]
    white_coverage: dict[int, float]


@dataclass(frozen=True)
class PresetMetrics:
    path: Path
    load_failed: bool
    error: str | None
    fps: int
    frames: tuple[FrameMetrics, ...]


@dataclass(frozen=True)
class MetricsCache:
    version: int
    presets: tuple[PresetMetrics, ...]
    probe_fps: int
    fbo_size: tuple[int, int]
    probe_mode: ProbeMode | None = None
    warmup_frames: int | None = None
    window_frames: int | None = None
    total_frames: int | None = None


def empty_frame_metrics() -> FrameMetrics:
    return FrameMetrics(
        max_luma=0.0,
        mean_luma=0.0,
        coverage={cutoff: 0.0 for cutoff in LUMA_COVERAGE_CUTOFFS},
        white_coverage={cutoff: 0.0 for cutoff in WHITE_COVERAGE_CUTOFFS},
    )


def sample_frame_metrics(width: int, height: int) -> FrameMetrics:
    raw = glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE)
    rgba = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)
    r = rgba[..., 0].astype(np.float32)
    g = rgba[..., 1].astype(np.float32)
    b = rgba[..., 2].astype(np.float32)
    luma = _LUMA_R * r + _LUMA_G * g + _LUMA_B * b
    white = np.minimum(np.minimum(r, g), b)
    coverage = {
        cutoff: float((luma >= cutoff).mean()) for cutoff in LUMA_COVERAGE_CUTOFFS
    }
    white_coverage = {
        cutoff: float((white >= cutoff).mean()) for cutoff in WHITE_COVERAGE_CUTOFFS
    }
    return FrameMetrics(
        max_luma=float(luma.max()),
        mean_luma=float(luma.mean()),
        coverage=coverage,
        white_coverage=white_coverage,
    )


def peak_metrics(
    frames: list[FrameMetrics] | tuple[FrameMetrics, ...],
    *,
    warmup_frames: int,
    window_frames: int,
) -> FrameMetrics:
    if not frames:
        return empty_frame_metrics()

    start = max(0, warmup_frames)
    if window_frames <= 0:
        window = frames[start:]
    else:
        window = frames[start : start + window_frames]
    if not window:
        return empty_frame_metrics()

    return FrameMetrics(
        max_luma=max(frame.max_luma for frame in window),
        mean_luma=max(frame.mean_luma for frame in window),
        coverage={
            cutoff: max(frame.coverage[cutoff] for frame in window)
            for cutoff in LUMA_COVERAGE_CUTOFFS
        },
        white_coverage={
            cutoff: max(frame.white_coverage[cutoff] for frame in window)
            for cutoff in WHITE_COVERAGE_CUTOFFS
        },
    )


def white_frame_fraction(
    frames: list[FrameMetrics] | tuple[FrameMetrics, ...],
    *,
    warmup_frames: int,
    window_frames: int,
    channel_min_cutoff: int,
    area_frac: float,
) -> float:
    if not frames:
        return 0.0

    start = max(0, warmup_frames)
    if window_frames <= 0:
        window = frames[start:]
    else:
        window = frames[start : start + window_frames]
    if not window:
        return 0.0

    white_count = sum(
        1
        for frame in window
        if frame.white_coverage[channel_min_cutoff] >= area_frac
    )
    return white_count / len(window)


def frame_metrics_to_dict(metrics: FrameMetrics) -> dict[str, Any]:
    return {
        "max_luma": metrics.max_luma,
        "mean_luma": metrics.mean_luma,
        "coverage": {str(cutoff): metrics.coverage[cutoff] for cutoff in LUMA_COVERAGE_CUTOFFS},
        "white_coverage": {
            str(cutoff): metrics.white_coverage[cutoff]
            for cutoff in WHITE_COVERAGE_CUTOFFS
        },
    }


def frame_metrics_from_dict(data: Any) -> FrameMetrics:
    if not isinstance(data, dict):
        raise ValueError("frame metrics must be a JSON object")

    max_luma = data.get("max_luma")
    mean_luma = data.get("mean_luma")
    if not isinstance(max_luma, (int, float)) or not isinstance(mean_luma, (int, float)):
        raise ValueError("frame metrics missing max_luma or mean_luma")

    coverage_raw = data.get("coverage")
    if not isinstance(coverage_raw, dict):
        raise ValueError("frame metrics missing coverage object")

    coverage: dict[int, float] = {}
    for cutoff in LUMA_COVERAGE_CUTOFFS:
        value = coverage_raw.get(str(cutoff), coverage_raw.get(cutoff))
        if not isinstance(value, (int, float)):
            raise ValueError(f"frame metrics missing coverage for cutoff {cutoff}")
        coverage[cutoff] = float(value)

    white_coverage_raw = data.get("white_coverage")
    if not isinstance(white_coverage_raw, dict):
        raise ValueError("frame metrics missing white_coverage object")

    white_coverage: dict[int, float] = {}
    for cutoff in WHITE_COVERAGE_CUTOFFS:
        value = white_coverage_raw.get(str(cutoff), white_coverage_raw.get(cutoff))
        if not isinstance(value, (int, float)):
            raise ValueError(f"frame metrics missing white_coverage for cutoff {cutoff}")
        white_coverage[cutoff] = float(value)

    return FrameMetrics(
        max_luma=float(max_luma),
        mean_luma=float(mean_luma),
        coverage=coverage,
        white_coverage=white_coverage,
    )


def preset_metrics_to_dict(metrics: PresetMetrics) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": str(metrics.path),
        "load_failed": metrics.load_failed,
        "fps": metrics.fps,
        "frames": [frame_metrics_to_dict(frame) for frame in metrics.frames],
    }
    if metrics.error is not None:
        payload["error"] = metrics.error
    return payload


def preset_metrics_from_dict(data: Any) -> PresetMetrics:
    if not isinstance(data, dict):
        raise ValueError("preset metrics must be a JSON object")

    path_raw = data.get("path")
    if not isinstance(path_raw, str) or not path_raw:
        raise ValueError("preset metrics missing path")

    load_failed = data.get("load_failed")
    if not isinstance(load_failed, bool):
        raise ValueError("preset metrics missing load_failed")

    fps = data.get("fps")
    if not isinstance(fps, int):
        raise ValueError("preset metrics missing fps")

    frames_raw = data.get("frames")
    if not isinstance(frames_raw, list):
        raise ValueError("preset metrics missing frames array")

    error_raw = data.get("error")
    error = error_raw if isinstance(error_raw, str) else None

    frames = tuple(frame_metrics_from_dict(entry) for entry in frames_raw)
    return PresetMetrics(
        path=Path(path_raw).resolve(),
        load_failed=load_failed,
        error=error,
        fps=fps,
        frames=frames,
    )


def metrics_cache_to_dict(cache: MetricsCache) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": cache.version,
        "probe_fps": cache.probe_fps,
        "fbo_size": list(cache.fbo_size),
        "presets": [preset_metrics_to_dict(preset) for preset in cache.presets],
    }
    if cache.probe_mode is not None:
        payload["probe_mode"] = cache.probe_mode
    if cache.warmup_frames is not None:
        payload["warmup_frames"] = cache.warmup_frames
    if cache.window_frames is not None:
        payload["window_frames"] = cache.window_frames
    if cache.total_frames is not None:
        payload["total_frames"] = cache.total_frames
    return payload


def _optional_probe_mode(data: dict[str, Any]) -> ProbeMode | None:
    probe_mode = data.get("probe_mode")
    if probe_mode is None:
        return None
    if probe_mode not in ("quick", "slow"):
        raise ValueError(f"metrics cache has invalid probe_mode: {probe_mode!r}")
    return probe_mode


def _optional_int_field(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"metrics cache field {key!r} must be an integer")
    return value


def metrics_cache_from_dict(data: Any) -> MetricsCache:
    if not isinstance(data, dict):
        raise ValueError("metrics cache root must be a JSON object")

    version = data.get("version")
    if version not in SUPPORTED_METRICS_CACHE_VERSIONS:
        if version == 2:
            raise ValueError(
                f"metrics cache version {version} is stale (current is "
                f"{METRICS_CACHE_VERSION}); regenerate with "
                "cleave scan-golden --probe or cleave scan-golden --probe --slow"
            )
        raise ValueError(f"unsupported metrics cache version: {version!r}")

    probe_fps = data.get("probe_fps")
    if not isinstance(probe_fps, int):
        raise ValueError("metrics cache missing probe_fps")

    fbo_size_raw = data.get("fbo_size")
    if (
        not isinstance(fbo_size_raw, list)
        or len(fbo_size_raw) != 2
        or not all(isinstance(value, int) for value in fbo_size_raw)
    ):
        raise ValueError("metrics cache missing fbo_size")

    presets_raw = data.get("presets")
    if not isinstance(presets_raw, list):
        raise ValueError("metrics cache missing presets array")

    probe_mode = _optional_probe_mode(data)
    warmup_frames = _optional_int_field(data, "warmup_frames")
    window_frames = _optional_int_field(data, "window_frames")
    total_frames = _optional_int_field(data, "total_frames")

    if version == METRICS_CACHE_VERSION:
        missing = [
            name
            for name, value in (
                ("probe_mode", probe_mode),
                ("warmup_frames", warmup_frames),
                ("window_frames", window_frames),
                ("total_frames", total_frames),
            )
            if value is None
        ]
        if missing:
            raise ValueError(
                f"metrics cache v{METRICS_CACHE_VERSION} missing required fields: "
                + ", ".join(missing)
            )

    presets = tuple(preset_metrics_from_dict(entry) for entry in presets_raw)
    return MetricsCache(
        version=version,
        presets=presets,
        probe_fps=probe_fps,
        fbo_size=(fbo_size_raw[0], fbo_size_raw[1]),
        probe_mode=probe_mode,
        warmup_frames=warmup_frames,
        window_frames=window_frames,
        total_frames=total_frames,
    )


def write_metrics_cache(path: Path, cache: MetricsCache) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(metrics_cache_to_dict(cache), fh, indent=2)
            fh.write("\n")
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def load_metrics_cache(path: Path) -> MetricsCache:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"metrics cache not found: {resolved}")

    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON: {exc}") from exc
    except OSError as exc:
        raise ValueError(str(exc)) from exc

    return metrics_cache_from_dict(raw)
