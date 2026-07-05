"""Golden-set harness for preset scan classifier tuning."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pygame
import yaml

from cleave.paths import repo_root
from cleave.preset_scan import (
    PROBE_FBO_HEIGHT,
    PROBE_FBO_WIDTH,
    PROBE_FPS,
    QUICK_PROBE_WARMUP_FRAMES,
    QUICK_PROBE_WINDOW_FRAMES,
    SLOW_PROBE_WARMUP_FRAMES,
    SLOW_PROBE_WINDOW_FRAMES,
    WHITE_CHANNEL_MIN,
    PresetResultCategory,
    ProbeMode,
    ProbeProfile,
    _configure_probe_projectm,
    build_probe_pcm,
    classify_preset_result,
    probe_preset_metrics,
    probe_profile,
    scan_thresholds,
)
from cleave.preset_scan_metrics import (
    METRICS_CACHE_VERSION,
    FrameMetrics,
    MetricsCache,
    PresetMetrics,
    load_metrics_cache,
    peak_metrics,
    white_frame_fraction,
    write_metrics_cache,
)
from cleave.projectm import PresetLoadFailure, ProjectM
from cleave.stem_pcm import samples_per_frame

GOLDEN_CASE_COUNT = 50
GoldenExpectedResult = Literal["ok", "dim", "black", "washed_out"]

DEFAULT_GOLDEN_SET_PATH = (
    repo_root() / "tests" / "fixtures" / "preset_scan_golden_set.yaml"
)
DEFAULT_METRICS_CACHE_PATH = (
    repo_root() / "tests" / "fixtures" / "preset_scan_golden_metrics.json"
)
DEFAULT_SLOW_METRICS_CACHE_PATH = (
    repo_root() / "tests" / "fixtures" / "preset_scan_golden_metrics_slow.json"
)

_VALID_EXPECTED: frozenset[str] = frozenset(("ok", "dim", "black", "washed_out"))


@dataclass(frozen=True)
class GoldenCase:
    id: int
    preset: Path
    expected_result: GoldenExpectedResult
    notes: str


@dataclass(frozen=True)
class GoldenSet:
    version: int
    preset_root: Path
    texture_paths: tuple[Path, ...]
    cases: tuple[GoldenCase, ...]


@dataclass(frozen=True)
class EvalMismatch:
    id: int
    preset_name: str
    expected: GoldenExpectedResult
    actual: PresetResultCategory
    luma: FrameMetrics | None
    white_frame_frac: float | None = None
    white_coverage_peak: float | None = None


@dataclass(frozen=True)
class EvalReport:
    total: int
    correct: int
    accuracy: float
    per_category_accuracy: dict[GoldenExpectedResult, float]
    confusion_matrix: dict[GoldenExpectedResult, dict[GoldenExpectedResult, int]]
    mismatches: tuple[EvalMismatch, ...]
    warmup_frames: int
    window_frames: int
    probe_mode: str


@dataclass(frozen=True)
class SweepResult:
    warmup_frames: int
    window_frames: int
    thresholds: dict[str, float] | None
    correct: int
    total: int
    accuracy: float


def load_golden_set(path: Path | None = None) -> GoldenSet:
    """Load and validate the golden-set YAML fixture."""
    resolved = (path or DEFAULT_GOLDEN_SET_PATH).expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"golden set not found: {resolved}")

    try:
        raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"malformed YAML: {exc}") from exc
    except OSError as exc:
        raise ValueError(str(exc)) from exc

    if not isinstance(raw, dict):
        raise ValueError("golden set root must be a mapping")

    version = raw.get("version")
    if not isinstance(version, int):
        raise ValueError("golden set missing version")

    preset_root_raw = raw.get("preset_root")
    if not isinstance(preset_root_raw, str) or not preset_root_raw:
        raise ValueError("golden set missing preset_root")
    preset_root = Path(preset_root_raw).expanduser().resolve()

    texture_paths_raw = raw.get("texture_paths")
    if not isinstance(texture_paths_raw, list) or not texture_paths_raw:
        raise ValueError("golden set missing texture_paths")
    texture_paths = tuple(
        Path(entry).expanduser().resolve()
        for entry in texture_paths_raw
        if isinstance(entry, str) and entry
    )
    if not texture_paths:
        raise ValueError("golden set missing texture_paths")

    cases_raw = raw.get("cases")
    if not isinstance(cases_raw, list):
        raise ValueError("golden set missing cases array")

    cases: list[GoldenCase] = []
    for index, entry in enumerate(cases_raw):
        if not isinstance(entry, dict):
            raise ValueError(f"case at index {index} must be a mapping")

        case_id = entry.get("id")
        if not isinstance(case_id, int):
            raise ValueError(f"case at index {index} missing id")

        preset_raw = entry.get("preset")
        if not isinstance(preset_raw, str) or not preset_raw:
            raise ValueError(f"case {case_id} missing preset")

        expected_raw = entry.get("expected_result")
        if expected_raw not in _VALID_EXPECTED:
            raise ValueError(f"case {case_id} missing or invalid expected_result")

        notes_raw = entry.get("notes", "")
        notes = notes_raw if isinstance(notes_raw, str) else ""

        preset_path = (preset_root / preset_raw).resolve()
        cases.append(
            GoldenCase(
                id=case_id,
                preset=preset_path,
                expected_result=expected_raw,
                notes=notes,
            )
        )

    if len(cases) != GOLDEN_CASE_COUNT:
        raise ValueError(
            f"golden set must contain {GOLDEN_CASE_COUNT} cases, got {len(cases)}"
        )

    seen_ids = {case.id for case in cases}
    expected_ids = set(range(1, GOLDEN_CASE_COUNT + 1))
    if seen_ids != expected_ids:
        missing = sorted(expected_ids - seen_ids)
        extra = sorted(seen_ids - expected_ids)
        parts: list[str] = []
        if missing:
            parts.append(f"missing ids: {missing}")
        if extra:
            parts.append(f"unexpected ids: {extra}")
        raise ValueError(f"golden set case ids invalid ({'; '.join(parts)})")

    cases_sorted = tuple(sorted(cases, key=lambda case: case.id))
    return GoldenSet(
        version=version,
        preset_root=preset_root,
        texture_paths=texture_paths,
        cases=cases_sorted,
    )


def probe_golden_set(
    golden: GoldenSet,
    cache_path: Path,
    *,
    slow: bool = False,
) -> MetricsCache:
    """GL probe every golden case; write full-frame metrics cache."""
    from cleave.preset_scan import create_probe_fbo

    profile = probe_profile(slow=slow)
    probe_pcm = build_probe_pcm(profile)
    texture_strs = [str(path) for path in golden.texture_paths]

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

    fbo = None
    presets: list[PresetMetrics] = []
    total = len(golden.cases)
    try:
        fbo = create_probe_fbo(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT)
        n_pcm = samples_per_frame(PROBE_FPS)
        frame_dt = 1.0 / PROBE_FPS

        for index, case in enumerate(golden.cases, start=1):
            _progress(f"Probing {index}/{total} {case.preset}...")
            pm = ProjectM()
            try:
                _configure_probe_projectm(pm, texture_strs)
                presets.append(
                    probe_preset_metrics(
                        pm,
                        fbo,
                        case.preset,
                        profile=profile,
                        pcm=probe_pcm,
                        n_pcm=n_pcm,
                        frame_dt=frame_dt,
                    )
                )
            finally:
                pm.destroy()
    finally:
        if fbo is not None:
            fbo.destroy()
        pygame.quit()

    cache = MetricsCache(
        version=METRICS_CACHE_VERSION,
        presets=tuple(presets),
        probe_fps=PROBE_FPS,
        fbo_size=(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT),
        probe_mode=profile.mode,
        warmup_frames=profile.warmup_frames,
        window_frames=profile.window_frames,
        total_frames=profile.total_frames,
    )
    write_metrics_cache(cache_path, cache)
    return cache


def format_probe_profile_summary(profile: ProbeProfile) -> str:
    return (
        f"{profile.mode}: {profile.warmup_frames} warmup + "
        f"{profile.window_frames} window, {profile.total_frames} frames"
    )


def resolve_cache_probe_profile(
    cache: MetricsCache,
    *,
    file: Any = None,
) -> ProbeProfile:
    """Return the probe profile stored in or inferred from a metrics cache."""
    if (
        cache.probe_mode is not None
        and cache.warmup_frames is not None
        and cache.window_frames is not None
    ):
        return ProbeProfile(
            warmup_frames=cache.warmup_frames,
            window_frames=cache.window_frames,
            mode=cache.probe_mode,
        )

    frame_counts = [len(entry.frames) for entry in cache.presets if entry.frames]
    if not frame_counts:
        raise ValueError("cannot infer probe profile from cache with no frame data")

    unique_counts = sorted(set(frame_counts))
    if len(unique_counts) != 1:
        raise ValueError(
            "cannot infer probe profile from cache with inconsistent frame counts: "
            + ", ".join(str(count) for count in unique_counts)
        )

    count = unique_counts[0]
    if count == QUICK_PROBE_WARMUP_FRAMES + QUICK_PROBE_WINDOW_FRAMES:
        profile = probe_profile(slow=False)
    elif count == SLOW_PROBE_WARMUP_FRAMES + SLOW_PROBE_WINDOW_FRAMES:
        profile = probe_profile(slow=True)
    else:
        raise ValueError(
            f"cannot infer probe profile from {count} cached frames per preset "
            f"(expected {QUICK_PROBE_WARMUP_FRAMES + QUICK_PROBE_WINDOW_FRAMES} "
            f"for quick or {SLOW_PROBE_WARMUP_FRAMES + SLOW_PROBE_WINDOW_FRAMES} for slow)"
        )

    out = file if file is not None else sys.stderr
    print(
        f"Warning: metrics cache v{cache.version} missing probe profile metadata; "
        f"inferred {format_probe_profile_summary(profile)} from frame count",
        file=out,
    )
    return profile


def resolve_eval_probe_window(
    cache: MetricsCache,
    *,
    warmup_frames: int | None = None,
    window_frames: int | None = None,
    strict: bool = True,
    file: Any = None,
) -> tuple[int, int, ProbeProfile]:
    """Resolve eval warmup/window from cache metadata, checking explicit overrides."""
    profile = resolve_cache_probe_profile(cache, file=file)
    cache_warmup = profile.warmup_frames
    cache_window = profile.window_frames

    resolved_warmup = cache_warmup if warmup_frames is None else warmup_frames
    resolved_window = cache_window if window_frames is None else window_frames

    if strict and (
        resolved_warmup != cache_warmup or resolved_window != cache_window
    ):
        raise ValueError(
            "eval probe profile mismatch: cache has "
            f"{format_probe_profile_summary(profile)}; "
            f"requested warmup={resolved_warmup} window={resolved_window}"
        )

    return resolved_warmup, resolved_window, profile


def evaluate(
    cache: MetricsCache,
    golden: GoldenSet,
    *,
    warmup_frames: int | None = None,
    window_frames: int | None = None,
    thresholds: dict[str, float] | None = None,
    strict_profile: bool = True,
    file: Any = None,
) -> EvalReport:
    """Classify cached metrics and compare to golden labels (GL-free)."""
    resolved_warmup, resolved_window, profile = resolve_eval_probe_window(
        cache,
        warmup_frames=warmup_frames,
        window_frames=window_frames,
        strict=strict_profile,
        file=file,
    )
    metrics_by_path = {entry.path.resolve(): entry for entry in cache.presets}
    mismatches: list[EvalMismatch] = []
    per_category_totals: dict[GoldenExpectedResult, int] = {
        label: 0 for label in _VALID_EXPECTED
    }
    per_category_correct: dict[GoldenExpectedResult, int] = {
        label: 0 for label in _VALID_EXPECTED
    }
    confusion: dict[GoldenExpectedResult, dict[GoldenExpectedResult, int]] = {
        expected: {actual: 0 for actual in _VALID_EXPECTED}
        for expected in _VALID_EXPECTED
    }

    correct = 0
    for case in golden.cases:
        preset_metrics = metrics_by_path.get(case.preset.resolve())
        if preset_metrics is None:
            raise ValueError(
                f"metrics cache missing preset for case {case.id}: {case.preset}"
            )

        actual, luma, white_frac, white_cov_peak = _classify_cached_preset(
            preset_metrics,
            warmup_frames=resolved_warmup,
            window_frames=resolved_window,
            probe_mode=profile.mode,
            thresholds=thresholds,
        )
        actual_golden = scan_result_to_golden(actual)

        per_category_totals[case.expected_result] += 1
        confusion[case.expected_result][actual_golden] += 1

        if actual_golden == case.expected_result:
            correct += 1
            per_category_correct[case.expected_result] += 1
        else:
            mismatches.append(
                EvalMismatch(
                    id=case.id,
                    preset_name=case.preset.name,
                    expected=case.expected_result,
                    actual=actual,
                    luma=luma,
                    white_frame_frac=white_frac,
                    white_coverage_peak=white_cov_peak,
                )
            )

    total = len(golden.cases)
    per_category_accuracy: dict[GoldenExpectedResult, float] = {}
    for label in _VALID_EXPECTED:
        count = per_category_totals[label]
        per_category_accuracy[label] = (
            per_category_correct[label] / count if count else 0.0
        )

    return EvalReport(
        total=total,
        correct=correct,
        accuracy=correct / total if total else 0.0,
        per_category_accuracy=per_category_accuracy,
        confusion_matrix=confusion,
        mismatches=tuple(mismatches),
        warmup_frames=resolved_warmup,
        window_frames=resolved_window,
        probe_mode=profile.mode,
    )


def default_threshold_sweep_variants(
    probe_mode: ProbeMode,
) -> tuple[dict[str, float] | None, ...]:
    """Default grid of white-detector knob overrides for sweep."""
    base = scan_thresholds(probe_mode)
    variants: list[dict[str, float] | None] = [None]
    for channel_min in (224.0, 235.0, 245.0):
        for area_frac in (0.5, 0.6, 0.7):
            for min_frac in (0.2, 0.3, 0.4):
                override = dict(base)
                override["white_channel_min"] = channel_min
                override["white_area_frac"] = area_frac
                override["min_white_frame_frac"] = min_frac
                variants.append(override)
    return tuple(variants)


def sweep(
    cache: MetricsCache,
    golden: GoldenSet,
    *,
    warmup_frames_values: tuple[int, ...] | None = None,
    window_frames_values: tuple[int, ...] | None = None,
    threshold_variants: tuple[dict[str, float] | None, ...] | None = None,
) -> list[SweepResult]:
    """Grid search over probe windows and thresholds; rank by golden agreement."""
    warmups = warmup_frames_values or (10, 15, 20)
    windows = window_frames_values or (60, 75)
    profile = resolve_cache_probe_profile(cache)
    threshold_sets = threshold_variants or default_threshold_sweep_variants(
        profile.mode
    )

    results: list[SweepResult] = []
    for warmup in warmups:
        for window in windows:
            for thresholds in threshold_sets:
                report = evaluate(
                    cache,
                    golden,
                    warmup_frames=warmup,
                    window_frames=window,
                    thresholds=thresholds,
                    strict_profile=False,
                )
                results.append(
                    SweepResult(
                        warmup_frames=warmup,
                        window_frames=window,
                        thresholds=thresholds,
                        correct=report.correct,
                        total=report.total,
                        accuracy=report.accuracy,
                    )
                )

    results.sort(
        key=lambda entry: (-entry.accuracy, -entry.correct, entry.warmup_frames, entry.window_frames)
    )
    return results


def print_eval_report(report: EvalReport, *, file: Any = None) -> None:
    """Print a human-readable evaluation summary to stderr."""
    out = file if file is not None else sys.stderr
    print(
        f"Golden eval: {report.correct}/{report.total} correct "
        f"({report.accuracy * 100:.1f}%) "
        f"[{report.probe_mode}: warmup={report.warmup_frames}, "
        f"window={report.window_frames}, "
        f"{report.warmup_frames + report.window_frames} frames]",
        file=out,
    )
    print("Per-category accuracy:", file=out)
    for label in ("ok", "dim", "black", "washed_out"):
        accuracy = report.per_category_accuracy[label]
        print(f"  {label}: {accuracy * 100:.1f}%", file=out)

    print("Confusion matrix (expected -> actual):", file=out)
    for expected in ("ok", "dim", "black", "washed_out"):
        row = report.confusion_matrix[expected]
        counts = ", ".join(f"{actual}={row[actual]}" for actual in row)
        print(f"  {expected}: {counts}", file=out)

    if report.mismatches:
        print(f"Mismatches ({len(report.mismatches)}):", file=out)
        for mismatch in report.mismatches:
            luma_bits = ""
            if mismatch.luma is not None:
                luma_bits = (
                    f" max={mismatch.luma.max_luma:.1f}"
                    f" mean={mismatch.luma.mean_luma:.1f}"
                    f" cov16={mismatch.luma.coverage.get(16, 0.0):.4f}"
                )
            white_bits = ""
            if mismatch.white_frame_frac is not None:
                white_bits = f" white_frac={mismatch.white_frame_frac:.3f}"
            if mismatch.white_coverage_peak is not None:
                white_bits += (
                    f" white_cov{int(WHITE_CHANNEL_MIN)}="
                    f"{mismatch.white_coverage_peak:.4f}"
                )
            print(
                f"  [{mismatch.id}] {mismatch.preset_name}: "
                f"expected={mismatch.expected} actual={mismatch.actual}"
                f"{luma_bits}{white_bits}",
                file=out,
            )


def scan_result_to_golden(result: PresetResultCategory) -> GoldenExpectedResult:
    """Map scan classifier output to golden label space."""
    if result == "load_failed":
        return "black"
    return result


def _classify_cached_preset(
    preset_metrics: PresetMetrics,
    *,
    warmup_frames: int,
    window_frames: int,
    probe_mode: ProbeMode,
    thresholds: dict[str, float] | None,
) -> tuple[PresetResultCategory, FrameMetrics | None, float | None, float | None]:
    failures: list[PresetLoadFailure] = []
    if preset_metrics.load_failed:
        failures = [
            PresetLoadFailure(
                filename=str(preset_metrics.path),
                message=preset_metrics.error or "load failed",
            )
        ]

    if not preset_metrics.frames:
        category, _ = classify_preset_result(
            failures, {}, probe_mode=probe_mode, thresholds=thresholds
        )
        return category, None, None, None

    window_slice = preset_metrics.frames[
        warmup_frames : warmup_frames + window_frames
    ]
    peaks = peak_metrics(
        preset_metrics.frames,
        warmup_frames=warmup_frames,
        window_frames=window_frames,
    )
    category, _ = classify_preset_result(
        failures,
        peaks,
        frames=window_slice,
        probe_mode=probe_mode,
        thresholds=thresholds,
    )
    th = scan_thresholds(probe_mode)
    if thresholds is not None:
        th.update(thresholds)
    white_frac = white_frame_fraction(
        window_slice,
        warmup_frames=0,
        window_frames=0,
        channel_min_cutoff=int(th["white_channel_min"]),
        area_frac=th["white_area_frac"],
    )
    white_cov_peak = (
        peaks.white_coverage.get(int(th["white_channel_min"]))
        if peaks.white_coverage
        else None
    )
    return category, peaks, white_frac, white_cov_peak


def _progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)
