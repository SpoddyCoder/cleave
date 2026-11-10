"""Sideways drag on stepped inspector values, and column splitters. No GL window."""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pygame
import pytest
from imgui_bundle import imgui

from cleave.config_schema.editor import (
    DEFAULT_HELP_WIDTH,
    DEFAULT_INSPECTOR_WIDTH,
)
from cleave.viz.focus_nav import TimelineFocus
from cleave.viz.imgui_host import ImGuiHost
from cleave.viz.menu_bar import MenuBarState
from cleave.viz.pointer_cursor import PointerShape, requested_pointer
from cleave.viz.shell_focus import CycleStop, ShellRegion
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_spec import apply_field_horizontal, row_spec
from cleave.viz.shell_host import (
    _VALUE_DRAG_THRESHOLD_PX,
    ShellHost,
    apply_value_drag,
    inspector_row_click_outcome,
    inspector_row_stepped,
    value_drag_steps,
)
from cleave.viz.value_nudge import value_parts
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


def test_plain_row_click_focuses_and_activates() -> None:
    assert inspector_row_click_outcome(
        double_click_row=False, clicked=True, activated=False, double_clicked=False
    ) == (True, True)


def test_double_click_row_only_focuses_on_a_single_click() -> None:
    assert inspector_row_click_outcome(
        double_click_row=True, clicked=True, activated=False, double_clicked=False
    ) == (True, False)


def test_double_click_row_activates_on_the_second_press() -> None:
    assert inspector_row_click_outcome(
        double_click_row=True, clicked=False, activated=True, double_clicked=True
    ) == (True, True)
    # The release after that press focuses only, so the action runs once.
    assert inspector_row_click_outcome(
        double_click_row=True, clicked=True, activated=False, double_clicked=False
    ) == (True, False)


def test_off_value_keeps_side_arrows_and_stepped_ignores_the_text() -> None:
    parts = value_parts("off", imgui.ImVec4(1.0, 1.0, 1.0, 1.0), stepped=True)
    assert [text for text, _color in parts] == ["< ", "off", " >"]

    assert tuple(inspect.signature(inspector_row_stepped).parameters) == (
        "state",
        "desc",
    )

    unlocked = _make_controls(("layer_1",))
    snap = RowDescriptor(RowKind.TIMELINE_PLACEMENT_SNAP)
    unlocked.session.timeline.placement_snap = "off"
    assert unlocked.session.timeline.locked is False
    assert inspector_row_stepped(unlocked.session, snap) is True

    unlocked.session.timeline.locked = True
    assert inspector_row_stepped(unlocked.session, snap) is False

    display = RowDescriptor(RowKind.LAYER_MANAGEMENT_COUNT)
    assert row_spec(display.kind).apply_horizontal is None
    assert inspector_row_stepped(unlocked.session, display) is False

    limiter = RowDescriptor(RowKind.POST_FX_LIMITER_ENABLED)
    assert row_spec(limiter.kind).blocked_by_section_lock is False
    unlocked.session.post_fx.locked = True
    assert inspector_row_stepped(unlocked.session, limiter) is True


def _seed_placement_snap_off(controls) -> None:
    controls.session.timeline.placement_snap = "off"


def _seed_hard_crossfade_off(controls) -> None:
    controls.session.timeline.hard_cut_fades.crossfade = False


def _seed_soft_crossfade_off(controls) -> None:
    controls.session.timeline.soft_cut_fades.crossfade = False


def _seed_compositor_hdr_off(controls) -> None:
    controls.session.project.compositor_hdr = False


def _seed_limiter_off(controls) -> None:
    controls.session.post_fx.limiter.enabled = False


def _seed_rolloff_mode_off(controls) -> None:
    controls.session.post_fx.highlight_rolloff.mode = "off"


def _seed_chroma_mode_off(controls) -> None:
    controls.session.post_fx.chroma_boost.mode = "off"


def _seed_invert_off(controls) -> None:
    controls.session.pattern_mask.invert = False


