"""Fixed shell windows, their borders, and the menu rule."""

from __future__ import annotations

from collections.abc import Callable

from imgui_bundle import imgui

from cleave.viz.imgui_theme import rgba
from cleave.viz.shell_widgets import PANEL_BORDER_PX, stroke_h_rule
from cleave.viz.theme import (
    BORDER_COLOR,
    HIGHLIGHT,
    PANEL_FOCUS_BORDER_ALPHA,
    TRANSPORT_RULE,
)

HELP_WINDOW = "##shell-help"
SHELL_FLAGS = (
    int(imgui.WindowFlags_.no_title_bar)
    | int(imgui.WindowFlags_.no_resize)
    | int(imgui.WindowFlags_.no_move)
    | int(imgui.WindowFlags_.no_saved_settings)
    | int(imgui.WindowFlags_.no_focus_on_appearing)
    | int(imgui.WindowFlags_.no_bring_to_front_on_focus)
    | int(imgui.WindowFlags_.no_nav)
    | int(imgui.WindowFlags_.no_scrollbar)
    | int(imgui.WindowFlags_.no_scroll_with_mouse)
)
_CHROME_WINDOW = "##shell-chrome"
_CHROME_FLAGS = (
    int(imgui.WindowFlags_.no_background)
    | int(imgui.WindowFlags_.no_inputs)
    | int(imgui.WindowFlags_.no_title_bar)
    | int(imgui.WindowFlags_.no_resize)
    | int(imgui.WindowFlags_.no_move)
    | int(imgui.WindowFlags_.no_saved_settings)
    | int(imgui.WindowFlags_.no_focus_on_appearing)
    | int(imgui.WindowFlags_.no_bring_to_front_on_focus)
    | int(imgui.WindowFlags_.no_nav)
)


def shell_window_flags(base: int, *, scrollable: bool) -> int:
    """Shell window flags. Scrollable panels keep the wheel and the scrollbar."""
    flags = int(base)
    if not scrollable:
        return flags
    hidden = (
        int(imgui.WindowFlags_.no_scrollbar)
        | int(imgui.WindowFlags_.no_scroll_with_mouse)
    )
    return flags & ~hidden


def scroll_clip_span(window_y: float, window_h: float, pad_y: float) -> tuple[float, float]:
    """Top and bottom clip edges for a scrollable panel's content.

    Dear ImGui clips window content at the border, so rows that overflow run
    into it. Insetting by the window padding keeps the same gap at the top
    and bottom edges that an unscrolled list has.
    """
    top = window_y + pad_y
    bottom = max(top, window_y + window_h - pad_y)
    return top, bottom


def _draw_padded_scroll_body(body: Callable[[], None]) -> None:
    """Draw *body* clipped inside the window padding, top and bottom."""
    pos = imgui.get_window_pos()
    size = imgui.get_window_size()
    top, bottom = scroll_clip_span(
        float(pos.y), float(size.y), float(imgui.get_style().window_padding.y)
    )
    imgui.push_clip_rect(
        imgui.ImVec2(float(pos.x), top),
        imgui.ImVec2(float(pos.x + size.x), bottom),
        True,
    )
    try:
        body()
    finally:
        imgui.pop_clip_rect()


def panel_border_overlap_px(border_size: float) -> int:
    """Pixels to pull a panel up so its top border shares the rule above.

    The transport rule fills the bar's last *border_size* rows, and a panel
    border fills its first *border_size* rows, so overlapping by the border
    width puts the two strokes on the same rows.
    """
    if border_size <= 0.0:
        return 0
    return max(1, int(round(border_size)))


def overlap_panel(
    rect: tuple[int, int, int, int], overlap: int
) -> tuple[int, int, int, int]:
    """Pull a panel up so its top border sits on the rule above it.

    The bottom edge stays put. The extra pixel covers the line already drawn
    by the window above, so the two strokes share one row.
    """
    x, y, width, height = rect
    if overlap <= 0 or height <= 0 or y < overlap:
        return rect
    return (x, y - overlap, width, height + overlap)


def panel_focus_border_rgba() -> imgui.ImVec4:
    """Highlight colour at the quieter panel focus-outline alpha."""
    return rgba(HIGHLIGHT, PANEL_FOCUS_BORDER_ALPHA / 255.0)


def fill_rect_border(rect: tuple[int, int, int, int], color_rgba: imgui.ImVec4) -> None:
    """Outline of the panel border width around *rect* on the current window.

    A stroked border is anti-aliased, so the solid rule underneath shows
    through it. Filled edges cover that rule. The focus outline uses the
    quieter focus alpha, so the rule tints the shared edge.
    """
    x, y, w, h = rect
    if w <= 2 * PANEL_BORDER_PX or h <= 2 * PANEL_BORDER_PX:
        return
    color = imgui.get_color_u32(color_rgba)
    draw = imgui.get_window_draw_list()
    x0, y0 = float(x), float(y)
    x1, y1 = x0 + float(w), y0 + float(h)
    t = PANEL_BORDER_PX
    draw.add_rect_filled(imgui.ImVec2(x0, y0), imgui.ImVec2(x1, y0 + t), color)
    draw.add_rect_filled(imgui.ImVec2(x0, y1 - t), imgui.ImVec2(x1, y1), color)
    draw.add_rect_filled(imgui.ImVec2(x0, y0), imgui.ImVec2(x0 + t, y1), color)
    draw.add_rect_filled(imgui.ImVec2(x1 - t, y0), imgui.ImVec2(x1, y1), color)


