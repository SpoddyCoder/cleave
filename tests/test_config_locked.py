"""Tests for layer lock in Cleave YAML config."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from cleave.config import (
    CleaveConfig,
    LayerConfig,
    PathsConfig,
    VisualizerConfig,
    _parse_layers,
)
from cleave.config_snapshot import write_session_snapshot
from cleave.extract import STEM_NAMES
from cleave.preset_playlist import PresetPlaylist, playlist_at_dir
from cleave.viz.controls import LayerRuntime, TuningSession


def _minimal_layers_raw(*, locked_stem: str | None = None) -> dict:
    layers: dict = {}
    for name in STEM_NAMES:
        entry: dict = {"preset": f"{name}/anchor.milk"}
        if name == locked_stem:
            entry["locked"] = True
        layers[name] = entry
    return layers


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


def test_write_session_snapshot_includes_locked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_root = root / "presets"
        for name in STEM_NAMES:
            stem_dir = preset_root / name
            stem_dir.mkdir(parents=True)
            (stem_dir / "anchor.milk").write_text("milk")

        config_path = root / "cleave.config.yaml"
        config_path.write_text("layers: {}\n")

        cfg = CleaveConfig(
            paths=PathsConfig(preset_root=preset_root, texture_paths=(root / "tex",)),
            layers={
                name: LayerConfig(preset=preset_root / name / "anchor.milk")
                for name in STEM_NAMES
            },
            visualizer=VisualizerConfig(),
            config_path=config_path,
        )

        session = TuningSession(
            layer_z_order=list(STEM_NAMES),
            layers={
                name: LayerRuntime(
                    playlist=playlist_at_dir(preset_root / name, index=0),
                    browse_floor=preset_root / name,
                    locked=(name == "bass"),
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layers"]["bass"]["locked"] is True
        for name in STEM_NAMES:
            if name != "bass":
                assert data["layers"][name]["locked"] is False