def _seed_trigger_off(controls) -> None:
    controls.session.layers["layer_1"].preset_switching_trigger = "off"


def _preset_switching_trigger(controls) -> str:
    return controls.session.layers["layer_1"].preset_switching_trigger


@pytest.mark.parametrize(
    ("desc", "seed", "read"),
    [
        pytest.param(
            RowDescriptor(RowKind.TIMELINE_PLACEMENT_SNAP),
            _seed_placement_snap_off,
            lambda controls: controls.session.timeline.placement_snap,
            id="placement_snap",
        ),
        pytest.param(
            RowDescriptor(RowKind.TIMELINE_HARD_CUT_CROSSFADE),
            _seed_hard_crossfade_off,
            lambda controls: controls.session.timeline.hard_cut_fades.crossfade,
            id="hard_cut_crossfade",
        ),
        pytest.param(
            RowDescriptor(RowKind.TIMELINE_SOFT_CUT_CROSSFADE),
            _seed_soft_crossfade_off,
            lambda controls: controls.session.timeline.soft_cut_fades.crossfade,
            id="soft_cut_crossfade",
        ),
        pytest.param(
            RowDescriptor(RowKind.PROJECT_COMPOSITOR_HDR),
            _seed_compositor_hdr_off,
            lambda controls: controls.session.project.compositor_hdr,
            id="compositor_hdr",
        ),
        pytest.param(
            RowDescriptor(RowKind.POST_FX_LIMITER_ENABLED),
            _seed_limiter_off,
            lambda controls: controls.session.post_fx.limiter.enabled,
            id="limiter_enabled",
        ),
        pytest.param(
            RowDescriptor(RowKind.POST_FX_HIGHLIGHT_ROLLOFF_MODE),
            _seed_rolloff_mode_off,
            lambda controls: controls.session.post_fx.highlight_rolloff.mode,
            id="highlight_rolloff_mode",
        ),
        pytest.param(
            RowDescriptor(RowKind.POST_FX_CHROMA_BOOST_MODE),
            _seed_chroma_mode_off,
            lambda controls: controls.session.post_fx.chroma_boost.mode,
            id="chroma_boost_mode",
        ),
        pytest.param(
            RowDescriptor(RowKind.PATTERN_MASK_INVERT),
            _seed_invert_off,
            lambda controls: controls.session.pattern_mask.invert,
            id="pattern_mask_invert",
        ),
        pytest.param(
            RowDescriptor(RowKind.TRACK_PRESET_SWITCHING_TRIGGER, slot="layer_1"),
            _seed_trigger_off,
            _preset_switching_trigger,
            id="preset_switching_trigger",
        ),
    ],
)
def test_off_value_drag_matches_one_horizontal_step(desc, seed, read) -> None:
    threshold = _VALUE_DRAG_THRESHOLD_PX
    dragged = _make_controls(("layer_1",))
    keyed = _make_controls(("layer_1",))
    seed(dragged)
    seed(keyed)
    before = read(dragged)

    remaining, crossed = apply_value_drag(dragged, desc, threshold, 0.0)
    apply_field_horizontal(keyed, desc, True, False)
    assert crossed is True
    assert remaining == 0.0
    assert read(dragged) == read(keyed)
    assert read(dragged) != before

    remaining, crossed = apply_value_drag(dragged, desc, -threshold, 0.0)
    apply_field_horizontal(keyed, desc, False, False)
    assert crossed is True
    assert remaining == 0.0
    assert read(dragged) == read(keyed)


def test_locked_placement_snap_drag_consumes_steps() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.timeline.locked = True
    controls.session.timeline.placement_snap = "off"
    desc = RowDescriptor(RowKind.TIMELINE_PLACEMENT_SNAP)

    remaining, crossed = apply_value_drag(
        controls, desc, _VALUE_DRAG_THRESHOLD_PX * 2 + 5.0, 0.0
    )

    assert crossed is True
    assert remaining == 5.0
    assert controls.session.timeline.placement_snap == "off"
    again, crossed_again = apply_value_drag(controls, desc, 0.0, remaining)
    assert crossed_again is False
    assert again == 5.0
    assert controls.session.timeline.placement_snap == "off"


