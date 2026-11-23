"""Populate a layer's ordered preset_list from directory or timeline role pools."""

from __future__ import annotations

import random
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from cleave.cue_roles import CUE_ROLES, CueRole
from cleave.preset_library import PresetCatalog
from cleave.preset_playlist import PresetPlaylist, milk_files_in_dir
from cleave.timeline import (
    SlotCue,
    TimelineFadeGroup,
    empty_lane,
    fold_lane_baseline,
    lane_on_transition_cues,
)
from cleave.viz.session import TuningSession
from cleave.preset_list_entry import PresetListEntry
from cleave.viz.user_presets import USER_PRESETS_DIRNAME, copy_with_dedup

DEFAULT_POPULATE_ROLE: CueRole = "bed"

DirectoryOrder = Literal["random", "sequential"]


def _fade_groups(session: TuningSession) -> tuple[TimelineFadeGroup, TimelineFadeGroup]:
    tl = session.timeline
    hard = TimelineFadeGroup(
        enabled=tl.hard_cut_fades.enabled,
        fade_in=tl.hard_cut_fades.fade_in,
        fade_out=tl.hard_cut_fades.fade_out,
        crossfade=tl.hard_cut_fades.crossfade,
    )
    soft = TimelineFadeGroup(
        enabled=tl.soft_cut_fades.enabled,
        fade_in=tl.soft_cut_fades.fade_in,
        fade_out=tl.soft_cut_fades.fade_out,
        crossfade=tl.soft_cut_fades.crossfade,
    )
    return hard, soft


def _switch_cues(session: TuningSession, slot: str) -> list[SlotCue]:
    """Start cues of the layer's clips that start a preset, in time order."""
    hard, soft = _fade_groups(session)
    lane = fold_lane_baseline(
        session.timeline.lanes.get(slot) or empty_lane(),
        1.0 if session.layers[slot].enabled else 0.0,
    )
    return [
        cue
        for _t, cue in lane_on_transition_cues(
            lane, hard_cut_fades=hard, soft_cut_fades=soft
        )
    ]


def on_segment_count(session: TuningSession, slot: str) -> int:
    """How many of the layer's clips start a preset."""
    return len(_switch_cues(session, slot))


def clips_missing_preset_count(session: TuningSession, slot: str) -> int:
    """How many of the layer's clips start a preset but hold none."""
    return sum(1 for cue in _switch_cues(session, slot) if cue.preset is None)


def on_segment_populate_count(session: TuningSession, slot: str) -> int:
    """How many presets timeline populate modes add for ``slot``."""
    return max(1, on_segment_count(session, slot))


def _on_segment_roles(session: TuningSession, slot: str) -> list[CueRole | None]:
    return [cue.role for cue in _switch_cues(session, slot)]


def copy_into_user_presets(
    project_dir: Path,
    sources: Sequence[Path],
) -> list[PresetListEntry]:
    dest_dir = project_dir / USER_PRESETS_DIRNAME
    return [copy_with_dedup(dest_dir, src) for src in sources if src.is_file()]


def browse_pool(playlist: PresetPlaylist) -> tuple[Path, ...]:
    """Presets the layer is browsing (folder or collection), blacklist excluded."""
    if playlist.collection is not None:
        return playlist.catalog.collection_paths(playlist.collection)
    return playlist.catalog.visible(milk_files_in_dir(playlist.current_dir))


def catalog_has_role_presets(catalog: PresetCatalog) -> bool:
    """Whether the preset library gives any preset a clip role."""
    return any(catalog.collection_paths(role) for role in CUE_ROLES)


def _pick_random(pool: Sequence[Path], rng: random.Random) -> Path | None:
    if not pool:
        return None
    return rng.choice(list(pool))


def populate_from_directory(
    session: TuningSession,
    slot: str,
    *,
    project_dir: Path,
    max_count: int | None = None,
    order: DirectoryOrder = "random",
    rng: random.Random | None = None,
) -> list[PresetListEntry]:
    """Replace ``preset_list`` with copies from the layer's browse folder or collection.

    Timeline trigger: one pick per on-segment (from lane cues if any).
    Other triggers: ``*.milk`` in the browse dir (``max_count`` limits the
    selection; ``None`` uses the full pool).

    ``order="random"`` shuffles or samples; ``order="sequential"`` walks the
    sorted directory order (cycling when more picks than files).
    """
    layer = session.layers[slot]
    pool = list(browse_pool(layer.playlist))
    if not pool:
        layer.preset_list = []
        return []
    rng = rng or random.Random()
    if layer.preset_switching_trigger == "timeline":
        count = on_segment_populate_count(session, slot)
        if order == "sequential":
            sources = [pool[i % len(pool)] for i in range(count)]
        else:
            picks = [_pick_random(pool, rng) for _ in range(count)]
            sources = [path for path in picks if path is not None]
    elif order == "sequential":
        sources = list(pool)
        if max_count is not None:
            sources = sources[:max_count]
    elif max_count is None:
        sources = list(pool)
        rng.shuffle(sources)
    else:
        sources = rng.sample(pool, min(max_count, len(pool)))
    layer.preset_list = copy_into_user_presets(project_dir, sources)
    return list(layer.preset_list)


def populate_from_cue_marker_roles(
    session: TuningSession,
    slot: str,
    *,
    project_dir: Path,
    catalog: PresetCatalog,
    default_role: CueRole = DEFAULT_POPULATE_ROLE,
    rng: random.Random | None = None,
) -> list[PresetListEntry]:
    """Replace ``preset_list`` with one pick per on-segment from each cue's role pool."""
    layer = session.layers[slot]
    roles = _on_segment_roles(session, slot)
    if not roles:
        roles = [default_role]
    rng = rng or random.Random()
    sources: list[Path] = []
    for role in roles:
        effective = role if role is not None else default_role
        pool = list(catalog.collection_paths(effective))
        pick = _pick_random(pool, rng)
        if pick is not None:
            sources.append(pick)
    layer.preset_list = copy_into_user_presets(project_dir, sources)
    return list(layer.preset_list)


def repopulate_preset_lists(
    session: TuningSession,
    *,
    mode: str,
    project_dir: Path,
    catalog: PresetCatalog,
    rng: random.Random | None = None,
) -> None:
    """Give every clip a preset on each-clip layers after Generate timeline.

    ``mode`` is a staged ``TimelinePresetRepopulate`` value.
    """
    rng = rng or random.Random()
    for slot in session.layer_z_order:
        runtime = session.layers.get(slot)
        if runtime is None or runtime.preset_switching != "on":
            continue
        if runtime.preset_switching_trigger != "timeline":
            continue
        if mode == "cue roles":
            populate_from_cue_marker_roles(
                session,
                slot,
                project_dir=project_dir,
                catalog=catalog,
                rng=rng,
            )
        elif mode == "directory sequential":
            populate_from_directory(
                session,
                slot,
                project_dir=project_dir,
                order="sequential",
                rng=rng,
            )
        else:
            populate_from_directory(
                session,
                slot,
                project_dir=project_dir,
                order="random",
                rng=rng,
            )
