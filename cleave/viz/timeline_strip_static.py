"""Timeline strip static panel: rows, level bars, cue ticks, clip outlines, scrollbar.

Each row names on its clips the presets its layer plays; rows on a timer also
mark where their presets change.

Drawn once per change of the static signature and cached; the live layer
(playhead, flashes, transport, role glyphs) is patched over it each frame.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, replace

import pygame

from cleave.song_markers import (
    DEFAULT_SONG_MARKER_TYPE,
    SONG_MARKER_TYPES,
    SongIntensity,
    SongSection,
)
from cleave.viz.preset_schedule import RowLabel, RowPresets, row_labels
from cleave.viz.material_icons import RECORD_GLYPH, REPLAY_GLYPH, SOLO_GLYPH
from cleave.viz.overlay_primitives import overlay_font, overlay_panel_surface
from cleave.viz.row_present_renderers import (
    render_header_toggle,
    render_visibility_icon,
)
from cleave.viz.theme import palette, timeline_ui_metrics
from cleave.viz.text_fit import fit_text_to_width
from cleave.timeline import LEVEL_EPS
from cleave.viz.timeline_ruler import (
    bar_label_spacing_px,
    draw_bar_lane,
    render_time_ruler,
    ruler_font,
    ruler_label_y,
    song_bound_xs,
)
from cleave.viz.timeline_strip_grid import GridLines, grid_lines
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
# Grid lines over the rows stay weaker than the ticks that mark cuts.
GRID_BAR_ALPHA: int = 80
GRID_BEAT_ALPHA: int = 35
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
# The name's size against the strip font, at full and at its smallest.
CLIP_LABEL_FONT_RATIO: float = 0.825
CLIP_LABEL_MIN_FONT_RATIO: float = 0.675
# Below this opacity the name shrinks with the clip, down to its smallest.
CLIP_LABEL_SHRINK_LEVEL: float = 0.5
# Rows taller than nominal grow the name at this share of their own growth,
# up to this many times its size.
CLIP_LABEL_GROWTH_RATE: float = 0.25
CLIP_LABEL_MAX_GROWTH: float = 1.3
# How far a row's off colour goes towards its section's colour, by intensity.
SECTION_TINT_MIX: dict[SongIntensity, float] = {
    "very calm": 0.08,
    "calm": 0.14,
    "normal": 0.22,
    "intense": 0.32,
    "very intense": 0.42,
}
# Section name in the ruler, clear of the marker line it starts on.
SECTION_LABEL_INSET: int = 5
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


def section_color(section_type: str) -> tuple[int, int, int]:
    """Colour of a section type's name and row tint."""
    colors = palette().song_section_colors
    return colors[(SONG_MARKER_TYPES.index(section_type) - 1) % len(colors)]


def typed_sections(state: TimelineViewState) -> list[SongSection]:
    """Sections with a type: each runs from its marker to the next."""
    times = state.song_marker_times
    ends = (*times[1:], state.duration_sec)
    return [
        SongSection(start, end, section_type, intensity)
        for start, end, section_type, intensity in zip(
            times, ends, state.song_marker_types, state.song_marker_intensities
        )
        if section_type != DEFAULT_SONG_MARKER_TYPE and end > start
    ]


def _section_span(
    section: SongSection, state: TimelineViewState, layout: StripLayout
) -> tuple[int, int] | None:
    """Pixel ``(left, right)`` of the section's visible part, or None out of view."""
    view_start, view_end = view_window(state)
    if section.end <= view_start or section.start >= view_end:
        return None
    left, right = (
        time_to_x(t, layout.bar_left, layout.bar_width, view_start, view_end)
        for t in (section.start, section.end)
    )
    return (left, right) if right > left else None


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
    tints: list[tuple[int, int, tuple[int, int, int]]],
) -> None:
    pygame.draw.rect(panel, palette().timeline_off_segment, bar_rect)
    for left, right, color in tints:
        pygame.draw.rect(
            panel, color, pygame.Rect(left, bar_rect.y, right - left, bar_rect.h)
        )
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


