"""The editor's mouse pointer: black shapes with a white outline, at the UI scale.

Draw code asks for a shape with ``request_pointer`` from the same hover test
that paints its highlight. The request rides ImGui's mouse-cursor slot, which
resets to the arrow every frame. ``ImGuiHost.end_frame`` reads the slot and
hands it to ``PointerCursors.apply``, which sets an OS cursor.

Shapes are data on a ``POINTER_GRID`` unit square. They are rasterised large
and scaled down, so edges stay smooth at every UI scale.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import pygame
from imgui_bundle import imgui

from cleave.viz.theme import (
    POINTER_BASE_PX,
    POINTER_OUTLINE_PX,
    ui_scale_generation,
    ui_scale_percent,
)

# Shapes are authored on a square this many units wide.
POINTER_GRID: float = 32.0
# Rasterise at this multiple of the final size, then scale down.
_SUPERSAMPLE: int = 4
_FILL = (0, 0, 0, 255)
_OUTLINE = (255, 255, 255, 255)
# Transparent white, so scaled edges blend to the outline colour, not to grey.
_CLEAR = (255, 255, 255, 0)

_Point = tuple[float, float]


class PointerShape(Enum):
    ARROW = "arrow"
    HAND = "hand"
    TEXT = "text"
    RESIZE_EW = "resize_ew"
    RESIZE_NS = "resize_ns"
    MOVE = "move"
    NOT_ALLOWED = "not_allowed"


@dataclass(frozen=True)
class _Poly:
    points: tuple[_Point, ...]


@dataclass(frozen=True)
class _Line:
    """A round-capped stroke."""

    start: _Point
    end: _Point
    width: float


@dataclass(frozen=True)
class _Ring:
    center: _Point
    radius: float
    width: float


_Part = _Poly | _Line | _Ring


@dataclass(frozen=True)
class _ShapeSpec:
    parts: tuple[_Part, ...]
    hotspot: _Point


def _transpose(points: tuple[_Point, ...]) -> tuple[_Point, ...]:
    return tuple((y, x) for x, y in points)


_ARROW_POINTS: tuple[_Point, ...] = (
    (2.5, 2.5),
    (2.5, 25.5),
    (7.9, 20.3),
    (12.0, 29.5),
    (15.5, 28.0),
    (11.5, 19.0),
    (18.7, 19.0),
)
_EW_POINTS: tuple[_Point, ...] = (
    (3.0, 16.0),
    (9.5, 9.5),
    (9.5, 14.0),
    (22.5, 14.0),
    (22.5, 9.5),
    (29.0, 16.0),
    (22.5, 22.5),
    (22.5, 18.0),
    (9.5, 18.0),
    (9.5, 22.5),
)
_MOVE_EW_POINTS: tuple[_Point, ...] = (
    (2.5, 16.0),
    (7.5, 11.0),
    (7.5, 14.5),
    (24.5, 14.5),
    (24.5, 11.0),
    (29.5, 16.0),
    (24.5, 21.0),
    (24.5, 17.5),
    (7.5, 17.5),
    (7.5, 21.0),
)
_CENTER: _Point = (16.0, 16.0)

_SHAPES: dict[PointerShape, _ShapeSpec] = {
    PointerShape.ARROW: _ShapeSpec((_Poly(_ARROW_POINTS),), (2.0, 2.0)),
    PointerShape.HAND: _ShapeSpec(
        (
            _Line((12.0, 5.0), (12.0, 18.0), 5.0),
            _Line((17.0, 12.5), (17.0, 19.0), 5.0),
            _Line((22.0, 13.5), (22.0, 20.0), 5.0),
            _Line((26.25, 15.5), (26.25, 21.0), 4.5),
            _Line((5.0, 17.5), (11.0, 24.0), 5.0),
            _Poly(
                (
                    (9.5, 17.0),
                    (28.5, 19.0),
                    (28.5, 22.5),
                    (25.5, 29.0),
                    (13.0, 29.0),
                    (8.0, 22.0),
                )
            ),
        ),
        (12.0, 2.0),
    ),
    PointerShape.TEXT: _ShapeSpec(
        (
            _Line((16.0, 5.0), (16.0, 27.0), 2.0),
            _Line((12.0, 4.0), (20.0, 4.0), 2.0),
            _Line((12.0, 28.0), (20.0, 28.0), 2.0),
        ),
        _CENTER,
    ),
    PointerShape.RESIZE_EW: _ShapeSpec((_Poly(_EW_POINTS),), _CENTER),
    PointerShape.RESIZE_NS: _ShapeSpec((_Poly(_transpose(_EW_POINTS)),), _CENTER),
    PointerShape.MOVE: _ShapeSpec(
        (_Poly(_MOVE_EW_POINTS), _Poly(_transpose(_MOVE_EW_POINTS))), _CENTER
    ),
    PointerShape.NOT_ALLOWED: _ShapeSpec(
        (
            _Ring(_CENTER, 10.0, 3.5),
            _Line((9.0, 9.0), (23.0, 23.0), 3.5),
        ),
        _CENTER,
    ),
}

_SYSTEM_CURSORS: dict[PointerShape, int] = {
    PointerShape.ARROW: pygame.SYSTEM_CURSOR_ARROW,
    PointerShape.HAND: pygame.SYSTEM_CURSOR_HAND,
    PointerShape.TEXT: pygame.SYSTEM_CURSOR_IBEAM,
    PointerShape.RESIZE_EW: pygame.SYSTEM_CURSOR_SIZEWE,
    PointerShape.RESIZE_NS: pygame.SYSTEM_CURSOR_SIZENS,
    PointerShape.MOVE: pygame.SYSTEM_CURSOR_SIZEALL,
    PointerShape.NOT_ALLOWED: pygame.SYSTEM_CURSOR_NO,
}

_IMGUI_CURSORS: dict[PointerShape, int] = {
    PointerShape.ARROW: int(imgui.MouseCursor_.arrow),
    PointerShape.HAND: int(imgui.MouseCursor_.hand),
    PointerShape.TEXT: int(imgui.MouseCursor_.text_input),
    PointerShape.RESIZE_EW: int(imgui.MouseCursor_.resize_ew),
    PointerShape.RESIZE_NS: int(imgui.MouseCursor_.resize_ns),
    PointerShape.MOVE: int(imgui.MouseCursor_.resize_all),
    PointerShape.NOT_ALLOWED: int(imgui.MouseCursor_.not_allowed),
}
_SHAPE_FOR_IMGUI: dict[int, PointerShape] = {
    value: shape for shape, value in _IMGUI_CURSORS.items()
}


def request_pointer(shape: PointerShape) -> None:
    """Ask for *shape* this frame. Call inside the ImGui frame; the last call wins."""
    imgui.set_mouse_cursor(_IMGUI_CURSORS[shape])


def requested_pointer() -> PointerShape:
    """This frame's requested shape. The arrow when nothing asked."""
    return _SHAPE_FOR_IMGUI.get(int(imgui.get_mouse_cursor()), PointerShape.ARROW)


