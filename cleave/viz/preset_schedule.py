"""What each timeline row shows of its layer's presets, and timer slices as clips.

``timer_slices`` works out which preset an on-a-timer layer plays in each
part of its clips. Slices are never stored: they follow the clips, the preset
list, and the preset duration. ``row_labels`` gives the parts a row names, for
every way a layer can change presets, so the strip and its tooltips agree.
``bake_timer_slices`` turns the slices into clips when a timer layer moves to
"each clip".
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from cleave.preset_list_entry import PresetListEntry
from cleave.timeline import (
    MIN_CLIP_SEC,
    TimelineClip,
    clip_butts_previous,
    clip_shown_preset,
    clip_starts_preset,
    empty_lane,
    lane_clips,
    set_clip_preset,
    split_clip,
)
from cleave.viz.clip_presets import (
    CONTINUES_GLYPH,
    clip_preset_list,
    deal_list_onto_clips,
    layer_inherit,
    preset_label,
    row_switching_clips,
    seed_timeline,
    spare_preset_count,
    timeline_is_empty,
)
from cleave.viz.session import TuningSession

PROJECTM_LABEL = "projectM decides"


@dataclass(frozen=True)
class TimerSlice:
    """Part of a clip over which a timer layer plays one preset.

    ``index`` is its preset list entry. ``continues`` marks a clip's first
    slice that carries on the preset shown before it.
    """

    clip_start: float
    start: float
    end: float
    index: int
    entry: PresetListEntry
    continues: bool


def timer_slices(
    clips: Sequence[TimelineClip],
    period: float,
    entries: Sequence[PresetListEntry],
) -> list[TimerSlice]:
    """Each clip cut where the timer changes preset, in time order.

    Song time drives the timer, so time spent in gaps counts and a short list
    loops, as playback does. Neighbours with the same preset are one slice.
    """
    if not entries:
        return []
    # Playback's own floor (``_advance_timer_indexed``).
    period = max(0.001, float(period))
    slices: list[TimerSlice] = []
    shown_k: int | None = None
    for clip in clips:
        k = math.floor(clip.start / period)
        start = clip.start
        while start < clip.end:
            end = min(clip.end, (k + 1) * period)
            if end > start:
                index = k % len(entries)
                entry = entries[index]
                last = slices[-1] if slices else None
                if (
                    last is not None
                    and last.clip_start == clip.start
                    and last.entry.file == entry.file
                ):
                    slices[-1] = TimerSlice(
                        last.clip_start,
                        last.start,
                        end,
                        last.index,
                        last.entry,
                        last.continues,
                    )
                else:
                    slices.append(
                        TimerSlice(
                            clip.start,
                            start,
                            end,
                            index,
                            entry,
                            start == clip.start
                            and _same_throughout(entries, shown_k, k),
                        )
                    )
                shown_k = k
            start = max(start, end)
            k += 1
    return slices


def _same_throughout(
    entries: Sequence[PresetListEntry], shown_k: int | None, k: int
) -> bool:
    """Whether the timer kept one preset from period ``shown_k`` through ``k``."""
    if shown_k is None:
        return False
    file = entries[k % len(entries)].file
    first = max(shown_k, k - len(entries))
    return all(entries[j % len(entries)].file == file for j in range(first, k))


@dataclass(frozen=True)
class RowPresets:
    """How a layer's presets change, as its timeline row needs it."""

    trigger: str = "off"
    period: float = 0.0
    entries: tuple[PresetListEntry, ...] = ()
    layer_preset: str | None = None


def row_presets(session: TuningSession, slot: str) -> RowPresets:
    layer = session.layers[slot]
    if layer.preset_switching != "on":
        current = layer.playlist.current
        return RowPresets(layer_preset=None if current is None else current.name)
    return RowPresets(
        trigger=layer.preset_switching_trigger,
        period=float(layer.preset_duration),
        entries=tuple(layer.preset_list),
    )


@dataclass(frozen=True)
class RowLabel:
    """Part of a clip and what the row writes on it.

    ``soft`` draws its start as a faint divider: what plays carries on across
    it, or it is a timer change rather than a clip's own edge. ``empty`` marks
    a clip that should start a preset but holds none. ``index`` is the preset
    list entry of a timer slice.
    """

    clip: TimelineClip
    start: float
    end: float
    text: str
    tooltip: str
    soft: bool = False
    empty: bool = False
    index: int | None = None


