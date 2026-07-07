"""Tests for Cleave YAML config parsing and serialization."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
import yaml

from cleave.config import (
    VIZ_CONFIG_FILENAME,
    CleaveConfig,
    LayerConfig,
    PathsConfig,
    RenderOverlayBackgroundConfig,
    RenderOverlayBorderConfig,
    RenderConfig,
    RenderOverlayConfig,
    RenderOverlayTextBlockConfig,
    RenderPostFxConfig,
    TimelineConfig,
    VisualizerConfig,
    clamp_beat_sensitivity,
    clamp_effect_pct,
    clamp_upscale,
    dump_yaml,
    ensure_project_viz_config,
    find_config_path,
    load_config,
    project_viz_config_path,
    render_output_size,
    render_hdr_compositing,
    _parse_layers,
)
from tests.support.config import default_highlight_rolloff_config, default_render_post_fx_config
from cleave.config_schema import (
    DEFAULT_HDR_COMPOSITING,
    DEFAULT_LAYER_SLOTS,
    DEFAULT_RENDER_HEIGHT,
    DEFAULT_RENDER_WIDTH,
    DEFAULT_UI_FADE_SEC,
    DEFAULT_UI_WIDTH,
    DEFAULT_UI_WIDTH_MODE,
    DEFAULT_VISUALIZER_PREVIEW_QUALITY,
    MAX_LAYER_COUNT,
    ParseCtx,
    PersistCtx,
    next_layer_slot,
    parse_hex_colour,
    parse_render_section,
    parse_timeline_section,
    parse_visualizer_section,
    persist_render,
    persist_visualizer,
    template_layer_entry,
    template_visualizer_section,
)
from cleave.user_config import EditorSettings
from cleave.viz.session import TuningSession
from cleave.paths import repo_root
from cleave.extract import STEM_NAMES
from cleave.timeline import TimelineCue
from tests.support.config import (
    TEST_LAYER_STEMS,
    slot_for_stem,
    write_minimal_config,
    write_user_config_file,
)

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


def _timeline_parse_ctx(
    slots: tuple[str, ...] = DEFAULT_LAYER_SLOTS,
) -> ParseCtx:
    return ParseCtx(layer_slots=slots)


def _layer_slots_raw(slots: list[str]) -> dict:
    stem_cycle = ["drums", "bass", "vocals", "other"]
    layers: dict = {}
    for slot in slots:
        stem = TEST_LAYER_STEMS.get(
            slot, stem_cycle[(int(slot.split("_")[1]) - 1) % len(stem_cycle)]
        )
        layers[slot] = {
            **template_layer_entry(slot, stem=stem),
            "preset": f"{stem}/{stem}.milk",
        }
    return layers


def _write_config_with_slots(
    project_dir: Path, preset_root: Path, slots: list[str], **overrides
) -> Path:
    data_overrides = {
        "layers": _layer_slots_raw(slots),
        "layer_z_order": list(slots),
    }
    data_overrides.update(overrides)
    return write_minimal_config(project_dir, preset_root, **data_overrides)


def _minimal_layers_raw(*, locked_slot: str | None = None) -> dict:
    layers: dict = {}
    for slot in DEFAULT_LAYER_SLOTS:
        stem = TEST_LAYER_STEMS[slot]
        entry: dict = {
            **template_layer_entry(slot, stem=stem),
            "preset": f"{stem}/anchor.milk",
        }
        if slot == locked_slot:
            entry["locked"] = True
        layers[slot] = entry
    return layers


def test_dump_yaml_keeps_long_preset_on_one_line() -> None:
    data = {"layers": {"layer_1": {"stem": "drums", "preset": _LONG_PRESET}}}
    buf = io.StringIO()
    dump_yaml(data, buf)
    dumped = buf.getvalue()

    assert len(_preset_lines(dumped)) == 1
    loaded = yaml.safe_load(dumped)["layers"]["layer_1"]["preset"]
    assert loaded == _LONG_PRESET


def test_parse_layers_reads_locked_true() -> None:
    preset_root = Path("/tmp/presets")
    layers, _ = _parse_layers(
        {"layers": _minimal_layers_raw(locked_slot="layer_1")},
        preset_root,
    )
    assert layers["layer_1"].locked is True
    for slot in DEFAULT_LAYER_SLOTS:
        if slot != "layer_1":
            assert layers[slot].locked is False


def test_clamp_effect_pct() -> None:
    assert clamp_effect_pct(-5) == 0
    assert clamp_effect_pct(150) == 100
    assert clamp_effect_pct(42.4) == 42


def test_clamp_beat_sensitivity() -> None:
    assert clamp_beat_sensitivity(-1) == 0
    assert clamp_beat_sensitivity(3.0) == 3.0
    assert clamp_beat_sensitivity(6.0) == 5.0
    assert clamp_beat_sensitivity(1.25) == 1.25


def test_clamp_upscale() -> None:
    assert clamp_upscale(1.0) == 1.0
    assert clamp_upscale(1.5) == 1.5
    assert clamp_upscale(0.5) == 1.0


def test_parse_visualizer_upscale_defaults_to_one() -> None:
    cfg = parse_visualizer_section({})
    assert cfg.upscale == 1.0


def test_parse_visualizer_reads_upscale() -> None:
    cfg = parse_visualizer_section({"visualizer": {"upscale": 2.0}})
    assert cfg.upscale == 2.0


def test_parse_visualizer_rejects_upscale_below_one() -> None:
    with pytest.raises(ValueError, match="visualizer.upscale must be >= 1.0"):
        parse_visualizer_section({"visualizer": {"upscale": 0.5}})


def test_visualizer_display_dimensions() -> None:
    cfg = VisualizerConfig(width=1280, height=720, upscale=1.5)
    assert cfg.display_width == 1920
    assert cfg.display_height == 1080

    cfg_round = VisualizerConfig(width=100, height=100, upscale=1.33)
    assert cfg_round.display_width == 133
    assert cfg_round.display_height == 133


def test_parse_visualizer_name_defaults_to_render() -> None:
    cfg = parse_visualizer_section({})
    assert cfg.name == "render"


def test_parse_visualizer_reads_name() -> None:
    cfg = parse_visualizer_section({"visualizer": {"name": "buttercup-24"}})
    assert cfg.name == "buttercup-24"


def test_parse_visualizer_preview_quality_defaults_to_balanced() -> None:
    cfg = parse_visualizer_section({})
    assert cfg.preview_quality == DEFAULT_VISUALIZER_PREVIEW_QUALITY


def test_parse_visualizer_ui_fade_defaults_to_ten() -> None:
    cfg = parse_visualizer_section({})
    assert cfg.ui_fade == DEFAULT_UI_FADE_SEC


def test_parse_visualizer_ui_width_defaults_to_one_ten() -> None:
    cfg = parse_visualizer_section({})
    assert cfg.ui_width == DEFAULT_UI_WIDTH


def test_parse_visualizer_ui_width_mode_defaults_to_flexible() -> None:
    cfg = parse_visualizer_section({})
    assert cfg.ui_width_mode == DEFAULT_UI_WIDTH_MODE


def test_parse_visualizer_ignores_editor_fields_in_project_yaml() -> None:
    cfg = parse_visualizer_section(
        {
            "visualizer": {
                "preview_quality": "performance",
                "ui_width_mode": "fixed",
                "ui_width": 80,
                "ui_fade": 25,
            }
        }
    )
    assert cfg.preview_quality == DEFAULT_VISUALIZER_PREVIEW_QUALITY
    assert cfg.ui_width_mode == DEFAULT_UI_WIDTH_MODE
    assert cfg.ui_width == DEFAULT_UI_WIDTH
    assert cfg.ui_fade == DEFAULT_UI_FADE_SEC


def test_parse_visualizer_section_accepts_editor_override() -> None:
    editor = EditorSettings(
        preview_quality="performance",
        ui_width_mode="fixed",
        ui_width=80,
        ui_fade=25.0,
    )
    cfg = parse_visualizer_section(
        {"visualizer": {"preview_quality": "ultra-performance", "ui_fade": 99}},
        editor=editor,
    )
    assert cfg.preview_quality == "performance"
    assert cfg.ui_width_mode == "fixed"
    assert cfg.ui_width == 80
    assert cfg.ui_fade == 25.0


def test_template_visualizer_section_omits_editor_fields() -> None:
    section = template_visualizer_section(name="test")
    assert section["name"] == "test"
    assert "width" in section
    assert "preview_quality" not in section
    assert "ui_width_mode" not in section
    assert "ui_width" not in section
    assert "ui_fade" not in section


def test_persist_visualizer_omits_editor_fields() -> None:
    cfg = CleaveConfig(
        paths=PathsConfig(
            preset_root=Path("/tmp/presets"),
            texture_paths=(Path("/tmp/textures"),),
        ),
        layers={},
        visualizer=VisualizerConfig(
            preview_quality="performance",
            ui_width_mode="fixed",
            ui_width=80,
            ui_fade=25.0,
        ),
        config_path=Path("/tmp/cleave-viz.yaml"),
        user_config_path=Path("/tmp/user-config.yaml"),
        layer_z_order=[],
        render=RenderConfig(),
        timeline=None,
    )
    ctx = PersistCtx(cfg=cfg, session=TuningSession(layer_z_order=[]), cfg_dir=Path("/tmp"))
    out = persist_visualizer(ctx)
    assert "width" in out
    assert "preview_quality" not in out
    assert "ui_width_mode" not in out
    assert "ui_width" not in out
    assert "ui_fade" not in out


def test_load_config_reads_visualizer_name(minimal_project: Path) -> None:
    cfg = load_config(project_root=minimal_project)
    assert cfg.visualizer.name == "cleave-test"


def test_layers_in_z_order_matches_reversed_layer_z_order() -> None:
    layer_z_order = ["layer_4", "layer_2", "layer_3", "layer_1"]
    cfg = CleaveConfig(
        paths=PathsConfig(
            preset_root=Path("/tmp/presets"),
            texture_paths=(Path("/tmp/textures"),),
        ),
        layers={
            slot: LayerConfig(
                preset=Path(
                    f"/tmp/presets/{TEST_LAYER_STEMS[slot]}/anchor.milk"
                ),
                stem=TEST_LAYER_STEMS[slot],
            )
            for slot in DEFAULT_LAYER_SLOTS
        },
        visualizer=VisualizerConfig(),
        config_path=Path("/tmp/cleave.config.yaml"),
        user_config_path=Path("/tmp/user-config.yaml"),
        layer_z_order=layer_z_order,
    )
    names = [name for name, _ in cfg.layers_in_z_order()]
    assert names == list(reversed(layer_z_order))


def test_load_config_clamps_beat_sensitivity(tmp_path: Path) -> None:
    preset_root = tmp_path / "presets"
    project_dir = tmp_path / "project"
    write_minimal_config(project_dir, preset_root)
    cfg_path = project_dir / VIZ_CONFIG_FILENAME
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    data["visualizer"]["beat_sensitivity"] = 6.0
    data["layers"]["layer_1"]["beat_sensitivity"] = -1
    with cfg_path.open("w", encoding="utf-8") as handle:
        dump_yaml(data, handle)

    cfg = load_config(project_root=project_dir)
    assert cfg.visualizer.beat_sensitivity == 5.0
    assert cfg.layers["layer_1"].beat_sensitivity == 0.0


def test_parse_layers_reads_effects() -> None:
    preset_root = Path("/tmp/presets")
    layers_raw = _minimal_layers_raw()
    layers_raw["layer_1"]["effects"] = {"pulse": {"onset": 75}}
    layers, _ = _parse_layers({"layers": layers_raw}, preset_root)
    assert layers["layer_1"].effects == {"pulse": {"onset": 75}}
    assert layers["layer_2"].effects == {}


def test_parse_layers_rejects_invalid_effect() -> None:
    preset_root = Path("/tmp/presets")
    layers_raw = _minimal_layers_raw()
    layers_raw["layer_1"]["effects"] = {"ripple": {"onset": 10}}
    with pytest.raises(ValueError, match="unknown effect"):
        _parse_layers({"layers": layers_raw}, preset_root)


def test_find_config_path_cli_override_wins(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    project_config = project / VIZ_CONFIG_FILENAME
    project_config.write_text("visualizer: {}\n", encoding="utf-8")

    override = tmp_path / "override.yaml"
    override.write_text("visualizer: {}\n", encoding="utf-8")

    found = find_config_path(config_path=override, project_root=project)
    assert found == override.resolve()


def test_find_config_path_project_config(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    project_config = project / VIZ_CONFIG_FILENAME
    project_config.write_text("visualizer: {}\n", encoding="utf-8")

    found = find_config_path(project_root=project)
    assert found == project_config.resolve()


def test_find_config_path_repo_template_fallback(tmp_path: Path) -> None:
    found = find_config_path(project_root=tmp_path / "no-config-here")
    assert found == (repo_root() / VIZ_CONFIG_FILENAME).resolve()


def test_load_config_project_paths_override_user_paths(tmp_path: Path) -> None:
    user_preset = tmp_path / "user-presets"
    user_texture = tmp_path / "user-textures"
    user_texture.mkdir()
    user_preset.mkdir()

    project_preset = tmp_path / "project-presets"
    project_texture = tmp_path / "project-textures"

    user_cfg_path = tmp_path / "user-config.yaml"
    write_user_config_file(
        user_cfg_path,
        preset_root=user_preset,
        texture_paths=(user_texture,),
    )

    project_dir = tmp_path / "project"
    write_minimal_config(
        project_dir,
        project_preset,
        paths={
            "preset_root": str(project_preset),
            "texture_paths": [str(project_texture)],
        },
    )

    cfg = load_config(project_root=project_dir, user_config_path=user_cfg_path)
    assert cfg.paths.preset_root == project_preset.resolve()
    assert cfg.paths.texture_paths == (project_texture.resolve(),)


def test_load_config_user_paths_when_project_omits_paths(tmp_path: Path) -> None:
    user_preset = tmp_path / "user-presets"
    user_texture = tmp_path / "user-textures"
    user_texture.mkdir()

    user_cfg_path = tmp_path / "user-config.yaml"
    write_user_config_file(
        user_cfg_path,
        preset_root=user_preset,
        texture_paths=(user_texture,),
    )

    project_dir = tmp_path / "project"
    write_minimal_config(project_dir, user_preset)
    cfg_path = project_dir / VIZ_CONFIG_FILENAME
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    del data["paths"]
    with cfg_path.open("w", encoding="utf-8") as handle:
        dump_yaml(data, handle)

    cfg = load_config(project_root=project_dir, user_config_path=user_cfg_path)
    assert cfg.paths.preset_root == user_preset.resolve()
    assert cfg.paths.texture_paths == (user_texture.resolve(),)


def test_load_config_editor_settings_from_user_config(tmp_path: Path) -> None:
    editor = EditorSettings(
        preview_quality="performance",
        ui_width_mode="fixed",
        ui_width=80,
        ui_fade=25.0,
    )
    user_cfg_path = tmp_path / "user-config.yaml"
    write_user_config_file(user_cfg_path, editor=editor)

    project_dir = tmp_path / "project"
    preset_root = tmp_path / "presets"
    write_minimal_config(project_dir, preset_root)

    cfg = load_config(project_root=project_dir, user_config_path=user_cfg_path)
    assert cfg.visualizer.preview_quality == "performance"
    assert cfg.visualizer.ui_width_mode == "fixed"
    assert cfg.visualizer.ui_width == 80
    assert cfg.visualizer.ui_fade == 25.0
    assert cfg.user_config_path == user_cfg_path.resolve()


def test_load_config_ignores_editor_fields_in_project_yaml(tmp_path: Path) -> None:
    user_editor = EditorSettings(
        preview_quality="performance",
        ui_width_mode="fixed",
        ui_width=80,
        ui_fade=25.0,
    )
    user_cfg_path = tmp_path / "user-config.yaml"
    write_user_config_file(user_cfg_path, editor=user_editor)

    project_dir = tmp_path / "project"
    preset_root = tmp_path / "presets"
    write_minimal_config(
        project_dir,
        preset_root,
        visualizer={
            **template_visualizer_section(name="cleave-test"),
            "preview_quality": "ultra-performance",
            "ui_width_mode": "flexible",
            "ui_width": 200,
            "ui_fade": 99,
        },
    )

    cfg = load_config(project_root=project_dir, user_config_path=user_cfg_path)
    assert cfg.visualizer.preview_quality == "performance"
    assert cfg.visualizer.ui_width_mode == "fixed"
    assert cfg.visualizer.ui_width == 80
    assert cfg.visualizer.ui_fade == 25.0


def test_load_config_round_trip(minimal_project: Path) -> None:
    cfg = load_config(project_root=minimal_project)
    assert cfg.config_path == (minimal_project / VIZ_CONFIG_FILENAME).resolve()
    assert set(cfg.layers) == set(DEFAULT_LAYER_SLOTS)
    assert cfg.visualizer.width > 0
    assert cfg.paths.preset_root.is_dir()
    for slot in DEFAULT_LAYER_SLOTS:
        assert cfg.layers[slot].preset.is_file()


def test_repo_template_omits_editor_fields_and_paths() -> None:
    data = yaml.safe_load((repo_root() / VIZ_CONFIG_FILENAME).read_text(encoding="utf-8"))
    visualizer = data["visualizer"]
    assert "preview_quality" not in visualizer
    assert "ui_width_mode" not in visualizer
    assert "ui_width" not in visualizer
    assert "ui_fade" not in visualizer
    assert "paths" not in data
    assert "layers" in data
    assert "render" in data


def test_ensure_project_viz_config_sets_project_name(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "song"
    dst = ensure_project_viz_config(project)
    assert dst == project_viz_config_path(project)
    assert dst.is_file()
    data = yaml.safe_load(dst.read_text(encoding="utf-8"))
    assert data["visualizer"]["name"] == "song"
    assert "preview_quality" not in data["visualizer"]
    assert "paths" not in data


def test_ensure_project_viz_config_skips_existing(tmp_path: Path) -> None:
    project = tmp_path / "projects" / "song"
    project.mkdir(parents=True)
    existing = project / VIZ_CONFIG_FILENAME
    existing.write_text("custom: true\n", encoding="utf-8")

    dst = ensure_project_viz_config(project)
    assert dst == existing.resolve()
    assert existing.read_text(encoding="utf-8") == "custom: true\n"


def _write_invalid_config(project_dir: Path, preset_root: Path, **overrides) -> Path:
    return write_minimal_config(project_dir, preset_root, **overrides)


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        (
            {"layer_z_order": ["layer_1", "layer_2", "layer_3"]},
            "layer_z_order must contain exactly",
        ),
        (
            {
                "layers": {
                    **{
                        slot: {
                            **template_layer_entry(slot, stem=TEST_LAYER_STEMS[slot]),
                            "preset": (
                                f"{TEST_LAYER_STEMS[slot]}/"
                                f"{TEST_LAYER_STEMS[slot]}.milk"
                            ),
                        }
                        for slot in DEFAULT_LAYER_SLOTS
                    },
                    "guitars": {"stem": "drums", "preset": "guitars/guitars.milk"},
                }
            },
            "invalid layer key",
        ),
        (
            {"layers": {}},
            "layers section must contain at least one layer",
        ),
        (
            {
                "layers": {
                    "layer_0": {
                        **template_layer_entry("layer_1", stem="drums"),
                        "preset": "drums/drums.milk",
                    }
                }
            },
            "invalid layer key 'layer_0'",
        ),
        (
            {
                "layers": {
                    "layer_9": {
                        **template_layer_entry("layer_1", stem="drums"),
                        "preset": "drums/drums.milk",
                    }
                }
            },
            "invalid layer key 'layer_9'",
        ),
        (
            {
                "layers": {
                    slot: {
                        **template_layer_entry(slot, stem=TEST_LAYER_STEMS[slot]),
                        "preset": (
                            f"{TEST_LAYER_STEMS[slot]}/"
                            f"{TEST_LAYER_STEMS[slot]}.milk"
                        ),
                        "blend_mode": "overlay" if slot == "layer_1" else "black-key",
                    }
                    for slot in DEFAULT_LAYER_SLOTS
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
    render = parse_render_section(data)
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
def testparse_hex_colour(value: str, expected: tuple[int, int, int]) -> None:
    assert parse_hex_colour(value, "test.colour") == expected


def test_parse_render_overlay_empty_background_colour() -> None:
    data = yaml.safe_load(_OVERLAY_YAML)
    data["render"]["overlay"]["body"]["background-colour"] = ""
    render = parse_render_section(data)
    assert render is not None
    assert render.overlay is not None
    assert render.overlay.body.background_colour is None
    assert render.overlay.title.background_colour == (51, 51, 255)


def test_parse_render_overlay_missing_background_colour() -> None:
    data = yaml.safe_load(_OVERLAY_YAML)
    del data["render"]["overlay"]["title"]["background-colour"]
    render = parse_render_section(data)
    assert render is not None
    assert render.overlay is not None
    assert render.overlay.title.background_colour is None


def test_parse_render_overlay_rejects_invalid_position() -> None:
    data = yaml.safe_load(_OVERLAY_YAML)
    data["render"]["overlay"]["position"] = "middle"
    with pytest.raises(ValueError, match="render.overlay.position must be one of"):
        parse_render_section(data)


def test_parse_render_width_height_defaults() -> None:
    render = parse_render_section({"render": {"fps": 24}})
    assert render is not None
    assert render.width == DEFAULT_RENDER_WIDTH
    assert render.height == DEFAULT_RENDER_HEIGHT


def test_parse_render_width_height_explicit() -> None:
    render = parse_render_section({"render": {"width": 1920, "height": 1080}})
    assert render is not None
    assert render.width == 1920
    assert render.height == 1080


def test_parse_render_hdr_compositing_defaults_true() -> None:
    render = parse_render_section({"render": {"fps": 24}})
    assert render is not None
    assert render.hdr_compositing is DEFAULT_HDR_COMPOSITING


def test_parse_render_hdr_compositing_explicit_false() -> None:
    render = parse_render_section({"render": {"hdr_compositing": False}})
    assert render is not None
    assert render.hdr_compositing is False


def test_render_hdr_compositing_false_without_render_section(
    minimal_project: Path,
) -> None:
    cfg = load_config(project_root=minimal_project)
    assert cfg.render is None
    assert render_hdr_compositing(cfg) is False


def test_persist_render_hdr_compositing_round_trip() -> None:
    render = parse_render_section(
        {"render": {"hdr_compositing": False, "fps": 24}}
    )
    assert render is not None
    cfg = CleaveConfig(
        paths=PathsConfig(preset_root=Path("/tmp"), texture_paths=()),
        layers={},
        visualizer=VisualizerConfig(),
        config_path=Path("/tmp/cleave-viz.yaml"),
        user_config_path=Path("/tmp/user-config.yaml"),
        render=render,
    )
    session = TuningSession(layer_z_order=[])
    payload = persist_render(PersistCtx(cfg=cfg, session=session, cfg_dir=None))
    assert payload["hdr_compositing"] is False

    round_trip = parse_render_section({"render": payload})
    assert round_trip is not None
    assert round_trip.hdr_compositing is False
    assert round_trip.fps == 24


def test_render_output_size_defaults_without_render_section(
    minimal_project: Path,
) -> None:
    cfg = load_config(project_root=minimal_project)
    assert render_output_size(cfg) == (DEFAULT_RENDER_WIDTH, DEFAULT_RENDER_HEIGHT)


def test_render_output_size_reads_render_section() -> None:
    render = parse_render_section({"render": {"width": 3840, "height": 2160}})
    assert render is not None
    cfg = CleaveConfig(
        paths=PathsConfig(preset_root=Path("/tmp"), texture_paths=()),
        layers={},
        visualizer=VisualizerConfig(),
        config_path=Path("/tmp/cleave-viz.yaml"),
        user_config_path=Path("/tmp/user-config.yaml"),
        render=render,
    )
    assert render_output_size(cfg) == (3840, 2160)


def test_parse_render_post_fx_defaults() -> None:
    data = yaml.safe_load(
        """\