def test_extreme_drags_keep_visualiser_and_column_minimums() -> None:
    minimum = MIN_COLUMN_WIDTH
    wide = 1280
    assert clamp_column_widths(wide, 0, min_column=minimum) == (
        minimum,
        wide - minimum,
        0,
    )
    for stack in (1, 50_000, 40):
        got_stack, viz, got_help = clamp_column_widths(
            wide, stack, min_column=minimum
        )
        assert viz >= 1
        assert got_stack >= minimum
        assert got_help == 0
        assert got_stack + viz + got_help == wide

    # Too narrow for the stack minimum: proportional, non-negative, visualiser lives.
    narrow = 40
    assert narrow < minimum + 1
    assert clamp_column_widths(narrow, 100_000, min_column=minimum) == (
        narrow - 1,
        1,
        0,
    )


def test_clamped_request_fits_again_when_the_display_grows() -> None:
    request_stack = 500
    stack, viz, help_w = clamp_column_widths(
        400, request_stack, min_column=MIN_COLUMN_WIDTH
    )
    assert viz >= 1
    assert stack >= MIN_COLUMN_WIDTH
    assert help_w == 0
    assert stack != request_stack

    assert clamp_column_widths(
        1280, request_stack, min_column=MIN_COLUMN_WIDTH
    ) == (request_stack, 1280 - request_stack, 0)


@contextmanager
def _host() -> Iterator[ShellHost]:
    editor = SimpleNamespace(
        inspector_width=DEFAULT_INSPECTOR_WIDTH,
        help_width=DEFAULT_HELP_WIDTH,
    )
    controls = SimpleNamespace(
        cfg=SimpleNamespace(editor=editor),
        settings=SimpleNamespace(
            set_shell_column_widths=MagicMock(),
            set_navigator_height=MagicMock(),
        ),
        set_shell_region=MagicMock(),
        disarm_value_nudge=MagicMock(),
    )
    with patch("cleave.viz.imgui_host._gl_context_current", return_value=False):
        imgui_host = ImGuiHost.create()
    host = ShellHost(
        imgui_host,
        MenuBarState(),
        controls,
        23,
    )
    host.set_layout(ShellLayout.compute(1280, 720, 23, 23, 0))
    try:
        yield host
    finally:
        host.imgui.destroy()


def _gesture_pointer(host: ShellHost) -> PointerShape:
    """The pointer the shell asks for at the last mouse position."""
    host.imgui.begin_frame(1.0 / 60.0)
    try:
        host._request_gesture_pointer()
        return requested_pointer()
    finally:
        host.imgui.end_frame()


def _motion(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(
        pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)
    )


def _button(kind: int, pos: tuple[int, int], button: int = 1) -> pygame.event.Event:
    return pygame.event.Event(kind, pos=pos, button=button)


def _stack_edge(host: ShellHost) -> int:
    layout = host.layout
    assert layout is not None
    if layout.navigator_side == "left":
        return layout.navigator[0] + layout.navigator[2]
    return layout.navigator[0]


