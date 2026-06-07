"""Write reproducible Cleave YAML snapshots from a live tuning session."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from cleave.config import CleaveConfig, clamp_beat_sensitivity, dump_yaml
from cleave.extract import STEM_NAMES
from cleave.preset_playlist import to_config_relative
from cleave.viz_tuning_controls import TuningSession

_UNNAMED_PATTERN = re.compile(r"^unnamed-(\d+)\.cleave\.config\.yaml$")


def next_unnamed_path(saved_dir: Path) -> Path:
    """Return the next unused ``unnamed-N.cleave.config.yaml`` under ``saved_dir``."""
    saved_dir.mkdir(parents=True, exist_ok=True)
    max_n = 0
    for entry in saved_dir.iterdir():
        if not entry.is_file():
            continue
        match = _UNNAMED_PATTERN.match(entry.name)
        if match is not None:
            max_n = max(max_n, int(match.group(1)))
    return saved_dir / f"unnamed-{max_n + 1}.cleave.config.yaml"


def _load_original_dict(cfg: CleaveConfig) -> dict[str, Any]:
    with cfg.config_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


def _path_to_yaml_str(path: Path) -> str:
    resolved = path.resolve()
    home = Path.home()
    try:
        rel = resolved.relative_to(home)
        return f"~/{rel.as_posix()}"
    except ValueError:
        return resolved.as_posix()


def _snapshot_layer_z_order(cfg: CleaveConfig, session: TuningSession) -> list[str]:
    order = session.layer_z_order
    if len(order) == len(STEM_NAMES) and set(order) == set(STEM_NAMES):
        return list(order)
    return list(cfg.layer_z_order)


def write_session_snapshot(
    path: Path,
    *,
    cfg: CleaveConfig,
    session: TuningSession,
) -> None:
    """Write a full reproducible YAML snapshot without modifying the launch config."""
    original = _load_original_dict(cfg)
    preset_root = cfg.paths.preset_root

    orig_vis = original.get("visualizer")
    visualizer: dict[str, Any] = {}
    if isinstance(orig_vis, dict) and "name" in orig_vis:
        visualizer["name"] = orig_vis["name"]
    visualizer["width"] = cfg.visualizer.width
    visualizer["height"] = cfg.visualizer.height
    visualizer["fps"] = cfg.visualizer.fps
    visualizer["beat_sensitivity"] = clamp_beat_sensitivity(
        cfg.visualizer.beat_sensitivity
    )

    orig_paths = original.get("paths")
    if isinstance(orig_paths, dict) and orig_paths:
        paths = dict(orig_paths)
    else:
        paths = {
            "preset_root": _path_to_yaml_str(cfg.paths.preset_root),
            "texture_paths": [_path_to_yaml_str(p) for p in cfg.paths.texture_paths],
        }

    layers_out: dict[str, dict[str, Any]] = {}
    global_beat = cfg.visualizer.beat_sensitivity

    for name in STEM_NAMES:
        layer_cfg = cfg.layers[name]
        if name in session.layers:
            runtime = session.layers[name]
            preset = runtime.playlist.config_preset_path(preset_root)
            opacity = runtime.opacity_pct / 100.0
            enabled = runtime.enabled
            blend_mode = runtime.blend_mode
            beat = runtime.beat_sensitivity
            locked = runtime.locked
        else:
            preset = to_config_relative(layer_cfg.preset, preset_root)
            opacity = layer_cfg.opacity
            enabled = layer_cfg.enabled
            blend_mode = layer_cfg.blend_mode
            locked = layer_cfg.locked
            beat = (
                layer_cfg.beat_sensitivity
                if layer_cfg.beat_sensitivity is not None
                else global_beat
            )

        layer_out: dict[str, Any] = {
            "preset": preset,
            "enabled": enabled,
            "opacity": opacity,
            "width": layer_cfg.width,
            "height": layer_cfg.height,
            "blend_mode": blend_mode,
            "locked": locked,
        }
        beat = clamp_beat_sensitivity(beat)
        if beat != global_beat:
            layer_out["beat_sensitivity"] = beat
        layers_out[name] = layer_out

    data = {
        "visualizer": visualizer,
        "paths": paths,
        "layer_z_order": _snapshot_layer_z_order(cfg, session),
        "layers": layers_out,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        dump_yaml(data, fh)
