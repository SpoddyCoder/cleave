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
from cleave.preset_rotation import PresetRotation
from cleave.projectm import ProjectM
from cleave.projectm_playlist import ProjectMPlaylist
from cleave.timeline import (
    TimelineFadeGroup,
    empty_lane,
    lane_on_transition_count,
)
from cleave.viz.layer import StemLayer

EMPTY_PRESET_LIST_NOTIFICATION = "No presets in switching list"


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
    layer.rotation_anchor = 0


def _timeline_list_index(on_transition_count: int) -> int:
    """0-based list index for timeline switching.

    ``lane_on_transition_count`` is how many on-transitions have fired
    (1 after the first section starts). Populate builds one preset per
    on-segment, so the first section maps to index 0.
    """
    return max(0, int(on_transition_count) - 1)


def _preset_paths(preset_list: list[str] | None) -> list[Path]:
    return [Path(path) for path in (preset_list or [])]


def reapply_projectm_preset_switching(
    session,
    layers_by_slot: dict[str, StemLayer],
    *,
    preset_root: Path,
    delta_sec: float = 0.0,
) -> None:
    """Re-attach projectM playlist switching after seek without reloading browse preset."""
    del preset_root
    from cleave.viz.editor_mode_controls import preset_switching_active

    if not preset_switching_active(session.settings.editor_mode):
        return
    for slot, layer in layers_by_slot.items():
        runtime = session.layers[slot]
        if runtime.preset_switching != "on":
            continue
        if runtime.preset_switching_trigger != "projectm":
            continue
        if layer.projectm_playlist is None:
            apply_preset_switching(
                layer,
                mode=runtime.preset_switching,
                trigger=runtime.preset_switching_trigger,
                preset_list=runtime.preset_list,
                preset_duration=runtime.preset_duration,
                soft_cut_duration=runtime.soft_cut_duration,
                easter_egg=runtime.easter_egg,
                preset_start_clean=runtime.preset_start_clean,
                hard_cut_enabled=runtime.hard_cut_enabled,
                hard_cut_duration=runtime.hard_cut_duration,
                hard_cut_sensitivity=runtime.hard_cut_sensitivity,
                session=session,
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
    trigger: PresetSwitchingTrigger = DEFAULT_PRESET_SWITCHING_TRIGGER,
    preset_list: list[str] | None = None,
    preset_duration: float = DEFAULT_PRESET_DURATION,
    soft_cut_duration: float = DEFAULT_SOFT_CUT_DURATION,
    easter_egg: float = DEFAULT_EASTER_EGG,
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN,
    hard_cut_enabled: bool = DEFAULT_HARD_CUT_ENABLED,
    hard_cut_duration: float = DEFAULT_HARD_CUT_DURATION,
    hard_cut_sensitivity: float = DEFAULT_HARD_CUT_SENSITIVITY,
    on_empty: Callable[[], None] | None = None,
    session=None,
) -> None:
    pm = layer.pm

    if layer.projectm_playlist is not None:
        layer.projectm_playlist.destroy()
        layer.projectm_playlist = None

    if mode != "on":
        _clear_list_rotation(layer)
        layer.auto_preset_path = None
        pm.lock_preset(True)
        pm.set_hard_cut_enabled(False)
        return

    del session

    paths = _preset_paths(preset_list)
    if not paths:
        _clear_list_rotation(layer)
        layer.auto_preset_path = None
        pm.lock_preset(True)
        pm.set_hard_cut_enabled(False)
        if on_empty is not None:
            on_empty()
        return

    if trigger in ("timer", "timeline"):
        # Timer and timeline index the list (timer by duration; timeline by
        # on-transitions when Render: TIMELINE is enabled).
        if trigger == "timeline" and layer.preset_rotation is not None:
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
    _sync_projectm_playlist_position(layer)
    restart_projectm_preset_timer(layer)


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

    anchor = _anchor_index(layer, paths)
    layer.rotation_anchor = anchor
    layer.list_switch_index = 0
    layer.preset_rotation = PresetRotation(paths=tuple(paths), anchor=anchor)
    path = layer.preset_rotation.path_for(0)
    if path is None:
        return
    _load_list_preset(layer, path, preset_start_clean=preset_start_clean)


