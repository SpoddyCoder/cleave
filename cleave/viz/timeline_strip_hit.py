"""Timeline strip hit testing: what a screen point lands on, from the last compose."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pygame

from cleave.song_markers import marker_index_near
from cleave.timeline import ClipEdge, TimelineClip
from cleave.viz.theme import timeline_ui_metrics
from cleave.viz.timeline_ruler import ruler_tick_top
from cleave.viz.timeline_strip_layout import (
    StripLayout,
    StripTarget,
    row_header_target_at,
    scrollbar_thumb_span,
    time_in_view,
    time_to_x,
    x_to_time,
)

# Pointer slack around a song marker, in pixels.
STRIP_HIT_PX: int = 4
# A clip edge takes the pointer within this many pixels, ahead of the body.
CLIP_EDGE_HIT_PX: int = 5


@dataclass(frozen=True)
class StripHit:
    """What a screen point lands on in the strip.

    ``row`` is None for the ruler and the scrollbar. ``t_sec`` is None outside
    the bar span (row labels and buttons). ``tolerance_sec`` is
    ``STRIP_HIT_PX`` in song time. ``target`` names a control: the corner
    ``"play"`` / ``"record"`` buttons, a row's ``"label"`` (layer number and
    stem abbreviation), one of its ``ROW_HEADER_BUTTONS`` (``"arm"``,
    ``"solo"``, ``"eye"``, ``"release"``), or the scrollbar's
    ``"scroll_thumb"`` / ``"scroll_track"``. On the
    scrollbar ``t_sec`` is the song time at that point along the track.
    ``marker_index`` is the song marker within ``STRIP_HIT_PX`` of the point on
    the ruler or in a row's bar, or None. ``clip_start`` is the start of the
    row's clip under the point, and ``clip_edge`` names the edge within
    ``CLIP_EDGE_HIT_PX`` of it (an edge wins over the body, and a boundary
    two clips share is the earlier clip's end).
    """

    row: int | None
    t_sec: float | None
    tolerance_sec: float
    target: StripTarget | None = None
    marker_index: int | None = None
    clip_start: float | None = None
    clip_edge: ClipEdge | None = None


def clip_hit_at_x(
    clips: Sequence[TimelineClip],
    x: float,
    *,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
) -> tuple[float, ClipEdge | None] | None:
    """The clip under bar pixel *x* as ``(clip start, edge)``, or None in a gap.

    The nearest edge within ``CLIP_EDGE_HIT_PX`` wins over a body; the edge
    zone never takes more than a third of a narrow clip, so its body stays
    grabbable. Where two clips butt, the shared boundary is the earlier
    clip's end.
    """
    best: tuple[float, int, float, ClipEdge] | None = None
    body: float | None = None
    for order, clip in enumerate(clips):
        if clip.end < view_start_sec or clip.start > view_end_sec:
            continue
        start_x = time_to_x(clip.start, bar_left, bar_width, view_start_sec, view_end_sec)
        end_x = time_to_x(clip.end, bar_left, bar_width, view_start_sec, view_end_sec)
        zone = min(float(CLIP_EDGE_HIT_PX), max(1.0, (end_x - start_x) / 3.0))
        for edge, edge_x, edge_t in (
            ("end", end_x, clip.end),
            ("start", start_x, clip.start),
        ):
            if not time_in_view(edge_t, view_start_sec, view_end_sec):
                continue
            distance = abs(x - edge_x)
            # Earlier clips sort first, and an end before a start, on a tie.
            rank = (distance, order * 2 + (0 if edge == "end" else 1))
            if distance <= zone and (best is None or rank < (best[0], best[1])):
                best = (distance, rank[1], clip.start, edge)
        if start_x <= x < end_x:
            body = clip.start
    if best is not None:
        return (best[2], best[3])
    return None if body is None else (body, None)


@dataclass(frozen=True)
class StripHitMap:
    """The strip as the last compose laid it out, for pointer queries."""

    layout: StripLayout
    duration_sec: float
    view: tuple[float, float]
    markers: tuple[float, ...]
    # Each row's clips, by display row.
    clips: tuple[tuple[TimelineClip, ...], ...]

    def hit_at(self, x: float, y: float) -> StripHit | None:
        """Ruler or layer row under a screen point."""
        layout = self.layout
        local_x = x - layout.panel_x
        local_y = y - layout.panel_y
        if not 0 <= local_x < layout.panel_w:
            return None
        view_start, view_end = self.view
        tolerance = STRIP_HIT_PX * self.view_sec_per_px()
        in_bar = layout.bar_left <= local_x < layout.bar_left + layout.bar_width
        t_sec = (
            x_to_time(
                local_x, layout.bar_left, layout.bar_width, view_start, view_end
            )
            if in_bar
            else None
        )
        marker_index = (
            marker_index_near(self.markers, t_sec, tolerance)
            if t_sec is not None
            else None
        )
        if -layout.badge_reserve <= local_y < layout.bar_top:
            upload_y = local_y + layout.badge_reserve
            for target, rect in zip(
                ("play", "record"), layout.transport_rects(), strict=True
            ):
                if pygame.Rect(rect).collidepoint(local_x, upload_y):
                    return StripHit(
                        row=None, t_sec=None, tolerance_sec=tolerance, target=target
                    )
            # The time scale starts at its major ticks; the labels above them
            # and the band's top edge stay clear for the resize splitter.
            ruler_h = layout.badge_reserve + layout.bar_top
            if upload_y < ruler_tick_top(ruler_h):
                return None
            return StripHit(
                row=None,
                t_sec=t_sec,
                tolerance_sec=tolerance,
                marker_index=marker_index,
            )
        # The scrollbar takes the gap above it and the padding below, so the
        # thin track is an easy target.
        if in_bar and layout.bar_bottom <= local_y < layout.panel_h:
            thumb_x, thumb_w = self.thumb_span()
            on_thumb = thumb_x <= local_x - layout.bar_left < thumb_x + thumb_w
            return StripHit(
                row=None,
                t_sec=self.scrollbar_time_at_x(x),
                tolerance_sec=tolerance,
                target="scroll_thumb" if on_thumb else "scroll_track",
            )
        header_target = row_header_target_at(
            local_x,
            padding=layout.padding,
            label_width=layout.label_width,
            slot_w=layout.slot_w,
        )
        for display_i in range(layout.row_count):
            row_y = layout.row_y(display_i)
            if row_y <= local_y < row_y + layout.row_h:
                clip_hit = (
                    clip_hit_at_x(
                        self.clips[display_i],
                        local_x,
                        bar_left=layout.bar_left,
                        bar_width=layout.bar_width,
                        view_start_sec=view_start,
                        view_end_sec=view_end,
                    )
                    if in_bar and display_i < len(self.clips)
                    else None
                )
                return StripHit(
                    row=display_i,
                    t_sec=t_sec,
                    tolerance_sec=tolerance,
                    target=header_target,
                    marker_index=marker_index,
                    clip_start=None if clip_hit is None else clip_hit[0],
                    clip_edge=None if clip_hit is None else clip_hit[1],
                )
        return None

    def row_label_rect(self, row: int) -> tuple[int, int, int, int] | None:
        """Screen rect of *row*'s label (number and stem)."""
        layout = self.layout
        if not 0 <= row < layout.row_count:
            return None
        return (
            layout.panel_x + layout.padding,
            layout.panel_y + layout.row_y(row),
            layout.label_width,
            layout.row_h,
        )

    def time_at_x(self, x: float) -> float:
        """Song time under screen *x*, clamped to the bar."""
        layout = self.layout
        return x_to_time(
            x - layout.panel_x, layout.bar_left, layout.bar_width, *self.view
        )

    def view_sec_per_px(self) -> float:
        """Song seconds one bar pixel spans in the visible window."""
        if self.layout.bar_width <= 0:
            return 0.0
        view_start, view_end = self.view
        return max(0.0, view_end - view_start) / self.layout.bar_width

    def scrollbar_time_at_x(self, x: float) -> float:
        """Song time at screen *x* along the scrollbar track (the whole song)."""
        layout = self.layout
        return x_to_time(
            x - layout.panel_x,
            layout.bar_left,
            layout.bar_width,
            0.0,
            self.duration_sec,
        )

    def scrollbar_sec_per_px(self) -> float:
        """Seconds the window start moves per pixel of thumb travel. 0 when it cannot move."""
        view_start, view_end = self.view
        _thumb_x, thumb_w = self.thumb_span()
        travel = self.layout.bar_width - thumb_w
        hidden = self.duration_sec - (view_end - view_start)
        if travel <= 0 or hidden <= 0:
            return 0.0
        return hidden / travel

    def thumb_span(self) -> tuple[int, int]:
        view_start, view_end = self.view
        return scrollbar_thumb_span(
            self.layout.scrollbar_rect[2],
            view_start,
            view_end,
            self.duration_sec,
            min_thumb=timeline_ui_metrics().scrollbar_min_thumb,
        )
