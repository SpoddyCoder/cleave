"""Timeline visibility algebra and per-frame layer enablement."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.timeline import TimelineCue, layer_visible_at
from cleave.viz.session import TuningSession
from cleave.viz.timeline_overlay import TimelineViewState

if TYPE_CHECKING:
    from cleave.viz.layer import StemLayer


def timeline_defaults(session: TuningSession) -> dict[str, bool]:
    return {name: session.layers[name].enabled for name in session.layer_z_order}


def timeline_committed_visible(
    session: TuningSession,
    stem: str,
    t_sec: float,
) -> bool:
    return layer_visible_at(
        session.timeline.cues,
        timeline_defaults(session),
        stem,
        t_sec,
    )


def snapshot_monitor_from_timeline(
    session: TuningSession,
    t_sec: float,
) -> dict[str, bool]:
    defaults = timeline_defaults(session)
    return {
        stem: layer_visible_at(session.timeline.cues, defaults, stem, t_sec)
        for stem in session.layer_z_order
    }


def snapshot_monitor_from_output(
    session: TuningSession,
    t_sec: float,
) -> dict[str, bool]:
    return {
        stem: effective_layer_enabled(session, stem, t_sec)
        for stem in session.layer_z_order
    }


def armed_recording_defaults(session: TuningSession) -> dict[str, bool]:
    defaults = timeline_defaults(session)
    defaults.update(session.timeline.record_baseline)
    return defaults


def armed_recording_visible(
    session: TuningSession,
    stem: str,
    t_sec: float,
) -> bool:
    """Visibility for an armed stem during an active record pass."""
    return layer_visible_at(
        session.timeline.record_buffer,
        armed_recording_defaults(session),
        stem,
        t_sec,
    )


def committed_visible_outside_punch(
    session: TuningSession,
    stem: str,
    record_start: float,
    record_stop: float,
) -> bool:
    """Committed visibility at *record_stop* ignoring armed-stem cues inside the punch."""
    kept = [
        cue
        for cue in session.timeline.cues
        if not (
            record_start <= cue.t <= record_stop
            and stem in cue.layers
        )
    ]
    return layer_visible_at(kept, timeline_defaults(session), stem, record_stop)


def build_record_punch_cues(
    session: TuningSession,
    record_start: float,
    record_stop: float,
) -> list[TimelineCue]:
    """Cues to punch on record stop: baseline, toggles, and committed restore at stop."""
    tl = session.timeline
    punch: list[TimelineCue] = []
    for stem in tl.armed_stems:
        baseline = tl.record_baseline.get(stem)
        if baseline is None:
            continue
        if baseline != timeline_committed_visible(session, stem, record_start):
            punch.append(
                TimelineCue(
                    t=record_start,
                    layers={stem: baseline},
                    show_tick=False,
                )
            )
    punch.extend(tl.record_buffer)
    for stem in tl.armed_stems:
        end_visible = armed_recording_visible(session, stem, record_stop)
        committed_at_stop = timeline_committed_visible(session, stem, record_stop)
        if end_visible != committed_at_stop:
            punch.append(
                TimelineCue(
                    t=record_stop,
                    layers={stem: committed_at_stop},
                    show_tick=False,
                )
            )
    return punch


def effective_layer_enabled(
    session: TuningSession,
    stem: str,
    t_sec: float,
) -> bool:
    if session.solo_stem is not None:
        return stem == session.solo_stem
    if not session.timeline.enabled:
        return session.layers[stem].enabled
    tl = session.timeline
    defaults = timeline_defaults(session)
    if tl.recording:
        if stem in tl.armed_stems:
            return armed_recording_visible(session, stem, t_sec)
        if stem in tl.override_stems:
            return tl.override_visible.get(stem, True)
        return layer_visible_at(tl.cues, defaults, stem, t_sec)
    if tl.preview_active:
        return tl.monitor[stem]
    if stem in tl.override_stems:
        return tl.override_visible.get(stem, True)
    return layer_visible_at(tl.cues, defaults, stem, t_sec)


def apply_layer_visibility(
    session: TuningSession,
    layers_by_name: dict[str, StemLayer],
    t_sec: float,
) -> None:
    for stem, layer in layers_by_name.items():
        layer.fbo.enabled = effective_layer_enabled(session, stem, t_sec)


def build_timeline_view_state(
    session: TuningSession,
    position_sec: float,
    duration_sec: float,
) -> TimelineViewState:
    tl = session.timeline
    monitor_visible = {
        stem: effective_layer_enabled(session, stem, position_sec)
        for stem in session.layer_z_order
    }
    timeline_visible = {
        stem: timeline_committed_visible(session, stem, position_sec)
        for stem in session.layer_z_order
    }
    return TimelineViewState(
        layer_z_order=list(session.layer_z_order),
        cues=list(tl.cues),
        defaults=timeline_defaults(session),
        position_sec=position_sec,
        duration_sec=duration_sec,
        focus_row=tl.focus_row,
        monitor_visible=monitor_visible,
        timeline_visible=timeline_visible,
        override_stems=set(tl.override_stems),
        armed_stems=set(tl.armed_stems),
        recording=tl.recording,
        record_start_sec=tl.record_start_sec,
        record_baseline=dict(tl.record_baseline),
        record_buffer=list(tl.record_buffer),
        enabled=tl.enabled,
        submenu_focused=tl.submenu_focused,
    )