render:
  post_fx:
    fade_in: 12
    fade_out: 3
"""
    )
    render = parse_render_section(data)
    assert render == RenderConfig(
        overlay=None,
        post_fx=default_render_post_fx_config(enabled=True, fade_in=12.0, fade_out=3.0),
    )


def test_parse_render_post_fx_highlight_rolloff_defaults() -> None:
    data = yaml.safe_load(
        """\
render:
  post_fx:
    highlight_rolloff:
      threshold_pct: 82
"""
    )
    render = parse_render_section(data)
    assert render is not None
    assert render.post_fx is not None
    hr = render.post_fx.highlight_rolloff
    assert hr.mode == "composite"
    assert hr.curve == "rolloff"
    assert hr.threshold_pct == 82
    assert hr.ceiling_pct == 65
    assert hr.strength_pct == 70
    assert hr.softness_pct == 40
    assert hr.desaturation_pct == 30


def test_parse_render_post_fx_chroma_boost_defaults() -> None:
    data = yaml.safe_load(
        """\
render:
  post_fx:
    chroma_boost:
      amount_pct: 40
"""
    )
    render = parse_render_section(data)
    assert render is not None
    assert render.post_fx is not None
    cb = render.post_fx.chroma_boost
    assert cb.mode == "off"
    assert cb.variant == "vibrance"
    assert cb.amount_pct == 40


@pytest.mark.parametrize("variant", ("saturation", "vibrance"))
def test_parse_render_post_fx_chroma_boost_valid_variants(variant: str) -> None:
    data = yaml.safe_load(
        f"""\
