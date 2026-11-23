"""Timeline strip static panel: rows, level bars, cue ticks, clip outlines, scrollbar.

Each row names on its clips the presets its layer plays; rows on a timer also
mark where their presets change.

Drawn once per change of the static signature and cached; the live layer
(playhead, flashes, transport, role glyphs) is patched over it each frame.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pygame

from cleave.viz.preset_schedule import RowLabel, RowPresets, row_labels
from cleave.viz.material_icons import RECORD_GLYPH, REPLAY_GLYPH, SOLO_GLYPH
from cleave.viz.overlay_primitives import overlay_panel_surface
from cleave.viz.row_present_renderers import (
    render_header_toggle,
    render_visibility_icon,
)
from cleave.viz.theme import palette, timeline_ui_metrics
from cleave.viz.text_fit import fit_text_to_width
from cleave.timeline import LEVEL_EPS
from cleave.viz.timeline_ruler import render_time_ruler, song_bound_xs
from cleave.viz.timeline_strip_layout import (
    StripLayout,
    clip_bar_span,
    layer_num_prefix,
    scrollbar_thumb_span,
    stem_abbrev_label,
    time_in_view,
    time_to_x,
)
from cleave.viz.timeline_strip_state import (
    TimelineViewState,
    bar_cues_for_row,
    bar_level_breakpoints_for_row,
    row_clips_for_view,
    view_window,
)
from cleave.viz.row_paint import RowState, row_bar_px, row_look
from cleave.viz.ui_tint import blit_hover, blit_row_band, draw_row_edge

# Dim end of the level-bar colour ramp sits this far from off toward the
# track colour (quarter beds stay readable).
_BAR_LEVEL_DIM_MIX: float = 0.4
CUE_TICK_ALPHA: int = 120
CUE_TICK_WIDTH: int = 2
# A join where the next clip continues the preset, and a timer row's preset
# changes, draw fainter and thinner than a clip boundary.
SOFT_TICK_ALPHA: int = 55
SOFT_TICK_WIDTH: int = 1
# Preset name on a clip: inset from the clip's start, past the
# trim handle, and from its end.
CLIP_LABEL_INSET: int = 5
# A clip narrower than this many pixels shows no name.
CLIP_LABEL_MIN_PX: int = 18
# Outline around the selected clip; thicker while the selection flash runs.
SELECTED_CLIP_OUTLINE_WIDTH: int = 2
# Trim handles at the edges of the hovered or selected clip.
CLIP_HANDLE_WIDTH: int = 3

# The focused strip row, as a focused navigator or inspector row.
_FOCUSED_LOOK = row_look(RowState.FOCUSED)

# One entry per row: (row_index, x, y, w, h, slot) in panel coordinates.
RowLayoutEntry = tuple[int, int, int, int, int, str]


def _lerp_rgb(
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    u = max(0.0, min(1.0, float(t)))
    return (
        int(round(a[0] + (b[0] - a[0]) * u)),
        int(round(a[1] + (b[1] - a[1]) * u)),
        int(round(a[2] + (b[2] - a[2]) * u)),
    )


def track_color(row_index: int) -> tuple[int, int, int]:
    """On-section colour of the timeline track at *row_index*."""
    return palette().timeline_track_colors[row_index % len(palette().timeline_track_colors)]


def bar_level_y(bar_rect: pygame.Rect, level: float) -> int:
    """Y of the top of a bottom-filled level within ``bar_rect``."""
    filled = max(0.0, min(1.0, float(level))) * bar_rect.h
    return bar_rect.bottom - int(round(filled))


def _draw_level_bar(
    panel: pygame.Surface,
    *,
    breakpoints: list[tuple[float, float]],
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
    bar_rect: pygame.Rect,
    on_color: tuple[int, int, int],
) -> None:
    pygame.draw.rect(panel, palette().timeline_off_segment, bar_rect)
    if view_end_sec <= view_start_sec or len(breakpoints) < 2:
        return
    dim_color = _lerp_rgb(palette().timeline_off_segment, on_color, _BAR_LEVEL_DIM_MIX)
    # Polygon fills include their vertices; Rect.bottom/right are exclusive.
    bottom = bar_rect.bottom - 1
    right = bar_rect.right - 1
    for index in range(len(breakpoints) - 1):
        t0, level0 = breakpoints[index]
        t1, level1 = breakpoints[index + 1]
        if t1 <= t0 or t1 <= view_start_sec or t0 >= view_end_sec:
            continue
        # Cut a segment that crosses a window edge at that edge.
        slope = (level1 - level0) / (t1 - t0)
        if t1 > view_end_sec:
            level1 = level0 + slope * (view_end_sec - t0)
            t1 = view_end_sec
        if t0 < view_start_sec:
            level0 = level0 + slope * (view_start_sec - t0)
            t0 = view_start_sec
        x0 = time_to_x(t0, bar_left, bar_width, view_start_sec, view_end_sec)
        x1 = min(
            time_to_x(t1, bar_left, bar_width, view_start_sec, view_end_sec), right
        )
        if x1 <= x0:
            continue
        if level0 <= LEVEL_EPS and level1 <= LEVEL_EPS:
            continue
        y0 = min(bar_level_y(bar_rect, level0), bottom)
        y1 = min(bar_level_y(bar_rect, level1), bottom)
        mean_level = 0.5 * (level0 + level1)
        color = _lerp_rgb(dim_color, on_color, mean_level)
        pygame.draw.polygon(
            panel,
            color,
            [(x0, y0), (x1, y1), (x1, bottom), (x0, bottom)],
        )


def header_rest_color(hovered: bool, *, blocked: bool = False) -> tuple[int, int, int]:
    """An unlit header button: muted, nudge on hover, disabled when blocked."""
    if blocked:
        return palette().disabled
    return palette().icon_hover_fg if hovered else palette().muted


def _draw_tick(
    panel: pygame.Surface,
    x: int,
    bar_rect: pygame.Rect,
    *,
    alpha: int,
    width: int,
) -> None:
    pygame.draw.line(
        panel,
        (*palette().label, alpha),
        (x, bar_rect.y),
        (x, bar_rect.bottom - 1),
        width,
    )


def _draw_clip_label(
    panel: pygame.Surface,
    font: pygame.font.Font,
    label: RowLabel,
    *,
    bar_rect: pygame.Rect,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
) -> None:
    clip = label.clip
    span = clip_bar_span(
        replace(clip, start=label.start, end=label.end),
        bar_left=bar_left,
        bar_width=bar_width,
        view_start_sec=view_start_sec,
        view_end_sec=view_end_sec,
    )
    if span is None:
        return
    left, right = span
    room = right - left - 2 * CLIP_LABEL_INSET
    text = label.text
    if not text or right - left < CLIP_LABEL_MIN_PX or room <= 0:
        return
    # The name sits on the clip's own colour, so it only shows where the
    # level bar is tall enough to hold a line of text.
    filled_h = int(round(max(0.0, min(1.0, float(clip.level))) * bar_rect.h))
    line_h = font.get_height()
    if filled_h < line_h:
        return
    fitted = fit_text_to_width(font, text, room)
    if not fitted:
        return
    color = (
        palette().button_danger_bg if label.empty else palette().timeline_clip_text
    )
    surf = font.render(fitted, True, color)
    top = bar_rect.bottom - filled_h
    panel.blit(surf, (left + CLIP_LABEL_INSET, top + (filled_h - line_h) // 2))


def build_static_panel(
    state: TimelineViewState,
    layout: StripLayout,
    font: pygame.font.Font,
) -> tuple[pygame.Surface, list[RowLayoutEntry]]:
    """The cached panel under the live layer, and where each row sits on it."""
    panel_w = layout.panel_w
    panel_h = layout.panel_h
    row_count = layout.row_count
    row_h = layout.row_h
    bar_left = layout.bar_left
    bar_width = layout.bar_width

    view_start, view_end = view_window(state)

    panel = overlay_panel_surface((panel_w, panel_h))
    row_layout: list[RowLayoutEntry] = []

    if state.show_bar_grid and state.bar_grid_times:
        for t in state.bar_grid_times:
            if not time_in_view(t, view_start, view_end):
                continue
            grid_x = time_to_x(t, bar_left, bar_width, view_start, view_end)
            pygame.draw.line(
                panel,
                palette().bar_grid,
                (grid_x, layout.bar_top),
                (grid_x, layout.bar_bottom - 1),
                1,
            )

    for display_i in range(row_count):
        row_index = display_i
        slot = state.layer_z_order[row_index]
        stem_source = state.slot_stems.get(slot, slot)
        row_y = layout.row_y(display_i)
        icon_y = layout.icon_y(row_y)
        row_rect = layout.row_rect(row_y)
        bar_rect = layout.bar_rect(row_y)
        armed = slot in state.armed_slots
        focused = state.submenu_focused and row_index == state.focus_row

        row_layout.append(
            (row_index, row_rect.x, row_rect.y, row_rect.w, row_rect.h, slot)
        )

        layer_num = row_index + 1
        layer_num_x = layout.padding
        stem_abbrev_x = layer_num_x + layout.layer_num_width
        hover_target = (
            state.hover_row_target[0]
            if state.hover_row_target is not None
            and state.hover_row_target[1] == row_index
            else None
        )

        if focused:
            blit_row_band(panel, row_rect, _FOCUSED_LOOK, bar_px=int(row_bar_px()))
        # Shell hover washes a header button that is drawn: not the label
        # (it only selects) or the empty back-to-timeline slot.
        if hover_target in ("arm", "solo", "eye") or (
            hover_target == "release" and slot in state.override_slots
        ):
            blit_hover(panel, layout.header_button_rect(hover_target, row_y))

        if focused:
            label_color = palette().value
        elif armed:
            label_color = palette().highlight
        else:
            label_color = palette().label
        num_surf = font.render(layer_num_prefix(layer_num), True, label_color)
        abbrev_surf = font.render(stem_abbrev_label(stem_source), True, label_color)
        num_y = row_y + max(0, (row_h - num_surf.get_height()) // 2)
        abbrev_y = row_y + max(0, (row_h - abbrev_surf.get_height()) // 2)
        panel.blit(num_surf, (layer_num_x, num_y))
        panel.blit(abbrev_surf, (stem_abbrev_x, abbrev_y))

        # The lit arm button and the recording eye are live-patched.
        panel.blit(
            render_header_toggle(
                RECORD_GLYPH,
                color=header_rest_color(
                    hover_target == "arm", blocked=state.locked
                ),
                line_height=layout.icon_h,
            ),
            (layout.header_button_x("arm"), icon_y),
        )
        solo = state.solo_slot == slot
        panel.blit(
            render_header_toggle(
                SOLO_GLYPH,
                color=palette().on_lit_icon if solo else header_rest_color(
                    hover_target == "solo"
                ),
                bg=palette().solo_bg if solo else None,
                line_height=layout.icon_h,
            ),
            (layout.header_button_x("solo"), icon_y),
        )
        if not (state.recording and armed):
            panel.blit(
                render_visibility_icon(
                    enabled=state.monitor_visible.get(slot, True),
                    override=slot in state.override_slots,
                    line_height=layout.icon_h,
                ),
                (layout.header_button_x("eye"), icon_y),
            )
        if slot in state.override_slots:
            panel.blit(
                render_header_toggle(
                    REPLAY_GLYPH,
                    color=palette().override_glyph,
                    bg=palette().override_bg,
                    line_height=layout.icon_h,
                ),
                (layout.header_button_x("release"), icon_y),
            )

        _draw_level_bar(
            panel,
            breakpoints=bar_level_breakpoints_for_row(state, slot),
            bar_left=bar_left,
            bar_width=bar_width,
            view_start_sec=view_start,
            view_end_sec=view_end,
            bar_rect=bar_rect,
            on_color=track_color(row_index),
        )

        row_clips = row_clips_for_view(state, slot)
        labels = row_labels(
            row_clips,
            state.presets.get(slot, RowPresets()),
            timeline_enabled=state.enabled,
        )
        soft_starts = {label.start for label in labels if label.soft}
        cue_times = [cue.t for cue in bar_cues_for_row(state, slot)]
        # Cue ticks mark every clip boundary, so butted clips show a divider;
        # timer changes inside a clip are marked too.
        ticks = {t: t in soft_starts for t in cue_times}
        ticks.update(
            (label.start, True) for label in labels if label.start > label.clip.start
        )
        for t, soft in ticks.items():
            if not time_in_view(t, view_start, view_end):
                continue
            _draw_tick(
                panel,
                time_to_x(t, bar_left, bar_width, view_start, view_end),
                bar_rect,
                alpha=SOFT_TICK_ALPHA if soft else CUE_TICK_ALPHA,
                width=SOFT_TICK_WIDTH if soft else CUE_TICK_WIDTH,
            )
        for label in labels:
            _draw_clip_label(
                panel,
                font,
                label,
                bar_rect=bar_rect,
                bar_left=bar_left,
                bar_width=bar_width,
                view_start_sec=view_start,
                view_end_sec=view_end,
            )

        # Per-slot selection memory stays in selected_clip_t; only the
        # focused row outlines its selected clip.
        selected_t = (
            state.selected_clip_t.get(slot)
            if row_index == state.focus_row and not state.recording
            else None
        )
        hover_t = (
            state.hover_clip[1]
            if state.hover_clip is not None and state.hover_clip[0] == row_index
            else None
        )
        editable = not state.locked and not state.recording
        for clip in row_clips:
            selected = selected_t is not None and clip.start == selected_t
            hovered = hover_t is not None and clip.start == hover_t
            if not selected and not (hovered and editable):
                continue
            span = clip_bar_span(
                clip,
                bar_left=bar_left,
                bar_width=bar_width,
                view_start_sec=view_start,
                view_end_sec=view_end,
            )
            if span is None:
                continue
            left, right = span
            if editable:
                for edge_t, handle_x in (
                    (clip.start, left),
                    (clip.end, right - CLIP_HANDLE_WIDTH),
                ):
                    if time_in_view(edge_t, view_start, view_end):
                        pygame.draw.rect(
                            panel,
                            palette().highlight if selected else palette().label,
                            pygame.Rect(
                                max(left, handle_x),
                                row_y,
                                min(CLIP_HANDLE_WIDTH, right - left),
                                row_h,
                            ),
                        )
            if selected:
                pygame.draw.rect(
                    panel,
                    palette().highlight,
                    pygame.Rect(left, row_y, right - left, row_h),
                    SELECTED_CLIP_OUTLINE_WIDTH,
                )

        if focused:
            # The edge goes over the clips, as on inspector rows.
            draw_row_edge(panel, row_rect, _FOCUSED_LOOK)

    # Song start and end marks continue the ruler's down through every row.
    for bound_x in song_bound_xs(
        duration_sec=state.duration_sec,
        bar_left=bar_left,
        bar_width=bar_width,
        view_start_sec=view_start,
        view_end_sec=view_end,
    ):
        pygame.draw.line(
            panel,
            palette().song_bound,
            (bound_x, 0),
            (bound_x, layout.bar_bottom - 1),
            1,
        )

    _draw_scrollbar(panel, state, layout)
    return panel, row_layout


def build_ruler(
    state: TimelineViewState,
    layout: StripLayout,
    *,
    font_size: int,
) -> pygame.Surface | None:
    """Time scale over the badge row and the strip's top padding."""
    view_start, view_end = view_window(state)
    return render_time_ruler(
        width=layout.panel_w,
        height=layout.badge_reserve + layout.bar_top,
        bar_left=layout.bar_left,
        bar_width=layout.bar_width,
        view_start_sec=view_start,
        view_end_sec=view_end,
        duration_sec=state.duration_sec,
        strip_font_size=font_size,
    )


