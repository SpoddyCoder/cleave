"""Palette roles applied to ImGui once per frame."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from imgui_bundle import imgui

from cleave.viz.theme import palette, row_half_pad_px


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
        imgui.Col_.nav_cursor: (p.row_focus_edge, 1.0),
        imgui.Col_.scrollbar_bg: (p.scrollbar_track, 1.0),
        imgui.Col_.scrollbar_grab: (p.scrollbar_thumb, 1.0),
        imgui.Col_.scrollbar_grab_hovered: (p.scrollbar_thumb_hover, 1.0),
        imgui.Col_.scrollbar_grab_active: (p.scrollbar_thumb_hover, 1.0),
        imgui.Col_.modal_window_dim_bg: (p.modal_scrim, p.modal_scrim_alpha / 255.0),
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


def shift(rgb: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    """Lighten *rgb* by a positive *amount*, darken it by a negative one (-1..1)."""
    return lighten(rgb, amount) if amount >= 0 else darken(rgb, -amount)


def shift_brightness(rgb: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    """Brighten *rgb* by a positive *amount*, darken it by a negative one (-1..1)."""
    return brighten(rgb, amount) if amount >= 0 else darken(rgb, -amount)


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


# The sizes ``ImGuiStyle::ScaleAllSizes`` scales, as imgui-bundle attributes,
# except border widths, which stay as the theme sets them.
_STYLE_SIZE_FIELDS = (
    "window_padding",
    "window_rounding",
    "window_min_size",
    "window_border_hover_padding",
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
    "scrollbar_padding",
    "scrollbar_rounding",
    "grab_min_size",
    "grab_rounding",
    "log_slider_deadzone",
    "tab_rounding",
    "tab_min_width_base",
    "tab_min_width_shrink",
    "separator_text_padding",
    "display_window_padding",
    "display_safe_area_padding",
    "mouse_cursor_scale",
)



def padded_row_spacing_y() -> float:
    """Item spacing between padded rows.

    Selectables grow by half the item spacing above and below, so this puts
    ``row_half_pad_px`` above and below every row's text. Whole pixels keep
    the measured navigator height the same from frame to frame, and an even
    count splits evenly above and below, so the text stays centred in its
    fill. It does not read the live style, so it holds inside
    ``padded_rows``.
    """
    return 2.0 * row_half_pad_px()


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


def two_line_row_height() -> float:
    """Selectable height for a two-line row: each line gets a full padded row,
    so the row is as tall as two single rows."""
    return imgui.get_text_line_height() + row_band_side()


def second_line_drop() -> float:
    """How far a two-line row's second line sits below its first: one padded row."""
    return row_band_side()


def first_line_band(item_min_y: float) -> tuple[float, float]:
    """Top and bottom of a two-line row's first line, from the item rect's top.

    Icons and arrows on the first line are this tall, as on a single row.
    """
    return item_min_y, item_min_y + row_band_side()


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
