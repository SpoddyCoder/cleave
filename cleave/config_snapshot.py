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


_LEGACY_RENDER_KEYS = ("overlay",)
_LEGACY_OVERLAY_CARD_KEYS = ("font", "start_delay", "display_time")


def _deep_merge_dicts(
    original: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(original)
    for key, value in payload.items():
        existing = merged.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            merged[key] = _deep_merge_dicts(existing, value)
        else:
            merged[key] = value
    return merged


def _strip_legacy_overlay_card_keys(render_out: dict[str, Any]) -> None:
    overlays = render_out.get("overlays")
    if not isinstance(overlays, dict):
        return
    for card_key in ("opening-card", "closing-card"):
        card = overlays.get(card_key)
        if isinstance(card, dict):
            for legacy_key in _LEGACY_OVERLAY_CARD_KEYS:
                card.pop(legacy_key, None)


def _snapshot_render(
    render_payload: dict[str, Any],
    original: dict[str, Any],
) -> dict[str, Any]:
    orig_render = original.get("render")
    orig: dict[str, Any] = dict(orig_render) if isinstance(orig_render, dict) else {}
    for legacy_key in _LEGACY_RENDER_KEYS:
        orig.pop(legacy_key, None)
    render_out = _deep_merge_dicts(orig, render_payload)
    _strip_legacy_overlay_card_keys(render_out)
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

    orig_editor = original.get("editor")
    editor_out: dict[str, Any] = {}
    if isinstance(orig_editor, dict) and "name" in orig_editor:
        editor_out["name"] = orig_editor["name"]
    editor_out.update(payload["editor"])

    data: dict[str, Any] = {
        "editor": editor_out,
        "layer_z_order": payload["layer_z_order"],
        "layers": payload["layers"],
        "render": _snapshot_render(payload["render"], original),
        "timeline": payload["timeline"],
    }

    orig_paths = original.get("paths")
    if isinstance(orig_paths, dict) and orig_paths:
        data["paths"] = dict(orig_paths)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        dump_yaml(data, fh)
