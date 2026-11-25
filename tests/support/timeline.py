"""Shared timeline lane, controller, and strip view-state builders for unit tests."""

from __future__ import annotations

from pathlib import Path

from cleave.config_schema.layers import DEFAULT_LAYER_SLOTS
from cleave.timeline import (
    LEVEL_EPS,
    SlotCue,
    TimelineFadeGroup,
    TimelineLane,
    canonicalize,
    copy_lane,
    empty_lane,
    lane_level_at,
)
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.timeline_controls import TimelineControls
from cleave.viz.timeline_strip_state import TimelineViewState
from tests.support.config import TEST_LAYER_STEMS
from tests.support.viz import make_playlist, stub_playback_state


def as_level(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    return float(value)


def make_lane(
    baseline,
    *transitions,
) -> TimelineLane:
    base = as_level(baseline)
    cues = [SlotCue(t=t, level=float(as_level(level))) for t, level in transitions]
    return TimelineLane(baseline=base, cues=canonicalize(base, cues))


def make_timeline_controls(
    *,
    slots: tuple[str, ...] = tuple(DEFAULT_LAYER_SLOTS),
    lanes: dict[str, TimelineLane] | None = None,
    focus_row: int = 0,
    armed_slots: set[str] | None = None,
    panel_open: bool = True,
    enabled: bool = True,
    position_sec: float = 0.0,
    recording: bool = False,
    beat_times: tuple[float, ...] = (),
    bar_times: tuple[float, ...] = (),
) -> tuple[
    TimelineControls,
    TuningSession,
    list[bool],
    list[bool],
    list[float],
    list[str],
]:
    preset_root = Path("/tmp/presets")
    session = TuningSession(
        layer_z_order=list(slots),
        layers={
            slot: LayerRuntime(
                playlist=make_playlist(slot),
                browse_floor=preset_root / slot,
                stem=TEST_LAYER_STEMS.get(slot, "drums"),
            )
            for slot in slots
        },
    )
    tl = session.timeline
    tl.enabled = enabled
    tl.panel_open = panel_open
    tl.lanes = {
        slot: copy_lane(lanes[slot]) if lanes and slot in lanes else empty_lane()
        for slot in slots
    }
    tl.focus_row = focus_row
    tl.armed_slots = set(armed_slots or ())
    tl.recording = recording

    playback = stub_playback_state()
    playback.player.seek(position_sec)

    visibility_calls: list[bool] = []
    exit_calls: list[bool] = []
    seeks: list[float] = []
    notifications: list[str] = []

    controls = TimelineControls(
        session,
        playback,
        120.0,
        on_visibility_change=lambda: visibility_calls.append(True),
        on_exit_submenu=lambda: exit_calls.append(True),
        on_seek=lambda delta: seeks.append(delta),
        on_notification=notifications.append,
        beat_times=beat_times,
        bar_times=bar_times,
    )
    return controls, session, visibility_calls, exit_calls, seeks, notifications


def strip_view_state(
    *,
    lanes: dict[str, TimelineLane] | None = None,
    defaults: dict[str, float] | None = None,
    position_sec: float = 0.0,
    duration_sec: float = 100.0,
    focus_row: int = 0,
    submenu_focused: bool = False,
    armed_slots: set[str] | None = None,
    recording: bool = False,
    record_start_sec: float | None = None,
    record_baseline: dict[str, float] | None = None,
    record_buffer: dict[str, list[SlotCue]] | None = None,
    record_high_water_mark: float | None = None,
    enabled: bool = True,
    layer_z_order: list[str] | None = None,
    monitor_visible: dict[str, bool] | None = None,
    override_slots: set[str] | None = None,
    solo_slot: str | None = None,
    hover_row_target: tuple[str, int] | None = None,
    arm_flash_start_ms: dict[str, int] | None = None,
    show_bar_grid: bool = False,
    bar_grid_times: tuple[float, ...] = (),
    beat_grid_times: tuple[float, ...] = (),
    song_marker_times: tuple[float, ...] = (),
    song_marker_types: tuple[str, ...] = (),
    song_marker_intensities: tuple[str, ...] | None = None,
    selected_song_marker_index: int | None = None,
    song_marker_flash_start_ms: int | None = None,
    hard_cut_fades_enabled: bool = False,
    hard_cut_fade_in: float = 2.0,
    hard_cut_fade_out: float = 2.0,
    hard_cut_crossfade: bool = False,
    soft_cut_fades_enabled: bool = False,
    soft_cut_fade_in: float = 2.0,
    soft_cut_fade_out: float = 2.0,
    soft_cut_crossfade: bool = False,
    selected_clip_t: dict[str, float] | None = None,
    hover_clip: tuple[int, float, str | None] | None = None,
    locked: bool = False,
    selected_clip_flash_start_ms: int | None = None,
) -> TimelineViewState:
    order = list(layer_z_order or list(DEFAULT_LAYER_SLOTS))
    lane_map = dict(lanes or {})
    default_map = {
        slot: float(as_level(level))
        for slot, level in (
            defaults or {slot: 1.0 for slot in (layer_z_order or list(DEFAULT_LAYER_SLOTS))}
        ).items()
    }
    if monitor_visible is None:
        monitor_visible = {
            stem: float(
                lane_level_at(
                    lane_map.get(stem) or TimelineLane(baseline=None, cues=[]),
                    position_sec,
                    inherit=float(as_level(default_map[stem])),
                )
            )
            > LEVEL_EPS
            for stem in order
        }
    return TimelineViewState(
        layer_z_order=order,
        slot_stems={
            slot: TEST_LAYER_STEMS.get(slot, "drums")
            for slot in order
        },
        lanes=lane_map,
        defaults=default_map,
        position_sec=position_sec,
        duration_sec=duration_sec,
        focus_row=focus_row,
        monitor_visible=monitor_visible,
        override_slots=set(override_slots or ()),
        solo_slot=solo_slot,
        hover_row_target=hover_row_target,
        armed_slots=set(armed_slots or ()),
        recording=recording,
        record_start_sec=record_start_sec,
        record_baseline={slot: float(as_level(level)) for slot, level in dict(record_baseline or ()).items()},
        record_buffer=dict(record_buffer or ()),
        record_high_water_mark=record_high_water_mark,
        enabled=enabled,
        submenu_focused=submenu_focused,
        arm_flash_start_ms=dict(arm_flash_start_ms or ()),
        show_bar_grid=show_bar_grid,
        bar_grid_times=bar_grid_times,
        beat_grid_times=beat_grid_times,
        song_marker_times=song_marker_times,
        song_marker_types=song_marker_types,
        song_marker_intensities=(
            ("normal",) * len(song_marker_types)
            if song_marker_intensities is None
            else song_marker_intensities
        ),
        selected_song_marker_index=selected_song_marker_index,
        song_marker_flash_start_ms=song_marker_flash_start_ms,
        hard_cut_fades=TimelineFadeGroup(
            enabled=hard_cut_fades_enabled,
            fade_in=hard_cut_fade_in,
            fade_out=hard_cut_fade_out,
            crossfade=hard_cut_crossfade,
        ),
        soft_cut_fades=TimelineFadeGroup(
            enabled=soft_cut_fades_enabled,
            fade_in=soft_cut_fade_in,
            fade_out=soft_cut_fade_out,
            crossfade=soft_cut_crossfade,
        ),
        selected_clip_t=dict(selected_clip_t or ()),
        selected_clip_flash_start_ms=selected_clip_flash_start_ms,
        hover_clip=hover_clip,
        locked=locked,
    )