def row_labels(
    clips: Sequence[TimelineClip], presets: RowPresets, *, timeline_enabled: bool
) -> list[RowLabel]:
    """What a row writes on its clips.

    With the timeline off only an each-clip row names its presets.
    """
    if presets.trigger == "timeline":
        return [_each_clip_label(clips, clip) for clip in clips]
    if not timeline_enabled:
        return []
    if presets.trigger == "timer":
        return _timer_labels(clips, presets)
    if presets.trigger == "projectm":
        return _steady_labels(
            clips, PROJECTM_LABEL, PROJECTM_LABEL
        ) if presets.entries else []
    if presets.layer_preset is None:
        return []
    return _steady_labels(
        clips, preset_label(presets.layer_preset), presets.layer_preset
    )


def _each_clip_label(
    clips: Sequence[TimelineClip], clip: TimelineClip
) -> RowLabel:
    shown = clip_shown_preset(clips, clip)
    name = "no preset" if shown is None else shown.display_name
    if not clip_starts_preset(clips, clip):
        return RowLabel(
            clip, clip.start, clip.end, CONTINUES_GLYPH, f"Continues {name}", soft=True
        )
    if clip.preset is None:
        tip = "No preset for this clip"
        if shown is not None:
            tip = f"{tip}: plays {name}"
        return RowLabel(
            clip, clip.start, clip.end, CONTINUES_GLYPH, tip, empty=True
        )
    return RowLabel(
        clip, clip.start, clip.end, preset_label(name), f"Starts {name}"
    )


def _steady_labels(
    clips: Sequence[TimelineClip], text: str, name: str
) -> list[RowLabel]:
    """One thing plays throughout: the first clip names it, the rest continue it."""
    return [
        RowLabel(
            clip,
            clip.start,
            clip.end,
            text if position == 0 else CONTINUES_GLYPH,
            name if position == 0 else f"Continues {name}",
            soft=clip_butts_previous(clips, clip),
        )
        for position, clip in enumerate(clips)
    ]


def _timer_labels(
    clips: Sequence[TimelineClip], presets: RowPresets
) -> list[RowLabel]:
    by_start = {clip.start: clip for clip in clips}
    labels: list[RowLabel] = []
    for part in timer_slices(clips, presets.period, presets.entries):
        clip = by_start[part.clip_start]
        name = part.entry.display_name
        inside = part.start > clip.start
        labels.append(
            RowLabel(
                clip,
                part.start,
                part.end,
                CONTINUES_GLYPH if part.continues else preset_label(name),
                f"Continues {name}" if part.continues else f"Starts {name}",
                soft=inside or (part.continues and clip_butts_previous(clips, clip)),
                index=part.index,
            )
        )
    return labels


def label_at(labels: Sequence[RowLabel], t_sec: float) -> RowLabel | None:
    """The label covering ``t_sec``."""
    return next((lab for lab in labels if lab.start <= t_sec < lab.end), None)


def bake_timer_slices(
    session: TuningSession, slot: str, duration_sec: float
) -> None:
    """Cut the row's clips where the timer changes preset, each part holding its own.

    Clips keep their look, cuts, and the gaps between them. A change too close
    to a clip's edge to leave a clip is dropped: the part takes its
    neighbour's preset. The layer's list becomes the presets in clip order.
    """
    layer = session.layers[slot]
    inherit = layer_inherit(session, slot)
    lane = session.timeline.lanes.get(slot) or empty_lane()
    clips = lane_clips(lane, inherit=inherit, duration_sec=duration_sec)
    slices = timer_slices(clips, layer.preset_duration, layer.preset_list)
    if not slices:
        deal_list_onto_clips(session, slot, duration_sec)
        return
    playing: PresetListEntry | None = None
    for clip in clips:
        parts = [part for part in slices if part.clip_start == clip.start]
        # A sliver at the start takes the next part's preset.
        while len(parts) > 1 and parts[0].end - clip.start < MIN_CLIP_SEC:
            parts.pop(0)
        butted = clip_butts_previous(clips, clip)
        for position, part in enumerate(parts):
            start = clip.start if position == 0 else part.start
            if position > 0:
                if clip.end - start < MIN_CLIP_SEC:
                    break
                holder = next(
                    other
                    for other in lane_clips(
                        lane, inherit=inherit, duration_sec=duration_sec
                    )
                    if other.start <= start < other.end
                )
                lane = split_clip(
                    lane, holder, start, inherit=inherit, duration_sec=duration_sec
                )
            carries_on = (
                position == 0
                and butted
                and playing is not None
                and playing.file == part.entry.file
            )
            lane = set_clip_preset(
                lane,
                start,
                None if carries_on else part.entry,
                inherit=inherit,
                duration_sec=duration_sec,
            )
            playing = part.entry
    session.timeline.lanes[slot] = lane
    layer.preset_list[:] = clip_preset_list(session, slot, duration_sec)


