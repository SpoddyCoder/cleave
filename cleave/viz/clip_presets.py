"""Presets held on timeline clips, for layers whose presets change on each clip.

With the ``timeline`` trigger ("each clip"), a clip that starts a preset holds
it on its start cue (``SlotCue.preset``); a clip butting the one before may
instead continue that clip's preset. The layer's ``preset_list`` is those
presets in clip order, then the spares: presets no clip holds. A clip that
should start a preset but holds none is empty, and plays on with the preset
before it. ``sync_each_clip_layers`` keeps list and clips in step at the end
of every recorded edit: list edits flow along the clips, and timeline edits
leave the other clips' presets alone.

Also here: seeding the timeline the first time it is turned on so nothing on
screen changes.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from cleave.cue_roles import CueRole
from cleave.preset_library import PresetCatalog
from cleave.preset_list_entry import PresetListEntry
from cleave.timeline import (
    TimelineClip,
    TimelineLane,
    clear_clip_preset,
    clip_butts_previous,
    clip_shown_preset,
    clip_starts_preset,
    empty_lane,
    lane_clips,
    set_clip_preset,
    start_clip_preset,
    switching_clips,
)
from cleave.viz.edit_history import EditSnapshot
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


def assign_clip_presets(
    session: TuningSession,
    slot: str,
    duration_sec: float,
    presets: Sequence[PresetListEntry | None],
) -> None:
    """Give the Nth clip that starts a preset ``presets[N]``; None leaves it empty.

    Clips past the end of ``presets`` are left empty.
    """
    lane = _lane(session, slot)
    inherit = layer_inherit(session, slot)
    clips = row_switching_clips(session, slot, duration_sec)
    for index, clip in enumerate(clips):
        preset = presets[index] if index < len(presets) else None
        if preset == clip.preset:
            continue
        if preset is None:
            lane = clear_clip_preset(
                lane, clip.start, inherit=inherit, duration_sec=duration_sec
            )
        else:
            lane = set_clip_preset(
                lane, clip.start, preset, inherit=inherit, duration_sec=duration_sec
            )
    session.timeline.lanes[slot] = lane


def deal_list_onto_clips(
    session: TuningSession, slot: str, duration_sec: float
) -> None:
    """Deal the preset list onto the clips in order; what is left over is spare."""
    assign_clip_presets(
        session, slot, duration_sec, list(session.layers[slot].preset_list)
    )


def spare_presets(
    session: TuningSession, slot: str, duration_sec: float
) -> list[PresetListEntry]:
    """The presets at the end of the list that no clip holds."""
    held = len(clip_preset_list(session, slot, duration_sec))
    return list(session.layers[slot].preset_list[held:])


def spare_preset_count(
    session: TuningSession, slot: str, duration_sec: float
) -> int:
    """How many presets at the end of the list no clip holds."""
    return len(spare_presets(session, slot, duration_sec))


def first_spare(
    session: TuningSession, slot: str, duration_sec: float
) -> PresetListEntry | None:
    """The first preset in the list that no clip holds."""
    return next(iter(spare_presets(session, slot, duration_sec)), None)


def set_clip_preset_and_list(
    session: TuningSession,
    slot: str,
    start: float,
    preset: PresetListEntry,
    duration_sec: float,
) -> None:
    """Give the clip at ``start`` ``preset`` in place of its own, in the list too."""
    held_before = 0
    replaces = False
    for clip in row_switching_clips(session, slot, duration_sec):
        if clip.start >= start:
            replaces = clip.start == start and clip.preset is not None
            break
        if clip.preset is not None:
            held_before += 1
    entries = session.layers[slot].preset_list
    entries[held_before : held_before + int(replaces)] = [preset]
    session.timeline.lanes[slot] = set_clip_preset(
        _lane(session, slot),
        start,
        preset,
        inherit=layer_inherit(session, slot),
        duration_sec=duration_sec,
    )


def start_new_clips(
    session: TuningSession, slot: str, duration_sec: float, starts: Sequence[float]
) -> None:
    """Let the new clips at ``starts`` take spares, while there are any.

    For clips that would continue the one before: the later part of a split,
    or a hold dropped in a take. They are only marked to start a preset; the
    spares fill them as the edit is recorded. Without a spare left they
    continue.
    """
    if not is_each_clip(session, slot):
        return
    lane = _lane(session, slot)
    inherit = layer_inherit(session, slot)
    clips = lane_clips(lane, inherit=inherit, duration_sec=duration_sec)
    starting = switching_clips(clips)
    held = [clip.preset for clip in starting if clip.preset is not None]
    spares = len(_without_entries(session.layers[slot].preset_list, held))
    # Clips already waiting for a preset come first.
    spares -= len(starting) - len(held)
    for clip in clips:
        if spares <= 0:
            break
        if clip.start not in starts or clip_starts_preset(clips, clip):
            continue
        lane = start_clip_preset(
            lane, clip.start, inherit=inherit, duration_sec=duration_sec
        )
        spares -= 1
    session.timeline.lanes[slot] = lane


def fill_empty_clips(
    session: TuningSession, slot: str, duration_sec: float
) -> None:
    """Give empty clips the spares, earliest clip first, and reorder the list to match."""
    layer = session.layers[slot]
    clips = row_switching_clips(session, slot, duration_sec)
    held = sum(1 for clip in clips if clip.preset is not None)
    spares = list(layer.preset_list[held:])
    if not spares or held == len(clips):
        return
    presets = [
        clip.preset
        if clip.preset is not None
        else (spares.pop(0) if spares else None)
        for clip in clips
    ]
    assign_clip_presets(session, slot, duration_sec, presets)
    layer.preset_list[:] = [
        *(preset for preset in presets if preset is not None),
        *spares,
    ]


def timeline_is_empty(session: TuningSession) -> bool:
    """True when no layer's row has been set: the timeline has never been used."""
    return all(
        lane.baseline is None and not lane.cues
        for lane in session.timeline.lanes.values()
    )


