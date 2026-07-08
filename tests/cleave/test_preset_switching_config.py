"""Config parse/persist for preset switching fields."""

from __future__ import annotations

from pathlib import Path

import yaml

from cleave.config import CleaveConfig, LayerConfig, PathsConfig, EditorConfig, load_config
from cleave.config_schema import (
    DEFAULT_EASTER_EGG,
    DEFAULT_HARD_CUT_DURATION,
    DEFAULT_HARD_CUT_ENABLED,
    DEFAULT_HARD_CUT_SENSITIVITY,
    DEFAULT_PRESET_START_CLEAN,
    DEFAULT_PRESET_DURATION,
    DEFAULT_PRESET_SWITCHING,
    DEFAULT_PRESET_SWITCHING_SCOPE,
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
    assert layer.preset_switching_scope == DEFAULT_PRESET_SWITCHING_SCOPE
    assert layer.preset_duration == DEFAULT_PRESET_DURATION
    assert layer.soft_cut_duration == DEFAULT_SOFT_CUT_DURATION
    assert layer.hard_cut_duration == DEFAULT_HARD_CUT_DURATION
    assert layer.hard_cut_sensitivity == DEFAULT_HARD_CUT_SENSITIVITY
    assert layer.hard_cut_enabled == DEFAULT_HARD_CUT_ENABLED
    assert layer.easter_egg == DEFAULT_EASTER_EGG
    assert layer.preset_start_clean == DEFAULT_PRESET_START_CLEAN


def test_parse_layers_preset_switching_projectm() -> None:
    preset_root = Path("/tmp/presets")
    data = {"layers": _layer_yaml()}
    data["layers"]["layer_1"]["preset_switching"] = "projectm"
    layers = parse_layers_section(data, ParseCtx(preset_root=preset_root))
    assert layers["layer_1"].preset_switching == "projectm"


def test_parse_layers_preset_switching_timing() -> None:
    preset_root = Path("/tmp/presets")
    data = {"layers": _layer_yaml()}
    data["layers"]["layer_1"].update(
        {
            "preset_duration": 45.0,
            "soft_cut_duration": 1.5,
            "hard_cut_duration": 30.0,
            "hard_cut_sensitivity": 3.5,
        }
    )
    layers = parse_layers_section(data, ParseCtx(preset_root=preset_root))
    layer = layers["layer_1"]
    assert layer.preset_duration == 45.0
    assert layer.soft_cut_duration == 1.5
    assert layer.hard_cut_duration == 30.0
    assert layer.hard_cut_sensitivity == 3.5


def _cfg_and_session(*, preset_switching: str = "none") -> tuple[CleaveConfig, TuningSession]:
    preset_root = Path("/tmp/presets")
    cfg = CleaveConfig(
        paths=PathsConfig(preset_root=preset_root, texture_paths=(preset_root / "tex",)),
        layers={
            "layer_1": LayerConfig(
                preset=preset_root / "drums" / "drums.milk",
                stem="drums",
            )
        },
        layer_z_order=["layer_1"],
        editor=EditorConfig(),
        config_path=Path("/tmp/test/cleave.config.yaml"),
        user_config_path=Path("/tmp/user-config.yaml"),
    )
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=PresetPlaylist(
                    current_dir=preset_root / "drums",
                    paths=(preset_root / "drums" / "drums.milk",),
                    index=0,
                ),
                browse_floor=preset_root / "drums",
                stem="drums",
                preset_switching=preset_switching,
            )
        },
    )
    return cfg, session


def test_persist_layers_omits_default_preset_switching() -> None:
    cfg, session = _cfg_and_session()
    out = persist_layers(PersistCtx(cfg=cfg, session=session))
    assert "preset_switching" not in out["layer_1"]
    assert "preset_switching_scope" not in out["layer_1"]
    assert "preset_duration" not in out["layer_1"]
    assert "soft_cut_duration" not in out["layer_1"]
    assert "hard_cut_duration" not in out["layer_1"]
    assert "hard_cut_sensitivity" not in out["layer_1"]
    assert "hard_cut_enabled" not in out["layer_1"]
    assert "easter_egg" not in out["layer_1"]
    assert "preset_start_clean" not in out["layer_1"]


