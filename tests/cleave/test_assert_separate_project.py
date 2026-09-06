"""Tests for scripts/assert_separate_project.py (fake project dirs; no Demucs)."""

from __future__ import annotations

import importlib.util
import json
import wave
from pathlib import Path

import pytest

from cleave.signals import SIGNALS_VERSION
from cleave.stems import STEM_NAMES, stems_dir

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = REPO_ROOT / "scripts" / "assert_separate_project.py"
_SMOKE_WAV = REPO_ROOT / "tests" / "fixtures" / "smoke-separate.wav"


def _load_assert_separate_project():
    spec = importlib.util.spec_from_file_location("assert_separate_project", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


assert_mod = _load_assert_separate_project()


def _write_stems(project: Path, names: tuple[str, ...] = STEM_NAMES) -> None:
    base = stems_dir(project)
    base.mkdir(parents=True)
    for name in names:
        (base / f"{name}.wav").write_bytes(b"wav")


def _write_signals(project: Path, version: object = SIGNALS_VERSION) -> None:
    payload = {"version": version}
    (project / "signals.json").write_text(json.dumps(payload), encoding="utf-8")


def test_smoke_separate_wav_is_short_pcm() -> None:
    assert _SMOKE_WAV.is_file()
    with wave.open(str(_SMOKE_WAV), "r") as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getcomptype() == "NONE"
        duration = handle.getnframes() / float(handle.getframerate())
        assert 1.5 <= duration <= 2.5
    assert _SMOKE_WAV.stat().st_size < 200_000


def test_assert_separate_project_ok(tmp_path: Path) -> None:
    project = tmp_path / "smoke-separate"
    project.mkdir()
    _write_stems(project)
    _write_signals(project)
    assert_mod.assert_separate_project(project)
    assert assert_mod.main([str(project)]) == 0


def test_assert_separate_project_missing_dir(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-project"
    with pytest.raises(SystemExit, match="missing project dir"):
        assert_mod.assert_separate_project(missing)


def test_assert_separate_project_missing_stem(tmp_path: Path) -> None:
    project = tmp_path / "track"
    project.mkdir()
    _write_stems(project, names=("drums", "bass", "vocals"))
    _write_signals(project)
    with pytest.raises(SystemExit, match=r"stems/other\.wav"):
        assert_mod.assert_separate_project(project)


def test_assert_separate_project_missing_signals(tmp_path: Path) -> None:
    project = tmp_path / "track"
    project.mkdir()
    _write_stems(project)
    with pytest.raises(SystemExit, match="signals.json"):
        assert_mod.assert_separate_project(project)


def test_assert_separate_project_wrong_version(tmp_path: Path) -> None:
    project = tmp_path / "track"
    project.mkdir()
    _write_stems(project)
    _write_signals(project, version=SIGNALS_VERSION - 1)
    with pytest.raises(SystemExit, match=f"!= {SIGNALS_VERSION}"):
        assert_mod.assert_separate_project(project)


def test_assert_separate_project_corrupt_signals(tmp_path: Path) -> None:
    project = tmp_path / "track"
    project.mkdir()
    _write_stems(project)
    (project / "signals.json").write_text("{", encoding="utf-8")
    with pytest.raises(SystemExit, match="unreadable"):
        assert_mod.assert_separate_project(project)
