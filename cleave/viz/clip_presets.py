"""Presets held on timeline clips, for layers whose presets change on each clip.

With the ``timeline`` trigger ("each clip"), every clip that starts a preset
holds it on its start cue (``SlotCue.preset``); a clip butting the one before
may instead continue that clip's preset. The layer's ``preset_list`` mirrors
those presets in clip order, so the Preset List page, the problem marks, and
the switching schedule read one list. ``sync_each_clip_layers`` keeps the two
in step at the end of every recorded edit: a list edit is pushed onto the
clips, and a timeline edit gives new clips a preset, then refreshes the list.

Also here: laying a preset list out as clips (entering "each clip" on an
untouched row), and seeding the timeline the first time it is turned on so
nothing on screen changes.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from cleave.cue_roles import CueRole
from cleave.preset_library import PresetCatalog
from cleave.preset_list_entry import PresetListEntry
from cleave.timeline import (
    SlotCue,
    TimelineClip,
    TimelineLane,
    canonicalize,
    clip_butts_previous,
    clip_shown_preset,
    clip_starts_preset,
    empty_lane,
    lane_clips,
    set_clip_preset,
    switching_clips,
)
from cleave.viz.session import TuningSession

# Shown for a clip that continues the preset of the clip before it.
CONTINUES_GLYPH = "\u21b3"


def preset_label(name: str) -> str:
    """A preset file name as clips show it, without ``.milk``."""
    return name[:-5] if name.lower().endswith(".milk") else name


# Picks a preset for a new clip on ``slot`` with ``role``; None when none is found.
ClipPresetPick = Callable[[str, CueRole | None], PresetListEntry | None]


def is_each_clip(session: TuningSession, slot: str) -> bool:
    """Whether the layer's presets change on each timeline clip."""
    layer = session.layers.get(slot)
    return (
        layer is not None
        and layer.preset_switching == "on"
        and layer.preset_switching_trigger == "timeline"
    )


def layer_inherit(session: TuningSession, slot: str) -> float:
    """Level a lane with no baseline takes: the layer's enabled switch."""
    return 1.0 if session.layers[slot].enabled else 0.0


def _lane(session: TuningSession, slot: str) -> TimelineLane:
    return session.timeline.lanes.get(slot) or empty_lane()


def row_switching_clips(
    session: TuningSession, slot: str, duration_sec: float
) -> list[TimelineClip]:
    """The layer's clips that start a preset, in time order."""
    return switching_clips(
        lane_clips(
            _lane(session, slot),
            inherit=layer_inherit(session, slot),
            duration_sec=duration_sec,
        )
    )


def clip_preset_list(
    session: TuningSession, slot: str, duration_sec: float
) -> list[PresetListEntry]:
    """The presets the layer's clips start, in clip order (clips without one skipped)."""
    return [
        clip.preset
        for clip in row_switching_clips(session, slot, duration_sec)
        if clip.preset is not None
    ]


def clips_without_preset(
    session: TuningSession, slot: str, duration_sec: float
) -> list[TimelineClip]:
    """Clips that should start a preset but hold none."""
    return [
        clip
        for clip in row_switching_clips(session, slot, duration_sec)
        if clip.preset is None
    ]


def lane_untouched(session: TuningSession, slot: str) -> bool:
    """True while the layer's row has no cues: one whole-song clip, or none."""
    return not _lane(session, slot).cues


def assign_clip_presets(
    session: TuningSession,
    slot: str,
    duration_sec: float,
    presets: Sequence[PresetListEntry | None],
) -> None:
    """Give the Nth clip that starts a preset ``presets[N]``; None leaves it as it is."""
    lane = _lane(session, slot)
    inherit = layer_inherit(session, slot)
    starts = [clip.start for clip in row_switching_clips(session, slot, duration_sec)]
    for start, preset in zip(starts, presets):
        if preset is None:
            continue
        lane = set_clip_preset(
            lane, start, preset, inherit=inherit, duration_sec=duration_sec
        )
    session.timeline.lanes[slot] = lane


def fill_missing_clip_presets(
    session: TuningSession,
    slot: str,
    duration_sec: float,
    pick: ClipPresetPick | None,
    *,
    from_entries: Sequence[PresetListEntry] = (),
) -> int:
    """Give each clip without a preset the next of ``from_entries``, then a pick.

    Returns how many clips got a preset.
    """
    queue = list(from_entries)
    presets: list[PresetListEntry | None] = []
    filled = 0
    for clip in row_switching_clips(session, slot, duration_sec):
        if clip.preset is not None:
            presets.append(None)
            continue
        preset = queue.pop(0) if queue else (pick(slot, clip.role) if pick else None)
        presets.append(preset)
        if preset is not None:
            filled += 1
    if filled:
        assign_clip_presets(session, slot, duration_sec, presets)
    return filled


def lay_out_list_as_clips(
    session: TuningSession,
    slot: str,
    duration_sec: float,
    entries: Sequence[PresetListEntry],
) -> int:
    """Replace the row with butted clips, one per preset duration, playing ``entries``.

    The schedule the timer trigger plays: clip ``k`` starts at
    ``k * preset_duration`` with ``entries[k % len(entries)]``, with no fade,
    and the last clip runs to the song end. Returns the clip count (0 leaves
    the row as it was).
    """
    layer = session.layers[slot]
    period = max(0.001, float(layer.preset_duration))
    if not entries or duration_sec <= 0.0:
        return 0
    count = max(1, math.ceil(duration_sec / period - 1e-9))
    cues = [
        SlotCue(
            t=k * period,
            level=1.0,
            cut="none",
            recast=k > 0,
            preset=entries[k % len(entries)],
        )
        for k in range(count)
    ]
    session.timeline.lanes[slot] = TimelineLane(
        baseline=0.0, cues=canonicalize(0.0, cues)
    )
    return count


