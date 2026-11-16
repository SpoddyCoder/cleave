"""Timeline strip geometry: time mapping, row headers, and the per-compose layout."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pygame

from cleave.timeline import TimelineClip, stem_abbreviation
from cleave.viz.icon_button import icon_gap, icon_row
from cleave.viz.material_icons import visibility_icon_slot_width
from cleave.viz.theme import LABEL, timeline_panel_height_px, timeline_ui_metrics
from cleave.viz.timeline_panel_cache import timeline_badge_reserve_px
from cleave.viz.timeline_ruler import ruler_tick_top


def timeline_band_height_px(row_count: int) -> int:
    """Shell band under the columns: the strip and the badge row above it."""
    if row_count <= 0:
        return 0
    metrics = timeline_ui_metrics()
    return timeline_panel_height_px(row_count) + timeline_badge_reserve_px(
        font_size=metrics.font_size
    )


def time_to_x(
    t_sec: float,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
) -> int:
    """X of *t_sec* with the visible window mapped onto the bar, clamped to it."""
    span = view_end_sec - view_start_sec
    if span <= 0:
        return bar_left
    ratio = max(0.0, min(1.0, (t_sec - view_start_sec) / span))
    return bar_left + int(ratio * bar_width)


def x_to_time(
    x: float,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
) -> float:
    """Inverse of ``time_to_x``, clamped to the visible window."""
    span = view_end_sec - view_start_sec
    if span <= 0 or bar_width <= 0:
        return view_start_sec
    ratio = max(0.0, min(1.0, (x - bar_left) / bar_width))
    return view_start_sec + ratio * span


def time_in_view(t_sec: float, view_start_sec: float, view_end_sec: float) -> bool:
    return view_start_sec <= t_sec <= view_end_sec


def scrollbar_thumb_span(
    track_w: int,
    view_start_sec: float,
    view_end_sec: float,
    duration_sec: float,
    *,
    min_thumb: int,
) -> tuple[int, int]:
    """Thumb ``(offset, width)`` along a track *track_w* pixels wide.

    The width is the visible share of the song, never under *min_thumb*. The
    offset runs the thumb's free travel as the window runs the song.
    """
    track_w = max(0, track_w)
    span = view_end_sec - view_start_sec
    if duration_sec <= 0 or span <= 0 or span >= duration_sec:
        return (0, track_w)
    thumb_w = max(min(min_thumb, track_w), int(round(track_w * span / duration_sec)))
    thumb_w = min(thumb_w, track_w)
    travel = track_w - thumb_w
    offset = int(round(travel * view_start_sec / (duration_sec - span)))
    return (max(0, min(travel, offset)), thumb_w)


StripTarget = Literal[
    "play",
    "record",
    "label",
    "arm",
    "solo",
    "eye",
    "release",
    "scroll_thumb",
    "scroll_track",
]

# A row's header buttons after its label, left to right, each a square icon
# box (``icon_button``) one nominal row tall: arm for recording, solo, the live
# visibility eye, and back to timeline (shown only while overridden).
ROW_HEADER_BUTTONS: tuple[StripTarget, ...] = ("arm", "solo", "eye", "release")
ROW_HEADER_TARGETS: frozenset[str] = frozenset(("label", *ROW_HEADER_BUTTONS))


def header_buttons_width(slot_w: int) -> int:
    """Width of a row's header buttons, with the icon gap between them."""
    count = len(ROW_HEADER_BUTTONS)
    return count * slot_w + (count - 1) * int(icon_gap())


def header_button_x(
    target: StripTarget,
    *,
    padding: int,
    label_width: int,
    slot_w: int,
) -> int:
    """Left edge of header button *target* in panel coordinates."""
    xs = icon_row(padding + label_width, len(ROW_HEADER_BUTTONS), slot_w, int(icon_gap()))
    return int(xs[ROW_HEADER_BUTTONS.index(target)])


def row_header_target_at(
    local_x: float,
    *,
    padding: int,
    label_width: int,
    slot_w: int,
) -> StripTarget | None:
    """The label or header button under panel *local_x*, or None past them.

    The gap between two buttons hits neither.
    """
    if padding <= local_x < padding + label_width:
        return "label"
    for target in ROW_HEADER_BUTTONS:
        left = header_button_x(
            target, padding=padding, label_width=label_width, slot_w=slot_w
        )
        if left <= local_x < left + slot_w:
            return target
    return None