def pointer_size_px() -> int:
    """Edge of the square pointer image at the live UI scale."""
    return max(8, round(POINTER_BASE_PX * ui_scale_percent() / 100.0))


def _fill_circle(
    surface: pygame.Surface, color: tuple[int, int, int, int], center: _Point, radius: float
) -> None:
    pygame.draw.circle(surface, color, center, max(1.0, radius))


def _fill_stroke(
    surface: pygame.Surface,
    color: tuple[int, int, int, int],
    start: _Point,
    end: _Point,
    half_width: float,
) -> None:
    """A stroke of even thickness at any angle, with round caps."""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length > 0.0:
        nx = -dy / length * half_width
        ny = dx / length * half_width
        pygame.draw.polygon(
            surface,
            color,
            (
                (start[0] + nx, start[1] + ny),
                (end[0] + nx, end[1] + ny),
                (end[0] - nx, end[1] - ny),
                (start[0] - nx, start[1] - ny),
            ),
        )
    _fill_circle(surface, color, start, half_width)
    _fill_circle(surface, color, end, half_width)


def _draw_part(
    surface: pygame.Surface,
    part: _Part,
    color: tuple[int, int, int, int],
    unit: float,
    grow: float,
) -> None:
    """Draw *part* at *unit* pixels per grid unit, swollen by *grow* pixels."""
    if isinstance(part, _Poly):
        points = [(x * unit, y * unit) for x, y in part.points]
        pygame.draw.polygon(surface, color, points)
        if grow > 0.0:
            for index, point in enumerate(points):
                _fill_stroke(surface, color, point, points[index - 1], grow)
        return
    if isinstance(part, _Line):
        start = (part.start[0] * unit, part.start[1] * unit)
        end = (part.end[0] * unit, part.end[1] * unit)
        _fill_stroke(surface, color, start, end, part.width * unit / 2.0 + grow)
        return
    center = (part.center[0] * unit, part.center[1] * unit)
    half = part.width * unit / 2.0 + grow
    outer = part.radius * unit + half
    pygame.draw.circle(surface, color, center, outer, max(1, round(2.0 * half)))


