"""Shared YAML value validators."""

from __future__ import annotations

from typing import Any

from cleave.blend_modes import BLEND_MODES, BlendMode
from cleave.cue_roles import CUE_ROLES, CueRole
from cleave.cut_types import CUT_TYPES, CutType
from cleave.extract import StemSource


def validate_blend_mode(raw: Any, *, path: str) -> BlendMode:
    if raw not in BLEND_MODES:
        allowed = ", ".join(f"'{mode}'" for mode in BLEND_MODES)
        raise ValueError(f"{path} must be one of: {allowed}")
    return raw


def validate_cue_role(raw: Any, *, path: str) -> CueRole:
    if raw not in CUE_ROLES:
        allowed = ", ".join(f"'{role}'" for role in CUE_ROLES)
        raise ValueError(f"{path} must be one of: {allowed}")
    return raw


def validate_cut_type(raw: Any, *, path: str) -> CutType:
    if raw not in CUT_TYPES:
        allowed = ", ".join(f"'{cut}'" for cut in CUT_TYPES)
        raise ValueError(f"{path} must be one of: {allowed}")
    return raw


def parse_blend_mode(
    slot: str, stem: StemSource, layer_raw: dict[str, Any]
) -> BlendMode:
    raw = layer_raw.get("blend_mode")
    if raw is None:
        from cleave.config_schema.layers import DEFAULT_BLEND_MODE

        return DEFAULT_BLEND_MODE[stem]
    return validate_blend_mode(raw, path=f"layers.{slot}.blend_mode")
