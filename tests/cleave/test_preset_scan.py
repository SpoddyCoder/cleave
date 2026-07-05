"""Unit tests for preset scan profiles, classification, and reports."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from cleave.preset_scan import (
    BLACK_COVERAGE,
    BLACK_MAX_LUMA,
    BRIGHT_ON_BLACK_COVERAGE,
    BRIGHT_ON_BLACK_MAX,
    COVERAGE_LUMA_MIN,
    CAPPED_DIM_COV16,
    CAPPED_DIM_MAX_HI,
    CAPPED_DIM_MAX_LO,
    CAPPED_DIM_MEAN,
    DIM_COVERAGE,
    DIM_MEAN_LUMA,
    PROBE_FBO_HEIGHT,
    PROBE_FBO_WIDTH,
    PROBE_FPS,
    QUICK_PROBE_WARMUP_FRAMES,
    QUICK_PROBE_WINDOW_FRAMES,
    QUICK_SCAN_THRESHOLDS,
    REFERENCE_CLIP_PATH,
    REPORT_FLUSH_EVERY,
    SLOW_PROBE_WARMUP_FRAMES,
    SLOW_PROBE_WINDOW_FRAMES,
    SLOW_CAPPED_DIM_COV16,
    SLOW_CAPPED_DIM_MAX_HI,
    SLOW_CAPPED_DIM_MEAN,
    SLOW_SCAN_THRESHOLDS,
    SLOW_SPARSE_DIM_COV16_MAX,
    SLOW_SPARSE_DIM_COV16_MIN,
    SLOW_SPARSE_DIM_MAX,
    SLOW_SPARSE_DIM_MEAN,
    SLOW_VERY_SPARSE_DIM_COV16,
    SLOW_VERY_SPARSE_DIM_MAX,
    SLOW_VERY_SPARSE_DIM_MEAN,
    SPARSE_DIM_COV16_MAX,
    SPARSE_DIM_COV16_MIN,
    SPARSE_DIM_MAX,
    SPARSE_DIM_MEAN,
    WASHED_COVERAGE_CUTOFF,
    WASHED_COVERAGE_HIGH,
    WASHED_COVERAGE_MODERATE,
    WASHED_COV192_BROAD_MIN,
    WASHED_COV192_CAP,
    WASHED_COV128_MIN,
    WASHED_COV16_MIN,
    WASHED_MEAN_BROAD,
    WASHED_MEAN_HIGH,
    WASHED_MEAN_MID,
    WASHED_MEAN_MODERATE,
    PresetScanResult,
    PresetScanTimings,
    ProbePcm,
    ScanReport,
    build_probe_pcm,
    build_scan_report,
    classify_preset_result,
    delete_presets,
    existing_report_status,
    load_resume_results,
    probe_pcm_metadata,
    probe_profile,
    quarantine_presets,
    run_scan,
    scan_report_summary,
    scan_report_to_dict,
    scan_thresholds,
    validate_quarantine_dir,
    write_scan_report,
)
from cleave.preset_scan_metrics import LUMA_COVERAGE_CUTOFFS, FrameMetrics
from cleave.preset_scan_targets import PresetTarget, ScanTargets
from cleave.projectm import PresetLoadFailure


def _coverage_at(
    *,
    cutoff_16: float = 0.0,
    cutoff_128: float = 0.0,
    cutoff_192: float = 0.0,
) -> dict[int, float]:
    coverage = {cutoff: 0.0 for cutoff in LUMA_COVERAGE_CUTOFFS}
    coverage[COVERAGE_LUMA_MIN] = cutoff_16
    coverage[128] = cutoff_128
    coverage[WASHED_COVERAGE_CUTOFF] = cutoff_192
    return coverage


def _peaks(
    *,
    max_luma: float,
    mean_luma: float,
    cutoff_16: float = 0.0,
    cutoff_128: float = 0.0,
    cutoff_192: float = 0.0,
) -> FrameMetrics:
    return FrameMetrics(
        max_luma=max_luma,
        mean_luma=mean_luma,
        coverage=_coverage_at(
            cutoff_16=cutoff_16,
            cutoff_128=cutoff_128,
            cutoff_192=cutoff_192,
        ),
    )


def test_probe_profile_quick() -> None:
    profile = probe_profile(slow=False)
    assert profile.warmup_frames == QUICK_PROBE_WARMUP_FRAMES
    assert profile.window_frames == QUICK_PROBE_WINDOW_FRAMES
    assert profile.total_frames == 90
    assert profile.mode == "quick"


def test_probe_profile_slow() -> None:
    profile = probe_profile(slow=True)
    assert profile.warmup_frames == SLOW_PROBE_WARMUP_FRAMES
    assert profile.window_frames == SLOW_PROBE_WINDOW_FRAMES
    assert profile.total_frames == 300
    assert profile.mode == "slow"


_TUNED_SLOW_ONLY_KEYS = frozenset(
    {
        "very_sparse_dim_cov16",
        "sparse_dim_cov16_min",
        "sparse_dim_cov16_max",
        "capped_dim_mean",
        "capped_dim_max_hi",
        "capped_dim_cov16",
        "washed_mean_high",
        "washed_coverage_high_max",
        "washed_coverage_moderate",
        "washed_mean_mid",
        "washed_mean_broad",
        "washed_cov192_cap",
    }
)


def test_scan_thresholds_quick_vs_slow() -> None:
    quick = scan_thresholds("quick")
    slow = scan_thresholds("slow")
    assert quick == QUICK_SCAN_THRESHOLDS
    assert slow == SLOW_SCAN_THRESHOLDS
    differing = {
        key
        for key in QUICK_SCAN_THRESHOLDS
        if quick[key] != slow[key]
    }
    assert _TUNED_SLOW_ONLY_KEYS <= differing
    for key in _TUNED_SLOW_ONLY_KEYS:
        assert quick[key] != slow[key]


def test_build_scan_report_uses_mode_thresholds() -> None:
    targets = ScanTargets(presets=())
    quick_report = build_scan_report(
        scan_mode="bulk",
        profile=probe_profile(slow=False),
        targets=targets,
        results=(),
    )
    slow_report = build_scan_report(
        scan_mode="bulk",
        profile=probe_profile(slow=True),
        targets=targets,
        results=(),
    )
    assert quick_report.thresholds == QUICK_SCAN_THRESHOLDS
    assert slow_report.thresholds == SLOW_SCAN_THRESHOLDS


def test_classify_preset_result_load_failed() -> None:
    failures = [
        PresetLoadFailure(filename="/tmp/a.milk", message="shader error"),
        PresetLoadFailure(filename="/tmp/b.milk", message="later"),
    ]
    result, error = classify_preset_result(
        failures, _peaks(max_luma=100.0, mean_luma=100.0, cutoff_16=0.5)
    )
    assert result == "load_failed"
    assert error == "shader error"


def test_classify_preset_result_black_low_max() -> None:
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=BLACK_MAX_LUMA - 0.01,
            mean_luma=0.0,
            cutoff_16=0.5,
        ),
    )
    assert result == "black"
    assert error is None


def test_classify_preset_result_black_low_coverage() -> None:
    result, error = classify_preset_result(
        [],
        _peaks(max_luma=50.0, mean_luma=25.0, cutoff_16=BLACK_COVERAGE - 0.0001),
    )
    assert result == "black"
    assert error is None


def test_classify_preset_result_black_boundary_not_black() -> None:
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=BLACK_MAX_LUMA,
            mean_luma=0.0,
            cutoff_16=BLACK_COVERAGE,
        ),
    )
    assert result == "dim"
    assert error is None


def test_classify_preset_result_dim() -> None:
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=BLACK_MAX_LUMA,
            mean_luma=DIM_MEAN_LUMA - 0.01,
            cutoff_16=DIM_COVERAGE - 0.001,
        ),
    )
    assert result == "dim"
    assert error is None


def test_classify_preset_result_dim_boundary_ok() -> None:
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=BLACK_MAX_LUMA,
            mean_luma=DIM_MEAN_LUMA,
            cutoff_16=DIM_COVERAGE,
        ),
    )
    assert result == "ok"
    assert error is None


def test_classify_preset_result_bright_on_black_guard() -> None:
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=BRIGHT_ON_BLACK_MAX,
            mean_luma=DIM_MEAN_LUMA - 1.0,
            cutoff_16=BRIGHT_ON_BLACK_COVERAGE,
        ),
    )
    assert result == "ok"
    assert error is None


def test_classify_preset_result_washed_out_high() -> None:
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=255.0,
            mean_luma=WASHED_MEAN_HIGH,
            cutoff_16=1.0,
            cutoff_192=WASHED_COVERAGE_HIGH + 0.03,
        ),
    )
    assert result == "washed_out"
    assert error is None


def test_classify_preset_result_bright_ok_not_washed_out() -> None:
    """Bright usable presets can saturate cov192 without being washed_out."""
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=255.0,
            mean_luma=WASHED_MEAN_HIGH - 9.0,
            cutoff_16=1.0,
            cutoff_192=1.0,
        ),
    )
    assert result == "ok"
    assert error is None


def test_classify_preset_result_washed_out_mid() -> None:
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=240.0,
            mean_luma=WASHED_MEAN_MID,
            cutoff_16=0.99,
            cutoff_192=WASHED_COV192_CAP,
        ),
    )
    assert result == "washed_out"
    assert error is None


def test_classify_preset_result_washed_out_moderate() -> None:
    """High mean with partial cov192 blowout (golden case 2 mid-wash path)."""
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=255.0,
            mean_luma=229.3,
            cutoff_16=0.9941,
            cutoff_192=WASHED_COV192_CAP - 0.01,
        ),
    )
    assert result == "washed_out"
    assert error is None


def test_classify_preset_result_moderate_wash_boundary_ok() -> None:
    """Below moderate mean stays ok even with high cov192."""
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=255.0,
            mean_luma=WASHED_MEAN_MODERATE - 1.0,
            cutoff_16=1.0,
            cutoff_192=WASHED_COVERAGE_MODERATE + 0.03,
        ),
    )
    assert result == "ok"
    assert error is None


def test_classify_preset_result_washed_out_broad() -> None:
    """High cov128 with moderate cov192 blowout (golden case 5)."""
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=255.0,
            mean_luma=WASHED_MEAN_BROAD + 7.4,
            cutoff_16=WASHED_COV16_MIN,
            cutoff_128=WASHED_COV128_MIN,
            cutoff_192=WASHED_COV192_BROAD_MIN + 0.07,
        ),
    )
    assert result == "washed_out"
    assert error is None


def test_classify_preset_result_broad_wash_boundary_ok() -> None:
    """Partial cov128 saturation stays ok below broad wash thresholds."""
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=255.0,
            mean_luma=WASHED_MEAN_MID - 5.0,
            cutoff_16=WASHED_COV16_MIN,
            cutoff_128=WASHED_COV128_MIN - 0.13,
            cutoff_192=WASHED_COV192_BROAD_MIN + 0.17,
        ),
    )
    assert result == "ok"
    assert error is None


def test_classify_preset_result_capped_dim_max_hi_boundary_ok() -> None:
    """Healthy mid-max presets stay ok above capped dim max (golden case 7)."""
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=CAPPED_DIM_MAX_HI + 3.3,
            mean_luma=DIM_MEAN_LUMA - 0.6,
            cutoff_16=CAPPED_DIM_COV16 + 0.0172,
        ),
    )
    assert result == "ok"
    assert error is None


def test_classify_preset_result_capped_dim_below_max_hi() -> None:
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=CAPPED_DIM_MAX_HI - 3.4,
            mean_luma=CAPPED_DIM_MEAN - 1.1,
            cutoff_16=CAPPED_DIM_COV16 + 0.6342,
        ),
    )
    assert result == "dim"
    assert error is None


def test_classify_preset_result_sparse_dim() -> None:
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=SPARSE_DIM_MAX + 20.0,
            mean_luma=SPARSE_DIM_MEAN - 2.0,
            cutoff_16=(SPARSE_DIM_COV16_MIN + SPARSE_DIM_COV16_MAX) / 2.0,
        ),
    )
    assert result == "dim"
    assert error is None


def test_classify_preset_result_black_flash_guard() -> None:
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=BRIGHT_ON_BLACK_MAX + 50.0,
            mean_luma=0.0,
            cutoff_16=BRIGHT_ON_BLACK_COVERAGE,
        ),
    )
    assert result == "ok"
    assert error is None


def test_classify_preset_result_slow_very_sparse_dim_boundary_ok() -> None:
    """Slow golden case 15: sparse peaks stay ok below very_sparse cov16."""
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=SLOW_VERY_SPARSE_DIM_MAX + 134.7,
            mean_luma=SLOW_VERY_SPARSE_DIM_MEAN - 4.2,
            cutoff_16=SLOW_VERY_SPARSE_DIM_COV16 - 0.0009,
        ),
        probe_mode="slow",
    )
    assert result == "ok"
    assert error is None


def test_classify_preset_result_slow_sparse_dim() -> None:
    """Slow golden case 1: mid-coverage sparse dim band."""
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=SLOW_SPARSE_DIM_MAX + 38.9,
            mean_luma=SLOW_SPARSE_DIM_MEAN - 0.3,
            cutoff_16=(SLOW_SPARSE_DIM_COV16_MIN + SLOW_SPARSE_DIM_COV16_MAX) / 2.0,
        ),
        probe_mode="slow",
    )
    assert result == "dim"
    assert error is None


def test_classify_preset_result_slow_capped_dim() -> None:
    """Slow golden case 30: high coverage with capped mean luma."""
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=SLOW_CAPPED_DIM_MAX_HI - 1.0,
            mean_luma=SLOW_CAPPED_DIM_MEAN - 0.5,
            cutoff_16=SLOW_CAPPED_DIM_COV16 + 0.96,
        ),
        probe_mode="slow",
    )
    assert result == "dim"
    assert error is None


def test_classify_preset_result_slow_capped_dim_max_hi_boundary_ok() -> None:
    """Slow presets above capped max_hi stay ok."""
    result, error = classify_preset_result(
        [],
        _peaks(
            max_luma=SLOW_CAPPED_DIM_MAX_HI + 0.1,
            mean_luma=SLOW_CAPPED_DIM_MEAN - 0.5,
            cutoff_16=SLOW_CAPPED_DIM_COV16 + 0.96,
        ),
        probe_mode="slow",
    )
    assert result == "ok"
    assert error is None


def test_classify_preset_result_ok() -> None:
    result, error = classify_preset_result(
        [],
        _peaks(max_luma=50.0, mean_luma=50.0, cutoff_16=0.5),
    )
    assert result == "ok"
    assert error is None


def test_classify_preset_result_accepts_metrics_dict() -> None:
    result, error = classify_preset_result(
        [],
        {
            "max_luma": 50.0,
            "mean_luma": 50.0,
            "coverage": _coverage_at(cutoff_16=0.5),
        },
    )
    assert result == "ok"
    assert error is None


def test_synthetic_pcm_burst_never_silence() -> None:
    from cleave.preset_scan import _synthetic_pcm_burst

    for frame_idx in range(8):
        pcm = _synthetic_pcm_burst(frame_idx, 1470)
        assert pcm.size > 0
        assert float(np.max(np.abs(pcm))) > 0.01


def test_build_scan_report_project_mode() -> None:
    project_dir = Path("/tmp/project")
    config_path = project_dir / "cleave-viz.yaml"
    preset_root = project_dir / "presets"
    texture_path = project_dir / "textures"
    preset_path = preset_root / "pack" / "a.milk"
    anchor_dir = preset_root / "pack"

    targets = ScanTargets(
        presets=(PresetTarget(path=preset_path, layers=("layer_1",)),),
        preset_root=preset_root,
        texture_paths=(texture_path,),
        layer_sources={"layer_1": (anchor_dir,)},
    )
    results = [
        PresetScanResult(
            path=preset_path,
            result="ok",
            layers=("layer_1",),
            timings=PresetScanTimings(load_sec=0.1, render_sec=0.5),
        ),
        PresetScanResult(
            path=preset_root / "pack" / "b.milk",
            result="black",
            layers=("layer_1",),
            error=None,
        ),
    ]
    report = build_scan_report(
        scan_mode="project",
        profile=probe_profile(slow=False),
        targets=targets,
        results=results,
        project_dir=project_dir,
        config_path=config_path,
    )

    assert report.scan_mode == "project"
    assert report.probe_mode == "quick"
    assert report.project_dir == project_dir.resolve()
    assert report.config_path == config_path.resolve()
    assert report.presets_dir is None
    assert report.preset_root == preset_root.resolve()
    assert report.texture_paths == (texture_path.resolve(),)
    assert report.layers == {"layer_1": [str(anchor_dir)]}
    assert report.probe_frames == QUICK_PROBE_WARMUP_FRAMES + QUICK_PROBE_WINDOW_FRAMES
    assert report.probe_fps == PROBE_FPS
    assert report.fbo_size == (PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT)
    assert report.pcm_source == "synthetic"
    assert report.pcm_channels == 1
    assert report.reference_clip_path is None
    assert len(report.presets) == 2

    summary = scan_report_summary(report)
    assert summary == {
        "total": 2,
        "load_failed": 0,
        "black": 1,
        "dim": 0,
        "washed_out": 0,
        "ok": 1,
    }


def test_build_scan_report_bulk_mode() -> None:
    presets_dir = Path("/tmp/presets-pack")
    targets = ScanTargets(
        presets=(PresetTarget(path=presets_dir / "a.milk", layers=()),),
        presets_dir=presets_dir,
    )
    report = build_scan_report(
        scan_mode="bulk",
        profile=probe_profile(slow=True),
        targets=targets,
        results=[
            PresetScanResult(
                path=presets_dir / "a.milk",
                result="load_failed",
                layers=(),
                error="parse error",
            ),
        ],
    )

    assert report.scan_mode == "bulk"
    assert report.probe_mode == "slow"
    assert report.pcm_source == "reference-clip"
    assert report.pcm_channels == 2
    assert report.reference_clip_path == REFERENCE_CLIP_PATH.resolve()
    assert report.project_dir is None
    assert report.config_path is None
    assert report.presets_dir == presets_dir.resolve()
    assert report.preset_root is None
    assert report.texture_paths == ()
    assert report.layers == {}


def test_scan_report_serialization_round_trip() -> None:
    preset_path = Path("/tmp/presets/a.milk")
    report = ScanReport(
        scan_mode="project",
        probe_mode="quick",
        project_dir=Path("/tmp/project"),
        config_path=Path("/tmp/project/cleave-viz.yaml"),
        presets_dir=None,
        preset_root=Path("/tmp/presets"),
        texture_paths=(Path("/tmp/textures"),),
        layers={"layer_1": ["/tmp/presets/pack"]},
        thresholds=dict(QUICK_SCAN_THRESHOLDS),
        probe_frames=QUICK_PROBE_WARMUP_FRAMES + QUICK_PROBE_WINDOW_FRAMES,
        probe_fps=PROBE_FPS,
        fbo_size=(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT),
        pcm_source="synthetic",
        pcm_channels=1,
        reference_clip_path=None,
        presets=(
            PresetScanResult(
                path=preset_path,
                result="ok",
                layers=("layer_1",),
            ),
        ),
    )

    payload = scan_report_to_dict(report)
    assert payload["scan_mode"] == "project"
    assert payload["probe_mode"] == "quick"
    assert payload["project_dir"] == "/tmp/project"
    assert payload["config_path"] == "/tmp/project/cleave-viz.yaml"
    assert payload["presets_dir"] is None
    assert payload["preset_root"] == "/tmp/presets"
    assert payload["texture_paths"] == ["/tmp/textures"]
    assert payload["layers"] == {"layer_1": ["/tmp/presets/pack"]}
    assert payload["thresholds"] == QUICK_SCAN_THRESHOLDS
    assert payload["probe_frames"] == QUICK_PROBE_WARMUP_FRAMES + QUICK_PROBE_WINDOW_FRAMES
    assert payload["probe_fps"] == PROBE_FPS
    assert payload["fbo_size"] == [PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT]
    assert payload["pcm_source"] == "synthetic"
    assert payload["pcm_channels"] == 1
    assert "reference_clip_path" not in payload
    assert payload["presets"] == [
        {
            "path": str(preset_path),
            "result": "ok",
            "layers": ["layer_1"],
        },
    ]
    assert payload["summary"] == {
        "total": 1,
        "load_failed": 0,
        "black": 0,
        "dim": 0,
        "washed_out": 0,
        "ok": 1,
    }
    assert payload["complete"] is True

    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / "scan-report.json"
        write_scan_report(report_path, report)
        loaded = json.loads(report_path.read_text(encoding="utf-8"))
        assert loaded == payload


def test_build_scan_report_complete_flag() -> None:
    targets = ScanTargets(presets=())
    partial = build_scan_report(
        scan_mode="bulk",
        profile=probe_profile(slow=False),
        targets=targets,
        results=(),
        complete=False,
    )
    assert partial.complete is False
    assert scan_report_to_dict(partial)["complete"] is False


def test_write_scan_report_atomic_round_trip() -> None:
    report = ScanReport(
        scan_mode="bulk",
        probe_mode="quick",
        project_dir=None,
        config_path=None,
        presets_dir=Path("/tmp/presets"),
        preset_root=None,
        texture_paths=(),
        layers={},
        thresholds=dict(QUICK_SCAN_THRESHOLDS),
        probe_frames=QUICK_PROBE_WARMUP_FRAMES + QUICK_PROBE_WINDOW_FRAMES,
        probe_fps=PROBE_FPS,
        fbo_size=(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT),
        pcm_source="synthetic",
        pcm_channels=1,
        reference_clip_path=None,
        presets=(),
        complete=False,
    )

    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / "nested" / "scan.json"
        write_scan_report(report_path, report)
        assert not any(report_path.parent.glob("*.tmp"))
        loaded = json.loads(report_path.read_text(encoding="utf-8"))
        assert loaded["complete"] is False
        assert loaded["scan_mode"] == "bulk"


def test_load_resume_results_valid() -> None:
    preset_path = Path("/tmp/presets/a.milk").resolve()
    payload = {
        "scan_mode": "project",
        "probe_mode": "slow",
        "presets": [
            {
                "path": str(preset_path),
                "result": "ok",
                "layers": ["layer_1"],
                "timings": {"load_sec": 0.1, "render_sec": 0.5},
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / "resume.json"
        report_path.write_text(json.dumps(payload), encoding="utf-8")
        resume = load_resume_results(report_path)

    assert resume.scan_mode == "project"
    assert resume.probe_mode == "slow"
    assert len(resume.results) == 1
    assert resume.results[0].path == preset_path
    assert resume.results[0].result == "ok"
    assert resume.results[0].layers == ("layer_1",)
    assert resume.skip_paths == frozenset({preset_path})
    assert resume.complete is True


def test_load_resume_results_incomplete_flag() -> None:
    preset_path = Path("/tmp/presets/a.milk").resolve()
    payload = {
        "scan_mode": "bulk",
        "probe_mode": "quick",
        "complete": False,
        "presets": [{"path": str(preset_path), "result": "ok", "layers": []}],
    }

    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / "resume.json"
        report_path.write_text(json.dumps(payload), encoding="utf-8")
        resume = load_resume_results(report_path)

    assert resume.complete is False


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"probe_mode": "quick", "presets": []}, "scan_mode"),
        ({"scan_mode": "bulk", "presets": []}, "probe_mode"),
        ({"scan_mode": "bulk", "probe_mode": "quick"}, "presets"),
        (
            {
                "scan_mode": "bulk",
                "probe_mode": "quick",
                "presets": [{"result": "ok", "layers": []}],
            },
            "path",
        ),
    ],
)
def test_load_resume_results_malformed(
    payload: dict, message: str, tmp_path: Path
) -> None:
    report_path = tmp_path / "resume.json"
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_resume_results(report_path)


def test_load_resume_results_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(ValueError, match="resume report not found"):
        load_resume_results(missing)


def test_load_resume_results_invalid_json(tmp_path: Path) -> None:
    report_path = tmp_path / "resume.json"
    report_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed JSON"):
        load_resume_results(report_path)


def test_validate_quarantine_dir_creates_missing(tmp_path: Path) -> None:
    scanned = tmp_path / "presets"
    scanned.mkdir()
    quarantine = tmp_path / "quarantine"

    resolved = validate_quarantine_dir(quarantine, (scanned,))
    assert resolved == quarantine.resolve()
    assert quarantine.is_dir()


def test_validate_quarantine_dir_rejects_file(tmp_path: Path) -> None:
    scanned = tmp_path / "presets"
    scanned.mkdir()
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError, match="not a directory"):
        validate_quarantine_dir(blocker, (scanned,))


def test_validate_quarantine_dir_rejects_inside_scanned(tmp_path: Path) -> None:
    scanned = tmp_path / "presets"
    scanned.mkdir()
    inside = scanned / "quarantine"

    with pytest.raises(ValueError, match="outside the scanned presets directory"):
        validate_quarantine_dir(inside, (scanned,))


def test_quarantine_presets_moves_washed_out(tmp_path: Path) -> None:
    presets_dir = tmp_path / "presets"
    presets_dir.mkdir()
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir()

    washed_path = presets_dir / "washed.milk"
    washed_path.write_text("washed", encoding="utf-8")

    moves = quarantine_presets(
        [PresetScanResult(path=washed_path, result="washed_out", layers=())],
        quarantine_dir,
    )

    assert not washed_path.exists()
    assert (quarantine_dir / "washed.milk").is_file()
    assert len(moves) == 1


def test_quarantine_presets_moves_failures_flat(tmp_path: Path) -> None:
    presets_dir = tmp_path / "presets"
    presets_dir.mkdir()
    quarantine_dir = tmp_path / "quarantine"
    quarantine_dir.mkdir()

    ok_path = presets_dir / "good.milk"
    bad_path = presets_dir / "bad.milk"
    dup_path = presets_dir / "dup.milk"
    ok_path.write_text("ok", encoding="utf-8")
    bad_path.write_text("bad", encoding="utf-8")
    dup_path.write_text("dup", encoding="utf-8")
    (quarantine_dir / "dup.milk").write_text("existing", encoding="utf-8")

    results = [
        PresetScanResult(path=ok_path, result="ok", layers=()),
        PresetScanResult(path=bad_path, result="black", layers=()),
        PresetScanResult(path=dup_path, result="dim", layers=()),
    ]
    moves = quarantine_presets(results, quarantine_dir)

    assert ok_path.is_file()
    assert not bad_path.exists()
    assert not dup_path.exists()
    assert (quarantine_dir / "bad.milk").is_file()
    assert (quarantine_dir / "dup_1.milk").is_file()
    assert len(moves) == 2


def _mock_run_scan_gl(monkeypatch: pytest.MonkeyPatch) -> None:
    def make_pm() -> MagicMock:
        fake_pm = MagicMock()
        fake_pm.destroy = MagicMock()
        return fake_pm

    fake_fbo = MagicMock()
    fake_fbo.destroy = MagicMock()
    fake_fbo.fbo_id = 1

    monkeypatch.setattr("cleave.preset_scan.pygame.init", lambda: None)
    monkeypatch.setattr("cleave.preset_scan.pygame.quit", lambda: None)
    monkeypatch.setattr(
        "cleave.preset_scan.pygame.display.set_mode",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr("cleave.preset_scan.ProjectM", make_pm)
    monkeypatch.setattr("cleave.preset_scan._ProbeFbo", lambda *args: fake_fbo)


def test_existing_report_status_incomplete(tmp_path: Path) -> None:
    report_path = tmp_path / "scan.json"
    report_path.write_text(
        json.dumps({"presets": [{}, {}, {}], "complete": False}),
        encoding="utf-8",
    )
    scanned, complete = existing_report_status(report_path)
    assert scanned == 3
    assert complete is False


def test_run_scan_creates_fresh_projectm_per_preset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pm_instances: list[MagicMock] = []

    def make_pm() -> MagicMock:
        fake_pm = MagicMock()
        fake_pm.destroy = MagicMock()
        pm_instances.append(fake_pm)
        return fake_pm

    monkeypatch.setattr("cleave.preset_scan.pygame.init", lambda: None)
    monkeypatch.setattr("cleave.preset_scan.pygame.quit", lambda: None)
    monkeypatch.setattr(
        "cleave.preset_scan.pygame.display.set_mode",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr("cleave.preset_scan.ProjectM", make_pm)

    fake_fbo = MagicMock()
    fake_fbo.destroy = MagicMock()
    fake_fbo.fbo_id = 1
    monkeypatch.setattr("cleave.preset_scan._ProbeFbo", lambda *args: fake_fbo)

    probe_pms: list[MagicMock] = []

    def fake_probe(pm, fbo, target, **kwargs):
        probe_pms.append(pm)
        return PresetScanResult(path=target.path, result="ok", layers=target.layers)

    monkeypatch.setattr("cleave.preset_scan._probe_preset", fake_probe)

    targets = tuple(
        PresetTarget(path=tmp_path / f"p{i}.milk", layers=())
        for i in range(3)
    )
    scan_targets = ScanTargets(presets=targets)

    run_scan(scan_targets)

    assert len(pm_instances) == 3
    for pm in pm_instances:
        pm.destroy.assert_called_once()
    assert probe_pms == pm_instances


def test_run_scan_resume_progress_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _mock_run_scan_gl(monkeypatch)

    targets = tuple(
        PresetTarget(path=tmp_path / name, layers=())
        for name in ("a.milk", "b.milk", "c.milk")
    )
    scan_targets = ScanTargets(presets=targets)

    monkeypatch.setattr(
        "cleave.preset_scan._probe_preset",
        lambda pm, fbo, target, **kwargs: PresetScanResult(
            path=target.path, result="ok", layers=target.layers
        ),
    )

    skip = frozenset({(tmp_path / "a.milk").resolve()})
    run_scan(scan_targets, skip_paths=skip)

    err = capsys.readouterr().err
    assert "Resuming: 1 done" in err
    assert "Scanning 2/3" in err
    assert "Scanning 3/3" in err


def test_run_scan_skip_paths_and_report_sink(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _mock_run_scan_gl(monkeypatch)

    targets = [
        PresetTarget(path=tmp_path / "a.milk", layers=()),
        PresetTarget(path=tmp_path / "b.milk", layers=()),
        PresetTarget(path=tmp_path / "c.milk", layers=()),
    ]
    scan_targets = ScanTargets(presets=tuple(targets))

    def fake_probe(pm, fbo, target, **kwargs):
        return PresetScanResult(path=target.path, result="ok", layers=target.layers)

    monkeypatch.setattr("cleave.preset_scan._probe_preset", fake_probe)

    sink_calls: list[tuple[int, bool]] = []

    def sink(results: list[PresetScanResult], complete: bool) -> None:
        sink_calls.append((len(results), complete))

    skip = frozenset({(tmp_path / "b.milk").resolve()})
    results = run_scan(
        scan_targets,
        report_sink=sink,
        skip_paths=skip,
    )

    assert [result.path.name for result in results] == ["a.milk", "c.milk"]
    assert sink_calls[-1] == (2, True)
    assert all(complete is False for _, complete in sink_calls[:-1])


def test_run_scan_report_sink_flushes_every_ten(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _mock_run_scan_gl(monkeypatch)

    targets = tuple(
        PresetTarget(path=tmp_path / f"p{i}.milk", layers=())
        for i in range(REPORT_FLUSH_EVERY + 1)
    )
    scan_targets = ScanTargets(presets=targets)

    monkeypatch.setattr(
        "cleave.preset_scan._probe_preset",
        lambda pm, fbo, target, **kwargs: PresetScanResult(
            path=target.path, result="ok", layers=target.layers
        ),
    )

    partial_flushes: list[int] = []

    def sink(results: list[PresetScanResult], complete: bool) -> None:
        if not complete:
            partial_flushes.append(len(results))

    run_scan(scan_targets, report_sink=sink)
    assert partial_flushes == [REPORT_FLUSH_EVERY]


def test_run_scan_keyboard_interrupt_flushes_sink(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _mock_run_scan_gl(monkeypatch)

    targets = tuple(
        PresetTarget(path=tmp_path / f"p{i}.milk", layers=())
        for i in range(3)
    )
    scan_targets = ScanTargets(presets=targets)

    def interrupting_probe(pm, fbo, target, **kwargs):
        if target.path.name == "p1.milk":
            raise KeyboardInterrupt
        return PresetScanResult(path=target.path, result="ok", layers=target.layers)

    monkeypatch.setattr("cleave.preset_scan._probe_preset", interrupting_probe)

    sink_calls: list[tuple[int, bool]] = []

    def sink(results: list[PresetScanResult], complete: bool) -> None:
        sink_calls.append((len(results), complete))

    with pytest.raises(KeyboardInterrupt):
        run_scan(scan_targets, report_sink=sink)

    assert sink_calls == [(1, False)]


def _healthy_coverage() -> dict[int, float]:
    return _coverage_at(cutoff_16=0.5, cutoff_192=0.0)


def test_probe_preset_clean_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    from cleave.preset_scan import _probe_preset

    fake_pm = MagicMock()
    fake_pm.drain_preset_failures.return_value = []
    fake_fbo = MagicMock()
    fake_fbo.fbo_id = 1
    target = PresetTarget(path=Path("/tmp/a.milk"), layers=("layer_1",))
    profile = probe_profile(slow=False)
    pcm = build_probe_pcm(profile)
    frame = FrameMetrics(
        max_luma=50.0,
        mean_luma=25.0,
        coverage=_healthy_coverage(),
    )

    monkeypatch.setattr(
        "cleave.preset_scan.sample_frame_metrics",
        lambda width, height: frame,
    )

    result = _probe_preset(
        fake_pm,
        fake_fbo,
        target,
        profile=profile,
        pcm=pcm,
        n_pcm=100,
        frame_dt=1.0 / PROBE_FPS,
    )

    assert fake_pm.set_preset_start_clean.call_args_list == [call(True), call(False)]
    fake_pm.load_preset.assert_called_once_with(target.path, smooth=False)
    fake_pm.lock_preset.assert_called_once_with(True)
    assert result.result == "ok"
    assert result.luma == frame


def test_probe_preset_uses_peak_metrics_over_last_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cleave.preset_scan import _probe_preset

    fake_pm = MagicMock()
    fake_pm.drain_preset_failures.return_value = []
    fake_fbo = MagicMock()
    fake_fbo.fbo_id = 1
    target = PresetTarget(path=Path("/tmp/a.milk"), layers=())

    frames = [
        FrameMetrics(max_luma=1.0, mean_luma=1.0, coverage=_healthy_coverage()),
        FrameMetrics(max_luma=200.0, mean_luma=50.0, coverage=_healthy_coverage()),
        FrameMetrics(max_luma=1.0, mean_luma=1.0, coverage=_healthy_coverage()),
    ]
    call_count = {"index": 0}

    def fake_sample(width: int, height: int) -> FrameMetrics:
        index = call_count["index"]
        call_count["index"] += 1
        return frames[min(index, len(frames) - 1)]

    monkeypatch.setattr("cleave.preset_scan.sample_frame_metrics", fake_sample)
    monkeypatch.setattr(
        "cleave.preset_scan._synthetic_pcm_burst",
        lambda frame_idx, n_pcm: np.zeros(n_pcm, dtype=np.float32),
    )

    short_profile = probe_profile(slow=False)
    short_profile = type(short_profile)(
        warmup_frames=0,
        window_frames=3,
        mode=short_profile.mode,
    )
    pcm = build_probe_pcm(short_profile)
    result = _probe_preset(
        fake_pm,
        fake_fbo,
        target,
        profile=short_profile,
        pcm=pcm,
        n_pcm=4,
        frame_dt=1.0 / PROBE_FPS,
    )

    assert result.luma is not None
    assert result.luma.max_luma == 200.0
    assert result.luma.mean_luma == 50.0
    assert result.result == "ok"


def test_preset_result_luma_serialization_round_trip() -> None:
    from cleave.preset_scan import _preset_result_from_dict, _preset_result_to_dict

    coverage = {cutoff: float(cutoff) / 256.0 for cutoff in LUMA_COVERAGE_CUTOFFS}
    preset = PresetScanResult(
        path=Path("/tmp/a.milk"),
        result="ok",
        layers=("layer_1",),
        luma=FrameMetrics(max_luma=42.0, mean_luma=12.0, coverage=coverage),
    )

    payload = _preset_result_to_dict(preset)
    assert payload["luma"]["max"] == 42.0
    assert payload["luma"]["mean"] == 12.0
    assert payload["luma"]["coverage"]["16"] == pytest.approx(16.0 / 256.0)

    restored = _preset_result_from_dict(payload)
    assert restored.luma == preset.luma


def test_load_resume_results_with_washed_out(tmp_path: Path) -> None:
    preset_path = tmp_path / "washed.milk"
    payload = {
        "scan_mode": "bulk",
        "probe_mode": "quick",
        "presets": [
            {
                "path": str(preset_path),
                "result": "washed_out",
                "layers": [],
            },
        ],
    }
    report_path = tmp_path / "resume.json"
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    resume = load_resume_results(report_path)
    assert resume.results[0].result == "washed_out"


def test_load_resume_results_with_luma(tmp_path: Path) -> None:
    preset_path = tmp_path / "a.milk"
    payload = {
        "scan_mode": "bulk",
        "probe_mode": "quick",
        "presets": [
            {
                "path": str(preset_path),
                "result": "ok",
                "layers": [],
                "luma": {
                    "max": 30.0,
                    "mean": 10.0,
                    "coverage": {str(cutoff): 0.1 for cutoff in LUMA_COVERAGE_CUTOFFS},
                },
            },
        ],
    }
    report_path = tmp_path / "resume.json"
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    resume = load_resume_results(report_path)
    assert resume.results[0].luma is not None
    assert resume.results[0].luma.max_luma == 30.0
    assert resume.results[0].luma.mean_luma == 10.0


def test_probe_pcm_metadata_quick() -> None:
    meta = probe_pcm_metadata(probe_profile(slow=False))
    assert meta == {
        "pcm_source": "synthetic",
        "pcm_channels": 1,
        "reference_clip_path": None,
    }


def test_probe_pcm_metadata_slow() -> None:
    meta = probe_pcm_metadata(probe_profile(slow=True))
    assert meta["pcm_source"] == "reference-clip"
    assert meta["pcm_channels"] == 2
    assert meta["reference_clip_path"] == REFERENCE_CLIP_PATH.resolve()


def test_build_probe_pcm_quick() -> None:
    pcm = build_probe_pcm(probe_profile(slow=False))
    assert pcm.source == "synthetic"
    assert pcm.channels == 1
    assert pcm._pcm is None
    chunk = pcm.chunk(3, 100)
    assert chunk.shape == (100,)
    assert float(np.max(np.abs(chunk))) > 0.01


def test_build_probe_pcm_slow() -> None:
    pcm = build_probe_pcm(probe_profile(slow=True))
    assert pcm.source == "reference-clip"
    assert pcm.channels == 2
    assert pcm._pcm is not None
    assert pcm.reference_clip_path == REFERENCE_CLIP_PATH.resolve()
    chunk = pcm.chunk(0, 100)
    assert chunk.shape == (200,)


def test_probe_pcm_chunk_zero_pads_past_end() -> None:
    pcm = ProbePcm(
        channels=2,
        source="reference-clip",
        reference_clip_path=REFERENCE_CLIP_PATH,
        _pcm=np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32),
    )
    chunk = pcm.chunk(9999, 10)
    assert chunk.shape == (20,)
    assert np.all(chunk == 0.0)


def test_scan_report_slow_includes_reference_clip_path() -> None:
    report = build_scan_report(
        scan_mode="bulk",
        profile=probe_profile(slow=True),
        targets=ScanTargets(presets=()),
        results=(),
    )
    payload = scan_report_to_dict(report)
    assert payload["pcm_source"] == "reference-clip"
    assert payload["pcm_channels"] == 2
    assert payload["reference_clip_path"] == str(REFERENCE_CLIP_PATH.resolve())


def test_delete_presets_removes_failures(tmp_path: Path) -> None:
    presets_dir = tmp_path / "presets"
    presets_dir.mkdir()
    ok_path = presets_dir / "good.milk"
    bad_path = presets_dir / "bad.milk"
    ok_path.write_text("ok", encoding="utf-8")
    bad_path.write_text("bad", encoding="utf-8")

    deleted = delete_presets(
        [
            PresetScanResult(path=ok_path, result="ok", layers=()),
            PresetScanResult(path=bad_path, result="black", layers=()),
        ]
    )

    assert ok_path.is_file()
    assert not bad_path.exists()
    assert deleted == [bad_path]
