"""Timeline visibility algebra and per-frame layer enablement."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from cleave.timeline import (
    SlotCue,
    TimelineLane,
    canonicalize,
    copy_lane,
    empty_lane,
    lane_visible_at,
    punch_lane,
    shift_bars_by_beats,
    strip_lane_range,
)
from cleave.viz.focus_nav import (
    FocusCursor,
    cursor_timeline_row,
    cursor_timeline_submenu_focused,
)
from cleave.viz.session import TuningSession
from cleave.viz.timeline_overlay import TimelineViewState, prune_expired_arm_flashes

if TYPE_CHECKING:
    from cleave.viz.layer import StemLayer


def _lane_for_slot(session: TuningSession, slot: str) -> TimelineLane:
    return session.timeline.lanes.get(slot) or empty_lane()


def _inherit_for_slot(session: TuningSession, slot: str) -> bool:
    return session.layers[slot].enabled


def timeline_defaults(session: TuningSession) -> dict[str, bool]:
    """Per-slot inherit values: concrete lane baseline, else ``layers[slot].enabled``."""
    return {
        slot: (
            lane.baseline
            if (lane := session.timeline.lanes.get(slot)) is not None
            and lane.baseline is not None
            else session.layers[slot].enabled
        )
        for slot in session.layer_z_order
    }


def timeline_committed_visible(
    session: TuningSession,
    slot: str,
    t_sec: float,
) -> bool:
    return lane_visible_at(
        _lane_for_slot(session, slot),
        t_sec,
        inherit=_inherit_for_slot(session, slot),
    )


def snapshot_monitor_from_timeline(
    session: TuningSession,
    t_sec: float,
) -> dict[str, bool]:
    return {
        slot: timeline_committed_visible(session, slot, t_sec)
        for slot in session.layer_z_order
    }


def snapshot_monitor_from_output(
    session: TuningSession,
    t_sec: float,
) -> dict[str, bool]:
    return {
        slot: effective_layer_enabled(session, slot, t_sec)
        for slot in session.layer_z_order
    }


def armed_recording_defaults(session: TuningSession) -> dict[str, bool]:
    defaults = timeline_defaults(session)
    defaults.update(session.timeline.record_baseline)
    return defaults


def _recording_lane(session: TuningSession, slot: str) -> TimelineLane:
    baseline = session.timeline.record_baseline[slot]
    cues = session.timeline.record_buffer.get(slot, [])
    return TimelineLane(baseline=baseline, cues=list(cues))


def armed_recording_visible(
    session: TuningSession,
    slot: str,
    t_sec: float,
) -> bool:
    """Visibility for a record-pass slot during an active take."""
    return lane_visible_at(_recording_lane(session, slot), t_sec, inherit=True)


def committed_visible_outside_punch(
    session: TuningSession,
    slot: str,
    record_start: float,
    record_stop: float,
) -> bool:
    """Committed visibility at *record_stop* ignoring cues inside the punch."""
    stripped = strip_lane_range(
        _lane_for_slot(session, slot),
        record_start,
        record_stop,
    )
    return lane_visible_at(
        stripped,
        record_stop,
        inherit=_inherit_for_slot(session, slot),
    )


def _fold_lane_baseline(session: TuningSession, slot: str) -> TimelineLane:
    """Freeze inherit into an explicit baseline when the lane was still untouched."""
    lane = _lane_for_slot(session, slot)
    if lane.baseline is not None:
        return TimelineLane(baseline=lane.baseline, cues=list(lane.cues))
    baseline = _inherit_for_slot(session, slot)
    return TimelineLane(
        baseline=baseline,
        cues=canonicalize(baseline, lane.cues),
    )


def _punch_cues_for_slot(
    session: TuningSession,
    slot: str,
    record_start: float,
    record_stop: float,
) -> list[SlotCue]:
    tl = session.timeline
    punch: list[SlotCue] = []
    baseline = tl.record_baseline[slot]
    if baseline != timeline_committed_visible(session, slot, record_start):
        punch.append(SlotCue(t=record_start, visible=baseline))
    punch.extend(tl.record_buffer.get(slot, []))
    end_visible = armed_recording_visible(session, slot, record_stop)
    committed_at_stop = timeline_committed_visible(session, slot, record_stop)
    if end_visible != committed_at_stop:
        punch.append(SlotCue(t=record_stop, visible=committed_at_stop))
    return punch


def build_record_punch_cues(
    session: TuningSession,
    record_start: float,
    record_stop: float,
    *,
    slots: set[str] | None = None,
) -> None:
    """Fold baselines and punch the take into each armed lane."""
    tl = session.timeline
    target_slots = set(tl.record_baseline) if slots is None else slots
    for slot in target_slots:
        if slot not in tl.record_baseline:
            continue
        slot_start = tl.record_slot_start_sec.get(slot, record_start)
        lane = _fold_lane_baseline(session, slot)
        new_cues = _punch_cues_for_slot(session, slot, slot_start, record_stop)
        tl.lanes[slot] = punch_lane(lane, slot_start, record_stop, new_cues)


def effective_layer_enabled(
    session: TuningSession,
    slot: str,
    t_sec: float,
) -> bool:
    if session.solo_slot is not None:
        return slot == session.solo_slot
    if not session.timeline.enabled:
        return session.layers[slot].enabled
    tl = session.timeline
    if tl.recording:
        if slot in tl.record_baseline:
            return armed_recording_visible(session, slot, t_sec)
        if slot in tl.override_slots:
            return tl.override_visible.get(slot, True)
        return timeline_committed_visible(session, slot, t_sec)
    if tl.preview_active:
        return tl.monitor[slot]
    if slot in tl.override_slots:
        return tl.override_visible.get(slot, True)
    return timeline_committed_visible(session, slot, t_sec)


def apply_layer_visibility(
    session: TuningSession,
    layers_by_slot: dict[str, StemLayer],
    t_sec: float,
) -> None:
    for slot, layer in layers_by_slot.items():
        layer.fbo.enabled = effective_layer_enabled(session, slot, t_sec)


def build_timeline_view_state(
    session: TuningSession,
    position_sec: float,
    duration_sec: float,
    *,
    focus_cursor: FocusCursor | None = None,
    bar_times: Sequence[float] = (),
    beat_times: Sequence[float] = (),
) -> TimelineViewState:
    tl = session.timeline
    prune_expired_arm_flashes(tl.arm_flash_start_ms)
    submenu_focused = (
        focus_cursor is not None and cursor_timeline_submenu_focused(focus_cursor)
    )
    focus_row = (
        cursor_timeline_row(focus_cursor)
        if submenu_focused
        else tl.focus_row
    )
    monitor_visible = {
        slot: effective_layer_enabled(session, slot, position_sec)
        for slot in session.layer_z_order
    }
    timeline_visible = {
        slot: timeline_committed_visible(session, slot, position_sec)
        for slot in session.layer_z_order
    }
    return TimelineViewState(
        layer_z_order=list(session.layer_z_order),
        lanes={
            slot: copy_lane(_lane_for_slot(session, slot))
            for slot in session.layer_z_order
        },
        defaults=timeline_defaults(session),
        position_sec=position_sec,
        duration_sec=duration_sec,
        focus_row=focus_row,
        monitor_visible=monitor_visible,
        timeline_visible=timeline_visible,
        slot_stems={slot: session.layers[slot].stem for slot in session.layer_z_order},
        override_slots=set(tl.override_slots),
        armed_slots=set(tl.armed_slots),
        recording=tl.recording,
        record_start_sec=tl.record_start_sec,
        record_slot_start_sec=dict(tl.record_slot_start_sec),
        record_baseline=dict(tl.record_baseline),
        record_buffer={
            slot: list(cues) for slot, cues in tl.record_buffer.items()
        },
        record_high_water_mark=tl.record_high_water_mark,
        enabled=tl.enabled,
        submenu_focused=submenu_focused,
        arm_flash_start_ms=dict(tl.arm_flash_start_ms),
        show_bar_grid=tl.show_bar_grid,
        bar_grid_times=shift_bars_by_beats(
            bar_times, beat_times, tl.bar_phase_offset
        ),
        song_marker_times=tuple(session.song_markers.times),
        selected_song_marker_index=session.song_markers.selected_index,
    )
