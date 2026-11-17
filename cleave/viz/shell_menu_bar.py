"""The shell's menu bar: titles, project label, and the open dropdown."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from imgui_bundle import imgui

from cleave.viz.commands import Command, CommandContext, MenuSeparator
from cleave.viz.imgui_theme import rgba
from cleave.viz.menu_bar import MenuBarState, menus_for_session
from cleave.viz.menu_rows import (
    draw_menu_rows,
    FittedWindow,
    MenuRowView,
)
from cleave.viz.shell_context import ShellContext
from cleave.viz.shell_widgets import selectable_label_origin
from cleave.viz.row_paint import RowState, row_band
from cleave.viz.theme import palette, tuning_ui_metrics, ui_chrome_px

if TYPE_CHECKING:
    from cleave.viz.menu_bar import Menu

# Vertical padding for the menu bar and the transport bar, which shares its height.
# Dear ImGui's default FramePadding.y is 3, which leaves both rows cramped.
_MENU_BAR_FRAME_PADDING_Y = 8.0


def menu_bar_height_px() -> int:
    """Pixels reserved for the menu bar before the first ImGui layout.

    Safe without a GL context or an ImGui context. ``ShellHost`` replaces
    this with the laid-out bar height after the first frame. The transport
    bar uses the same height.
    """
    font_size = float(tuning_ui_metrics().font_size)
    return max(1, int(round(font_size + _menu_bar_pad_y() * 2.0)))


def menu_bar_project_label(project_slug: str, dirty: bool) -> tuple[str, str]:
    """Prefix and name at the right end of the menu bar; ``*`` marks unsaved changes."""
    return "Project: ", f"{project_slug}*" if dirty else project_slug


def _menu_bar_pad_y() -> float:
    """Menu bar frame padding in whole pixels, so its labels and underlines stay on the pixel grid."""
    return float(round(ui_chrome_px(_MENU_BAR_FRAME_PADDING_Y)))


@contextmanager
def _menu_bar_frame_padding() -> Iterator[None]:
    """Extra vertical padding for the menu bar. Other rows keep the default."""
    style = imgui.get_style()
    imgui.push_style_var(
        imgui.StyleVar_.frame_padding,
        imgui.ImVec2(style.frame_padding.x, _menu_bar_pad_y()),
    )
    try:
        yield
    finally:
        imgui.pop_style_var()


def _draw_mnemonic_underline(label: str, color: tuple[int, int, int]) -> None:
    """1px underline two pixels under the ink of a top menu's first letter."""
    letter = label[:1]
    if not letter:
        return
    origin_x, origin_y = selectable_label_origin()
    glyph = imgui.get_font().find_glyph(ord(letter))
    letter_width = imgui.calc_text_size(letter).x
    # Two pixels under the glyph. The line box still has descent below that.
    y = origin_y + glyph.y1 + 2.0
    packed = imgui.get_color_u32(rgba(color))
    imgui.get_window_draw_list().add_rect_filled(
        imgui.ImVec2(origin_x, y),
        imgui.ImVec2(origin_x + letter_width, y + 1.0),
        packed,
    )


def _mouse_in_current_window() -> bool:
    origin = imgui.get_window_pos()
    size = imgui.get_window_size()
    mouse = imgui.get_mouse_pos()
    return (
        origin.x <= mouse.x < origin.x + size.x
        and origin.y <= mouse.y < origin.y + size.y
    )


def command_row_view(command: Command, ctx: CommandContext) -> MenuRowView:
    """A menu-bar command as a drawn menu row."""
    return MenuRowView(
        id=command.id,
        label=command.label,
        enabled=bool(command.enabled(ctx)),
        checked=(
            command.kind == "check"
            and command.checked is not None
            and bool(command.checked(ctx))
        ),
        shortcut=command.shortcut,
        color=command.label_role(ctx) if command.label_role is not None else palette().value,
    )