render:
  post_fx:
    chroma_boost:
      variant: {variant}
"""
    )
    render = parse_render_section(data)
    assert render is not None
    assert render.post_fx is not None
    assert render.post_fx.chroma_boost.variant == variant


@pytest.mark.parametrize("mode", ("off", "per_layer", "composite"))
def test_parse_render_post_fx_chroma_boost_valid_modes(mode: str) -> None:
    data = yaml.safe_load(
        f"""\
render:
  post_fx:
    chroma_boost:
      mode: {mode}
"""
    )
    render = parse_render_section(data)
    assert render is not None
    assert render.post_fx is not None
    assert render.post_fx.chroma_boost.mode == mode


@pytest.mark.parametrize("curve", ("rolloff", "smoothstep", "aces_fit"))
def test_parse_render_post_fx_highlight_rolloff_valid_curves(curve: str) -> None:
    data = yaml.safe_load(
        f"""\
render:
  post_fx:
    highlight_rolloff:
      curve: {curve}
"""
    )
    render = parse_render_section(data)
    assert render is not None
    assert render.post_fx is not None
    assert render.post_fx.highlight_rolloff.curve == curve


@pytest.mark.parametrize("mode", ("off", "per_layer", "composite"))
def test_parse_render_post_fx_highlight_rolloff_valid_modes(mode: str) -> None:
    data = yaml.safe_load(
        f"""\
