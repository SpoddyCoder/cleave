"""Write reproducible Cleave YAML snapshots from a live tuning session."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from cleave.config import CleaveConfig, dump_yaml
from cleave.config_schema import persisted_session_payload
from cleave.viz.session import TuningSession

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


def _snapshot_render_overlay(
    cfg: CleaveConfig,
    session: TuningSession,
    original: dict[str, Any],
) -> dict[str, Any]:
    payload = persisted_session_payload(cfg, session)
    overlay_payload = payload["render"]["overlay"]
    post_fx_payload = payload["render"]["post_fx"]

    orig_render = original.get("render")
    orig_overlay: dict[str, Any] = {}
    if isinstance(orig_render, dict):
        orig_overlay_raw = orig_render.get("overlay")
        if isinstance(orig_overlay_raw, dict):
            orig_overlay = dict(orig_overlay_raw)

    overlay: dict[str, Any] = dict(orig_overlay)
    overlay["enabled"] = overlay_payload["enabled"]
    overlay["title"] = overlay_payload["title"]
    overlay["body"] = overlay_payload["body"]
    overlay["start_delay"] = overlay_payload["start_delay"]
    overlay["display_time"] = overlay_payload["display_time"]
    overlay["position"] = overlay_payload["position"]

    background = orig_overlay.get("background")
    background_out: dict[str, Any] = (
        dict(background) if isinstance(background, dict) else {}
    )
    bg_payload = overlay_payload["background"]
    background_out["margin"] = bg_payload["margin"]
    background_out["padding"] = bg_payload["padding"]
    background_out["colour"] = bg_payload["colour"]
    background_out["opacity"] = bg_payload["opacity"]

    border = background_out.get("border")
    border_out: dict[str, Any] = dict(border) if isinstance(border, dict) else {}
    border_payload = bg_payload["border"]
    border_out["colour"] = border_payload["colour"]
    border_out["width"] = border_payload["width"]
    background_out["border"] = border_out
    overlay["background"] = background_out
    overlay.pop("font", None)

    orig_pp: dict[str, Any] = {}
    if isinstance(orig_render, dict):
        orig_pp_raw = orig_render.get("post_fx")
        if isinstance(orig_pp_raw, dict):
            orig_pp = dict(orig_pp_raw)

    post_fx: dict[str, Any] = dict(orig_pp)
    post_fx["enabled"] = post_fx_payload["enabled"]
    post_fx["fade_in"] = post_fx_payload["fade_in"]
    post_fx["fade_out"] = post_fx_payload["fade_out"]
    hr_payload = post_fx_payload["highlight_rolloff"]
    hr_orig = post_fx.get("highlight_rolloff")
    highlight_rolloff: dict[str, Any] = (
        dict(hr_orig) if isinstance(hr_orig, dict) else {}
    )
    highlight_rolloff["enabled"] = hr_payload["enabled"]
    highlight_rolloff["mode"] = hr_payload["mode"]
    highlight_rolloff["curve"] = hr_payload["curve"]
    highlight_rolloff["threshold_pct"] = hr_payload["threshold_pct"]
    highlight_rolloff["strength_pct"] = hr_payload["strength_pct"]
    highlight_rolloff["softness_pct"] = hr_payload["softness_pct"]
    post_fx["highlight_rolloff"] = highlight_rolloff

    render_out: dict[str, Any] = {}
    if isinstance(orig_render, dict):
        render_out = {
            key: value
            for key, value in orig_render.items()
            if key not in ("overlay", "post_fx")
        }
    render_payload = payload["render"]
    render_out["fps"] = render_payload["fps"]
    render_out["width"] = render_payload["width"]
    render_out["height"] = render_payload["height"]
    render_out["overlay"] = overlay
    render_out["post_fx"] = post_fx
    return render_out


def persisted_session_signature(cfg: CleaveConfig, session: TuningSession) -> str:
    """Stable compare key for persisted session state."""
    return json.dumps(
        persisted_session_payload(cfg, session),
        sort_keys=True,
        separators=(",", ":"),
    )


def write_session_snapshot(
    path: Path,
    *,
    cfg: CleaveConfig,
    session: TuningSession,
) -> None:
    """Write a full reproducible YAML snapshot without modifying the launch config."""
    original = _load_original_dict(cfg)
    payload = persisted_session_payload(cfg, session)

    orig_vis = original.get("visualizer")
    visualizer: dict[str, Any] = {}
    if isinstance(orig_vis, dict) and "name" in orig_vis:
        visualizer["name"] = orig_vis["name"]
    visualizer.update(payload["visualizer"])

    orig_paths = original.get("paths")
    if isinstance(orig_paths, dict) and orig_paths:
        paths = dict(orig_paths)
    else:
        paths = {
            "preset_root": _path_to_yaml_str(cfg.paths.preset_root),
            "texture_paths": [_path_to_yaml_str(p) for p in cfg.paths.texture_paths],
        }

    data = {
        "visualizer": visualizer,
        "paths": paths,
        "layer_z_order": payload["layer_z_order"],
        "layers": payload["layers"],
        "render": _snapshot_render_overlay(cfg, session, original),
        "timeline": payload["timeline"],
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        dump_yaml(data, fh)