def clip_bar_span(
    clip: TimelineClip,
    *,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
) -> tuple[int, int] | None:
    """Pixel ``(left, right)`` of the clip's visible part, or None out of view."""
    if clip.end <= view_start_sec or clip.start >= view_end_sec:
        return None
    left = time_to_x(
        max(clip.start, view_start_sec), bar_left, bar_width, view_start_sec, view_end_sec
    )
    right = time_to_x(
        min(clip.end, view_end_sec), bar_left, bar_width, view_start_sec, view_end_sec
    )
    return (left, max(left + 1, right))


# Corner buttons sit this far below the top of the badge row.
TRANSPORT_BUTTON_DROP_PX: int = 2


def transport_button_rects(
    *,
    padding: int,
    label_width: int,
    bar_left: int,
    corner_h: int,
    gap: int,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """Play and record button rects in the corner above the row headers.

    Play sits over the row labels (layer number and stem). Record starts at
    the arm buttons and runs to the start of the ruler, over the other row
    buttons. It holds the record glyph plus ``REC``. Rects are in upload
    coordinates (top of the badge row is y=0).
    """
    y = TRANSPORT_BUTTON_DROP_PX
    h = max(1, corner_h - gap)
    play = (padding, y, label_width, h)
    record_x = padding + label_width
    record = (record_x, y, max(1, bar_left - record_x), h)
    return play, record


def playhead_x(
    position_sec: float,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
) -> int:
    return time_to_x(position_sec, bar_left, bar_width, view_start_sec, view_end_sec)


def layer_num_prefix(layer_num: int) -> str:
    return f" {layer_num} "


def stem_abbrev_label(stem: str) -> str:
    return f" {stem_abbreviation(stem)} "


def stem_label_text(layer_num: int, stem: str) -> str:
    return f"{layer_num_prefix(layer_num)}{stem_abbrev_label(stem)}"


def row_prefix_width(
    layer_num_width: int,
    stem_abbrev_width: int,
    row_height: int,
) -> int:
    """Width of a row's header: number, stem, and its ``ROW_HEADER_BUTTONS``."""
    return (
        layer_num_width
        + stem_abbrev_width
        + header_buttons_width(visibility_icon_slot_width(row_height))
    )


@dataclass(frozen=True)
class StripLayout:
    """Where everything sits in one compose of the strip, in panel coordinates.

    The panel's top is y=0; the badge row and ruler sit above it, so upload
    coordinates are panel coordinates plus ``badge_reserve``.
    """

    panel_w: int
    panel_h: int
    panel_x: int
    panel_y: int
    padding: int
    row_gap: int
    row_count: int
    row_h: int
    # Header button and transport glyph line height: the nominal row, centred
    # in a taller row when the band is dragged taller.
    icon_h: int
    bar_left: int
    bar_width: int
    # Width of each of a row's ROW_HEADER_BUTTONS.
    slot_w: int
    layer_num_width: int
    stem_abbrev_width: int
    badge_reserve: int
    bar_top: int
    bar_bottom: int
    # Scrollbar track under the rows, in panel coordinates.
    scrollbar_rect: tuple[int, int, int, int]

    @property
    def label_width(self) -> int:
        """Width of a row's label: layer number and stem abbreviation."""
        return self.layer_num_width + self.stem_abbrev_width

    def row_y(self, display_i: int) -> int:
        return self.padding + display_i * (self.row_h + self.row_gap)

    def icon_y(self, row_y: int) -> int:
        """Top of the nominal-height icon line centred in the row at *row_y*."""
        return row_y + (self.row_h - self.icon_h) // 2

    def row_rect(self, row_y: int) -> pygame.Rect:
        return pygame.Rect(self.padding, row_y, self.panel_w - self.padding * 2, self.row_h)

    def bar_rect(self, row_y: int) -> pygame.Rect:
        """The level bar of the row at *row_y*, inset from the row's top and bottom."""
        inset = timeline_ui_metrics().bar_vertical_inset
        return pygame.Rect(
            self.bar_left,
            row_y + inset,
            self.bar_width,
            max(1, self.row_h - inset * 2),
        )

    def header_button_x(self, target: StripTarget) -> int:
        return header_button_x(
            target,
            padding=self.padding,
            label_width=self.label_width,
            slot_w=self.slot_w,
        )

    def header_button_rect(
        self, target: StripTarget, row_y: int
    ) -> tuple[int, int, int, int]:
        """Panel rect of a row's header button *target*: its square icon box,
        centred in the row, so the hover wash matches a lit button."""
        return (self.header_button_x(target), self.icon_y(row_y), self.slot_w, self.slot_w)

    def transport_rects(
        self,
    ) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
        """Play and record button rects, in upload coordinates."""
        return transport_button_rects(
            padding=self.padding,
            label_width=self.label_width,
            bar_left=self.bar_left,
            corner_h=self.badge_reserve + self.bar_top,
            gap=timeline_ui_metrics().rec_badge_gap,
        )

    def transport_icon_size(self) -> int:
        """Transport glyph size: as tall as a row's level bar."""
        return max(1, self.icon_h - 2 * timeline_ui_metrics().bar_vertical_inset)

    def playhead_top_y(self, *, y_offset: int) -> int:
        """The playhead rises through the ruler to the top of its major ticks."""
        ruler_top = y_offset - self.badge_reserve
        return ruler_top + ruler_tick_top(self.badge_reserve + self.bar_top)

    def playhead_strip_rect(
        self, playhead_px: int, *, y_offset: int
    ) -> tuple[int, int, int, int]:
        """The column a playhead at *playhead_px* covers, with a pixel each side."""
        playhead_left = max(
            self.bar_left,
            min(self.bar_left + self.bar_width - 1, playhead_px),
        )
        width = max(1, timeline_ui_metrics().playhead_width)
        y = self.playhead_top_y(y_offset=y_offset)
        return (playhead_left - width, y, width * 2 + 1, y_offset + self.bar_bottom - y)


def compute_strip_layout(
    row_count: int,
    *,
    font: pygame.font.Font,
    font_size: int,
    padding: int,
    row_gap: int,
    viewport_width: int,
    viewport_height: int,
    timeline_rect: tuple[int, int, int, int] | None = None,
) -> StripLayout | None:
    """Lay the strip out for *row_count* rows, or None when there is no room.

    The shell's timeline band is the container and the strip fills its width.
    With no band the strip sits at the viewport bottom at its fit height.
    """
    if row_count == 0:
        return None

    metrics = timeline_ui_metrics()
    icon_h = metrics.row_height
    fills_band = timeline_rect is not None
    if timeline_rect is None:
        timeline_rect = (0, 0, viewport_width, viewport_height)
    band_x, band_y, band_w, band_h = timeline_rect
    if band_w <= 0 or band_h <= 0:
        return None
    badge_reserve = timeline_badge_reserve_px(font_size=font_size, padding=padding)
    # Rows share any band height past the nominal fit.
    fit_h = timeline_panel_height_px(row_count)
    spare = band_h - badge_reserve - fit_h if fills_band else 0
    row_h = icon_h + max(0, spare) // row_count
    panel_h = fit_h + (row_h - icon_h) * row_count
    panel_w = band_w

    layer_num_width = font.render(layer_num_prefix(max(row_count, 1)), True, LABEL).get_width()
    stem_abbrev_width = font.render(stem_abbrev_label("drums"), True, LABEL).get_width()
    prefix_width = row_prefix_width(layer_num_width, stem_abbrev_width, icon_h)
    bar_left = padding + prefix_width
    bar_width = max(1, panel_w - padding * 2 - prefix_width)
    bar_bottom = padding + row_count * row_h + (row_count - 1) * row_gap
    return StripLayout(
        panel_w=panel_w,
        panel_h=panel_h,
        panel_x=band_x,
        panel_y=band_y + band_h - panel_h,
        padding=padding,
        row_gap=row_gap,
        row_count=row_count,
        row_h=row_h,
        icon_h=icon_h,
        bar_left=bar_left,
        bar_width=bar_width,
        slot_w=visibility_icon_slot_width(icon_h),
        layer_num_width=layer_num_width,
        stem_abbrev_width=stem_abbrev_width,
        badge_reserve=badge_reserve,
        bar_top=padding,
        bar_bottom=bar_bottom,
        scrollbar_rect=(
            bar_left,
            bar_bottom + metrics.scrollbar_gap,
            bar_width,
            metrics.scrollbar_height,
        ),
    )