def rebuild_list_rotation_preserving_index(
    layer: StemLayer,
    *,
    preset_list: list[str] | None = None,
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN,
) -> None:
    """Rebuild list rotation; keep anchor and switch index."""
    paths = _preset_paths(preset_list)
    if not paths:
        _clear_list_rotation(layer)
        layer.auto_preset_path = None
        return

    anchor = layer.rotation_anchor
    index = layer.list_switch_index
    layer.preset_rotation = PresetRotation(paths=tuple(paths), anchor=anchor)
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


def advance_timeline_preset_switching(
    session,
    layers_by_slot: dict[str, StemLayer],
    t_sec: float,
) -> None:
    """Compatibility alias for frame ticks; advances any list-indexed switching."""
    advance_preset_switching(session, layers_by_slot, t_sec)


def resync_timeline_preset_switching(
    session,
    layers_by_slot: dict[str, StemLayer],
    t_sec: float,
) -> None:
    """Resync list-indexed layers after seek."""
    advance_preset_switching(session, layers_by_slot, t_sec)


def _advance_timeline_indexed(
    session,
    layers_by_slot: dict[str, StemLayer],
    t_sec: float,
) -> None:
    if not session.timeline.enabled:
        return
    hard_cut_fades, soft_cut_fades = _timeline_fade_groups(session)
    tl = session.timeline

    for slot, layer in layers_by_slot.items():
        runtime = session.layers[slot]
        if runtime.preset_switching != "on":
            continue
        if runtime.preset_switching_trigger != "timeline":
            continue
        rotation = layer.preset_rotation
        if rotation is None:
            continue
        lane = tl.lanes.get(slot) or empty_lane()
        count = lane_on_transition_count(
            lane,
            t_sec,
            hard_cut_fades=hard_cut_fades,
            soft_cut_fades=soft_cut_fades,
        )
        index = _timeline_list_index(count)
        if index == layer.list_switch_index:
            continue
        path = rotation.path_for(index)
        layer.list_switch_index = index
        if path is None:
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
        if path is None:
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


def reanchor_list_preset_after_browse(
    layer: StemLayer,
    session,
    t_sec: float,
    *,
    preset_list: list[str] | None = None,
) -> None:
    """Keep the browsed preset; next index advance starts from the following entry."""
    pm = layer.pm
    pm.lock_preset(True)
    pm.set_hard_cut_enabled(False)

    paths = _preset_paths(preset_list)
    if not paths:
        _clear_list_rotation(layer)
        return

    index = 0
    runtime = session.layers.get(layer.slot)
    if (
        runtime is not None
        and runtime.preset_switching_trigger == "timeline"
    ):
        hard_cut_fades, soft_cut_fades = _timeline_fade_groups(session)
        lane = session.timeline.lanes.get(layer.slot) or empty_lane()
        index = _timeline_list_index(
            lane_on_transition_count(
                lane,
                t_sec,
                hard_cut_fades=hard_cut_fades,
                soft_cut_fades=soft_cut_fades,
            )
        )
    elif (
        runtime is not None
        and runtime.preset_switching_trigger == "timer"
    ):
        duration = max(0.001, float(runtime.preset_duration))
        index = int(math.floor(max(0.0, t_sec) / duration))

    browse_index = _anchor_index(layer, paths)
    anchor = (browse_index - index) % len(paths)
    layer.rotation_anchor = anchor
    layer.list_switch_index = index
    layer.preset_rotation = PresetRotation(paths=tuple(paths), anchor=anchor)


def load_manual_preset_clean(
    layer: StemLayer,
    *,
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN,
) -> None:
    """Load the current browse preset with a guaranteed clean (black) boot."""
    pm = layer.pm
    current = layer.playlist.current
    if current is None:
        return
    pm.set_preset_start_clean(True)
    layer.playlist.load_into(pm, smooth=False)
    pm.set_preset_start_clean(preset_start_clean)
    layer.auto_preset_path = current.resolve()


def sync_manual_browse_with_list(layer: StemLayer) -> None:
    """Align list-switching state after manual preset browse (projectM trigger)."""
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
    """Track the playing auto-switch preset without moving browse selection."""
    layer.auto_preset_path = path.resolve()


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


def _anchor_index(layer: StemLayer, paths: Sequence[Path]) -> int:
    current = layer.playlist.current
    if current is None or not paths:
        return 0
    resolved = current.resolve()
    for index, candidate in enumerate(paths):
        if candidate.resolve() == resolved:
            return index
    return 0
