"""The editor's mouse pointer: shapes, UI-scale sizing, and OS cursor updates."""

from __future__ import annotations

import os
from collections.abc import Iterator
from unittest.mock import patch

import pygame
import pytest
from imgui_bundle import imgui

from cleave.config_schema.editor import DEFAULT_UI_SCALE
from cleave.viz.pointer_cursor import (
    PointerCursors,
    PointerShape,
    build_pointer_surface,
    pointer_hotspot,
    pointer_size_px,
    request_pointer,
    requested_pointer,
)
from cleave.viz.theme import POINTER_BASE_PX, set_ui_scale_percent

_SET_CURSOR = "cleave.viz.pointer_cursor.pygame.mouse.set_cursor"


@pytest.fixture(autouse=True)
def _default_ui_scale() -> Iterator[None]:
    yield
    set_ui_scale_percent(DEFAULT_UI_SCALE)


def test_pointer_size_follows_ui_scale() -> None:
    assert pointer_size_px() == POINTER_BASE_PX
    set_ui_scale_percent(200)
    assert pointer_size_px() == POINTER_BASE_PX * 2
    set_ui_scale_percent(80)
    assert pointer_size_px() == round(POINTER_BASE_PX * 0.8)


@pytest.mark.parametrize("shape", list(PointerShape))
@pytest.mark.parametrize("size", [26, 32, 64])
def test_every_shape_is_black_with_a_white_outline_inside_its_square(
    shape: PointerShape, size: int
) -> None:
    surface = build_pointer_surface(shape, size)
    assert surface.get_size() == (size, size)
    pixels = [
        surface.get_at((x, y)) for x in range(size) for y in range(size)
    ]
    assert any(p.a == 255 and max(p.r, p.g, p.b) < 40 for p in pixels)
    assert any(p.a == 255 and min(p.r, p.g, p.b) > 215 for p in pixels)
    assert any(p.a == 0 for p in pixels)
    hot_x, hot_y = pointer_hotspot(shape, size)
    assert 0 <= hot_x < size and 0 <= hot_y < size


def test_arrow_hotspot_is_its_tip_and_centred_shapes_use_the_middle() -> None:
    assert pointer_hotspot(PointerShape.ARROW, 32) == (2, 2)
    assert pointer_hotspot(PointerShape.ARROW, 64) == (4, 4)
    assert pointer_hotspot(PointerShape.RESIZE_EW, 32) == (16, 16)
    assert pointer_hotspot(PointerShape.TEXT, 64) == (32, 32)


def test_apply_sets_the_cursor_only_when_the_shape_changes() -> None:
    cursors = PointerCursors()
    with patch(_SET_CURSOR) as set_cursor:
        cursors.apply(PointerShape.ARROW)
        cursors.apply(PointerShape.ARROW)
        assert set_cursor.call_count == 1
        cursors.apply(PointerShape.HAND)
        assert set_cursor.call_count == 2
    arrow = set_cursor.call_args_list[0].args[0]
    assert arrow.type == "color"
    assert arrow.data[0] == pointer_hotspot(PointerShape.ARROW, POINTER_BASE_PX)
    assert arrow.data[1].get_size() == (POINTER_BASE_PX, POINTER_BASE_PX)
    assert cursors.applied is PointerShape.HAND


def test_ui_scale_change_rebuilds_the_showing_cursor() -> None:
    cursors = PointerCursors()
    with patch(_SET_CURSOR) as set_cursor:
        cursors.apply(PointerShape.ARROW)
        set_ui_scale_percent(150)
        cursors.apply(PointerShape.ARROW)
    assert set_cursor.call_count == 2
    rebuilt = set_cursor.call_args_list[1].args[0]
    assert rebuilt.data[1].get_size() == (POINTER_BASE_PX * 3 // 2,) * 2


def test_refused_colour_cursor_falls_back_to_system_cursors() -> None:
    calls: list[object] = []

    def set_cursor(cursor: object) -> None:
        calls.append(cursor)
        if not isinstance(cursor, int):
            raise pygame.error("no colour cursors")

    cursors = PointerCursors()
    with patch(_SET_CURSOR, side_effect=set_cursor):
        cursors.apply(PointerShape.HAND)
        cursors.apply(PointerShape.RESIZE_NS)
    assert calls[1:] == [pygame.SYSTEM_CURSOR_HAND, pygame.SYSTEM_CURSOR_SIZENS]


def test_request_resets_to_arrow_each_frame_and_the_last_request_wins() -> None:
    context = imgui.create_context()
    try:
        io = imgui.get_io()
        io.set_ini_filename(os.devnull)
        io.display_size = imgui.ImVec2(320.0, 200.0)
        io.fonts.get_tex_data_as_rgba32()
        imgui.new_frame()
        request_pointer(PointerShape.HAND)
        request_pointer(PointerShape.TEXT)
        assert requested_pointer() is PointerShape.TEXT
        imgui.render()
        imgui.new_frame()
        assert requested_pointer() is PointerShape.ARROW
        for shape in PointerShape:
            request_pointer(shape)
            assert requested_pointer() is shape
        imgui.render()
    finally:
        imgui.destroy_context(context)