def seed_timeline(session: TuningSession) -> None:
    """Build the first timeline so turning it on changes nothing on screen.

    An enabled layer gets one whole-song clip and keeps its switching; a
    disabled layer stays off.
    """
    for slot in session.layer_z_order:
        session.timeline.lanes[slot] = TimelineLane(
            baseline=layer_inherit(session, slot), cues=[]
        )


def _without_entries(
    entries: Sequence[PresetListEntry], remove: Sequence[PresetListEntry]
) -> list[PresetListEntry]:
    """``entries`` less one occurrence of each of ``remove``."""
    left = list(entries)
    for entry in remove:
        if entry in left:
            left.remove(entry)
    return left


def _all_clips(
    session: TuningSession,
    slot: str,
    duration_sec: float,
    before: EditSnapshot | None = None,
) -> list[TimelineClip]:
    """The row's clips now, or as they were in ``before``."""
    lane = (
        _lane(session, slot)
        if before is None
        else before.lanes.get(slot) or empty_lane()
    )
    return lane_clips(
        lane, inherit=layer_inherit(session, slot), duration_sec=duration_sec
    )


def _clips_before(
    session: TuningSession, slot: str, before: EditSnapshot, duration_sec: float
) -> list[PresetListEntry]:
    """The presets the row's clips held before the edit, in clip order."""
    clips = _all_clips(session, slot, duration_sec, before)
    return [c.preset for c in switching_clips(clips) if c.preset is not None]


def changed_clip_count(
    session: TuningSession, slot: str, duration_sec: float, before: EditSnapshot
) -> int:
    """How many of the row's clips hold another preset, or none, since ``before``."""
    old = {
        clip.start: clip.preset
        for clip in _all_clips(session, slot, duration_sec, before)
    }
    return sum(
        1
        for clip in _all_clips(session, slot, duration_sec)
        if clip.start in old and old[clip.start] != clip.preset
    )


def layers_label(session: TuningSession, slots: Sequence[str]) -> str:
    """``layer 2``, or ``layers 1 and 3``, as the panel numbers them."""
    numbers = [
        str(index)
        for index, slot in enumerate(session.layer_z_order, start=1)
        if slot in slots
    ]
    if len(numbers) == 1:
        return f"layer {numbers[0]}"
    return f"layers {', '.join(numbers[:-1])} and {numbers[-1]}"


TIMELINE_LOCK_REASON = "Unlock the timeline to change clips"


def layer_lock_reason(session: TuningSession, slots: Sequence[str]) -> str:
    """Why a preset change on locked ``slots`` is refused."""
    whose = "its" if len(slots) == 1 else "their"
    return f"Unlock {layers_label(session, slots)} to change {whose} presets"


