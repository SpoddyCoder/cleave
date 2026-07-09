"""Retained surfaces and signatures for the bottom timeline strip."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from cleave.config_schema import MAX_LAYER_COUNT
from cleave.viz.overlay_upload import OverlayGpuState, UploadSignature
from cleave.viz.playback import format_mmss
from cleave.viz.theme import timeline_panel_height_px, timeline_ui_metrics

if TYPE_CHECKING:
    from cleave.viz.timeline_overlay import TimelineViewState


@dataclass(frozen=True)
class TimelineStaticSignature:
    """Everything affecting strip chrome except live transport/playhead.

    While recording, ``record_playhead_sec`` is included because armed-row bars
    grow with the playhead (see ``bar_segments_for_row``). Outside recording the
    playhead is live-patched only.
    """

    layer_z_order: tuple[str, ...]
    cues_fingerprint: tuple[tuple[float, tuple[tuple[str, bool], ...], bool], ...]
    defaults: tuple[tuple[str, bool], ...]
    duration_sec: float
    focus_row: int
    monitor_visible: tuple[tuple[str, bool], ...]
    timeline_visible: tuple[tuple[str, bool], ...]
    slot_stems: tuple[tuple[str, str], ...]
    override_slots: frozenset[str]
    armed_slots: frozenset[str]
    recording: bool
    submenu_focused: bool
    record_start_sec: float | None
    record_baseline: tuple[tuple[str, bool], ...]
    record_buffer_fingerprint: tuple[tuple[float, tuple[tuple[str, bool], ...], bool], ...]
    record_high_water_mark: float | None
    record_playhead_sec: float | None
    panel_w: int
    panel_h: int
    visibility_bucket: int


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


def visibility_bucket(visibility: float) -> int:
    if visibility <= 0.01:
        return 0
    return min(255, int(visibility * 255))


def _cue_fingerprint(cues: list) -> tuple[tuple[float, tuple[tuple[str, bool], ...], bool], ...]:
    return tuple(
        (cue.t, tuple(sorted(cue.layers.items())), cue.show_tick) for cue in cues
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
        cues_fingerprint=_cue_fingerprint(state.cues),
        defaults=tuple(sorted(state.defaults.items())),
        duration_sec=state.duration_sec,
        focus_row=state.focus_row,
        monitor_visible=tuple(sorted(state.monitor_visible.items())),
        timeline_visible=tuple(sorted(state.timeline_visible.items())),
        slot_stems=tuple(sorted((k, str(v)) for k, v in state.slot_stems.items())),
        override_slots=frozenset(state.override_slots),
        armed_slots=frozenset(state.armed_slots),
        recording=state.recording,
        submenu_focused=state.submenu_focused,
        record_start_sec=state.record_start_sec,
        record_baseline=tuple(sorted(state.record_baseline.items())),
        record_buffer_fingerprint=_cue_fingerprint(state.record_buffer),
        record_high_water_mark=state.record_high_water_mark,
        record_playhead_sec=state.position_sec if state.recording else None,
        panel_w=panel_w,
        panel_h=panel_h,
        visibility_bucket=visibility_bucket(visibility),
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
    font = pygame.font.SysFont("monospace", font_size)
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