def _draw_scrollbar(
    panel: pygame.Surface,
    state: TimelineViewState,
    layout: StripLayout,
) -> None:
    """Rail under the rows; the pill thumb is the visible share of the song.

    A thin rail and a rounded neutral thumb keep it from reading as a
    level bar. The whole song in view draws the rail alone.
    """
    track_x, track_y, track_w, track_h = layout.scrollbar_rect
    if track_w <= 0 or track_h <= 0:
        return
    view_start, view_end = view_window(state)
    rail_h = max(1, track_h // 3)
    pygame.draw.rect(
        panel,
        palette().timeline_scroll_rail,
        (track_x, track_y + (track_h - rail_h) // 2, track_w, rail_h),
    )
    if view_end - view_start >= state.duration_sec:
        return
    thumb_x, thumb_w = scrollbar_thumb_span(
        track_w,
        view_start,
        view_end,
        state.duration_sec,
        min_thumb=timeline_ui_metrics().scrollbar_min_thumb,
    )
    pygame.draw.rect(
        panel,
        palette().timeline_scroll_thumb,
        (track_x + thumb_x, track_y, thumb_w, track_h),
        border_radius=track_h // 2,
    )


@dataclass(frozen=True)
class StaticLayers:
    """The cached panel and ruler as laid on the upload surface.

    The panel sits ``panel_y_offset`` below the upload's top, under the ruler.
    """

    panel: pygame.Surface
    ruler: pygame.Surface | None
    panel_y_offset: int

    def lay(self, upload: pygame.Surface) -> None:
        """Clear the upload surface and lay the panel and ruler on it."""
        upload.fill((0, 0, 0, 0))
        upload.blit(self.panel, (0, self.panel_y_offset))
        if self.ruler is not None:
            upload.blit(self.ruler, (0, 0))

    def restore(self, upload: pygame.Surface, rect: tuple[int, int, int, int]) -> None:
        """Repaint *rect* exactly as ``lay`` leaves it, before live drawing.

        Same steps as ``lay`` clipped to the rect, so a pixel restored here
        matches a full rebuild.
        """
        upload.set_clip(rect)
        upload.fill((0, 0, 0, 0), rect)
        upload.blit(self.panel, (0, self.panel_y_offset))
        if self.ruler is not None:
            upload.blit(self.ruler, (0, 0))
        upload.set_clip(None)
