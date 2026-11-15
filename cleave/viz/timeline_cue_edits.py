"""Cue selection and cue edits shared by the strip, inspector, and menus.

Selection helpers are plain functions on the session. Every cue edit goes
through ``CueEditor``, which records it in ``TimelineHistory`` so it can be
undone. The strip calls it for its focused row; the inspector for the row
page's slot; the cue context menu for the row it opened on.
"""

from __future__ import annotations

import pygame

from cleave.blend_modes import BlendMode
from cleave.cue_roles import CueRole
from cleave.cut_types import CutType
from cleave.timeline import (
    LEVEL_EDIT_MIN,
    LEVEL_EPS,
    LEVEL_STEP_LARGE,
    LEVEL_STEP_SMALL,
    SlotCue,
    cue_at_time,
    cue_editable_for_blend_role,
    empty_lane,
    lane_last_on_level,
    lane_level_at,
    levels_equal,
    navigable_cue_times,
    remove_lane_cue,
    set_lane_cue,
    update_lane_cue,
)
from cleave.viz.session import TuningSession
from cleave.viz.timeline_history import TimelineHistory


def cue_selection_allowed(session: TuningSession) -> bool:
    """Cue selection pauses while recording."""
    return not session.timeline.recording


def cue_edits_allowed(session: TuningSession) -> bool:
    """Cue edits need an unlocked timeline that is not recording."""
    tl = session.timeline
    return not tl.locked and not tl.recording


def selected_cue(session: TuningSession, slot: str) -> SlotCue | None:
    """The selected cue of *slot*, or None when none is selected or it is gone."""
    tl = session.timeline
    cue_t = tl.selected_cue_t.get(slot)
    if cue_t is None:
        return None
    return cue_at_time(tl.lanes.get(slot) or empty_lane(), cue_t)


def select_cue(session: TuningSession, slot: str, cue_t: float) -> None:
    """Select the cue at *cue_t* on *slot* and start its flash."""
    tl = session.timeline
    if tl.selected_cue_t.get(slot) == cue_t:
        return
    tl.selected_cue_t[slot] = cue_t
    tl.selected_cue_flash_start_ms = pygame.time.get_ticks()


def step_cue_selection(
    session: TuningSession, slot: str, *, forward: bool, playhead_sec: float
) -> None:
    """Select the next or previous cue on *slot*, stopping at the ends.

    With no selection, picks the first cue at or after the playhead going
    forward, or the last at or before it going back.
    """
    if not cue_selection_allowed(session):
        return
    tl = session.timeline
    times = navigable_cue_times(tl.lanes.get(slot) or empty_lane())
    if not times:
        return
    current = tl.selected_cue_t.get(slot)
    if current is None or current not in times:
        if forward:
            pick = next((t for t in times if t >= playhead_sec), times[-1])
        else:
            pick = next((t for t in reversed(times) if t <= playhead_sec), times[0])
        select_cue(session, slot, pick)
        return
    index = times.index(current)
    index = min(index + 1, len(times) - 1) if forward else max(index - 1, 0)
    select_cue(session, slot, times[index])


_KEEP = object()


