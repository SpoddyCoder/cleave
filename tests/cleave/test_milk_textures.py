"""Tests for cleave.milk_textures."""

from __future__ import annotations

import filecmp
from pathlib import Path

from cleave.milk_textures import (
    extract_texture_names,
    project_texture_search_paths,
    resolve_texture_file,
    sync_project_textures,
)


def _write_milk(path: Path, *sampler_lines: str) -> None:
    body = "\n".join(sampler_lines)
    path.write_text(f"preset\n{body}\n", encoding="utf-8")


def test_extract_texture_names_custom_samplers(tmp_path: Path) -> None:
    milk = tmp_path / "test.milk"
    _write_milk(
        milk,
        "sampler sampler_clouds",
        "sampler sampler_fw_bricks",
        "sampler sampler_fc_metal",
        "sampler sampler_pw_glass",
        "sampler sampler_pc_wood",
    )
    assert extract_texture_names(milk) == {
        "clouds",
        "bricks",
        "metal",
        "glass",
        "wood",
    }


def test_extract_texture_names_skips_builtin_and_rand(tmp_path: Path) -> None:
    milk = tmp_path / "builtin.milk"
    _write_milk(
        milk,
        "sampler sampler_main",
        "sampler sampler_fw_main",
        "sampler sampler_fw_noise_hq",
        "sampler sampler_noise_lq",
        "sampler sampler_rand02",
        "sampler sampler_rand02_smalltiled",
        "sampler sampler_clouds",
    )
    assert extract_texture_names(milk) == {"clouds"}


def test_extract_texture_names_strips_filter_prefixes(tmp_path: Path) -> None:
    milk = tmp_path / "prefixed.milk"
    _write_milk(
        milk,
        "sampler sampler_fw_clouds",
        "sampler sampler_fc_plane",
    )
    assert extract_texture_names(milk) == {"clouds", "plane"}


def test_extract_texture_names_missing_file() -> None:
    assert extract_texture_names(Path("/no/such/file.milk")) == set()


def test_resolve_texture_file_finds_first_match(tmp_path: Path) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    first.mkdir()
    second.mkdir()
    (first / "tex.png").write_bytes(b"first")
    (second / "tex.jpg").write_bytes(b"second")

    found = resolve_texture_file("tex", [first, second])
    assert found == first / "tex.png"


def test_resolve_texture_file_finds_nested_match(tmp_path: Path) -> None:
    search = tmp_path / "textures"
    nested = search / "pack" / "textures"
    nested.mkdir(parents=True)
    (nested / "worms.jpg").write_bytes(b"worms")

    assert resolve_texture_file("worms", [search]) == nested / "worms.jpg"


def test_resolve_texture_file_multiple_extensions(tmp_path: Path) -> None:
    search = tmp_path / "textures"
    search.mkdir()
    (search / "brick.tga").write_bytes(b"data")

    assert resolve_texture_file("brick", [search]) == search / "brick.tga"
    assert resolve_texture_file("missing", [search]) is None


def test_sync_project_textures_copies_and_removes_orphans(tmp_path: Path) -> None:
    project = tmp_path / "project"
    presets = project / "presets"
    source = tmp_path / "source"
    presets.mkdir(parents=True)
    source.mkdir()
    (source / "clouds.png").write_bytes(b"clouds")
    (source / "bricks.jpg").write_bytes(b"bricks")

    milk = presets / "scene.milk"
    _write_milk(milk, "sampler sampler_clouds")

    textures = project / "textures"
    textures.mkdir()
    orphan = textures / "old.png"
    orphan.write_bytes(b"old")

    sync_project_textures(project, [milk], [source])

    copied = textures / "clouds.png"
    assert copied.is_file()
    assert filecmp.cmp(source / "clouds.png", copied, shallow=False)
    assert not orphan.exists()
    assert not (textures / "bricks.jpg").exists()


def test_sync_project_textures_idempotent(tmp_path: Path) -> None:
    project = tmp_path / "project"
    presets = project / "presets"
    source = tmp_path / "source"
    presets.mkdir(parents=True)
    source.mkdir()
    (source / "tex.png").write_bytes(b"data")
    milk = presets / "a.milk"
    _write_milk(milk, "sampler sampler_tex")

    sync_project_textures(project, [milk], [source])
    copied = project / "textures" / "tex.png"
    mtime = copied.stat().st_mtime

    sync_project_textures(project, [milk], [source])
    assert copied.stat().st_mtime == mtime


def test_sync_project_textures_keeps_existing_when_source_missing(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    presets = project / "presets"
    presets.mkdir(parents=True)
    textures = project / "textures"
    textures.mkdir()
    (textures / "kept.png").write_bytes(b"kept")
    milk = presets / "a.milk"
    _write_milk(milk, "sampler sampler_kept")

    sync_project_textures(project, [milk], [])

    assert (textures / "kept.png").read_bytes() == b"kept"


def test_project_texture_search_paths_prepends_when_present(tmp_path: Path) -> None:
    project = tmp_path / "project"
    bundled = project / "textures"
    bundled.mkdir(parents=True)
    global_tex = tmp_path / "global"

    assert project_texture_search_paths(project, [global_tex]) == [
        bundled,
        global_tex,
    ]


def test_project_texture_search_paths_unchanged_when_missing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    global_tex = tmp_path / "global"

    assert project_texture_search_paths(project, [global_tex]) == [global_tex]