def test_persist_layers_writes_timing_overrides() -> None:
    cfg, session = _cfg_and_session(preset_switching="projectm")
    runtime = session.layers["layer_1"]
    runtime.preset_duration = 45.0
    runtime.soft_cut_duration = 1.5
    runtime.hard_cut_duration = 30.0
    runtime.hard_cut_sensitivity = 3.5
    out = persist_layers(PersistCtx(cfg=cfg, session=session))
    assert out["layer_1"]["preset_duration"] == 45.0
    assert out["layer_1"]["soft_cut_duration"] == 1.5
    assert out["layer_1"]["hard_cut_duration"] == 30.0
    assert out["layer_1"]["hard_cut_sensitivity"] == 3.5


def test_parse_layers_preset_switching_easter_egg_and_start_clean() -> None:
    preset_root = Path("/tmp/presets")
    data = {"layers": _layer_yaml()}
    data["layers"]["layer_1"].update(
        {
            "easter_egg": 2.5,
            "preset_start_clean": True,
        }
    )
    layers = parse_layers_section(data, ParseCtx(preset_root=preset_root))
    layer = layers["layer_1"]
    assert layer.easter_egg == 2.5
    assert layer.preset_start_clean is True


def test_parse_layers_easter_egg_clamps() -> None:
    preset_root = Path("/tmp/presets")
    data = {"layers": _layer_yaml()}
    data["layers"]["layer_1"]["easter_egg"] = 99.0
    layers = parse_layers_section(data, ParseCtx(preset_root=preset_root))
    assert layers["layer_1"].easter_egg == 5.0


def test_persist_layers_writes_hard_cut_disabled() -> None:
    cfg, session = _cfg_and_session(preset_switching="projectm")
    session.layers["layer_1"].hard_cut_enabled = False
    out = persist_layers(PersistCtx(cfg=cfg, session=session))
    assert out["layer_1"]["hard_cut_enabled"] is False


def test_persist_layers_writes_projectm_mode(tmp_path: Path) -> None:
    preset_root = Path("/tmp/presets")
    config_path = tmp_path / "cleave.config.yaml"
    config_path.write_text("layers: {}\n", encoding="utf-8")
    cfg = CleaveConfig(
        paths=PathsConfig(preset_root=preset_root, texture_paths=(preset_root / "tex",)),
        layers={
            "layer_1": LayerConfig(
                preset=preset_root / "drums" / "drums.milk",
                stem="drums",
            )
        },
        layer_z_order=["layer_1"],
        editor=EditorConfig(),
        config_path=config_path,
        user_config_path=Path("/tmp/user-config.yaml"),
    )
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=PresetPlaylist(
                    current_dir=preset_root / "drums",
                    paths=(preset_root / "drums" / "drums.milk",),
                    index=0,
                ),
                browse_floor=preset_root / "drums",
                stem="drums",
                preset_switching="projectm",
            )
        },
    )
    out = persist_layers(PersistCtx(cfg=cfg, session=session))
    assert out["layer_1"]["preset_switching"] == "projectm"
    assert "preset_switching_scope" not in out["layer_1"]

    path = tmp_path / "snap.yaml"
    write_session_snapshot(path, cfg=cfg, session=session)
    data = yaml.safe_load(path.read_text())
    assert data["layers"]["layer_1"]["preset_switching"] == "projectm"


def test_load_config_round_trip_preset_switching(tmp_path: Path) -> None:
    preset_root = tmp_path / "presets"
    preset_root.mkdir()
    milk = preset_root / "drums" / "drums.milk"
    milk.parent.mkdir(parents=True)
    milk.write_text("; test\n", encoding="utf-8")
    config_path = tmp_path / "cleave.config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "paths": {
                    "preset_root": str(preset_root),
                    "texture_paths": [str(preset_root / "textures")],
                },
                "layers": {
                    "layer_1": {
                        "stem": "drums",
                        "preset": "drums/drums.milk",
                        "preset_switching": "projectm",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config(config_path)
    assert cfg.layers["layer_1"].preset_switching == "projectm"