render:
  post_fx:
    highlight_rolloff:
      mode: {mode}
"""
    )
    render = parse_render_section(data)
    assert render is not None
    assert render.post_fx is not None
    assert render.post_fx.highlight_rolloff.mode == mode


def test_parse_render_post_fx_highlight_rolloff_rejects_invalid_curve() -> None:
    data = yaml.safe_load(
        """\
render:
  post_fx:
    highlight_rolloff:
      curve: reinhard
"""
    )
    with pytest.raises(ValueError, match="curve must be one of"):
        parse_render_section(data)


def test_parse_render_post_fx_highlight_rolloff_rejects_invalid_mode() -> None:
    data = yaml.safe_load(
        """\
render:
  post_fx:
    highlight_rolloff:
      mode: reinhard
"""
    )
    with pytest.raises(ValueError, match="mode must be one of"):
        parse_render_section(data)


def test_parse_render_post_fx_highlight_rolloff_clamps() -> None:
    data = yaml.safe_load(
        """\
render:
  post_fx:
    highlight_rolloff:
      threshold_pct: 10
      ceiling_pct: 80
      strength_pct: 250
      softness_pct: -5
      desaturation_pct: 150
"""
    )
    render = parse_render_section(data)
    assert render is not None
    hr = render.post_fx.highlight_rolloff
    assert hr.threshold_pct == 10
    assert hr.ceiling_pct == 10
    assert hr.strength_pct == 200
    assert hr.softness_pct == 0
    assert hr.desaturation_pct == 100


def test_load_config_render_none_without_overlay_section(
    minimal_project: Path,
) -> None:
    cfg = load_config(project_root=minimal_project)
    assert cfg.render is None


def test_load_config_missing_preset_file(tmp_path: Path) -> None:
    preset_root = tmp_path / "presets"
    project_dir = tmp_path / "project"
    write_minimal_config(project_dir, preset_root)
    cfg_path = project_dir / VIZ_CONFIG_FILENAME
    text = cfg_path.read_text(encoding="utf-8").replace(
        "drums/drums.milk", "drums/missing.milk"
    )
    cfg_path.write_text(text, encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="missing preset"):
        load_config(project_root=project_dir)


def test_parse_timeline_defaults_enabled_true() -> None:
    timeline = parse_timeline_section(
        {"timeline": {}},
        _timeline_parse_ctx(),
    )
    assert timeline == TimelineConfig(enabled=True, cues=())


def test_parse_timeline_reads_cues_sorted_by_t() -> None:
    timeline = parse_timeline_section(
        {
            "timeline": {
                "enabled": True,
                "cues": [
                    {"t": 10.0, "layers": {"layer_1": False}},
                    {"t": 2.5, "layers": {"layer_2": True}},
                ],
            }
        },
        _timeline_parse_ctx(),
    )
    assert timeline is not None
    assert timeline.enabled is True
    assert timeline.cues == (
        TimelineCue(t=2.5, layers={"layer_2": True}),
        TimelineCue(t=10.0, layers={"layer_1": False}),
    )


def test_parse_timeline_rejects_unknown_stem() -> None:
    with pytest.raises(ValueError, match="unknown layer keys in timeline.cues"):
        parse_timeline_section(
            {
                "timeline": {
                    "cues": [{"t": 1.0, "layers": {"synth": True}}],
                }
            },
            _timeline_parse_ctx(),
        )


def test_parse_timeline_clamps_negative_t() -> None:
    with pytest.raises(ValueError, match="timeline.cues\\[0\\].t must be non-negative"):
        parse_timeline_section(
            {
                "timeline": {
                    "cues": [{"t": -1.0, "layers": {"layer_1": False}}],
                }
            },
            _timeline_parse_ctx(),
        )


def test_load_config_reads_timeline(minimal_project: Path) -> None:
    cfg_path = minimal_project / VIZ_CONFIG_FILENAME
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    data["timeline"] = {
        "enabled": True,
        "cues": [{"t": 3.0, "layers": {"layer_3": False}}],
    }
    with cfg_path.open("w", encoding="utf-8") as handle:
        dump_yaml(data, handle)

    cfg = load_config(project_root=minimal_project)
    assert cfg.timeline is not None
    assert cfg.timeline.enabled is True
    assert cfg.timeline.cues == (TimelineCue(t=3.0, layers={"layer_3": False}),)


def test_next_layer_slot_skips_used_slots() -> None:
    assert next_layer_slot(["layer_1", "layer_2"]) == "layer_3"


def test_next_layer_slot_raises_at_capacity() -> None:
    slots = [f"layer_{i}" for i in range(1, MAX_LAYER_COUNT + 1)]
    with pytest.raises(ValueError, match=f"Maximum {MAX_LAYER_COUNT} layers"):
        next_layer_slot(slots)


@pytest.mark.parametrize("count", [1, 8])
def test_load_config_accepts_variable_layer_count(
    tmp_path: Path, count: int
) -> None:
    preset_root = tmp_path / "presets"
    project_dir = tmp_path / "project"
    slots = [f"layer_{i}" for i in range(1, count + 1)]
    _write_config_with_slots(project_dir, preset_root, slots)
    cfg = load_config(project_root=project_dir)
    assert list(cfg.layers) == slots
    assert cfg.layer_z_order == slots


def test_load_config_rejects_z_order_for_missing_layer(tmp_path: Path) -> None:
    preset_root = tmp_path / "presets"
    project_dir = tmp_path / "project"
    _write_config_with_slots(
        project_dir,
        preset_root,
        ["layer_1", "layer_2", "layer_3"],
        layer_z_order=["layer_1", "layer_2", "layer_4"],
    )
    with pytest.raises(ValueError, match="layer_z_order must contain each of"):
        load_config(project_root=project_dir)


def test_parse_timeline_rejects_layer_not_in_config(tmp_path: Path) -> None:
    preset_root = tmp_path / "presets"
    project_dir = tmp_path / "project"
    _write_config_with_slots(project_dir, preset_root, ["layer_1", "layer_2"])
    cfg_path = project_dir / VIZ_CONFIG_FILENAME
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    data["timeline"] = {
        "cues": [{"t": 1.0, "layers": {"layer_3": True}}],
    }
    with cfg_path.open("w", encoding="utf-8") as handle:
        dump_yaml(data, handle)
    with pytest.raises(ValueError, match="unknown layer keys in timeline.cues"):
        load_config(project_root=project_dir)


def test_cleave_config_layer_z_order_defaults_to_list() -> None:
    cfg = CleaveConfig(
        paths=PathsConfig(
            preset_root=Path("/tmp/presets"),
            texture_paths=(Path("/tmp/textures"),),
        ),
        layers={},
        visualizer=VisualizerConfig(),
        config_path=Path("/tmp/cleave.config.yaml"),
        user_config_path=Path("/tmp/user-config.yaml"),
    )
    assert isinstance(cfg.layer_z_order, list)
    cfg.layer_z_order.append("layer_5")
    assert "layer_5" in cfg.layer_z_order

