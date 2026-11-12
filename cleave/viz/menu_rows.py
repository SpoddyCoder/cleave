"""Menu rows shared by the menu-bar dropdown and context menus.

Both draw the same row: a check column, the label, and a right-aligned
shortcut, with an opaque highlight on the keyboard row and the disabled
colour on rows that cannot run. Callers resolve their own items into
``MenuRowView`` first.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

from imgui_bundle import imgui

from cleave.viz.context_menu import (
    ContextMenuItem,
    ContextMenuState,
    ContextSubmenu,
)
from cleave.viz.imgui_theme import rgba
from cleave.viz.theme import BACKGROUND, DISABLED, HIGHLIGHT, MUTED, VALUE, ui_chrome_px

Rect = tuple[int, int, int, int]

MENU_POPUP_TOP_PAD_PX = 4.0
CHECK_MARK = "✓"
# The ImGui atlas carries this for the navigator twisty.
SUBMENU_MARK = "▸"
POPUP_FLAGS = (
    int(imgui.WindowFlags_.no_title_bar)
    | int(imgui.WindowFlags_.no_resize)
    | int(imgui.WindowFlags_.no_move)
    | int(imgui.WindowFlags_.no_scrollbar)
    | int(imgui.WindowFlags_.always_auto_resize)
    | int(imgui.WindowFlags_.no_saved_settings)
    | int(imgui.WindowFlags_.no_focus_on_appearing)
    | int(imgui.WindowFlags_.no_nav)
)

_CONTEXT_WINDOW = "##cleave-context-menu"
_SUBMENU_WINDOW = "##cleave-context-submenu"


@dataclass(frozen=True)
class MenuRowView:
    """One drawn row. ``color`` is the label colour when not highlighted."""

    id: str
    label: str
    enabled: bool = True
    checked: bool = False
    shortcut: str | None = None
    color: tuple[int, int, int] = VALUE
    submenu: bool = False


@dataclass(frozen=True)
class MenuRowsResult:
    """Row index clicked this frame, the row under the pointer, and row rects.

    ``rects`` has one screen rect per row, None for a separator.
    """

    clicked: int | None = None
    hovered: int | None = None
    rects: tuple[Rect | None, ...] = ()


@contextmanager
def opaque_highlight_fill(active: bool) -> Iterator[None]:
    """Push an opaque highlight header fill for an open menu title or row."""
    if active:
        fill = rgba(HIGHLIGHT, 1.0)
        imgui.push_style_color(imgui.Col_.header, fill)
        imgui.push_style_color(imgui.Col_.header_hovered, fill)
        imgui.push_style_color(imgui.Col_.header_active, fill)
    try:
        yield
    finally:
        if active:
            imgui.pop_style_color(3)


def draw_menu_rows(
    rows: Sequence[MenuRowView | None],
    highlighted: int | None,
) -> MenuRowsResult:
    """Draw *rows* in the current window; None is a separator."""
    style = imgui.get_style()
    pad_x = style.frame_padding.x
    check_w = imgui.calc_text_size(CHECK_MARK).x
    gap = max(imgui.calc_text_size("  ").x, ui_chrome_px(16.0))
    label_w = 0.0
    shortcut_w = 0.0
    any_submenu = False
    for row in rows:
        if row is None:
            continue
        label_w = max(label_w, imgui.calc_text_size(row.label).x)
        if row.shortcut:
            shortcut_w = max(shortcut_w, imgui.calc_text_size(row.shortcut).x)
        any_submenu = any_submenu or row.submenu
    mark_w = imgui.calc_text_size(SUBMENU_MARK).x if any_submenu else 0.0
    arrow_w = gap * 0.5 + mark_w if any_submenu else 0.0
    row_w = pad_x * 2.0 + check_w + gap + label_w + gap + shortcut_w + arrow_w + pad_x
    draw_list = imgui.get_window_draw_list()
    # Whole pixels: text snaps down to a pixel, so a fractional row top
    # leaves the label off-centre in its fill.
    imgui.set_cursor_pos_y(
        imgui.get_cursor_pos_y() + round(ui_chrome_px(MENU_POPUP_TOP_PAD_PX))
    )
    clicked: int | None = None
    hovered: int | None = None
    rects: list[Rect | None] = []
    for index, row in enumerate(rows):
        if row is None:
            imgui.separator()
            rects.append(None)
            continue
        is_highlighted = highlighted == index
        pos = imgui.get_cursor_screen_pos()
        # Disabled skips the hover wash. The keyboard row stays selectable
        # so its opaque fill still paints.
        flags = int(
            imgui.SelectableFlags_.disabled
            if not row.enabled and not is_highlighted
            else imgui.SelectableFlags_.none
        )
        with opaque_highlight_fill(is_highlighted):
            pressed, _selected = imgui.selectable(
                f"##{row.id}",
                is_highlighted,
                flags,
                imgui.ImVec2(row_w, 0.0),
            )
        rect_min = imgui.get_item_rect_min()
        rect_max = imgui.get_item_rect_max()
        rects.append(
            (
                int(rect_min.x),
                int(rect_min.y),
                int(rect_max.x - rect_min.x),
                int(rect_max.y - rect_min.y),
            )
        )
        if imgui.is_item_hovered(int(imgui.HoveredFlags_.allow_when_disabled)):
            hovered = index
        if is_highlighted:
            ink = rgba(BACKGROUND)
            label_color = check_color = shortcut_color = ink
        else:
            label_color = rgba(row.color if row.enabled else DISABLED)
            check_color = rgba(VALUE if row.enabled else DISABLED)
            shortcut_color = rgba(MUTED)
        # Selectable anchors the label at the cursor and pads the highlight
        # with half of ItemSpacing on each side. Frame padding would push
        # the label down so the fill sits high, flush with the next row.
        text_y = pos.y
        text_x = pos.x + pad_x
        if row.checked:
            draw_list.add_text(
                imgui.ImVec2(text_x, text_y),
                imgui.get_color_u32(check_color),
                CHECK_MARK,
            )
        draw_list.add_text(
            imgui.ImVec2(text_x + check_w + gap, text_y),
            imgui.get_color_u32(label_color),
            row.label,
        )
        if row.shortcut:
            shortcut_width = imgui.calc_text_size(row.shortcut).x
            draw_list.add_text(
                imgui.ImVec2(
                    pos.x + row_w - pad_x - arrow_w - shortcut_width, text_y
                ),
                imgui.get_color_u32(shortcut_color),
                row.shortcut,
            )
        if row.submenu:
            draw_list.add_text(
                imgui.ImVec2(pos.x + row_w - pad_x - mark_w, text_y),
                imgui.get_color_u32(label_color),
                SUBMENU_MARK,
            )
        if pressed and row.enabled:
            clicked = index
    return MenuRowsResult(clicked=clicked, hovered=hovered, rects=tuple(rects))


def context_menu_row_views(
    entries: Sequence[object],
) -> tuple[MenuRowView | None, ...]:
    """Rows for a context menu's entries; separators become None."""
    views: list[MenuRowView | None] = []
    for entry in entries:
        if isinstance(entry, ContextSubmenu):
            views.append(
                MenuRowView(
                    id=entry.id,
                    label=entry.label,
                    enabled=entry.enabled,
                    shortcut=entry.shortcut,
                    submenu=True,
                )
            )
            continue
        if not isinstance(entry, ContextMenuItem):
            views.append(None)
            continue
        views.append(
            MenuRowView(
                id=entry.id,
                label=entry.label,
                enabled=entry.enabled,
                checked=bool(entry.checked),
                shortcut=entry.shortcut,
            )
        )
    return tuple(views)


