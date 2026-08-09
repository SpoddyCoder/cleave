"""Config parse/persist for unified preset switching fields."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from cleave.config import CleaveConfig, LayerConfig, PathsConfig, EditorConfig
from cleave.config_schema import (
    DEFAULT_EASTER_EGG,
    DEFAULT_HARD_CUT_DURATION,
    DEFAULT_HARD_CUT_ENABLED,
    DEFAULT_HARD_CUT_SENSITIVITY,
    DEFAULT_PRESET_START_CLEAN,
    DEFAULT_PRESET_DURATION,
    DEFAULT_PRESET_SWITCHING,
    DEFAULT_PRESET_SWITCHING_TRIGGER,
    DEFAULT_SOFT_CUT_DURATION,
    ParseCtx,
    parse_layers_section,
    persist_layers,
    PersistCtx,
    template_layer_entry,
)
from cleave.config_snapshot import write_session_snapshot
from cleave.preset_playlist import PresetPlaylist
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.config import TEST_LAYER_STEMS


def _layer_yaml() -> dict:
    return {
        slot: {
            **template_layer_entry(slot, stem=TEST_LAYER_STEMS[slot]),
            "preset": f"{TEST_LAYER_STEMS[slot]}/{TEST_LAYER_STEMS[slot]}.milk",
        }
        for slot in ("layer_1",)
    }


def test_parse_layers_preset_switching_defaults_omitted() -> None:
    preset_root = Path("/tmp/presets")
    data = {"layers": _layer_yaml()}
    layers = parse_layers_section(data, ParseCtx(preset_root=preset_root))
    layer = layers["layer_1"]
    assert layer.preset_switching == DEFAULT_PRESET_SWITCHING
    assert layer.preset_switching_trigger == DEFAULT_PRESET_SWITCHING_TRIGGER
    assert layer.preset_duration == DEFAULT_PRESET_DURATION
    assert layer.soft_cut_duration == DEFAULT_SOFT_CUT_DURATION
    assert layer.hard_cut_duration == DEFAULT_HARD_CUT_DURATION
    assert layer.hard_cut_sensitivity == DEFAULT_HARD_CUT_SENSITIVITY
    assert layer.hard_cut_enabled == DEFAULT_HARD_CUT_ENABLED
    assert layer.easter_egg == DEFAULT_EASTER_EGG
    assert layer.preset_start_clean == DEFAULT_PRESET_START_CLEAN
    assert layer.preset_switching_list == []


def test_parse_layers_preset_switching_on() -> None:
    preset_root = Path("/tmp/presets")
    data = {"layers": _layer_yaml()}
    data["layers"]["layer_1"]["preset_switching"] = "on"
    data["layers"]["layer_1"]["preset_switching_trigger"] = "projectm"
    layers = parse_layers_section(data, ParseCtx(preset_root=preset_root))
    assert layers["layer_1"].preset_switching == "on"
    assert layers["layer_1"].preset_switching_trigger == "projectm"


def test_parse_layers_rejects_legacy_modes() -> None:
    preset_root = Path("/tmp/presets")
    for mode in ("none", "projectm", "timeline", "user_defined"):
        data = {"layers": _layer_yaml()}
        data["layers"]["layer_1"]["preset_switching"] = mode
        with pytest.raises(ValueError, match="preset_switching"):
            parse_layers_section(data, ParseCtx(preset_root=preset_root))


def test_parse_layers_rejects_bad_trigger() -> None:
    preset_root = Path("/tmp/presets")
    data = {"layers": _layer_yaml()}
    data["layers"]["layer_1"]["preset_switching_trigger"] = "beat"
    with pytest.raises(ValueError, match="preset_switching_trigger"):
        parse_layers_section(data, ParseCtx(preset_root=preset_root))


def test_parse_layers_accepts_timeline_trigger() -> None:
    preset_root = Path("/tmp/presets")
    data = {"layers": _layer_yaml()}
    data["layers"]["layer_1"]["preset_switching"] = "on"
    data["layers"]["layer_1"]["preset_switching_trigger"] = "timeline"
    layers = parse_layers_section(data, ParseCtx(preset_root=preset_root))
    assert layers["layer_1"].preset_switching_trigger == "timeline"


def test_parse_preset_switching_list_relative_to_cfg_dir(tmp_path: Path) -> None:
    milk = tmp_path / "presets" / "a.milk"
    milk.parent.mkdir(parents=True)
    milk.write_text("MILK")
    preset_root = tmp_path / "preset-root"
    preset_root.mkdir()
    data = {"layers": _layer_yaml()}
    data["layers"]["layer_1"]["preset_switching"] = "on"
    data["layers"]["layer_1"]["preset_switching_list"] = ["presets/a.milk"]
    layers = parse_layers_section(
        data, ParseCtx(preset_root=preset_root, cfg_dir=tmp_path)
    )
    assert layers["layer_1"].preset_switching_list == [milk.resolve()]


def test_persist_omits_defaults() -> None:
    cfg = CleaveConfig(
        paths=PathsConfig(
            preset_root=Path("/tmp/presets"),
            texture_paths=(Path("/tmp/textures"),),
        ),
        layers={
            "layer_1": LayerConfig(
                preset=Path("/tmp/presets/drums/a.milk"),
                stem="drums",
            )
        },
        editor=EditorConfig(),
        layer_z_order=["layer_1"],
        config_path=Path("/tmp/cleave.config.yaml"),
        user_config_path=Path("/tmp/user-config.yaml"),
    )
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=PresetPlaylist(
                    current_dir=Path("/tmp/presets/drums"),
                    paths=(Path("/tmp/presets/drums/a.milk"),),
                    index=0,
                ),
                browse_floor=Path("/tmp/presets/drums"),
                stem="drums",
            )
        },
    )
    out = persist_layers(PersistCtx(cfg=cfg, session=session, cfg_dir=Path("/tmp")))
    layer_out = out["layer_1"]
    assert "preset_switching" not in layer_out
    assert "preset_switching_trigger" not in layer_out
    assert "preset_switching_list" not in layer_out


def test_persist_writes_non_defaults(tmp_path: Path) -> None:
    milk = tmp_path / "presets" / "a.milk"
    milk.parent.mkdir()
    milk.write_text("MILK")
    cfg = CleaveConfig(
        paths=PathsConfig(
            preset_root=tmp_path / "presets",
            texture_paths=(tmp_path / "textures",),
        ),
        layers={
            "layer_1": LayerConfig(
                preset=tmp_path / "presets" / "drums" / "a.milk",
                stem="drums",
            )
        },
        editor=EditorConfig(),
        layer_z_order=["layer_1"],
        config_path=tmp_path / "cleave.config.yaml",
        user_config_path=tmp_path / "user-config.yaml",
    )
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=PresetPlaylist(
                    current_dir=tmp_path / "presets" / "drums",
                    paths=(tmp_path / "presets" / "drums" / "a.milk",),
                    index=0,
                ),
                browse_floor=tmp_path / "presets" / "drums",
                stem="drums",
                preset_switching="on",
                preset_switching_trigger="projectm",
                preset_list=[str(milk.resolve())],
            )
        },
    )
    out = persist_layers(PersistCtx(cfg=cfg, session=session, cfg_dir=tmp_path))
    layer_out = out["layer_1"]
    assert layer_out["preset_switching"] == "on"
    assert layer_out["preset_switching_trigger"] == "projectm"
    assert layer_out["preset_switching_list"] == ["presets/a.milk"]


def test_persist_list_outside_cfg_dir_keeps_absolute() -> None:
    outside = Path("/tmp/presets/layer_1/a.milk")
    cfg = CleaveConfig(
        paths=PathsConfig(
            preset_root=Path("/tmp/presets"),
            texture_paths=(),
        ),
        layers={
            "layer_1": LayerConfig(
                preset=outside,
                stem="drums",
            )
        },
        editor=EditorConfig(),
        layer_z_order=["layer_1"],
        config_path=Path("/tmp/test/cleave.config.yaml"),
        user_config_path=Path("/tmp/user-config.yaml"),
    )
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=PresetPlaylist(
                    current_dir=Path("/tmp/presets/layer_1"),
                    paths=(outside,),
                    index=0,
                ),
                browse_floor=Path("/tmp/presets/layer_1"),
                stem="drums",
                preset_switching="on",
                preset_list=[str(outside)],
            )
        },
    )
    out = persist_layers(
        PersistCtx(cfg=cfg, session=session, cfg_dir=Path("/tmp/test"))
    )
    assert out["layer_1"]["preset_switching_list"] == [outside.resolve().as_posix()]


def test_round_trip_snapshot(tmp_path: Path) -> None:
    browse = tmp_path / "preset-root" / "drums"
    browse.mkdir(parents=True)
    milk = browse / "a.milk"
    milk.write_text("MILK")
    project_presets = tmp_path / "presets"
    project_presets.mkdir()
    copied = project_presets / "b.milk"
    copied.write_text("MILK2")
    cfg_path = tmp_path / "unnamed-1.yaml"
    cfg_path.write_text("layers:\n  layer_1: {}\n", encoding="utf-8")
    cfg = CleaveConfig(
        paths=PathsConfig(
            preset_root=tmp_path / "preset-root",
            texture_paths=(tmp_path / "textures",),
        ),
        layers={
            "layer_1": LayerConfig(
                preset=milk,
                stem="drums",
                preset_switching="on",
                preset_switching_trigger="timer",
                preset_switching_list=[copied],
            )
        },
        editor=EditorConfig(),
        config_path=cfg_path,
        user_config_path=tmp_path / "user-config.yaml",
        layer_z_order=["layer_1"],
    )
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=PresetPlaylist(
                    current_dir=browse, paths=(milk,), index=0
                ),
                browse_floor=browse,
                stem="drums",
                preset_switching="on",
                preset_switching_trigger="timer",
                preset_list=[str(copied.resolve())],
            )
        },
    )
    write_session_snapshot(cfg_path, cfg=cfg, session=session)
    loaded = yaml.safe_load(cfg_path.read_text())
    assert loaded["layers"]["layer_1"]["preset_switching"] == "on"
    assert loaded["layers"]["layer_1"]["preset_switching_list"] == [
        "presets/b.milk"
    ]
