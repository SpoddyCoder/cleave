"""Bottom timeline strip overlay for per-stem layer visibility cues."""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from cleave.timeline import TimelineCue, layer_visible_at, stem_abbreviation
from cleave.viz.overlay import _clip_rect_to_surface
from cleave.viz.theme import (
    ARMED_BG,
    BACKGROUND,
    BACKGROUND_ALPHA,
    BORDER_COLOR,
    BORDER_WIDTH,
    HIGHLIGHT,
    LABEL,
    VALUE,
)

PANEL_HEIGHT_FRACTION: float = 0.2
OFF_SEGMENT_COLOR: tuple[int, int, int] = (40, 40, 40)
FOCUS_BG_ALPHA: int = 50
ARMED_BG_ALPHA: int = 200
CUE_TICK_ALPHA: int = 120
PLAYHEAD_WIDTH: int = 2


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
        self._label_width: int = 0
        self._row_layout: list[tuple[int, int, int, int, str, int]] = []

    def _font_get(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", self._font_size)
        return self._font

    @property
    def panel_rect(self) -> tuple[int, int, int, int] | None:
        return self._panel_rect

    @property
    def row_layout(self) -> list[tuple[int, int, int, int, str, int]]:
        """Last draw layout: ``(row_index, x, y, w, h, stem)`` in panel coordinates."""
        return list(self._row_layout)

    def draw(self, surface: pygame.Surface, state: TimelineViewState) -> None:
        self._panel_rect = None
        self._row_layout = []
        if not state.enabled:
            return

        width, height = surface.get_size()
        panel_w = width - self._margin * 2
        panel_h = max(1, int(height * PANEL_HEIGHT_FRACTION))
        panel_x = self._margin
        panel_y = height - panel_h - self._margin

        font = self._font_get()
        label_sample = font.render("O: ", True, LABEL)
        self._label_width = label_sample.get_width()
        row_count = len(state.layer_z_order)
        if row_count == 0:
            return

        inner_h = panel_h - self._padding * 2
        row_h = max(1, (inner_h - self._row_gap * (row_count - 1)) // row_count)
        bar_left = self._padding + self._label_width
        bar_width = max(1, panel_w - self._padding * 2 - self._label_width)

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((*BACKGROUND, BACKGROUND_ALPHA))

        cue_times = unique_cue_times(state.cues, state.duration_sec)
        playhead_px = playhead_x(
            state.position_sec, bar_left, bar_width, state.duration_sec
        )

        for display_i in range(row_count):
            row_index = row_count - 1 - display_i
            stem = state.layer_z_order[row_index]
            row_y = self._padding + display_i * (row_h + self._row_gap)
            row_rect = pygame.Rect(self._padding, row_y, panel_w - self._padding * 2, row_h)
            bar_rect = pygame.Rect(bar_left, row_y, bar_width, row_h)

            self._row_layout.append(
                (row_index, row_rect.x, row_rect.y, row_rect.w, row_rect.h, stem)
            )

            if stem in state.armed_stems:
                armed_surf = pygame.Surface((row_rect.w, row_rect.h), pygame.SRCALPHA)
                armed_surf.fill((*ARMED_BG, ARMED_BG_ALPHA))
                panel.blit(armed_surf, row_rect.topleft)
            elif row_index == state.focus_row:
                focus_surf = pygame.Surface((row_rect.w, row_rect.h), pygame.SRCALPHA)
                focus_surf.fill((*HIGHLIGHT, FOCUS_BG_ALPHA))
                panel.blit(focus_surf, row_rect.topleft)

            label = f"{stem_abbreviation(stem)}: "
            label_surf = font.render(label, True, LABEL)
            label_y = row_y + max(0, (row_h - label_surf.get_height()) // 2)
            panel.blit(label_surf, (self._padding, label_y))

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

            for cue_t in cue_times:
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

        if state.recording:
            rec_surf = font.render("REC", True, HIGHLIGHT)
            panel.blit(rec_surf, (panel_w - self._padding - rec_surf.get_width(), self._padding))

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
