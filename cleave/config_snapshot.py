"""Write reproducible Cleave YAML snapshots from a live tuning session."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from cleave.config import CleaveConfig, RenderOverlayConfig, RenderOverlayTextBlockConfig, clamp_beat_sensitivity, clamp_effect_pct, dump_yaml
from cleave.extract import STEM_NAMES
from cleave.preset_playlist import to_config_relative
from cleave.viz.controls import TuningSession
from cleave.viz.render_overlay import default_render_overlay_config

_UNNAMED_PATTERN = re.compile(r"^unnamed-(\d+)\.yaml$")


def next_unnamed_path(project_dir: Path) -> Path:
    """Return the next unused ``unnamed-N.yaml`` in ``project_dir``."""
    project_dir.mkdir(parents=True, exist_ok=True)
    max_n = 0
    for entry in project_dir.iterdir():
        if not entry.is_file():
            continue
        match = _UNNAMED_PATTERN.match(entry.name)
        if match is not None:
            max_n = max(max_n, int(match.group(1)))
    return project_dir / f"unnamed-{max_n + 1}.yaml"


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


def _sparse_effects(
    effects: dict[str, dict[str, int]],
) -> dict[str, dict[str, int]] | None:
    out: dict[str, dict[str, int]] = {}
    for effect_id, drivers in effects.items():
        sparse_drivers: dict[str, int] = {}
        for driver_slug, pct in drivers.items():
            clamped = clamp_effect_pct(pct)
            if clamped != 0:
                sparse_drivers[driver_slug] = clamped
        if sparse_drivers:
            out[effect_id] = sparse_drivers
    return out or None


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _render_overlay_base(cfg: CleaveConfig) -> RenderOverlayConfig:
    if cfg.render is not None and cfg.render.overlay is not None:
        return cfg.render.overlay
    return default_render_overlay_config()


def _text_block_to_yaml(
    block: RenderOverlayTextBlockConfig,
    *,
    font: str,
    font_size: int,
    colour_key: str,
    margin_bottom: int | None = None,
) -> dict[str, Any]:
    content = block.content
    if "\n" in content:
        content = content + "\n"
    out: dict[str, Any] = {
        "content": content,
        "font": font,
        "font-size": font_size,
        colour_key: _rgb_to_hex(block.colour),
    }
    if block.background_colour is not None:
        out["background-colour"] = _rgb_to_hex(block.background_colour)
    if margin_bottom is not None:
        out["margin-bottom"] = margin_bottom
    return out


def _snapshot_render_overlay(
    cfg: CleaveConfig,
    session: TuningSession,
    original: dict[str, Any],
) -> dict[str, Any]:
    runtime = session.render_overlay
    base = _render_overlay_base(cfg)
    bg = base.background

    orig_render = original.get("render")
    orig_overlay: dict[str, Any] = {}
    if isinstance(orig_render, dict):
        orig_overlay_raw = orig_render.get("overlay")
        if isinstance(orig_overlay_raw, dict):
            orig_overlay = dict(orig_overlay_raw)

    overlay: dict[str, Any] = dict(orig_overlay)
    overlay["enabled"] = runtime.enabled or session.render_overlay_solo
    overlay["title"] = _text_block_to_yaml(
        base.title,
        font=runtime.title_font,
        font_size=runtime.title_font_size,
        colour_key="font-colour",
        margin_bottom=runtime.title_margin_bottom,
    )
    overlay["body"] = _text_block_to_yaml(
        base.body,
        font=runtime.body_font,
        font_size=runtime.body_font_size,
        colour_key="colour",
    )
    overlay["start_delay"] = runtime.start_delay
    overlay["display_time"] = runtime.display_time
    overlay["position"] = runtime.position

    background = orig_overlay.get("background")
    background_out: dict[str, Any] = (
        dict(background) if isinstance(background, dict) else {}
    )
    background_out["margin"] = bg.margin
    background_out["padding"] = bg.padding
    background_out["colour"] = _rgb_to_hex(bg.colour)
    background_out["opacity"] = runtime.opacity_pct / 100.0

    border = background_out.get("border")
    border_out: dict[str, Any] = dict(border) if isinstance(border, dict) else {}
    border_out["colour"] = _rgb_to_hex(bg.border.colour)
    border_out["width"] = runtime.border_width
    background_out["border"] = border_out
    overlay["background"] = background_out
    overlay.pop("font", None)

    runtime_pp = session.render_post_fx
    orig_pp: dict[str, Any] = {}
    if isinstance(orig_render, dict):
        orig_pp_raw = orig_render.get("post_fx")
        if isinstance(orig_pp_raw, dict):
            orig_pp = dict(orig_pp_raw)

    post_fx: dict[str, Any] = dict(orig_pp)
    post_fx["enabled"] = runtime_pp.enabled or session.render_post_fx_solo
    post_fx["fade_in"] = runtime_pp.fade_in
    post_fx["fade_out"] = runtime_pp.fade_out

    render_out: dict[str, Any] = {}
    if isinstance(orig_render, dict):
        render_out = {
            key: value
            for key, value in orig_render.items()
            if key not in ("overlay", "post_fx")
        }
    render_out["overlay"] = overlay
    render_out["post_fx"] = post_fx
    return render_out


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
            effects = runtime.effects
            locked = runtime.locked
        else:
            preset = to_config_relative(layer_cfg.preset, preset_root)
            opacity = layer_cfg.opacity
            enabled = layer_cfg.enabled
            blend_mode = layer_cfg.blend_mode
            locked = layer_cfg.locked
            effects = layer_cfg.effects
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
        sparse_effects = _sparse_effects(effects)
        if sparse_effects is not None:
            layer_out["effects"] = sparse_effects
        layers_out[name] = layer_out

    data = {
        "visualizer": visualizer,
        "paths": paths,
        "layer_z_order": _snapshot_layer_z_order(cfg, session),
        "layers": layers_out,
        "render": _snapshot_render_overlay(cfg, session, original),
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        dump_yaml(data, fh)
