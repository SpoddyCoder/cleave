"""Apply per-layer preset switching mode to live ProjectM instances."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from cleave.preset_playlist import milk_files_in_dir
from cleave.projectm_playlist import ProjectMPlaylist
from cleave.viz.layer import StemLayer

PresetSwitchingMode = Literal["none", "projectm"]
PresetSwitchingScope = Literal["directory"]

EMPTY_ROTATION_NOTIFICATION = "No presets in directory for auto switching"

# libprojectM default soft-cut crossfade is 3s; blending shows a white flash in Cleave.
# Match manual preset browse (smooth=False) by disabling the crossfade duration.
PROJECTM_AUTO_SOFT_CUT_DURATION_SEC = 0.0


def apply_preset_switching(
    layer: StemLayer,
    *,
    mode: PresetSwitchingMode,
    scope: PresetSwitchingScope,
    on_empty: Callable[[], None] | None = None,
) -> None:
    pm = layer.pm

    if layer.projectm_playlist is not None:
        layer.projectm_playlist.destroy()
        layer.projectm_playlist = None

    if mode == "none":
        pm.lock_preset(True)
        pm.set_hard_cut_enabled(False)
        return

    pm.lock_preset(False)
    pm.set_hard_cut_enabled(True)
    pm.set_soft_cut_duration(PROJECTM_AUTO_SOFT_CUT_DURATION_SEC)

    if scope == "directory":
        preset_dir = layer.playlist.current_dir
        if not milk_files_in_dir(preset_dir):
            pm.lock_preset(True)
            if on_empty is not None:
                on_empty()
            return

        playlist = ProjectMPlaylist.create()
        playlist.connect(pm)
        playlist.add_path(preset_dir, recurse=False, allow_duplicates=False)
        playlist.set_shuffle(False)
        layer.projectm_playlist = playlist
