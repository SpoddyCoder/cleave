"""Palette roles applied to ImGui once per frame."""

from __future__ import annotations

import math
from collections.abc import Iterator
from contextlib import contextmanager

from imgui_bundle import imgui

from cleave.viz.theme import palette, ui_chrome_px


def imgui_color_roles() -> dict[imgui.Col_, tuple[tuple[int, int, int], float]]:
    """ImGui colour slots from the live palette, each with its alpha."""
    p = palette()
    hover_wash = p.hover_bg_alpha / 255.0
    return {
        imgui.Col_.text: (p.value, 1.0),
        imgui.Col_.text_disabled: (p.disabled, 1.0),
        imgui.Col_.window_bg: (p.background, 1.0),
        imgui.Col_.child_bg: (p.background, 1.0),
        imgui.Col_.popup_bg: (p.surface_bg, 1.0),
        imgui.Col_.menu_bar_bg: (p.background, 1.0),
        imgui.Col_.border: (p.surface_edge, 1.0),
        imgui.Col_.header: (p.row_select_tint, p.row_selected_alpha[0]),
        imgui.Col_.header_hovered: (p.hover, hover_wash),
        imgui.Col_.header_active: (p.hover, hover_wash),
        imgui.Col_.button: (p.button_bg, 1.0),
        imgui.Col_.button_hovered: (p.button_hover_bg, 1.0),
        imgui.Col_.button_active: (p.button_active_bg, 1.0),
        imgui.Col_.frame_bg: (p.background, 1.0),
        imgui.Col_.title_bg: (p.background, 1.0),
        imgui.Col_.title_bg_active: (p.background, 1.0),
        imgui.Col_.title_bg_collapsed: (p.background, 1.0),
        imgui.Col_.check_mark: (p.value, 1.0),
        imgui.Col_.separator: (p.transport_rule, 1.0),
        imgui.Col_.text_selected_bg: (p.row_select_tint, 0.5),
        imgui.Col_.nav_highlight: (p.row_focus_edge, 1.0),
        imgui.Col_.scrollbar_bg: (p.scrollbar_track, 1.0),
        imgui.Col_.scrollbar_grab: (p.scrollbar_thumb, 1.0),
        imgui.Col_.scrollbar_grab_hovered: (p.scrollbar_thumb_hover, 1.0),
        imgui.Col_.scrollbar_grab_active: (p.scrollbar_thumb_hover, 1.0),
        imgui.Col_.modal_window_dim_bg: (p.background, p.modal_scrim_alpha / 255.0),
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
    imgui.push_style_color(imgui.Col_.window_bg, rgba(palette().surface_bg))
    imgui.push_style_color(imgui.Col_.child_bg, rgba(palette().surface_bg))
    imgui.push_style_color(imgui.Col_.border, rgba(palette().surface_edge))
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
    """Write ``imgui_color_roles()`` and the shell's square corners onto the style."""
    style = imgui.get_style()
    style.window_rounding = 0.0
    style.frame_rounding = 0.0
    style.popup_rounding = 0.0
    style.scrollbar_rounding = 0.0
    for slot, (role, alpha) in imgui_color_roles().items():
        style.set_color_(int(slot), rgba(role, alpha))
