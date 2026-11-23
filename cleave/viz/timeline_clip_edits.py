"""Clip selection and clip edits shared by the strip, inspector, and menus.

A clip is one visible span of a layer's lane: an on cue up to the next cue
or the song end (``cleave.timeline.lane_clips``). Clips are read from the
lane each time, with the layer's enabled switch standing in for a lane that
has no baseline; nothing is cached on the session. A selection is the
selected clip's start time.

Selection helpers are plain functions on the session. Every clip edit goes
through ``ClipEditor``, which turns it into cue operations and records it in
``EditHistory`` so it can be undone. The strip calls it for its focused
row; the inspector for the row page's slot; the clip context menu for the
row it opened on.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

import numpy as np
import pygame

from cleave.blend_modes import BlendMode
from cleave.cue_roles import CueRole
from cleave.cut_types import CutType
from cleave.timeline import (
    LEVEL_EDIT_MIN,
    LEVEL_STEP_LARGE,
    LEVEL_STEP_SMALL,
    MIN_CLIP_SEC,
    ClipEdge,
    ClipGrip,
    TimelineClip,
    TimelineLane,
    add_clip,
    clip_at,
    clip_butts_previous,
    clip_starts_preset,
    clip_move_bounds,
    clip_starting_at,
    clip_trim_bounds,
    copy_lane,
    empty_lane,
    lane_clips,
    lane_last_on_level,
    levels_equal,
    move_clip,
    remove_clip,
    set_clip_preset,
    shift_bars_by_beats,
    snap_placement_time,
    split_clip,
    trim_clip,
    update_clip,
)
from cleave.preset_list_entry import PresetListEntry
from cleave.viz.clip_presets import ClipPresetPick, is_each_clip
from cleave.viz.session import TuningSession
from cleave.viz.edit_history import EditHistory

# Length of a new clip, and the large trim step, when the song has no bar grid.
DEFAULT_BAR_SEC = 2.0
# Trim step of the inspector's Start and End rows with placement snap off.
FREE_TRIM_STEP_SEC = 0.1


def clip_selection_allowed(session: TuningSession) -> bool:
    """Clip selection pauses while recording."""
    return not session.timeline.recording


def clip_edits_allowed(session: TuningSession) -> bool:
    """Clip edits need an unlocked timeline that is not recording."""
    tl = session.timeline
    return not tl.locked and not tl.recording


def snap_for_session(
    session: TuningSession,
    t_sec: float,
    beat_times: Sequence[float],
    bar_times: Sequence[float],
) -> float:
    """Snap *t_sec* by the timeline's placement snap and bar phase."""
    return snap_placement_time(
        t_sec,
        session.timeline.placement_snap,
        beat_times=beat_times,
        bar_times=bar_times,
        bar_phase=session.timeline.bar_phase_offset,
    )


def bar_length_sec(bar_times: Sequence[float]) -> float:
    """Median bar length, or ``DEFAULT_BAR_SEC`` without a bar grid."""
    if len(bar_times) < 2:
        return DEFAULT_BAR_SEC
    interval = float(np.median(np.diff(np.asarray(bar_times, dtype=np.float64))))
    if not np.isfinite(interval) or interval <= 0.0:
        return DEFAULT_BAR_SEC
    return interval


def _inherit(session: TuningSession, slot: str) -> float:
    # A lane with no baseline inherits the layer's enabled switch.
    return 1.0 if session.layers[slot].enabled else 0.0


def _lane(session: TuningSession, slot: str) -> TimelineLane:
    return session.timeline.lanes.get(slot) or empty_lane()


def row_clips(
    session: TuningSession, slot: str, duration_sec: float
) -> list[TimelineClip]:
    """The clips of *slot*'s lane, in time order."""
    return lane_clips(
        _lane(session, slot),
        inherit=_inherit(session, slot),
        duration_sec=duration_sec,
    )


def selected_clip(
    session: TuningSession, slot: str, duration_sec: float
) -> TimelineClip | None:
    """The selected clip of *slot*, or None when none is selected or it is gone."""
    start = session.timeline.selected_clip_t.get(slot)
    if start is None:
        return None
    return clip_starting_at(row_clips(session, slot, duration_sec), start)


