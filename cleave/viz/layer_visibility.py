"""Timeline visibility algebra and per-frame layer enablement."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.timeline import TimelineCue, layer_visible_at
from cleave.viz.focus_nav import (
    FocusCursor,
    TimelineFocus,
    cursor_timeline_row,
    cursor_timeline_submenu_focused,
)
from cleave.viz.session import TuningSession
from cleave.viz.timeline_overlay import TimelineViewState, prune_expired_arm_flashes

if TYPE_CHECKING:
    from cleave.viz.layer import StemLayer


def _slot_has_committed_cues(cues: list[TimelineCue], slot: str) -> bool:
    return any(slot in cue.layers for cue in cues)


def _slot_has_t0_cue(cues: list[TimelineCue], slot: str) -> bool:
    return any(slot in cue.layers and cue.t == 0.0 for cue in cues)


def _anchor_visibility_for_slot(
    cues: list[TimelineCue],
    slot: str,
    layer_enabled_fallback: bool,
) -> bool:
    """Pre-first-cue visibility for a slot that already has timeline cues."""
    for cue in cues:
        if cue.t == 0.0 and slot in cue.layers:
            return cue.layers[slot]
    slot_cues = [cue for cue in cues if slot in cue.layers]
    if not slot_cues:
        return layer_enabled_fallback
    earliest = min(slot_cues, key=lambda cue: cue.t)
    if earliest.t > 0.0 and earliest.show_tick:
        return not earliest.layers[slot]
    return layer_enabled_fallback


def timeline_defaults(session: TuningSession) -> dict[str, bool]:
    cues = session.timeline.cues
    return {
        slot: (
            _anchor_visibility_for_slot(cues, slot, session.layers[slot].enabled)
            if _slot_has_committed_cues(cues, slot)
            else session.layers[slot].enabled
        )
        for slot in session.layer_z_order
    }


def timeline_committed_visible(
    session: TuningSession,
    slot: str,
    t_sec: float,
) -> bool:
    return layer_visible_at(
        session.timeline.cues,
        timeline_defaults(session),
        slot,
        t_sec,
    )


def snapshot_monitor_from_timeline(
    session: TuningSession,
    t_sec: float,
) -> dict[str, bool]:
    defaults = timeline_defaults(session)
    return {
        slot: layer_visible_at(session.timeline.cues, defaults, slot, t_sec)
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


def armed_recording_visible(
    session: TuningSession,
    slot: str,
    t_sec: float,
) -> bool:
    """Visibility for a record-pass slot during an active take."""
    return layer_visible_at(
        session.timeline.record_buffer,
        armed_recording_defaults(session),
        slot,
        t_sec,
    )


def committed_visible_outside_punch(
    session: TuningSession,
    slot: str,
    record_start: float,
    record_stop: float,
) -> bool:
    """Committed visibility at *record_stop* ignoring armed-slot cues inside the punch."""
    kept = [
        cue
        for cue in session.timeline.cues
        if not (
            record_start <= cue.t <= record_stop
            and slot in cue.layers
        )
    ]
    return layer_visible_at(kept, timeline_defaults(session), slot, record_stop)


def build_record_punch_cues(
    session: TuningSession,
    record_start: float,
    record_stop: float,
    *,
    slots: set[str] | None = None,
) -> list[TimelineCue]:
    """Cues to punch on record stop: baseline, toggles, and committed restore at stop."""
    tl = session.timeline
    target_slots = set(tl.record_baseline) if slots is None else slots
    punch: list[TimelineCue] = []
    for slot in target_slots:
        if slot not in tl.record_baseline:
            continue
        if not _slot_has_t0_cue(tl.cues, slot):
            punch.append(
                TimelineCue(
                    t=0.0,
                    layers={
                        slot: timeline_committed_visible(session, slot, 0.0),
                    },
                    show_tick=False,
                )
            )
    for slot, baseline in tl.record_baseline.items():
        if slot not in target_slots:
            continue
        if baseline != timeline_committed_visible(session, slot, record_start):
            punch.append(
                TimelineCue(
                    t=record_start,
                    layers={slot: baseline},
                    show_tick=False,
                )
            )
    punch.extend(
        cue
        for cue in tl.record_buffer
        if target_slots.intersection(cue.layers)
    )
    for slot in target_slots:
        if slot not in tl.record_baseline:
            continue
        end_visible = armed_recording_visible(session, slot, record_stop)
        committed_at_stop = timeline_committed_visible(session, slot, record_stop)
        if end_visible != committed_at_stop:
            punch.append(
                TimelineCue(
                    t=record_stop,
                    layers={slot: committed_at_stop},
                    show_tick=False,
                )
            )
    return punch


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
    defaults = timeline_defaults(session)
    if tl.recording:
        if slot in tl.record_baseline:
            return armed_recording_visible(session, slot, t_sec)
        if slot in tl.override_slots:
            return tl.override_visible.get(slot, True)
        return layer_visible_at(tl.cues, defaults, slot, t_sec)
    if tl.preview_active:
        return tl.monitor[slot]
    if slot in tl.override_slots:
        return tl.override_visible.get(slot, True)
    return layer_visible_at(tl.cues, defaults, slot, t_sec)


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
        cues=list(tl.cues),
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
        record_baseline=dict(tl.record_baseline),
        record_buffer=list(tl.record_buffer),
        record_high_water_mark=tl.record_high_water_mark,
        enabled=tl.enabled,
        submenu_focused=submenu_focused,
        arm_flash_start_ms=dict(tl.arm_flash_start_ms),
    )