def build_pointer_surface(shape: PointerShape, size_px: int) -> pygame.Surface:
    """*shape* as a *size_px* square: black fill, white outline, clear elsewhere."""
    spec = _SHAPES[shape]
    big = size_px * _SUPERSAMPLE
    unit = big / POINTER_GRID
    outline = POINTER_OUTLINE_PX * size_px / POINTER_BASE_PX * _SUPERSAMPLE
    surface = pygame.Surface((big, big), pygame.SRCALPHA)
    surface.fill(_CLEAR)
    for part in spec.parts:
        _draw_part(surface, part, _OUTLINE, unit, outline)
    for part in spec.parts:
        _draw_part(surface, part, _FILL, unit, 0.0)
    return pygame.transform.smoothscale(surface, (size_px, size_px))


def pointer_hotspot(shape: PointerShape, size_px: int) -> tuple[int, int]:
    """The click point of *shape* in a *size_px* image."""
    x, y = _SHAPES[shape].hotspot
    scale = size_px / POINTER_GRID
    last = size_px - 1
    return (min(last, round(x * scale)), min(last, round(y * scale)))


class PointerCursors:
    """Builds the pointer set at the UI scale and sets the OS cursor on change."""

    def __init__(self) -> None:
        self._generation: int | None = None
        self._cursors: dict[PointerShape, pygame.cursors.Cursor] = {}
        self._applied: PointerShape | None = None
        # Set when SDL refuses a colour cursor; the OS shapes take over.
        self._system_only = False

    @property
    def applied(self) -> PointerShape | None:
        return self._applied

    def apply(self, shape: PointerShape) -> None:
        """Show *shape*. Does nothing when it is already showing at this scale."""
        generation = ui_scale_generation()
        if generation != self._generation:
            self._generation = generation
            self._cursors = {}
            self._applied = None
        if shape is self._applied:
            return
        self._applied = shape
        if not self._system_only:
            if _set_cursor(self._cursor(shape)):
                return
            self._system_only = True
        _set_cursor(_SYSTEM_CURSORS[shape])

    def _cursor(self, shape: PointerShape) -> pygame.cursors.Cursor:
        cursor = self._cursors.get(shape)
        if cursor is None:
            size = pointer_size_px()
            cursor = pygame.cursors.Cursor(
                pointer_hotspot(shape, size), build_pointer_surface(shape, size)
            )
            self._cursors[shape] = cursor
        return cursor


def _set_cursor(cursor: pygame.cursors.Cursor | int) -> bool:
    try:
        pygame.mouse.set_cursor(cursor)
    except pygame.error:
        return False
    return True
