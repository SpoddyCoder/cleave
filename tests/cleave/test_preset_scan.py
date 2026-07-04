"""Unit tests for preset scan profiles, classification, and reports."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

from cleave.preset_scan import (
    BLACK_MAX_LUMA_THRESHOLD,
    DIM_MEAN_LUMA_THRESHOLD,
    PROBE_FBO_HEIGHT,
    PROBE_FBO_WIDTH,
    PROBE_FPS,
    QUICK_PROBE_FRAMES,
    QUICK_PROBE_WARMUP_SEC,
    SLOW_PROBE_FRAMES,
    SLOW_PROBE_WARMUP_SEC,
    PresetScanResult,
    PresetScanTimings,
    ScanReport,
    build_scan_report,
    classify_preset_result,
    probe_profile,
    scan_report_summary,
    scan_report_to_dict,
    write_scan_report,
)
from cleave.preset_scan_targets import PresetTarget, ScanTargets
from cleave.projectm import PresetLoadFailure


def test_probe_profile_quick() -> None:
    profile = probe_profile(slow=False)
    assert profile.frames == QUICK_PROBE_FRAMES
    assert profile.warmup_sec == QUICK_PROBE_WARMUP_SEC
    assert profile.mode == "quick"


def test_probe_profile_slow() -> None:
    profile = probe_profile(slow=True)
    assert profile.frames == SLOW_PROBE_FRAMES
    assert profile.warmup_sec == SLOW_PROBE_WARMUP_SEC
    assert profile.mode == "slow"


def test_classify_preset_result_load_failed() -> None:
    failures = [
        PresetLoadFailure(filename="/tmp/a.milk", message="shader error"),
        PresetLoadFailure(filename="/tmp/b.milk", message="later"),
    ]
    result, error = classify_preset_result(failures, max_luma=100.0, mean_luma=100.0)
    assert result == "load_failed"
    assert error == "shader error"


def test_classify_preset_result_black() -> None:
    result, error = classify_preset_result(
        [],
        max_luma=BLACK_MAX_LUMA_THRESHOLD - 0.01,
        mean_luma=0.0,
    )
    assert result == "black"
    assert error is None


def test_classify_preset_result_black_boundary_not_black() -> None:
    result, error = classify_preset_result(
        [],
        max_luma=BLACK_MAX_LUMA_THRESHOLD,
        mean_luma=0.0,
    )
    assert result == "dim"
    assert error is None


def test_classify_preset_result_dim() -> None:
    result, error = classify_preset_result(
        [],
        max_luma=BLACK_MAX_LUMA_THRESHOLD,
        mean_luma=DIM_MEAN_LUMA_THRESHOLD - 0.01,
    )
    assert result == "dim"
    assert error is None


def test_classify_preset_result_dim_boundary_ok() -> None:
    result, error = classify_preset_result(
        [],
        max_luma=BLACK_MAX_LUMA_THRESHOLD,
        mean_luma=DIM_MEAN_LUMA_THRESHOLD,
    )
    assert result == "ok"
    assert error is None


def test_classify_preset_result_ok() -> None:
    result, error = classify_preset_result([], max_luma=50.0, mean_luma=50.0)
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
    assert report.probe_frames == QUICK_PROBE_FRAMES
    assert report.probe_fps == PROBE_FPS
    assert report.fbo_size == (PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT)
    assert len(report.presets) == 2

    summary = scan_report_summary(report)
    assert summary == {
        "total": 2,
        "load_failed": 0,
        "black": 1,
        "dim": 0,
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
        thresholds={
            "black_max_luma": BLACK_MAX_LUMA_THRESHOLD,
            "dim_mean_luma": DIM_MEAN_LUMA_THRESHOLD,
        },
        probe_frames=QUICK_PROBE_FRAMES,
        probe_fps=PROBE_FPS,
        fbo_size=(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT),
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
    assert payload["thresholds"]["black_max_luma"] == BLACK_MAX_LUMA_THRESHOLD
    assert payload["probe_frames"] == QUICK_PROBE_FRAMES
    assert payload["probe_fps"] == PROBE_FPS
    assert payload["fbo_size"] == [PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT]
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
        "ok": 1,
    }

    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / "scan-report.json"
        write_scan_report(report_path, report)
        loaded = json.loads(report_path.read_text(encoding="utf-8"))
        assert loaded == payload
