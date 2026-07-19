"""Apply per-layer preset switching mode to live ProjectM instances."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cleave.config_schema import (
    DEFAULT_EASTER_EGG,
    DEFAULT_HARD_CUT_DURATION,
    DEFAULT_HARD_CUT_ENABLED,
    DEFAULT_HARD_CUT_SENSITIVITY,
    DEFAULT_PRESET_DURATION,
    DEFAULT_PRESET_START_CLEAN,
    DEFAULT_PRESET_SWITCHING_SHUFFLE,
    DEFAULT_SOFT_CUT_DURATION,
    PresetSwitchingMode,
    PresetSwitchingScope,
)
from cleave.preset_playlist import milk_files_in_dir
from cleave.projectm import ProjectM
from cleave.projectm_playlist import ProjectMPlaylist
from cleave.viz.layer import StemLayer

EMPTY_ROTATION_NOTIFICATION = "No presets in directory for auto switching"
EMPTY_USER_PRESETS_NOTIFICATION = "No presets in user-defined rotation set"


def _apply_projectm_timing(
    pm: ProjectM,
    *,
    preset_duration: float,
    soft_cut_duration: float,
    easter_egg: float,
    preset_start_clean: bool,
    hard_cut_enabled: bool,
    hard_cut_duration: float,
    hard_cut_sensitivity: float,
) -> None:
    pm.set_preset_duration(preset_duration)
    pm.set_soft_cut_duration(soft_cut_duration)
    pm.set_easter_egg(easter_egg)
    pm.set_preset_start_clean(preset_start_clean)
    pm.set_hard_cut_enabled(hard_cut_enabled)
    pm.set_hard_cut_duration(hard_cut_duration)
    pm.set_hard_cut_sensitivity(hard_cut_sensitivity)


def reapply_projectm_preset_switching(
    session,
    layers_by_slot: dict[str, StemLayer],
    *,
    delta_sec: float = 0.0,
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
                user_presets=runtime.user_presets,
                shuffle=runtime.preset_switching_shuffle,
                preset_duration=runtime.preset_duration,
                soft_cut_duration=runtime.soft_cut_duration,
                easter_egg=runtime.easter_egg,
                preset_start_clean=runtime.preset_start_clean,
                hard_cut_enabled=runtime.hard_cut_enabled,
                hard_cut_duration=runtime.hard_cut_duration,
                hard_cut_sensitivity=runtime.hard_cut_sensitivity,
            )
            continue
        _reapply_on_seek(
            layer,
            delta_sec,
            preset_duration=runtime.preset_duration,
            soft_cut_duration=runtime.soft_cut_duration,
            easter_egg=runtime.easter_egg,
            preset_start_clean=runtime.preset_start_clean,
            hard_cut_enabled=runtime.hard_cut_enabled,
            hard_cut_duration=runtime.hard_cut_duration,
            hard_cut_sensitivity=runtime.hard_cut_sensitivity,
        )


def apply_preset_switching(
    layer: StemLayer,
    *,
    mode: PresetSwitchingMode,
    scope: PresetSwitchingScope,
    user_presets: list[str] | None = None,
    shuffle: bool = DEFAULT_PRESET_SWITCHING_SHUFFLE,
    preset_duration: float = DEFAULT_PRESET_DURATION,
    soft_cut_duration: float = DEFAULT_SOFT_CUT_DURATION,
    easter_egg: float = DEFAULT_EASTER_EGG,
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN,
    hard_cut_enabled: bool = DEFAULT_HARD_CUT_ENABLED,
    hard_cut_duration: float = DEFAULT_HARD_CUT_DURATION,
    hard_cut_sensitivity: float = DEFAULT_HARD_CUT_SENSITIVITY,
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
    _apply_projectm_timing(
        pm,
        preset_duration=preset_duration,
        soft_cut_duration=soft_cut_duration,
        easter_egg=easter_egg,
        preset_start_clean=preset_start_clean,
        hard_cut_enabled=hard_cut_enabled,
        hard_cut_duration=hard_cut_duration,
        hard_cut_sensitivity=hard_cut_sensitivity,
    )

    if scope == "user_defined":
        paths = [Path(path) for path in (user_presets or [])]
        if not paths:
            layer.auto_preset_path = None
            pm.lock_preset(True)
            if on_empty is not None:
                on_empty()
            return

        playlist = ProjectMPlaylist.create()
        playlist.connect(pm, on_preset_loaded=_auto_preset_loaded_callback(layer))
        playlist.add_presets(paths, allow_duplicates=True)
        playlist.set_shuffle(shuffle)
        layer.projectm_playlist = playlist
        _sync_projectm_playlist_position(layer)
        restart_projectm_preset_timer(layer)
        return

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
    # Match Cleave browse order (sorted filenames); add_path uses readdir order.
    playlist.sort()
    playlist.set_shuffle(shuffle)
    layer.projectm_playlist = playlist
    _sync_projectm_playlist_position(layer)
    restart_projectm_preset_timer(layer)


def load_manual_preset_clean(
    layer: StemLayer,
    *,
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN,
) -> None:
    """Load the current browse preset with a guaranteed clean (black) boot.

    ``load_preset(smooth=False)`` inherits the previous preset's final frame as
    projectM feedback state, so a preset that only develops when seeded looks
    fine after a switch even when it cannot start from black. Manual browsing
    forces ``preset_start_clean`` for this load so each preset boots from black,
    then restores the layer's configured value for later auto-switch transitions.
    """
    pm = layer.pm
    if layer.playlist.current is None:
        return
    pm.set_preset_start_clean(True)
    layer.playlist.load_into(pm, smooth=False)
    pm.set_preset_start_clean(preset_start_clean)


def sync_manual_browse_with_user_defined_rotation(layer: StemLayer) -> None:
    """Align user-defined rotation state after manual preset browse."""
    current = layer.playlist.current
    if current is None:
        return
    layer.auto_preset_path = current.resolve()
    _sync_projectm_playlist_position(layer)


def restart_projectm_preset_timer(layer: StemLayer) -> None:
    """Load the active auto-switch preset and restart projectM's duration timer."""
    path = active_auto_preset_path(layer)
    if path is None:
        return
    layer.pm.load_preset(path, smooth=False)
    _record_auto_preset(layer, path)


