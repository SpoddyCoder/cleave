"""Retained surfaces and signatures for the bottom timeline strip."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from cleave.config_schema.layers import MAX_LAYER_COUNT
from cleave.timeline import SlotCue, TimelineLane
from cleave.viz.overlay_primitives import overlay_font, visibility_bucket
from cleave.viz.overlay_upload import OverlayGpuState, UploadSignature
from cleave.viz.playback import format_mmss
from cleave.viz.theme import timeline_panel_height_px, timeline_ui_metrics

if TYPE_CHECKING:
    from cleave.viz.timeline_overlay import TimelineViewState


@dataclass(frozen=True)
class TimelineStaticSignature:
    """Everything affecting strip chrome except live transport/playhead.

    While recording, ``record_playhead_sec`` is included because armed-row bars
    grow with the playhead (see ``bar_level_breakpoints_for_row``). Outside
    recording the playhead is live-patched only.
    """

    layer_z_order: tuple[str, ...]
    lanes_fingerprint: tuple[
        tuple[
            str,
            float | None,
            tuple[tuple[float, float, str | None, str | None, str | None], ...],
        ],
        ...,
    ]
    defaults: tuple[tuple[str, float], ...]
    duration_sec: float
    focus_row: int
    monitor_visible: tuple[tuple[str, bool], ...]
    timeline_level: tuple[tuple[str, float], ...]
    slot_stems: tuple[tuple[str, str], ...]
    override_slots: frozenset[str]
    armed_slots: frozenset[str]
    recording: bool
    submenu_focused: bool
    record_start_sec: float | None
    record_slot_start_sec: tuple[tuple[str, float], ...]
    record_baseline: tuple[tuple[str, float], ...]
    record_buffer_fingerprint: tuple[
        tuple[str, tuple[tuple[float, float, str | None, str | None, str | None], ...]],
        ...,
    ]
    record_high_water_mark: float | None
    record_playhead_sec: float | None
    panel_w: int
    panel_h: int
    visibility_bucket: int
    show_bar_grid: bool
    bar_grid_times: tuple[float, ...]
    song_marker_times: tuple[float, ...]
    selected_song_marker_index: int | None
    hard_cut_fades_enabled: bool
    hard_cut_fade_in: float
    hard_cut_fade_out: float
    hard_cut_crossfade: bool
    soft_cut_fades_enabled: bool
    soft_cut_fade_in: float
    soft_cut_fade_out: float
    soft_cut_crossfade: bool
    selected_cue_t: tuple[tuple[str, float], ...]


@dataclass
class TimelinePanelCache:
    panel: pygame.Surface | None = None
    static_signature: TimelineStaticSignature | None = None
    panel_size: tuple[int, int] | None = None
    gpu: OverlayGpuState = field(default_factory=OverlayGpuState)
    last_live_signature: tuple | None = None
    last_playhead_rect: tuple[int, int, int, int] | None = None
    last_badge_rect: tuple[int, int, int, int] | None = None
    last_flash_rects: tuple[tuple[int, int, int, int], ...] = ()
    last_glyph_rects: tuple[tuple[int, int, int, int], ...] = ()


def _slot_cues_fingerprint(
    cues: list[SlotCue],
) -> tuple[tuple[float, float, str | None, str | None, str | None], ...]:
    return tuple((cue.t, cue.level, cue.blend, cue.role, cue.cut) for cue in cues)


def _lane_fingerprint(
    lane: TimelineLane,
) -> tuple[
    float | None, tuple[tuple[float, float, str | None, str | None, str | None], ...]
]:
    return (lane.baseline, _slot_cues_fingerprint(lane.cues))


def _lanes_fingerprint(
    lanes: dict[str, TimelineLane],
) -> tuple[
    tuple[
        str,
        float | None,
        tuple[tuple[float, float, str | None, str | None, str | None], ...],
    ],
    ...,
]:
    return tuple(
        (slot, *_lane_fingerprint(lane))
        for slot, lane in sorted(lanes.items())
    )


def _record_buffer_fingerprint(
    record_buffer: dict[str, list[SlotCue]],
) -> tuple[
    tuple[str, tuple[tuple[float, float, str | None, str | None, str | None], ...]],
    ...,
]:
    return tuple(
        (slot, _slot_cues_fingerprint(cues))
        for slot, cues in sorted(record_buffer.items())
    )


def timeline_static_signature(
    state: TimelineViewState,
    *,
    panel_w: int,
    panel_h: int,
    visibility: float,
) -> TimelineStaticSignature:
    return TimelineStaticSignature(
        layer_z_order=tuple(state.layer_z_order),
        lanes_fingerprint=_lanes_fingerprint(state.lanes),
        defaults=tuple(sorted(state.defaults.items())),
        duration_sec=state.duration_sec,
        focus_row=state.focus_row,
        monitor_visible=tuple(sorted(state.monitor_visible.items())),
        timeline_level=tuple(sorted(state.timeline_level.items())),
        slot_stems=tuple(sorted((k, str(v)) for k, v in state.slot_stems.items())),
        override_slots=frozenset(state.override_slots),
        armed_slots=frozenset(state.armed_slots),
        recording=state.recording,
        submenu_focused=state.submenu_focused,
        record_start_sec=state.record_start_sec,
        record_slot_start_sec=tuple(sorted(state.record_slot_start_sec.items())),
        record_baseline=tuple(sorted(state.record_baseline.items())),
        record_buffer_fingerprint=_record_buffer_fingerprint(state.record_buffer),
        record_high_water_mark=state.record_high_water_mark,
        record_playhead_sec=state.position_sec if state.recording else None,
        panel_w=panel_w,
        panel_h=panel_h,
        visibility_bucket=visibility_bucket(visibility),
        show_bar_grid=state.show_bar_grid,
        bar_grid_times=state.bar_grid_times,
        song_marker_times=state.song_marker_times,
        selected_song_marker_index=state.selected_song_marker_index,
        hard_cut_fades_enabled=state.hard_cut_fades.enabled,
        hard_cut_fade_in=state.hard_cut_fades.fade_in,
        hard_cut_fade_out=state.hard_cut_fades.fade_out,
        hard_cut_crossfade=state.hard_cut_fades.crossfade,
        soft_cut_fades_enabled=state.soft_cut_fades.enabled,
        soft_cut_fade_in=state.soft_cut_fades.fade_in,
        soft_cut_fade_out=state.soft_cut_fades.fade_out,
        soft_cut_crossfade=state.soft_cut_fades.crossfade,
        selected_cue_t=tuple(sorted(state.selected_cue_t.items())),
    )


def timeline_upload_signature(
    static_sig: TimelineStaticSignature,
    screen_rect: tuple[int, int, int, int],
    live_sig: tuple,
) -> UploadSignature:
    return UploadSignature(
        active_size=(screen_rect[2], screen_rect[3]),
        screen_rect=screen_rect,
        content_hash=(static_sig, live_sig),
    )


def timeline_badge_reserve_px(*, font_size: int | None = None) -> int:
    metrics = timeline_ui_metrics()
    if font_size is None:
        font_size = metrics.font_size
    font = overlay_font(font_size)
    sample = font.render(f"[{format_mmss(0.0)}]", True, (255, 255, 255))
    badge_h = sample.get_height() + metrics.rec_badge_pad_y * 2
    return badge_h + metrics.rec_badge_gap


def timeline_panel_max_dimensions(
    viewport_w: int,
    viewport_h: int,
    *,
    margin: int | None = None,
) -> tuple[int, int]:
    metrics = timeline_ui_metrics()
    if margin is None:
        margin = metrics.margin
    panel_w = max(1, viewport_w - margin * 2)
    panel_h = timeline_panel_height_px(MAX_LAYER_COUNT)
    badge_reserve = timeline_badge_reserve_px(font_size=metrics.font_size)
    return panel_w, panel_h + badge_reserve