def select_clip(session: TuningSession, slot: str, start: float) -> None:
    """Select the clip at *start* on *slot*; start its flash and title swipe."""
    tl = session.timeline
    if tl.selected_clip_t.get(slot) == start:
        return
    tl.selected_clip_t[slot] = start
    tl.selected_clip_flash_start_ms = pygame.time.get_ticks()
    tl.selected_clip_serial += 1


def deselect_clip(session: TuningSession, slot: str) -> None:
    tl = session.timeline
    tl.selected_clip_t.pop(slot, None)
    tl.selected_clip_flash_start_ms = None


def step_clip_selection(
    session: TuningSession,
    slot: str,
    *,
    forward: bool,
    playhead_sec: float,
    duration_sec: float,
) -> None:
    """Select the next or previous clip on *slot*, stopping at the ends.

    With no selection, picks the first clip starting at or after the playhead
    going forward, or the last starting at or before it going back.
    """
    if not clip_selection_allowed(session):
        return
    starts = [clip.start for clip in row_clips(session, slot, duration_sec)]
    if not starts:
        return
    current = session.timeline.selected_clip_t.get(slot)
    if current is None or current not in starts:
        if forward:
            pick = next((t for t in starts if t >= playhead_sec), starts[-1])
        else:
            pick = next((t for t in reversed(starts) if t <= playhead_sec), starts[0])
        select_clip(session, slot, pick)
        return
    index = starts.index(current)
    index = min(index + 1, len(starts) - 1) if forward else max(index - 1, 0)
    select_clip(session, slot, starts[index])


@dataclass
class _ClipDrag:
    slot: str
    # None moves the whole clip; an edge trims it, and "roll" moves the
    # boundary it shares with the next clip.
    grip: ClipGrip | None
    clip: TimelineClip
    # The lane as it was, or None when the slot had no stored lane.
    lane: TimelineLane | None
    selected_t: float | None
    # Pointer time minus the clip start, held while the clip moves.
    grab_offset: float