def reset_projectm_preset_timer(
    layer: StemLayer,
    *,
    preset_duration: float = DEFAULT_PRESET_DURATION,
    soft_cut_duration: float = DEFAULT_SOFT_CUT_DURATION,
    easter_egg: float = DEFAULT_EASTER_EGG,
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN,
    hard_cut_enabled: bool = DEFAULT_HARD_CUT_ENABLED,
    hard_cut_duration: float = DEFAULT_HARD_CUT_DURATION,
    hard_cut_sensitivity: float = DEFAULT_HARD_CUT_SENSITIVITY,
) -> None:
    """Reset projectM's duration timer without reloading the preset file."""
    pm = layer.pm
    pm.lock_preset(True)
    pm.lock_preset(False)
    _apply_projectm_timing(
        pm,
        preset_duration=preset_duration,
        soft_cut_duration=soft_cut_duration,
        easter_egg=easter_egg,
        preset_start_clean=preset_start_clean,
        hard_cut_enabled=hard_cut_enabled,
        hard_cut_duration=hard_cut_duration,
        hard_cut_sensitivity=hard_cut_sensitivity,
    )


def active_auto_preset_path(layer: StemLayer) -> Path | None:
    if layer.auto_preset_path is not None:
        return layer.auto_preset_path
    current = layer.playlist.current
    if current is None:
        return None
    return current.resolve()


def _reapply_on_seek(
    layer: StemLayer,
    delta_sec: float,
    *,
    preset_duration: float = DEFAULT_PRESET_DURATION,
    soft_cut_duration: float = DEFAULT_SOFT_CUT_DURATION,
    easter_egg: float = DEFAULT_EASTER_EGG,
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN,
    hard_cut_enabled: bool = DEFAULT_HARD_CUT_ENABLED,
    hard_cut_duration: float = DEFAULT_HARD_CUT_DURATION,
    hard_cut_sensitivity: float = DEFAULT_HARD_CUT_SENSITIVITY,
) -> None:
    playlist = layer.projectm_playlist
    if playlist is None:
        return
    pm = layer.pm
    pm.lock_preset(False)
    _apply_projectm_timing(
        pm,
        preset_duration=preset_duration,
        soft_cut_duration=soft_cut_duration,
        easter_egg=easter_egg,
        preset_start_clean=preset_start_clean,
        hard_cut_enabled=hard_cut_enabled,
        hard_cut_duration=hard_cut_duration,
        hard_cut_sensitivity=hard_cut_sensitivity,
    )
    playlist.connect(pm, on_preset_loaded=_auto_preset_loaded_callback(layer))
    if delta_sec < 0:
        restart_projectm_preset_timer(layer)
    else:
        reset_projectm_preset_timer(
            layer,
            preset_duration=preset_duration,
            soft_cut_duration=soft_cut_duration,
            easter_egg=easter_egg,
            preset_start_clean=preset_start_clean,
            hard_cut_enabled=hard_cut_enabled,
            hard_cut_duration=hard_cut_duration,
            hard_cut_sensitivity=hard_cut_sensitivity,
        )


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