def entry_hint(entry: object) -> str | None:
    """Tooltip text for a row: why it is disabled, or what it needs."""
    if isinstance(entry, (ContextMenuItem, ContextSubmenu)):
        return entry.hint
    return None


def clamp_menu_origin(
    anchor: tuple[float, float],
    size: tuple[float, float],
    display: tuple[float, float],
) -> tuple[float, float]:
    """Top-left for a menu of *size* at *anchor*, flipped or pushed inside *display*.

    A menu that would cross the right or bottom edge opens to the left of or
    above the anchor, as long as that fits; otherwise it slides to the edge.
    """
    ax, ay = anchor
    width, height = size
    display_w, display_h = display
    x = ax
    if x + width > display_w:
        x = ax - width if ax - width >= 0 else max(0.0, display_w - width)
    y = ay
    if y + height > display_h:
        y = ay - height if ay - height >= 0 else max(0.0, display_h - height)
    return (x, y)


def submenu_origin(
    parent: Rect,
    size: tuple[float, float],
    display: tuple[float, float],
    *,
    top_pad: float = 0.0,
) -> tuple[float, float]:
    """Top-left for a submenu of *size* beside the *parent* row.

    It opens to the right of the row, its first row level with it, and to
    the left when the right side has no room. It slides up to stay inside.
    """
    px, py, pw, _ph = parent
    width, height = size
    display_w, display_h = display
    x = float(px + pw)
    if x + width > display_w:
        x = px - width if px - width >= 0 else max(0.0, display_w - width)
    y = float(py) - top_pad
    if y + height > display_h:
        y = max(0.0, display_h - height)
    return (x, max(0.0, y))


