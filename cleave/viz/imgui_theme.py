"""Theme roles applied to ImGui once per frame."""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager

from imgui_bundle import imgui

from cleave.viz.theme import (
    BUTTON_ACTIVE_BG,
    BUTTON_BG,
    BUTTON_HOVER_BG,
    BACKGROUND,
    DISABLED,
    HOVER,
    HOVER_BG_ALPHA,
    MODAL_SCRIM_ALPHA,
    ROW_FOCUS_EDGE,
    ROW_SELECT_TINT,
    ROW_SELECTED_ALPHA,
    SCROLLBAR_THUMB,
    SCROLLBAR_THUMB_HOVER,
    SCROLLBAR_TRACK,
    SURFACE_BG,
    SURFACE_EDGE,
    TRANSPORT_RULE,
    VALUE,
    ui_chrome_px,
)

_SELECTED_WASH = ROW_SELECTED_ALPHA[0]
_HOVER_WASH = HOVER_BG_ALPHA / 255.0
# Same black scrim as the pygame modal underlay.
_SCRIM = MODAL_SCRIM_ALPHA / 255.0

IMGUI_COLOR_ROLES: dict[imgui.Col_, tuple[tuple[int, int, int], float]] = {
    imgui.Col_.text: (VALUE, 1.0),
    imgui.Col_.text_disabled: (DISABLED, 1.0),
    imgui.Col_.window_bg: (BACKGROUND, 1.0),
    imgui.Col_.child_bg: (BACKGROUND, 1.0),
    imgui.Col_.popup_bg: (SURFACE_BG, 1.0),
    imgui.Col_.menu_bar_bg: (BACKGROUND, 1.0),
    imgui.Col_.border: (SURFACE_EDGE, 1.0),
    imgui.Col_.header: (ROW_SELECT_TINT, _SELECTED_WASH),
    imgui.Col_.header_hovered: (HOVER, _HOVER_WASH),
    imgui.Col_.header_active: (HOVER, _HOVER_WASH),
    imgui.Col_.button: (BUTTON_BG, 1.0),
    imgui.Col_.button_hovered: (BUTTON_HOVER_BG, 1.0),
    imgui.Col_.button_active: (BUTTON_ACTIVE_BG, 1.0),
    imgui.Col_.frame_bg: (BACKGROUND, 1.0),
    imgui.Col_.title_bg: (BACKGROUND, 1.0),
    imgui.Col_.title_bg_active: (BACKGROUND, 1.0),
    imgui.Col_.title_bg_collapsed: (BACKGROUND, 1.0),
    imgui.Col_.check_mark: (VALUE, 1.0),
    imgui.Col_.separator: (TRANSPORT_RULE, 1.0),
    imgui.Col_.text_selected_bg: (ROW_SELECT_TINT, 0.5),
    imgui.Col_.nav_highlight: (ROW_FOCUS_EDGE, 1.0),
    imgui.Col_.scrollbar_bg: (SCROLLBAR_TRACK, 1.0),
    imgui.Col_.scrollbar_grab: (SCROLLBAR_THUMB, 1.0),
    imgui.Col_.scrollbar_grab_hovered: (SCROLLBAR_THUMB_HOVER, 1.0),
    imgui.Col_.scrollbar_grab_active: (SCROLLBAR_THUMB_HOVER, 1.0),
    imgui.Col_.modal_window_dim_bg: (BACKGROUND, _SCRIM),
}


