"""Headless ModalSurface: z-order, kinds, and pointer intents. No GL window."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pygame
import pytest
from imgui_bundle import imgui

from cleave.viz.commands import CommandContext
from cleave.viz.imgui_theme import rgba
from cleave.viz.menu_bar import MenuBarState
from cleave.viz.modal import (
    ModalHost,
    ModalKind,
    ModalLabeledLine,
    ModalOption,
    ModalViewState,
    TextFocusRegion,
    caret_line_column,
)
from cleave.viz.modal_layout import (
    EDITING_HINT,
    TEXT_BUTTON_LABELS,
    caret_index_at_point,
    measure_panel,
    measure_text_panel,
    single_line_scroll_x,
    text_field_lines,
    text_max_field_lines,
    visible_field_lines,
)
from cleave.viz.modal_surface import (
    ImGuiTextMeasure,
    ModalPointerIntent,
    ModalPointerKind,
    ModalSurface,
    apply_modal_pointer,
)
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.shell_layout import ShellLayout
from cleave.viz.theme import (
    DISABLED,
    FOCUS_ROW_BG_ALPHA,
    HIGHLIGHT,
    LABEL,
    VALUE,
    tuning_ui_metrics,
)

Rect = tuple[int, int, int, int]


class _Overlay:
    def __init__(self) -> None:
        self.visibility = 1.0

    def notify_input(self) -> None:
        return None


def _content_names() -> list[str]:
    lists = list(imgui.get_draw_data().cmd_lists)
    names = [
        str(draw_list._owner_name)
        for draw_list in lists
        if "Foreground" not in str(draw_list._owner_name)
    ]
    del lists
    return names


@contextmanager
def _host() -> Iterator[object]:
    from cleave.viz import imgui_host
    from cleave.viz.imgui_host import ImGuiHost
    from cleave.viz.shell_host import ShellHost, menu_bar_height_px

    controls = SimpleNamespace(
        session=SimpleNamespace(layer_z_order=()),
        shell_focus=SimpleNamespace(region=ShellRegion.NAVIGATOR),
        build_view_state=lambda **_kwargs: None,
        set_shell_region=MagicMock(),
        modal_host=ModalHost(),
    )
    with patch.object(imgui_host, "_gl_context_current", return_value=False):
        host = ShellHost(
            ImGuiHost.create(),
            _Overlay(),
            MenuBarState(),
            controls,
            menu_bar_height_px(),
        )
    host.imgui.display_size = (1280, 720)
    height = host.menu_bar_height_px
    host.set_layout(ShellLayout.compute(1280, 720, height, height, 0))
    host._draw_navigator = lambda: None
    host._draw_inspector = lambda _state: None
    try:
        yield host
    finally:
        try:
            # Destroying a context after a single frame breaks the next one.
            _draw(host)
            _draw(host)
        finally:
            host.imgui.destroy()


def _draw(host: object) -> None:
    from cleave.viz.shell_host import draw_shell_frame

    draw_shell_frame(host, host._menu_state, CommandContext(), 1.0, 1.0 / 60.0)


def _motion(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(
        pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)
    )


def _button(pos: tuple[int, int]) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)


def _assert_shell_before(names: list[str], later: str) -> None:
    later_at = names.index(later)
    for name in (
        "##MainMenuBar",
        "##shell-transport",
        "##shell-navigator",
        "##shell-inspector",
        "##shell-chrome",
    ):
        assert names.index(name) < later_at, names


def _center(rect: Rect) -> tuple[int, int]:
    x, y, width, height = rect
    return (x + width // 2, y + height // 2)


def _above(rect: Rect) -> tuple[int, int]:
    x, y, width, _height = rect
    return (x + width // 2, y - 1)


def _glyphs(text: str) -> int:
    """ImGui emits no quad for a space, and four vertices for every other glyph."""
    return sum(1 for char in text if char != " ")


def _pack(role: tuple[int, int, int], alpha: float = 1.0) -> int:
    return int(imgui.get_color_u32(rgba(role, alpha)))


def _color_counts() -> dict[int, int]:
    found: dict[int, int] = {}
    for draw_list in imgui.get_draw_data().cmd_lists:
        if str(draw_list._owner_name) != "##modal":
            continue
        for index in range(draw_list.vtx_buffer.size()):
            color = int(draw_list.vtx_buffer[index].col)
            found[color] = found.get(color, 0) + 1
    return found


def _field_clip_elems(field: Rect) -> int:
    total = 0
    matched = False
    for draw_list in imgui.get_draw_data().cmd_lists:
        if str(draw_list._owner_name) != "##modal":
            continue
        for index in range(draw_list.cmd_buffer.size()):
            clip = draw_list.cmd_buffer[index].clip_rect
            if (
                abs(clip.x - field[0]) <= 1
                and abs(clip.y - field[1]) <= 1
                and abs(clip.z - (field[0] + field[2])) <= 1
                and abs(clip.w - (field[1] + field[3])) <= 1
            ):
                matched = True
                total += int(draw_list.cmd_buffer[index].elem_count)
    assert matched, field
    return total


def _contains(rect: Rect, x: int, y: int) -> bool:
    rx, ry, rw, rh = rect
    return rw > 0 and rh > 0 and rx <= x < rx + rw and ry <= y < ry + rh


def _idle(host: object, surface: ModalSurface) -> None:
    host.process_event(_motion((0, 0)))
    host.top_layer.push(surface)
    _draw(host)


def _pointer(host: object, surface: ModalSurface, pos: tuple[int, int], *, click: bool) -> None:
    host.process_event(_motion(pos))
    if click:
        host.process_event(_button(pos))
    host.top_layer.push(surface)
    _draw(host)


def _yes_no() -> ModalViewState:
    return ModalViewState(
        kind=ModalKind.YES_NO,
        message="Save changes?",
        options=("Yes", "No"),
        focus_index=0,
    )


def _choice() -> ModalViewState:
    return ModalViewState(
        kind=ModalKind.CHOICE,
        message="Pick a layer",
        options=("Drums", "Bass", "Other"),
        focus_index=0,
    )


def _unsaved() -> ModalViewState:
    return ModalViewState(
        kind=ModalKind.UNSAVED_QUIT,
        message="Unsaved changes - save changes before exit?",
        options=("Save", "Don't Save", "Cancel"),
        focus_index=0,
    )


def _progress() -> ModalViewState:
    return ModalViewState(
        kind=ModalKind.PROGRESS,
        message="Rendering",
        options=(),
        focus_index=0,
        labeled_lines=(ModalLabeledLine("Stem", "drums"),),
        progress_fraction=0.5,
    )


def _text() -> ModalViewState:
    return ModalViewState(
        kind=ModalKind.TEXT,
        message=None,
        options=(),
        focus_index=0,
        cta="Preset name",
        draft="Hello",
        single_line=True,
        editing=True,
        caret_index=len("Hello"),
        focus_region=TextFocusRegion.FIELD,
        button_index=0,
        caret_visible=True,
    )


def test_modal_draws_after_shell_and_scrim() -> None:
    with _host() as host:
        host.top_layer.push(ModalSurface(_yes_no(), ImGuiTextMeasure()))
        _draw(host)
        names = _content_names()
        _assert_shell_before(names, "##top-scrim")
        assert names.index("##top-scrim") < names.index("##modal"), names
        del names
        window = imgui.internal.find_window_by_name("##modal")
        assert window is not None
        flags = int(window.flags)
        for name in (
            "no_title_bar",
            "no_resize",
            "no_move",
            "no_saved_settings",
            "no_nav",
        ):
            assert flags & int(getattr(imgui.WindowFlags_, name)), name
    assert not imgui.get_current_context()


@pytest.mark.parametrize(
    "view",
    [_yes_no(), _choice(), _unsaved(), _progress(), _text()],
    ids=["yes_no", "choice", "unsaved_quit", "progress", "text"],
)
def test_kind_renders_with_idle_mouse(view: ModalViewState) -> None:
    with _host() as host:
        surface = ModalSurface(view, ImGuiTextMeasure())
        _idle(host, surface)
        names = _content_names()
        assert "##modal" in names
        del names
        assert surface.intent is None
        assert surface.panel_rect is not None
        assert not _contains(surface.panel_rect, 0, 0)
        screen_w, screen_h = host.imgui.display_size
        line_gap = tuning_ui_metrics().line_gap
        if view.kind == ModalKind.TEXT:
            expected = measure_text_panel(
                surface.measure,
                view,
                line_gap=line_gap,
                screen_w=screen_w,
                screen_h=screen_h,
            )
        else:
            expected = measure_panel(
                surface.measure, view, line_gap=line_gap, screen_w=screen_w
            )
        assert surface.panel_rect[2:] == expected
        assert abs(surface.panel_rect[0] - (screen_w - expected[0]) // 2) <= 1
        assert abs(surface.panel_rect[1] - (screen_h - expected[1]) // 2) <= 1
        colors = _color_counts()
        wash = _pack(HIGHLIGHT, FOCUS_ROW_BG_ALPHA / 255.0)
        assert colors.get(_pack(LABEL), 0) > 0
        if view.kind == ModalKind.TEXT:
            assert colors.get(_pack(DISABLED), 0) == 4 * (
                _glyphs(EDITING_HINT) + sum(_glyphs(label) for label in TEXT_BUTTON_LABELS)
            )
            assert colors.get(_pack(HIGHLIGHT), 0) == 4
            assert wash not in colors
        elif view.kind == ModalKind.PROGRESS:
            assert colors.get(_pack(LABEL), 0) == 4 * (
                _glyphs(view.message or "")
                + sum(_glyphs(line.prefix()) for line in view.labeled_lines)
            )
            assert _pack(HIGHLIGHT) not in colors
            assert wash not in colors
        else:
            focused = view.options[view.focus_index]
            assert colors.get(_pack(HIGHLIGHT), 0) == 4 * _glyphs(focused)
            assert colors.get(wash, 0) == 4
            assert colors.get(_pack(VALUE), 0) > 0
        if view.kind == ModalKind.TEXT:
            assert surface.text_field_rect is not None
            assert len(surface.text_button_rects) == 2
            assert surface.option_rects == ()
        elif view.kind == ModalKind.PROGRESS:
            assert surface.option_rects == ()
            assert surface.text_field_rect is None
        else:
            assert len(surface.option_rects) == len(view.options)


def test_click_option_activates_that_index() -> None:
    with _host() as host:
        surface = ModalSurface(_choice(), ImGuiTextMeasure())
        _idle(host, surface)
        assert len(surface.option_rects) == 3
        _pointer(host, surface, _center(surface.option_rects[2]), click=True)
        assert surface.intent == ModalPointerIntent(
            ModalPointerKind.ACTIVATE_OPTION, index=2
        )


def test_click_option_runs_action_once_after_the_frame() -> None:
    ran: list[str] = []
    modal = ModalHost()
    modal.prompt_choice(
        "Pick a layer",
        [
            ModalOption("Drums", lambda: ran.append("drums")),
            ModalOption("Bass", lambda: ran.append("bass")),
            ModalOption("Other", lambda: ran.append("other")),
        ],
    )
    view = modal.view_state()
    assert view is not None
    with _host() as host:
        surface = ModalSurface(view, ImGuiTextMeasure())
        _idle(host, surface)
        _pointer(host, surface, _center(surface.option_rects[2]), click=True)
        assert ran == []
        assert modal.active
        apply_modal_pointer(modal, surface.intent)
    assert ran == ["other"]
    assert not modal.active


def test_hover_option_records_that_index() -> None:
    with _host() as host:
        surface = ModalSurface(_choice(), ImGuiTextMeasure())
        _idle(host, surface)
        _pointer(host, surface, _center(surface.option_rects[1]), click=False)
        assert surface.intent == ModalPointerIntent(
            ModalPointerKind.HOVER_OPTION, index=1
        )


@pytest.mark.parametrize(
    "view",
    [_yes_no(), _choice(), _unsaved(), _text()],
    ids=["yes_no", "choice", "unsaved_quit", "text"],
)
def test_click_outside_cancels(view: ModalViewState) -> None:
    with _host() as host:
        surface = ModalSurface(view, ImGuiTextMeasure())
        _idle(host, surface)
        assert surface.panel_rect is not None
        _pointer(host, surface, _above(surface.panel_rect), click=True)
        assert surface.intent == ModalPointerIntent(ModalPointerKind.CANCEL)


def test_click_outside_progress_records_nothing() -> None:
    with _host() as host:
        surface = ModalSurface(_progress(), ImGuiTextMeasure())
        _idle(host, surface)
        assert surface.panel_rect is not None
        assert surface.option_rects == ()
        _pointer(host, surface, _above(surface.panel_rect), click=True)
        assert surface.intent is None


def test_click_inside_progress_records_nothing() -> None:
    with _host() as host:
        surface = ModalSurface(_progress(), ImGuiTextMeasure())
        _idle(host, surface)
        assert surface.panel_rect is not None
        _pointer(host, surface, _center(surface.panel_rect), click=True)
        assert surface.intent is None


def test_click_inside_miss_records_nothing() -> None:
    with _host() as host:
        surface = ModalSurface(_yes_no(), ImGuiTextMeasure())
        _idle(host, surface)
        panel = surface.panel_rect
        assert panel is not None
        point = (panel[0] + panel[2] // 2, panel[1] + 1)
        assert _contains(panel, point[0], point[1])
        assert all(not _contains(rect, point[0], point[1]) for rect in surface.option_rects)
        _pointer(host, surface, point, click=True)
        assert surface.intent is None


def test_click_text_field_places_caret_at_prefix() -> None:
    view = _text()
    with _host() as host:
        surface = ModalSurface(view, ImGuiTextMeasure())
        _idle(host, surface)
        field = surface.text_field_rect
        assert field is not None
        prefix = "Hel"
        local_x = surface.measure.size(prefix)[0]
        local_y = 1
        scroll = single_line_scroll_x(
            surface.measure,
            view.draft or "",
            view.caret_index,
            field[2],
        )
        assert scroll == 0
        screen_w = int(host.imgui.display_size[0])
        expected = caret_index_at_point(
            view.draft or "",
            text_field_lines(surface.measure, view, screen_w=screen_w),
            0,
            local_x,
            local_y,
            surface.measure,
            tuning_ui_metrics().line_gap,
            scroll,
        )
        _pointer(host, surface, (field[0] + local_x, field[1] + local_y), click=True)
        assert surface.intent == ModalPointerIntent(
            ModalPointerKind.FOCUS_TEXT_FIELD, caret_index=expected
        )
        assert expected == len(prefix)


def test_click_confirm_activates_text_button() -> None:
    with _host() as host:
        surface = ModalSurface(_text(), ImGuiTextMeasure())
        _idle(host, surface)
        assert len(surface.text_button_rects) == 2
        _pointer(host, surface, _center(surface.text_button_rects[0]), click=True)
        assert surface.intent == ModalPointerIntent(
            ModalPointerKind.ACTIVATE_TEXT_BUTTON, index=0
        )


def test_apply_modal_pointer_dispatches_each_kind() -> None:
    host = MagicMock()
    apply_modal_pointer(host, None)
    host.hover_option.assert_not_called()
    host.activate_option.assert_not_called()
    host.cancel.assert_not_called()
    host.focus_text_field.assert_not_called()
    host.hover_text_field.assert_not_called()
    host.hover_text_button.assert_not_called()
    host.activate_text_button.assert_not_called()

    apply_modal_pointer(
        host, ModalPointerIntent(ModalPointerKind.HOVER_OPTION, index=1)
    )
    host.hover_option.assert_called_once_with(1)
    apply_modal_pointer(
        host, ModalPointerIntent(ModalPointerKind.ACTIVATE_OPTION, index=0)
    )
    host.activate_option.assert_called_once_with(0)
    apply_modal_pointer(host, ModalPointerIntent(ModalPointerKind.CANCEL))
    host.cancel.assert_called_once_with()
    apply_modal_pointer(
        host,
        ModalPointerIntent(ModalPointerKind.FOCUS_TEXT_FIELD, caret_index=3),
    )
    host.focus_text_field.assert_called_once_with(3)
    apply_modal_pointer(host, ModalPointerIntent(ModalPointerKind.HOVER_TEXT_FIELD))
    host.hover_text_field.assert_called_once_with()
    apply_modal_pointer(
        host, ModalPointerIntent(ModalPointerKind.HOVER_TEXT_BUTTON, index=1)
    )
    host.hover_text_button.assert_called_once_with(1)
    apply_modal_pointer(
        host, ModalPointerIntent(ModalPointerKind.ACTIVATE_TEXT_BUTTON, index=0)
    )
    host.activate_text_button.assert_called_once_with(0)

    ran: list[str] = []
    modal = ModalHost()
    modal.prompt_yes_no("Save?", on_confirm=lambda: ran.append("yes"))
    apply_modal_pointer(
        modal, ModalPointerIntent(ModalPointerKind.ACTIVATE_OPTION, index=0)
    )
    assert ran == ["yes"]
    assert not modal.active

    modal.prompt_yes_no("Save?", on_confirm=lambda: None)
    apply_modal_pointer(modal, ModalPointerIntent(ModalPointerKind.CANCEL))
    assert not modal.active

    modal.prompt_text("Name", "hello", on_confirm=lambda _draft: None)
    modal.handle_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0))
    assert modal.view_state() is not None
    assert modal.view_state().editing is False
    apply_modal_pointer(
        modal,
        ModalPointerIntent(ModalPointerKind.FOCUS_TEXT_FIELD, caret_index=2),
    )
    focused = modal.view_state()
    assert focused is not None
    assert focused.editing is True
    assert focused.caret_index == 2

    modal.prompt_progress("Rendering...", fraction=0.4)
    apply_modal_pointer(modal, ModalPointerIntent(ModalPointerKind.CANCEL))
    progress = modal.view_state()
    assert modal.active
    assert progress is not None
    assert progress.kind == ModalKind.PROGRESS
    assert progress.progress_fraction == 0.4


def test_navigator_click_does_not_set_shell_region() -> None:
    with _host() as host:
        host.top_layer.push(ModalSurface(_yes_no(), ImGuiTextMeasure()))
        _draw(host)
        assert host.top_layer.modal_active
        layout = host.layout
        assert layout is not None
        nav_x, nav_y, nav_w, nav_h = layout.navigator
        navigator = (nav_x + nav_w - 1, nav_y + nav_h // 2)
        with patch("cleave.viz.shell_host.pygame.mouse.set_cursor") as set_cursor:
            host.process_event(_button(navigator))
            assert host.imgui.queued_buttons == [(0, True)]
            assert host._splitter is None
            set_cursor.assert_not_called()
        host._controls.set_shell_region.assert_not_called()


def test_modal_host_active_routes_navigator_click_before_draw() -> None:
    with _host() as host:
        host._controls.modal_host.prompt_yes_no("Save?", on_confirm=lambda: None)
        assert host._controls.modal_host.active
        assert not host.top_layer.modal_active
        layout = host.layout
        assert layout is not None
        nav_x, nav_y, nav_w, nav_h = layout.navigator
        navigator = (nav_x + nav_w - 1, nav_y + nav_h // 2)
        host.process_event(_button(navigator))
        assert host.imgui.queued_buttons == [(0, True)]
        host._controls.set_shell_region.assert_not_called()


def test_right_click_does_not_activate_or_cancel() -> None:
    with _host() as host:
        surface = ModalSurface(_choice(), ImGuiTextMeasure())
        _idle(host, surface)
        option = _center(surface.option_rects[1])
        host.process_event(_motion(option))
        host.process_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=option, button=3))
        host.top_layer.push(surface)
        _draw(host)
        assert surface.intent == ModalPointerIntent(
            ModalPointerKind.HOVER_OPTION, index=1
        )
        outside = _above(surface.panel_rect)
        assert surface.panel_rect is not None
        host.process_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=option, button=3))
        host.process_event(_motion(outside))
        host.process_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=outside, button=3)
        )
        host.top_layer.push(surface)
        _draw(host)
        assert surface.intent is None


def test_click_scrolled_field_uses_scroll_and_clip() -> None:
    draft = "W" * 80
    view = ModalViewState(
        kind=ModalKind.TEXT,
        message=None,
        options=(),
        focus_index=0,
        cta="Name",
        draft=draft,
        single_line=True,
        editing=True,
        caret_index=len(draft),
        focus_region=TextFocusRegion.FIELD,
        button_index=0,
        caret_visible=True,
    )
    with _host() as host:
        surface = ModalSurface(view, ImGuiTextMeasure())
        _idle(host, surface)
        field = surface.text_field_rect
        assert field is not None
        assert surface.measure.size(draft)[0] > field[2]
        assert _field_clip_elems(field) > 0
        scroll = single_line_scroll_x(
            surface.measure, draft, view.caret_index, field[2]
        )
        assert scroll > 0
        local_x, local_y = 2, 1
        screen_w = int(host.imgui.display_size[0])
        lines = text_field_lines(surface.measure, view, screen_w=screen_w)
        line_gap = tuning_ui_metrics().line_gap
        expected = caret_index_at_point(
            draft, lines, 0, local_x, local_y, surface.measure, line_gap, scroll
        )
        unscrolled = caret_index_at_point(
            draft, lines, 0, local_x, local_y, surface.measure, line_gap, 0
        )
        assert expected != unscrolled
        _pointer(host, surface, (field[0] + local_x, field[1] + local_y), click=True)
        assert surface.intent == ModalPointerIntent(
            ModalPointerKind.FOCUS_TEXT_FIELD, caret_index=expected
        )


def test_click_multiline_field_uses_visible_window() -> None:
    lines = [f"line{index:02d}xxxx" for index in range(40)]
    draft = "\n".join(lines)
    view = ModalViewState(
        kind=ModalKind.TEXT,
        message=None,
        options=(),
        focus_index=0,
        cta="Body",
        draft=draft,
        single_line=False,
        editing=True,
        caret_index=len(draft),
        focus_region=TextFocusRegion.FIELD,
        button_index=0,
        caret_visible=True,
    )
    with _host() as host:
        surface = ModalSurface(view, ImGuiTextMeasure())
        _idle(host, surface)
        field = surface.text_field_rect
        assert field is not None
        screen_w = int(host.imgui.display_size[0])
        screen_h = int(host.imgui.display_size[1])
        measure = surface.measure
        line_gap = tuning_ui_metrics().line_gap
        line_h = measure.get_linesize()
        field_lines = text_field_lines(measure, view, screen_w=screen_w)
        caret_line, _column = caret_line_column(draft, field_lines, view.caret_index)
        max_lines = text_max_field_lines(
            line_h=line_h,
            line_gap=line_gap,
            screen_h=screen_h,
            cta_line_count=2,
            has_error=False,
        )
        visible, visual = visible_field_lines(field_lines, caret_line, max_lines)
        clamped = max(0, min(caret_line, max(0, len(field_lines) - 1)))
        visible_start = clamped - visual
        assert visible_start > 0
        assert len(visible) < len(field_lines)
        local_x = measure.size(visible[1][:3])[0]
        local_y = (line_h + line_gap) + line_h // 2
        assert local_y < field[3]
        expected = caret_index_at_point(
            draft,
            field_lines,
            visible_start,
            local_x,
            local_y,
            measure,
            line_gap,
            0,
        )
        from_first_line = caret_index_at_point(
            draft, field_lines, 0, local_x, local_y, measure, line_gap, 0
        )
        assert expected != from_first_line
        _pointer(host, surface, (field[0] + local_x, field[1] + local_y), click=True)
        assert surface.intent == ModalPointerIntent(
            ModalPointerKind.FOCUS_TEXT_FIELD, caret_index=expected
        )


def test_caret_quad_follows_caret_visible() -> None:
    hidden = ModalViewState(
        kind=ModalKind.TEXT,
        message=None,
        options=(),
        focus_index=0,
        cta="Name",
        draft="Hello",
        single_line=True,
        editing=True,
        caret_index=5,
        focus_region=TextFocusRegion.FIELD,
        button_index=0,
        caret_visible=False,
    )
    shown = ModalViewState(
        kind=ModalKind.TEXT,
        message=None,
        options=(),
        focus_index=0,
        cta="Name",
        draft="Hello",
        single_line=True,
        editing=True,
        caret_index=5,
        focus_region=TextFocusRegion.FIELD,
        button_index=0,
        caret_visible=True,
    )
    with _host() as host:
        surface = ModalSurface(hidden, ImGuiTextMeasure())
        _idle(host, surface)
        field = surface.text_field_rect
        assert field is not None
        hidden_elems = _field_clip_elems(field)
        assert _color_counts().get(_pack(HIGHLIGHT), 0) == 0
        surface = ModalSurface(shown, ImGuiTextMeasure())
        _idle(host, surface)
        field = surface.text_field_rect
        assert field is not None
        assert _field_clip_elems(field) == hidden_elems + 6
        assert _color_counts().get(_pack(HIGHLIGHT), 0) == 4


def test_text_button_colours_follow_focus() -> None:
    navigating = ModalViewState(
        kind=ModalKind.TEXT,
        message=None,
        options=(),
        focus_index=0,
        cta="Preset name",
        draft="Hello",
        single_line=True,
        editing=False,
        caret_index=0,
        focus_region=TextFocusRegion.FIELD,
        button_index=0,
        caret_visible=False,
    )
    confirming = ModalViewState(
        kind=ModalKind.TEXT,
        message=None,
        options=(),
        focus_index=0,
        cta="Preset name",
        draft="Hello",
        single_line=True,
        editing=False,
        caret_index=0,
        focus_region=TextFocusRegion.BUTTONS,
        button_index=0,
        caret_visible=False,
    )
    with _host() as host:
        surface = ModalSurface(navigating, ImGuiTextMeasure())
        _idle(host, surface)
        colors = _color_counts()
        wash = _pack(HIGHLIGHT, FOCUS_ROW_BG_ALPHA / 255.0)
        assert colors.get(_pack(DISABLED), 0) == 4 * sum(
            _glyphs(label) for label in TEXT_BUTTON_LABELS
        )
        assert colors.get(wash, 0) == 4
        assert _pack(HIGHLIGHT) not in colors
        _pointer(host, surface, _center(surface.text_field_rect), click=False)
        assert surface.intent == ModalPointerIntent(ModalPointerKind.HOVER_TEXT_FIELD)

        surface = ModalSurface(confirming, ImGuiTextMeasure())
        _idle(host, surface)
        colors = _color_counts()
        assert _pack(DISABLED) not in colors
        assert colors.get(_pack(HIGHLIGHT), 0) == 4 * _glyphs(TEXT_BUTTON_LABELS[0])
        assert colors.get(wash, 0) == 4
        _pointer(host, surface, _center(surface.text_button_rects[1]), click=False)
        assert surface.intent == ModalPointerIntent(
            ModalPointerKind.HOVER_TEXT_BUTTON, index=1
        )
        _pointer(host, surface, _center(surface.text_button_rects[1]), click=True)
        assert surface.intent == ModalPointerIntent(
            ModalPointerKind.ACTIVATE_TEXT_BUTTON, index=1
        )
