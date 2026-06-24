"""Stem layer data class."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cleave.gl_compositor import LayerFbo
from cleave.preset_playlist import PresetPlaylist
from cleave.projectm import ProjectM
from cleave.projectm_playlist import ProjectMPlaylist


@dataclass
class StemLayer:
    slot: str
    pm: ProjectM
    fbo: LayerFbo
    playlist: PresetPlaylist
    projectm_playlist: ProjectMPlaylist | None = None
    auto_preset_path: Path | None = None