def lighten(rgb: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    """Move *rgb* toward white by *amount* (0..1)."""
    r, g, b = (round(c + (255 - c) * amount) for c in rgb)
    return r, g, b


def brighten(rgb: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    """Scale *rgb* up by *amount* (0..1), keeping its hue and saturation."""
    r, g, b = (min(255, round(c * (1.0 + amount))) for c in rgb)
    return r, g, b


def darken(rgb: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    """Move *rgb* toward black by *amount* (0..1)."""
    r, g, b = (round(c * (1.0 - amount)) for c in rgb)
    return r, g, b


def rgba(rgb: tuple[int, int, int], alpha: float = 1.0) -> imgui.ImVec4:
    return imgui.ImVec4(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, alpha)


@contextmanager
def floating_surface() -> Iterator[None]:
    """Push the floating surface's ink fill and violet edge.

    Wrap a window's ``begin``, and any ``begin_child`` inside it, so a child
    (the file picker's list) shares the ink rather than the shell's black.
    Menus, context menus, the open choice list, dialogs, the file picker, and
    info panels all float over the shell in this one look.
    """
    imgui.push_style_color(imgui.Col_.window_bg, rgba(SURFACE_BG))
    imgui.push_style_color(imgui.Col_.child_bg, rgba(SURFACE_BG))
    imgui.push_style_color(imgui.Col_.border, rgba(SURFACE_EDGE))
    try:
        yield
    finally:
        imgui.pop_style_color(3)


# Every size ``ImGuiStyle::ScaleAllSizes`` scales, as imgui-bundle attributes.
_STYLE_SIZE_FIELDS = (
    "window_padding",
    "window_rounding",
    "window_min_size",
    "child_rounding",
    "popup_rounding",
    "frame_padding",
    "frame_rounding",
    "item_spacing",
    "item_inner_spacing",
    "cell_padding",
    "touch_extra_padding",
    "indent_spacing",
    "columns_min_spacing",
    "scrollbar_size",
    "scrollbar_rounding",
    "grab_min_size",
    "grab_rounding",
    "log_slider_deadzone",
    "tab_rounding",
    "tab_min_width_for_close_button",
    "separator_text_padding",
    "display_window_padding",
    "display_safe_area_padding",
    "mouse_cursor_scale",
)


# Extra space above and below each navigator, inspector, and menu row's
# highlight, so it clears the text and a focused row's outline clears its
# segments, combo box, or buttons.
ROW_PAD_Y = 2.0


def padded_row_spacing_y() -> float:
    """Item spacing between padded rows.

    Selectables grow by half the item spacing above and below, so this adds
    ROW_PAD_Y to each side of every row's highlight. Whole pixels keep the
    measured navigator height the same from frame to frame, and an even count
    splits evenly above and below, so the text stays centred in its fill.
    """
    spacing = imgui.get_style().item_spacing.y + 2.0 * ui_chrome_px(ROW_PAD_Y)
    return 2.0 * math.floor(spacing * 0.5 + 0.5)


def row_band(text_top_y: float) -> tuple[float, float]:
    """Top and bottom of the highlight band for a row whose text starts at *text_top_y*.

    The band a padded selectable fills: half the padded row spacing above and
    below one text line. Every icon button on a row is this tall.
    """
    pad = padded_row_spacing_y() * 0.5
    return text_top_y - pad, text_top_y + imgui.get_text_line_height() + pad


def row_band_side() -> float:
    """Height of a padded row's highlight band, and so the side of its icon boxes."""
    return imgui.get_text_line_height() + padded_row_spacing_y()


@contextmanager
def padded_rows() -> Iterator[None]:
    """Push the padded row spacing for a list of rows, then pop."""
    imgui.push_style_var(
        imgui.StyleVar_.item_spacing,
        imgui.ImVec2(imgui.get_style().item_spacing.x, padded_row_spacing_y()),
    )
    try:
        yield
    finally:
        imgui.pop_style_var()


def apply_imgui_style_scale(factor: float) -> None:
    """Set style sizes to ImGui's defaults scaled by *factor*.

    Starts from a fresh default style each time, so repeated changes do not
    compound ImGui's per-call rounding.
    """
    scaled = imgui.Style()
    scaled.scale_all_sizes(factor)
    style = imgui.get_style()
    for name in _STYLE_SIZE_FIELDS:
        setattr(style, name, getattr(scaled, name))


def apply_imgui_theme() -> None:
    """Write ``IMGUI_COLOR_ROLES`` and the shell's square corners onto the style."""
    style = imgui.get_style()
    style.window_rounding = 0.0
    style.frame_rounding = 0.0
    style.popup_rounding = 0.0
    style.scrollbar_rounding = 0.0
    for slot, (role, alpha) in IMGUI_COLOR_ROLES.items():
        style.set_color_(int(slot), rgba(role, alpha))
