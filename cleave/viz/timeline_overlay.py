"""Bottom timeline strip overlay for per-stem layer visibility cues."""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from cleave.config_schema import DEFAULT_TIMELINE_FADES_APPLY_TO, DEFAULT_TIMELINE_FADES_ENABLED, DEFAULT_TIMELINE_FADE_IN, DEFAULT_TIMELINE_FADE_OUT, TimelineFadesApplyTo
from cleave.extract import StemSource
from cleave.timeline import (
    SlotCue,
    TimelineLane,
    empty_lane,
    lane_fade_spans,
    lane_segments,
    lane_tick_times,
    stem_abbreviation,
)
from cleave.viz.material_icons import visibility_icon_slot_width
from cleave.viz.overlay_upload import (
    UploadPlan,
    UploadSignature,
    clip_dirty_rects,
    upload_plan_for_signature,
)
from cleave.viz.timeline_panel_cache import (
    TimelinePanelCache,
    timeline_badge_reserve_px,
    timeline_panel_max_dimensions,
    timeline_static_signature,
    timeline_upload_signature,
)
from cleave.viz.tuning_panel_draw import clip_rect_to_bounds, clip_rect_to_surface, render_visibility_icon
from cleave.viz.playback import format_mmss
from cleave.viz.theme import (
    ARMED_BG,
    BACKGROUND,
    BACKGROUND_ALPHA,
    BAR_GRID,
    BORDER_COLOR,
    BORDER_WIDTH,
    HIGHLIGHT,
    LABEL,
    PLAYHEAD,
    PLAYHEAD_FLASH,
    REC_BG,
    SONG_MARKER,
    SONG_MARKER_SELECTED,
    TIMELINE_BAR_ON,
    VALUE,
    timeline_panel_height_px,
    timeline_ui_metrics,
)
from cleave.viz.ui_tint import blit_tint

_timeline_ui = timeline_ui_metrics()
TIMELINE_PANEL_GAP: int = _timeline_ui.panel_gap
OFF_SEGMENT_COLOR: tuple[int, int, int] = (40, 40, 40)


def timeline_viewport_reserve_px(row_count: int, *, margin: int | None = None) -> int:
    metrics = timeline_ui_metrics()
    if margin is None:
        margin = metrics.margin
    panel_h = timeline_panel_height_px(row_count)
    return panel_h + margin + metrics.panel_gap


BAR_VERTICAL_INSET: int = _timeline_ui.bar_vertical_inset
ARMED_BG_ALPHA: int = 220
CUE_TICK_ALPHA: int = 120
PLAYHEAD_WIDTH: int = _timeline_ui.playhead_width
REC_BADGE_GAP: int = _timeline_ui.rec_badge_gap
REC_BADGE_PAD_X: int = _timeline_ui.rec_badge_pad_x
REC_BADGE_PAD_Y: int = _timeline_ui.rec_badge_pad_y
REC_TIME_GAP: int = _timeline_ui.rec_time_gap
REC_FLASH_MS: int = 500
PLAYHEAD_FLASH_MS: int = 400
ARM_FLASH_HALF_MS: int = 150
ARM_FLASH_DURATION_MS: int = ARM_FLASH_HALF_MS * 4


@dataclass
class TimelineViewState:
    layer_z_order: list[str]
    lanes: dict[str, TimelineLane]
    defaults: dict[str, bool]
    position_sec: float
    duration_sec: float
    focus_row: int  # 0..N-1, index into layer_z_order (0 = bottom stem)
    monitor_visible: dict[str, bool]
    timeline_visible: dict[str, bool]
    slot_stems: dict[str, StemSource] = field(default_factory=dict)
    override_slots: set[str] = field(default_factory=set)
    armed_slots: set[str] = field(default_factory=set)
    recording: bool = False
    record_start_sec: float | None = None
    record_slot_start_sec: dict[str, float] = field(default_factory=dict)
    record_baseline: dict[str, bool] = field(default_factory=dict)
    record_buffer: dict[str, list[SlotCue]] = field(default_factory=dict)
    record_high_water_mark: float | None = None
    enabled: bool = False
    submenu_focused: bool = False
    arm_flash_start_ms: dict[str, int] = field(default_factory=dict)
    show_bar_grid: bool = False
    bar_grid_times: tuple[float, ...] = ()
    song_marker_times: tuple[float, ...] = ()
    selected_song_marker_index: int | None = None
    fades_enabled: bool = DEFAULT_TIMELINE_FADES_ENABLED
    fade_in: float = DEFAULT_TIMELINE_FADE_IN
    fade_out: float = DEFAULT_TIMELINE_FADE_OUT
    fades_apply_to: TimelineFadesApplyTo = DEFAULT_TIMELINE_FADES_APPLY_TO


def visibility_segments(
    lane: TimelineLane,
    duration_sec: float,
    *,
    inherit: bool,
) -> list[tuple[float, float, bool]]:
    """Return ``(start_t, end_t, visible)`` segments over ``[0, duration_sec]``."""
    return lane_segments(lane, duration_sec, inherit=inherit)


def cue_times_for_stem(
    lane: TimelineLane,
    duration_sec: float,
) -> list[float]:
    """Cue times within ``[0, duration_sec]`` (every stored cue is a real transition)."""
    return lane_tick_times(lane, duration_sec)