class MenuBarPanel:
    """The menu titles, the project label, and the open dropdown."""

    def __init__(self, context: ShellContext, bar_height: int) -> None:
        self._ctx = context
        self.height_px = bar_height
        # Left and right edge of the open dropdown, for the rule above it.
        self.dropdown_span: tuple[float, float] | None = None
        # One fitted window per top menu, so a hover onto the next title
        # shows its dropdown at its own size, not the last menu's for a frame.
        self._dropdown_window = FittedWindow("##cleave-menu", remember_keys=True)
        # Top label under the pointer last frame. Hover opens on entry only, so
        # a click that closes a menu is not undone while the pointer stays put.
        self._bar_hover_index: int | None = None
        # Dropdown row under the pointer last frame. Only a move onto a new
        # row takes the highlight, so a resting pointer does not fight the
        # arrow keys.
        self._dropdown_hover_index: int | None = None

    def draw(
        self, menu_state: MenuBarState, command_ctx: CommandContext
    ) -> tuple[float | None, dict[int, tuple[float, float]], tuple[Menu, ...]]:
        """Draw the bar. Returns the rule row, each title's dropdown anchor, and the menus."""
        with _menu_bar_frame_padding():
            self.height_px = max(1, int(round(imgui.get_frame_height())))
            return self.draw_bar(menu_state, command_ctx)

    def draw_bar(
        self, menu_state: MenuBarState, command_ctx: CommandContext
    ) -> tuple[float | None, dict[int, tuple[float, float]], tuple[Menu, ...]]:
        menus = menus_for_session(self._ctx.controls.session)
        anchors: dict[int, tuple[float, float]] = {}
        imgui.push_style_color(imgui.Col_.text, rgba(palette().label))
        # The bar's own border is covered by the menu titles. The white rule
        # is drawn later, on top.
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
        bar_open = imgui.begin_main_menu_bar()
        rule_y: float | None = None
        hovered_index = self._bar_hover_index
        hovered_now: int | None = None
        try:
            if bar_open:
                bar_bottom = imgui.get_window_pos().y + imgui.get_window_height()
                self.height_px = max(1, int(round(bar_bottom)))
                rule_y = bar_bottom - 1.0
                pad_x = imgui.get_style().frame_padding.x
                for index, menu in enumerate(menus):
                    active = menu_state.focused and menu_state.menu_index == index
                    width = imgui.calc_text_size(menu.label).x + pad_x * 2.0
                    # The open title is lit (no marker bar), including under
                    # the pointer. Idle hover is the theme's violet wash.
                    with row_band(RowState.LIT if active else None, bar=False) as mark_band:
                        if active:
                            imgui.push_style_color(imgui.Col_.text, rgba(palette().value))
                        clicked, _selected = imgui.selectable(
                            menu.label,
                            active,
                            0,
                            imgui.ImVec2(width, 0.0),
                        )
                        mark_band(imgui.get_item_rect_min().x)
                        if active:
                            imgui.pop_style_color()
                    label_y = selectable_label_origin()[1]
                    underline = palette().value if active else palette().label
                    _draw_mnemonic_underline(menu.label, underline)
                    # The dropdown's top border sits on the rule row. The
                    # title's item rect ends a few pixels above the bar
                    # bottom, so anchoring there doubled the top border
                    # whenever the popup drew in front of the bar.
                    anchors[index] = (imgui.get_item_rect_min().x, rule_y)
                    if clicked:
                        menu_state.click_top(index, menus)
                    elif imgui.is_item_hovered() and hovered_index != index:
                        menu_state.hover_top(index, menus)
                    if imgui.is_item_hovered():
                        hovered_now = index
                if menus:
                    self._draw_bar_project_label(label_y, command_ctx.config_dirty)
        finally:
            if bar_open:
                imgui.end_main_menu_bar()
            self._bar_hover_index = hovered_now
            imgui.pop_style_var()
            imgui.pop_style_color()
        return rule_y, anchors, menus

    def _draw_bar_project_label(self, label_y: float, dirty: bool) -> None:
        """Right-aligned project name on the menu titles' text line.

        Painted on the bar's draw list, not laid out as an item, so the menu
        bar's horizontal layout cannot shift or wrap it. Dropped when it would
        overlap the last menu title.
        """
        prefix, name = menu_bar_project_label(
            self._ctx.controls.cfg.project_slug, dirty
        )
        style = imgui.get_style()
        left = imgui.get_item_rect_max().x + style.frame_padding.x
        # Same inset as the transport bar's FPS readout below it.
        right = (
            imgui.get_window_pos().x
            + imgui.get_window_width()
            - style.window_padding.x
        )
        prefix_w = imgui.calc_text_size(prefix).x
        x = right - prefix_w - imgui.calc_text_size(name).x
        if x < left:
            return
        draw = imgui.get_window_draw_list()
        draw.add_text(
            imgui.ImVec2(x, label_y), imgui.get_color_u32(rgba(palette().label)), prefix
        )
        draw.add_text(
            imgui.ImVec2(x + prefix_w, label_y),
            imgui.get_color_u32(rgba(palette().value)),
            name,
        )

    def draw_dropdown(
        self,
        menu_state: MenuBarState,
        command_ctx: CommandContext,
        menus: tuple[Menu, ...],
        anchors: dict[int, tuple[float, float]],
    ) -> bool:
        """Draw the open menu's rows. True when the pointer is on them."""
        self.dropdown_span = None
        if not menu_state.dropdown_open or not menus:
            return False
        index = menu_state.menu_index % len(menus)
        menu = menus[index]
        anchor = anchors.get(index)
        if anchor is None:
            origin_x = 0.0
            origin_y = float(self.height_px) - 1.0
        else:
            origin_x, origin_y = anchor
        # Begun after the shell panels and raised over them; chrome is raised
        # after this window. Do not focus it: FocusWindow clears the menu-bar
        # button's ActiveId, and a later click on another top label never
        # completes. A menu's first open measures off-screen for one frame.
        with self._dropdown_window.begin(
            (index, menu.label),
            lambda _size, _display: (origin_x, origin_y),
        ) as (visible, measuring, rect):
            if not visible:
                return False
            hit = self._draw_rows(
                menu_state, command_ctx, menus, index, menu, measuring=measuring
            )
            if measuring:
                return False
            x, _y, width, _height = rect
            self.dropdown_span = (float(x), float(x + width))
            return hit or _mouse_in_current_window()

    def _draw_rows(
        self,
        menu_state: MenuBarState,
        command_ctx: CommandContext,
        menus: tuple[Menu, ...],
        menu_index: int,
        menu: Menu,
        *,
        measuring: bool,
    ) -> bool:
        rows = tuple(
            None
            if isinstance(item, MenuSeparator)
            else command_row_view(item, command_ctx)
            for item in menu.items
        )
        result = draw_menu_rows(rows, menu_state.item_index)
        if measuring:
            self._dropdown_hover_index = None
        elif result.hovered != self._dropdown_hover_index:
            self._dropdown_hover_index = result.hovered
            if result.hovered is not None:
                row = rows[result.hovered]
                menu_state.hover_item(
                    result.hovered if row is not None and row.enabled else None
                )
        if result.clicked is None:
            return False
        menu_state.click_item(
            menu_index,
            result.clicked,
            menus,
            command_ctx,
            self._ctx.controls,
        )
        return True
