"""Tests for Demucs separation and project layout."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock, patch

import pytest
import yaml

from cleave.config import VIZ_CONFIG_FILENAME
from cleave.stems import STEM_NAMES, stems_dir
from cleave.paths import model_cache_dir
from cleave.project import (
    PROJECT_FILENAME,
    load_manifest,
    rewrite_manifest_slug,
    write_manifest,
)
from cleave.separate import (
    _run_demucs,
    project_stems_complete,
    resolve_separate_target,
    run_separate,
    signals_complete,
)


def _write_stub_stems(project: Path) -> None:
    base = stems_dir(project)
    base.mkdir(parents=True, exist_ok=True)
    for name in STEM_NAMES:
        (base / f"{name}.wav").write_bytes(b"wav")


@contextmanager
def _mock_demucs_writes_stems() -> Iterator[dict[str, MagicMock]]:
    """Stub the Demucs Python API so ``save_audio`` writes dummy stem wavs."""
    model_obj = MagicMock()
    model_obj.sources = ["drums", "bass", "other", "vocals"]
    model_obj.audio_channels = 2
    model_obj.samplerate = 44100

    def fake_save_audio(_wav: object, path: str, **_kwargs: object) -> None:
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"wav")

    with (
        patch("torch.hub.set_dir") as set_dir,
        patch("torch.cuda.is_available", return_value=False),
        patch("demucs.pretrained.get_model", return_value=model_obj) as get_model,
        patch("demucs.separate.load_track", return_value=MagicMock()),
        patch("demucs.apply.apply_model", return_value=[MagicMock()]),
        patch("demucs.audio.save_audio", side_effect=fake_save_audio),
    ):
        yield {"set_dir": set_dir, "get_model": get_model, "model": model_obj}


def test_project_stems_complete_false_when_missing(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    assert project_stems_complete(project) is False


def test_project_stems_complete_true_when_all_present(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    _write_stub_stems(project)
    assert project_stems_complete(project) is True


def test_signals_complete_false_when_missing(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    assert signals_complete(project) is False


def test_signals_complete_true_when_current_version(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    (project / "signals.json").write_text('{"version": 4}')
    assert signals_complete(project) is True


def test_signals_complete_false_when_stale_version(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    (project / "signals.json").write_text('{"version": 2}')
    assert signals_complete(project) is False


def test_signals_complete_false_when_corrupt(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    (project / "signals.json").write_text("not-json")
    assert signals_complete(project) is False


def test_signals_complete_false_when_missing_version(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    (project / "signals.json").write_text("{}")
    assert signals_complete(project) is False


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


def test_run_separate_writes_project_viz_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    audio = tmp_path / "my-track.flac"
    audio.write_bytes(b"audio")

    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    _write_stub_stems(project)
    (project / "signals.json").write_text('{"version": 4}')

    with patch("cleave.separate._run_demucs") as run_demucs, patch(
        "cleave.analyse.run_analyse"
    ) as run_analyse:
        run_separate(audio)

    viz_config = project / VIZ_CONFIG_FILENAME
    assert viz_config.is_file()
    data = yaml.safe_load(viz_config.read_text(encoding="utf-8"))
    assert data["editor"]["name"] == "my-track"
    run_demucs.assert_not_called()
    run_analyse.assert_not_called()


def test_run_separate_noop_when_stems_and_signals_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    audio = tmp_path / "my-track.flac"
    audio.write_bytes(b"audio")

    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    _write_stub_stems(project)
    (project / "signals.json").write_text('{"version": 4}')

    with patch("cleave.separate._run_demucs") as run_demucs, patch(
        "cleave.analyse.run_analyse"
    ) as run_analyse:
        result = run_separate(audio)

    assert result == project.resolve()
    run_demucs.assert_not_called()
    run_analyse.assert_not_called()


def test_run_separate_complete_project_skips_stem_split_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    monkeypatch.setattr("cleave.separate.stem_split_available", lambda: False)
    audio = tmp_path / "my-track.flac"
    audio.write_bytes(b"audio")

    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    _write_stub_stems(project)
    (project / "signals.json").write_text('{"version": 4}')

    result = run_separate(audio)
    assert result == project.resolve()


def test_run_separate_missing_torch_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    monkeypatch.setattr("cleave.separate.stem_split_available", lambda: False)
    monkeypatch.setattr("cleave.separate.is_frozen", lambda: True)
    audio = tmp_path / "my-track.flac"
    audio.write_bytes(b"audio")

    with pytest.raises(RuntimeError, match="not in this Windows build"):
        run_separate(audio)


def test_run_separate_analyse_only_when_stems_exist_stale_signals(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    _write_stub_stems(project)
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "my-track.flac",
        demucs_model="htdemucs",
    )
    (project / "signals.json").write_text('{"version": 2}')

    with patch("cleave.separate._run_demucs") as run_demucs, patch(
        "cleave.analyse.run_analyse", return_value=project / "signals.json"
    ) as run_analyse:
        result = run_separate("my-track")

    assert result == project.resolve()
    run_demucs.assert_not_called()
    run_analyse.assert_called_once_with(
        project.resolve(), high_quality=False, beat_detection_stem="full_mix"
    )


def test_run_separate_analyse_only_when_stems_exist_no_signals(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    _write_stub_stems(project)
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
        "cleave.analyse.run_analyse", return_value=project / "signals.json"
    ) as run_analyse:
        result = run_separate("my-track")

    assert result == project.resolve()
    run_demucs.assert_not_called()
    run_analyse.assert_called_once_with(
        project.resolve(), high_quality=False, beat_detection_stem="full_mix"
    )


def test_run_separate_reanalyses_on_explicit_beat_stem_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    _write_stub_stems(project)
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "my-track.flac",
        demucs_model="htdemucs",
    )
    (project / "signals.json").write_text(
        '{"version": 4, "beat_detection_stem": "full_mix"}'
    )

    with patch("cleave.separate._run_demucs") as run_demucs, patch(
        "cleave.analyse.run_analyse", return_value=project / "signals.json"
    ) as run_analyse:
        result = run_separate("my-track", beat_detection_stem="drums")

    assert result == project.resolve()
    run_demucs.assert_not_called()
    run_analyse.assert_called_once_with(
        project.resolve(), high_quality=False, beat_detection_stem="drums"
    )


def test_run_separate_skips_when_explicit_beat_stem_matches_stored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    audio = tmp_path / "my-track.flac"
    audio.write_bytes(b"audio")

    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    _write_stub_stems(project)
    (project / "signals.json").write_text(
        '{"version": 4, "beat_detection_stem": "drums"}'
    )

    with patch("cleave.separate._run_demucs") as run_demucs, patch(
        "cleave.analyse.run_analyse"
    ) as run_analyse:
        result = run_separate(audio, beat_detection_stem="drums")

    assert result == project.resolve()
    run_demucs.assert_not_called()
    run_analyse.assert_not_called()


def test_run_separate_skips_when_flag_omitted_even_if_stored_is_drums(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    audio = tmp_path / "my-track.flac"
    audio.write_bytes(b"audio")

    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    _write_stub_stems(project)
    (project / "signals.json").write_text(
        '{"version": 4, "beat_detection_stem": "drums"}'
    )

    with patch("cleave.separate._run_demucs") as run_demucs, patch(
        "cleave.analyse.run_analyse"
    ) as run_analyse:
        result = run_separate(audio)

    assert result == project.resolve()
    run_demucs.assert_not_called()
    run_analyse.assert_not_called()


def test_run_demucs_skips_copy_when_mix_in_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    (project / "renders").mkdir()
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=mix,
        demucs_model="htdemucs",
    )

    with _mock_demucs_writes_stems() as mocks:
        _run_demucs(mix, project, high_quality=False, force=True)

    mocks["get_model"].assert_called_once_with("htdemucs")
    mocks["set_dir"].assert_called_once_with(str(model_cache_dir()))
    assert mix.read_bytes() == b"mix"
    for name in STEM_NAMES:
        assert (stems_dir(project) / f"{name}.wav").is_file()


def test_run_demucs_high_quality_loads_htdemucs_ft(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")

    with _mock_demucs_writes_stems() as mocks:
        _run_demucs(mix, project, high_quality=True, force=True)

    mocks["get_model"].assert_called_once_with("htdemucs_ft")
    assert load_manifest(project).demucs_model == "htdemucs_ft"


def test_run_demucs_wraps_get_model_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")

    with (
        patch("torch.hub.set_dir"),
        patch("torch.cuda.is_available", return_value=False),
        patch("demucs.pretrained.get_model", side_effect=RuntimeError("hub down")),
        patch("demucs.separate.load_track"),
        patch("demucs.apply.apply_model"),
        patch("demucs.audio.save_audio"),
        pytest.raises(RuntimeError, match="demucs failed"),
    ):
        _run_demucs(mix, project, high_quality=False, force=True)


def test_run_demucs_raises_when_stems_not_written(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")
    model_obj = MagicMock()
    model_obj.sources = ["drums", "bass", "other", "vocals"]

    with (
        patch("torch.hub.set_dir"),
        patch("torch.cuda.is_available", return_value=False),
        patch("demucs.pretrained.get_model", return_value=model_obj),
        patch("demucs.separate.load_track", return_value=MagicMock()),
        patch("demucs.apply.apply_model", return_value=[MagicMock()]),
        patch("demucs.audio.save_audio"),
        pytest.raises(RuntimeError, match="missing stem files"),
    ):
        _run_demucs(mix, project, high_quality=False, force=True)


def test_run_separate_force_runs_demucs_and_analyse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    _write_stub_stems(project)
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
        "cleave.analyse.run_analyse", return_value=project / "signals.json"
    ) as run_analyse:
        result = run_separate("my-track", force=True)

    assert result == project.resolve()
    run_demucs.assert_called_once_with(
        mix.resolve(), project.resolve(), high_quality=False, force=True
    )
    run_analyse.assert_called_once_with(
        project.resolve(), high_quality=False, beat_detection_stem="full_mix"
    )


def test_run_separate_force_uses_stored_beat_detection_stem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    _write_stub_stems(project)
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "elsewhere.flac",
        demucs_model="htdemucs",
    )
    (project / "signals.json").write_text(
        '{"version": 4, "beat_detection_stem": "drums"}'
    )

    with patch("cleave.separate._run_demucs") as run_demucs, patch(
        "cleave.analyse.run_analyse", return_value=project / "signals.json"
    ) as run_analyse:
        result = run_separate("my-track", force=True)

    assert result == project.resolve()
    run_demucs.assert_called_once()
    run_analyse.assert_called_once_with(
        project.resolve(), high_quality=False, beat_detection_stem="drums"
    )


def test_run_separate_force_explicit_beat_stem_overrides_stored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "my-track"
    project.mkdir(parents=True)
    _write_stub_stems(project)
    mix = project / "my-track.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=tmp_path / "elsewhere.flac",
        demucs_model="htdemucs",
    )
    (project / "signals.json").write_text(
        '{"version": 4, "beat_detection_stem": "drums"}'
    )

    with patch("cleave.separate._run_demucs") as run_demucs, patch(
        "cleave.analyse.run_analyse", return_value=project / "signals.json"
    ) as run_analyse:
        result = run_separate(
            "my-track", force=True, beat_detection_stem="bass"
        )

    assert result == project.resolve()
    run_demucs.assert_called_once()
    run_analyse.assert_called_once_with(
        project.resolve(), high_quality=False, beat_detection_stem="bass"
    )


def test_run_separate_creates_project_and_renders(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    audio = tmp_path / "song.flac"
    audio.write_bytes(b"audio")

    project = tmp_path / "projects" / "song"

    with _mock_demucs_writes_stems(), patch(
        "cleave.analyse.run_analyse", return_value=project / "signals.json"
    ):
        result = run_separate(audio)

    assert result == project.resolve()
    assert project.is_dir()
    assert (project / "renders").is_dir()
    assert stems_dir(project).is_dir()
    assert (project / "song.flac").read_bytes() == b"audio"
    assert (project / PROJECT_FILENAME).is_file()
    manifest = load_manifest(project)
    assert manifest.slug == "song"
    assert manifest.mix_filename == "song.flac"
    assert manifest.demucs_model == "htdemucs"
    for name in STEM_NAMES:
        assert (stems_dir(project) / f"{name}.wav").is_file()


def test_run_separate_force_deletes_stale_mix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "song"
    project.mkdir(parents=True)
    (project / "renders").mkdir()
    _write_stub_stems(project)
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

    with _mock_demucs_writes_stems(), patch(
        "cleave.analyse.run_analyse", return_value=project / "signals.json"
    ):
        run_separate(new_audio, force=True)

    assert not (project / "old-name.flac").exists()
    assert (project / "song.wav").read_bytes() == b"new"
    manifest = load_manifest(project)
    assert manifest.mix_filename == "song.wav"


def test_run_separate_force_preserves_song_markers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    project = tmp_path / "projects" / "song"
    project.mkdir(parents=True)
    (project / "renders").mkdir()
    _write_stub_stems(project)
    mix = project / "song.flac"
    mix.write_bytes(b"mix")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "elsewhere.flac",
        demucs_model="htdemucs",
        song_markers=(12.5, 64.0, 120.0),
    )
    rewrite_manifest_slug(project, "song", restored_from="archived-slug")

    with _mock_demucs_writes_stems(), patch(
        "cleave.analyse.run_analyse", return_value=project / "signals.json"
    ):
        run_separate("song", force=True)

    manifest = load_manifest(project)
    assert [m.time for m in manifest.song_markers] == [12.5, 64.0, 120.0]
    assert all(m.marker_type == "standard" for m in manifest.song_markers)
    assert manifest.restored_from == "archived-slug"
    assert manifest.demucs_model == "htdemucs"
    assert manifest.mix_filename == "song.flac"
