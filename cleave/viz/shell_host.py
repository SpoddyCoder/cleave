"""ImGui shell on the live pygame OpenGL window.

``ShellHost`` owns the layout, the top layer, and event routing, and draws
the menu bar, transport, navigator, inspector, and help through the region
modules. Keyboard stays in ``input_dispatch``; the host only feeds mouse input.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from imgui_bundle import imgui

from cleave.viz.commands import command_context, CommandContext
from cleave.viz.context_menu import ContextMenuProvider
from cleave.viz.help_column import draw_help_column
from cleave.viz.choice_widgets import raise_open_choice_lists
from cleave.viz.help_content import (
    help_section_kwargs,
    help_sections_for_stop,
    modal_help_content,
)
from cleave.viz.imgui_host import ImGuiHost, mouse_button
from cleave.viz.imgui_theme import rgba
from cleave.viz.menu_bar import MenuBarState
from cleave.viz.menu_rows import ContextMenuSurface, ContextSubmenuSurface
from cleave.viz.navigator_context_menu import navigator_node_menu
from cleave.viz.overlay_profiler import OverlayProfiler
from cleave.viz.panel_notification import PanelNotificationActive
from cleave.viz.pointer_cursor import PointerShape, request_pointer
from cleave.viz.preset_context_menu import PRESET_MENU_KINDS, preset_row_menu
from cleave.viz.profiler_panel import draw_profiler_panel
from cleave.viz.row_kinds import RowDescriptor
from cleave.viz.shell_context import ShellContext, ShellFrame
from cleave.viz.shell_focus import cycle_stop_for_focus, CycleStop, ShellRegion
from cleave.viz.shell_layout import ShellLayout
from cleave.viz.shell_inspector import InspectorPanel
from cleave.viz.shell_menu_bar import MenuBarPanel
from cleave.viz.shell_navigator import NavigatorPanel
from cleave.viz.shell_splitters import SplitterDrag
from cleave.viz.shell_strip import StripPointerRouter
from cleave.viz.shell_transport import (
    transport_content_pad_y,
    TransportBar,
    TransportReadout,
)
from cleave.viz.shell_widgets import (
    InlineField,
    PANEL_BORDER_PX,
    rect_has_point,
    RowDrag,
)
from cleave.viz.shell_windows import (
    draw_fixed_window,
    draw_menu_rule,
    draw_panel_border,
    HELP_WINDOW,
    overlap_panel,
    panel_border_overlap_px,
)
from cleave.viz.theme import palette
from cleave.viz.timeline_pointer import MIDDLE_BUTTON, RIGHT_BUTTON, TimelinePointer
from cleave.viz.top_layer import TopLayer

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls
    from cleave.viz.tuning_view_state import TuningViewState

# pygame numbers the mouse back (X1) and forward (X2) side buttons 6 and 7.
_PAGE_HISTORY_BUTTONS = {6: -1, 7: 1}


class ShellHost:
    """ImGui shell drawn through an ``ImGuiHost`` on the current GL context."""

    def __init__(
        self,
        imgui_host: ImGuiHost,
        menu_state: MenuBarState,
        controls: TuningControls,
        bar_height: int,
        *,
        strip_pointer: TimelinePointer | None = None,
        preview_menu: ContextMenuProvider | None = None,
        play_menu: ContextMenuProvider | None = None,
        profiler: OverlayProfiler | None = None,
    ) -> None:
        self.imgui = imgui_host
        self._profiler = (
            profiler if profiler is not None else OverlayProfiler(enabled=False)
        )
        self.top_layer = TopLayer()
        self.context = ShellContext(controls, menu_state, self.top_layer)
        self._preview_menu = preview_menu
        self._play_menu = play_menu
        self._inline = InlineField()
        self._row_drag = RowDrag(self.context)
        self.menu_bar = MenuBarPanel(self.context, bar_height)
        self.transport = TransportBar(self.context, self._inline)
        self.navigator = NavigatorPanel(self.context, self._row_drag)
        self.inspector = InspectorPanel(self.context, self._row_drag, self._inline)
        self.splitters = SplitterDrag(self.context)
        self.strip = StripPointerRouter(self.context, strip_pointer)
        self._context_surface = ContextMenuSurface(
            lambda: self.context.controls.context_menu
        )
        self._context_submenu_surface = ContextSubmenuSurface(self._context_surface)

    @property
    def menu_bar_height_px(self) -> int:
        return self.menu_bar.height_px

    @property
    def nav_content_height_px(self) -> int:
        """Navigator list height for the rows now visible. 0 until measured."""
        return self.navigator.content_height_px

    @property
    def transport_notice_clicked(self) -> bool:
        """True on the frame a click landed on a timed toast."""
        return self.transport.notice_clicked

    @property
    def layout(self) -> ShellLayout | None:
        return self.context.layout

    def set_layout(self, layout: ShellLayout) -> None:
        """Remember the frame's shell rects for the transport, navigator, and inspector."""
        self.context.layout = layout

    @property
    def insp_width(self) -> int | None:
        """Inspector width requested by an in-progress splitter drag."""
        return self.splitters.insp_width

    @property
    def help_width(self) -> int | None:
        """Help width requested by an in-progress splitter drag."""
        return self.splitters.help_width

    @property
    def navigator_height(self) -> int | None:
        """Navigator height requested by an in-progress splitter drag."""
        return self.splitters.navigator_height

    @property
    def timeline_height(self) -> int | None:
        """Timeline band height requested by an in-progress splitter drag."""
        return self.splitters.timeline_height

    def process_event(self, event: pygame.event.Event) -> None:
        """Mouse motion, buttons, and wheel only. Keys stay out of ImGui."""
        # Host active covers the click before the top layer has drawn the modal.
        if event.type == pygame.WINDOWFOCUSLOST:
            self.strip.cancel()
            self.strip.clear_hover()
            self.context.controls.context_menu.close()
            return
        if event.type == pygame.WINDOWLEAVE:
            self.strip.clear_hover()
            return
        if self.context.modal_has_pointer():
            self._process_modal_event(event)
            return
        imgui_host = self.imgui
        if event.type == pygame.MOUSEMOTION:
            imgui_host.process_mouse_event(event)
            x = float(event.pos[0])
            y = float(event.pos[1])
            self.splitters.track_motion(x, y)
            if self.strip.pointer is not None:
                self.strip.pointer.motion(x, y)
            return
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            if self._page_history_button(event):
                return
            button = mouse_button(event)
            if button is None:
                return
            down = event.type == pygame.MOUSEBUTTONDOWN
            if down:
                x = float(event.pos[0])
                y = float(event.pos[1])
                captured = self.top_layer.captures_pointer(x, y)
                context_menu = self.context.controls.context_menu
                if context_menu.is_open and not captured:
                    # A press outside an open menu only closes it. A
                    # right-click goes on to open the menu under it.
                    context_menu.close()
                    if button != RIGHT_BUTTON:
                        return
                if button == RIGHT_BUTTON:
                    if not captured:
                        self._assign_shell_region(x, y)
                        self._open_context_menu(x, y)
                    return
                # Swallow the left button so ImGui does not activate a row
                # or start a value drag. A top-layer hit keeps the click.
                if (
                    button == 0
                    and not captured
                    and self.splitters.begin(event.pos)
                ):
                    return
                if button == 0 and not captured:
                    self._assign_shell_region(x, y)
                    self.strip.press(x, y)
                elif button == MIDDLE_BUTTON and not captured:
                    self.strip.press(x, y, button)
                imgui_host.press_button(button)
            elif button == 0 and self.splitters.active is not None:
                self.splitters.end(event.pos)
                return
            elif not imgui_host.button_held(button):
                return
            else:
                if button in (0, MIDDLE_BUTTON) and self.strip.pointer is not None:
                    self.strip.pointer.release()
                imgui_host.release_button(button)
            imgui_host.process_mouse_event(event)
            return
        if event.type == pygame.MOUSEWHEEL:
            if not self.strip.wheel(event, self.imgui.mouse_pos):
                imgui_host.process_mouse_event(event)

    def _page_history_button(self, event: pygame.event.Event) -> bool:
        """Mouse back and forward buttons step the page history on press.

        A press while a context menu is open only closes the menu.
        """
        step = _PAGE_HISTORY_BUTTONS.get(getattr(event, "button", 0))
        if step is None:
            return False
        if event.type != pygame.MOUSEBUTTONDOWN:
            return True
        context_menu = self.context.controls.context_menu
        if context_menu.is_open:
            context_menu.close()
            return True
        navigator = self.context.controls.navigator
        if step < 0:
            navigator.go_back()
        else:
            navigator.go_forward()
        return True

    def process_play_event(self, event: pygame.event.Event) -> None:
        """Mouse while Play full screen shows only the visualiser.

        A right-click opens the play menu; a press outside an open menu
        closes it. Nothing else under the pointer acts.
        """
        context_menu = self.context.controls.context_menu
        if event.type == pygame.WINDOWFOCUSLOST:
            context_menu.close()
            return
        imgui_host = self.imgui
        if event.type == pygame.MOUSEMOTION:
            imgui_host.process_mouse_event(event)
            return
        if event.type not in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            return
        button = mouse_button(event)
        if button is None:
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            x = float(event.pos[0])
            y = float(event.pos[1])
            if self.top_layer.captures_pointer(x, y):
                imgui_host.press_button(button)
                imgui_host.process_mouse_event(event)
                return
            context_menu.close()
            if button == RIGHT_BUTTON and self._play_menu is not None:
                context_menu.open(self._play_menu, (x, y))
            return
        if imgui_host.button_held(button):
            imgui_host.release_button(button)
            imgui_host.process_mouse_event(event)

    def draw_play_frame(self, dt: float) -> None:
        """One ImGui frame for Play full screen: only an open context menu."""
        self.imgui.begin_frame(dt)
        try:
            if self.context.controls.context_menu.is_open:
                self.top_layer.push(self._context_surface)
                self.top_layer.push(self._context_submenu_surface)
            self.top_layer.draw()
            self.draw_profiler_panel((0, 0))
        finally:
            self.end_imgui_frame()

    def draw_profiler_panel(self, origin: tuple[int, int] | None = None) -> None:
        """Draw the frame timer while it is on, at *origin* or the visualiser."""
        if not self._profiler.enabled:
            return
        if origin is None:
            layout = self.context.layout
            origin = (0, 0) if layout is None else layout.visualiser[:2]
        draw_profiler_panel(self._profiler.report, origin)

    def end_imgui_frame(self) -> None:
        with self._profiler.time_section("ui_render"):
            self.imgui.end_frame()

    def _open_context_menu(self, x: float, y: float) -> None:
        """Open the menu for whatever sits under (*x*, *y*), if it has one."""
        provider = self._context_menu_at(x, y)
        if provider is None:
            return
        self.context.menu_state.blur()
        self.context.controls.context_menu.open(provider, (x, y))

    def _context_menu_at(self, x: float, y: float) -> ContextMenuProvider | None:
        pointer = self.strip.under(x, y)
        if pointer is not None:
            provider = pointer.context_menu_at(x, y)
            if provider is not None:
                self.strip.cancel()
            return provider
        layout = self.context.layout
        if layout is not None and rect_has_point(layout.inspector, x, y):
            return self._inspector_menu_at(x, y)
        if layout is not None and rect_has_point(layout.visualiser, x, y):
            return self._preview_menu
        if layout is None or not rect_has_point(layout.navigator, x, y):
            return None
        node_id = self.navigator.row_at(x, y)
        if node_id is None:
            return None
        self.context.controls.navigator.select(node_id)
        return self._nav_menu(node_id)

    def open_focus_context_menu(self) -> bool:
        """Open the focused item's menu (Shift+F10, Menu key). False when it has none."""
        found = self._focus_context_menu()
        if found is None:
            return False
        provider, anchor = found
        self.context.menu_state.blur()
        self.context.controls.context_menu.open(provider, anchor, keyboard=True)
        return self.context.controls.context_menu.is_open

    def _focus_context_menu(
        self,
    ) -> tuple[ContextMenuProvider, tuple[float, float]] | None:
        region = self.context.controls.shell_focus.region
        if region is ShellRegion.TIMELINE:
            pointer = self.strip.pointer
            if pointer is None or not self.strip.has_scope():
                return None
            row = self.context.controls.session.timeline.focus_row
            anchor = pointer.row_menu_anchor(row)
            if anchor is None:
                return None
            return pointer.row_menu(row), anchor
        if region is ShellRegion.NAVIGATOR:
            node_id = self.context.controls.shell_focus.selected_id
            rect = self.navigator.row_rects.get(node_id)
            if rect is None:
                return None
            x, y, _w, h = rect
            return self._nav_menu(node_id), (float(x), float(y + h))
        if region is ShellRegion.INSPECTOR:
            desc = self.context.controls.shell_focus.inspector_cursor
            found = self.inspector.row_rects.get(desc) if desc is not None else None
            provider = self._inspector_menu(desc) if desc is not None else None
            if found is None or provider is None:
                return None
            (x, y, _w, h), _row = found
            return provider, (float(x), float(y + h))
        if region is ShellRegion.PREVIEW:
            layout = self.context.layout
            if layout is None or self._preview_menu is None:
                return None
            x, y, _w, _h = layout.visualiser
            return self._preview_menu, (float(x), float(y))
        return None

    def _inspector_menu_at(self, x: float, y: float) -> ContextMenuProvider | None:
        """The menu for the inspector row under (*x*, *y*); the row takes focus."""
        for desc, (rect, row) in self.inspector.row_rects.items():
            if not rect_has_point(rect, x, y):
                continue
            provider = self._inspector_menu(desc)
            if provider is not None:
                self.context.controls.inspector.focus_row(row)
            return provider
        return None

    def _inspector_menu(self, desc: RowDescriptor) -> ContextMenuProvider | None:
        if desc.kind in PRESET_MENU_KINDS:
            return preset_row_menu(self.context.controls, desc)
        return None

    def _nav_menu(self, node_id: str) -> ContextMenuProvider:
        return navigator_node_menu(
            self.context.controls, node_id, self.navigator.toggle_expanded
        )

    def _process_modal_event(self, event: pygame.event.Event) -> None:
        """Forward the pointer to ImGui. The shell takes no region or splitter."""
        self.splitters.cancel()
        self.strip.cancel()
        self.strip.clear_hover()
        self.context.controls.disarm_value_nudge()
        imgui_host = self.imgui
        if event.type == pygame.MOUSEMOTION:
            imgui_host.process_mouse_event(event)
            modal_host = self.context.controls.modal_host
            if modal_host.active:
                modal_host.note_pointer_motion(event)
            return
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            button = mouse_button(event)
            if button is None:
                return
            if event.type == pygame.MOUSEBUTTONDOWN:
                imgui_host.press_button(button)
            else:
                imgui_host.release_button(button)
            imgui_host.process_mouse_event(event)
            return
        if event.type == pygame.MOUSEWHEEL:
            imgui_host.process_mouse_event(event)

    def _assign_shell_region(self, x: float, y: float) -> None:
        """A click chooses navigator, inspector, the preview, or the open strip.

        Menu, transport, and help leave the region alone. A miss when no
        layout is stored does nothing. The strip stays open.
        """
        layout = self.context.layout
        if layout is None:
            return
        if rect_has_point(layout.navigator, x, y):
            self.context.controls.set_shell_region(ShellRegion.NAVIGATOR)
            return
        if rect_has_point(layout.inspector, x, y):
            self.context.controls.set_shell_region(ShellRegion.INSPECTOR)
            return
        if layout.timeline[3] > 0 and rect_has_point(layout.timeline, x, y):
            self.context.controls.set_shell_region(ShellRegion.TIMELINE)
            return
        if rect_has_point(layout.visualiser, x, y):
            self.context.controls.set_shell_region(ShellRegion.PREVIEW)

    def _request_gesture_pointer(self) -> None:
        """Pointer for the strip, a live drag, and the splitters.

        Called after the shell windows, so these win over a widget's request.
        A modal or top-layer surface under the pointer keeps its own.
        """
        mouse = imgui.get_mouse_pos()
        if self.context.modal_has_pointer() or self.top_layer.captures_pointer(
            float(mouse.x), float(mouse.y)
        ):
            return
        if self.context.controls.context_menu.is_open:
            # A press outside the open menu only closes it.
            return
        shape = self.strip.pointer_shape()
        row_dragging = self._row_drag.gesture is not None
        if row_dragging:
            shape = PointerShape.MOVE
        elif self.inspector.values.value_drag_crossed and imgui.is_mouse_down(0):
            shape = PointerShape.RESIZE_EW
        splitter = self.splitters.active
        if splitter is None and not imgui.is_mouse_down(0):
            splitter = self.splitters.at(float(mouse.x), float(mouse.y))
        if splitter is not None:
            shape = (
                PointerShape.RESIZE_NS
                if splitter in ("nav", "timeline")
                else PointerShape.RESIZE_EW
            )
        if shape is not None:
            request_pointer(shape)
        if splitter is None and not row_dragging:
            self.strip.show_button_tooltip()

    def draw_windows(
        self,
        menu_state: MenuBarState,
        command_ctx: CommandContext,
        readout: TransportReadout | None = None,
        notice: PanelNotificationActive | None = None,
    ) -> float | None:
        """Menu bar, transport, navigator, inspector, and the open dropdown.

        The caller owns the ImGui frame and the fade. Returns the menu-rule
        row, or None when the bar did not open.
        """
        self.context.command_ctx = command_ctx
        if self.context.input_blocked():
            self.context.controls.disarm_value_nudge()
        rule_y, anchors, menus = self.menu_bar.draw(menu_state, command_ctx)
        if menu_state.dropdown_open:
            # Opening a context menu blurs the bar, so both open together
            # only when the bar just opened. The dropdown wins.
            self.context.controls.context_menu.close()
        if self.context.layout is not None:
            self._draw_shell(menu_state, readout, notice)
        popup_hovered = self.menu_bar.draw_dropdown(
            menu_state, command_ctx, menus, anchors
        )
        if imgui.is_mouse_clicked(0) and not popup_hovered:
            mouse = imgui.get_mouse_pos()
            in_bar = 0.0 <= mouse.y < float(self.menu_bar.height_px)
            if not in_bar:
                menu_state.blur()
        if self.context.controls.context_menu.is_open:
            self.top_layer.push(self._context_surface)
            self.top_layer.push(self._context_submenu_surface)
        self._request_gesture_pointer()
        self.inspector.values.release_gestures()
        return rule_y

    def draw_chrome(self, rule_y: float | None) -> None:
        """Menu rule, above the shell windows and the open dropdown."""
        draw_menu_rule(rule_y, self.menu_bar.dropdown_span)

    def _chrome_contains(self, x: float, y: float) -> bool:
        if self.top_layer.captures_pointer(x, y):
            return True
        if y < self.menu_bar.height_px:
            return True
        layout = self.context.layout
        if layout is None:
            return False
        rects = [layout.transport, layout.navigator, layout.inspector]
        if layout.help[2] > 0 and layout.help[3] > 0:
            rects.append(layout.help)
        return any(rect_has_point(rect, x, y) for rect in rects)

    def _cycle_stop(self, menu_state: MenuBarState) -> CycleStop:
        session = self.context.controls.session
        return cycle_stop_for_focus(
            menu_focused=menu_state.focused,
            region=self.context.controls.shell_focus.region,
            strip_open=bool(session.timeline.panel_open),
        )

    def _draw_shell(
        self,
        menu_state: MenuBarState,
        readout: TransportReadout | None,
        notice: PanelNotificationActive | None,
    ) -> None:
        layout = self.context.layout
        if layout is None:
            return
        if readout is None:
            readout = TransportReadout(False, 0.0, 0.0, "—", None)
        state = self.context.controls.build_view_state(
            paused=readout.paused,
            position_sec=readout.position_sec,
            fps=readout.fps,
        )
        frame = ShellFrame(
            view_state=state,
            nav_nodes=self.navigator.visible_nodes(),
            command_ctx=self.context.command_ctx
            or command_context(self.context.controls),
        )
        stop = self._cycle_stop(menu_state)
        self._inline.reset()
        style = imgui.get_style()
        # Default WindowMinSize is 32px, taller than this one-line bar, so the
        # transport was painted through its own text and over the side panels.
        saved_min_x = float(style.window_min_size.x)
        saved_min_y = float(style.window_min_size.y)
        style.window_min_size = imgui.ImVec2(1.0, 1.0)
        overlap = panel_border_overlap_px(PANEL_BORDER_PX)
        try:
            pad_y = transport_content_pad_y(
                layout.transport[3], imgui.get_text_line_height(), PANEL_BORDER_PX
            )
            imgui.push_style_var(
                imgui.StyleVar_.window_padding,
                imgui.ImVec2(style.window_padding.x, pad_y),
            )
            try:
                draw_fixed_window(
                    "##shell-transport",
                    layout.transport,
                    active=False,
                    body=lambda: self.transport.draw(readout, notice),
                )
            finally:
                imgui.pop_style_var()
            navigator = overlap_panel(layout.navigator, overlap)
            inspector = overlap_panel(layout.inspector, overlap)
            draw_fixed_window(
                "##shell-navigator",
                navigator,
                active=stop is CycleStop.NAVIGATOR,
                idle_border=palette().panel_edge,
                body=lambda: self.navigator.draw(frame),
                scrollable=True,
            )
            draw_fixed_window(
                "##shell-inspector",
                inspector,
                active=stop is CycleStop.INSPECTOR,
                idle_border=palette().panel_edge,
                body=lambda: self.inspector.draw(frame),
            )
            self._draw_help(
                layout.help,
                overlap,
                state=state,
                menu_state=menu_state,
            )
            if layout.timeline[3] > 0:
                # The strip has no ImGui window, so its container outline is
                # drawn here, sharing the rule under the columns above it.
                draw_panel_border(
                    overlap_panel(layout.timeline, overlap),
                    rgba(palette().panel_focus_edge)
                    if stop is CycleStop.TIMELINE
                    else rgba(palette().panel_edge),
                )
            if stop is CycleStop.NAVIGATOR:
                draw_panel_border(navigator, rgba(palette().panel_focus_edge))
            elif stop is CycleStop.INSPECTOR:
                draw_panel_border(inspector, rgba(palette().panel_focus_edge))
            elif stop is CycleStop.PREVIEW:
                draw_panel_border(
                    overlap_panel(layout.visualiser, overlap),
                    rgba(palette().panel_focus_edge),
                )
            # An open inspector dropdown stays above those outlines.
            raise_open_choice_lists()
        finally:
            style.window_min_size = imgui.ImVec2(saved_min_x, saved_min_y)
        inline = self.context.controls.inline_edit
        # A click outside the open text field keeps the edit. The click that
        # opened a transport field this frame is not one.
        if (
            inline.text_target is not None
            and imgui.is_mouse_clicked(0)
            and not self._inline.hovered
            and not self._inline.began
        ):
            inline.finish()

    def _draw_help(
        self,
        rect: tuple[int, int, int, int],
        overlap: int,
        *,
        state: TuningViewState | None,
        menu_state: MenuBarState,
    ) -> None:
        if rect[2] <= 0 or rect[3] <= 0:
            return
        modal_help = self.context.controls.modal_host.help_sections()

        def body() -> None:
            if modal_help:
                draw_help_column(modal_help_content(modal_help))
                return
            if state is None:
                return
            stop = self._cycle_stop(menu_state)
            shell_focus = self.context.controls.shell_focus
            draw_help_column(
                help_sections_for_stop(
                    stop,
                    **help_section_kwargs(state, shell_focus, stop=stop),
                )
            )

        panel = overlap_panel(rect, overlap)
        draw_fixed_window(
            HELP_WINDOW,
            panel,
            active=False,
            idle_border=palette().panel_edge,
            body=body,
            scrollable=True,
        )
        if modal_help:
            # A form's help stays bright above the scrim, under the modal.
            self.top_layer.lift(HELP_WINDOW, panel)


def draw_shell_frame(
    shell: ShellHost,
    menu_state: MenuBarState,
    command_ctx: CommandContext,
    dt: float,
    readout: TransportReadout | None = None,
    notice: PanelNotificationActive | None = None,
) -> None:
    """One ImGui frame: shell windows, chrome, then the top layer.

    The menu, navigator, and inspector stay visible.
    """
    shell.transport.notice_clicked = False
    shell.imgui.begin_frame(dt)
    try:
        rule_y = shell.draw_windows(
            menu_state, command_ctx, readout, notice
        )
        shell.draw_chrome(rule_y)
        shell.top_layer.draw()
        shell.draw_profiler_panel()
    finally:
        shell.end_imgui_frame()
