"""Sideways drag on stepped inspector values, and column splitters. No GL window."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pygame

from cleave.config_schema.editor import (
    DEFAULT_INSPECTOR_WIDTH,
    DEFAULT_NAVIGATOR_WIDTH,
)
from cleave.viz.menu_bar import MenuBarState
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import apply_field_horizontal
from cleave.viz.shell_host import (
    _VALUE_DRAG_THRESHOLD_PX,
    ShellHost,
    apply_value_drag,
    value_drag_steps,
)
from cleave.viz.shell_layout import (
    MIN_COLUMN_WIDTH,
    SPLITTER_HIT_PX,
    ShellLayout,
    clamp_column_widths,
    splitter_hit,
)
from tests.cleave.viz.test_controls import _make_controls

_OPACITY = RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")


def _opacity(controls) -> int:
    return controls.session.layers["layer_1"].opacity_pct


def test_value_drag_steps_direction_count_and_remainder() -> None:
    assert value_drag_steps(25.0, 10.0) == (2, 5.0)
    assert value_drag_steps(-25.0, 10.0) == (-2, -5.0)
    assert value_drag_steps(9.0, 10.0) == (0, 9.0)
    assert value_drag_steps(-9.0, 10.0) == (0, -9.0)
    assert value_drag_steps(10.0, 10.0) == (1, 0.0)
    assert value_drag_steps(-10.0, 10.0) == (-1, 0.0)


def test_drag_delta_matches_one_horizontal_step() -> None:
    threshold = _VALUE_DRAG_THRESHOLD_PX
    dragged = _make_controls(("layer_1",))
    keyed = _make_controls(("layer_1",))

    remaining, crossed = apply_value_drag(dragged, _OPACITY, threshold, 0.0)
    apply_field_horizontal(keyed, _OPACITY, True, False)

    assert crossed is True
    assert remaining == 0.0
    assert _opacity(dragged) == _opacity(keyed)

    dragged_back = _make_controls(("layer_1",))
    keyed_back = _make_controls(("layer_1",))
    apply_value_drag(dragged_back, _OPACITY, -threshold, 0.0)
    apply_field_horizontal(keyed_back, _OPACITY, False, False)
    assert _opacity(dragged_back) == _opacity(keyed_back)

    burst = _make_controls(("layer_1",))
    keyed_burst = _make_controls(("layer_1",))
    remaining, crossed = apply_value_drag(
        burst, _OPACITY, threshold * 2 + 5.0, 0.0
    )
    apply_field_horizontal(keyed_burst, _OPACITY, True, False)
    apply_field_horizontal(keyed_burst, _OPACITY, True, False)
    assert crossed is True
    assert remaining == 5.0
    assert _opacity(burst) == _opacity(keyed_burst)

    held = _make_controls(("layer_1",))
    before = _opacity(held)
    remaining, crossed = apply_value_drag(held, _OPACITY, threshold - 1.0, 0.0)
    assert crossed is False
    assert remaining == threshold - 1.0
    assert _opacity(held) == before
    remaining, crossed = apply_value_drag(held, _OPACITY, 1.0, remaining)
    assert crossed is True
    assert remaining == 0.0
    assert _opacity(held) == before + 1


def test_locked_drag_does_not_change_the_value() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.layers["layer_1"].locked = True
    before = _opacity(controls)

    remaining, crossed = apply_value_drag(
        controls, _OPACITY, _VALUE_DRAG_THRESHOLD_PX * 2 + 5.0, 0.0
    )

    assert crossed is True
    assert remaining == 5.0
    assert _opacity(controls) == before
    again, crossed_again = apply_value_drag(controls, _OPACITY, 0.0, remaining)
    assert crossed_again is False
    assert again == 5.0
    assert _opacity(controls) == before


def test_extreme_drags_keep_visualiser_and_column_minimums() -> None:
    minimum = MIN_COLUMN_WIDTH
    wide = 1280
    assert clamp_column_widths(wide, 0, 0, min_column=minimum) == (
        minimum,
        wide - minimum * 2,
        minimum,
    )
    for nav, insp in ((1, 1), (50_000, 40), (40, 50_000), (50_000, 50_000)):
        got_nav, viz, got_insp = clamp_column_widths(
            wide, nav, insp, min_column=minimum
        )
        assert viz >= 1
        assert got_nav >= minimum
        assert got_insp >= minimum
        assert got_nav + viz + got_insp == wide

    # Too narrow for both minimums: proportional, non-negative, visualiser lives.
    narrow = 80
    assert narrow < minimum * 2 + 1
    assert clamp_column_widths(
        narrow, 100_000, 100_000, min_column=minimum
    ) == (39, 1, 40)


def test_clamped_request_fits_again_when_the_display_grows() -> None:
    request_nav, request_insp = 400, 500
    nav, viz, insp = clamp_column_widths(
        400, request_nav, request_insp, min_column=MIN_COLUMN_WIDTH
    )
    assert viz >= 1
    assert nav >= MIN_COLUMN_WIDTH
    assert insp >= MIN_COLUMN_WIDTH
    assert (nav, insp) != (request_nav, request_insp)

    assert clamp_column_widths(
        1280, request_nav, request_insp, min_column=MIN_COLUMN_WIDTH
    ) == (request_nav, 1280 - request_nav - request_insp, request_insp)


class _Overlay:
    def __init__(self, visibility: float = 1.0) -> None:
        self.visibility = visibility

    def notify_input(self) -> None:
        return None


def _host(visibility: float = 1.0) -> ShellHost:
    overlay = _Overlay(visibility)
    editor = SimpleNamespace(
        navigator_width=DEFAULT_NAVIGATOR_WIDTH,
        inspector_width=DEFAULT_INSPECTOR_WIDTH,
    )
    controls = SimpleNamespace(
        cfg=SimpleNamespace(editor=editor),
        settings=SimpleNamespace(set_shell_column_widths=MagicMock()),
    )
    host = ShellHost(
        None,
        None,
        overlay,
        MenuBarState(),
        controls,
        (1280, 720),
        23,
    )
    host.set_layout(ShellLayout.compute(1280, 720, 23, 23, 0))
    return host


def _motion(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(
        pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)
    )


def _button(kind: int, pos: tuple[int, int], button: int = 1) -> pygame.event.Event:
    return pygame.event.Event(kind, pos=pos, button=button)


def test_splitter_drag_updates_session_widths_without_imgui_buttons() -> None:
    host = _host()
    left = (230, 100)
    right_edge = 1280 - 495
    with patch("cleave.viz.shell_host.pygame.mouse.set_cursor") as set_cursor:
        host.process_event(_motion(left))
        set_cursor.assert_called_with(pygame.SYSTEM_CURSOR_SIZEWE)
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, left))
        host.process_event(_button(pygame.MOUSEBUTTONUP, left))
        assert host.nav_width is None
        assert host._splitter is None
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, left))
        assert host._buttons == []
        assert 0 not in host._held
        assert host.nav_width is None
        assert host.insp_width is None
        assert host._value_drag_accum == 0.0
        assert host._value_drag_crossed is False

        host.process_event(_motion((400, 100)))
        assert host.nav_width == 400
        assert host._buttons == []
        nav_request = host.nav_width
        host.process_event(_button(pygame.MOUSEBUTTONUP, (400, 120)))
        assert host.nav_width is None
        assert host.insp_width is None
        assert host._splitter is None
        assert host._buttons == []

        host.process_event(_motion((right_edge, 100)))
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, (right_edge, 100)))
        host.process_event(_motion((700, 100)))
        assert host.insp_width == 1280 - 700
        insp_request = host.insp_width
        host.process_event(_button(pygame.MOUSEBUTTONUP, (700, 100)))
        assert host.insp_width is None
        assert host.nav_width is None
        assert host._buttons == []

        narrow = ShellLayout.compute(
            320,
            200,
            23,
            23,
            0,
            nav_width=nav_request,
            insp_width=insp_request,
        )
        assert nav_request == 400
        assert insp_request == 1280 - 700
        assert narrow.visualiser[2] >= 1
        assert narrow.navigator[2] >= MIN_COLUMN_WIDTH
        assert narrow.inspector[2] >= MIN_COLUMN_WIDTH
        assert narrow.navigator[2] < 400

        restored = ShellLayout.compute(
            1280,
            720,
            23,
            23,
            0,
            nav_width=nav_request,
            insp_width=insp_request,
        )
        assert restored.navigator[2] == 400
        assert restored.inspector[2] == 1280 - 700

        host.process_event(_motion((640, 400)))
        set_cursor.assert_called_with(pygame.SYSTEM_CURSOR_ARROW)


def test_splitter_drag_is_ignored_when_the_shell_is_hidden() -> None:
    host = _host(visibility=0.0)
    with patch("cleave.viz.shell_host.pygame.mouse.set_cursor"):
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, (230, 100)))
    assert host.nav_width is None
    assert host.insp_width is None
    assert host._buttons == []
    assert host._splitter is None
    host._controls.settings.set_shell_column_widths.assert_not_called()


def test_splitter_drag_release_persists_requested_widths() -> None:
    host = _host()
    left = (DEFAULT_NAVIGATOR_WIDTH, 100)
    pointer_x = 2000
    with patch("cleave.viz.shell_host.pygame.mouse.set_cursor"):
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, left))
        host.process_event(_motion((pointer_x, 100)))
        assert host.nav_width == pointer_x
        host.process_event(_button(pygame.MOUSEBUTTONUP, (pointer_x, 120)))
    fitted = ShellLayout.compute(
        1280,
        720,
        23,
        23,
        0,
        nav_width=pointer_x,
        insp_width=DEFAULT_INSPECTOR_WIDTH,
    )
    assert fitted.navigator[2] != pointer_x
    host._controls.settings.set_shell_column_widths.assert_called_once_with(
        pointer_x,
        DEFAULT_INSPECTOR_WIDTH,
    )
    assert host.nav_width is None
    assert host.insp_width is None


def test_splitter_drag_release_persists_the_other_columns_live_width() -> None:
    host = _host()
    host._insp_width = 510
    left = (DEFAULT_NAVIGATOR_WIDTH, 100)
    with patch("cleave.viz.shell_host.pygame.mouse.set_cursor"):
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, left))
        host.process_event(_motion((400, 100)))
        host.process_event(_button(pygame.MOUSEBUTTONUP, (400, 100)))
    host._controls.settings.set_shell_column_widths.assert_called_once_with(400, 510)
    assert host.nav_width is None
    assert host.insp_width is None


def test_cancelled_splitter_drag_does_not_persist() -> None:
    host = _host()
    left = (DEFAULT_NAVIGATOR_WIDTH, 100)
    with patch("cleave.viz.shell_host.pygame.mouse.set_cursor"):
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, left))
        host.process_event(_motion((400, 100)))
        assert host.nav_width == 400
        host._overlay.visibility = 0.0
        host.process_event(_button(pygame.MOUSEBUTTONUP, (400, 100)))
    host._controls.settings.set_shell_column_widths.assert_not_called()
    assert host._splitter is None
    assert host.nav_width == 400


def test_splitter_mouseup_under_one_pixel_does_not_persist() -> None:
    host = _host()
    host._insp_width = 510
    left = (DEFAULT_NAVIGATOR_WIDTH, 100)
    with patch("cleave.viz.shell_host.pygame.mouse.set_cursor"):
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, left))
        host.process_event(_button(pygame.MOUSEBUTTONUP, (left[0], left[1] + 40)))
    host._controls.settings.set_shell_column_widths.assert_not_called()
    assert host.nav_width is None
    assert host.insp_width == 510
    assert host._splitter is None


def test_clicks_outside_a_splitter_still_reach_imgui() -> None:
    host = _host()
    with patch("cleave.viz.shell_host.pygame.mouse.set_cursor"):
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, (100, 100)))
    assert host._buttons == [(0, True)]
    assert host.nav_width is None


def test_theme_exports_hover_role() -> None:
    from cleave.viz.theme import HOVER, HOVER_BG_ALPHA

    assert isinstance(HOVER, tuple)
    assert len(HOVER) == 3
    assert all(type(channel) is int for channel in HOVER)
    assert type(HOVER_BG_ALPHA) is int
    assert 0 < HOVER_BG_ALPHA <= 255


def test_splitter_hit_zone_is_six_pixels() -> None:
    assert SPLITTER_HIT_PX == 6
    layout = ShellLayout.compute(1280, 720, 23, 23, 0)
    edge = layout.navigator[2]
    assert splitter_hit(layout, edge - 3, 100) == "nav"
    assert splitter_hit(layout, edge + 2, 100) == "nav"
    assert splitter_hit(layout, edge - 4, 100) is None
    assert splitter_hit(layout, edge + 3, 100) is None
    assert splitter_hit(layout, edge, 10) is None
