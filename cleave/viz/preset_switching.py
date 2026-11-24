"""Apply per-layer preset switching from an explicit ordered preset list."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from pathlib import Path

from cleave.config_schema.layers import (
    DEFAULT_EASTER_EGG,
    DEFAULT_HARD_CUT_DURATION,
    DEFAULT_HARD_CUT_ENABLED,
    DEFAULT_HARD_CUT_SENSITIVITY,
    DEFAULT_PRESET_DURATION,
    DEFAULT_PRESET_START_CLEAN,
    DEFAULT_PRESET_SWITCHING_TRIGGER,
    DEFAULT_SOFT_CUT_DURATION,
    PresetSwitchingMode,
    PresetSwitchingTrigger,
)
from cleave.preset_list_entry import PresetListEntry, entry_paths
from cleave.preset_rotation import PresetRotation
from cleave.projectm import ProjectM
from cleave.projectm_playlist import ProjectMPlaylist
from cleave.timeline import (
    TimelineFadeGroup,
    empty_lane,
    fold_lane_baseline,
    lane_on_transition_cues,
)
from cleave.viz.layer import StemLayer

EMPTY_PRESET_LIST_NOTIFICATION = "No presets in switching list"
BROWSING_PAUSED_NOTIFICATION = (
    "Previewing presets - preset switching is paused. Use the button to resume it."
)
SWITCHING_RESUMED_NOTIFICATION = "Preset switching resumed from previous position."


def panel_layer_number(layer_z_order: Sequence[str], slot: str) -> int:
    """1-based layer number shown on the panel (position in z-order)."""
    return layer_z_order.index(slot) + 1


def layer_notification(layer_z_order: Sequence[str], slot: str, message: str) -> str:
    """Prefix a panel toast with the layer number the user sees."""
    return f"Layer {panel_layer_number(layer_z_order, slot)}: {message}"


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


def _clear_list_rotation(layer: StemLayer) -> None:
    layer.preset_rotation = None
    layer.list_switch_index = 0


def _preset_paths(preset_list: list[PresetListEntry] | None) -> list[Path]:
    return entry_paths(preset_list or [])


def apply_preset_switching(
    layer: StemLayer,
    *,
    mode: PresetSwitchingMode,
    trigger: PresetSwitchingTrigger = DEFAULT_PRESET_SWITCHING_TRIGGER,
    preset_list: list[PresetListEntry] | None = None,
    preset_duration: float = DEFAULT_PRESET_DURATION,
    soft_cut_duration: float = DEFAULT_SOFT_CUT_DURATION,
    easter_egg: float = DEFAULT_EASTER_EGG,
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN,
    hard_cut_enabled: bool = DEFAULT_HARD_CUT_ENABLED,
    hard_cut_duration: float = DEFAULT_HARD_CUT_DURATION,
    hard_cut_sensitivity: float = DEFAULT_HARD_CUT_SENSITIVITY,
    on_empty: Callable[[], None] | None = None,
    session=None,
    resume: bool = False,
) -> None:
    """Set the layer's switching up from its list and settings.

    While the layer is previewing a preset (``switching_paused``), the
    schedule is rebuilt without loading anything, so list and setting edits
    keep the preview on screen. *resume* ends the preview and loads the
    scheduled entry: the song-time entry for timer and timeline, or the entry
    that was playing when the preview started for the projectM trigger.
    """
    previewing = layer.switching_paused
    resume_index = layer.resume_list_index
    keep_preview = previewing and not resume
    pm = layer.pm

    # A running list edit keeps the playing item; a fresh start begins at
    # item 1; a resume returns to the item that was playing at the preview.
    keep_playing = layer.projectm_playlist is not None and not previewing
    if layer.projectm_playlist is not None:
        layer.projectm_playlist.destroy()
        layer.projectm_playlist = None

    del session
    paths = _preset_paths(preset_list)
    if mode != "on" or trigger == "off" or not paths:
        layer.switching_paused = False
        layer.resume_list_index = None
        _clear_list_rotation(layer)
        layer.auto_preset_path = None
        pm.lock_preset(True)
        pm.set_hard_cut_enabled(False)
        if mode == "on" and trigger != "off" and on_empty is not None:
            on_empty()
        return

    if keep_preview:
        _rebuild_schedule_for_preview(layer, paths=paths, trigger=trigger)
        return
    layer.switching_paused = False
    layer.resume_list_index = None

    if trigger in ("timer", "timeline"):
        # Timer and timeline index the list from song time (timer by
        # duration; timeline by on-transitions when the timeline is enabled).
        # An existing rotation keeps its index: the per-frame advance tracks
        # song time, including while paused.
        if layer.preset_rotation is not None:
            rebuild_list_rotation_preserving_index(
                layer,
                preset_list=preset_list,
                preset_start_clean=preset_start_clean,
            )
            return
        _apply_indexed_list_switching(
            layer,
            paths=paths,
            preset_start_clean=preset_start_clean,
        )
        return

    # projectM trigger: feed the list into ProjectMPlaylist.
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
    _clear_list_rotation(layer)
    playlist = ProjectMPlaylist.create()
    playlist.connect(pm, on_preset_loaded=_auto_preset_loaded_callback(layer))
    playlist.add_presets(paths, allow_duplicates=True)
    playlist.set_shuffle(False)
    layer.projectm_playlist = playlist
    if previewing:
        start = 0 if resume_index is None else resume_index
    elif keep_playing:
        start = _list_index_of(playlist, layer.auto_preset_path)
    else:
        start = 0
    _start_projectm_playlist_at(layer, start)
    restart_projectm_preset_timer(layer)


def _rebuild_schedule_for_preview(
    layer: StemLayer,
    *,
    paths: Sequence[Path],
    trigger: PresetSwitchingTrigger,
) -> None:
    """Rebuild the schedule behind a preview without loading a preset."""
    layer.pm.lock_preset(True)
    layer.pm.set_hard_cut_enabled(False)
    if trigger in ("timer", "timeline"):
        index = layer.list_switch_index if layer.preset_rotation is not None else 0
        layer.preset_rotation = PresetRotation(paths=tuple(paths))
        layer.list_switch_index = index
        layer.resume_list_index = None
        return
    _clear_list_rotation(layer)
    if layer.resume_list_index is not None:
        layer.resume_list_index = min(layer.resume_list_index, len(paths) - 1)


def _apply_indexed_list_switching(
    layer: StemLayer,
    *,
    paths: Sequence[Path],
    preset_start_clean: bool,
) -> None:
    pm = layer.pm
    pm.lock_preset(True)
    pm.set_hard_cut_enabled(False)
    pm.set_preset_start_clean(preset_start_clean)

    layer.list_switch_index = 0
    layer.preset_rotation = PresetRotation(paths=tuple(paths))
    path = layer.preset_rotation.path_for(0)
    if path is None:
        return
    _load_list_preset(layer, path, preset_start_clean=preset_start_clean)


def rebuild_list_rotation_preserving_index(
    layer: StemLayer,
    *,
    preset_list: list[PresetListEntry] | None = None,
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN,
) -> None:
    """Rebuild list rotation; keep the switch index."""
    paths = _preset_paths(preset_list)
    if not paths:
        _clear_list_rotation(layer)
        layer.auto_preset_path = None
        return

    index = layer.list_switch_index
    layer.preset_rotation = PresetRotation(paths=tuple(paths))
    path = layer.preset_rotation.path_for(index)
    if path is None:
        return
    _load_list_preset(layer, path, preset_start_clean=preset_start_clean)


def _load_list_preset(
    layer: StemLayer,
    path: Path,
    *,
    preset_start_clean: bool,
) -> None:
    pm = layer.pm
    pm.set_preset_start_clean(preset_start_clean)
    pm.load_preset(path, smooth=False)
    _record_auto_preset(layer, path)


def _timeline_fade_groups(session) -> tuple[TimelineFadeGroup, TimelineFadeGroup]:
    tl = session.timeline
    hard_cut_fades = TimelineFadeGroup(
        enabled=tl.hard_cut_fades.enabled,
        fade_in=tl.hard_cut_fades.fade_in,
        fade_out=tl.hard_cut_fades.fade_out,
        crossfade=tl.hard_cut_fades.crossfade,
    )
    soft_cut_fades = TimelineFadeGroup(
        enabled=tl.soft_cut_fades.enabled,
        fade_in=tl.soft_cut_fades.fade_in,
        fade_out=tl.soft_cut_fades.fade_out,
        crossfade=tl.soft_cut_fades.crossfade,
    )
    return hard_cut_fades, soft_cut_fades


def advance_preset_switching(
    session,
    layers_by_slot: dict[str, StemLayer],
    t_sec: float,
) -> None:
    """Advance list-indexed switching (timeline on-transitions or timer)."""
    from cleave.viz.editor_mode_controls import preset_switching_active

    if not preset_switching_active(session.settings.editor_mode):
        return

    _advance_timeline_indexed(session, layers_by_slot, t_sec)
    _advance_timer_indexed(session, layers_by_slot, t_sec)


def clip_switch_at(
    session,
    slot: str,
    t_sec: float,
) -> tuple[int, Path | None]:
    """The each-clip schedule at ``t_sec``: list index and the preset to play.

    The preset is the one held by the last clip that started a preset at or
    before ``t_sec``, passing over empty clips (or the first such clip, before
    any has started). The index is its place in the layer's preset list,
    which leads with the clips' presets in order. ``None`` when no clip holds
    a preset.
    """
    hard_cut_fades, soft_cut_fades = _timeline_fade_groups(session)
    runtime = session.layers[slot]
    lane = fold_lane_baseline(
        session.timeline.lanes.get(slot) or empty_lane(),
        1.0 if runtime.enabled else 0.0,
    )
    switches = lane_on_transition_cues(
        lane,
        hard_cut_fades=hard_cut_fades,
        soft_cut_fades=soft_cut_fades,
    )
    held = [(trigger, cue) for trigger, cue in switches if cue.preset is not None]
    if not held:
        return 0, None
    index = 0
    for position, (trigger, _cue) in enumerate(held):
        if trigger > t_sec:
            break
        index = position
    preset = held[index][1].preset
    return index, None if preset is None else preset.file


def _advance_timeline_indexed(
    session,
    layers_by_slot: dict[str, StemLayer],
    t_sec: float,
) -> None:
    if not session.timeline.enabled:
        return
    for slot, layer in layers_by_slot.items():
        runtime = session.layers[slot]
        if runtime.preset_switching != "on":
            continue
        if runtime.preset_switching_trigger != "timeline":
            continue
        if layer.preset_rotation is None:
            continue
        index, path = clip_switch_at(session, slot, t_sec)
        layer.list_switch_index = index
        if layer.switching_paused or path is None:
            continue
        if (
            layer.auto_preset_path is not None
            and path.resolve() == layer.auto_preset_path
        ):
            continue
        _load_list_preset(
            layer,
            path,
            preset_start_clean=runtime.preset_start_clean,
        )


def _advance_timer_indexed(
    session,
    layers_by_slot: dict[str, StemLayer],
    t_sec: float,
) -> None:
    for slot, layer in layers_by_slot.items():
        runtime = session.layers[slot]
        if runtime.preset_switching != "on":
            continue
        if runtime.preset_switching_trigger != "timer":
            continue
        rotation = layer.preset_rotation
        if rotation is None or not rotation.paths:
            continue
        duration = max(0.001, float(runtime.preset_duration))
        count = int(math.floor(max(0.0, t_sec) / duration))
        if count == layer.list_switch_index:
            continue
        path = rotation.path_for(count)
        layer.list_switch_index = count
        if layer.switching_paused or path is None:
            continue
        if (
            layer.auto_preset_path is not None
            and path.resolve() == layer.auto_preset_path
        ):
            continue
        _load_list_preset(
            layer,
            path,
            preset_start_clean=runtime.preset_start_clean,
        )


def load_manual_preset_clean(
    layer: StemLayer,
    *,
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN,
) -> None:
    """Load the current browse preset with a guaranteed clean (black) boot."""
    pm = layer.pm
    current = layer.playlist.current
    if current is None:
        layer.auto_preset_path = None
        return
    pm.set_preset_start_clean(True)
    layer.playlist.load_into(pm, smooth=False)
    pm.set_preset_start_clean(preset_start_clean)
    layer.auto_preset_path = current.resolve()


def restart_projectm_preset_timer(layer: StemLayer) -> None:
    """Load the active auto-switch preset and restart projectM's duration timer."""
    path = active_auto_preset_path(layer)
    if path is None:
        return
    layer.pm.load_preset(path, smooth=False)
    _record_auto_preset(layer, path)