def test_splitter_drag_updates_session_widths_without_imgui_buttons() -> None:
    with _host() as host:
        edge = _stack_edge(host)
        host.process_event(_motion((edge, 100)))
        assert _gesture_pointer(host) is PointerShape.RESIZE_EW
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, (edge, 100)))
        host.process_event(_button(pygame.MOUSEBUTTONUP, (edge, 100)))
        assert host.insp_width is None
        assert host._splitter is None
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, (edge, 100)))
        assert host.imgui.queued_buttons == []
        assert not host.imgui.button_held(0)
        assert host.insp_width is None
        assert host.help_width is None
        assert host._value_drag_accum == 0.0
        assert host._value_drag_crossed is False

        host.process_event(_motion((700, 100)))
        assert host.insp_width == 700
        assert host.imgui.queued_buttons == []
        insp_request = host.insp_width
        host.process_event(_button(pygame.MOUSEBUTTONUP, (700, 120)))
        assert host.insp_width is None
        assert host.help_width is None
        assert host._splitter is None
        assert host.imgui.queued_buttons == []

        narrow = ShellLayout.compute(
            320,
            200,
            23,
            23,
            0,
            insp_width=insp_request,
        )
        assert insp_request == 700
        assert narrow.visualiser[2] >= 1
        assert narrow.navigator[2] >= MIN_COLUMN_WIDTH
        assert narrow.inspector[2] == narrow.navigator[2]
        assert narrow.navigator[2] < insp_request

        restored = ShellLayout.compute(
            1280,
            720,
            23,
            23,
            0,
            insp_width=insp_request,
        )
        assert restored.navigator[2] == insp_request
        assert restored.inspector[2] == insp_request

        host.process_event(_motion((100, 400)))
        assert _gesture_pointer(host) is PointerShape.ARROW


def test_splitter_drag_release_persists_requested_widths() -> None:
    with _host() as host:
        edge = _stack_edge(host)
        pointer_x = 2000
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, (edge, 100)))
        host.process_event(_motion((pointer_x, 100)))
        assert host.insp_width == pointer_x
        request = host.insp_width
        host.process_event(_button(pygame.MOUSEBUTTONUP, (pointer_x, 120)))
        fitted = ShellLayout.compute(
            1280,
            720,
            23,
            23,
            0,
            insp_width=request,
        )
        assert fitted.inspector[2] != request
        host._controls.settings.set_shell_column_widths.assert_called_once_with(
            request,
            DEFAULT_HELP_WIDTH,
        )
        assert host.insp_width is None
        assert host.help_width is None


def test_splitter_drag_release_persists_the_other_columns_live_width() -> None:
    with _host() as host:
        host._help_width = 360
        edge = _stack_edge(host)
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, (edge, 100)))
        host.process_event(_motion((700, 100)))
        host.process_event(_button(pygame.MOUSEBUTTONUP, (700, 100)))
        host._controls.settings.set_shell_column_widths.assert_called_once_with(
            700, 360
        )
        assert host.insp_width is None
        assert host.help_width is None


def test_splitter_mouseup_under_one_pixel_does_not_persist() -> None:
    with _host() as host:
        host._help_width = 360
        edge = _stack_edge(host)
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, (edge, 100)))
        host.process_event(_button(pygame.MOUSEBUTTONUP, (edge, 140)))
        host._controls.settings.set_shell_column_widths.assert_not_called()
        assert host.insp_width is None
        assert host.help_width == 360
        assert host._splitter is None


def test_help_splitter_drag_persists_requested_width() -> None:
    with _host() as host:
        layout = ShellLayout.compute(
            1280, 720, 23, 23, 0, help_width=DEFAULT_HELP_WIDTH
        )
        host.set_layout(layout)
        edge = layout.help[0]
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, (edge, 100)))
        host.process_event(_motion((edge - 40, 100)))
        assert host.help_width == DEFAULT_HELP_WIDTH + 40
        assert host.insp_width is None
        host.process_event(_button(pygame.MOUSEBUTTONUP, (edge - 40, 100)))
        host._controls.settings.set_shell_column_widths.assert_called_once_with(
            DEFAULT_INSPECTOR_WIDTH,
            DEFAULT_HELP_WIDTH + 40,
        )
        assert host.help_width is None
        assert host.insp_width is None
        assert host._splitter is None


def test_help_splitter_under_one_pixel_does_not_persist() -> None:
    with _host() as host:
        layout = ShellLayout.compute(
            1280, 720, 23, 23, 0, help_width=DEFAULT_HELP_WIDTH
        )
        host.set_layout(layout)
        edge = layout.help[0]
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, (edge, 100)))
        host.process_event(_button(pygame.MOUSEBUTTONUP, (edge, 140)))
        host._controls.settings.set_shell_column_widths.assert_not_called()
        assert host.help_width is None
        assert host._splitter is None