def _level_at(breakpoints: list[tuple[float, float]], t: float) -> float:
    """Level at *t*; on a step, the level that starts there."""
    index = bisect_right(breakpoints, t, key=lambda point: point[0])
    if index == 0 or not breakpoints:
        return 0.0
    if index == len(breakpoints):
        return breakpoints[-1][1]
    t0, level0 = breakpoints[index - 1]
    t1, level1 = breakpoints[index]
    return level0 + (level1 - level0) * (t - t0) / (t1 - t0)


def _draw_row_grid(
    panel: pygame.Surface,
    lines: GridLines,
    *,
    breakpoints: list[tuple[float, float]],
    bar_rect: pygame.Rect,
    view_start_sec: float,
    view_end_sec: float,
) -> None:
    """Grid lines over a row's level bar: dark on the clips, light where it is off.

    Columns are blitted: drawing with an alpha colour would replace the panel's
    alpha instead of blending.
    """
    blits: list[tuple[pygame.Surface, tuple[int, int], tuple[int, int, int, int]]] = []
    for times, alpha in (
        (lines.beats, GRID_BEAT_ALPHA),
        (lines.bars, GRID_BAR_ALPHA),
    ):
        on = pygame.Surface((1, bar_rect.h), pygame.SRCALPHA)
        on.fill((*palette().timeline_clip_text, alpha))
        off = pygame.Surface((1, bar_rect.h), pygame.SRCALPHA)
        off.fill((*palette().label, alpha))
        for t in times:
            x = min(
                time_to_x(t, bar_rect.x, bar_rect.w, view_start_sec, view_end_sec),
                bar_rect.right - 1,
            )
            level = _level_at(breakpoints, t)
            off_h = bar_rect.h
            if level > LEVEL_EPS:
                off_h = max(0, min(bar_rect.h, bar_level_y(bar_rect, level) - bar_rect.y))
            if off_h:
                blits.append((off, (x, bar_rect.y), (0, 0, 1, off_h)))
            if off_h < bar_rect.h:
                blits.append(
                    (on, (x, bar_rect.y + off_h), (0, 0, 1, bar_rect.h - off_h))
                )
    panel.blits(blits, doreturn=False)


def _grid_lines(
    state: TimelineViewState, layout: StripLayout, font_size: int
) -> GridLines:
    if not state.show_bar_grid:
        return GridLines()
    view_start, view_end = view_window(state)
    return grid_lines(
        state.bar_grid_times,
        state.beat_grid_times,
        view_start_sec=view_start,
        view_end_sec=view_end,
        bar_width=layout.bar_width,
        min_label_px=bar_label_spacing_px(len(state.bar_grid_times), font_size),
    )


def clip_label_font_size(
    level: float, strip_font_size: int, *, row_growth: float = 1.0
) -> int:
    """The preset name's font size on a clip at *level*.

    *row_growth* is the row's height over the nominal row height.
    """
    growth = 1.0 + max(0.0, row_growth - 1.0) * CLIP_LABEL_GROWTH_RATE
    growth = min(CLIP_LABEL_MAX_GROWTH, growth)
    full = strip_font_size * CLIP_LABEL_FONT_RATIO * growth
    smallest = strip_font_size * CLIP_LABEL_MIN_FONT_RATIO * growth
    scaled = full * min(1.0, level / CLIP_LABEL_SHRINK_LEVEL)
    return max(1, int(round(max(smallest, scaled))))


def _draw_clip_label(
    panel: pygame.Surface,
    label: RowLabel,
    *,
    font_size: int,
    row_growth: float,
    bar_rect: pygame.Rect,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
) -> None:
    clip = label.clip
    level = max(0.0, min(1.0, float(clip.level)))
    size = clip_label_font_size(level, font_size, row_growth=row_growth)
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
    font = overlay_font(size)
    fitted = fit_text_to_width(font, text, room)
    if not fitted:
        return
    color = (
        palette().button_danger_bg if label.empty else palette().timeline_clip_text
    )
    surf = font.render(fitted, True, color)
    # Centred on the clip's level bar; on a short bar the name rests on the
    # row's bottom edge and rises past the fill.
    filled_h = int(round(level * bar_rect.h))
    line_h = font.get_height()
    y = bar_rect.bottom - filled_h + (filled_h - line_h) // 2
    y = max(bar_rect.top, min(y, bar_rect.bottom - line_h))
    panel.blit(surf, (left + CLIP_LABEL_INSET, y))