class CueEditor:
    """Edits to one layer's selected cue, each recorded for undo."""

    def __init__(self, session: TuningSession, history: TimelineHistory) -> None:
        self.session = session
        self.history = history

    def add_cue(self, slot: str, t_sec: float) -> bool:
        """Add a cue at *t_sec* that flips the lane, and select it.

        Where the lane is off the cue turns it on at the lane's last on level;
        where it is on, the cue turns it off. False when edits are blocked or
        a cue already sits at *t_sec*.
        """
        session = self.session
        if not cue_edits_allowed(session):
            return False
        tl = session.timeline
        lane = tl.lanes.get(slot) or empty_lane()
        if cue_at_time(lane, t_sec) is not None:
            return False
        # A lane with no baseline inherits the layer's enabled switch.
        inherit = 1.0 if session.layers[slot].enabled else 0.0
        on = lane_level_at(lane, t_sec, inherit=inherit) > LEVEL_EPS
        level = 0.0 if on else lane_last_on_level(lane, t_sec)
        with self.history.recording("Add cue"):
            tl.lanes[slot] = set_lane_cue(lane, t_sec, level)
            select_cue(session, slot, t_sec)
        return True

    def delete_selected(self, slot: str) -> None:
        """Delete *slot*'s selected cue, then select the next one, else the previous."""
        session = self.session
        if not cue_edits_allowed(session):
            return
        cue = selected_cue(session, slot)
        if cue is None:
            return
        tl = session.timeline
        lane = tl.lanes.get(slot) or empty_lane()
        with self.history.recording("Delete cue"):
            updated = remove_lane_cue(lane, cue.t)
            tl.lanes[slot] = updated
            times = navigable_cue_times(updated)
            pick = next((t for t in times if t > cue.t), None)
            if pick is None:
                pick = next((t for t in reversed(times) if t < cue.t), None)
            if pick is None:
                tl.selected_cue_t.pop(slot, None)
                tl.selected_cue_flash_start_ms = None
            else:
                select_cue(session, slot, pick)

    def nudge_level(self, slot: str, *, forward: bool, large: bool) -> None:
        """Step an on cue's opacity by 1% (10% when *large*), clamped to its range."""
        if not cue_edits_allowed(self.session):
            return
        cue = selected_cue(self.session, slot)
        if cue is None or not cue_editable_for_blend_role(cue):
            return
        # Integer percent math matches the layer opacity fader (1% / 10%).
        step_pct = int(
            round((LEVEL_STEP_LARGE if large else LEVEL_STEP_SMALL) * 100.0)
        )
        min_pct = int(round(LEVEL_EDIT_MIN * 100.0))
        pct = int(round(float(cue.level) * 100.0))
        new_pct = max(min_pct, min(100, pct + (step_pct if forward else -step_pct)))
        new_level = new_pct / 100.0
        if levels_equal(new_level, cue.level):
            return
        self._update(slot, cue, "Cue level", "level", level=new_level)

    def set_cut(self, slot: str, cut: CutType) -> None:
        """Set the selected cue's cut. Off cues take a cut too."""
        if not cue_edits_allowed(self.session):
            return
        cue = selected_cue(self.session, slot)
        if cue is None or cue.cut == cut:
            return
        self._update(slot, cue, "Cue cut", "cut", cut=cut)

    def set_blend(self, slot: str, blend: BlendMode | None) -> None:
        """Set an on cue's blend mode; None inherits the layer's."""
        if not cue_edits_allowed(self.session):
            return
        cue = selected_cue(self.session, slot)
        if cue is None or not cue_editable_for_blend_role(cue) or cue.blend == blend:
            return
        self._update(slot, cue, "Cue blend", "blend", blend=blend)

    def set_role(self, slot: str, role: CueRole | None) -> None:
        """Set an on cue's role, or clear it with None."""
        if not cue_edits_allowed(self.session):
            return
        cue = selected_cue(self.session, slot)
        if cue is None or not cue_editable_for_blend_role(cue) or cue.role == role:
            return
        self._update(slot, cue, "Cue role", "role", role=role)

    def _update(
        self,
        slot: str,
        cue: SlotCue,
        label: str,
        kind: str,
        *,
        level: float | None = None,
        cut: object = _KEEP,
        blend: object = _KEEP,
        role: object = _KEEP,
    ) -> None:
        tl = self.session.timeline
        with self.history.recording(label, merge_key=(kind, slot, cue.t)):
            lane = tl.lanes.get(slot) or empty_lane()
            updated = update_lane_cue(
                lane,
                cue.t,
                blend=cue.blend if blend is _KEEP else blend,
                role=cue.role if role is _KEEP else role,
                level=level,
                cut=cue.cut if cut is _KEEP else cut,
            )
            tl.lanes[slot] = updated
            if cue.t not in navigable_cue_times(updated):
                tl.selected_cue_t.pop(slot, None)
                tl.selected_cue_flash_start_ms = None