class ContextMenuSurface:
    """The open context menu as a top-layer window at its anchor.

    Non-modal: the top layer records its rect, so the shell under it does
    not take the pointer. A click on an enabled row runs it; hovering a row
    with a hint shows the hint as a tooltip. Keep one instance and push it
    each frame the menu is open, so it remembers its size for edge clamping.
    """

    modal = False

    def __init__(self, state: Callable[[], ContextMenuState]) -> None:
        self._state = state
        self._size: tuple[float, float] = (0.0, 0.0)
        self._last_hovered: int | None = None
        self.row_rects: tuple[Rect | None, ...] = ()

    @property
    def state(self) -> ContextMenuState:
        return self._state()

    def draw(self) -> Rect:
        state = self._state()
        entries = state.items()
        if not entries:
            return (0, 0, 0, 0)
        display = imgui.get_io().display_size
        x, y = clamp_menu_origin(
            state.anchor, self._size, (float(display.x), float(display.y))
        )
        imgui.set_next_window_pos(imgui.ImVec2(x, y), imgui.Cond_.always)
        visible, _open = imgui.begin(_CONTEXT_WINDOW, None, POPUP_FLAGS)
        try:
            imgui.internal.bring_window_to_display_front(
                imgui.internal.find_window_by_name(_CONTEXT_WINDOW)
            )
            pos = imgui.get_window_pos()
            size = imgui.get_window_size()
            self._size = (float(size.x), float(size.y))
            rect = (int(pos.x), int(pos.y), max(0, int(size.x)), max(0, int(size.y)))
            if not visible:
                return rect
            result = draw_menu_rows(context_menu_row_views(entries), state.highlight)
        finally:
            imgui.end()
        self.row_rects = result.rects
        if result.hovered != self._last_hovered:
            # Only a move onto a new row takes the highlight, so a resting
            # pointer does not fight the arrow keys.
            self._last_hovered = result.hovered
            if result.hovered is not None:
                state.hover(result.hovered)
        if result.hovered is not None:
            hint = entry_hint(entries[result.hovered])
            if hint:
                imgui.set_tooltip(hint)
        if result.clicked is not None:
            state.activate(result.clicked)
        return rect


class ContextSubmenuSurface:
    """The open submenu of a context menu, beside its parent row.

    Push it right after its ``ContextMenuSurface`` every frame the menu is
    open; it draws nothing while no submenu is open.
    """

    modal = False

    def __init__(self, parent: ContextMenuSurface) -> None:
        self._parent = parent
        self._size: tuple[float, float] = (0.0, 0.0)
        self._last_hovered: int | None = None

    def draw(self) -> Rect:
        state = self._parent.state
        sub = state.submenu_items()
        index = state.submenu
        rects = self._parent.row_rects
        if not sub or index is None or not 0 <= index < len(rects):
            self._last_hovered = None
            return (0, 0, 0, 0)
        parent_rect = rects[index]
        if parent_rect is None:
            return (0, 0, 0, 0)
        display = imgui.get_io().display_size
        x, y = submenu_origin(
            parent_rect,
            self._size,
            (float(display.x), float(display.y)),
            top_pad=round(ui_chrome_px(MENU_POPUP_TOP_PAD_PX)),
        )
        imgui.set_next_window_pos(imgui.ImVec2(x, y), imgui.Cond_.always)
        visible, _open = imgui.begin(_SUBMENU_WINDOW, None, POPUP_FLAGS)
        try:
            imgui.internal.bring_window_to_display_front(
                imgui.internal.find_window_by_name(_SUBMENU_WINDOW)
            )
            pos = imgui.get_window_pos()
            size = imgui.get_window_size()
            self._size = (float(size.x), float(size.y))
            rect = (int(pos.x), int(pos.y), max(0, int(size.x)), max(0, int(size.y)))
            if not visible:
                return rect
            result = draw_menu_rows(context_menu_row_views(sub), state.sub_highlight)
        finally:
            imgui.end()
        if result.hovered != self._last_hovered:
            self._last_hovered = result.hovered
            if result.hovered is not None:
                state.hover_submenu(result.hovered)
        if result.hovered is not None:
            hint = entry_hint(sub[result.hovered])
            if hint:
                imgui.set_tooltip(hint)
        if result.clicked is not None:
            state.activate_submenu(result.clicked)
        return rect
