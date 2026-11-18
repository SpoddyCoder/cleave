"""Timeline strip hit testing: what a screen point lands on, from the last compose."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pygame

from cleave.song_markers import marker_index_near
from cleave.timeline import ClipGrip, TimelineClip
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
# Where two clips butt, the pointer within this many pixels of the boundary
# rolls it; the edge zones lie beyond it, one inside each clip.
CLIP_ROLL_HIT_PX: int = 3


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
    row's clip under the point, and ``clip_grip`` what an edge press grabs
    (``clip_hit_at_x``), or None on the body.
    """

    row: int | None
    t_sec: float | None
    tolerance_sec: float
    target: StripTarget | None = None
    marker_index: int | None = None
    clip_start: float | None = None
    clip_grip: ClipGrip | None = None


def clip_hit_at_x(
    clips: Sequence[TimelineClip],
    x: float,
    *,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
) -> tuple[float, ClipGrip | None] | None:
    """The clip under bar pixel *x* as ``(clip start, grip)``, or None in a gap.

    A free edge grabs within ``CLIP_EDGE_HIT_PX``. Where two clips butt, the
    boundary rolls within ``CLIP_ROLL_HIT_PX`` (named by the earlier clip),
    and past that each side trims its own clip's edge out to
    ``CLIP_EDGE_HIT_PX`` more. The nearest edge wins over a body; an edge zone
    never takes more than a third of a narrow clip, so its body stays
    grabbable.
    """
    spans: list[tuple[TimelineClip, float, float, float]] = []
    for clip in clips:
        if clip.end < view_start_sec or clip.start > view_end_sec:
            continue
        start_x = time_to_x(clip.start, bar_left, bar_width, view_start_sec, view_end_sec)
        end_x = time_to_x(clip.end, bar_left, bar_width, view_start_sec, view_end_sec)
        zone = min(float(CLIP_EDGE_HIT_PX), max(1.0, (end_x - start_x) / 3.0))
        spans.append((clip, start_x, end_x, zone))
    # (distance, order, clip start, grip); earlier edges win a tie.
    best: tuple[float, int, float, ClipGrip] | None = None
    body: float | None = None

    def offer(distance: float, order: int, start: float, grip: ClipGrip) -> None:
        nonlocal best
        if best is None or (distance, order) < (best[0], best[1]):
            best = (distance, order, start, grip)

    for index, (clip, start_x, end_x, zone) in enumerate(spans):
        previous = spans[index - 1] if index > 0 else None
        following = spans[index + 1] if index + 1 < len(spans) else None
        if start_x <= x < end_x:
            body = clip.start
        butts_previous = previous is not None and previous[0].end == clip.start
        if not butts_previous and time_in_view(clip.start, view_start_sec, view_end_sec):
            distance = abs(x - start_x)
            if distance <= zone:
                offer(distance, index * 2 + 1, clip.start, "start")
        if not time_in_view(clip.end, view_start_sec, view_end_sec):
            continue
        offset = x - end_x
        if following is not None and following[0].start == clip.end:
            if abs(offset) <= CLIP_ROLL_HIT_PX:
                offer(abs(offset), index * 2, clip.start, "roll")
            elif offset < 0 and -offset <= CLIP_ROLL_HIT_PX + zone:
                offer(-offset, index * 2, clip.start, "end")
            elif offset > 0 and offset <= CLIP_ROLL_HIT_PX + following[3]:
                offer(offset, index * 2 + 2, following[0].start, "start")
        elif abs(offset) <= zone:
            offer(abs(offset), index * 2, clip.start, "end")
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
            buttons=layout.header_buttons,
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
                    clip_grip=None if clip_hit is None else clip_hit[1],
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
