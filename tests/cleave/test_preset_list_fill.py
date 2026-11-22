"""New-project preset list fill."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
import yaml

from cleave.config import (
    ensure_project_viz_config,
    load_config,
    project_viz_config_path,
)
from cleave.preset_list_fill import (
    fill_new_project_preset_lists,
    needed_preset_count,
)

MILKDROP_ORIGINAL = Path("presets-milkdrop-original") / "Milkdrop-Original"


def _write_milk(folder: Path, count: int) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        (folder / f"preset_{index:03d}.milk").write_text(f"// {index}\n")


@pytest.fixture
def data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "data"
    monkeypatch.setenv("CLEAVE_DATA", str(root))
    return root


def _new_project(tmp_path: Path, duration_sec: float) -> Path:
    project = tmp_path / "projects" / "song"
    ensure_project_viz_config(project)
    (project / "signals.json").write_text(json.dumps({"duration_sec": duration_sec}))
    return project


def test_fills_each_layer_from_milkdrop_original(
    tmp_path: Path, data_root: Path
) -> None:
    _write_milk(data_root / "presets" / MILKDROP_ORIGINAL, 40)
    project = _new_project(tmp_path, 200.0)

    filled = fill_new_project_preset_lists(project, rng=random.Random(1))

    cfg = load_config(project_root=project)
    assert filled == list(cfg.layers)
    for layer in cfg.layers.values():
        expected = needed_preset_count(
            song_duration_sec=200.0,
            preset_duration=layer.preset_duration,
            trigger=layer.preset_switching_trigger,
        )
        assert len(layer.preset_switching_list) == expected
        assert all(entry.file.is_file() for entry in layer.preset_switching_list)
        assert all(
            entry.file.parent == (project / "presets").resolve()
            for entry in layer.preset_switching_list
        )


def test_count_is_capped_by_folder_size(tmp_path: Path, data_root: Path) -> None:
    _write_milk(data_root / "presets" / MILKDROP_ORIGINAL, 3)
    project = _new_project(tmp_path, 600.0)

    fill_new_project_preset_lists(project, rng=random.Random(1))

    cfg = load_config(project_root=project)
    assert all(len(layer.preset_switching_list) == 3 for layer in cfg.layers.values())


def test_template_layers_all_use_milkdrop_original(
    tmp_path: Path, data_root: Path
) -> None:
    _write_milk(data_root / "presets" / MILKDROP_ORIGINAL, 40)
    project = _new_project(tmp_path, 100.0)

    fill_new_project_preset_lists(project, rng=random.Random(1))

    folder = (data_root / "presets" / MILKDROP_ORIGINAL).resolve()
    for layer in load_config(project_root=project).layers.values():
        assert layer.preset == folder
        assert layer.preset_switching_list
        assert all(
            entry.source is not None and Path(entry.source).parent == folder
            for entry in layer.preset_switching_list
        )


def test_missing_folder_leaves_list_empty(tmp_path: Path, data_root: Path) -> None:
    project = _new_project(tmp_path, 100.0)

    assert fill_new_project_preset_lists(project) == []
    cfg = load_config(project_root=project)
    assert all(not layer.preset_switching_list for layer in cfg.layers.values())


def test_no_signals_leaves_config_alone(tmp_path: Path, data_root: Path) -> None:
    _write_milk(data_root / "presets" / MILKDROP_ORIGINAL, 40)
    project = tmp_path / "projects" / "song"
    ensure_project_viz_config(project)
    before = project_viz_config_path(project).read_text()

    assert fill_new_project_preset_lists(project) == []
    assert project_viz_config_path(project).read_text() == before
