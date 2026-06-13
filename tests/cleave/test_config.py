"""Tests for Cleave YAML config parsing and serialization."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
import yaml

from cleave.config import (
    DEFAULT_VIZ_CONFIG_FILENAME,
    PROJECT_VIZ_CONFIG_FILENAME,
    CleaveConfig,
    LayerConfig,
    PathsConfig,
    RenderOverlayBackgroundConfig,
    RenderOverlayBorderConfig,
    RenderConfig,
    RenderOverlayConfig,
    RenderOverlayTextBlockConfig,
    RenderPostFxConfig,
    VisualizerConfig,
    clamp_beat_sensitivity,
    clamp_effect_pct,
    dump_yaml,
    ensure_project_viz_config,
    find_config_path,
    load_config,
    project_viz_config_path,
    _parse_hex_colour,
    _parse_layers,
    _parse_render,
    _parse_visualizer,
)
from cleave.paths import repo_root
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
    assert clamp_beat_sensitivity(3.0) == 3.0
    assert clamp_beat_sensitivity(6.0) == 5.0
    assert clamp_beat_sensitivity(1.25) == 1.25


def test_parse_visualizer_name_defaults_to_render() -> None:
    cfg = _parse_visualizer({})
    assert cfg.name == "render"


def test_parse_visualizer_reads_name() -> None:
    cfg = _parse_visualizer({"visualizer": {"name": "buttercup-24"}})
    assert cfg.name == "buttercup-24"


def test_load_config_reads_visualizer_name(minimal_project: Path) -> None:
    cfg = load_config(project_root=minimal_project)
    assert cfg.visualizer.name == "cleave-test"


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
    cfg_path = project_dir / PROJECT_VIZ_CONFIG_FILENAME
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    data["visualizer"]["beat_sensitivity"] = 6.0
    data["layers"]["drums"]["beat_sensitivity"] = -1
    with cfg_path.open("w", encoding="utf-8") as handle:
        dump_yaml(data, handle)

    cfg = load_config(project_root=project_dir)
    assert cfg.visualizer.beat_sensitivity == 5.0
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
    project_config = project / PROJECT_VIZ_CONFIG_FILENAME
    project_config.write_text("visualizer: {}\n", encoding="utf-8")

    override = tmp_path / "override.yaml"
    override.write_text("visualizer: {}\n", encoding="utf-8")

    found = find_config_path(config_path=override, project_root=project)
    assert found == override.resolve()


def test_find_config_path_project_config(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    project_config = project / PROJECT_VIZ_CONFIG_FILENAME
    project_config.write_text("visualizer: {}\n", encoding="utf-8")

    found = find_config_path(project_root=project)
    assert found == project_config.resolve()


def test_find_config_path_repo_template_fallback(tmp_path: Path) -> None:
    found = find_config_path(project_root=tmp_path / "no-config-here")
    assert found == (repo_root() / DEFAULT_VIZ_CONFIG_FILENAME).resolve()


def test_ensure_project_viz_config_sets_project_name(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "song"
    dst = ensure_project_viz_config(project)
    assert dst == project_viz_config_path(project)
    assert dst.is_file()
    data = yaml.safe_load(dst.read_text(encoding="utf-8"))
    assert data["visualizer"]["name"] == "song"


def test_ensure_project_viz_config_skips_existing(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "song"
    project.mkdir(parents=True)
    existing = project / PROJECT_VIZ_CONFIG_FILENAME
    existing.write_text("custom: true\n", encoding="utf-8")

    dst = ensure_project_viz_config(project)
    assert dst == existing.resolve()
    assert existing.read_text(encoding="utf-8") == "custom: true\n"


def test_find_config_path_global_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    global_config = tmp_path / "global" / DEFAULT_VIZ_CONFIG_FILENAME
    global_config.parent.mkdir(parents=True)
    global_config.write_text("visualizer: {}\n", encoding="utf-8")
    monkeypatch.setattr("cleave.config.GLOBAL_CONFIG_PATH", global_config)

    found = find_config_path(project_root=tmp_path / "no-config-here")
    assert found == global_config.resolve()


def test_load_config_round_trip(minimal_project: Path) -> None:
    cfg = load_config(project_root=minimal_project)
    assert cfg.config_path == (minimal_project / PROJECT_VIZ_CONFIG_FILENAME).resolve()
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


_OVERLAY_YAML = """\
render:
  overlay:
    enabled: true
    title:
      content: |
        Cleave Final Render
      font-size: 24
      font-colour: "#ffffff"
      background-colour: "#3333ff"
      margin-bottom: 10
    body:
      content: |
        Place anything you like here
        Like musician names, year of release etc.
        Edit the cleave-viz.yaml to modify this message, colours etc.
      font-size: 18
      colour: "#ffffff"
      background-colour: "#3333ff"
    start_delay: 10
    display_time: 30
    position: bottom-left
    background:
      margin: 40
      padding: 20
      colour: "#000000"
      opacity: 0.7
      border:
        colour: "#ffffff"
        width: 4