def locked_each_clip_reason(session: TuningSession) -> str | None:
    """Why an edit that replaces every row cannot run: the locked each-clip
    layers it would take presets from. None when there are none."""
    slots = [
        slot
        for slot in session.layer_z_order
        if session.layers[slot].locked and is_each_clip(session, slot)
    ]
    return layer_lock_reason(session, slots) if slots else None


def clip_preset_lock_reason(session: TuningSession, slot: str) -> str | None:
    """Why the layer's clips cannot gain or lose a preset, or None when they can."""
    if not is_each_clip(session, slot):
        return None
    if session.layers[slot].locked:
        return layer_lock_reason(session, (slot,))
    return TIMELINE_LOCK_REASON if session.timeline.locked else None


def edit_refusal(
    session: TuningSession, duration_sec: float, before: EditSnapshot
) -> str | None:
    """Why a lock forbids the edit just made, or None when it may stand.

    A locked timeline keeps each-clip layers' clips as they are. A locked
    layer keeps its preset list, when its presets change, and, with each
    clip, which presets its clips hold.
    """
    for slot in session.layer_z_order:
        each_clip = is_each_clip(session, slot)
        if session.timeline.locked and (
            each_clip or before.triggers.get(slot) == "timeline"
        ):
            if _all_clips(session, slot, duration_sec) != _all_clips(
                session, slot, duration_sec, before
            ):
                return TIMELINE_LOCK_REASON
        layer = session.layers[slot]
        if layer.locked and (
            layer.preset_list != before.preset_lists.get(slot)
            or layer.preset_switching_trigger != before.triggers.get(slot)
            or (
                each_clip
                and clip_preset_list(session, slot, duration_sec)
                != _clips_before(session, slot, before, duration_sec)
            )
        ):
            return layer_lock_reason(session, (slot,))
    return None


def sync_each_clip_layers(
    session: TuningSession, duration_sec: float, before: EditSnapshot
) -> list[str]:
    """Keep each-clip layers' clips and preset lists in step after an edit.

    Runs once per recorded edit, with the state from before it. A list edit
    that keeps the list's length changes the clips' presets in place; one
    that adds past the held presets leaves every clip its preset; any other
    deals the list along the clips. A timeline edit leaves the other clips'
    presets alone, and a preset a clip lost joins the end of the spares.
    Spares then fill empty clips. A layer the edit did not touch is left
    alone. Returns the slots whose list changed, so switching can reload.
    """
    changed: list[str] = []
    for slot in session.layer_z_order:
        if not is_each_clip(session, slot):
            continue
        layer = session.layers[slot]
        old_list = list(before.preset_lists.get(slot, []))
        if (
            layer.preset_list == old_list
            and before.triggers.get(slot) == "timeline"
            and before.lanes.get(slot) == session.timeline.lanes.get(slot)
        ):
            continue
        held = clip_preset_list(session, slot, duration_sec)
        entered = before.triggers.get(slot) != "timeline"
        if entered:
            # Entering each clip has already dealt the list.
            pass
        elif layer.preset_list != old_list:
            if layer.preset_list[: len(held)] == held:
                pass
            elif len(layer.preset_list) == len(old_list):
                queue = iter(list(layer.preset_list))
                assign_clip_presets(
                    session,
                    slot,
                    duration_sec,
                    [
                        next(queue, None) if clip.preset is not None else None
                        for clip in row_switching_clips(session, slot, duration_sec)
                    ],
                )
            else:
                deal_list_onto_clips(session, slot, duration_sec)
        else:
            old_held = _clips_before(session, slot, before, duration_sec)
            spares = _without_entries(
                old_list[len(old_held) :], _without_entries(held, old_held)
            )
            lost = _without_entries(old_held, held)
            layer.preset_list[:] = [*held, *spares, *lost]
        fill_empty_clips(session, slot, duration_sec)
        if layer.preset_list != old_list:
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
    continues), or None. ``starts`` is whether the clip starts a preset,
    ``empty`` whether it should but holds none, and ``butted`` whether it touches the clip before, so it may continue that
    clip's preset instead. ``list_index`` is the clip's entry in the layer's
    preset list, when it starts a preset of its own.
    """

    name: str | None
    starts: bool
    empty: bool
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
        empty=starts and clip.preset is None,
        butted=clip_butts_previous(clips, clip),
        list_index=list_index,
    )