def active_auto_preset_path(layer: StemLayer) -> Path | None:
    playing = playing_switching_preset_path(layer)
    if playing is not None:
        return playing
    current = layer.playlist.current
    if current is None:
        return None
    return current.resolve()


def _auto_preset_loaded_callback(layer: StemLayer) -> Callable[[Path], None]:
    def on_preset_loaded(path: Path) -> None:
        # The playlist reports only a switch that loaded.
        layer.pm.clear_preset_failure(path)
        _record_auto_preset(layer, path)

    return on_preset_loaded


def _record_auto_preset(layer: StemLayer, path: Path) -> None:
    """Track the playing auto-switch preset without moving browse selection."""
    layer.auto_preset_path = path.resolve()


def playing_switching_preset_path(layer: StemLayer) -> Path | None:
    """Preset currently playing from the switching list, if any.

    While ``switching_paused``, the browse playlist current is playing.
    projectM position and timer/timeline rotation win over a stale
    ``auto_preset_path`` when switching is running.
    """
    if layer.switching_paused:
        current = layer.playlist.current
        if current is None:
            return None
        return current.resolve()
    playlist = layer.projectm_playlist
    if playlist is not None:
        item = playlist.item(playlist.get_position())
        if item is not None:
            return item.resolve()
    rotation = layer.preset_rotation
    if rotation is not None:
        path = rotation.path_for(layer.list_switch_index)
        if path is not None:
            return path.resolve()
    if layer.auto_preset_path is not None:
        return layer.auto_preset_path
    return None