def test_cycle_stop_stays_on_timeline_while_help_is_open() -> None:
    controls = _make_controls(("layer_1",))
    controls.session.help_visible = True
    controls.session.timeline.panel_open = True
    controls.set_shell_region(ShellRegion.TIMELINE)
    with _host() as host:
        host._controls = controls
        menu = MenuBarState()
        assert host._cycle_stop(menu) is CycleStop.TIMELINE


def test_navigator_content_height_is_measured_for_the_next_frame() -> None:
    from cleave.viz.commands import command_context
    from cleave.viz.shell_host import draw_shell_frame
    from cleave.viz.shell_layout import navigator_row_px

    controls = _make_controls(("layer_1",))
    with _host() as host:
        host._controls = controls
        host.imgui.display_size = (1280, 720)
        assert host.nav_content_height_px == 0
        draw_shell_frame(
            host, MenuBarState(), command_context(controls), 1 / 60
        )
        measured = host.nav_content_height_px
        assert measured > navigator_row_px()
        draw_shell_frame(
            host, MenuBarState(), command_context(controls), 1 / 60
        )
        assert host.nav_content_height_px == measured


def test_navigator_height_follows_rows_opened_before_the_next_draw() -> None:
    from cleave.viz.commands import command_context
    from cleave.viz.shell_host import draw_shell_frame

    controls = _make_controls(("layer_1",))
    with _host() as host:
        host._controls = controls
        host.imgui.display_size = (1280, 720)
        controls.shell_focus.nav_expanded.clear()
        draw_shell_frame(host, MenuBarState(), command_context(controls), 1 / 60)
        closed = host.nav_content_height_px
        controls.shell_focus.nav_expanded.add("post_fx")
        predicted = host.nav_content_height_px
        assert predicted > closed
        draw_shell_frame(host, MenuBarState(), command_context(controls), 1 / 60)
        assert predicted - host.nav_content_height_px in (0, 1)


def test_chrome_contains_open_help_column() -> None:
    with _host() as host:
        layout = ShellLayout.compute(
            1280, 720, 23, 23, 0, help_width=DEFAULT_HELP_WIDTH
        )
        host.set_layout(layout)
        x, y, w, h = layout.help
        assert host._chrome_contains(x + w / 2, y + h / 2)
        closed = ShellLayout.compute(1280, 720, 23, 23, 0, help_width=0)
        host.set_layout(closed)
        vx, vy, vw, vh = closed.visualiser
        assert not host._chrome_contains(vx + vw / 2, vy + vh / 2)


def test_clicks_outside_a_splitter_still_reach_imgui() -> None:
    with _host() as host:
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, (100, 100)))
        assert host.imgui.queued_buttons == [(0, True)]
        assert host.insp_width is None


def test_theme_exports_hover_role() -> None:
    from cleave.viz.theme import HOVER, HOVER_BG_ALPHA

    assert isinstance(HOVER, tuple)
    assert len(HOVER) == 3
    assert all(type(channel) is int for channel in HOVER)
    assert type(HOVER_BG_ALPHA) is int
    assert 0 < HOVER_BG_ALPHA <= 255


