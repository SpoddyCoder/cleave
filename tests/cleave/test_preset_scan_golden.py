"""Unit tests for preset scan golden-set harness."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from cleave.preset_scan import (
    BLACK_COVERAGE,
    BLACK_MAX_LUMA,
    DIM_COVERAGE,
    DIM_MEAN_LUMA,
    QUICK_PROBE_WARMUP_FRAMES,
    QUICK_PROBE_WINDOW_FRAMES,
    SLOW_PROBE_WARMUP_FRAMES,
    SLOW_PROBE_WINDOW_FRAMES,
    scan_thresholds,
)
from cleave.preset_scan_golden import (
    DEFAULT_METRICS_CACHE_PATH,
    GOLDEN_CASE_COUNT,
    GoldenCase,
    GoldenSet,
    default_threshold_sweep_variants,
    evaluate,
    load_golden_set,
    load_metrics_cache,
    resolve_cache_probe_profile,
    resolve_eval_probe_window,
    scan_result_to_golden,
    sweep,
    _merge_threshold_variants,
)
from cleave.preset_scan_metrics import (
    METRICS_CACHE_VERSION,
    FrameMetrics,
    MetricsCache,
    PresetMetrics,
    LUMA_COVERAGE_CUTOFFS,
    WHITE_COVERAGE_CUTOFFS,
)
from cleave.paths import repo_root

FIXTURE_PATH = (
    repo_root() / "tests" / "fixtures" / "preset_scan_golden_set.yaml"
)


def _coverage(
    *,
    cutoff_16: float = 0.0,
    cutoff_192: float = 0.0,
) -> dict[int, float]:
    coverage = {cutoff: 0.0 for cutoff in LUMA_COVERAGE_CUTOFFS}
    coverage[16] = cutoff_16
    coverage[192] = cutoff_192
    return coverage


def _white_coverage(*, white_235: float = 0.0) -> dict[int, float]:
    white_coverage = {cutoff: 0.0 for cutoff in WHITE_COVERAGE_CUTOFFS}
    white_coverage[235] = white_235
    return white_coverage


def _frame(
    *,
    max_luma: float,
    mean_luma: float,
    cutoff_16: float = 0.0,
    cutoff_192: float = 0.0,
    white_235: float = 0.0,
) -> FrameMetrics:
    return FrameMetrics(
        max_luma=max_luma,
        mean_luma=mean_luma,
        coverage=_coverage(cutoff_16=cutoff_16, cutoff_192=cutoff_192),
        white_coverage=_white_coverage(white_235=white_235),
    )


def _mini_golden(tmp_path: Path) -> GoldenSet:
    preset_root = tmp_path / "presets"
    preset_root.mkdir()
    ok_path = preset_root / "ok.milk"
    dim_path = preset_root / "dim.milk"
    fail_path = preset_root / "fail.milk"
    ok_path.write_text("ok", encoding="utf-8")
    dim_path.write_text("dim", encoding="utf-8")
    fail_path.write_text("fail", encoding="utf-8")

    return GoldenSet(
        version=1,
        preset_root=preset_root,
        texture_paths=(tmp_path / "textures",),
        cases=(
            GoldenCase(id=1, preset=ok_path, expected_result="ok", notes=""),
            GoldenCase(id=2, preset=dim_path, expected_result="dim", notes=""),
            GoldenCase(id=3, preset=fail_path, expected_result="black", notes=""),
        ),
    )


def _mini_cache(golden: GoldenSet) -> MetricsCache:
    ok_path, dim_path, fail_path = (case.preset for case in golden.cases)
    healthy = _frame(max_luma=50.0, mean_luma=50.0, cutoff_16=0.5)
    dim = _frame(
        max_luma=BLACK_MAX_LUMA,
        mean_luma=DIM_MEAN_LUMA - 0.01,
        cutoff_16=DIM_COVERAGE - 0.001,
    )
    return MetricsCache(
        version=METRICS_CACHE_VERSION,
        probe_fps=30,
        fbo_size=(480, 270),
        probe_mode="quick",
        warmup_frames=0,
        window_frames=90,
        total_frames=90,
        presets=(
            PresetMetrics(
                path=ok_path,
                load_failed=False,
                error=None,
                fps=30,
                frames=(healthy,) * 90,
            ),
            PresetMetrics(
                path=dim_path,
                load_failed=False,
                error=None,
                fps=30,
                frames=(dim,) * 90,
            ),
            PresetMetrics(
                path=fail_path,
                load_failed=True,
                error="shader compile failed",
                fps=30,
                frames=(),
            ),
        ),
    )


def test_load_golden_set_parses_fixture() -> None:
    golden = load_golden_set(FIXTURE_PATH)

    assert golden.version == 1
    assert golden.preset_root == (repo_root() / "assets" / "milkdrop-presets").resolve()
    assert len(golden.texture_paths) == 1
    assert golden.texture_paths[0] == (
        repo_root() / "assets" / "milkdrop-presets" / "presets-milkdrop-texture-pack"
    ).resolve()
    assert len(golden.cases) == GOLDEN_CASE_COUNT
    assert golden.cases[0].id == 1
    assert golden.cases[-1].id == GOLDEN_CASE_COUNT
    assert golden.cases[0].preset.name == "BrainStain-Blackwidow.milk"
    assert golden.cases[0].expected_result == "dim"
    assert "Milkdrop-Original" in str(golden.cases[0].preset)


def test_load_golden_set_validates_case_count(tmp_path: Path) -> None:
    yaml_path = tmp_path / "golden.yaml"
    yaml_path.write_text(
        textwrap.dedent(
            """
            version: 1
            preset_root: /tmp/presets
            texture_paths:
              - /tmp/textures
            cases:
              - id: 1
                preset: a.milk
                expected_result: ok
            """
        ).strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must contain 50 cases"):
        load_golden_set(yaml_path)


def test_scan_result_to_golden_maps_load_failed() -> None:
    assert scan_result_to_golden("load_failed") == "black"
    assert scan_result_to_golden("ok") == "ok"


def test_evaluate_with_synthetic_cache(tmp_path: Path) -> None:
    golden = _mini_golden(tmp_path)
    cache = _mini_cache(golden)

    report = evaluate(
        cache,
        golden,
        warmup_frames=0,
        window_frames=90,
    )

    assert report.total == 3
    assert report.correct == 3
    assert report.accuracy == 1.0
    assert report.mismatches == ()


def test_evaluate_load_failed_counts_as_black(tmp_path: Path) -> None:
    golden = _mini_golden(tmp_path)
    cache = _mini_cache(golden)

    report = evaluate(cache, golden, warmup_frames=0, window_frames=90)

    assert report.confusion_matrix["black"]["black"] == 1
    mismatch_ids = {entry.id for entry in report.mismatches}
    assert 3 not in mismatch_ids


def test_evaluate_reports_mismatch(tmp_path: Path) -> None:
    golden = _mini_golden(tmp_path)
    cache = _mini_cache(golden)
    ok_path = golden.cases[0].preset
    blackish = _frame(
        max_luma=BLACK_MAX_LUMA - 0.01,
        mean_luma=0.0,
        cutoff_16=BLACK_COVERAGE - 0.0001,
    )
    patched = MetricsCache(
        version=cache.version,
        probe_fps=cache.probe_fps,
        fbo_size=cache.fbo_size,
        probe_mode=cache.probe_mode,
        warmup_frames=cache.warmup_frames,
        window_frames=cache.window_frames,
        total_frames=cache.total_frames,
        presets=(
            PresetMetrics(
                path=ok_path,
                load_failed=False,
                error=None,
                fps=30,
                frames=(blackish,) * 90,
            ),
            cache.presets[1],
            cache.presets[2],
        ),
    )

    report = evaluate(patched, golden, warmup_frames=0, window_frames=90)

    assert report.correct == 2
    assert len(report.mismatches) == 1
    assert report.mismatches[0].id == 1
    assert report.mismatches[0].expected == "ok"
    assert report.mismatches[0].actual == "black"


def test_sweep_returns_ranked_results(tmp_path: Path) -> None:
    golden = _mini_golden(tmp_path)
    cache = _mini_cache(golden)

    results = sweep(
        cache,
        golden,
        warmup_frames_values=(0,),
        window_frames_values=(90,),
        threshold_variants=(None,),
    )

    assert len(results) == 1
    assert results[0].accuracy == 1.0
    assert results[0].warmup_frames == 0
    assert results[0].window_frames == 90


def test_sweep_ranks_better_configs_first(tmp_path: Path) -> None:
    golden = _mini_golden(tmp_path)
    cache = _mini_cache(golden)

    results = sweep(
        cache,
        golden,
        warmup_frames_values=(0, 50),
        window_frames_values=(90,),
        threshold_variants=(None,),
    )

    assert len(results) == 2
    assert results[0].accuracy >= results[1].accuracy


def test_default_threshold_sweep_variants_quick_is_expanded() -> None:
    variants = default_threshold_sweep_variants("quick")
    assert variants[0] is None
    assert len(variants) > 100
    assert any(
        entry is not None and "washed_mean_peak" in entry for entry in variants
    )
    assert any(
        entry is not None and "dim_bob_cov_lo" in entry for entry in variants
    )


def test_default_threshold_sweep_variants_slow_covers_white_and_dim() -> None:
    variants = default_threshold_sweep_variants("slow")
    assert variants[0] is None
    assert len(variants) > 100
    assert any(
        entry is not None and "washed_mean_peak" in entry for entry in variants
    )
    assert all(
        entry is None or "dim_bob_cov_lo" not in entry for entry in variants
    )


def test_merge_threshold_variants_deduplicates() -> None:
    merged = _merge_threshold_variants(
        (None, {"white_area_frac": 0.6}),
        (None, {"white_area_frac": 0.6}, {"min_white_frame_frac": 0.3}),
    )
    assert merged == (None, {"white_area_frac": 0.6}, {"min_white_frame_frac": 0.3})


def test_evaluate_uses_cache_probe_profile() -> None:
    golden = load_golden_set(FIXTURE_PATH)
    ok_path = golden.cases[2].preset
    cache = MetricsCache(
        version=METRICS_CACHE_VERSION,
        probe_fps=30,
        fbo_size=(480, 270),
        probe_mode="slow",
        warmup_frames=SLOW_PROBE_WARMUP_FRAMES,
        window_frames=SLOW_PROBE_WINDOW_FRAMES,
        total_frames=SLOW_PROBE_WARMUP_FRAMES + SLOW_PROBE_WINDOW_FRAMES,
        presets=(
            PresetMetrics(
                path=ok_path,
                load_failed=False,
                error=None,
                fps=30,
                frames=(
                    _frame(max_luma=50.0, mean_luma=50.0, cutoff_16=0.5),
                )
                * (SLOW_PROBE_WARMUP_FRAMES + SLOW_PROBE_WINDOW_FRAMES),
            ),
        ),
    )
    mini = GoldenSet(
        version=1,
        preset_root=golden.preset_root,
        texture_paths=golden.texture_paths,
        cases=(golden.cases[2],),
    )

    report = evaluate(cache, mini)

    assert report.warmup_frames == SLOW_PROBE_WARMUP_FRAMES
    assert report.window_frames == SLOW_PROBE_WINDOW_FRAMES
    assert report.probe_mode == "slow"


def test_evaluate_uses_slow_thresholds_for_slow_cache(monkeypatch) -> None:
    golden = load_golden_set(FIXTURE_PATH)
    ok_path = golden.cases[2].preset
    cache = MetricsCache(
        version=METRICS_CACHE_VERSION,
        probe_fps=30,
        fbo_size=(480, 270),
        probe_mode="slow",
        warmup_frames=SLOW_PROBE_WARMUP_FRAMES,
        window_frames=SLOW_PROBE_WINDOW_FRAMES,
        total_frames=SLOW_PROBE_WARMUP_FRAMES + SLOW_PROBE_WINDOW_FRAMES,
        presets=(
            PresetMetrics(
                path=ok_path,
                load_failed=False,
                error=None,
                fps=30,
                frames=(
                    _frame(max_luma=50.0, mean_luma=50.0, cutoff_16=0.5),
                )
                * (SLOW_PROBE_WARMUP_FRAMES + SLOW_PROBE_WINDOW_FRAMES),
            ),
        ),
    )
    mini = GoldenSet(
        version=1,
        preset_root=golden.preset_root,
        texture_paths=golden.texture_paths,
        cases=(golden.cases[2],),
    )
    seen_modes: list[str] = []
    real_scan_thresholds = scan_thresholds

    def track_scan_thresholds(mode: str) -> dict[str, float]:
        seen_modes.append(mode)
        return real_scan_thresholds(mode)

    monkeypatch.setattr(
        "cleave.preset_scan.scan_thresholds",
        track_scan_thresholds,
    )

    evaluate(cache, mini)

    assert seen_modes == ["slow"]


def test_evaluate_rejects_profile_mismatch(tmp_path: Path) -> None:
    golden = _mini_golden(tmp_path)
    cache = _mini_cache(golden)

    with pytest.raises(ValueError, match="eval probe profile mismatch"):
        evaluate(cache, golden, warmup_frames=10, window_frames=90)


def test_resolve_cache_probe_profile_infers_quick_from_frame_count(tmp_path: Path) -> None:
    golden = _mini_golden(tmp_path)
    cache = MetricsCache(
        version=METRICS_CACHE_VERSION,
        probe_fps=30,
        fbo_size=(480, 270),
        presets=_mini_cache(golden).presets,
    )

    profile = resolve_cache_probe_profile(cache)

    assert profile.mode == "quick"
    assert profile.warmup_frames == QUICK_PROBE_WARMUP_FRAMES
    assert profile.window_frames == QUICK_PROBE_WINDOW_FRAMES


def test_resolve_eval_probe_window_uses_cache_by_default(tmp_path: Path) -> None:
    golden = _mini_golden(tmp_path)
    cache = _mini_cache(golden)

    warmup, window, profile = resolve_eval_probe_window(cache)

    assert warmup == 0
    assert window == 90
    assert profile.mode == "quick"


GOLDEN_CASE_2_ID = 2


def test_golden_case_2_not_washed_out_with_v3_cache() -> None:
    """Case 2: visualizer black; scan ok/black is accepted, not washed_out."""
    if not DEFAULT_METRICS_CACHE_PATH.is_file():
        pytest.skip("metrics cache not generated; run: cleave scan-golden --probe")

    golden = load_golden_set(FIXTURE_PATH)
    try:
        cache = load_metrics_cache(DEFAULT_METRICS_CACHE_PATH)
    except ValueError:
        pytest.skip("metrics cache outdated; run: cleave scan-golden --probe")
    if cache.version != METRICS_CACHE_VERSION:
        pytest.skip("metrics cache outdated; run: cleave scan-golden --probe")

    case_2 = next(case for case in golden.cases if case.id == GOLDEN_CASE_2_ID)
    assert case_2.expected_result == "black"
    mini = GoldenSet(
        version=golden.version,
        preset_root=golden.preset_root,
        texture_paths=golden.texture_paths,
        cases=(case_2,),
    )
    report = evaluate(cache, mini)

    mismatch = next(
        (entry for entry in report.mismatches if entry.id == GOLDEN_CASE_2_ID),
        None,
    )
    assert mismatch is None
