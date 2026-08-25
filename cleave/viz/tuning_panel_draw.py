"""Pygame draw path for the live tuning tree panel.

Row typography: LABEL prefixes, VALUE defaults, DISABLED/LOCKED state overrides.
See cleave/viz/theme.py and .cursor/rules/live-tuning-ui.mdc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pygame

from cleave.config_schema.editor import DEFAULT_UI_FADE_SEC
from cleave.viz.row_semantics import (
    row_is_pinned,
)
from cleave.viz.row_present_renderers import (
    TREE_INDENT,
    RowPresentContext,
    action_parameter_label_color,
    compose_surface,
    fit_row_text,
    is_notification_row,
    is_settings_header_row,
    is_transport_row,
    notification_accent,
    notification_elapsed,
    preset_row_prefix_width,
    render_label_value_row,
    render_present_row,
    render_text,
    render_visibility_icon,
    row_bg_color,
    row_has_tree_focus,
    row_indent,
    row_shows_action_enter_hint,
    row_shows_enter_icon,
    row_text,
    row_value_color,
    row_visibility_icon_key,
    track_header_prefix_width,
    tree_branch_prefix_width,
)
from cleave.viz.frame_rate import (
    FPS_DISPLAY_LABEL,
    format_fps_value,
)
from cleave.viz.material_icons import (
    material_font,
)
from cleave.viz.panel_notification import notification_attention
from cleave.viz.ui_tint import draw_opaque_row_background
from cleave.viz.theme import (
    BACKGROUND,
    BACKGROUND_ALPHA,
    BORDER_COLOR,
    BORDER_WIDTH,
    FADE_DURATION_SEC,
    FOCUS_ROW_BG_ALPHA,
    HIGHLIGHT,
    LABEL,
    PANEL_CONTENT_MAX_WIDTH,
    panel_content_max_width_px,
    SCROLLBAR_CONTENT_GAP,
    SCROLLBAR_THUMB,
    SCROLLBAR_TRACK,
    SCROLLBAR_WIDTH,
    VALUE,
    tuning_ui_metrics,
)
from cleave.viz.overlay_profiler import OverlayDrawCounters
from cleave.viz.overlay_upload import (
    OverlayGpuState,
    UploadPlan,
    UploadSignature,
    clip_dirty_rects,
    upload_plan_for_signature,
)
from cleave.viz.tuning_panel_cache import (
    PanelSignature,
    RowRenderEntry,
    RowRenderKey,
    TuningPanelCache,
    ensure_row_surface,
    live_upload_signature,
    panel_signature,
    static_row_keys,
    tuning_upload_signature,
)
from cleave.viz.tuning_view_state import TuningViewState

Anchor = Literal["topleft", "bottomleft"]

# Test-facing aliases for the extracted present-style helpers.
_row_text = row_text
_row_value_color = row_value_color
_row_indent = row_indent
_row_has_tree_focus = row_has_tree_focus
_row_bg_color = row_bg_color
_render_text = render_text
_compose_surface = compose_surface
_render_label_value_row = render_label_value_row
_notification_elapsed = notification_elapsed
_notification_accent = notification_accent
_row_shows_action_enter_hint = row_shows_action_enter_hint
_row_shows_enter_icon = row_shows_enter_icon
_action_parameter_label_color = action_parameter_label_color


def track_sub_rows_visible(state: TuningViewState, slot: str) -> bool:
    return state.tracks[slot].runtime.expanded


@dataclass(frozen=True)
class PanelScrollMetrics:
    scrollable_indices: list[int]
    header_indices: list[int]
    row_stride: int
    scroll_content_h: int
    header_block_h: int
    max_panel_h: int
    natural_h: int
    panel_h: int
    scroll_viewport_h: int
    needs_scroll: bool
    show_scrollbar: bool


HELP_HINT_LABEL = "H - help"


@dataclass(frozen=True)
class PanelHelpHintLayout:
    x: int
    y: int


def panel_help_hint_layout(
    *,
    panel_w: int,
    panel_h: int,
    padding: int,
    line_h: int,
    hint_width: int,
    show_scrollbar: bool,
) -> PanelHelpHintLayout:
    """Bottom-right help CTA; shifts left when the scrollbar column is visible."""
    right_reserve = (
        SCROLLBAR_WIDTH + SCROLLBAR_CONTENT_GAP if show_scrollbar else 0
    )
    return PanelHelpHintLayout(
        x=panel_w - padding - right_reserve - hint_width,
        y=panel_h - padding - line_h,
    )


def bottom_row_highlight_width(
    *,
    panel_w: int,
    padding: int,
    font: pygame.font.Font,
    show_scrollbar: bool,
) -> int:
    """Bottom-row focus tint and text budget: full width minus help and one character."""
    hint_width = font.size(HELP_HINT_LABEL)[0]
    char_w = max(1, font.size("M")[0])
    right_reserve = (
        SCROLLBAR_WIDTH + SCROLLBAR_CONTENT_GAP if show_scrollbar else 0
    )
    hint_x = panel_w - padding - right_reserve - hint_width
    return max(0, hint_x - padding - char_w)


def panel_bottom_row_index(
    *,
    visible_indices: list[int],
    metrics: PanelScrollMetrics,
    scroll_y: int,
    padding: int,
    line_h: int,
    panel_h: int,
) -> int | None:
    """Index of the row drawn on the help-hint line, if any."""
    if not visible_indices:
        return None
    help_y = panel_h - padding - line_h
    if not metrics.needs_scroll:
        return visible_indices[-1]
    scroll_top = padding + metrics.header_block_h
    bottom_index: int | None = None
    for row_index, index in enumerate(metrics.scrollable_indices):
        y = scroll_top + row_index * metrics.row_stride - scroll_y
        if y <= help_y < y + line_h:
            bottom_index = index
    return bottom_index


@dataclass(frozen=True)
class PanelFpsLayout:
    x: int
    y: int


def panel_fps_layout(
    *,
    panel_w: int,
    padding: int,
    text_width: int,
    show_scrollbar: bool,
) -> PanelFpsLayout:
    """Top-right FPS readout in the header region; shifts left for the scrollbar."""
    right_reserve = (
        SCROLLBAR_WIDTH + SCROLLBAR_CONTENT_GAP if show_scrollbar else 0
    )
    return PanelFpsLayout(
        x=panel_w - padding - right_reserve - text_width,
        y=padding,
    )


def fps_display_text_width(font: pygame.font.Font, fps: float) -> int:
    """Width of the two-tone FPS readout (label + value)."""
    return font.size(FPS_DISPLAY_LABEL)[0] + font.size(format_fps_value(fps))[0]


def _render_fps_display(
    font: pygame.font.Font,
    fps: float,
    *,
    counters: OverlayDrawCounters | None = None,
) -> pygame.Surface:
    return _render_label_value_row(
        font,
        prefix=FPS_DISPLAY_LABEL,
        value=format_fps_value(fps),
        value_color=VALUE,
        line_height=font.get_linesize(),
        counters=counters,
    )


def settings_header_highlight_width(
    *,
    panel_w: int,
    padding: int,
    font: pygame.font.Font,
    fps: float,
    show_scrollbar: bool,
) -> int:
    """Settings-header focus tint: full row width minus FPS text and one character."""
    fps_text_width = fps_display_text_width(font, fps)
    char_w = max(1, font.size("M")[0])
    fps_layout = panel_fps_layout(
        panel_w=panel_w,
        padding=padding,
        text_width=fps_text_width,
        show_scrollbar=show_scrollbar,
    )
    return max(0, fps_layout.x - padding - char_w)


def tuning_panel_max_dimensions(
    viewport_w: int,
    viewport_h: int,
    ui_width: int,
    *,
    timeline_panel_open: bool = False,
    margin_y: int,
    padding: int,
    panel_max_width: int | None = None,
    timeline_row_count: int = 0,
) -> tuple[int, int]:
    """Maximum panel width and height for stable GPU texture capacity."""
    del viewport_w  # horizontal placement uses margin_x elsewhere
    max_w = (
        panel_max_width
        if panel_max_width is not None
        else panel_content_max_width_px(ui_width)
    )
    max_panel_w = max_w + padding * 2
    max_panel_h = viewport_h - margin_y * 2
    if timeline_panel_open and timeline_row_count > 0:
        from cleave.viz.timeline_overlay import timeline_viewport_reserve_px

        max_panel_h -= timeline_viewport_reserve_px(timeline_row_count)
    return max_panel_w, max_panel_h


@dataclass(frozen=True)
class ComposedTuningPanel:
    upload_surface: pygame.Surface
    panel_size: tuple[int, int]
    screen_rect: tuple[int, int, int, int]
    upload_plan: UploadPlan
    upload_signature: UploadSignature
    capacity: tuple[int, int]


def scroll_metrics(
    *,
    visible_indices: list[int],
    first_scrollable_visible: int | None,
    line_h: int,
    line_gap: int,
    padding: int,
    header_gap: int,
    max_panel_h: int,
) -> PanelScrollMetrics:
    if first_scrollable_visible is not None:
        split_pos = visible_indices.index(first_scrollable_visible)
        header_indices = visible_indices[:split_pos]
        scrollable_indices = visible_indices[split_pos:]
    else:
        header_indices = list(visible_indices)
        scrollable_indices = []

    row_stride = line_h + line_gap
    n_scroll = len(scrollable_indices)
    scroll_content_h = (
        n_scroll * line_h + max(0, n_scroll - 1) * line_gap if n_scroll else 0
    )

    n_header = len(header_indices)
    header_rows_h = (
        n_header * line_h + max(0, n_header - 1) * line_gap if n_header else 0
    )
    header_block_h = header_rows_h
    if scrollable_indices:
        header_block_h += header_gap

    visible_count = len(visible_indices)
    natural_h = (
        visible_count * line_h
        + max(0, visible_count - 1) * line_gap
        + (header_gap if first_scrollable_visible is not None else 0)
        + padding * 2
    )

    needs_scroll = natural_h > max_panel_h
    if needs_scroll:
        scroll_viewport_h = max(
            0, max_panel_h - padding * 2 - header_block_h
        )
        panel_h = min(natural_h, max_panel_h)
        show_scrollbar = scroll_content_h > scroll_viewport_h
    else:
        scroll_viewport_h = scroll_content_h
        panel_h = natural_h
        show_scrollbar = False

    return PanelScrollMetrics(
        scrollable_indices=scrollable_indices,
        header_indices=header_indices,
        row_stride=row_stride,
        scroll_content_h=scroll_content_h,
        header_block_h=header_block_h,
        max_panel_h=max_panel_h,
        natural_h=natural_h,
        panel_h=panel_h,
        scroll_viewport_h=scroll_viewport_h,
        needs_scroll=needs_scroll,
        show_scrollbar=show_scrollbar,
    )


def panel_content_max_width(
    *,
    index: int,
    scrollable_indices: frozenset[int],
    show_scrollbar: bool,
    panel_max_width: int = PANEL_CONTENT_MAX_WIDTH,
) -> int:
    """Content width budget for a row; scrollable rows reserve the scrollbar column."""
    if show_scrollbar and index in scrollable_indices:
        return panel_max_width - SCROLLBAR_WIDTH
    return panel_max_width


def _transport_icons_width(line_h: int) -> int:
    icon_h = line_h + 1
    bar_w = max(2, (icon_h + 4) // 7)
    inner_gap = max(1, bar_w // 2)
    tri_w = (icon_h * 3) // 4
    slot_w = max(tri_w, 2 * bar_w + inner_gap, bar_w + inner_gap + tri_w)
    gap = max(8, line_h // 2)
    return 3 * slot_w + 2 * gap


def _glyph_icon_width(glyph: str, line_h: int) -> int:
    icon_h = line_h + 1
    return material_font(icon_h).size(glyph)[0]


def _scrollable_row_in_viewport(
    *,
    row_index: int,
    scroll_y: int,
    scroll_top: int,
    scroll_bottom: int,
    row_stride: int,
    line_h: int,
) -> bool:
    local_y = row_index * row_stride
    y = scroll_top + local_y - scroll_y
    return y + line_h > scroll_top and y < scroll_bottom


def clip_rect_to_surface(
    rect: tuple[int, int, int, int],
    surface: pygame.Surface,
) -> tuple[int, int, int, int] | None:
    """Intersection of rect with surface bounds (for subsurface-safe panel_rect)."""
    return clip_rect_to_bounds(rect, surface.get_width(), surface.get_height())


def clip_rect_to_bounds(
    rect: tuple[int, int, int, int],
    bounds_w: int,
    bounds_h: int,
) -> tuple[int, int, int, int] | None:
    """Intersection of rect with a width/height viewport."""
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return None
    left = max(x, 0)
    top = max(y, 0)
    right = min(x + w, bounds_w)
    bottom = min(y + h, bounds_h)
    clip_w = right - left
    clip_h = bottom - top
    if clip_w <= 0 or clip_h <= 0:
        return None
    return (left, top, clip_w, clip_h)


class TuningOverlay:
    """Tree-style live tuning panel; holds visible after input, then fades out."""

    def __init__(
        self,
        *,
        anchor: Anchor = "topleft",
        margin: tuple[int, int] | None = None,
        font_size: int | None = None,
        padding: int | None = None,
        line_gap: int | None = None,
        hold_idle_sec: float | None = None,
    ) -> None:
        metrics = tuning_ui_metrics()
        if margin is None:
            margin = (metrics.margin, metrics.margin)
        if font_size is None:
            font_size = metrics.font_size
        if padding is None:
            padding = metrics.padding
        if line_gap is None:
            line_gap = metrics.line_gap
        self._anchor = anchor
        self._margin = margin
        self._font_size = font_size
        self._padding = padding
        self._line_gap = line_gap
        self._hold_idle_sec = (
            DEFAULT_UI_FADE_SEC if hold_idle_sec is None else max(0.0, hold_idle_sec)
        )
        self._fade_duration_sec = FADE_DURATION_SEC
        self._idle_sec = self._hold_idle_sec + self._fade_duration_sec + 1.0
        self._visibility = 0.0
        self._font: pygame.font.Font | None = None
        self._panel_rect: tuple[int, int, int, int] | None = None
        self._panel_scratch: pygame.Surface | None = None
        self._scroll_y = 0
        self._panel_cache = TuningPanelCache()

    @property
    def gpu_state(self) -> OverlayGpuState:
        return self._panel_cache.gpu

    def _clamp_scroll(self, scroll_content_h: int, viewport_h: int) -> None:
        max_scroll = max(0, scroll_content_h - viewport_h)
        if self._scroll_y < 0:
            self._scroll_y = 0
        elif self._scroll_y > max_scroll:
            self._scroll_y = max_scroll

    def _ensure_focus_visible(
        self,
        state: TuningViewState,
        scrollable_indices: list[int],
        row_stride: int,
        viewport_h: int,
        line_h: int,
    ) -> None:
        try:
            row_index = scrollable_indices.index(state.focus_index)
        except ValueError:
            return
        row_y = row_index * row_stride
        if row_y < self._scroll_y:
            self._scroll_y = row_y
        elif row_y + line_h > self._scroll_y + viewport_h:
            self._scroll_y = row_y + line_h - viewport_h
        n = len(scrollable_indices)
        scroll_content_h = n * row_stride - self._line_gap if n > 0 else 0
        self._clamp_scroll(scroll_content_h, viewport_h)

    def set_hold_idle_sec(self, sec: float) -> None:
        if not isinstance(sec, (int, float)):
            return
        sec = max(0.0, sec)
        was_disabled = self._hold_idle_sec <= 0
        self._hold_idle_sec = sec
        if sec <= 0:
            if self._visibility > 0:
                self._visibility = 1.0
                self._idle_sec = 0.0
        elif was_disabled and self._visibility > 0:
            self._idle_sec = 0.0

    def notify_input(self) -> None:
        self._idle_sec = 0.0
        self._visibility = 1.0

    def hide_immediately(self) -> None:
        self._idle_sec = self._hold_idle_sec + self._fade_duration_sec + 1.0
        self._visibility = 0.0
        self._scroll_y = 0
        self._panel_cache.clear_all()

    def is_visible(self) -> bool:
        return self._visibility > 0.01

    @property
    def visibility(self) -> float:
        return self._visibility

    def update(self, dt_sec: float) -> None:
        hold_idle_sec = self._hold_idle_sec
        if hold_idle_sec <= 0:
            return
        self._idle_sec += dt_sec
        if self._idle_sec <= hold_idle_sec:
            self._visibility = 1.0
        elif self._fade_duration_sec <= 0:
            self._visibility = 0.0
        elif self._idle_sec <= hold_idle_sec + self._fade_duration_sec:
            fade_t = (self._idle_sec - hold_idle_sec) / self._fade_duration_sec
            self._visibility = 1.0 - fade_t
        else:
            self._visibility = 0.0

    def _font_get(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", self._font_size)
        return self._font

    @property
    def panel_rect(self) -> tuple[int, int, int, int] | None:
        """Top-left x, y, width, height of the last drawn panel, if any."""
        return self._panel_rect

    def _ensure_panel_scratch(
        self,
        panel_w: int,
        panel_h: int,
        *,
        counters: OverlayDrawCounters | None = None,
    ) -> pygame.Surface:
        if (
            self._panel_scratch is None
            or self._panel_scratch.get_size() != (panel_w, panel_h)
        ):
            self._panel_scratch = _compose_surface(
                (panel_w, panel_h), counters=counters
            )
        return self._panel_scratch

    def _draw_notification_attention_fill(
        self,
        panel: pygame.Surface,
        *,
        state: TuningViewState,
        index: int,
        row_rect: tuple[int, int, int, int],
    ) -> None:
        desc = state.layout.descriptor(index)
        attention = notification_attention(
            notification_elapsed(state, desc.marker_index)
        )
        if attention.fill_progress <= 0.001:
            return
        x, y, row_w, line_h = row_rect
        if attention.fill_progress >= 0.999:
            fill_w = row_w
        else:
            fill_w = max(1, int(round(row_w * attention.fill_progress)))
        if attention.fill_from_left:
            fill_x = x
        else:
            fill_x = x + max(0, row_w - fill_w)
        accent = notification_accent(desc.marker_index)
        fill_alpha = int(255 * self._visibility)
        if fill_alpha < 2:
            return
        pygame.draw.rect(
            panel,
            (*accent, fill_alpha),
            (fill_x, y, fill_w, line_h),
        )

    def _blit_row(
        self,
        panel: pygame.Surface,
        *,
        state: TuningViewState,
        index: int,
        surf: pygame.Surface,
        time_surf: pygame.Surface | None,
        y: int,
        text_alpha: int,
        panel_w: int,
        line_h: int,
        font: pygame.font.Font | None = None,
        show_scrollbar: bool = False,
        clip_for_help_hint: bool = False,
    ) -> None:
        row_w = panel_w - self._padding * 2
        panel_bg_alpha = int(BACKGROUND_ALPHA * self._visibility)
        bg = _row_bg_color(state, index)
        if clip_for_help_hint and font is not None:
            row_w = bottom_row_highlight_width(
                panel_w=panel_w,
                padding=self._padding,
                font=font,
                show_scrollbar=show_scrollbar,
            )
        elif (
            bg is not None
            and is_settings_header_row(state, index)
            and state.fps is not None
            and font is not None
        ):
            row_w = settings_header_highlight_width(
                panel_w=panel_w,
                padding=self._padding,
                font=font,
                fps=state.fps,
                show_scrollbar=show_scrollbar,
            )
        row_rect = (self._padding, y, row_w, line_h)
        tint_alpha = (
            int(FOCUS_ROW_BG_ALPHA * self._visibility) if bg is not None else 0
        )
        draw_opaque_row_background(
            panel,
            row_rect,
            BACKGROUND,
            panel_bg_alpha,
            bg,
            tint_alpha=tint_alpha,
        )
        if is_notification_row(state, index):
            self._draw_notification_attention_fill(
                panel,
                state=state,
                index=index,
                row_rect=row_rect,
            )

        indent = self._padding + _row_indent(state, index)
        if text_alpha >= 2:
            surf.set_alpha(text_alpha)
            old_clip = panel.get_clip()
            panel.set_clip(pygame.Rect(*row_rect))
            try:
                panel.blit(surf, (indent, y))
                if time_surf is not None:
                    time_surf.set_alpha(text_alpha)
                    panel.blit(time_surf, (indent + surf.get_width(), y))
            finally:
                panel.set_clip(old_clip)

    def _draw_scrollbar(
        self,
        panel: pygame.Surface,
        *,
        panel_w: int,
        scroll_top: int,
        scroll_viewport_h: int,
        scroll_content_h: int,
        border_alpha: int,
    ) -> None:
        if border_alpha < 2:
            return
        track_x = panel_w - SCROLLBAR_WIDTH
        track_y = scroll_top
        track_bottom = track_y + scroll_viewport_h
        track_color = (*SCROLLBAR_TRACK, border_alpha)
        pygame.draw.line(panel, track_color, (track_x, track_y), (track_x, track_bottom))
        pygame.draw.line(
            panel,
            track_color,
            (track_x + SCROLLBAR_WIDTH - 1, track_y),
            (track_x + SCROLLBAR_WIDTH - 1, track_bottom),
        )
        max_scroll = scroll_content_h - scroll_viewport_h
        if max_scroll <= 0:
            return
        thumb_h = max(8, int(scroll_viewport_h * scroll_viewport_h / scroll_content_h))
        thumb_travel = scroll_viewport_h - thumb_h
        thumb_y = track_y + int(self._scroll_y * thumb_travel / max_scroll)
        pygame.draw.rect(
            panel,
            (*SCROLLBAR_THUMB, border_alpha),
            (track_x, thumb_y, SCROLLBAR_WIDTH, thumb_h),
        )

    def _build_row_at_index(
        self,
        font: pygame.font.Font,
        state: TuningViewState,
        index: int,
        *,
        max_content_width: int,
        line_h: int,
        counters: OverlayDrawCounters | None = None,
        cache: TuningPanelCache | None = None,
    ) -> tuple[pygame.Surface, pygame.Surface | None, int]:
        ctx = RowPresentContext(
            font=font,
            state=state,
            index=index,
            padding=self._padding,
            line_h=line_h,
            max_content_width=max_content_width,
            counters=counters,
            cache=cache,
        )
        return render_present_row(ctx)

    def _max_content_width(
        self,
        index: int,
        *,
        scrollable_indices: frozenset[int],
        show_scrollbar: bool,
        panel_max_width: int,
    ) -> int:
        return panel_content_max_width(
            index=index,
            scrollable_indices=scrollable_indices,
            show_scrollbar=show_scrollbar,
            panel_max_width=panel_max_width,
        )

    def _ensure_cache_panel(
        self,
        panel_w: int,
        panel_h: int,
        *,
        counters: OverlayDrawCounters | None = None,
    ) -> pygame.Surface:
        cache = self._panel_cache
        if cache.panel is None or cache.panel.get_size() != (panel_w, panel_h):
            cache.panel = _compose_surface((panel_w, panel_h), counters=counters)
        return cache.panel

    def _transport_row_y(
        self,
        transport_index: int,
        *,
        metrics: PanelScrollMetrics,
        visible_indices: list[int],
        first_scrollable_visible: int | None,
    ) -> int:
        if metrics.needs_scroll:
            try:
                header_pos = metrics.header_indices.index(transport_index)
            except ValueError:
                return self._padding
            return self._padding + header_pos * metrics.row_stride
        row_y = self._padding
        for index in visible_indices:
            if index == first_scrollable_visible:
                row_y += metrics.row_stride
            if index == transport_index:
                return row_y
            row_y += metrics.row_stride
        return self._padding

    def _patch_live_panel_rows(
        self,
        panel: pygame.Surface,
        state: TuningViewState,
        *,
        font: pygame.font.Font,
        metrics: PanelScrollMetrics,
        visible_indices: list[int],
        first_scrollable_visible: int | None,
        transport_index: int,
        transport_entry: RowRenderEntry,
        panel_w: int,
        line_h: int,
        text_alpha: int,
        counters: OverlayDrawCounters | None = None,
    ) -> None:
        cache = self._panel_cache
        bg_alpha = int(BACKGROUND_ALPHA * self._visibility)
        transport_y = self._transport_row_y(
            transport_index,
            metrics=metrics,
            visible_indices=visible_indices,
            first_scrollable_visible=first_scrollable_visible,
        )
        cache.last_transport_rect = (
            BORDER_WIDTH,
            transport_y,
            panel_w - 2 * BORDER_WIDTH,
            line_h,
        )
        if bg_alpha >= 2:
            pygame.draw.rect(
                panel,
                (*BACKGROUND, bg_alpha),
                (
                    BORDER_WIDTH,
                    transport_y,
                    panel_w - 2 * BORDER_WIDTH,
                    line_h,
                ),
            )
        self._blit_row(
            panel,
            state=state,
            index=transport_index,
            surf=transport_entry.primary,
            time_surf=transport_entry.secondary,
            y=transport_y,
            text_alpha=text_alpha,
            panel_w=panel_w,
            line_h=line_h,
        )

        if state.fps is not None and text_alpha >= 2:
            if cache.last_fps_rect is not None and bg_alpha >= 2:
                pygame.draw.rect(panel, (*BACKGROUND, bg_alpha), cache.last_fps_rect)
            fps_surf = _render_fps_display(font, state.fps, counters=counters)
            fps_surf.set_alpha(text_alpha)
            fps_layout = panel_fps_layout(
                panel_w=panel_w,
                padding=self._padding,
                text_width=fps_surf.get_width(),
                show_scrollbar=metrics.show_scrollbar,
            )
            panel.blit(fps_surf, (fps_layout.x, fps_layout.y))
            cache.last_fps_rect = (
                fps_layout.x,
                fps_layout.y,
                fps_surf.get_width(),
                fps_surf.get_height(),
            )

    def _composite_panel_rows(
        self,
        panel: pygame.Surface,
        state: TuningViewState,
        built_rows: dict[int, RowRenderEntry],
        *,
        font: pygame.font.Font,
        metrics: PanelScrollMetrics,
        visible_indices: list[int],
        first_scrollable_visible: int | None,
        panel_w: int,
        panel_h: int,
        line_h: int,
        text_alpha: int,
        header_gap: int,
    ) -> None:
        bottom_index = panel_bottom_row_index(
            visible_indices=visible_indices,
            metrics=metrics,
            scroll_y=self._scroll_y,
            padding=self._padding,
            line_h=line_h,
            panel_h=panel_h,
        )
        if metrics.needs_scroll:
            header_y = self._padding
            for row_index, index in enumerate(metrics.header_indices):
                y = header_y + row_index * metrics.row_stride
                entry = built_rows[index]
                self._blit_row(
                    panel,
                    state=state,
                    index=index,
                    surf=entry.primary,
                    time_surf=entry.secondary,
                    y=y,
                    text_alpha=text_alpha,
                    panel_w=panel_w,
                    line_h=line_h,
                    font=font,
                    show_scrollbar=metrics.show_scrollbar,
                    clip_for_help_hint=index == bottom_index,
                )

            scroll_top = self._padding + metrics.header_block_h
            scroll_bottom = scroll_top + metrics.scroll_viewport_h
            old_clip = panel.get_clip()
            clip_right_reserve = (
                SCROLLBAR_WIDTH + SCROLLBAR_CONTENT_GAP
                if metrics.show_scrollbar
                else self._padding
            )
            clip_w = panel_w - self._padding - clip_right_reserve
            panel.set_clip(
                pygame.Rect(self._padding, scroll_top, clip_w, metrics.scroll_viewport_h)
            )
            for row_index, index in enumerate(metrics.scrollable_indices):
                local_y = row_index * metrics.row_stride
                y = scroll_top + local_y - self._scroll_y
                if y + line_h <= scroll_top or y >= scroll_bottom:
                    continue
                entry = built_rows[index]
                self._blit_row(
                    panel,
                    state=state,
                    index=index,
                    surf=entry.primary,
                    time_surf=entry.secondary,
                    y=y,
                    text_alpha=text_alpha,
                    panel_w=panel_w,
                    line_h=line_h,
                    font=font,
                    show_scrollbar=metrics.show_scrollbar,
                    clip_for_help_hint=index == bottom_index,
                )
            panel.set_clip(old_clip)

            if metrics.show_scrollbar:
                self._draw_scrollbar(
                    panel,
                    panel_w=panel_w,
                    scroll_top=scroll_top,
                    scroll_viewport_h=metrics.scroll_viewport_h,
                    scroll_content_h=metrics.scroll_content_h,
                    border_alpha=int(255 * self._visibility),
                )
        else:
            row_y = self._padding
            for index in visible_indices:
                if index == first_scrollable_visible:
                    row_y += header_gap
                entry = built_rows[index]
                self._blit_row(
                    panel,
                    state=state,
                    index=index,
                    surf=entry.primary,
                    time_surf=entry.secondary,
                    y=row_y,
                    text_alpha=text_alpha,
                    panel_w=panel_w,
                    line_h=line_h,
                    font=font,
                    show_scrollbar=metrics.show_scrollbar,
                    clip_for_help_hint=index == bottom_index,
                )
                row_y += line_h + self._line_gap

    def _draw_panel_chrome(
        self,
        panel: pygame.Surface,
        state: TuningViewState,
        *,
        font: pygame.font.Font,
        metrics: PanelScrollMetrics,
        panel_w: int,
        panel_h: int,
        line_h: int,
        text_alpha: int,
        counters: OverlayDrawCounters | None,
        draw_fps: bool,
    ) -> None:
        cache = self._panel_cache
        if draw_fps and state.fps is not None and text_alpha >= 2:
            fps_surf = _render_fps_display(font, state.fps, counters=counters)
            fps_surf.set_alpha(text_alpha)
            fps_layout = panel_fps_layout(
                panel_w=panel_w,
                padding=self._padding,
                text_width=fps_surf.get_width(),
                show_scrollbar=metrics.show_scrollbar,
            )
            panel.blit(fps_surf, (fps_layout.x, fps_layout.y))
            cache.last_fps_rect = (
                fps_layout.x,
                fps_layout.y,
                fps_surf.get_width(),
                fps_surf.get_height(),
            )
        elif not draw_fps:
            cache.last_fps_rect = None

        if text_alpha >= 2:
            help_hint = _render_text(
                font, HELP_HINT_LABEL, True, LABEL, counters=counters
            )
            help_hint.set_alpha(text_alpha)
            hint_layout = panel_help_hint_layout(
                panel_w=panel_w,
                panel_h=panel_h,
                padding=self._padding,
                line_h=line_h,
                hint_width=help_hint.get_width(),
                show_scrollbar=metrics.show_scrollbar,
            )
            panel.blit(help_hint, (hint_layout.x, hint_layout.y))

        border_alpha = int(255 * self._visibility)
        if border_alpha >= 2 and BORDER_WIDTH > 0:
            pygame.draw.rect(
                panel,
                (*BORDER_COLOR, border_alpha),
                panel.get_rect(),
                width=BORDER_WIDTH,
            )

    def compose_panel(
        self,
        state: TuningViewState,
        *,
        viewport_width: int,
        viewport_height: int,
        timeline_panel_open: bool = False,
        counters: OverlayDrawCounters | None = None,
    ) -> ComposedTuningPanel | None:
        self._panel_rect = None
        if self._visibility <= 0.01 or len(state.layout) == 0:
            return None

        font = self._font_get()
        line_h = font.get_linesize()
        frame = state.layout_frame
        if frame is not None:
            visible_indices = list(frame.visible_indices)
        else:
            visible_indices = state.layout.visible_indices(state)
        first_scrollable_visible = next(
            (
                index
                for index in visible_indices
                if not row_is_pinned(state.layout.kind(index))
            ),
            None,
        )
        header_gap = line_h + self._line_gap
        _, margin_y = self._margin
        panel_max_width = panel_content_max_width_px(state.settings.ui_width)
        capacity = tuning_panel_max_dimensions(
            viewport_width,
            viewport_height,
            state.settings.ui_width,
            timeline_panel_open=timeline_panel_open,
            margin_y=margin_y,
            padding=self._padding,
            panel_max_width=panel_max_width,
            timeline_row_count=len(state.layer_z_order),
        )
        max_panel_h = capacity[1]
        metrics = scroll_metrics(
            visible_indices=visible_indices,
            first_scrollable_visible=first_scrollable_visible,
            line_h=line_h,
            line_gap=self._line_gap,
            padding=self._padding,
            header_gap=header_gap,
            max_panel_h=max_panel_h,
        )
        if metrics.needs_scroll:
            self._ensure_focus_visible(
                state,
                metrics.scrollable_indices,
                metrics.row_stride,
                metrics.scroll_viewport_h,
                line_h,
            )
            scroll_top = self._padding + metrics.header_block_h
            scroll_bottom = scroll_top + metrics.scroll_viewport_h
            raster_indices: set[int] = set(metrics.header_indices)
            for row_index, index in enumerate(metrics.scrollable_indices):
                if _scrollable_row_in_viewport(
                    row_index=row_index,
                    scroll_y=self._scroll_y,
                    scroll_top=scroll_top,
                    scroll_bottom=scroll_bottom,
                    row_stride=metrics.row_stride,
                    line_h=line_h,
                ):
                    raster_indices.add(index)
        else:
            raster_indices = set(visible_indices)

        scrollable_indices = frozenset(metrics.scrollable_indices)
        panel_max_width = panel_content_max_width_px(state.settings.ui_width)
        vis_tuple = tuple(visible_indices)
        # Stable order matching layout; viewport rows only for the static signature.
        raster_tuple = tuple(i for i in vis_tuple if i in raster_indices)
        cache = self._panel_cache
        structure_changed = cache.row_cache_structure != vis_tuple
        if structure_changed:
            # Content-keyed surfaces stay valid across expand/collapse; prune
            # unused entries after the full compose below instead of clear_rows().
            cache.row_cache_structure = vis_tuple

        def max_content_width_for(index: int) -> int:
            return self._max_content_width(
                index,
                scrollable_indices=scrollable_indices,
                show_scrollbar=metrics.show_scrollbar,
                panel_max_width=panel_max_width,
            )

        static_keys = static_row_keys(
            state,
            font=font,
            cache=cache,
            indices=raster_tuple,
            max_content_width_for_index=max_content_width_for,
            line_h=line_h,
        )

        panel_h = metrics.panel_h
        prev_sig = cache.panel_signature
        prev_size = cache.panel_size
        candidate_w = (
            prev_size[0]
            if prev_size is not None
            else panel_max_width + self._padding * 2
        )
        new_sig = panel_signature(
            state,
            visibility=self._visibility,
            panel_w=candidate_w,
            panel_h=panel_h,
            scroll_y=self._scroll_y,
            timeline_panel_open=timeline_panel_open,
            static_row_keys=static_keys,
        )
        can_incremental = (
            cache.panel is not None
            and prev_sig is not None
            and prev_size is not None
            and new_sig == prev_sig
            and prev_size[1] == panel_h
        )

        transport_index = next(
            (
                index
                for index in visible_indices
                if is_transport_row(state, index)
            ),
            None,
        )

        if can_incremental:
            assert cache.panel is not None
            assert transport_index is not None
            panel = cache.panel
            panel_w = prev_size[0]
            text_alpha = int(255 * self._visibility)
            transport_entry = ensure_row_surface(
                cache,
                state,
                transport_index,
                font,
                self._build_row_at_index,
                max_content_width=max_content_width_for(transport_index),
                line_h=line_h,
                counters=counters,
            )
            self._patch_live_panel_rows(
                panel,
                state,
                font=font,
                metrics=metrics,
                visible_indices=visible_indices,
                first_scrollable_visible=first_scrollable_visible,
                transport_index=transport_index,
                transport_entry=transport_entry,
                panel_w=panel_w,
                line_h=line_h,
                text_alpha=text_alpha,
                counters=counters,
            )
            self._panel_scratch = panel
            placement = self._finish_compose_panel(
                panel_w=panel_w,
                panel_h=panel_h,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
            )
            if placement is None:
                return None
            assert prev_sig is not None
            return self._build_composed_panel(
                panel,
                panel_sig=prev_sig,
                panel_size=(panel_w, panel_h),
                placement=placement,
                state=state,
                capacity=capacity,
                incremental=True,
            )

        built_rows: dict[int, RowRenderEntry] = {}
        row_widths: list[int] = []
        used_row_keys: set[RowRenderKey] = set()
        # Width from viewport rows only; off-screen estimates are skipped.
        for index in raster_tuple:
            max_content_width = max_content_width_for(index)
            entry = ensure_row_surface(
                cache,
                state,
                index,
                font,
                self._build_row_at_index,
                max_content_width=max_content_width,
                line_h=line_h,
                counters=counters,
                used_keys=used_row_keys,
            )
            built_rows[index] = entry
            row_widths.append(entry.content_width)

        content_w = max(row_widths) if row_widths else 0
        if state.settings.ui_width_mode == "fixed":
            content_w = panel_max_width
        else:
            # Path rows are fitted to panel_max already. Allow natural
            # action-parameter chrome (e.g. editor-mode confirm) to widen past
            # the configured max, still capped by the viewport.
            margin_x, _ = self._margin
            viewport_content_max = max(
                panel_max_width,
                viewport_width - margin_x * 2 - self._padding * 2,
            )
            content_w = min(content_w, viewport_content_max)
        panel_w = content_w + self._padding * 2
        if panel_w > capacity[0]:
            capacity = (panel_w, capacity[1])

        bottom_index = panel_bottom_row_index(
            visible_indices=visible_indices,
            metrics=metrics,
            scroll_y=self._scroll_y,
            padding=self._padding,
            line_h=line_h,
            panel_h=panel_h,
        )
        if bottom_index is not None and bottom_index in raster_indices:
            bottom_max = bottom_row_highlight_width(
                panel_w=panel_w,
                padding=self._padding,
                font=font,
                show_scrollbar=metrics.show_scrollbar,
            )
            if bottom_max != max_content_width_for(bottom_index):
                built_rows[bottom_index] = ensure_row_surface(
                    cache,
                    state,
                    bottom_index,
                    font,
                    self._build_row_at_index,
                    max_content_width=bottom_max,
                    line_h=line_h,
                    counters=counters,
                    used_keys=used_row_keys,
                )

        if structure_changed:
            cache.retain_row_surfaces(used_row_keys)

        alpha = int(BACKGROUND_ALPHA * self._visibility)
        if alpha < 2:
            return None

        new_sig = panel_signature(
            state,
            visibility=self._visibility,
            panel_w=panel_w,
            panel_h=panel_h,
            scroll_y=self._scroll_y,
            timeline_panel_open=timeline_panel_open,
            static_row_keys=static_keys,
        )

        panel = self._ensure_cache_panel(panel_w, panel_h, counters=counters)
        panel.fill((*BACKGROUND, alpha))

        text_alpha = int(255 * self._visibility)

        self._composite_panel_rows(
            panel,
            state,
            built_rows,
            font=font,
            metrics=metrics,
            visible_indices=visible_indices,
            first_scrollable_visible=first_scrollable_visible,
            panel_w=panel_w,
            panel_h=panel_h,
            line_h=line_h,
            text_alpha=text_alpha,
            header_gap=header_gap,
        )

        self._draw_panel_chrome(
            panel,
            state,
            font=font,
            metrics=metrics,
            panel_w=panel_w,
            panel_h=panel_h,
            line_h=line_h,
            text_alpha=text_alpha,
            counters=counters,
            draw_fps=True,
        )

        cache.panel_signature = new_sig
        cache.panel_size = (panel_w, panel_h)
        self._set_transport_rect_cache(
            transport_index,
            metrics=metrics,
            visible_indices=visible_indices,
            first_scrollable_visible=first_scrollable_visible,
            panel_w=panel_w,
            line_h=line_h,
        )
        self._panel_scratch = panel

        placement = self._finish_compose_panel(
            panel_w=panel_w,
            panel_h=panel_h,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
        if placement is None:
            return None
        return self._build_composed_panel(
            panel,
            panel_sig=new_sig,
            panel_size=(panel_w, panel_h),
            placement=placement,
            state=state,
            capacity=capacity,
            incremental=False,
        )

    def _set_transport_rect_cache(
        self,
        transport_index: int | None,
        *,
        metrics: PanelScrollMetrics,
        visible_indices: list[int],
        first_scrollable_visible: int | None,
        panel_w: int,
        line_h: int,
    ) -> None:
        if transport_index is None:
            self._panel_cache.last_transport_rect = None
            return
        transport_y = self._transport_row_y(
            transport_index,
            metrics=metrics,
            visible_indices=visible_indices,
            first_scrollable_visible=first_scrollable_visible,
        )
        self._panel_cache.last_transport_rect = (
            BORDER_WIDTH,
            transport_y,
            panel_w - 2 * BORDER_WIDTH,
            line_h,
        )

    def _build_composed_panel(
        self,
        panel: pygame.Surface,
        *,
        panel_sig: PanelSignature,
        panel_size: tuple[int, int],
        placement: tuple[tuple[int, int, int, int], tuple[int, int]],
        state: TuningViewState,
        capacity: tuple[int, int],
        incremental: bool,
    ) -> ComposedTuningPanel:
        cache = self._panel_cache
        screen_rect, src_offset = placement
        live_sig = live_upload_signature(state)
        upload_signature = tuning_upload_signature(panel_sig, screen_rect, live_sig)
        panel_w, panel_h = panel_size
        src_x, src_y = src_offset
        active_w, active_h = screen_rect[2], screen_rect[3]

        if incremental and live_sig == cache.last_live_signature:
            upload_plan = upload_plan_for_signature(
                upload_signature,
                cache.gpu.last_signature,
            )
        elif incremental:
            dirty_rects: list[tuple[int, int, int, int]] = []
            if cache.last_transport_rect is not None:
                dirty_rects.append(cache.last_transport_rect)
            if cache.last_fps_rect is not None and state.fps is not None:
                dirty_rects.append(cache.last_fps_rect)
            upload_plan = upload_plan_for_signature(
                upload_signature,
                cache.gpu.last_signature,
                dirty_rects=clip_dirty_rects(tuple(dirty_rects), panel_w, panel_h),
            )
        else:
            cache.last_live_signature = None
            clip_rect = (
                (src_x, src_y, active_w, active_h)
                if src_x != 0 or src_y != 0 or (active_w, active_h) != (panel_w, panel_h)
                else ()
            )
            if clip_rect:
                upload_plan = upload_plan_for_signature(
                    upload_signature,
                    cache.gpu.last_signature,
                    dirty_rects=clip_dirty_rects(clip_rect, panel_w, panel_h),
                )
            else:
                upload_plan = upload_plan_for_signature(
                    upload_signature,
                    cache.gpu.last_signature,
                )

        cache.last_live_signature = live_sig
        return ComposedTuningPanel(
            upload_surface=panel,
            panel_size=panel_size,
            screen_rect=screen_rect,
            upload_plan=upload_plan,
            upload_signature=upload_signature,
            capacity=capacity,
        )

    def _finish_compose_panel(
        self,
        *,
        panel_w: int,
        panel_h: int,
        viewport_width: int,
        viewport_height: int,
    ) -> tuple[tuple[int, int, int, int], tuple[int, int]] | None:
        mx, my = self._margin
        if self._anchor == "topleft":
            pos = (mx, my)
        else:
            pos = (mx, viewport_height - panel_h - my)

        bounds = clip_rect_to_bounds(
            (pos[0], pos[1], panel_w, panel_h),
            viewport_width,
            viewport_height,
        )
        if bounds is None:
            return None
        self._panel_rect = bounds
        src_x = bounds[0] - pos[0]
        src_y = bounds[1] - pos[1]
        return bounds, (src_x, src_y)

    def draw(
        self,
        surface: pygame.Surface,
        state: TuningViewState,
        *,
        timeline_panel_open: bool = False,
        counters: OverlayDrawCounters | None = None,
    ) -> None:
        composed = self.compose_panel(
            state,
            viewport_width=surface.get_width(),
            viewport_height=surface.get_height(),
            timeline_panel_open=timeline_panel_open,
            counters=counters,
        )
        if composed is None:
            self._panel_rect = None
            return
        panel = self._panel_scratch
        assert panel is not None
        mx, my = self._margin
        if self._anchor == "topleft":
            blit_pos = (mx, my)
        else:
            blit_pos = (mx, surface.get_height() - panel.get_height() - my)
        surface.blit(panel, blit_pos)