def build_static_panel(
    state: TimelineViewState,
    layout: StripLayout,
    font: pygame.font.Font,
    *,
    font_size: int,
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

    tints = [
        (
            *span,
            _lerp_rgb(
                palette().timeline_off_segment,
                section_color(section.section_type),
                SECTION_TINT_MIX[section.intensity],
            ),
        )
        for section in typed_sections(state)
        if (span := _section_span(section, state, layout)) is not None
    ]

    # In the gaps between rows; each row redraws the lines over its own bar.
    lines = _grid_lines(state, layout, font_size)
    for t in lines.bars:
        grid_x = min(
            time_to_x(t, bar_left, bar_width, view_start, view_end),
            bar_left + bar_width - 1,
        )
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

        breakpoints = bar_level_breakpoints_for_row(state, slot)
        _draw_level_bar(
            panel,
            breakpoints=breakpoints,
            bar_left=bar_left,
            bar_width=bar_width,
            view_start_sec=view_start,
            view_end_sec=view_end,
            bar_rect=bar_rect,
            on_color=track_color(row_index),
            tints=tints,
        )
        _draw_row_grid(
            panel,
            lines,
            breakpoints=breakpoints,
            bar_rect=bar_rect,
            view_start_sec=view_start,
            view_end_sec=view_end,
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
        for label in labels if state.show_preset_names else ():
            _draw_clip_label(
                panel,
                label,
                font_size=font_size,
                row_growth=layout.row_h / max(1, layout.icon_h),
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
    """Time scale over the badge row and the strip's top padding, then the bar lane.

    Section names share the time scale's line and hide the times they cover.
    """
    view_start, view_end = view_window(state)
    names = _section_names(state, layout, font_size)
    ruler = render_time_ruler(
        width=layout.panel_w,
        height=layout.ruler_h,
        bar_left=layout.bar_left,
        bar_width=layout.bar_width,
        view_start_sec=view_start,
        view_end_sec=view_end,
        duration_sec=state.duration_sec,
        strip_font_size=font_size,
        reserved=[
            (x - SECTION_LABEL_INSET, x + name.get_width()) for x, name in names
        ],
    )
    if ruler is not None:
        for x, name in names:
            ruler.blit(name, (x, ruler_label_y(layout.ruler_h, name.get_height())))
    if ruler is None or not layout.bar_lane_h:
        return ruler
    band = pygame.Surface((layout.panel_w, layout.band_h), pygame.SRCALPHA)
    band.blit(ruler, (0, 0))
    draw_bar_lane(
        band,
        _grid_lines(state, layout, font_size),
        top=layout.ruler_h,
        height=layout.bar_lane_h,
        bar_left=layout.bar_left,
        bar_width=layout.bar_width,
        view_start_sec=view_start,
        view_end_sec=view_end,
        duration_sec=state.duration_sec,
        strip_font_size=font_size,
    )
    return band


def _section_names(
    state: TimelineViewState, layout: StripLayout, font_size: int
) -> list[tuple[int, pygame.Surface]]:
    """``(x, name)`` of each section in view whose whole name fits."""
    font = ruler_font(font_size)
    names: list[tuple[int, pygame.Surface]] = []
    for section in typed_sections(state):
        span = _section_span(section, state, layout)
        if span is None:
            continue
        x = span[0] + SECTION_LABEL_INSET
        name = font.render(
            section.section_type, True, section_color(section.section_type)
        )
        if x + name.get_width() <= span[1]:
            names.append((x, name))
    return names


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