def draw_panel_border(
    rect: tuple[int, int, int, int], color_rgba: imgui.ImVec4
) -> None:
    """Outline above the shell windows that share its edges.

    Shell windows stay in an earlier display slot, so a border drawn with
    its panel sits under the rule it overlaps. This window is moved in front
    of those panels and left behind the menu popup, which begins afterwards.
    """
    display = imgui.get_io().display_size
    imgui.set_next_window_pos(imgui.ImVec2(0.0, 0.0), imgui.Cond_.always)
    imgui.set_next_window_size(
        imgui.ImVec2(display.x, display.y), imgui.Cond_.always
    )
    imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
    try:
        _visible, _opened = imgui.begin(
            "##shell-focus-border", None, _CHROME_FLAGS
        )
        try:
            imgui.internal.bring_window_to_display_front(
                imgui.internal.find_window_by_name("##shell-focus-border")
            )
            draw = imgui.get_window_draw_list()
            draw.push_clip_rect(imgui.ImVec2(0.0, 0.0), display, False)
            try:
                fill_rect_border(rect, color_rgba)
            finally:
                draw.pop_clip_rect()
        finally:
            imgui.end()
    finally:
        imgui.pop_style_var()


def draw_fixed_window(
    title: str,
    rect: tuple[int, int, int, int],
    *,
    active: bool,
    body: Callable[[], None],
    idle_border: tuple[int, int, int] | None = None,
    scrollable: bool = False,
) -> None:
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    border = HIGHLIGHT if active else idle_border
    imgui.set_next_window_pos(
        imgui.ImVec2(float(x), float(y)), imgui.Cond_.always
    )
    imgui.set_next_window_size(
        imgui.ImVec2(float(w), float(h)), imgui.Cond_.always
    )
    imgui.push_style_var(
        imgui.StyleVar_.window_border_size,
        PANEL_BORDER_PX if border is not None else 0.0,
    )
    if border is not None:
        # ImGui centres a thick window border on a half pixel, which
        # blurs it; hide that stroke and fill the edges instead.
        alpha = PANEL_FOCUS_BORDER_ALPHA / 255.0 if active else 1.0
        imgui.push_style_color(imgui.Col_.border, rgba(border, 0.0))
    try:
        _visible, _opened = imgui.begin(
            title,
            None,
            shell_window_flags(SHELL_FLAGS, scrollable=scrollable),
        )
        try:
            if scrollable:
                _draw_padded_scroll_body(body)
            else:
                body()
            if border is not None:
                draw = imgui.get_window_draw_list()
                draw.push_clip_rect(
                    imgui.ImVec2(float(x), float(y)),
                    imgui.ImVec2(float(x + w), float(y + h)),
                    False,
                )
                try:
                    fill_rect_border(rect, rgba(border, alpha))
                finally:
                    draw.pop_clip_rect()
        finally:
            imgui.end()
    finally:
        if border is not None:
            imgui.pop_style_color()
        imgui.pop_style_var()


def draw_menu_rule(
    rule_y: float | None, dropdown_span: tuple[float, float] | None
) -> None:
    """Menu rule, above the shell windows.

    Full-display, no background, and no inputs. Raised after Begin so the
    order stays shell windows, dropdown, then this window.
    """
    display = imgui.get_io().display_size
    imgui.set_next_window_pos(imgui.ImVec2(0.0, 0.0), imgui.Cond_.always)
    imgui.set_next_window_size(
        imgui.ImVec2(display.x, display.y), imgui.Cond_.always
    )
    # A non-zero border insets the window clip and would eat the edge rule.
    imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
    try:
        _visible, _opened = imgui.begin(_CHROME_WINDOW, None, _CHROME_FLAGS)
        try:
            imgui.internal.bring_window_to_display_front(
                imgui.internal.find_window_by_name(_CHROME_WINDOW)
            )
            draw = imgui.get_window_draw_list()
            draw.push_clip_rect(imgui.ImVec2(0.0, 0.0), display, False)
            try:
                if rule_y is not None:
                    stroke_h_rule(
                        0.0, display.x, rule_y, TRANSPORT_RULE, PANEL_BORDER_PX
                    )
                    span = dropdown_span
                    if span is not None:
                        # The popup's top border sits on this row.
                        stroke_h_rule(
                            span[0], span[1], rule_y, BORDER_COLOR, PANEL_BORDER_PX
                        )
            finally:
                draw.pop_clip_rect()
        finally:
            imgui.end()
    finally:
        imgui.pop_style_var()
