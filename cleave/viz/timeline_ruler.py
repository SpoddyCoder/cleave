"""Time scale above the timeline strip's layer rows.

Ticks come from a visible time window (``view_start_sec`` .. ``view_end_sec``)
mapped onto the bar width, so a zoomed or scrolled strip only has to pass a
narrower window. Steps follow how many pixels a second spans.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from cleave.viz.overlay_primitives import overlay_font
from cleave.viz.theme import BAR_GRID, MUTED, SONG_BOUND

# (major, minor) step pairs in seconds, fine to coarse. From 10s up, labelled
# marks land on whole tens of seconds.
_STEPS: tuple[tuple[float, float], ...] = (
    (0.1, 0.05),
    (0.2, 0.1),
    (0.5, 0.1),
    (1.0, 0.5),
    (2.0, 1.0),
    (5.0, 1.0),
    (10.0, 2.0),
    (20.0, 5.0),
    (30.0, 10.0),
    (60.0, 15.0),
    (120.0, 30.0),
    (300.0, 60.0),
    (600.0, 120.0),
    (900.0, 300.0),
    (1800.0, 600.0),
    (3600.0, 900.0),
)
MIN_MINOR_TICK_PX: int = 5
LABEL_TICK_GAP_PX: int = 3
# Labelled marks keep this many label widths (plus gaps) apart.
LABEL_SPACING_RATIO: float = 1.5
# Baseline sits this far above the ruler's bottom edge (the first row).
RULER_BOTTOM_GAP_PX: int = 8
# Ruler font relative to the strip font.
RULER_FONT_RATIO: float = 0.8


@dataclass(frozen=True)
class RulerTicks:
    major_step: float
    minor_step: float | None
    major: tuple[float, ...]
    minor: tuple[float, ...]


def view_time_to_x(
    t_sec: float,
    *,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
) -> int:
    span = view_end_sec - view_start_sec
    if span <= 0:
        return bar_left
    ratio = (t_sec - view_start_sec) / span
    return bar_left + int(ratio * bar_width)


def format_ruler_time(t_sec: float, step_sec: float) -> str:
    """``m:ss`` (``h:mm:ss`` past an hour); tenths when the step is under 1s."""
    if step_sec < 1.0:
        tenths = int(round(t_sec * 10))
        whole, frac = divmod(tenths, 10)
        return f"{_clock(whole)}.{frac}"
    return _clock(int(round(t_sec)))


def _clock(total_sec: int) -> str:
    hours, rem = divmod(max(0, total_sec), 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _times_in_window(step: float, start: float, end: float) -> list[float]:
    first = math.ceil(start / step - 1e-9)
    last = math.floor(end / step + 1e-9)
    return [round(i * step, 6) for i in range(first, last + 1)]


def ruler_ticks(
    *,
    view_start_sec: float,
    view_end_sec: float,
    bar_width: int,
    min_label_px: int,
) -> RulerTicks | None:
    """Major ticks spaced at least *min_label_px* apart, plus minor ticks that fit."""
    span = view_end_sec - view_start_sec
    if span <= 0 or bar_width <= 0:
        return None
    px_per_sec = bar_width / span
    major_step, minor_step = _STEPS[-1]
    for major, minor in _STEPS:
        if major * px_per_sec >= min_label_px:
            major_step, minor_step = major, minor
            break
    major_times = _times_in_window(major_step, view_start_sec, view_end_sec)
    minor_times: list[float] = []
    minor: float | None = minor_step
    if minor_step * px_per_sec < MIN_MINOR_TICK_PX:
        minor = None
    else:
        major_set = set(major_times)
        minor_times = [
            t
            for t in _times_in_window(minor_step, view_start_sec, view_end_sec)
            if t not in major_set
        ]
    return RulerTicks(
        major_step=major_step,
        minor_step=minor,
        major=tuple(major_times),
        minor=tuple(minor_times),
    )


def song_bound_xs(
    *,
    duration_sec: float,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
) -> tuple[int, ...]:
    """X of the song's start and end marks that fall inside the visible window.

    These marks run from the ruler down through every layer row.
    """
    if duration_sec <= 0 or bar_width <= 0:
        return ()
    bar_right = bar_left + bar_width - 1
    xs: list[int] = []
    for t in (0.0, duration_sec):
        if view_start_sec <= t <= view_end_sec:
            x = view_time_to_x(
                t,
                bar_left=bar_left,
                bar_width=bar_width,
                view_start_sec=view_start_sec,
                view_end_sec=view_end_sec,
            )
            xs.append(min(x, bar_right))
    return tuple(xs)


def ruler_tick_top(height: int) -> int:
    """Y of the top of the major ticks on a ruler *height* pixels tall."""
    bottom = max(0, height - 1 - RULER_BOTTOM_GAP_PX)
    return max(0, bottom - max(2, height // 2))


def ruler_font(strip_font_size: int) -> pygame.font.Font:
    return overlay_font(max(1, int(round(strip_font_size * RULER_FONT_RATIO))))


def render_time_ruler(
    *,
    width: int,
    height: int,
    bar_left: int,
    bar_width: int,
    view_start_sec: float,
    view_end_sec: float,
    duration_sec: float,
    strip_font_size: int,
) -> pygame.Surface | None:
    """Transparent ruler surface *width* x *height*; ticks rise from the baseline.

    Song start and end marks run on past the baseline to the bottom edge, where
    the strip's rows continue them.
    """
    if width <= 0 or height <= 0:
        return None
    font = ruler_font(strip_font_size)
    sample = format_ruler_time(max(view_end_sec, 0.0), 1.0)
    label_w = font.size(sample + ".0")[0]
    ticks = ruler_ticks(
        view_start_sec=view_start_sec,
        view_end_sec=view_end_sec,
        bar_width=bar_width,
        min_label_px=int((label_w + LABEL_TICK_GAP_PX * 4) * LABEL_SPACING_RATIO),
    )
    if ticks is None:
        return None

    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    bottom = max(0, height - 1 - RULER_BOTTOM_GAP_PX)
    bar_right = bar_left + bar_width
    major_h = max(2, height // 2)
    minor_h = max(1, height // 5)

    def x_of(t: float) -> int:
        return view_time_to_x(
            t,
            bar_left=bar_left,
            bar_width=bar_width,
            view_start_sec=view_start_sec,
            view_end_sec=view_end_sec,
        )

    labels: list[tuple[int, pygame.Surface]] = []
    for t in ticks.major:
        label = font.render(format_ruler_time(t, ticks.major_step), True, MUTED)
        label_x = min(x_of(t), bar_right - 1) + LABEL_TICK_GAP_PX
        if label_x + label.get_width() <= bar_right:
            labels.append((label_x, label))

    pygame.draw.line(surface, BAR_GRID, (bar_left, bottom), (bar_right - 1, bottom), 1)
    for t in ticks.minor:
        x = x_of(t)
        # Minor ticks under a label would read as part of its text.
        if any(lx - 1 <= x <= lx + lab.get_width() for lx, lab in labels):
            continue
        pygame.draw.line(surface, BAR_GRID, (x, bottom - minor_h), (x, bottom), 1)
    for t in ticks.major:
        x = min(x_of(t), bar_right - 1)
        pygame.draw.line(surface, MUTED, (x, bottom - major_h), (x, bottom), 1)
    for x in song_bound_xs(
        duration_sec=duration_sec,
        bar_left=bar_left,
        bar_width=bar_width,
        view_start_sec=view_start_sec,
        view_end_sec=view_end_sec,
    ):
        pygame.draw.line(surface, MUTED, (x, bottom - major_h), (x, bottom), 1)
        if bottom + 1 < height:
            pygame.draw.line(surface, SONG_BOUND, (x, bottom + 1), (x, height - 1), 1)
    for label_x, label in labels:
        label_y = max(0, bottom - 1 - label.get_height())
        surface.blit(label, (label_x, label_y))
    return surface