def enter_each_clip(
    session: TuningSession, slot: str, previous: str, duration_sec: float
) -> None:
    """Give the row's clips presets as the layer moves to "each clip".

    From the timer, the row is cut where the timer changes preset. Otherwise
    the clips stay and take the list's presets in order.
    """
    if previous == "timer":
        bake_timer_slices(session, slot, duration_sec)
    else:
        deal_list_onto_clips(session, slot, duration_sec)


@dataclass(frozen=True)
class EachClipChange:
    """What moving a layer to "each clip" would do to what the user has made."""

    turns_timeline_on: bool
    clips_before: int
    clips_after: int
    replaced: int
    dropped: int
    spares: int
    empty: int

    @property
    def destructive(self) -> bool:
        """Whether anything already there would change or go."""
        return (
            self.turns_timeline_on
            or self.clips_after != self.clips_before
            or self.replaced > 0
            or self.dropped > 0
        )

    def summary(self) -> str:
        """One sentence for each thing that would happen."""
        parts: list[str] = []
        if self.turns_timeline_on:
            parts.append(
                "The timeline turns on and decides when every layer shows."
            )
        if self.clips_after != self.clips_before:
            parts.append(
                f"{_count(self.clips_before, 'clip')} on this layer "
                f"{'is' if self.clips_before == 1 else 'are'} cut into "
                f"{self.clips_after}, where the timer changes preset."
            )
        else:
            parts.append("This layer's clips are not cut.")
        if self.replaced:
            parts.append(
                f"{_count(self.replaced, 'clip')} "
                f"{'loses its' if self.replaced == 1 else 'lose their'} "
                "earlier preset."
            )
        if self.dropped:
            parts.append(
                f"{_count(self.dropped, 'preset')} the timer never shows "
                f"{'leaves' if self.dropped == 1 else 'leave'} the preset list."
            )
        if self.spares:
            parts.append(
                f"{_count(self.spares, 'preset')} in the list "
                f"{'has' if self.spares == 1 else 'have'} no clip."
            )
        if self.empty:
            parts.append(
                f"{_count(self.empty, 'clip')} "
                f"{'gets' if self.empty == 1 else 'get'} no preset."
            )
        parts.append("Undo puts everything back.")
        return "\n".join(parts)


def _count(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def each_clip_change(
    session: TuningSession, slot: str, duration_sec: float
) -> EachClipChange:
    """Try moving the layer to "each clip", and put everything back."""
    layer = session.layers[slot]
    timeline = session.timeline
    lanes, entries = timeline.lanes, list(layer.preset_list)

    def clips() -> list[TimelineClip]:
        return lane_clips(
            timeline.lanes.get(slot) or empty_lane(),
            inherit=layer_inherit(session, slot),
            duration_sec=duration_sec,
        )

    timeline.lanes = dict(lanes)
    try:
        if not timeline.enabled and timeline_is_empty(session):
            seed_timeline(session)
        before = clips()
        enter_each_clip(
            session, slot, layer.preset_switching_trigger, duration_sec
        )
        after = clips()
        starts = {clip.start: clip for clip in after}
        kept = {entry.file for entry in layer.preset_list}
        return EachClipChange(
            turns_timeline_on=not timeline.enabled,
            clips_before=len(before),
            clips_after=len(after),
            replaced=sum(
                1
                for clip in before
                if clip.preset is not None and starts[clip.start].preset != clip.preset
            ),
            dropped=sum(1 for entry in entries if entry.file not in kept),
            spares=spare_preset_count(session, slot, duration_sec),
            empty=sum(
                1
                for clip in row_switching_clips(session, slot, duration_sec)
                if clip.preset is None
            ),
        )
    finally:
        timeline.lanes = lanes
        layer.preset_list[:] = entries
