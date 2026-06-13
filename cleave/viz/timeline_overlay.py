"""Bottom timeline strip overlay for per-stem layer visibility cues."""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from cleave.timeline import TimelineCue, layer_visible_at, stem_abbreviation
from cleave.viz.material_icons import visibility_icon_slot_width
from cleave.viz.overlay import _clip_rect_to_surface, render_visibility_icon
from cleave.viz.theme import (
    ARMED_BG,
    BACKGROUND,
    BACKGROUND_ALPHA,
    BORDER_COLOR,
    BORDER_WIDTH,
    HIGHLIGHT,
    LABEL,
    REC_BG,
    TIMELINE_FOCUS_BG,
    VALUE,
)

PANEL_HEIGHT_FRACTION: float = 0.2
OFF_SEGMENT_COLOR: tuple[int, int, int] = (40, 40, 40)
FOCUS_BG_ALPHA: int = 160
ARMED_BG_ALPHA: int = 220
CUE_TICK_ALPHA: int = 120
PLAYHEAD_WIDTH: int = 2
REC_BADGE_GAP: int = 4
REC_BADGE_PAD_X: int = 8
REC_BADGE_PAD_Y: int = 4
REC_FLASH_MS: int = 500


@dataclass
class TimelineViewState:
    layer_z_order: list[str]
    cues: list[TimelineCue]
    defaults: dict[str, bool]
    position_sec: float
    duration_sec: float
    focus_row: int  # 0..3, bottom stem first
    armed_stems: set[str] = field(default_factory=set)
    recording: bool = False
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
            if stem in cue.layers and 0.0 <= cue.t <= duration_sec
        }
    )


def _rec_flash_visible() -> bool:
    return (pygame.time.get_ticks() // REC_FLASH_MS) % 2 == 0


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


def stem_label_text(stem: str) -> str:
    return f" {stem_abbreviation(stem)} "


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
        self._rec_badge_rect: tuple[int, int, int, int] | None = None
        self._stem_label_width: int = 0
        self._row_layout: list[tuple[int, int, int, int, str, int]] = []

    def _font_get(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", self._font_size)
        return self._font

    @property
    def panel_rect(self) -> tuple[int, int, int, int] | None:
        return self._panel_rect

    @property
    def rec_badge_rect(self) -> tuple[int, int, int, int] | None:
        return self._rec_badge_rect

    @property
    def row_layout(self) -> list[tuple[int, int, int, int, str, int]]:
        """Last draw layout: ``(row_index, x, y, w, h, stem)`` in panel coordinates."""
        return list(self._row_layout)

    def draw(self, surface: pygame.Surface, state: TimelineViewState) -> None:
        self._panel_rect = None
        self._rec_badge_rect = None
        self._row_layout = []
        if not state.enabled:
            return

        width, height = surface.get_size()
        panel_w = width - self._margin * 2
        panel_h = max(1, int(height * PANEL_HEIGHT_FRACTION))
        panel_x = self._margin
        panel_y = height - panel_h - self._margin

        font = self._font_get()
        label_sample = font.render(stem_label_text("drums"), True, LABEL)
        self._stem_label_width = label_sample.get_width()
        row_count = len(state.layer_z_order)
        if row_count == 0:
            return

        inner_h = panel_h - self._padding * 2
        row_h = max(1, (inner_h - self._row_gap * (row_count - 1)) // row_count)
        eye_slot_w = visibility_icon_slot_width(row_h)
        prefix_width = self._stem_label_width + eye_slot_w
        bar_left = self._padding + prefix_width
        bar_width = max(1, panel_w - self._padding * 2 - prefix_width)

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((*BACKGROUND, BACKGROUND_ALPHA))

        playhead_px = playhead_x(
            state.position_sec, bar_left, bar_width, state.duration_sec
        )

        for display_i in range(row_count):
            row_index = row_count - 1 - display_i
            stem = state.layer_z_order[row_index]
            row_y = self._padding + display_i * (row_h + self._row_gap)
            row_rect = pygame.Rect(self._padding, row_y, panel_w - self._padding * 2, row_h)
            bar_rect = pygame.Rect(bar_left, row_y, bar_width, row_h)
            armed = stem in state.armed_stems
            focused = row_index == state.focus_row

            self._row_layout.append(
                (row_index, row_rect.x, row_rect.y, row_rect.w, row_rect.h, stem)
            )

            if focused:
                focus_surf = pygame.Surface((row_rect.w, row_rect.h), pygame.SRCALPHA)
                focus_surf.fill((*TIMELINE_FOCUS_BG, FOCUS_BG_ALPHA))
                panel.blit(focus_surf, row_rect.topleft)

            label_rect = pygame.Rect(self._padding, row_y, self._stem_label_width, row_h)
            if armed:
                armed_surf = pygame.Surface((label_rect.w, label_rect.h), pygame.SRCALPHA)
                armed_surf.fill((*ARMED_BG, ARMED_BG_ALPHA))
                panel.blit(armed_surf, label_rect.topleft)

            label = stem_label_text(stem)
            label_color = VALUE if (armed or focused) else LABEL
            label_surf = font.render(label, True, label_color)
            label_y = row_y + max(0, (row_h - label_surf.get_height()) // 2)
            panel.blit(label_surf, (self._padding, label_y))

            visible_now = layer_visible_at(
                state.cues, state.defaults, stem, state.position_sec
            )
            icon_surf = render_visibility_icon(
                enabled=visible_now, solo=False, line_height=row_h
            )
            panel.blit(icon_surf, (self._padding + self._stem_label_width, row_y))

            for start_t, end_t, visible in visibility_segments(
                state.cues, state.defaults, stem, state.duration_sec
            ):
                x0 = time_to_x(start_t, bar_left, bar_width, state.duration_sec)
                x1 = time_to_x(end_t, bar_left, bar_width, state.duration_sec)
                if x1 <= x0:
                    continue
                color = VALUE if visible else OFF_SEGMENT_COLOR
                seg_rect = pygame.Rect(x0, bar_rect.y, max(1, x1 - x0), bar_rect.h)
                pygame.draw.rect(panel, color, seg_rect)

            for cue_t in cue_times_for_stem(state.cues, stem, state.duration_sec):
                tick_x = time_to_x(cue_t, bar_left, bar_width, state.duration_sec)
                pygame.draw.line(
                    panel,
                    (*LABEL, CUE_TICK_ALPHA),
                    (tick_x, bar_rect.y),
                    (tick_x, bar_rect.bottom - 1),
                    1,
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

        if state.recording:
            self._rec_badge_rect = self._draw_rec_badge(
                surface, font, panel_x, panel_y, panel_w
            )

    def _draw_rec_badge(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        panel_x: int,
        panel_y: int,
        panel_w: int,
    ) -> tuple[int, int, int, int]:
        text_surf = font.render("REC", True, VALUE)
        badge_w = text_surf.get_width() + REC_BADGE_PAD_X * 2
        badge_h = text_surf.get_height() + REC_BADGE_PAD_Y * 2
        badge_x = panel_x + panel_w - badge_w
        badge_y = panel_y - REC_BADGE_GAP - badge_h
        badge_rect = (badge_x, badge_y, badge_w, badge_h)
        if _rec_flash_visible():
            pygame.draw.rect(surface, REC_BG, badge_rect)
            surface.blit(
                text_surf,
                (badge_x + REC_BADGE_PAD_X, badge_y + REC_BADGE_PAD_Y),
            )
        return _clip_rect_to_surface(badge_rect, surface)
