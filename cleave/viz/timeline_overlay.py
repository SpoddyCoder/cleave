"""Bottom timeline strip overlay for per-stem layer visibility cues."""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from cleave.timeline import TimelineCue, layer_visible_at, stem_abbreviation
from cleave.viz.material_icons import visibility_icon_slot_width
from cleave.viz.overlay import _clip_rect_to_surface, render_visibility_icon
from cleave.viz.playback import format_mmss
from cleave.viz.theme import (
    ARMED_BG,
    BACKGROUND,
    BACKGROUND_ALPHA,
    BORDER_COLOR,
    BORDER_WIDTH,
    FOCUS_ROW_BG_ALPHA,
    HIGHLIGHT,
    LABEL,
    REC_BG,
    VALUE,
)

PANEL_HEIGHT_FRACTION: float = 0.2
OFF_SEGMENT_COLOR: tuple[int, int, int] = (40, 40, 40)
BAR_VERTICAL_INSET: int = 3
ARMED_BG_ALPHA: int = 220
CUE_TICK_ALPHA: int = 120
PLAYHEAD_WIDTH: int = 2
REC_BADGE_GAP: int = 4
REC_BADGE_PAD_X: int = 8
REC_BADGE_PAD_Y: int = 4
REC_TIME_GAP: int = 2
REC_FLASH_MS: int = 500


def _blit_focus_tint(panel: pygame.Surface, rect: pygame.Rect) -> None:
    if rect.w <= 0 or rect.h <= 0:
        return
    surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    surf.fill((*HIGHLIGHT, FOCUS_ROW_BG_ALPHA))
    panel.blit(surf, rect.topleft)


@dataclass
class TimelineViewState:
    layer_z_order: list[str]
    cues: list[TimelineCue]
    defaults: dict[str, bool]
    position_sec: float
    duration_sec: float
    focus_row: int  # 0..3, index into layer_z_order (0 = bottom stem)
    monitor_visible: dict[str, bool]
    timeline_visible: dict[str, bool]
    override_stems: set[str] = field(default_factory=set)
    armed_stems: set[str] = field(default_factory=set)
    recording: bool = False
    record_start_sec: float | None = None
    record_baseline: dict[str, bool] = field(default_factory=dict)
    record_buffer: list[TimelineCue] = field(default_factory=list)
    enabled: bool = False


def visibility_segments(
    cues: list[TimelineCue],
    defaults: dict[str, bool],
    stem: str,
    duration_sec: float,
) -> list[tuple[float, float, bool]]:
    """Return ``(start_t, end_t, visible)`` segments for *stem* over ``[0, duration_sec]``."""
    if duration_sec <= 0:
        return []
    boundaries = sorted({0.0, duration_sec} | {cue.t for cue in cues})
    segments: list[tuple[float, float, bool]] = []
    for index in range(len(boundaries) - 1):
        start_t = boundaries[index]
        end_t = boundaries[index + 1]
        if end_t <= start_t:
            continue
        visible = layer_visible_at(cues, defaults, stem, start_t)
        segments.append((start_t, end_t, visible))
    return segments


def unique_cue_times(cues: list[TimelineCue], duration_sec: float) -> list[float]:
    return sorted({cue.t for cue in cues if 0.0 <= cue.t <= duration_sec})


def cue_times_for_stem(
    cues: list[TimelineCue],
    stem: str,
    duration_sec: float,
) -> list[float]:
    """Cue times that change visibility for *stem* within ``[0, duration_sec]``."""
    return sorted(
        {
            cue.t
            for cue in cues
            if (
                stem in cue.layers
                and cue.show_tick
                and 0.0 <= cue.t <= duration_sec
            )
        }
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
    stem: str,
) -> list[tuple[float, float, bool]]:
    """Visibility segments for one timeline row, including live record preview."""
    duration = state.duration_sec
    if duration <= 0:
        return []
    if not (state.recording and stem in state.armed_stems):
        return visibility_segments(state.cues, state.defaults, stem, duration)

    record_start = state.record_start_sec
    if record_start is None:
        record_start = state.position_sec
    record_start = max(0.0, min(record_start, duration))
    playhead = max(0.0, min(state.position_sec, duration))

    segments: list[tuple[float, float, bool]] = []
    committed = visibility_segments(state.cues, state.defaults, stem, duration)

    if record_start > 0.0:
        segments.extend(_clip_segments(committed, 0.0, record_start))

    if playhead > record_start:
        armed_defaults = dict(state.defaults)
        armed_defaults.update(state.record_baseline)
        segments.extend(
            _clip_segments(
                visibility_segments(
                    state.record_buffer, armed_defaults, stem, playhead
                ),
                record_start,
                playhead,
            )
        )

    if playhead < duration:
        segments.extend(_clip_segments(committed, playhead, duration))
    return segments