def _lane_for_view(state: TimelineViewState, slot: str) -> TimelineLane:
    return state.lanes.get(slot) or empty_lane()


def _inherit_for_view(state: TimelineViewState, slot: str) -> bool:
    return state.defaults.get(slot, True)


def _recording_view_lane(state: TimelineViewState, slot: str) -> TimelineLane:
    return TimelineLane(
        baseline=state.record_baseline[slot],
        cues=list(state.record_buffer.get(slot, [])),
    )


def _clip_segments(
    segments: list[tuple[float, float, bool]],
    range_start: float,
    range_end: float,
) -> list[tuple[float, float, bool]]:
    clipped: list[tuple[float, float, bool]] = []
    for start_t, end_t, visible in segments:
        clip_start = max(start_t, range_start)
        clip_end = min(end_t, range_end)
        if clip_end > clip_start:
            clipped.append((clip_start, clip_end, visible))
    return clipped


def bar_segments_for_row(
    state: TimelineViewState,
    slot: str,
) -> list[tuple[float, float, bool]]:
    """Visibility segments for one timeline row, including live record preview."""
    duration = state.duration_sec
    if duration <= 0:
        return []
    inherit = _inherit_for_view(state, slot)
    lane = _lane_for_view(state, slot)
    if not (state.recording and slot in state.record_baseline):
        return visibility_segments(lane, duration, inherit=inherit)

    record_start = state.record_slot_start_sec.get(slot, state.record_start_sec)
    if record_start is None:
        record_start = state.position_sec
    record_start = max(0.0, min(record_start, duration))
    playhead = max(0.0, min(state.position_sec, duration))

    segments: list[tuple[float, float, bool]] = []
    committed = visibility_segments(lane, duration, inherit=inherit)

    if record_start > 0.0:
        segments.extend(_clip_segments(committed, 0.0, record_start))

    effective_end = max(playhead, state.record_high_water_mark or 0.0)
    if effective_end > record_start:
        segments.extend(
            _clip_segments(
                visibility_segments(
                    _recording_view_lane(state, slot),
                    effective_end,
                    inherit=True,
                ),
                record_start,
                effective_end,
            )
        )

    if effective_end < duration:
        segments.extend(_clip_segments(committed, effective_end, duration))
    return segments


def bar_tick_times_for_row(state: TimelineViewState, slot: str) -> list[float]:
    """Cue tick times for one timeline row."""
    duration = state.duration_sec
    lane = _lane_for_view(state, slot)
    if not (state.recording and slot in state.record_baseline):
        return cue_times_for_stem(lane, duration)

    record_start = state.record_slot_start_sec.get(slot, state.record_start_sec)
    if record_start is None:
        record_start = state.position_sec
    playhead = state.position_sec
    effective_end = max(playhead, state.record_high_water_mark or 0.0)
    committed_ticks = [
        t
        for t in cue_times_for_stem(lane, duration)
        if t < record_start or t > effective_end
    ]
    live_ticks = [
        t
        for t in cue_times_for_stem(_recording_view_lane(state, slot), duration)
        if record_start <= t <= effective_end
    ]
    return sorted(set(committed_ticks) | set(live_ticks))


def _clip_fade_spans(
    spans: list[tuple[float, float, str]],
    range_start: float,
    range_end: float,
) -> list[tuple[float, float, str]]:
    clipped: list[tuple[float, float, str]] = []
    for t0, t1, kind in spans:
        clip_start = max(t0, range_start)
        clip_end = min(t1, range_end)
        if clip_end > clip_start:
            clipped.append((clip_start, clip_end, kind))
    return clipped


def _fade_spans_for_lane(
    state: TimelineViewState,
    lane: TimelineLane,
    slot: str,
) -> list[tuple[float, float, str]]:
    exclude_song_markers = state.fades_apply_to == "exclude_song_markers"
    return lane_fade_spans(
        lane,
        inherit=_inherit_for_view(state, slot),
        fade_in=state.fade_in,
        fade_out=state.fade_out,
        duration_sec=state.duration_sec,
        song_marker_times=state.song_marker_times,
        exclude_song_markers=exclude_song_markers,
    )


def bar_fade_spans_for_row(
    state: TimelineViewState,
    slot: str,
) -> list[tuple[float, float, str]]:
    """Fade wedge spans for one timeline row, including live record preview."""
    duration = state.duration_sec
    if duration <= 0 or not state.fades_enabled:
        return []
    lane = _lane_for_view(state, slot)
    if not (state.recording and slot in state.record_baseline):
        return _fade_spans_for_lane(state, lane, slot)

    record_start = state.record_slot_start_sec.get(slot, state.record_start_sec)
    if record_start is None:
        record_start = state.position_sec
    record_start = max(0.0, min(record_start, duration))
    playhead = max(0.0, min(state.position_sec, duration))
    effective_end = max(playhead, state.record_high_water_mark or 0.0)

    spans: list[tuple[float, float, str]] = []
    committed_spans = _fade_spans_for_lane(state, lane, slot)
    if record_start > 0.0:
        spans.extend(_clip_fade_spans(committed_spans, 0.0, record_start))
    if effective_end > record_start:
        exclude_song_markers = state.fades_apply_to == "exclude_song_markers"
        live_spans = lane_fade_spans(
            _recording_view_lane(state, slot),
            inherit=True,
            fade_in=state.fade_in,
            fade_out=state.fade_out,
            duration_sec=state.duration_sec,
            song_marker_times=state.song_marker_times,
            exclude_song_markers=exclude_song_markers,
        )
        spans.extend(_clip_fade_spans(live_spans, record_start, effective_end))
    if effective_end < duration:
        spans.extend(_clip_fade_spans(committed_spans, effective_end, duration))
    return spans


