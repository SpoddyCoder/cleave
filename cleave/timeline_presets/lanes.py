"""Write woven changes as timeline clips, and generate a whole layers timeline."""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence

from cleave.cue_roles import CUE_ROLE_BLEND, CueRole
from cleave.signals import Signals
from cleave.song_markers import SongMarker, resolve_sections
from cleave.stems import StemSource
from cleave.timeline import LEVEL_EPS, SlotCue, TimelineLane, canonicalize
from cleave.timeline_presets.plan import plan_timeline
from cleave.timeline_presets.shapes import section_parts
from cleave.timeline_presets.weave import SlotEvents, weave

_EPS = 1e-6


def compose_layers_timeline(
    slots: Sequence[str],
    duration_sec: float,
    rng: random.Random,
    bar_times: Sequence[float] = (),
    song_markers: Sequence[SongMarker] = (),
    density_bias: int = 0,
    signals: Signals | None = None,
    slot_stems: Mapping[str, StemSource] | None = None,
) -> dict[str, TimelineLane]:
    """A layers timeline for the song's sections.

    Without signals and stems there are no roles, so each layer keeps its own
    blend mode.
    """
    slot_list = list(slots)
    if not slot_list or duration_sec <= 0.0:
        return {}
    bars = [float(t) for t in bar_times if 0.0 <= float(t) < duration_sec]
    parts = section_parts(resolve_sections(song_markers, duration_sec))
    plan = plan_timeline(
        slot_list,
        parts,
        bars=bars,
        density_bias=density_bias,
        rng=rng,
        signals=signals if slot_stems else None,
        slot_stems=slot_stems,
    )
    woven = weave(slot_list, plan, duration_sec)
    return {slot: lane_from_events(woven[slot], duration_sec) for slot in slot_list}


def lane_from_events(events: SlotEvents, duration_sec: float) -> TimelineLane:
    """One layer's clips: a cue for every change of opacity, role, or preset."""
    times = sorted(
        {round(t, 6) for t, _ in events.levels}
        | {round(t, 6) for t, _ in events.roles}
        | {round(t, 6) for t in events.recasts}
    )
    recasts = {round(t, 6) for t in events.recasts}
    cues: list[SlotCue] = []
    level = 0.0
    role: CueRole | None = None
    for t in times:
        if t >= duration_sec - _EPS:
            break
        new_level = events.level_at(t)
        new_role = _role_at(events.roles, t) if new_level > LEVEL_EPS else None
        recast = t in recasts and level > LEVEL_EPS and new_level > LEVEL_EPS
        if abs(new_level - level) <= LEVEL_EPS and new_role == role and not recast:
            continue
        held = level > LEVEL_EPS and new_level > LEVEL_EPS
        cues.append(
            SlotCue(
                t=t,
                level=new_level,
                blend=None if new_role is None else CUE_ROLE_BLEND[new_role],
                role=new_role,
                cut="none",
                recast=recast,
                # Same opacity with a new role still has to take it.
                anchor=held and not recast and abs(new_level - level) <= LEVEL_EPS,
            )
        )
        level, role = new_level, new_role
    # Off from the start, so a layer the plan never uses stays off.
    return TimelineLane(baseline=0.0, cues=canonicalize(0.0, cues))


def _role_at(roles: Sequence[tuple[float, CueRole | None]], t: float) -> CueRole | None:
    role: CueRole | None = None
    for at, value in sorted(roles, key=lambda item: item[0]):
        if at > t + _EPS:
            break
        role = value
    return role