def switching_list_index(layer: StemLayer) -> int | None:
    """Switching-list index that is playing, or that resumes after a pause.

    Timer and timeline follow song time, so their index keeps moving while
    paused. The projectM trigger resumes at the item playing when browsing
    paused it, or at the list item auditioned since.
    """
    rotation = layer.preset_rotation
    if rotation is not None:
        if not rotation.paths:
            return None
        return layer.list_switch_index % len(rotation.paths)
    if layer.switching_paused:
        return layer.resume_list_index
    playlist = layer.projectm_playlist
    if playlist is None or playlist.size() == 0:
        return None
    return playlist.get_position()


def _list_index_of(playlist: ProjectMPlaylist, path: Path | None) -> int:
    if path is None:
        return 0
    target = path.resolve()
    for index in range(playlist.size()):
        item = playlist.item(index)
        if item is not None and item.resolve() == target:
            return index
    return 0


def _start_projectm_playlist_at(layer: StemLayer, index: int) -> None:
    playlist = layer.projectm_playlist
    if playlist is None:
        return
    size = playlist.size()
    if size == 0:
        return
    index = min(max(0, index), size - 1)
    playlist.set_position(index, hard_cut=True)
    item = playlist.item(index)
    if item is not None:
        _record_auto_preset(layer, item)