def _rect_center(rect: tuple[int, int, int, int]) -> tuple[int, int]:
    x, y, w, h = rect
    return (x + w // 2, y + max(h, 1) // 2)


def _open_strip_layout() -> ShellLayout:
    return ShellLayout.compute(1280, 720, 23, 23, 80)


def _click(host: ShellHost, pos: tuple[int, int]) -> None:
    host.process_event(_button(pygame.MOUSEBUTTONDOWN, pos))


def test_click_in_timeline_rect_sets_timeline_region() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.session.timeline.panel_open = True
    controls.session.timeline.focus_row = 1
    with _host() as host:
        host._controls = controls
        layout = _open_strip_layout()
        host.set_layout(layout)

        _click(host, _rect_center(layout.timeline))

        assert controls.shell_focus.region is ShellRegion.TIMELINE
        assert controls.session.timeline.panel_open is True
        assert controls.focus_cursor == TimelineFocus(1)
        assert host.imgui.queued_buttons == [(0, True)]


def test_click_in_navigator_sets_navigator_and_keeps_strip_open() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.open_timeline_panel(enter_submenu=True)
    with _host() as host:
        host._controls = controls
        layout = _open_strip_layout()
        host.set_layout(layout)

        _click(host, _rect_center(layout.navigator))

        assert controls.shell_focus.region is ShellRegion.NAVIGATOR
        assert controls.session.timeline.panel_open is True


def test_click_in_inspector_sets_inspector_and_keeps_strip_open() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.open_timeline_panel(enter_submenu=True)
    with _host() as host:
        host._controls = controls
        layout = _open_strip_layout()
        host.set_layout(layout)

        _click(host, _rect_center(layout.inspector))

        assert controls.shell_focus.region is ShellRegion.INSPECTOR
        assert controls.session.timeline.panel_open is True


def test_click_in_help_leaves_the_region() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.open_timeline_panel(enter_submenu=True)
    controls.set_timeline_focus_row(1)
    controls.session.help_visible = True
    with _host() as host:
        host._controls = controls
        layout = ShellLayout.compute(
            1280, 720, 23, 23, 80, help_width=DEFAULT_HELP_WIDTH
        )
        host.set_layout(layout)

        _click(host, _rect_center(layout.help))

        assert controls.shell_focus.region is ShellRegion.TIMELINE
        assert controls.focus_cursor == TimelineFocus(1)
        assert controls.session.timeline.panel_open is True
        assert controls.session.help_visible is True
        assert host.imgui.queued_buttons == [(0, True)]


def test_click_in_visualiser_or_menu_does_not_change_region() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.open_timeline_panel(enter_submenu=True)
    with _host() as host:
        host._controls = controls
        layout = _open_strip_layout()
        host.set_layout(layout)

        _click(host, _rect_center(layout.visualiser))
        assert controls.shell_focus.region is ShellRegion.TIMELINE
        assert controls.session.timeline.panel_open is True

        _click(host, _rect_center(layout.menu))
        assert controls.shell_focus.region is ShellRegion.TIMELINE
        assert controls.session.timeline.panel_open is True

        _click(host, _rect_center(layout.transport))
        assert controls.shell_focus.region is ShellRegion.TIMELINE
        assert controls.session.timeline.panel_open is True


def test_splitter_hit_zone_is_six_pixels() -> None:
    assert SPLITTER_HIT_PX == 6
    layout = ShellLayout.compute(1280, 720, 23, 23, 0)
    edge = layout.navigator[0] + layout.navigator[2]
    assert splitter_hit(layout, edge - 3, 100) == "insp"
    assert splitter_hit(layout, edge + 2, 100) == "insp"
    assert splitter_hit(layout, edge - 4, 100) is None
    assert splitter_hit(layout, edge + 3, 100) is None
    assert splitter_hit(layout, edge, 10) is None
    assert splitter_hit(layout, edge, layout.inspector[1] + 4) == "insp"


def _nav_boundary(host: ShellHost) -> tuple[int, int]:
    layout = host.layout
    assert layout is not None
    return (layout.navigator[0] + layout.navigator[2] // 2, layout.inspector[1])


def test_nav_splitter_drag_sets_and_persists_navigator_height() -> None:
    with _host() as host:
        x, y = _nav_boundary(host)
        top = host.layout.navigator[1]
        host.process_event(_motion((x, y)))
        assert _gesture_pointer(host) is PointerShape.RESIZE_NS
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, (x, y)))
        assert host.imgui.queued_buttons == []
        host.process_event(_motion((x + 30, top + 300)))
        assert host.navigator_height == 300
        assert host.insp_width is None
        host.process_event(_button(pygame.MOUSEBUTTONUP, (x + 30, top + 300)))
        host._controls.settings.set_navigator_height.assert_called_once_with(300)
        host._controls.settings.set_shell_column_widths.assert_not_called()
        assert host.navigator_height is None
        assert host._splitter is None


