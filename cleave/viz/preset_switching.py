"""Apply per-layer preset switching mode to live ProjectM instances."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from cleave.config_schema import (
    DEFAULT_CAST_ROLES_DEFAULT_ROLE,
    DEFAULT_CAST_ROLES_TIMELINE_BEHAVIOUR,
    DEFAULT_EASTER_EGG,
    DEFAULT_HARD_CUT_DURATION,
    DEFAULT_HARD_CUT_ENABLED,
    DEFAULT_HARD_CUT_SENSITIVITY,
    DEFAULT_PRESET_DURATION,
    DEFAULT_PRESET_START_CLEAN,
    DEFAULT_PRESET_SWITCHING_SHUFFLE,
    DEFAULT_PRESET_SWITCHING_SHUFFLE_SALT,
    DEFAULT_SOFT_CUT_DURATION,
    CastRolesTimelineBehaviour,
    PresetSwitchingMode,
    PresetSwitchingRotationSet,
)
from cleave.cue_roles import CUE_ROLES, CueRole, role_pool_paths
from cleave.preset_playlist import milk_files_in_dir
from cleave.preset_rotation import (
    PresetRotation,
    first_shuffle_bag_order,
    layer_rotation_seed,
)
from cleave.projectm import ProjectM
from cleave.projectm_playlist import ProjectMPlaylist
from cleave.timeline import (
    TimelineFadeGroup,
    empty_lane,
    lane_on_transition_count,
    lane_on_transition_cues,
)
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


def _clear_timeline_rotation(layer: StemLayer) -> None:
    layer.preset_rotation = None
    layer.role_rotations = {}
    layer.last_cast_role = None
    layer.timeline_switch_count = 0
    layer.rotation_anchor = 0


def _build_role_rotations(
    layer: StemLayer,
    preset_root: Path,
    *,
    shuffle: bool,
    shuffle_salt: int,
) -> dict[CueRole, PresetRotation]:
    role_rotations: dict[CueRole, PresetRotation] = {}
    for role in CUE_ROLES:
        pool = role_pool_paths(preset_root, role)
        if not pool:
            continue
        role_rotations[role] = PresetRotation(
            paths=pool,
            shuffle=shuffle,
            seed=layer_rotation_seed(
                pool, slot=layer.slot, shuffle_salt=shuffle_salt
            ),
            anchor=0,
        )
    return role_rotations


def _timeline_path_for_count(
    layer: StemLayer,
    *,
    count: int,
) -> Path | None:
    """Seek-stable path for transition ``count`` from the main rotation only."""
    rotation = layer.preset_rotation
    if rotation is None:
        return None
    return rotation.path_for(count)


def _cast_roles_path_for_count(
    layer: StemLayer,
    *,
    count: int,
    lane,
    song_marker_times: Sequence[float],
    song_marker_fades: TimelineFadeGroup,
    standard_fades: TimelineFadeGroup,
    behaviour: CastRolesTimelineBehaviour,
    default_role: CueRole,
) -> Path | None:
    """Seek-stable path after ``count`` on-transitions for cast-roles rotation.

    ``on_transition``: every rise advances; null cue role uses ``last_cast_role``
    (initialised to ``default_role``).
    ``hold_current``: only role-marked cues advance; null-role cues keep the
    prior path (caller skips reload when unchanged).
    Count 0 uses default-role pool entry 0.
    """
    default_rotation = layer.role_rotations.get(default_role) or layer.preset_rotation
    if default_rotation is None:
        return None
    if count < 1:
        layer.last_cast_role = default_role
        return default_rotation.path_for(0)

    cues = lane_on_transition_cues(
        lane,
        song_marker_times=song_marker_times,
        song_marker_fades=song_marker_fades,
        standard_fades=standard_fades,
    )
    last_role: CueRole = default_role
    role_use_count: dict[CueRole, int] = {role: 0 for role in CUE_ROLES}
    active_path: Path | None = default_rotation.path_for(0)
    limit = min(count, len(cues))

    for index in range(limit):
        cue = cues[index][1]
        if behaviour == "hold_current":
            if cue.role is None:
                continue
            role = cue.role
        else:
            role = cue.role if cue.role is not None else last_role
        last_role = role
        role_rotation = layer.role_rotations.get(role)
        if role_rotation is None:
            continue
        active_path = role_rotation.path_for(role_use_count[role])
        role_use_count[role] += 1

    layer.last_cast_role = last_role
    return active_path


def reapply_projectm_preset_switching(
    session,
    layers_by_slot: dict[str, StemLayer],
    *,
    preset_root: Path,
    delta_sec: float = 0.0,
) -> None:
    """Re-attach projectM playlist switching after seek without reloading browse preset."""
    from cleave.viz.editor_mode_controls import preset_switching_active

    if not preset_switching_active(session):
        return
    for slot, layer in layers_by_slot.items():
        runtime = session.layers[slot]
        if runtime.preset_switching != "projectm":
            continue
        if layer.projectm_playlist is None:
            apply_preset_switching(
                layer,
                mode=runtime.preset_switching,
                rotation_set=runtime.preset_switching_rotation_set,
                user_presets=runtime.user_presets,
                shuffle=runtime.preset_switching_shuffle,
                shuffle_salt=runtime.preset_switching_shuffle_salt,
                preset_duration=runtime.preset_duration,
                soft_cut_duration=runtime.soft_cut_duration,
                easter_egg=runtime.easter_egg,
                preset_start_clean=runtime.preset_start_clean,
                hard_cut_enabled=runtime.hard_cut_enabled,
                hard_cut_duration=runtime.hard_cut_duration,
                hard_cut_sensitivity=runtime.hard_cut_sensitivity,
                cast_roles_default_role=runtime.cast_roles_default_role,
                cast_roles_timeline_behaviour=runtime.cast_roles_timeline_behaviour,
                preset_root=preset_root,
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
    rotation_set: PresetSwitchingRotationSet,
    preset_root: Path,
    user_presets: list[str] | None = None,
    shuffle: bool = DEFAULT_PRESET_SWITCHING_SHUFFLE,
    shuffle_salt: int = DEFAULT_PRESET_SWITCHING_SHUFFLE_SALT,
    preset_duration: float = DEFAULT_PRESET_DURATION,
    soft_cut_duration: float = DEFAULT_SOFT_CUT_DURATION,
    easter_egg: float = DEFAULT_EASTER_EGG,
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN,
    hard_cut_enabled: bool = DEFAULT_HARD_CUT_ENABLED,
    hard_cut_duration: float = DEFAULT_HARD_CUT_DURATION,
    hard_cut_sensitivity: float = DEFAULT_HARD_CUT_SENSITIVITY,
    cast_roles_default_role: CueRole = DEFAULT_CAST_ROLES_DEFAULT_ROLE,
    cast_roles_timeline_behaviour: CastRolesTimelineBehaviour = (
        DEFAULT_CAST_ROLES_TIMELINE_BEHAVIOUR
    ),
    on_empty: Callable[[], None] | None = None,
    session=None,
) -> None:
    pm = layer.pm

    if layer.projectm_playlist is not None:
        layer.projectm_playlist.destroy()
        layer.projectm_playlist = None

    if mode != "timeline":
        _clear_timeline_rotation(layer)

    if mode == "none":
        layer.auto_preset_path = None
        pm.lock_preset(True)
        pm.set_hard_cut_enabled(False)
        return

    if mode == "timeline":
        # Already rotating: rebuild in place (shuffle/salt/paths) without
        # resetting anchor or switch count. First enable still re-anchors.
        if layer.preset_rotation is not None:
            rebuild_timeline_preset_rotation_preserving_count(
                layer,
                rotation_set=rotation_set,
                user_presets=user_presets,
                shuffle=shuffle,
                shuffle_salt=shuffle_salt,
                preset_start_clean=preset_start_clean,
                cast_roles_default_role=cast_roles_default_role,
                cast_roles_timeline_behaviour=cast_roles_timeline_behaviour,
                preset_root=preset_root,
                session=session,
            )
            return
        _apply_timeline_preset_switching(
            layer,
            rotation_set=rotation_set,
            user_presets=user_presets,
            shuffle=shuffle,
            shuffle_salt=shuffle_salt,
            preset_start_clean=preset_start_clean,
            cast_roles_default_role=cast_roles_default_role,
            preset_root=preset_root,
            on_empty=on_empty,
        )
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

    # cast_roles is timeline-only; projectM mode uses the browse directory.
    effective_rotation: PresetSwitchingRotationSet = (
        "directory" if rotation_set == "cast_roles" else rotation_set
    )
    paths = _rotation_paths(
        layer,
        rotation_set=effective_rotation,
        user_presets=user_presets,
        preset_root=preset_root,
        cast_roles_default_role=cast_roles_default_role,
    )
    if not paths:
        layer.auto_preset_path = None
        pm.lock_preset(True)
        if on_empty is not None:
            on_empty()
        return

    playlist = ProjectMPlaylist.create()
    playlist.connect(pm, on_preset_loaded=_auto_preset_loaded_callback(layer))
    if shuffle:
        seed = layer_rotation_seed(
            paths, slot=layer.slot, shuffle_salt=shuffle_salt
        )
        ordered = first_shuffle_bag_order(paths, seed=seed)
        playlist.add_presets(ordered, allow_duplicates=True)
    elif effective_rotation == "user_defined":
        playlist.add_presets(paths, allow_duplicates=True)
    else:
        playlist.add_path(
            layer.playlist.current_dir, recurse=False, allow_duplicates=False
        )
        # Match Cleave browse order (sorted filenames); add_path uses readdir order.
        playlist.sort()
    # Deterministic Cleave order when shuffle is on; never use libprojectM shuffle.
    playlist.set_shuffle(False)
    layer.projectm_playlist = playlist
    _sync_projectm_playlist_position(layer)
    restart_projectm_preset_timer(layer)


def _rotation_paths(
    layer: StemLayer,
    *,
    rotation_set: PresetSwitchingRotationSet,
    user_presets: list[str] | None,
    preset_root: Path | None = None,
    cast_roles_default_role: CueRole = DEFAULT_CAST_ROLES_DEFAULT_ROLE,
) -> list[Path]:
    if rotation_set == "user_defined":
        return [Path(path) for path in (user_presets or [])]
    if rotation_set == "cast_roles":
        if preset_root is None:
            return []
        return list(role_pool_paths(preset_root, cast_roles_default_role))
    return list(milk_files_in_dir(layer.playlist.current_dir))


def _anchor_index(layer: StemLayer, paths: Sequence[Path]) -> int:
    current = layer.playlist.current
    if current is None or not paths:
        return 0
    resolved = current.resolve()
    for index, candidate in enumerate(paths):
        if candidate.resolve() == resolved:
            return index
    return 0


def _apply_timeline_preset_switching(
    layer: StemLayer,
    *,
    rotation_set: PresetSwitchingRotationSet,
    user_presets: list[str] | None,
    shuffle: bool,
    shuffle_salt: int,
    preset_start_clean: bool,
    cast_roles_default_role: CueRole,
    preset_root: Path,
    on_empty: Callable[[], None] | None,
) -> None:
    pm = layer.pm
    pm.lock_preset(True)
    pm.set_hard_cut_enabled(False)
    pm.set_preset_start_clean(preset_start_clean)

    paths = _rotation_paths(
        layer,
        rotation_set=rotation_set,
        user_presets=user_presets,
        preset_root=preset_root,
        cast_roles_default_role=cast_roles_default_role,
    )
    if not paths:
        _clear_timeline_rotation(layer)
        layer.auto_preset_path = None
        if on_empty is not None:
            on_empty()
        return

    anchor = _anchor_index(layer, paths)
    layer.rotation_anchor = anchor
    layer.timeline_switch_count = 0
    layer.last_cast_role = (
        cast_roles_default_role if rotation_set == "cast_roles" else None
    )
    layer.preset_rotation = PresetRotation(
        paths=tuple(paths),
        shuffle=shuffle,
        seed=layer_rotation_seed(
            paths, slot=layer.slot, shuffle_salt=shuffle_salt
        ),
        anchor=anchor,
    )
    if rotation_set == "cast_roles":
        layer.role_rotations = _build_role_rotations(
            layer,
            preset_root,
            shuffle=shuffle,
            shuffle_salt=shuffle_salt,
        )
        default_rotation = layer.role_rotations.get(cast_roles_default_role)
        if default_rotation is not None:
            layer.preset_rotation = PresetRotation(
                paths=default_rotation.paths,
                shuffle=shuffle,
                seed=default_rotation.seed,
                anchor=0,
            )
            layer.rotation_anchor = 0
    else:
        layer.role_rotations = {}
    path = layer.preset_rotation.path_for(0)
    if path is None:
        return
    _load_timeline_preset(layer, path, preset_start_clean=preset_start_clean)


def rebuild_timeline_preset_rotation_preserving_count(
    layer: StemLayer,
    *,
    rotation_set: PresetSwitchingRotationSet,
    preset_root: Path,
    user_presets: list[str] | None = None,
    shuffle: bool = DEFAULT_PRESET_SWITCHING_SHUFFLE,
    shuffle_salt: int = DEFAULT_PRESET_SWITCHING_SHUFFLE_SALT,
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN,
    cast_roles_default_role: CueRole = DEFAULT_CAST_ROLES_DEFAULT_ROLE,
    cast_roles_timeline_behaviour: CastRolesTimelineBehaviour = (
        DEFAULT_CAST_ROLES_TIMELINE_BEHAVIOUR
    ),
    session=None,
) -> None:
    """Rebuild timeline rotation; keep anchor and switch count.

    Used after shuffle/salt changes (and other in-place timeline rebuilds) so the
    active ``path_for(count)`` stays aligned with the playhead-derived count.
    """
    paths = _rotation_paths(
        layer,
        rotation_set=rotation_set,
        user_presets=user_presets,
        preset_root=preset_root,
        cast_roles_default_role=cast_roles_default_role,
    )
    if not paths:
        _clear_timeline_rotation(layer)
        layer.auto_preset_path = None
        return

    anchor = layer.rotation_anchor
    count = layer.timeline_switch_count
    layer.preset_rotation = PresetRotation(
        paths=tuple(paths),
        shuffle=shuffle,
        seed=layer_rotation_seed(
            paths, slot=layer.slot, shuffle_salt=shuffle_salt
        ),
        anchor=anchor,
    )
    if rotation_set == "cast_roles":
        layer.role_rotations = _build_role_rotations(
            layer,
            preset_root,
            shuffle=shuffle,
            shuffle_salt=shuffle_salt,
        )
        default_rotation = layer.role_rotations.get(cast_roles_default_role)
        if default_rotation is not None:
            layer.preset_rotation = PresetRotation(
                paths=default_rotation.paths,
                shuffle=shuffle,
                seed=default_rotation.seed,
                anchor=0,
            )
    else:
        layer.role_rotations = {}
        layer.last_cast_role = None

    path: Path | None
    if rotation_set == "cast_roles" and session is not None:
        song_marker_fades, standard_fades, song_marker_times = _timeline_fade_groups(
            session
        )
        lane = session.timeline.lanes.get(layer.slot) or empty_lane()
        path = _cast_roles_path_for_count(
            layer,
            count=count,
            lane=lane,
            song_marker_times=song_marker_times,
            song_marker_fades=song_marker_fades,
            standard_fades=standard_fades,
            behaviour=cast_roles_timeline_behaviour,
            default_role=cast_roles_default_role,
        )
    else:
        path = layer.preset_rotation.path_for(count)
    if path is None:
        return
    _load_timeline_preset(layer, path, preset_start_clean=preset_start_clean)


def _load_timeline_preset(
    layer: StemLayer,
    path: Path,
    *,
    preset_start_clean: bool,
) -> None:
    pm = layer.pm
    pm.set_preset_start_clean(preset_start_clean)
    pm.load_preset(path, smooth=False)
    _record_auto_preset(layer, path)


def _timeline_fade_groups(session) -> tuple[
    TimelineFadeGroup, TimelineFadeGroup, Sequence[float]
]:
    tl = session.timeline
    song_marker_fades = TimelineFadeGroup(
        enabled=tl.song_marker_fades.enabled,
        fade_in=tl.song_marker_fades.fade_in,
        fade_out=tl.song_marker_fades.fade_out,
    )
    standard_fades = TimelineFadeGroup(
        enabled=tl.standard_cue_fades.enabled,
        fade_in=tl.standard_cue_fades.fade_in,
        fade_out=tl.standard_cue_fades.fade_out,
    )
    return song_marker_fades, standard_fades, session.song_markers.times


def advance_timeline_preset_switching(
    session,
    layers_by_slot: dict[str, StemLayer],
    t_sec: float,
) -> None:
    """Load the seek-stable rotation preset when a layer's on-transition count changes.

    Uses committed lane cues only. No-op when timeline is disabled, in preset
    curation, or when the count is unchanged (preset holds).
    """
    from cleave.viz.editor_mode_controls import preset_switching_active

    if not preset_switching_active(session):
        return
    if not session.timeline.enabled:
        return

    song_marker_fades, standard_fades, song_marker_times = _timeline_fade_groups(
        session
    )
    tl = session.timeline

    for slot, layer in layers_by_slot.items():
        runtime = session.layers[slot]
        if runtime.preset_switching != "timeline":
            continue
        rotation = layer.preset_rotation
        if rotation is None:
            continue
        lane = tl.lanes.get(slot) or empty_lane()
        count = lane_on_transition_count(
            lane,
            t_sec,
            song_marker_times=song_marker_times,
            song_marker_fades=song_marker_fades,
            standard_fades=standard_fades,
        )
        if count == layer.timeline_switch_count:
            continue
        if runtime.preset_switching_rotation_set == "cast_roles":
            path = _cast_roles_path_for_count(
                layer,
                count=count,
                lane=lane,
                song_marker_times=song_marker_times,
                song_marker_fades=song_marker_fades,
                standard_fades=standard_fades,
                behaviour=runtime.cast_roles_timeline_behaviour,
                default_role=runtime.cast_roles_default_role,
            )
        else:
            path = _timeline_path_for_count(layer, count=count)
        layer.timeline_switch_count = count
        if path is None:
            continue
        if (
            layer.auto_preset_path is not None
            and path.resolve() == layer.auto_preset_path
        ):
            continue
        _load_timeline_preset(
            layer,
            path,
            preset_start_clean=runtime.preset_start_clean,
        )


def resync_timeline_preset_switching(
    session,
    layers_by_slot: dict[str, StemLayer],
    t_sec: float,
) -> None:
    """Resync timeline-mode layers after seek (load preset for transition count)."""
    advance_timeline_preset_switching(session, layers_by_slot, t_sec)


def reanchor_timeline_preset_after_browse(
    layer: StemLayer,
    session,
    t_sec: float,
    *,
    rotation_set: PresetSwitchingRotationSet,
    user_presets: list[str] | None = None,
    shuffle: bool = DEFAULT_PRESET_SWITCHING_SHUFFLE,
    shuffle_salt: int = DEFAULT_PRESET_SWITCHING_SHUFFLE_SALT,
    cast_roles_default_role: CueRole = DEFAULT_CAST_ROLES_DEFAULT_ROLE,
    preset_root: Path | None = None,
) -> None:
    """Keep the browsed preset; next on-transition advances from the following entry."""
    pm = layer.pm
    pm.lock_preset(True)
    pm.set_hard_cut_enabled(False)

    paths = _rotation_paths(
        layer,
        rotation_set=rotation_set,
        user_presets=user_presets,
        preset_root=preset_root,
        cast_roles_default_role=cast_roles_default_role,
    )
    if not paths:
        _clear_timeline_rotation(layer)
        return

    count = 0
    if session.timeline.enabled:
        song_marker_fades, standard_fades, song_marker_times = _timeline_fade_groups(
            session
        )
        lane = session.timeline.lanes.get(layer.slot) or empty_lane()
        count = lane_on_transition_count(
            lane,
            t_sec,
            song_marker_times=song_marker_times,
            song_marker_fades=song_marker_fades,
            standard_fades=standard_fades,
        )

    browse_index = _anchor_index(layer, paths)
    anchor = (browse_index - count) % len(paths)
    layer.rotation_anchor = anchor
    layer.timeline_switch_count = count
    layer.preset_rotation = PresetRotation(
        paths=tuple(paths),
        shuffle=shuffle,
        seed=layer_rotation_seed(
            paths, slot=layer.slot, shuffle_salt=shuffle_salt
        ),
        anchor=anchor,
    )


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
    """Track the playing auto-switch preset without moving browse selection.

    Browse ``playlist.index`` is the saved/manual preset; mutating it here
    would dirty config during ordinary playback.
    """
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