def timeline_is_empty(session: TuningSession) -> bool:
    """True when no layer's row has been set: the timeline has never been used."""
    return all(
        lane.baseline is None and not lane.cues
        for lane in session.timeline.lanes.values()
    )


def seed_timeline_from_switching(
    session: TuningSession, duration_sec: float
) -> list[str]:
    """Build the first timeline so turning it on changes nothing on screen.

    An enabled layer switching on a timer gets its schedule as clips, and its
    presets then change on each clip; one already set to change on each clip
    gets its list laid out the same way. Every other enabled layer gets one
    whole-song clip and keeps its switching; a disabled layer stays off.
    Returns the slots moved from the timer to "each clip".
    """
    converted: list[str] = []
    for slot in session.layer_z_order:
        layer = session.layers[slot]
        if not layer.enabled:
            session.timeline.lanes[slot] = TimelineLane(baseline=0.0, cues=[])
            continue
        trigger = layer.preset_switching_trigger
        if (
            layer.preset_switching == "on"
            and trigger in ("timer", "timeline")
            and lay_out_list_as_clips(
                session, slot, duration_sec, list(layer.preset_list)
            )
        ):
            if trigger == "timer":
                layer.preset_switching_trigger = "timeline"
                converted.append(slot)
            continue
        session.timeline.lanes[slot] = TimelineLane(baseline=1.0, cues=[])
    return converted


def mirror_list_from_clips(
    session: TuningSession, slot: str, duration_sec: float
) -> bool:
    """Set the layer's preset list to its clips' presets. True when it changed."""
    layer = session.layers[slot]
    entries = clip_preset_list(session, slot, duration_sec)
    if layer.preset_list == entries:
        return False
    layer.preset_list[:] = entries
    return True


def sync_each_clip_layers(
    session: TuningSession,
    duration_sec: float,
    lists_before: Mapping[str, Sequence[PresetListEntry]],
    pick: ClipPresetPick | None,
) -> list[str]:
    """Keep each-clip layers' clips and preset lists in step after an edit.

    A list changed by the edit is pushed onto the clips in order. Clips left
    without a preset then get one from ``pick``, and the list is rebuilt from
    the clips. Returns the slots whose list changed, so switching can reload.
    """
    changed: list[str] = []
    for slot in session.layer_z_order:
        if not is_each_clip(session, slot):
            continue
        layer = session.layers[slot]
        before = list(lists_before.get(slot, []))
        if list(layer.preset_list) != before:
            assign_clip_presets(
                session, slot, duration_sec, list(layer.preset_list)
            )
        fill_missing_clip_presets(session, slot, duration_sec, pick)
        mirror_list_from_clips(session, slot, duration_sec)
        if list(layer.preset_list) != before:
            changed.append(slot)
    return changed


@dataclass
class ClipPresetPicker:
    """Picks a new clip's preset: one with the clip's role, else the layer's folder.

    The pick is copied into the project's presets folder, like a list preset.
    """

    session: TuningSession
    project_dir: Path | None
    catalog: PresetCatalog | None
    rng: random.Random = field(default_factory=random.Random)

    def __call__(self, slot: str, role: CueRole | None) -> PresetListEntry | None:
        from cleave.viz.preset_list_populate import (
            browse_pool,
            copy_into_user_presets,
        )

        if self.project_dir is None:
            return None
        pool: Sequence[Path] = ()
        if role is not None and self.catalog is not None:
            pool = tuple(self.catalog.collection_paths(role))
        if not pool:
            pool = tuple(browse_pool(self.session.layers[slot].playlist))
        if not pool:
            return None
        copied = copy_into_user_presets(self.project_dir, [self.rng.choice(pool)])
        return copied[0] if copied else None


@dataclass(frozen=True)
class ClipPresetView:
    """The selected clip's preset, as the inspector and clip menu show it.

    ``name`` is the preset playing during the clip (its own, or the one it
    continues), or None. ``starts`` is whether the clip starts it, and
    ``butted`` whether it touches the clip before, so it may continue that
    clip's preset instead. ``list_index`` is the clip's entry in the layer's
    preset list, when it starts a preset of its own.
    """

    name: str | None
    starts: bool
    butted: bool
    list_index: int | None


def clip_preset_view(
    session: TuningSession, slot: str, clip: TimelineClip, duration_sec: float
) -> ClipPresetView:
    clips = lane_clips(
        _lane(session, slot),
        inherit=layer_inherit(session, slot),
        duration_sec=duration_sec,
    )
    shown = clip_shown_preset(clips, clip)
    starts = clip_starts_preset(clips, clip)
    list_index: int | None = None
    if starts and clip.preset is not None:
        with_presets = [
            other.start
            for other in switching_clips(clips)
            if other.preset is not None
        ]
        if clip.start in with_presets:
            list_index = with_presets.index(clip.start)
    return ClipPresetView(
        name=None if shown is None else shown.display_name,
        starts=starts,
        butted=clip_butts_previous(clips, clip),
        list_index=list_index,
    )