class ClipEditor:
    """Edits to one layer's clips, each recorded for undo."""

    def __init__(
        self,
        session: TuningSession,
        history: EditHistory,
        *,
        duration_sec: float,
        beat_times: Sequence[float] = (),
        bar_times: Sequence[float] = (),
        pick_preset: ClipPresetPick | None = None,
    ) -> None:
        """``pick_preset`` chooses a preset for a clip that starts a new one
        on a layer whose presets change on each clip."""
        self.session = session
        self.history = history
        self.duration_sec = duration_sec
        self._pick_preset = pick_preset
        self._beat_times = tuple(beat_times)
        self._bar_times = tuple(bar_times)
        self._drag: _ClipDrag | None = None

    def snap(self, t_sec: float) -> float:
        """Snap *t_sec* by the timeline's placement snap."""
        return snap_for_session(
            self.session, t_sec, self._beat_times, self._bar_times
        )

    def clips(self, slot: str) -> list[TimelineClip]:
        return row_clips(self.session, slot, self.duration_sec)

    def selected(self, slot: str) -> TimelineClip | None:
        return selected_clip(self.session, slot, self.duration_sec)

    def cut_out_hint(self, slot: str) -> str | None:
        """Why the selected clip has no cut out of its own, or None when it has."""
        clip = self.selected(slot)
        if clip is None or clip.has_end_cue:
            return None
        return cut_out_unavailable_hint(clip)

    def add_clip_at(self, slot: str, t_sec: float) -> bool:
        """Add a clip from *t_sec* (snapped) and select it.

        It runs to the next clip's start or one bar on, whichever is sooner,
        at the lane's last on level. A snap that lands inside the clip before
        starts the new one where that clip ends. False when edits are blocked
        or there is no room at *t_sec*.
        """
        session = self.session
        if not clip_edits_allowed(session):
            return False
        clips = self.clips(slot)
        start = self.snap(t_sec)
        covering = clip_at(clips, start)
        if covering is not None:
            if covering.end <= t_sec:
                start = covering.end
            elif clip_at(clips, t_sec) is None:
                start = t_sec
            else:
                return False
        start = max(0.0, start)
        following = next((clip.start for clip in clips if clip.start > start), None)
        end = min(
            start + bar_length_sec(self._bar_times),
            self.duration_sec if following is None else following,
        )
        if end - start < MIN_CLIP_SEC or clip_at(clips, start) is not None:
            return False
        lane = _lane(session, slot)
        with self.history.recording("Add clip"):
            session.timeline.lanes[slot] = add_clip(
                lane,
                start,
                end,
                lane_last_on_level(lane, start),
                inherit=_inherit(session, slot),
                duration_sec=self.duration_sec,
                # On an each-clip layer a new clip starts a preset of its
                # own, even against the clip before; one is picked as the
                # edit is recorded.
                recast=is_each_clip(session, slot),
            )
            select_clip(session, slot, start)
        return True

    def delete_selected(self, slot: str) -> None:
        """Turn *slot*'s selected clip off, then select the next clip, else the previous."""
        session = self.session
        if not clip_edits_allowed(session):
            return
        clip = self.selected(slot)
        if clip is None:
            return
        with self.history.recording("Delete clip"):
            session.timeline.lanes[slot] = remove_clip(
                _lane(session, slot),
                clip,
                inherit=_inherit(session, slot),
                duration_sec=self.duration_sec,
            )
            starts = [other.start for other in self.clips(slot)]
            pick = next((t for t in starts if t > clip.start), None)
            if pick is None:
                pick = next((t for t in reversed(starts) if t < clip.start), None)
            if pick is None:
                deselect_clip(session, slot)
            else:
                select_clip(session, slot, pick)

    def split_at(self, slot: str, t_sec: float) -> bool:
        """Split the clip under *t_sec* in two and select the second part.

        False when edits are blocked, no clip is there, or either part would
        be too short.
        """
        session = self.session
        if not clip_edits_allowed(session):
            return False
        clip = clip_at(self.clips(slot), t_sec)
        if (
            clip is None
            or t_sec < clip.start + MIN_CLIP_SEC
            or t_sec > clip.end - MIN_CLIP_SEC
        ):
            return False
        with self.history.recording("Split clip"):
            session.timeline.lanes[slot] = split_clip(
                _lane(session, slot),
                clip,
                t_sec,
                inherit=_inherit(session, slot),
                duration_sec=self.duration_sec,
            )
            select_clip(session, slot, t_sec)
        return True

    def nudge_level(self, slot: str, *, forward: bool, large: bool) -> None:
        """Step the selected clip's opacity by 1% (10% when *large*), clamped to its range."""
        if not clip_edits_allowed(self.session):
            return
        clip = self.selected(slot)
        if clip is None:
            return
        # Integer percent math matches the layer opacity fader (1% / 10%).
        step_pct = int(
            round((LEVEL_STEP_LARGE if large else LEVEL_STEP_SMALL) * 100.0)
        )
        min_pct = int(round(LEVEL_EDIT_MIN * 100.0))
        pct = int(round(float(clip.level) * 100.0))
        new_pct = max(min_pct, min(100, pct + (step_pct if forward else -step_pct)))
        new_level = new_pct / 100.0
        if levels_equal(new_level, clip.level):
            return
        self._update(slot, replace(clip, level=new_level), "Clip level", "level")

    def set_blend(self, slot: str, blend: BlendMode | None) -> None:
        """Set the selected clip's blend mode; None inherits the layer's."""
        clip = self._editable(slot)
        if clip is None or clip.blend == blend:
            return
        self._update(slot, replace(clip, blend=blend), "Clip blend", "blend")

    def set_role(self, slot: str, role: CueRole | None) -> None:
        """Set the selected clip's role, or clear it with None."""
        clip = self._editable(slot)
        if clip is None or clip.role == role:
            return
        self._update(slot, replace(clip, role=role), "Clip role", "role")

    def set_cut_in(self, slot: str, cut: CutType) -> None:
        """Set how the selected clip starts."""
        clip = self._editable(slot)
        if clip is None or clip.cut_in == cut:
            return
        self._update(slot, replace(clip, cut_in=cut), "Clip cut", "cut_in")

    def set_cut_out(self, slot: str, cut: CutType) -> None:
        """Set how the selected clip ends. A clip with no end cue of its own has none."""
        clip = self._editable(slot)
        if clip is None or not clip.has_end_cue or clip.cut_out == cut:
            return
        self._update(slot, replace(clip, cut_out=cut), "Clip cut", "cut_out")

    def set_starts_preset(self, slot: str, starts: bool) -> None:
        """Make the selected clip start a preset of its own, or continue the one before.

        Only a clip butting the one before can continue it. Starting one picks
        a preset by the clip's role, else from the layer's folder.
        """
        clip = self._editable(slot)
        if clip is None:
            return
        clips = self.clips(slot)
        if not clip_butts_previous(clips, clip):
            return
        if clip_starts_preset(clips, clip) == starts:
            return
        preset = None
        if starts:
            if self._pick_preset is None:
                return
            preset = self._pick_preset(slot, clip.role)
            if preset is None:
                return
        self._set_preset(
            slot,
            clip,
            preset,
            "Clip starts new preset" if starts else "Clip continues preset",
        )

    def pick_another_preset(self, slot: str) -> None:
        """Give the selected clip another preset, by its role, else from the layer's folder."""
        clip = self._editable(slot)
        if clip is None or self._pick_preset is None:
            return
        if not clip_starts_preset(self.clips(slot), clip):
            return
        preset = self._pick_preset(slot, clip.role)
        if preset is None:
            return
        self._set_preset(slot, clip, preset, "Pick clip preset")

    def set_preset(self, slot: str, preset: PresetListEntry) -> None:
        """Give the selected clip *preset* (Paste)."""
        clip = self._editable(slot)
        if clip is None or clip.preset == preset:
            return
        self._set_preset(slot, clip, preset, "Paste clip preset")

    def _set_preset(
        self,
        slot: str,
        clip: TimelineClip,
        preset: PresetListEntry | None,
        label: str,
    ) -> None:
        session = self.session
        with self.history.recording(label):
            session.timeline.lanes[slot] = set_clip_preset(
                _lane(session, slot),
                clip.start,
                preset,
                inherit=_inherit(session, slot),
                duration_sec=self.duration_sec,
            )

    def trim_step(
        self, slot: str, edge: ClipEdge, *, forward: bool, large: bool
    ) -> None:
        """Move one edge of the selected clip by a snap step (a bar when *large*)."""
        clip = self._editable(slot)
        if clip is None:
            return
        current = clip.start if edge == "start" else clip.end
        target = self._step_time(current, forward=forward, large=large)
        with self.history.recording("Trim clip", merge_key=("trim", slot, edge)):
            self._trim(slot, clip, edge, target)

    # A drag spans frames: begin on the first motion, update per motion, then
    # end on release or cancel on Esc.

    @property
    def dragging(self) -> bool:
        return self._drag is not None

    @property
    def drag_grip(self) -> ClipGrip | None:
        """The edge grip being dragged, or None for a move or no drag."""
        return None if self._drag is None else self._drag.grip

    def begin_drag(self, slot: str, grip: ClipGrip | None, grab_t: float) -> bool:
        """Start moving (*grip* None), trimming, or rolling *slot*'s selected clip.

        A ``"start"`` or ``"end"`` grip trims only this clip, opening a gap at
        a boundary it shares with a neighbour; ``"roll"`` moves the clip's end
        and the next clip's start together.
        """
        if self._drag is not None:
            self.cancel_drag()
        session = self.session
        if not clip_edits_allowed(session):
            return False
        clip = self.selected(slot)
        if clip is None:
            return False
        stored = session.timeline.lanes.get(slot)
        label = {None: "Move clip", "roll": "Roll clips"}.get(grip, "Trim clip")
        self.history.begin(label)
        self._drag = _ClipDrag(
            slot=slot,
            grip=grip,
            clip=clip,
            lane=None if stored is None else copy_lane(stored),
            selected_t=session.timeline.selected_clip_t.get(slot),
            grab_offset=grab_t - clip.start,
        )
        return True

    def update_drag(self, t_sec: float) -> None:
        """Place the dragged clip or edge for the pointer at *t_sec*, snapped.

        Each update starts again from the lane the drag began with, so
        snapping and clamping never accumulate.
        """
        drag = self._drag
        if drag is None:
            return
        self._restore_drag_lane(drag)
        if drag.grip is None:
            self._move(drag.slot, drag.clip, self.snap(t_sec - drag.grab_offset))
        elif drag.grip == "roll":
            self._trim(drag.slot, drag.clip, "end", self.snap(t_sec))
        else:
            self._trim(
                drag.slot, drag.clip, drag.grip, self.snap(t_sec), roll=False
            )

    def end_drag(self) -> None:
        """Keep the drag's result as one undo step."""
        if self._drag is None:
            return
        self._drag = None
        self.history.commit()

    def cancel_drag(self) -> None:
        """Put the clip back where the drag began; nothing is recorded."""
        drag = self._drag
        if drag is None:
            return
        self._drag = None
        self._restore_drag_lane(drag)
        tl = self.session.timeline
        if drag.selected_t is None:
            tl.selected_clip_t.pop(drag.slot, None)
        else:
            tl.selected_clip_t[drag.slot] = drag.selected_t
        self.history.cancel()

    def _restore_drag_lane(self, drag: _ClipDrag) -> None:
        lanes = self.session.timeline.lanes
        if drag.lane is None:
            lanes.pop(drag.slot, None)
        else:
            lanes[drag.slot] = copy_lane(drag.lane)

    def _editable(self, slot: str) -> TimelineClip | None:
        if not clip_edits_allowed(self.session):
            return None
        return self.selected(slot)

    def _step_time(self, t_sec: float, *, forward: bool, large: bool) -> float:
        """The next grid time from *t_sec*: the snap grid, or bars when *large*."""
        tl = self.session.timeline
        bars = (
            shift_bars_by_beats(self._bar_times, self._beat_times, tl.bar_phase_offset)
            if tl.bar_phase_offset
            else self._bar_times
        )
        if large or tl.placement_snap == "bar":
            grid: Sequence[float] = bars
        elif tl.placement_snap == "beat":
            grid = self._beat_times
        else:
            grid = ()
        eps = 1e-6
        if forward:
            pick = next((float(t) for t in grid if t > t_sec + eps), None)
        else:
            pick = next((float(t) for t in reversed(grid) if t < t_sec - eps), None)
        if pick is not None:
            return pick
        if large:
            step = bar_length_sec(self._bar_times)
        elif grid:
            # Past the grid's end, keep stepping at its usual interval.
            step = (
                bar_length_sec(grid) if len(grid) > 1 else FREE_TRIM_STEP_SEC
            )
        else:
            step = FREE_TRIM_STEP_SEC
        return t_sec + step if forward else t_sec - step

    def _move(self, slot: str, clip: TimelineClip, new_start: float) -> None:
        session = self.session
        lane = _lane(session, slot)
        low, high = clip_move_bounds(self.clips(slot), clip, self.duration_sec)
        start = max(low, min(high, new_start))
        session.timeline.lanes[slot] = move_clip(
            lane,
            clip,
            start,
            inherit=_inherit(session, slot),
            duration_sec=self.duration_sec,
        )
        session.timeline.selected_clip_t[slot] = start

    def _trim(
        self,
        slot: str,
        clip: TimelineClip,
        edge: ClipEdge,
        t_sec: float,
        *,
        roll: bool = True,
    ) -> None:
        """Trim *edge*; a shared edge rolls unless *roll* is False."""
        session = self.session
        lane = _lane(session, slot)
        low, high = clip_trim_bounds(
            self.clips(slot), clip, edge, MIN_CLIP_SEC, self.duration_sec, roll=roll
        )
        target = max(low, min(high, t_sec))
        session.timeline.lanes[slot] = trim_clip(
            lane,
            clip,
            edge,
            target,
            inherit=_inherit(session, slot),
            duration_sec=self.duration_sec,
            roll=roll,
        )
        if edge == "start":
            session.timeline.selected_clip_t[slot] = target

    def _update(self, slot: str, clip: TimelineClip, label: str, kind: str) -> None:
        session = self.session
        with self.history.recording(label, merge_key=(kind, slot, clip.start)):
            session.timeline.lanes[slot] = update_clip(
                _lane(session, slot), clip, inherit=_inherit(session, slot)
            )
            # A level change can merge the clip into a matching neighbour.
            if self.selected(slot) is None:
                deselect_clip(session, slot)


def cut_out_unavailable_hint(clip: TimelineClip) -> str:
    """Why *clip* (one without an end cue) has no cut out to set."""
    if clip.butts_next:
        return "Butts the next clip; set its Cut in"
    return "Runs to the song end"
