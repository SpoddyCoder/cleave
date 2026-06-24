"""Apply per-layer preset switching mode to live ProjectM instances."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from cleave.preset_playlist import milk_files_in_dir
from cleave.projectm_playlist import ProjectMPlaylist
from cleave.viz.layer import StemLayer

PresetSwitchingMode = Literal["none", "projectm"]
PresetSwitchingScope = Literal["directory"]

EMPTY_ROTATION_NOTIFICATION = "No presets in directory for auto switching"

# libprojectM default soft-cut crossfade is 3s; blending shows a white flash in Cleave.
# Auto switches load via instant preset callback (smooth=False); keep duration at zero so any
# remaining soft-cut path from beat spikes also skips crossfade blending.
PROJECTM_AUTO_SOFT_CUT_DURATION_SEC = 0.0


def reapply_projectm_preset_switching(
    session,
    layers_by_slot: dict[str, StemLayer],
    *,
    delta_sec: float = 0.0,
    on_empty: Callable[[], None] | None = None,
) -> None:
    """Re-attach projectM playlist switching after seek without reloading browse preset."""
    for slot, layer in layers_by_slot.items():
        runtime = session.layers[slot]
        if runtime.preset_switching != "projectm":
            continue
        if layer.projectm_playlist is None:
            apply_preset_switching(
                layer,
                mode=runtime.preset_switching,
                scope=runtime.preset_switching_scope,
                on_empty=on_empty,
            )
            continue
        _reapply_on_seek(layer, delta_sec)


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
        layer.auto_preset_path = None
        pm.lock_preset(True)
        pm.set_hard_cut_enabled(False)
        return

    pm.lock_preset(False)
    pm.set_hard_cut_enabled(True)
    pm.set_soft_cut_duration(PROJECTM_AUTO_SOFT_CUT_DURATION_SEC)

    if scope == "directory":
        preset_dir = layer.playlist.current_dir
        if not milk_files_in_dir(preset_dir):
            layer.auto_preset_path = None
            pm.lock_preset(True)
            if on_empty is not None:
                on_empty()
            return

        playlist = ProjectMPlaylist.create()
        playlist.connect(pm, on_preset_loaded=_auto_preset_loaded_callback(layer))
        playlist.add_path(preset_dir, recurse=False, allow_duplicates=False)
        playlist.set_shuffle(False)
        layer.projectm_playlist = playlist
        _sync_projectm_playlist_position(layer)
        restart_projectm_preset_timer(layer)


def restart_projectm_preset_timer(layer: StemLayer) -> None:
    """Load the active auto-switch preset and restart projectM's duration timer."""
    path = active_auto_preset_path(layer)
    if path is None:
        return
    layer.pm.load_preset(path, smooth=False)
    _record_auto_preset(layer, path)


def reset_projectm_preset_timer(layer: StemLayer) -> None:
    """Reset projectM's duration timer without reloading the preset file."""
    pm = layer.pm
    pm.lock_preset(True)
    pm.lock_preset(False)
    pm.set_hard_cut_enabled(True)
    pm.set_soft_cut_duration(PROJECTM_AUTO_SOFT_CUT_DURATION_SEC)


def active_auto_preset_path(layer: StemLayer) -> Path | None:
    if layer.auto_preset_path is not None:
        return layer.auto_preset_path
    current = layer.playlist.current
    if current is None:
        return None
    return current.resolve()


def _reapply_on_seek(layer: StemLayer, delta_sec: float) -> None:
    playlist = layer.projectm_playlist
    if playlist is None:
        return
    pm = layer.pm
    pm.lock_preset(False)
    pm.set_hard_cut_enabled(True)
    pm.set_soft_cut_duration(PROJECTM_AUTO_SOFT_CUT_DURATION_SEC)
    playlist.connect(pm, on_preset_loaded=_auto_preset_loaded_callback(layer))
    if delta_sec < 0:
        restart_projectm_preset_timer(layer)
    else:
        reset_projectm_preset_timer(layer)


def _auto_preset_loaded_callback(layer: StemLayer) -> Callable[[Path], None]:
    def on_preset_loaded(path: Path) -> None:
        _record_auto_preset(layer, path)

    return on_preset_loaded


def _record_auto_preset(layer: StemLayer, path: Path) -> None:
    resolved = path.resolve()
    layer.auto_preset_path = resolved
    browse = layer.playlist
    if browse.current_dir.resolve() != resolved.parent:
        return
    for index, candidate in enumerate(browse.paths):
        if candidate.resolve() == resolved:
            browse.index = index
            return


def _sync_projectm_playlist_position(layer: StemLayer) -> None:
    playlist = layer.projectm_playlist
    path = active_auto_preset_path(layer)
    if playlist is None or path is None:
        return
    target = path.resolve()
    for index in range(playlist.size()):
        item = playlist.item(index)
        if item is not None and item.resolve() == target:
            playlist.set_position(index, hard_cut=True)
            return
