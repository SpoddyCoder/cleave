"""Tests for Cleave config snapshot writing."""

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
from cleave.config_snapshot import next_unnamed_path, write_session_snapshot
from cleave.extract import STEM_NAMES
from cleave.preset_playlist import playlist_at_dir
from cleave.viz.controls import LayerRuntime, TuningSession


def test_next_unnamed_path_empty_dir(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    assert next_unnamed_path(project_dir) == project_dir / "unnamed-1.yaml"


def test_next_unnamed_path_fills_gaps(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "unnamed-1.yaml").write_text("a\n", encoding="utf-8")
    (project_dir / "unnamed-3.yaml").write_text("b\n", encoding="utf-8")
    assert next_unnamed_path(project_dir) == project_dir / "unnamed-4.yaml"


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


def test_write_session_snapshot_sparse_effects() -> None:
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
                    effects={"pulse": {"onset": 60}} if name == "drums" else {},
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layers"]["drums"]["effects"] == {"pulse": {"onset": 60}}
        assert "effects" not in data["layers"]["bass"]


def test_write_session_snapshot_sparse_all_effect_types() -> None:
    """Non-zero effect keys persist; zero drivers and empty effect groups are omitted."""
    session_effects: dict[str, dict[str, dict[str, int]]] = {
        "drums": {
            "pulse": {"onset": 35},
            "flare": {"onset": 20},
            "flash": {"onset": 15},
            "grit": {"onset": 10},
        },
        "bass": {
            "pulse": {"sub_bass": 40, "mid_bass": 0},
            "flash": {"sub_bass": 10},
            "grit": {"sub_bass": 5},
        },
        "vocals": {
            "pulse": {"rms": 45},
            "hue": {"pitch": 25},
            "flash": {"rms": 10},
            "grit": {"rms": 0},
        },
        "other": {
            "pulse": {"centroid": 30},
            "flash": {"centroid": 0},
            "grit": {"centroid": 5},
        },
    }
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
                    effects=session_effects[name],
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layers"]["drums"]["effects"] == session_effects["drums"]
        assert data["layers"]["bass"]["effects"] == {
            "pulse": {"sub_bass": 40},
            "flash": {"sub_bass": 10},
            "grit": {"sub_bass": 5},
        }
        assert data["layers"]["vocals"]["effects"] == {
            "pulse": {"rms": 45},
            "hue": {"pitch": 25},
            "flash": {"rms": 10},
        }
        assert data["layers"]["other"]["effects"] == {
            "pulse": {"centroid": 30},
            "grit": {"centroid": 5},
        }

        round_trip = _parse_layers({"layers": data["layers"]}, preset_root)
        assert round_trip["drums"].effects == session_effects["drums"]
        assert round_trip["bass"].effects["pulse"] == {"sub_bass": 40}
        assert round_trip["vocals"].effects["hue"] == {"pitch": 25}


def test_write_session_snapshot_uses_session_z_order_when_valid() -> None:
    session_order = ["other", "drums", "bass", "vocals"]
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
            layer_z_order=("drums", "vocals", "bass", "other"),
        )

        session = TuningSession(
            layer_z_order=session_order,
            layers={
                name: LayerRuntime(
                    playlist=playlist_at_dir(preset_root / name, index=0),
                    browse_floor=preset_root / name,
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layer_z_order"] == session_order


def test_write_session_snapshot_falls_back_to_cfg_z_order_when_invalid() -> None:
    cfg_order = ("drums", "vocals", "bass", "other")
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
            layer_z_order=cfg_order,
        )

        session = TuningSession(
            layer_z_order=["drums", "bass"],
            layers={
                name: LayerRuntime(
                    playlist=playlist_at_dir(preset_root / name, index=0),
                    browse_floor=preset_root / name,
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["layer_z_order"] == list(cfg_order)


def test_write_session_snapshot_sparse_beat_sensitivity() -> None:
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
            visualizer=VisualizerConfig(beat_sensitivity=1.0),
            config_path=config_path,
        )

        session = TuningSession(
            layer_z_order=list(STEM_NAMES),
            layers={
                name: LayerRuntime(
                    playlist=playlist_at_dir(preset_root / name, index=0),
                    browse_floor=preset_root / name,
                    beat_sensitivity=1.5 if name == "bass" else 1.0,
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert data["visualizer"]["beat_sensitivity"] == 1.0
        assert "beat_sensitivity" not in data["layers"]["drums"]
        assert data["layers"]["bass"]["beat_sensitivity"] == 1.5


def test_write_session_snapshot_omits_all_zero_effects() -> None:
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
                    effects=(
                        {"pulse": {"onset": 0}, "flare": {"onset": 0}}
                        if name == "vocals"
                        else {}
                    ),
                )
                for name in STEM_NAMES
            },
        )

        out_path = root / "snapshot.yaml"
        write_session_snapshot(out_path, cfg=cfg, session=session)

        data = yaml.safe_load(out_path.read_text(encoding="utf-8"))
        assert "effects" not in data["layers"]["vocals"]
