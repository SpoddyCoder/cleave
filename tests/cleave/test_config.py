"""Tests for Cleave YAML config parsing and serialization."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
import yaml

from cleave.config import (
    CONFIG_FILENAME,
    CleaveConfig,
    LayerConfig,
    PathsConfig,
    VisualizerConfig,
    clamp_beat_sensitivity,
    clamp_effect_pct,
    dump_yaml,
    find_config_path,
    load_config,
    _parse_layers,
)
from cleave.extract import STEM_NAMES
from tests.support.config import write_minimal_config

_LONG_PRESET = (
    "presets-cream-of-the-crop/Drawing/Dunes/"
    "LuxXx - Melt down the Engine inz+.milk"
)


def _preset_lines(dumped: str) -> list[str]:
    lines: list[str] = []
    collecting = False
    for line in dumped.splitlines():
        if line.strip().startswith("preset:"):
            collecting = True
            lines.append(line)
        elif collecting and line.startswith("      "):
            lines.append(line)
        elif collecting:
            break
    return lines


def _minimal_layers_raw(*, locked_stem: str | None = None) -> dict:
    layers: dict = {}
    for name in STEM_NAMES:
        entry: dict = {"preset": f"{name}/anchor.milk"}
        if name == locked_stem:
            entry["locked"] = True
        layers[name] = entry
    return layers


def test_dump_yaml_keeps_long_preset_on_one_line() -> None:
    data = {"layers": {"drums": {"preset": _LONG_PRESET}}}
    buf = io.StringIO()
    dump_yaml(data, buf)
    dumped = buf.getvalue()

    assert len(_preset_lines(dumped)) == 1
    loaded = yaml.safe_load(dumped)["layers"]["drums"]["preset"]
    assert loaded == _LONG_PRESET


def test_parse_layers_reads_locked_true() -> None:
    preset_root = Path("/tmp/presets")
    layers = _parse_layers(
        {"layers": _minimal_layers_raw(locked_stem="drums")},
        preset_root,
    )
    assert layers["drums"].locked is True
    for name in STEM_NAMES:
        if name != "drums":
            assert layers[name].locked is False


def test_clamp_effect_pct() -> None:
    assert clamp_effect_pct(-5) == 0
    assert clamp_effect_pct(150) == 100
    assert clamp_effect_pct(42.4) == 42


def test_clamp_beat_sensitivity() -> None:
    assert clamp_beat_sensitivity(-1) == 0
    assert clamp_beat_sensitivity(3.0) == 2.0
    assert clamp_beat_sensitivity(1.25) == 1.25


def test_layers_in_z_order_matches_reversed_layer_z_order() -> None:
    layer_z_order = ("other", "bass", "vocals", "drums")
    cfg = CleaveConfig(
        paths=PathsConfig(
            preset_root=Path("/tmp/presets"),
            texture_paths=(Path("/tmp/textures"),),
        ),
        layers={
            name: LayerConfig(preset=Path(f"/tmp/presets/{name}/anchor.milk"))
            for name in STEM_NAMES
        },
        visualizer=VisualizerConfig(),
        config_path=Path("/tmp/cleave.config.yaml"),
        layer_z_order=layer_z_order,
    )
    names = [name for name, _ in cfg.layers_in_z_order()]
    assert names == list(reversed(layer_z_order))


def test_load_config_clamps_beat_sensitivity(tmp_path: Path) -> None:
    preset_root = tmp_path / "presets"
    project_dir = tmp_path / "project"
    write_minimal_config(project_dir, preset_root)
    cfg_path = project_dir / CONFIG_FILENAME
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    data["visualizer"]["beat_sensitivity"] = 3.0
    data["layers"]["drums"]["beat_sensitivity"] = -1
    with cfg_path.open("w", encoding="utf-8") as handle:
        dump_yaml(data, handle)

    cfg = load_config(project_root=project_dir)
    assert cfg.visualizer.beat_sensitivity == 2.0
    assert cfg.layers["drums"].beat_sensitivity == 0.0


def test_parse_layers_reads_effects() -> None:
    preset_root = Path("/tmp/presets")
    layers_raw = {
        name: {"preset": f"{name}/anchor.milk"} for name in STEM_NAMES
    }
    layers_raw["drums"]["effects"] = {"pulse": {"onset": 75}}
    layers = _parse_layers({"layers": layers_raw}, preset_root)
    assert layers["drums"].effects == {"pulse": {"onset": 75}}
    assert layers["bass"].effects == {}


def test_parse_layers_rejects_invalid_effect() -> None:
    preset_root = Path("/tmp/presets")
    layers_raw = {
        name: {"preset": f"{name}/anchor.milk"} for name in STEM_NAMES
    }
    layers_raw["drums"]["effects"] = {"ripple": {"onset": 10}}
    with pytest.raises(ValueError, match="unknown effect"):
        _parse_layers({"layers": layers_raw}, preset_root)


def test_find_config_path_cli_override_wins(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    project_config = project / CONFIG_FILENAME
    project_config.write_text("visualizer: {}\n", encoding="utf-8")

    override = tmp_path / "override.yaml"
    override.write_text("visualizer: {}\n", encoding="utf-8")

    found = find_config_path(config_path=override, project_root=project)
    assert found == override.resolve()


def test_find_config_path_project_config(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    project_config = project / CONFIG_FILENAME
    project_config.write_text("visualizer: {}\n", encoding="utf-8")

    found = find_config_path(project_root=project)
    assert found == project_config.resolve()


def test_find_config_path_global_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    global_config = tmp_path / "global" / CONFIG_FILENAME
    global_config.parent.mkdir(parents=True)
    global_config.write_text("visualizer: {}\n", encoding="utf-8")
    monkeypatch.setattr("cleave.config.GLOBAL_CONFIG_PATH", global_config)

    found = find_config_path(project_root=tmp_path / "no-config-here")
    assert found == global_config.resolve()


def test_load_config_round_trip(minimal_project: Path) -> None:
    cfg = load_config(project_root=minimal_project)
    assert cfg.config_path == (minimal_project / CONFIG_FILENAME).resolve()
    assert set(cfg.layers) == set(STEM_NAMES)
    assert cfg.visualizer.width > 0
    assert cfg.paths.preset_root.is_dir()
    for name in STEM_NAMES:
        assert cfg.layers[name].preset.is_file()


def _write_invalid_config(project_dir: Path, preset_root: Path, **overrides) -> Path:
    return write_minimal_config(project_dir, preset_root, **overrides)


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        (
            {"layer_z_order": ["drums", "bass", "vocals"]},
            "layer_z_order must contain exactly",
        ),
        (
            {
                "layers": {
                    **{
                        name: {
                            "preset": f"{name}/{name}.milk",
                            "enabled": True,
                            "opacity": 1.0,
                            "width": 1280,
                            "height": 720,
                            "blend_mode": "black-key",
                        }
                        for name in STEM_NAMES
                    },
                    "guitars": {"preset": "guitars/guitars.milk"},
                }
            },
            "unknown layer keys",
        ),
        (
            {
                "layers": {
                    name: {
                        "preset": f"{name}/{name}.milk",
                        "enabled": True,
                        "opacity": 1.0,
                        "width": 1280,
                        "height": 720,
                        "blend_mode": "black-key",
                    }
                    for name in STEM_NAMES
                    if name != "other"
                }
            },
            "missing layer config",
        ),
        (
            {
                "layers": {
                    name: {
                        "preset": f"{name}/{name}.milk",
                        "enabled": True,
                        "opacity": 1.0,
                        "width": 1280,
                        "height": 720,
                        "blend_mode": "overlay" if name == "drums" else "black-key",
                    }
                    for name in STEM_NAMES
                }
            },
            "blend_mode must be one of",
        ),
    ],
)
def test_load_config_validation_errors(
    tmp_path: Path, overrides: dict, match: str
) -> None:
    preset_root = tmp_path / "presets"
    project_dir = tmp_path / "project"
    _write_invalid_config(project_dir, preset_root, **overrides)
    with pytest.raises(ValueError, match=match):
        load_config(project_root=project_dir)


def test_load_config_missing_preset_file(tmp_path: Path) -> None:
    preset_root = tmp_path / "presets"
    project_dir = tmp_path / "project"
    write_minimal_config(project_dir, preset_root)
    cfg_path = project_dir / CONFIG_FILENAME
    text = cfg_path.read_text(encoding="utf-8").replace(
        "drums/drums.milk", "drums/missing.milk"
    )
    cfg_path.write_text(text, encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="missing preset"):
        load_config(project_root=project_dir)
