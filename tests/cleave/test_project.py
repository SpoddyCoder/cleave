"""Tests for cleave.project manifest helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from cleave.project import (
    PROJECT_FILENAME,
    CompositorSettings,
    MilkdropSettings,
    ProjectManifest,
    ProjectRenderSettings,
    load_manifest,
    manifest_path,
    mix_path,
    resolve_mix_path,
    rewrite_manifest_slug,
    save_compositor_settings,
    save_milkdrop_settings,
    save_render_settings,
    save_song_markers,
    write_manifest,
)
from cleave.song_markers import SongMarker


def test_write_and_load_manifest(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    original = tmp_path / "source.flac"
    original.write_bytes(b"audio")

    when = datetime(2026, 6, 8, 20, 15, tzinfo=timezone.utc)
    path = write_manifest(
        project,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=original,
        demucs_model="htdemucs",
        separated_at=when,
    )

    assert path == manifest_path(project)
    manifest = load_manifest(project)
    assert manifest == ProjectManifest(
        version=1,
        slug="my-track",
        mix_filename="my-track.flac",
        original_path=str(original.resolve()),
        separated_at="2026-06-08T20:15:00+00:00",
        demucs_model="htdemucs",
    )


def test_mix_path_from_manifest(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    mix_file = project / "song.flac"
    mix_file.write_bytes(b"mix")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "elsewhere.flac",
        demucs_model="htdemucs",
    )

    assert mix_path(project) == mix_file.resolve()


def test_load_manifest_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="project manifest not found"):
        load_manifest(tmp_path)


def test_resolve_mix_path_uses_manifest(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    mix_file = project / "song.flac"
    mix_file.write_bytes(b"mix")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "elsewhere.flac",
        demucs_model="htdemucs",
    )

    assert resolve_mix_path(project) == mix_file.resolve()


def test_resolve_mix_path_missing_manifest_raises(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()

    with pytest.raises(FileNotFoundError, match="no project mix"):
        resolve_mix_path(project)


def test_resolve_mix_path_missing_mix_raises(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "elsewhere.flac",
        demucs_model="htdemucs",
    )

    with pytest.raises(FileNotFoundError, match="audio not found"):
        resolve_mix_path(project)


def test_manifest_round_trip_yaml(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    original = tmp_path / "source.flac"
    original.write_bytes(b"audio")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=original,
        demucs_model="htdemucs_ft",
    )

    with (project / PROJECT_FILENAME).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    assert data["version"] == 1
    assert data["slug"] == "song"
    assert data["mix"]["filename"] == "song.flac"
    assert data["ingest"]["demucs_model"] == "htdemucs_ft"


def test_manifest_restored_from_round_trip(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    manifest = ProjectManifest(
        version=1,
        slug="song",
        mix_filename="song.flac",
        original_path=str((tmp_path / "source.flac").resolve()),
        separated_at="2026-06-08T20:15:00+00:00",
        demucs_model="htdemucs",
        restored_from="original-slug",
    )
    with (project / PROJECT_FILENAME).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest.to_dict(), handle, sort_keys=False)

    loaded = load_manifest(project)
    assert loaded == manifest

    with (project / PROJECT_FILENAME).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert data["restored-from"] == "original-slug"


def test_manifest_omits_restored_from_when_none(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )

    with (project / PROJECT_FILENAME).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    assert "restored-from" not in data
    assert load_manifest(project).restored_from is None


def test_rewrite_manifest_slug_updates_slug_and_restored_from(tmp_path: Path) -> None:
    project = tmp_path / "old-slug"
    project.mkdir()
    write_manifest(
        project,
        slug="old-slug",
        mix_filename="old-slug.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
        song_markers=(12.5, 64.0),
    )

    rewrite_manifest_slug(project, "new-slug", restored_from="old-slug")

    manifest = load_manifest(project)
    assert manifest.slug == "new-slug"
    assert manifest.restored_from == "old-slug"
    assert manifest.mix_filename == "old-slug.flac"
    assert [m.time for m in manifest.song_markers] == [12.5, 64.0]


def test_manifest_round_trip_without_song_markers(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )

    with (project / PROJECT_FILENAME).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    assert "song-markers" not in data
    assert load_manifest(project).song_markers == ()


def test_manifest_round_trip_with_song_markers(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    manifest = ProjectManifest(
        version=1,
        slug="song",
        mix_filename="song.flac",
        original_path=str((tmp_path / "source.flac").resolve()),
        separated_at="2026-06-08T20:15:00+00:00",
        demucs_model="htdemucs",
        restored_from="original-slug",
        song_markers=(
            SongMarker(8.25, "standard"),
            SongMarker(64.5, "crescendo"),
            SongMarker(120.0, "diminuendo"),
        ),
    )
    with (project / PROJECT_FILENAME).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest.to_dict(), handle, sort_keys=False)

    loaded = load_manifest(project)
    assert loaded == manifest

    with (project / PROJECT_FILENAME).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert data["version"] == 1
    assert data["song-markers"] == [
        {"time": 8.25, "type": "standard"},
        {"time": 64.5, "type": "crescendo"},
        {"time": 120.0, "type": "diminuendo"},
    ]
    assert data["restored-from"] == "original-slug"
    assert data["ingest"]["demucs_model"] == "htdemucs"


def test_manifest_loads_bare_float_song_markers_as_standard(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    with (project / PROJECT_FILENAME).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            {
                "version": 1,
                "slug": "song",
                "mix": {"filename": "song.flac"},
                "ingest": {
                    "original_path": "/tmp/source.flac",
                    "separated_at": "2026-06-08T20:15:00+00:00",
                    "demucs_model": "htdemucs",
                },
                "song-markers": [8.25, 64.5],
            },
            handle,
            sort_keys=False,
        )

    loaded = load_manifest(project)
    assert loaded.song_markers == (SongMarker(8.25), SongMarker(64.5))



def test_write_manifest_update_preserves_song_markers_and_restored_from(
    tmp_path: Path,
) -> None:
    project = tmp_path / "song"
    project.mkdir()
    original = tmp_path / "source.flac"
    original.write_bytes(b"audio")
    when = datetime(2026, 6, 8, 20, 15, tzinfo=timezone.utc)
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=original,
        demucs_model="htdemucs",
        separated_at=when,
        song_markers=(10.0, 42.5),
    )
    rewrite_manifest_slug(project, "song", restored_from="archived-slug")

    new_original = tmp_path / "new-source.wav"
    new_original.write_bytes(b"new")
    later = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
    write_manifest(
        project,
        slug="song",
        mix_filename="song.wav",
        original_path=new_original,
        demucs_model="htdemucs_ft",
        separated_at=later,
    )

    manifest = load_manifest(project)
    assert manifest.mix_filename == "song.wav"
    assert manifest.original_path == str(new_original.resolve())
    assert manifest.separated_at == "2026-07-22T12:00:00+00:00"
    assert manifest.demucs_model == "htdemucs_ft"
    assert manifest.song_markers == (SongMarker(10.0), SongMarker(42.5))
    assert manifest.restored_from == "archived-slug"
    assert manifest.version == 1


def test_save_song_markers_preserves_ingest(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    original = tmp_path / "source.flac"
    original.write_bytes(b"audio")
    when = datetime(2026, 6, 8, 20, 15, tzinfo=timezone.utc)
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=original,
        demucs_model="htdemucs_ft",
        separated_at=when,
    )
    rewrite_manifest_slug(project, "song", restored_from="archived-slug")

    save_song_markers(
        project,
        (SongMarker(10.0, "crescendo"), SongMarker(42.5, "diminuendo")),
    )

    manifest = load_manifest(project)
    assert manifest.song_markers == (
        SongMarker(10.0, "crescendo"),
        SongMarker(42.5, "diminuendo"),
    )
    assert manifest.slug == "song"
    assert manifest.mix_filename == "song.flac"
    assert manifest.original_path == str(original.resolve())
    assert manifest.separated_at == "2026-06-08T20:15:00+00:00"
    assert manifest.demucs_model == "htdemucs_ft"
    assert manifest.restored_from == "archived-slug"
    assert manifest.version == 1

    with (project / PROJECT_FILENAME).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert data["ingest"] == {
        "original_path": str(original.resolve()),
        "separated_at": "2026-06-08T20:15:00+00:00",
        "demucs_model": "htdemucs_ft",
    }
    assert data["restored-from"] == "archived-slug"
    assert data["song-markers"] == [
        {"time": 10.0, "type": "crescendo"},
        {"time": 42.5, "type": "diminuendo"},
    ]


def test_manifest_round_trip_with_milkdrop(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    manifest = ProjectManifest(
        version=1,
        slug="song",
        mix_filename="song.flac",
        original_path=str((tmp_path / "source.flac").resolve()),
        separated_at="2026-06-08T20:15:00+00:00",
        demucs_model="htdemucs",
        milkdrop=MilkdropSettings(beat_sensitivity=1.5),
    )
    with (project / PROJECT_FILENAME).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest.to_dict(), handle, sort_keys=False)

    loaded = load_manifest(project)
    assert loaded == manifest
    with (project / PROJECT_FILENAME).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert data["milkdrop"] == {"beat_sensitivity": 1.5}


def test_manifest_omits_milkdrop_when_none(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )
    with (project / PROJECT_FILENAME).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert "milkdrop" not in data
    assert load_manifest(project).milkdrop is None


def test_write_manifest_update_preserves_milkdrop(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    original = tmp_path / "source.flac"
    original.write_bytes(b"audio")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=original,
        demucs_model="htdemucs",
        milkdrop=MilkdropSettings(beat_sensitivity=3.25),
    )
    write_manifest(
        project,
        slug="song",
        mix_filename="song.wav",
        original_path=tmp_path / "new-source.wav",
        demucs_model="htdemucs_ft",
    )
    manifest = load_manifest(project)
    assert manifest.mix_filename == "song.wav"
    assert manifest.milkdrop == MilkdropSettings(beat_sensitivity=3.25)


def test_save_milkdrop_settings_preserves_ingest_and_markers(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    original = tmp_path / "source.flac"
    original.write_bytes(b"audio")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=original,
        demucs_model="htdemucs_ft",
        song_markers=(10.0, 42.5),
    )
    rewrite_manifest_slug(project, "song", restored_from="archived-slug")
    save_milkdrop_settings(project, 6.0)

    manifest = load_manifest(project)
    assert manifest.milkdrop == MilkdropSettings(beat_sensitivity=5.0)
    assert [m.time for m in manifest.song_markers] == [10.0, 42.5]
    assert manifest.restored_from == "archived-slug"
    assert manifest.mix_filename == "song.flac"


def test_manifest_round_trip_with_compositor(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    manifest = ProjectManifest(
        version=1,
        slug="song",
        mix_filename="song.flac",
        original_path=str((tmp_path / "source.flac").resolve()),
        separated_at="2026-06-08T20:15:00+00:00",
        demucs_model="htdemucs",
        compositor=CompositorSettings(hdr=False),
    )
    with (project / PROJECT_FILENAME).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest.to_dict(), handle, sort_keys=False)

    loaded = load_manifest(project)
    assert loaded == manifest
    with (project / PROJECT_FILENAME).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert data["compositor"] == {"hdr": False}


def test_manifest_omits_compositor_when_none(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )
    with (project / PROJECT_FILENAME).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert "compositor" not in data
    assert load_manifest(project).compositor is None


def test_write_manifest_update_preserves_compositor(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    original = tmp_path / "source.flac"
    original.write_bytes(b"audio")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=original,
        demucs_model="htdemucs",
        compositor=CompositorSettings(hdr=False),
    )
    write_manifest(
        project,
        slug="song",
        mix_filename="song.wav",
        original_path=tmp_path / "new-source.wav",
        demucs_model="htdemucs_ft",
    )
    manifest = load_manifest(project)
    assert manifest.mix_filename == "song.wav"
    assert manifest.compositor == CompositorSettings(hdr=False)


def test_save_compositor_settings_preserves_ingest_and_markers(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    original = tmp_path / "source.flac"
    original.write_bytes(b"audio")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=original,
        demucs_model="htdemucs_ft",
        song_markers=(10.0, 42.5),
    )
    rewrite_manifest_slug(project, "song", restored_from="archived-slug")
    save_compositor_settings(project, False)

    manifest = load_manifest(project)
    assert manifest.compositor == CompositorSettings(hdr=False)
    assert [m.time for m in manifest.song_markers] == [10.0, 42.5]
    assert manifest.restored_from == "archived-slug"
    assert manifest.mix_filename == "song.flac"


def test_parse_compositor_defaults_hdr_when_section_omits_key(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )
    path = project / PROJECT_FILENAME
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["compositor"] = {}
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    assert load_manifest(project).compositor == CompositorSettings(hdr=True)


def test_parse_compositor_rejects_non_bool_hdr(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )
    path = project / PROJECT_FILENAME
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["compositor"] = {"hdr": 1}
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    with pytest.raises(ValueError, match="compositor.hdr"):
        load_manifest(project)


def test_save_render_settings_preserves_ingest_and_markers(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    original = tmp_path / "source.flac"
    original.write_bytes(b"audio")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=original,
        demucs_model="htdemucs_ft",
        song_markers=(10.0, 42.5),
    )
    rewrite_manifest_slug(project, "song", restored_from="archived-slug")
    save_render_settings(project, width=1280, height=720, fps=24)

    manifest = load_manifest(project)
    assert manifest.render == ProjectRenderSettings(width=1280, height=720, fps=24)
    assert [m.time for m in manifest.song_markers] == [10.0, 42.5]
    assert manifest.restored_from == "archived-slug"
    assert manifest.mix_filename == "song.flac"


def test_write_manifest_preserves_render_settings(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    original = tmp_path / "source.flac"
    original.write_bytes(b"audio")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=original,
        demucs_model="htdemucs",
        render=ProjectRenderSettings(width=3840, height=2160, fps=48),
    )
    write_manifest(
        project,
        slug="song",
        mix_filename="song.wav",
        original_path=tmp_path / "new-source.wav",
        demucs_model="htdemucs_ft",
    )
    manifest = load_manifest(project)
    assert manifest.mix_filename == "song.wav"
    assert manifest.render == ProjectRenderSettings(width=3840, height=2160, fps=48)


def test_parse_render_defaults_when_section_omits_keys(tmp_path: Path) -> None:
    from cleave.config_schema.project_render import (
        DEFAULT_RENDER_FPS,
        DEFAULT_RENDER_HEIGHT,
        DEFAULT_RENDER_WIDTH,
    )

    project = tmp_path / "song"
    project.mkdir()
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )
    path = project / PROJECT_FILENAME
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["render"] = {}
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    assert load_manifest(project).render == ProjectRenderSettings(
        width=DEFAULT_RENDER_WIDTH,
        height=DEFAULT_RENDER_HEIGHT,
        fps=DEFAULT_RENDER_FPS,
    )


def test_parse_render_rejects_non_int_width(tmp_path: Path) -> None:
    project = tmp_path / "song"
    project.mkdir()
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )
    path = project / PROJECT_FILENAME
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["render"] = {"width": "wide"}
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    with pytest.raises(ValueError, match="render.width"):
        load_manifest(project)


def _write_unknown_key(project: Path) -> None:
    path = project / PROJECT_FILENAME
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["custom_metadata"] = True
    data["milkdrop"] = {"beat_sensitivity": 4.0, "extra_pm": "keep"}
    data["compositor"] = {"hdr": True, "extra_comp": 1}
    data["render"] = {
        "width": 1920,
        "height": 1080,
        "fps": 60,
        "extra_render": "keep",
    }
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def _assert_unknown_keys_survive(project: Path) -> None:
    data = yaml.safe_load(
        (project / PROJECT_FILENAME).read_text(encoding="utf-8")
    )
    assert data["custom_metadata"] is True
    assert data["milkdrop"]["extra_pm"] == "keep"
    assert data["compositor"]["extra_comp"] == 1
    assert data["render"]["extra_render"] == "keep"


def _seed_manifest(tmp_path: Path) -> Path:
    project = tmp_path / "song"
    project.mkdir()
    write_manifest(
        project,
        slug="song",
        mix_filename="song.flac",
        original_path=tmp_path / "source.flac",
        demucs_model="htdemucs",
    )
    _write_unknown_key(project)
    return project


def test_save_song_markers_preserves_unknown_keys(tmp_path: Path) -> None:
    project = _seed_manifest(tmp_path)
    save_song_markers(project, (SongMarker(1.5),))
    _assert_unknown_keys_survive(project)
    assert load_manifest(project).song_markers == (SongMarker(1.5),)


def test_save_milkdrop_settings_preserves_unknown_keys(tmp_path: Path) -> None:
    project = _seed_manifest(tmp_path)
    save_milkdrop_settings(project, 2.5)
    _assert_unknown_keys_survive(project)
    assert load_manifest(project).milkdrop == MilkdropSettings(2.5)


def test_save_compositor_settings_preserves_unknown_keys(tmp_path: Path) -> None:
    project = _seed_manifest(tmp_path)
    save_compositor_settings(project, False)
    _assert_unknown_keys_survive(project)
    assert load_manifest(project).compositor == CompositorSettings(False)


def test_save_render_settings_preserves_unknown_keys(tmp_path: Path) -> None:
    project = _seed_manifest(tmp_path)
    save_render_settings(project, width=1280, height=720, fps=24)
    _assert_unknown_keys_survive(project)
    assert load_manifest(project).render == ProjectRenderSettings(1280, 720, 24)


def test_rewrite_manifest_slug_preserves_unknown_keys(tmp_path: Path) -> None:
    project = _seed_manifest(tmp_path)
    rewrite_manifest_slug(project, "new-slug", restored_from="old-slug")
    _assert_unknown_keys_survive(project)
    manifest = load_manifest(project)
    assert manifest.slug == "new-slug"
    assert manifest.restored_from == "old-slug"


def test_write_manifest_update_preserves_unknown_keys(tmp_path: Path) -> None:
    project = _seed_manifest(tmp_path)
    rewrite_manifest_slug(project, "song", restored_from="archived-slug")
    new_original = tmp_path / "new-source.wav"
    new_original.write_bytes(b"new")
    write_manifest(
        project,
        slug="song",
        mix_filename="song.wav",
        original_path=new_original,
        demucs_model="htdemucs_ft",
    )
    _assert_unknown_keys_survive(project)
    manifest = load_manifest(project)
    assert manifest.mix_filename == "song.wav"
    assert manifest.demucs_model == "htdemucs_ft"
    assert manifest.restored_from == "archived-slug"