def bar_tick_times_for_row(state: TimelineViewState, stem: str) -> list[float]:
    """Cue tick times for one timeline row."""
    duration = state.duration_sec
    if not (state.recording and stem in state.armed_stems):
        return cue_times_for_stem(state.cues, stem, duration)

    record_start = state.record_start_sec
    if record_start is None:
        record_start = state.position_sec
    playhead = state.position_sec
    committed_ticks = [
        t
        for t in cue_times_for_stem(state.cues, stem, duration)
        if t < record_start or t > playhead
    ]
    live_ticks = [
        t
        for t in cue_times_for_stem(state.record_buffer, stem, duration)
        if record_start <= t <= playhead
    ]
    return sorted(set(committed_ticks) | set(live_ticks))


def rec_flash_visible(ticks_ms: int | None = None) -> bool:
    if ticks_ms is None:
        ticks_ms = pygame.time.get_ticks()
    return (ticks_ms // REC_FLASH_MS) % 2 == 0


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


class TimelineOverlay:
    """Bottom-anchored timeline panel drawn over the composited frame."""

    def __init__(
        self,
        *,
        margin: int = 10,
        font_size: int = 14,
        padding: int = 8,
        row_gap: int = 2,
    ) -> None:
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

    def _font_get(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", self._font_size)
        return self._font

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

    def draw(self, surface: pygame.Surface, state: TimelineViewState) -> None:
        self._panel_rect = None
        self._header_badge_rect = None
        self._bar_layout = None
        self._row_layout = []
        if not state.enabled:
            return

        width, height = surface.get_size()
        panel_w = width - self._margin * 2
        panel_h = max(1, int(height * PANEL_HEIGHT_FRACTION))
        panel_x = self._margin
        panel_y = height - panel_h - self._margin

        font = self._font_get()
        num_sample = font.render(layer_num_prefix(4), True, LABEL)
        abbrev_sample = font.render(stem_abbrev_label("drums"), True, LABEL)
        self._layer_num_width = num_sample.get_width()
        self._stem_abbrev_width = abbrev_sample.get_width()
        row_count = len(state.layer_z_order)
        if row_count == 0:
            return

        inner_h = panel_h - self._padding * 2
        row_h = max(1, (inner_h - self._row_gap * (row_count - 1)) // row_count)
        eye_slot_w = visibility_icon_slot_width(row_h)
        prefix_width = row_prefix_width(
            self._layer_num_width, self._stem_abbrev_width, row_h
        )
        bar_left = self._padding + prefix_width
        bar_width = max(1, panel_w - self._padding * 2 - prefix_width - eye_slot_w)
        self._bar_layout = (bar_left, bar_width, eye_slot_w)
        timeline_eye_x = panel_w - self._padding - eye_slot_w

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((*BACKGROUND, BACKGROUND_ALPHA))

        playhead_px = playhead_x(
            state.position_sec, bar_left, bar_width, state.duration_sec
        )

        for display_i in range(row_count):
            row_index = display_i
            stem = state.layer_z_order[row_index]
            row_y = self._padding + display_i * (row_h + self._row_gap)
            row_rect = pygame.Rect(self._padding, row_y, panel_w - self._padding * 2, row_h)
            bar_rect = pygame.Rect(
                bar_left,
                row_y + BAR_VERTICAL_INSET,
                bar_width,
                max(1, row_h - BAR_VERTICAL_INSET * 2),
            )
            armed = stem in state.armed_stems
            focused = row_index == state.focus_row

            self._row_layout.append(
                (row_index, row_rect.x, row_rect.y, row_rect.w, row_rect.h, stem)
            )

            layer_num = row_index + 1
            layer_num_x = self._padding
            stem_abbrev_x = layer_num_x + self._layer_num_width
            monitor_eye_x = stem_abbrev_x + self._stem_abbrev_width

            if focused:
                _blit_focus_tint(panel, row_rect)

            abbrev_rect = pygame.Rect(
                stem_abbrev_x, row_y, self._stem_abbrev_width, row_h
            )
            if armed and (not state.recording or rec_flash_visible()):
                armed_surf = pygame.Surface((abbrev_rect.w, abbrev_rect.h), pygame.SRCALPHA)
                armed_surf.fill((*ARMED_BG, ARMED_BG_ALPHA))
                panel.blit(armed_surf, abbrev_rect.topleft)

            if focused:
                label_color = HIGHLIGHT
            elif armed:
                label_color = VALUE
            else:
                label_color = LABEL
            num_surf = font.render(layer_num_prefix(layer_num), True, label_color)
            abbrev_surf = font.render(stem_abbrev_label(stem), True, label_color)
            num_y = row_y + max(0, (row_h - num_surf.get_height()) // 2)
            abbrev_y = row_y + max(0, (row_h - abbrev_surf.get_height()) // 2)
            panel.blit(num_surf, (layer_num_x, num_y))
            panel.blit(abbrev_surf, (stem_abbrev_x, abbrev_y))

            monitor_enabled = state.monitor_visible.get(stem, True)
            timeline_enabled = state.timeline_visible.get(stem, True)
            monitor_override = stem in state.override_stems or (
                state.recording and armed and rec_flash_visible()
            )
            monitor_icon = render_visibility_icon(
                enabled=monitor_enabled,
                override=monitor_override,
                line_height=row_h,
            )
            timeline_icon = render_visibility_icon(
                enabled=timeline_enabled,
                solo=False,
                line_height=row_h,
            )
            panel.blit(monitor_icon, (monitor_eye_x, row_y))
            panel.blit(timeline_icon, (timeline_eye_x, row_y))

            bar_column_rect = pygame.Rect(bar_left, row_y, bar_width, row_h)
            if focused:
                _blit_focus_tint(panel, bar_column_rect)

            for start_t, end_t, visible in bar_segments_for_row(state, stem):
                x0 = time_to_x(start_t, bar_left, bar_width, state.duration_sec)
                x1 = time_to_x(end_t, bar_left, bar_width, state.duration_sec)
                if x1 <= x0:
                    continue
                color = VALUE if visible else OFF_SEGMENT_COLOR
                seg_rect = pygame.Rect(x0, bar_rect.y, max(1, x1 - x0), bar_rect.h)
                pygame.draw.rect(panel, color, seg_rect)

            for cue_t in bar_tick_times_for_row(state, stem):
                tick_x = time_to_x(cue_t, bar_left, bar_width, state.duration_sec)
                pygame.draw.line(
                    panel,
                    (*LABEL, CUE_TICK_ALPHA),
                    (tick_x, bar_rect.y),
                    (tick_x, bar_rect.bottom - 1),
                    1,
                )

            if focused and BAR_VERTICAL_INSET > 0:
                _blit_focus_tint(
                    panel,
                    pygame.Rect(bar_left, row_y, bar_width, BAR_VERTICAL_INSET),
                )
                _blit_focus_tint(
                    panel,
                    pygame.Rect(
                        bar_left,
                        bar_rect.bottom,
                        bar_width,
                        BAR_VERTICAL_INSET,
                    ),
                )

        bar_top = self._padding
        bar_bottom = self._padding + row_count * row_h + (row_count - 1) * self._row_gap
        playhead_left = max(bar_left, min(bar_left + bar_width - 1, playhead_px))
        pygame.draw.line(
            panel,
            HIGHLIGHT,
            (playhead_left, bar_top),
            (playhead_left, bar_bottom - 1),
            PLAYHEAD_WIDTH,
        )

        if BORDER_WIDTH > 0:
            pygame.draw.rect(
                panel,
                (*BORDER_COLOR, 255),
                panel.get_rect(),
                width=BORDER_WIDTH,
            )

        surface.blit(panel, (panel_x, panel_y))
        self._panel_rect = _clip_rect_to_surface(
            (panel_x, panel_y, panel_w, panel_h),
            surface,
        )

        self._header_badge_rect = self._draw_header_badges(
            surface,
            font,
            panel_x,
            panel_y,
            panel_w,
            state.position_sec,
            state.recording,
        )

    def _draw_header_badges(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        panel_x: int,
        panel_y: int,
        panel_w: int,
        position_sec: float,
        recording: bool,
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
        time_x = panel_x + panel_w - time_w
        badge_y = panel_y - REC_BADGE_GAP - badge_h

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

        return _clip_rect_to_surface((header_x, badge_y, total_w, badge_h), surface)