"""


def test_parse_render_overlay_full_template() -> None:
    data = yaml.safe_load(_OVERLAY_YAML)
    render = _parse_render(data)
    assert render is not None
    overlay = render.overlay
    assert overlay == RenderOverlayConfig(
        enabled=True,
        title=RenderOverlayTextBlockConfig(
            content="Cleave Final Render",
            font="monospace",
            font_size=24,
            colour=(255, 255, 255),
            background_colour=(51, 51, 255),
            margin_bottom=10,
        ),
        body=RenderOverlayTextBlockConfig(
            content=(
                "Place anything you like here\n"
                "Like musician names, year of release etc.\n"
                "Edit the cleave-viz.yaml to modify this message, colours etc."
            ),
            font="monospace",
            font_size=18,
            colour=(255, 255, 255),
            background_colour=(51, 51, 255),
        ),
        start_delay=10.0,
        display_time=30.0,
        position="bottom-left",
        background=RenderOverlayBackgroundConfig(
            margin=40,
            padding=20,
            colour=(0, 0, 0),
            opacity=0.7,
            border=RenderOverlayBorderConfig(colour=(255, 255, 255), width=4),
        ),
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("#123", (0x11, 0x22, 0x33)),
        ("#ffaa00", (255, 170, 0)),
        ("#223344", (34, 51, 68)),
    ],
)
def test_parse_hex_colour(value: str, expected: tuple[int, int, int]) -> None:
    assert _parse_hex_colour(value, "test.colour") == expected


def test_parse_render_overlay_empty_background_colour() -> None:
    data = yaml.safe_load(_OVERLAY_YAML)
    data["render"]["overlay"]["body"]["background-colour"] = ""
    render = _parse_render(data)
    assert render is not None
    assert render.overlay is not None
    assert render.overlay.body.background_colour is None
    assert render.overlay.title.background_colour == (51, 51, 255)


def test_parse_render_overlay_missing_background_colour() -> None:
    data = yaml.safe_load(_OVERLAY_YAML)
    del data["render"]["overlay"]["title"]["background-colour"]
    render = _parse_render(data)
    assert render is not None
    assert render.overlay is not None
    assert render.overlay.title.background_colour is None


def test_parse_render_overlay_rejects_invalid_position() -> None:
    data = yaml.safe_load(_OVERLAY_YAML)
    data["render"]["overlay"]["position"] = "middle"
    with pytest.raises(ValueError, match="render.overlay.position must be one of"):
        _parse_render(data)


def test_parse_render_post_fx_defaults() -> None:
    data = yaml.safe_load(
        """\
render:
  post_fx:
    fade_in: 12
    fade_out: 3
"""
    )
    render = _parse_render(data)
    assert render == RenderConfig(
        overlay=None,
        post_fx=RenderPostFxConfig(
            enabled=True,
            fade_in=12.0,
            fade_out=3.0,
        ),
    )


def test_load_config_render_none_without_overlay_section(
    minimal_project: Path,
) -> None:
    cfg = load_config(project_root=minimal_project)
    assert cfg.render is None


def test_load_config_missing_preset_file(tmp_path: Path) -> None:
    preset_root = tmp_path / "presets"
    project_dir = tmp_path / "project"
    write_minimal_config(project_dir, preset_root)
    cfg_path = project_dir / PROJECT_VIZ_CONFIG_FILENAME
    text = cfg_path.read_text(encoding="utf-8").replace(
        "drums/drums.milk", "drums/missing.milk"
    )
    cfg_path.write_text(text, encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="missing preset"):
        load_config(project_root=project_dir)
