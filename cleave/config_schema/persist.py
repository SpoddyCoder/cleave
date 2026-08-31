"""Session persist payload: editor, layers, render, and timeline."""

from __future__ import annotations

from typing import Any

from cleave.config_schema.descriptors import PersistCtx
from cleave.config_schema.editor import persist_project_editor_section
from cleave.config_schema.layers import persist_layer_z_order, persist_layers
from cleave.config_schema.render import persist_render
from cleave.config_schema.timeline import persist_timeline


def persisted_session_payload(cfg: Any, session: Any) -> dict[str, Any]:
    cfg_dir = getattr(cfg, "config_path", None)
    cfg_dir = cfg_dir.parent if cfg_dir is not None else None
    ctx = PersistCtx(cfg=cfg, session=session, cfg_dir=cfg_dir)
    return {
        "editor": persist_project_editor_section(ctx),
        "layer_z_order": persist_layer_z_order(ctx),
        "layers": persist_layers(ctx),
        "render": persist_render(ctx),
        "timeline": persist_timeline(ctx),
    }
