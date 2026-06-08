"""Tests for Demucs separation and project layout."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from cleave.extract import STEM_NAMES
from cleave.project import PROJECT_FILENAME, load_manifest, write_manifest
from cleave.separate import (
    project_stems_complete,
    resolve_separate_target,
    run_separate,
    signals_complete,
)


def test_project_stems_complete_false_when_missing(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    assert project_stems_complete(project) is False


def test_project_stems_complete_true_when_all_present(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    for name in STEM_NAMES:
        (project / f"{name}.wav").write_bytes(b"wav")
    assert project_stems_complete(project) is True


def test_signals_complete_false_when_missing(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    assert signals_complete(project) is False


def test_signals_complete_true_when_present(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    (project / "signals.json").write_text("{}")
    assert signals_complete(project) is True


def test_resolve_separate_target_audio_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    audio = tmp_path / "song.flac"
    audio.write_bytes(b"audio")

    project_dir, audio_path = resolve_separate_target(audio)

    assert project_dir == (tmp_path / "projects" / "song").resolve()
    assert audio_path == audio.resolve()


def test_resolve_separate_target_project_slug(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "my-track.flac",
        demucs_model="htdemucs",
    )

    project_dir, audio_path = resolve_separate_target("my-track")

    assert project_dir == project.resolve()
    assert audio_path == mix.resolve()


def test_run_separate_noop_when_stems_and_signals_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    audio = tmp_path / "my-track.flac"
    audio.write_bytes(b"audio")

    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    for name in STEM_NAMES:
        (project / f"{name}.wav").write_bytes(b"wav")
    (project / "signals.json").write_text("{}")

    with patch("cleave.separate._run_demucs") as run_demucs, patch(
        "cleave.separate.run_analyse"
    ) as run_analyse:
        result = run_separate(audio)

    assert result == project.resolve()
    run_demucs.assert_not_called()
    run_analyse.assert_not_called()


def test_run_separate_analyse_only_when_stems_exist_no_signals(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    for name in STEM_NAMES:
        (project / f"{name}.wav").write_bytes(b"wav")
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "my-track.flac",
        demucs_model="htdemucs",
    )

    with patch("cleave.separate._run_demucs") as run_demucs, patch(
        "cleave.separate.run_analyse", return_value=project / "signals.json"
    ) as run_analyse:
        result = run_separate("my-track")

    assert result == project.resolve()
    run_demucs.assert_not_called()
    run_analyse.assert_called_once_with(project.resolve(), slow=False)


def test_run_separate_force_runs_demucs_and_analyse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    for name in STEM_NAMES:
        (project / f"{name}.wav").write_bytes(b"wav")
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "elsewhere.flac",
        demucs_model="htdemucs",
    )
    (project / "signals.json").write_text("{}")

    with patch("cleave.separate._run_demucs") as run_demucs, patch(
        "cleave.separate.run_analyse", return_value=project / "signals.json"
    ) as run_analyse:
        result = run_separate("my-track", force=True)

    assert result == project.resolve()
    run_demucs.assert_called_once_with(
        mix.resolve(), project.resolve(), slow=False, force=True
    )
    run_analyse.assert_called_once_with(project.resolve(), slow=False)


def test_run_separate_creates_project_and_renders(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    audio = tmp_path / "song.flac"
    audio.write_bytes(b"audio")

    project = tmp_path / "projects" / "song"
    demucs_out = tmp_path / "demucs-out" / "htdemucs" / "song"
    demucs_out.mkdir(parents=True)
    for name in STEM_NAMES:
        (demucs_out / f"{name}.wav").write_bytes(b"wav")

    def fake_run(cmd: list[str], *, check: bool) -> None:
        out_flag = cmd.index("-o")
        out_root = Path(cmd[out_flag + 1])
        target = out_root / "htdemucs" / "song"
        target.parent.mkdir(parents=True, exist_ok=True)
        for name in STEM_NAMES:
            shutil_copy = demucs_out / f"{name}.wav"
            target.mkdir(parents=True, exist_ok=True)
            (target / f"{name}.wav").write_bytes(shutil_copy.read_bytes())

    with patch("cleave.separate.subprocess.run", side_effect=fake_run), patch(
        "cleave.separate.run_analyse", return_value=project / "signals.json"
    ):
        result = run_separate(audio)

    assert result == project.resolve()
    assert project.is_dir()
    assert (project / "renders").is_dir()
    assert (project / "song.flac").read_bytes() == b"audio"
    assert (project / PROJECT_FILENAME).is_file()
    manifest = load_manifest(project)
    assert manifest.slug == "song"
    assert manifest.mix_filename == "song.flac"
    assert manifest.demucs_model == "htdemucs"
    for name in STEM_NAMES:
        assert (project / f"{name}.wav").is_file()


def test_run_separate_force_deletes_stale_mix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "song"
    project.mkdir(parents=True)
    (project / "renders").mkdir()
    for name in STEM_NAMES:
        (project / f"{name}.wav").write_bytes(b"wav")
    (project / "old-name.flac").write_bytes(b"old")
    write_manifest(
        project,
        slug="song",
        mix_filename="old-name.flac",
        original_path=tmp_path / "old-name.flac",
        demucs_model="htdemucs",
    )

    new_audio = tmp_path / "song.wav"
    new_audio.write_bytes(b"new")

    demucs_out = tmp_path / "demucs-out" / "htdemucs" / "song"
    demucs_out.mkdir(parents=True)
    for name in STEM_NAMES:
        (demucs_out / f"{name}.wav").write_bytes(b"wav")

    def fake_run(cmd: list[str], *, check: bool) -> None:
        out_flag = cmd.index("-o")
        out_root = Path(cmd[out_flag + 1])
        target = out_root / "htdemucs" / "song"
        target.mkdir(parents=True, exist_ok=True)
        for name in STEM_NAMES:
            (target / f"{name}.wav").write_bytes(b"wav")

    with patch("cleave.separate.subprocess.run", side_effect=fake_run), patch(
        "cleave.separate.run_analyse", return_value=project / "signals.json"
    ):
        run_separate(new_audio, force=True)

    assert not (project / "old-name.flac").exists()
    assert (project / "song.wav").read_bytes() == b"new"
    manifest = load_manifest(project)
    assert manifest.mix_filename == "song.wav"
