"""Live layer sync handlers for tuning controls."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from cleave.blend_modes import BlendMode
from cleave.preset_playlist import PresetPlaylist


@dataclass(frozen=True)
class LiveLayerBindings:
    on_preset_change: Callable[[str, PresetPlaylist], None]
    on_blend_change: Callable[[str, BlendMode], None]
    on_opacity_change: Callable[[str, int], None]
    on_layer_enabled_change: Callable[[str, bool], None]
    on_timeline_enabled_change: Callable[[], None]
    on_solo_change: Callable[[], None]
    on_beat_change: Callable[[str, float], None]
    on_seek: Callable[[float], None]
