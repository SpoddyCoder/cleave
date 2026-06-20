"""Stem layer data class."""

from __future__ import annotations

from dataclasses import dataclass

from cleave.gl_compositor import LayerFbo
from cleave.preset_playlist import PresetPlaylist
from cleave.projectm import ProjectM


@dataclass
class StemLayer:
    slot: str
    pm: ProjectM
    fbo: LayerFbo
    playlist: PresetPlaylist