def _draw_fade_wedge(
    panel: pygame.Surface,
    *,
    t0: float,
    t1: float,
    kind: str,
    bar_left: int,
    bar_width: int,
    duration_sec: float,
    bar_rect: pygame.Rect,
    color: tuple[int, int, int],
) -> None:
    x0 = time_to_x(t0, bar_left, bar_width, duration_sec)
    x1 = time_to_x(t1, bar_left, bar_width, duration_sec)
    if x1 <= x0:
        return
    top = bar_rect.y
    bottom = bar_rect.bottom - 1
    if kind == "in":
        points = [(x0, bottom), (x1, bottom), (x1, top)]
    else:
        points = [(x0, top), (x0, bottom), (x1, bottom)]
    pygame.draw.polygon(panel, color, points)


def rec_flash_visible(ticks_ms: int | None = None) -> bool:
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    return (ticks_ms // REC_FLASH_MS) % 2 == 0


def playhead_flash_bright(ticks_ms: int | None = None) -> bool:
    """True on the bright half of the playhead blink cycle."""
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    return (ticks_ms // PLAYHEAD_FLASH_MS) % 2 == 0


def playhead_color(ticks_ms: int | None = None) -> tuple[int, int, int]:
    if playhead_flash_bright(ticks_ms):
        return PLAYHEAD_FLASH
    return PLAYHEAD


def prune_expired_arm_flashes(
    flash_starts: dict[str, int],
    ticks_ms: int | None = None,
) -> None:
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    expired = [
        slot
        for slot, start_ms in flash_starts.items()
        if ticks_ms - start_ms >= ARM_FLASH_DURATION_MS
    ]
    for slot in expired:
        flash_starts.pop(slot, None)


def arm_abbrev_flash_active(
    flash_starts: dict[str, int],
    slot: str,
    ticks_ms: int | None = None,
) -> bool:
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    start_ms = flash_starts.get(slot)
    if start_ms is None:
        return False
    return ticks_ms - start_ms < ARM_FLASH_DURATION_MS


def arm_abbrev_flash_visible(
    flash_starts: dict[str, int],
    slot: str,
    ticks_ms: int | None = None,
) -> bool:
    if not arm_abbrev_flash_active(flash_starts, slot, ticks_ms=ticks_ms):
        return False
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    start_ms = flash_starts[slot]
    elapsed = ticks_ms - start_ms
    return (elapsed // ARM_FLASH_HALF_MS) % 2 == 0


def armed_abbrev_bg_visible(
    *,
    armed: bool,
    recording: bool,
    flash_starts: dict[str, int],
    slot: str,
    ticks_ms: int | None = None,
) -> bool:
    if arm_abbrev_flash_active(flash_starts, slot, ticks_ms=ticks_ms):
        return arm_abbrev_flash_visible(flash_starts, slot, ticks_ms=ticks_ms)
    return armed and (not recording or rec_flash_visible(ticks_ms))


def time_to_x(t_sec: float, bar_left: int, bar_width: int, duration_sec: float) -> int:
    if duration_sec <= 0:
        return bar_left
    ratio = max(0.0, min(1.0, t_sec / duration_sec))
    return bar_left + int(ratio * bar_width)


def playhead_x(
    position_sec: float,
    bar_left: int,
    bar_width: int,
    duration_sec: float,
) -> int:
    return time_to_x(position_sec, bar_left, bar_width, duration_sec)


def layer_num_prefix(layer_num: int) -> str:
    return f" {layer_num} "


def stem_abbrev_label(stem: str) -> str:
    return f" {stem_abbreviation(stem)} "


def transport_time_text(position_sec: float) -> str:
    return f"[{format_mmss(position_sec)}]"


def stem_label_text(layer_num: int, stem: str) -> str:
    return f"{layer_num_prefix(layer_num)}{stem_abbrev_label(stem)}"


def row_prefix_width(
    layer_num_width: int,
    stem_abbrev_width: int,
    row_height: int,
) -> int:
    """Width of the row label prefix (num, abbrev, monitor eye slot)."""
    eye_slot_w = visibility_icon_slot_width(row_height)
    return layer_num_width + stem_abbrev_width + eye_slot_w


def timeline_live_signature(
    state: TimelineViewState,
    *,
    playhead_px: int,
    bar_left: int,
    bar_width: int,
    row_count: int,
    row_h: int,
    flash_sig: tuple = (),
    ticks_ms: int | None = None,
) -> tuple:
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    rec_flash = rec_flash_visible(ticks_ms) if state.recording else None
    return (
        playhead_px,
        bar_left,
        bar_width,
        row_count,
        row_h,
        transport_time_text(state.position_sec),
        rec_flash,
        playhead_flash_bright(ticks_ms),
        flash_sig,
    )


@dataclass(frozen=True)
class _TimelineLayout:
    panel_w: int
    panel_h: int
    panel_x: int
    panel_y: int
    row_count: int
    row_h: int
    bar_left: int
    bar_width: int
    eye_slot_w: int
    timeline_eye_x: int
    layer_num_width: int
    stem_abbrev_width: int
    badge_reserve: int
    bar_top: int
    bar_bottom: int


@dataclass(frozen=True)
class ComposedTimelinePanel:
    upload_surface: pygame.Surface
    panel_size: tuple[int, int]
    screen_rect: tuple[int, int, int, int]
    upload_plan: UploadPlan
    upload_signature: UploadSignature
    capacity: tuple[int, int]


class TimelineOverlay:
    """Bottom-anchored timeline panel drawn over the composited frame."""

    def __init__(
        self,
        *,
        margin: int | None = None,
        font_size: int | None = None,
        padding: int | None = None,
        row_gap: int | None = None,
    ) -> None:
        metrics = timeline_ui_metrics()
        if margin is None:
            margin = metrics.margin
        if font_size is None:
            font_size = metrics.font_size
        if padding is None:
            padding = metrics.padding
        if row_gap is None:
            row_gap = metrics.row_gap
        self._margin = margin
        self._font_size = font_size
        self._padding = padding
        self._row_gap = row_gap
        self._font: pygame.font.Font | None = None
        self._panel_rect: tuple[int, int, int, int] | None = None
        self._header_badge_rect: tuple[int, int, int, int] | None = None
        self._layer_num_width: int = 0
        self._stem_abbrev_width: int = 0
        self._bar_layout: tuple[int, int, int] | None = None
        self._row_layout: list[tuple[int, int, int, int, str, int]] = []
        self._cache = TimelinePanelCache()
        self._visibility = 1.0
        self._upload_scratch: pygame.Surface | None = None
        self._blit_src: tuple[int, int] = (0, 0)

    def _font_get(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", self._font_size)
        return self._font

    @property
    def gpu_state(self):
        return self._cache.gpu

    @property
    def panel_rect(self) -> tuple[int, int, int, int] | None:
        return self._panel_rect

    @property
    def header_badge_rect(self) -> tuple[int, int, int, int] | None:
        return self._header_badge_rect

    @property
    def bar_layout(self) -> tuple[int, int, int] | None:
        """Last draw bar metrics: ``(bar_left, bar_width, eye_slot_w)`` in panel coordinates."""
        return self._bar_layout

    @property
    def row_layout(self) -> list[tuple[int, int, int, int, str, int]]:
        """Last draw layout: ``(row_index, x, y, w, h, stem)`` in panel coordinates."""
        return list(self._row_layout)

    def _compute_layout(
        self,
        state: TimelineViewState,
        *,
        viewport_width: int,
        viewport_height: int,
    ) -> _TimelineLayout | None:
        row_count = len(state.layer_z_order)
        if row_count == 0:
            return None

        metrics = timeline_ui_metrics()
        row_h = metrics.row_height
        panel_w = viewport_width - self._margin * 2
        panel_h = timeline_panel_height_px(row_count)
        panel_x = self._margin
        panel_y = viewport_height - panel_h - self._margin
        badge_reserve = timeline_badge_reserve_px(font_size=self._font_size)

        font = self._font_get()
        num_sample = font.render(layer_num_prefix(max(row_count, 1)), True, LABEL)
        abbrev_sample = font.render(stem_abbrev_label("drums"), True, LABEL)
        layer_num_width = num_sample.get_width()
        stem_abbrev_width = abbrev_sample.get_width()
        eye_slot_w = visibility_icon_slot_width(row_h)
        prefix_width = row_prefix_width(layer_num_width, stem_abbrev_width, row_h)
        bar_left = self._padding + prefix_width
        bar_width = max(1, panel_w - self._padding * 2 - prefix_width - eye_slot_w)
        timeline_eye_x = panel_w - self._padding - eye_slot_w
        bar_top = self._padding
        bar_bottom = self._padding + row_count * row_h + (row_count - 1) * self._row_gap

        self._layer_num_width = layer_num_width
        self._stem_abbrev_width = stem_abbrev_width
        self._bar_layout = (bar_left, bar_width, eye_slot_w)

        return _TimelineLayout(
            panel_w=panel_w,
            panel_h=panel_h,
            panel_x=panel_x,
            panel_y=panel_y,
            row_count=row_count,
            row_h=row_h,
            bar_left=bar_left,
            bar_width=bar_width,
            eye_slot_w=eye_slot_w,
            timeline_eye_x=timeline_eye_x,
            layer_num_width=layer_num_width,
            stem_abbrev_width=stem_abbrev_width,
            badge_reserve=badge_reserve,
            bar_top=bar_top,
            bar_bottom=bar_bottom,
        )

    def _build_static_panel(
        self,
        state: TimelineViewState,
        layout: _TimelineLayout,
    ) -> pygame.Surface:
        panel_w = layout.panel_w
        panel_h = layout.panel_h
        row_count = layout.row_count
        row_h = layout.row_h
        bar_left = layout.bar_left
        bar_width = layout.bar_width
        timeline_eye_x = layout.timeline_eye_x

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((*BACKGROUND, BACKGROUND_ALPHA))
        font = self._font_get()
        self._row_layout = []

        if state.show_bar_grid and state.bar_grid_times:
            for t in state.bar_grid_times:
                grid_x = time_to_x(t, bar_left, bar_width, state.duration_sec)
                pygame.draw.line(
                    panel,
                    BAR_GRID,
                    (grid_x, layout.bar_top),
                    (grid_x, layout.bar_bottom - 1),
                    1,
                )

        for display_i in range(row_count):
            row_index = display_i
            slot = state.layer_z_order[row_index]
            stem_source = state.slot_stems.get(slot, slot)
            row_y = self._padding + display_i * (row_h + self._row_gap)
            row_rect = pygame.Rect(self._padding, row_y, panel_w - self._padding * 2, row_h)
            bar_rect = pygame.Rect(
                bar_left,
                row_y + BAR_VERTICAL_INSET,
                bar_width,
                max(1, row_h - BAR_VERTICAL_INSET * 2),
            )
            armed = slot in state.armed_slots
            focused = state.submenu_focused and row_index == state.focus_row

            self._row_layout.append(
                (row_index, row_rect.x, row_rect.y, row_rect.w, row_rect.h, slot)
            )

            layer_num = row_index + 1
            layer_num_x = self._padding
            stem_abbrev_x = layer_num_x + layout.layer_num_width
            monitor_eye_x = stem_abbrev_x + layout.stem_abbrev_width

            if focused:
                blit_tint(panel, row_rect, HIGHLIGHT)

            abbrev_rect = pygame.Rect(
                stem_abbrev_x, row_y, layout.stem_abbrev_width, row_h
            )
            # Armed abbrev background and recording monitor flash are live-patched.

            if focused or armed:
                label_color = HIGHLIGHT
            else:
                label_color = LABEL
            num_surf = font.render(layer_num_prefix(layer_num), True, label_color)
            abbrev_surf = font.render(stem_abbrev_label(stem_source), True, label_color)
            num_y = row_y + max(0, (row_h - num_surf.get_height()) // 2)
            abbrev_y = row_y + max(0, (row_h - abbrev_surf.get_height()) // 2)
            panel.blit(num_surf, (layer_num_x, num_y))
            panel.blit(abbrev_surf, (stem_abbrev_x, abbrev_y))

            monitor_enabled = state.monitor_visible.get(slot, True)
            timeline_enabled = state.timeline_visible.get(slot, True)
            monitor_override = (
                slot in state.override_slots
                and not (state.recording and armed)
            )
            if not (state.recording and armed):
                monitor_icon = render_visibility_icon(
                    enabled=monitor_enabled,
                    override=monitor_override,
                    line_height=row_h,
                )
                panel.blit(monitor_icon, (monitor_eye_x, row_y))
            timeline_icon = render_visibility_icon(
                enabled=timeline_enabled,
                solo=False,
                line_height=row_h,
            )
            panel.blit(timeline_icon, (timeline_eye_x, row_y))

            bar_column_rect = pygame.Rect(bar_left, row_y, bar_width, row_h)
            if focused:
                blit_tint(panel, bar_column_rect, HIGHLIGHT)

            for start_t, end_t, visible in bar_segments_for_row(state, slot):
                x0 = time_to_x(start_t, bar_left, bar_width, state.duration_sec)
                x1 = time_to_x(end_t, bar_left, bar_width, state.duration_sec)
                if x1 <= x0:
                    continue
                color = TIMELINE_BAR_ON if visible else OFF_SEGMENT_COLOR
                seg_rect = pygame.Rect(x0, bar_rect.y, max(1, x1 - x0), bar_rect.h)
                pygame.draw.rect(panel, color, seg_rect)

            for t0, t1, kind in bar_fade_spans_for_row(state, slot):
                _draw_fade_wedge(
                    panel,
                    t0=t0,
                    t1=t1,
                    kind=kind,
                    bar_left=bar_left,
                    bar_width=bar_width,
                    duration_sec=state.duration_sec,
                    bar_rect=bar_rect,
                    color=TIMELINE_BAR_ON,
                )

            for cue_t in bar_tick_times_for_row(state, slot):
                tick_x = time_to_x(cue_t, bar_left, bar_width, state.duration_sec)
                pygame.draw.line(
                    panel,
                    (*LABEL, CUE_TICK_ALPHA),
                    (tick_x, bar_rect.y),
                    (tick_x, bar_rect.bottom - 1),
                    1,
                )

            if focused and BAR_VERTICAL_INSET > 0:
                blit_tint(
                    panel,
                    pygame.Rect(bar_left, row_y, bar_width, BAR_VERTICAL_INSET),
                    HIGHLIGHT,
                )
                blit_tint(
                    panel,
                    pygame.Rect(
                        bar_left,
                        bar_rect.bottom,
                        bar_width,
                        BAR_VERTICAL_INSET,
                    ),
                    HIGHLIGHT,
                )

        for marker_i, marker_t in enumerate(state.song_marker_times):
            marker_x = time_to_x(marker_t, bar_left, bar_width, state.duration_sec)
            selected = marker_i == state.selected_song_marker_index
            pygame.draw.line(
                panel,
                SONG_MARKER_SELECTED if selected else SONG_MARKER,
                (marker_x, layout.bar_top),
                (marker_x, layout.bar_bottom - 1),
                4 if selected else 2,
            )

        if BORDER_WIDTH > 0:
            pygame.draw.rect(
                panel,
                (*BORDER_COLOR, 255),
                panel.get_rect(),
                width=BORDER_WIDTH,
            )
        return panel

    def _row_y(self, display_i: int, row_h: int) -> int:
        return self._padding + display_i * (row_h + self._row_gap)

    def _restore_upload_rect_from_static(
        self,
        upload: pygame.Surface,
        static_panel: pygame.Surface,
        rect: tuple[int, int, int, int],
        *,
        panel_y_offset: int,
    ) -> None:
        x, y, w, h = rect
        panel_y = y - panel_y_offset
        if panel_y < 0 or panel_y >= static_panel.get_height():
            return
        clip_h = min(h, static_panel.get_height() - panel_y)
        if clip_h <= 0:
            return
        source = static_panel.subsurface((x, panel_y, w, clip_h))
        upload.blit(source, (x, y))

    def _draw_row_live_flash(
        self,
        upload: pygame.Surface,
        static_panel: pygame.Surface,
        state: TimelineViewState,
        layout: _TimelineLayout,
        *,
        row_index: int,
        panel_y_offset: int,
    ) -> list[tuple[int, int, int, int]]:
        slot = state.layer_z_order[row_index]
        row_h = layout.row_h
        row_y = self._row_y(row_index, row_h)
        upload_y = panel_y_offset + row_y
        armed = slot in state.armed_slots
        stem_abbrev_x = self._padding + layout.layer_num_width
        monitor_eye_x = stem_abbrev_x + layout.stem_abbrev_width
        eye_slot_w = visibility_icon_slot_width(row_h)
        dirty: list[tuple[int, int, int, int]] = []

        abbrev_rect = (stem_abbrev_x, upload_y, layout.stem_abbrev_width, row_h)
        self._restore_upload_rect_from_static(
            upload,
            static_panel,
            abbrev_rect,
            panel_y_offset=panel_y_offset,
        )
        if armed_abbrev_bg_visible(
            armed=armed,
            recording=state.recording,
            flash_starts=state.arm_flash_start_ms,
            slot=slot,
        ):
            armed_surf = pygame.Surface(
                (layout.stem_abbrev_width, row_h), pygame.SRCALPHA
            )
            armed_surf.fill((*ARMED_BG, ARMED_BG_ALPHA))
            upload.blit(armed_surf, (stem_abbrev_x, upload_y))
            # Red fill is live-patched over the static glyph; redraw so it stays readable.
            stem_source = state.slot_stems.get(slot, slot)
            abbrev_surf = self._font_get().render(
                stem_abbrev_label(stem_source), True, HIGHLIGHT
            )
            abbrev_y = upload_y + max(0, (row_h - abbrev_surf.get_height()) // 2)
            upload.blit(abbrev_surf, (stem_abbrev_x, abbrev_y))
        dirty.append(abbrev_rect)

        monitor_rect = (monitor_eye_x, upload_y, eye_slot_w, row_h)
        self._restore_upload_rect_from_static(
            upload,
            static_panel,
            monitor_rect,
            panel_y_offset=panel_y_offset,
        )
        monitor_enabled = state.monitor_visible.get(slot, True)
        monitor_override = (
            slot in state.override_slots
            and not (state.recording and armed)
        ) or (state.recording and armed and rec_flash_visible())
        monitor_icon = render_visibility_icon(
            enabled=monitor_enabled,
            override=monitor_override,
            line_height=row_h,
        )
        upload.blit(monitor_icon, (monitor_eye_x, upload_y))
        dirty.append(monitor_rect)
        return dirty

    def _live_flash_row_indices(self, state: TimelineViewState) -> tuple[int, ...]:
        indices: list[int] = []
        for row_index, slot in enumerate(state.layer_z_order):
            armed = slot in state.armed_slots
            if arm_abbrev_flash_active(state.arm_flash_start_ms, slot):
                indices.append(row_index)
            elif state.recording and armed:
                indices.append(row_index)
            elif armed and not state.recording:
                indices.append(row_index)
        return tuple(indices)

    def _live_flash_signature(self, state: TimelineViewState) -> tuple:
        parts: list[tuple] = []
        for row_index in self._live_flash_row_indices(state):
            slot = state.layer_z_order[row_index]
            armed = slot in state.armed_slots
            parts.append(
                (
                    slot,
                    armed_abbrev_bg_visible(
                        armed=armed,
                        recording=state.recording,
                        flash_starts=state.arm_flash_start_ms,
                        slot=slot,
                    ),
                    (
                        (slot in state.override_slots and not (state.recording and armed))
                        or (state.recording and armed and rec_flash_visible())
                    ),
                )
            )
        return tuple(parts)

    def _playhead_strip_rect(
        self,
        layout: _TimelineLayout,
        playhead_px: int,
        *,
        y_offset: int,
    ) -> tuple[int, int, int, int]:
        playhead_left = max(
            layout.bar_left,
            min(layout.bar_left + layout.bar_width - 1, playhead_px),
        )
        x = playhead_left - max(1, PLAYHEAD_WIDTH)
        y = y_offset + layout.bar_top
        w = max(1, PLAYHEAD_WIDTH) * 2 + 1
        h = layout.bar_bottom - layout.bar_top
        return (x, y, w, h)

    def _draw_playhead(
        self,
        surface: pygame.Surface,
        layout: _TimelineLayout,
        playhead_px: int,
        *,
        y_offset: int,
    ) -> tuple[int, int, int, int]:
        playhead_left = max(
            layout.bar_left,
            min(layout.bar_left + layout.bar_width - 1, playhead_px),
        )
        y0 = y_offset + layout.bar_top
        y1 = y_offset + layout.bar_bottom - 1
        pygame.draw.line(
            surface,
            playhead_color(),
            (playhead_left, y0),
            (playhead_left, y1),
            PLAYHEAD_WIDTH,
        )
        return self._playhead_strip_rect(layout, playhead_px, y_offset=y_offset)

    def _draw_header_badges_on_surface(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        panel_w: int,
        position_sec: float,
        recording: bool,
        *,
        y_offset: int = 0,
    ) -> tuple[int, int, int, int]:
        time_surf = font.render(transport_time_text(position_sec), True, VALUE)
        time_w = time_surf.get_width() + REC_BADGE_PAD_X * 2
        time_h = time_surf.get_height() + REC_BADGE_PAD_Y * 2

        rec_w = 0
        rec_surf: pygame.Surface | None = None
        if recording:
            rec_surf = font.render("REC", True, VALUE)
            rec_w = rec_surf.get_width() + REC_BADGE_PAD_X * 2

        badge_h = time_h
        gap = REC_TIME_GAP if recording else 0
        total_w = time_w + gap + rec_w
        time_x = panel_w - time_w
        badge_y = y_offset

        pygame.draw.rect(surface, BACKGROUND, (time_x, badge_y, time_w, badge_h))
        surface.blit(
            time_surf,
            (time_x + REC_BADGE_PAD_X, badge_y + REC_BADGE_PAD_Y),
        )

        header_x = time_x
        if recording and rec_surf is not None:
            rec_x = time_x - gap - rec_w
            header_x = rec_x
            if rec_flash_visible():
                pygame.draw.rect(surface, REC_BG, (rec_x, badge_y, rec_w, badge_h))
            surface.blit(
                rec_surf,
                (rec_x + REC_BADGE_PAD_X, badge_y + REC_BADGE_PAD_Y),
            )

        return (header_x, badge_y, total_w, badge_h)

    def _ensure_upload_scratch(
        self,
        upload_w: int,
        upload_h: int,
    ) -> pygame.Surface:
        scratch = self._upload_scratch
        if (
            scratch is not None
            and scratch.get_width() == upload_w
            and scratch.get_height() == upload_h
        ):
            return scratch
        scratch = pygame.Surface((upload_w, upload_h), pygame.SRCALPHA)
        self._upload_scratch = scratch
        return scratch

    def _patch_live_overlay(
        self,
        upload: pygame.Surface,
        static_panel: pygame.Surface,
        state: TimelineViewState,
        layout: _TimelineLayout,
        *,
        playhead_px: int,
        incremental: bool,
    ) -> list[tuple[int, int, int, int]]:
        cache = self._cache
        panel_y_offset = layout.badge_reserve
        font = self._font_get()

        if incremental and cache.last_playhead_rect is not None:
            self._restore_upload_rect_from_static(
                upload,
                static_panel,
                cache.last_playhead_rect,
                panel_y_offset=panel_y_offset,
            )

        playhead_rect = self._draw_playhead(
            upload,
            layout,
            playhead_px,
            y_offset=panel_y_offset,
        )
        cache.last_playhead_rect = playhead_rect

        badge_top = panel_y_offset - layout.badge_reserve
        if incremental and cache.last_badge_rect is not None:
            bx, by, bw, bh = cache.last_badge_rect
            upload.fill((0, 0, 0, 0), (bx, by, bw, bh))

        badge_rect = self._draw_header_badges_on_surface(
            upload,
            font,
            layout.panel_w,
            state.position_sec,
            state.recording,
            y_offset=badge_top,
        )
        cache.last_badge_rect = badge_rect

        flash_dirty: list[tuple[int, int, int, int]] = []
        for row_index in self._live_flash_row_indices(state):
            flash_dirty.extend(
                self._draw_row_live_flash(
                    upload,
                    static_panel,
                    state,
                    layout,
                    row_index=row_index,
                    panel_y_offset=panel_y_offset,
                )
            )
        cache.last_flash_rects = tuple(flash_dirty)
        return flash_dirty

    def compose_panel(
        self,
        state: TimelineViewState,
        *,
        viewport_width: int,
        viewport_height: int,
        visibility: float = 1.0,
    ) -> ComposedTimelinePanel | None:
        self._visibility = visibility
        self._panel_rect = None
        self._header_badge_rect = None
        if visibility <= 0.01:
            return None

        layout = self._compute_layout(
            state,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
        if layout is None:
            return None

        panel_w = layout.panel_w
        panel_h = layout.panel_h
        static_sig = timeline_static_signature(
            state,
            panel_w=panel_w,
            panel_h=panel_h,
            visibility=visibility,
        )
        cache = self._cache
        can_reuse_static = (
            cache.panel is not None
            and cache.static_signature == static_sig
            and cache.panel_size == (panel_w, panel_h)
        )

        if can_reuse_static:
            assert cache.panel is not None
            static_panel = cache.panel
            incremental = True
        else:
            static_panel = self._build_static_panel(state, layout)
            cache.panel = static_panel
            cache.static_signature = static_sig
            cache.panel_size = (panel_w, panel_h)
            cache.last_playhead_rect = None
            cache.last_badge_rect = None
            cache.last_flash_rects = ()
            cache.last_live_signature = None
            incremental = False

        upload_w = panel_w
        upload_h = panel_h + layout.badge_reserve
        upload = self._ensure_upload_scratch(upload_w, upload_h)
        upload.fill((0, 0, 0, 0))
        upload.blit(static_panel, (0, layout.badge_reserve))

        playhead_px = playhead_x(
            state.position_sec,
            layout.bar_left,
            layout.bar_width,
            state.duration_sec,
        )
        prev_playhead = cache.last_playhead_rect
        prev_badge = cache.last_badge_rect
        prev_flash = cache.last_flash_rects
        flash_dirty = self._patch_live_overlay(
            upload,
            static_panel,
            state,
            layout,
            playhead_px=playhead_px,
            incremental=incremental,
        )

        upload_top_y = layout.panel_y - layout.badge_reserve
        screen_bounds = clip_rect_to_bounds(
            (layout.panel_x, upload_top_y, upload_w, upload_h),
            viewport_width,
            viewport_height,
        )
        if screen_bounds is None:
            return None

        sx, sy, sw, sh = screen_bounds
        panel_screen_y = layout.panel_y
        self._panel_rect = clip_rect_to_bounds(
            (layout.panel_x, panel_screen_y, panel_w, panel_h),
            viewport_width,
            viewport_height,
        )
        badge_screen_y = panel_screen_y - layout.badge_reserve
        badge_local = cache.last_badge_rect
        if badge_local is not None:
            bx, by, bw, bh = badge_local
            self._header_badge_rect = clip_rect_to_bounds(
                (layout.panel_x + bx, badge_screen_y + by, bw, bh),
                viewport_width,
                viewport_height,
            )

        capacity = timeline_panel_max_dimensions(
            viewport_width,
            viewport_height,
            margin=self._margin,
        )
        live_sig = timeline_live_signature(
            state,
            playhead_px=playhead_px,
            bar_left=layout.bar_left,
            bar_width=layout.bar_width,
            row_count=layout.row_count,
            row_h=layout.row_h,
            flash_sig=self._live_flash_signature(state),
        )
        upload_signature = timeline_upload_signature(static_sig, screen_bounds, live_sig)

        src_x = sx - layout.panel_x
        src_y = sy - upload_top_y
        if incremental and live_sig == cache.last_live_signature:
            upload_plan = upload_plan_for_signature(
                upload_signature,
                cache.gpu.last_signature,
            )
        elif incremental:
            dirty_rects: list[tuple[int, int, int, int]] = []
            for rect in (
                *prev_flash,
                *flash_dirty,
                prev_playhead,
                cache.last_playhead_rect,
                prev_badge,
                cache.last_badge_rect,
            ):
                if rect is not None:
                    dirty_rects.append(rect)
            upload_plan = upload_plan_for_signature(
                upload_signature,
                cache.gpu.last_signature,
                dirty_rects=clip_dirty_rects(tuple(dirty_rects), upload_w, upload_h),
            )
        else:
            clip_rect = (
                (src_x, src_y, sw, sh)
                if src_x != 0 or src_y != 0 or (sw, sh) != (upload_w, upload_h)
                else ()
            )
            if clip_rect:
                upload_plan = upload_plan_for_signature(
                    upload_signature,
                    cache.gpu.last_signature,
                    dirty_rects=clip_dirty_rects(clip_rect, upload_w, upload_h),
                )
            else:
                upload_plan = upload_plan_for_signature(
                    upload_signature,
                    cache.gpu.last_signature,
                )

        cache.last_live_signature = live_sig
        self._blit_src = (src_x, src_y)

        return ComposedTimelinePanel(
            upload_surface=upload,
            panel_size=(panel_w, panel_h),
            screen_rect=screen_bounds,
            upload_plan=upload_plan,
            upload_signature=upload_signature,
            capacity=capacity,
        )

    def draw(
        self,
        surface: pygame.Surface,
        state: TimelineViewState,
    ) -> None:
        composed = self.compose_panel(
            state,
            viewport_width=surface.get_width(),
            viewport_height=surface.get_height(),
        )
        if composed is None:
            self._panel_rect = None
            self._header_badge_rect = None
            self._bar_layout = None
            self._row_layout = []
            return
        sx, sy, sw, sh = composed.screen_rect
        src_x, src_y = self._blit_src
        surface.blit(composed.upload_surface, (sx, sy), (src_x, src_y, sw, sh))