def test_nav_splitter_under_one_pixel_does_not_persist() -> None:
    with _host() as host:
        x, y = _nav_boundary(host)
        host.process_event(_button(pygame.MOUSEBUTTONDOWN, (x, y)))
        host.process_event(_button(pygame.MOUSEBUTTONUP, (x + 40, y)))
        host._controls.settings.set_navigator_height.assert_not_called()
        assert host._splitter is None


def test_strip_pointer_gets_press_drag_and_release_in_timeline_rect() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.session.timeline.panel_open = True
    pointer = MagicMock()
    with _host() as host:
        host._controls = controls
        host._strip_pointer = pointer
        layout = _open_strip_layout()
        host.set_layout(layout)
        pos = _rect_center(layout.timeline)

        _click(host, pos)
        host.process_event(_motion((pos[0] + 30, pos[1])))
        host.process_event(_button(pygame.MOUSEBUTTONUP, pos))

        assert controls.shell_focus.region is ShellRegion.TIMELINE
        pointer.press.assert_called_once_with(float(pos[0]), float(pos[1]))
        pointer.motion.assert_called_with(float(pos[0] + 30), float(pos[1]))
        pointer.release.assert_called_once()


def test_strip_pointer_ignores_clicks_outside_strip_or_when_closed() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.session.timeline.panel_open = True
    pointer = MagicMock()
    with _host() as host:
        host._controls = controls
        host._strip_pointer = pointer
        layout = _open_strip_layout()
        host.set_layout(layout)

        _click(host, _rect_center(layout.navigator))
        controls.session.timeline.panel_open = False
        _click(host, _rect_center(layout.timeline))

        pointer.press.assert_not_called()


def test_strip_pointer_cancels_when_window_loses_focus() -> None:
    pointer = MagicMock()
    with _host() as host:
        host._strip_pointer = pointer
        host.process_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        pointer.cancel.assert_called_once()


def _strip_host(host: ShellHost, *, hover=None, over_ruler=False, scrubbing=False):
    host._strip_pointer = SimpleNamespace(
        over_ruler=over_ruler,
        scrubbing=scrubbing,
        hover_pressable=hover is not None and hover != ("eye", 3),
    )
    host._controls.session = SimpleNamespace(
        timeline=SimpleNamespace(panel_open=True, strip_hover=hover)
    )
    return host


def test_strip_buttons_ask_for_the_hand_and_the_ruler_for_left_right() -> None:
    with _host() as host:
        host.imgui.process_mouse_event(_motion((640, 400)))
        _strip_host(host)
        assert _gesture_pointer(host) is PointerShape.ARROW
        _strip_host(host, hover=("record", None))
        assert _gesture_pointer(host) is PointerShape.HAND
        _strip_host(host, hover=("label", 1))
        assert _gesture_pointer(host) is PointerShape.HAND
        _strip_host(host, hover=("eye", 3))
        assert _gesture_pointer(host) is PointerShape.ARROW
        _strip_host(host, over_ruler=True)
        assert _gesture_pointer(host) is PointerShape.RESIZE_EW
        _strip_host(host, hover=("eye", 0), scrubbing=True)
        assert _gesture_pointer(host) is PointerShape.RESIZE_EW
        host._controls.session.timeline.panel_open = False
        assert _gesture_pointer(host) is PointerShape.ARROW


def test_modal_keeps_the_splitter_and_strip_pointers_away() -> None:
    with _host() as host:
        edge = _stack_edge(host)
        host.imgui.process_mouse_event(_motion((edge, 100)))
        _strip_host(host, hover=("play", None))
        assert _gesture_pointer(host) is PointerShape.RESIZE_EW
        host._controls.modal_host = SimpleNamespace(active=True)
        assert _gesture_pointer(host) is PointerShape.ARROW
