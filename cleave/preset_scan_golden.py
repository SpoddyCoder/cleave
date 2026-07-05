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
    PresetResultCategory,
    classify_preset_result,
    probe_preset_metrics,
    probe_profile,
)
from cleave.preset_scan_metrics import (
    METRICS_CACHE_VERSION,
    FrameMetrics,
    MetricsCache,
    PresetMetrics,
    load_metrics_cache,
    peak_metrics,
    write_metrics_cache,
)
from cleave.projectm import PresetLoadFailure, ProjectM
from cleave.stem_pcm import samples_per_frame

GOLDEN_CASE_COUNT = 30
GoldenExpectedResult = Literal["ok", "dim", "black", "washed_out"]

DEFAULT_GOLDEN_SET_PATH = (
    repo_root() / "tests" / "fixtures" / "preset_scan_golden_set.yaml"
)
DEFAULT_METRICS_CACHE_PATH = (
    repo_root() / "tests" / "fixtures" / "preset_scan_golden_metrics.json"
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

    pm: ProjectM | None = None
    fbo = None
    presets: list[PresetMetrics] = []
    total = len(golden.cases)
    try:
        pm = ProjectM()
        pm.set_window_size(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT)
        pm.set_fps(PROBE_FPS)
        pm.set_hard_cut_enabled(False)
        pm.set_texture_paths(texture_strs)

        fbo = create_probe_fbo(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT)
        n_pcm = samples_per_frame(PROBE_FPS)
        frame_dt = 1.0 / PROBE_FPS

        for index, case in enumerate(golden.cases, start=1):
            _progress(f"Probing {index}/{total} {case.preset}...")
            presets.append(
                probe_preset_metrics(
                    pm,
                    fbo,
                    case.preset,
                    profile=profile,
                    n_pcm=n_pcm,
                    frame_dt=frame_dt,
                )
            )
    finally:
        if fbo is not None:
            fbo.destroy()
        if pm is not None:
            pm.destroy()
        pygame.quit()

    cache = MetricsCache(
        version=METRICS_CACHE_VERSION,
        presets=tuple(presets),
        probe_fps=PROBE_FPS,
        fbo_size=(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT),
    )
    write_metrics_cache(cache_path, cache)
    return cache


def evaluate(
    cache: MetricsCache,
    golden: GoldenSet,
    *,
    warmup_frames: int = QUICK_PROBE_WARMUP_FRAMES,
    window_frames: int = QUICK_PROBE_WINDOW_FRAMES,
    thresholds: dict[str, float] | None = None,
) -> EvalReport:
    """Classify cached metrics and compare to golden labels (GL-free)."""
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

        actual, luma = _classify_cached_preset(
            preset_metrics,
            warmup_frames=warmup_frames,
            window_frames=window_frames,
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
        warmup_frames=warmup_frames,
        window_frames=window_frames,
    )


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
    threshold_sets = threshold_variants or (None,)

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
        f"[warmup={report.warmup_frames}, window={report.window_frames}]",
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
            print(
                f"  [{mismatch.id}] {mismatch.preset_name}: "
                f"expected={mismatch.expected} actual={mismatch.actual}{luma_bits}",
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
    thresholds: dict[str, float] | None,
) -> tuple[PresetResultCategory, FrameMetrics | None]:
    failures: list[PresetLoadFailure] = []
    if preset_metrics.load_failed:
        failures = [
            PresetLoadFailure(
                filename=str(preset_metrics.path),
                message=preset_metrics.error or "load failed",
            )
        ]

    if not preset_metrics.frames:
        category, _ = classify_preset_result(failures, {}, thresholds=thresholds)
        return category, None

    peaks = peak_metrics(
        preset_metrics.frames,
        warmup_frames=warmup_frames,
        window_frames=window_frames,
    )
    category, _ = classify_preset_result(failures, peaks, thresholds=thresholds)
    return category, peaks


def _progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)
