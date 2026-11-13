"""Cue role labels, blend defaults, and panel markers."""

from __future__ import annotations

from typing import Literal

from cleave.blend_modes import BlendMode

CueRole = Literal["bed", "pulse", "lead", "accent"]

CUE_ROLES: tuple[CueRole, ...] = ("bed", "pulse", "lead", "accent")

CUE_ROLE_BLEND: dict[CueRole, BlendMode] = {
    "bed": "black-key",
    "pulse": "add",
    "lead": "black-key",
    "accent": "add",
}

CUE_ROLE_MARKER_LETTER: dict[CueRole, str] = {
    "bed": "B",
    "pulse": "P",
    "lead": "L",
    "accent": "A",
}

CUE_ROLE_HELP_BLURB: dict[CueRole, str] = {
    "bed": "calm, dark background",
    "pulse": "reacts to the beat, middle depth",
    "lead": "busy, bright main visual",
    "accent": "short, bright hits",
}

CUE_ROLE_MARKER_HELP_ENTRIES: tuple[tuple[str, str], ...] = tuple(
    (
        f"[R:{CUE_ROLE_MARKER_LETTER[role]}]",
        f"{role} ({CUE_ROLE_HELP_BLURB[role]})",
    )
    for role in CUE_ROLES
)
