"""Unit tests for preset scan target derivation."""

from __future__ import annotations

import tempfile
from pathlib import Path

from cleave.config import (
    CleaveConfig,
    LayerConfig,
    PathsConfig,
    VisualizerConfig,
)
from cleave.config_schema import DEFAULT_LAYER_SLOTS
from cleave.preset_scan_targets import build_bulk_targets, build_project_targets
from cleave.extract import STEM_NAMES


def _write_milk(path: Path) -> None:
    path.write_text("milk")


def _layer_config(
    preset: Path,
    *,
    stem: str = "drums",
    enabled: bool = True,
    preset_switching: str = "projectm",
    preset_switching_presets: list[Path] | None = None,
) -> LayerConfig:
    return LayerConfig(
        preset=preset,
        stem=stem,  # type: ignore[arg-type]
        enabled=enabled,
        preset_switching=preset_switching,  # type: ignore[arg-type]
        preset_switching_presets=preset_switching_presets or [],
    )


def _project_cfg(
    tmp: Path,
    *,
    layers: dict[str, LayerConfig],
    layer_z_order: list[str] | None = None,
) -> CleaveConfig:
    texture_dir = tmp / "textures"
    texture_dir.mkdir(exist_ok=True)
    return CleaveConfig(
        paths=PathsConfig(
            preset_root=tmp / "presets",
            texture_paths=(texture_dir.resolve(),),
        ),
        layers=layers,
        visualizer=VisualizerConfig(),
        config_path=tmp / "cleave-viz.yaml",
        layer_z_order=layer_z_order or ["layer_1"],
    )


def test_project_targets_include_sibling_presets_non_recursive() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_dir = root / "presets" / "pack"
        preset_dir.mkdir(parents=True)
        anchor = preset_dir / "anchor.milk"
        sibling = preset_dir / "sibling.milk"
        nested_dir = preset_dir / "nested"
        nested_dir.mkdir()
        _write_milk(anchor)
        _write_milk(sibling)
        _write_milk(nested_dir / "deep.milk")

        cfg = _project_cfg(
            root,
            layers={
                "layer_1": _layer_config(anchor, preset_switching="projectm"),
            },
        )
        targets = build_project_targets(cfg)

        paths = {target.path for target in targets.presets}
        assert paths == {anchor.resolve(), sibling.resolve()}
        assert targets.layer_sources["layer_1"] == (preset_dir.resolve(),)
        assert targets.preset_root == (root / "presets").resolve()
        assert targets.texture_paths == ((root / "textures").resolve(),)


def test_project_targets_include_anchor_dir_when_preset_switching_none() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_dir = root / "presets" / "locked"
        preset_dir.mkdir(parents=True)
        locked = preset_dir / "locked.milk"
        sibling = preset_dir / "other.milk"
        _write_milk(locked)
        _write_milk(sibling)

        cfg = _project_cfg(
            root,
            layers={
                "layer_1": _layer_config(locked, preset_switching="none"),
            },
        )
        targets = build_project_targets(cfg)

        paths = {target.path for target in targets.presets}
        assert paths == {locked.resolve(), sibling.resolve()}


def test_project_targets_include_disabled_layers() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        preset_dir = root / "presets" / "off"
        preset_dir.mkdir(parents=True)
        anchor = preset_dir / "a.milk"
        sibling = preset_dir / "b.milk"
        _write_milk(anchor)
        _write_milk(sibling)

        cfg = _project_cfg(
            root,
            layers={
                "layer_1": _layer_config(anchor, enabled=False),
            },
        )
        targets = build_project_targets(cfg)

        assert len(targets.presets) == 2


def test_project_targets_user_defined_adds_rotation_presets() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        anchor_dir = root / "presets" / "anchor"
        extra_dir = root / "extras"
        anchor_dir.mkdir(parents=True)
        extra_dir.mkdir()
        anchor = anchor_dir / "anchor.milk"
        sibling = anchor_dir / "sibling.milk"
        extra = extra_dir / "extra.milk"
        _write_milk(anchor)
        _write_milk(sibling)
        _write_milk(extra)

        cfg = _project_cfg(
            root,
            layers={
                "layer_1": _layer_config(
                    anchor,
                    preset_switching="user_defined",
                    preset_switching_presets=[extra],
                ),
            },
        )
        targets = build_project_targets(cfg)

        paths = {target.path for target in targets.presets}
        assert paths == {
            anchor.resolve(),
            sibling.resolve(),
            extra.resolve(),
        }
        assert targets.layer_sources["layer_1"] == (
            anchor_dir.resolve(),
            extra.resolve(),
        )


def test_project_targets_dedup_presets_across_layers() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shared_dir = root / "presets" / "shared"
        shared_dir.mkdir(parents=True)
        shared = shared_dir / "shared.milk"
        other = shared_dir / "other.milk"
        _write_milk(shared)
        _write_milk(other)

        cfg = _project_cfg(
            root,
            layers={
                "layer_1": _layer_config(
                    shared,
                    stem="drums",
                    preset_switching="none",
                ),
                "layer_2": _layer_config(
                    other,
                    stem="bass",
                    preset_switching="none",
                ),
            },
            layer_z_order=["layer_1", "layer_2"],
        )
        targets = build_project_targets(cfg)

        shared_target = next(t for t in targets.presets if t.path == shared.resolve())
        assert shared_target.layers == ("layer_1", "layer_2")
        assert len(targets.presets) == 2


def test_project_targets_respect_layer_z_order_slots() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        layers: dict[str, LayerConfig] = {}
        for index, slot in enumerate(DEFAULT_LAYER_SLOTS[:2]):
            preset_dir = root / "presets" / slot
            preset_dir.mkdir(parents=True)
            preset = preset_dir / f"{slot}.milk"
            _write_milk(preset)
            layers[slot] = _layer_config(
                preset,
                stem=STEM_NAMES[index],
                preset_switching="none",
            )

        cfg = _project_cfg(
            root,
            layers=layers,
            layer_z_order=["layer_1", "layer_2"],
        )
        targets = build_project_targets(cfg)

        assert len(targets.presets) == 2
        assert set(targets.layer_sources) == {"layer_1", "layer_2"}


def test_bulk_targets_non_recursive() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        direct = root / "direct.milk"
        nested_dir = root / "nested"
        nested_dir.mkdir()
        nested = nested_dir / "nested.milk"
        _write_milk(direct)
        _write_milk(nested)

        targets = build_bulk_targets(root, recursive=False)

        assert [target.path for target in targets.presets] == [direct.resolve()]
        assert targets.presets_dir == root.resolve()
        assert targets.presets[0].layers == ()


def test_bulk_targets_recursive() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        direct = root / "direct.milk"
        nested_dir = root / "nested"
        nested_dir.mkdir()
        nested = nested_dir / "nested.milk"
        _write_milk(direct)
        _write_milk(nested)

        targets = build_bulk_targets(root, recursive=True)

        assert [target.path for target in targets.presets] == [
            direct.resolve(),
            nested.resolve(),
        ]
