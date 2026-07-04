"""Unit tests for preset scan profiles, classification, and reports."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from cleave.preset_scan import (
    BLACK_MAX_LUMA_THRESHOLD,
    DIM_MEAN_LUMA_THRESHOLD,
    PROBE_FBO_HEIGHT,
    PROBE_FBO_WIDTH,
    PROBE_FPS,
    QUICK_PROBE_FRAMES,
    QUICK_PROBE_WARMUP_SEC,
    REPORT_FLUSH_EVERY,
    SLOW_PROBE_FRAMES,
    SLOW_PROBE_WARMUP_SEC,
    PresetScanResult,
    PresetScanTimings,
    ScanReport,
    build_scan_report,
    classify_preset_result,
    existing_report_status,
    load_resume_results,
    probe_profile,
    quarantine_presets,
    run_scan,
    scan_report_summary,
    scan_report_to_dict,
    validate_quarantine_dir,
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
        thresholds={
            "black_max_luma": BLACK_MAX_LUMA_THRESHOLD,
            "dim_mean_luma": DIM_MEAN_LUMA_THRESHOLD,
        },
        probe_frames=QUICK_PROBE_FRAMES,
        probe_fps=PROBE_FPS,
        fbo_size=(PROBE_FBO_WIDTH, PROBE_FBO_HEIGHT),
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
    fake_pm = MagicMock()
    fake_pm.destroy = MagicMock()
    fake_fbo = MagicMock()
    fake_fbo.destroy = MagicMock()
    fake_fbo.fbo_id = 1

    monkeypatch.setattr("cleave.preset_scan.pygame.init", lambda: None)
    monkeypatch.setattr("cleave.preset_scan.pygame.quit", lambda: None)
    monkeypatch.setattr(
        "cleave.preset_scan.pygame.display.set_mode",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr("cleave.preset_scan.ProjectM", lambda: fake_pm)
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
