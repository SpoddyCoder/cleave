"""Populate a layer's ordered preset_list from directory or timeline role pools."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from cleave.cue_roles import CueRole, role_pool_paths
from cleave.preset_playlist import milk_files_in_dir
from cleave.timeline import (
    TimelineFadeGroup,
    empty_lane,
    lane_on_transition_cues,
)
from cleave.viz.session import TuningSession
from cleave.viz.user_presets import USER_PRESETS_DIRNAME, copy_with_dedup

DEFAULT_POPULATE_ROLE: CueRole = "bed"

DirectoryOrder = Literal["random", "sequential"]


def needed_preset_count(
    *,
    song_duration_sec: float,
    preset_duration: float,
    trigger: str,
) -> int:
    """How many presets to populate for timer/projectm over the song."""
    duration = max(1e-6, float(preset_duration))
    base = math.ceil(float(song_duration_sec) / duration)
    if trigger == "projectm":
        return max(1, base + 2)
    return max(1, base)


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


def _on_segment_count(session: TuningSession, slot: str) -> int:
    hard, soft = _fade_groups(session)
    lane = session.timeline.lanes.get(slot) or empty_lane()
    return len(lane_on_transition_cues(lane, hard_cut_fades=hard, soft_cut_fades=soft))


def on_segment_populate_count(session: TuningSession, slot: str) -> int:
    """How many presets timeline populate modes add for ``slot``."""
    return max(1, _on_segment_count(session, slot))


def _on_segment_roles(session: TuningSession, slot: str) -> list[CueRole | None]:
    hard, soft = _fade_groups(session)
    lane = session.timeline.lanes.get(slot) or empty_lane()
    cues = lane_on_transition_cues(lane, hard_cut_fades=hard, soft_cut_fades=soft)
    return [cue.role for _, cue in cues]


def _copy_into_user_presets(
    project_dir: Path,
    sources: Sequence[Path],
) -> list[str]:
    dest_dir = project_dir / USER_PRESETS_DIRNAME
    out: list[str] = []
    for src in sources:
        if not src.is_file():
            continue
        dest = copy_with_dedup(dest_dir, src)
        out.append(str(dest.resolve()))
    return out


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
) -> list[str]:
    """Replace ``preset_list`` with copies from the layer browse directory.

    Timeline trigger: one pick per on-segment (from lane cues if any).
    Other triggers: ``*.milk`` in the browse dir (``max_count`` limits the
    selection; ``None`` uses the full pool).

    ``order="random"`` shuffles or samples; ``order="sequential"`` walks the
    sorted directory order (cycling when more picks than files).
    """
    layer = session.layers[slot]
    browse_dir = layer.playlist.current_dir
    pool = list(milk_files_in_dir(browse_dir))
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
    layer.preset_list = _copy_into_user_presets(project_dir, sources)
    return list(layer.preset_list)


def populate_from_cue_marker_roles(
    session: TuningSession,
    slot: str,
    *,
    project_dir: Path,
    preset_root: Path,
    default_role: CueRole = DEFAULT_POPULATE_ROLE,
    rng: random.Random | None = None,
) -> list[str]:
    """Replace ``preset_list`` with one pick per on-segment from each cue's role pool."""
    layer = session.layers[slot]
    roles = _on_segment_roles(session, slot)
    if not roles:
        roles = [default_role]
    rng = rng or random.Random()
    sources: list[Path] = []
    for role in roles:
        effective = role if role is not None else default_role
        pool = list(role_pool_paths(preset_root, effective))
        pick = _pick_random(pool, rng)
        if pick is not None:
            sources.append(pick)
    layer.preset_list = _copy_into_user_presets(project_dir, sources)
    return list(layer.preset_list)


def repopulate_preset_lists(
    session: TuningSession,
    *,
    mode: str,
    project_dir: Path,
    preset_root: Path,
    rng: random.Random | None = None,
) -> None:
    """Repopulate layers with timeline-trigger switching after a preset apply.

    ``mode`` is a staged ``TimelinePresetRepopulate`` value. ``no`` is a no-op.
    """
    if mode == "no":
        return
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
                preset_root=preset_root,
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
