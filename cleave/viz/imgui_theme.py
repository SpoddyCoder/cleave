"""Theme roles applied to ImGui once per frame."""

from __future__ import annotations

from imgui_bundle import imgui

from cleave.viz.theme import (
    BUTTON_ACTIVE_BG,
    BUTTON_BG,
    BUTTON_HOVER_BG,
    BACKGROUND,
    BORDER_COLOR,
    DISABLED,
    FOCUS_ROW_BG_ALPHA,
    HIGHLIGHT,
    HOVER,
    HOVER_BG_ALPHA,
    MODAL_SCRIM_ALPHA,
    SELECTED_WASH_ALPHA,
    TRANSPORT_RULE,
    VALUE,
)

_HIGHLIGHT_WASH = FOCUS_ROW_BG_ALPHA / 255.0
_SELECTED_WASH = SELECTED_WASH_ALPHA / 255.0
_HOVER_WASH = HOVER_BG_ALPHA / 255.0
# Same black scrim as the pygame modal underlay.
_SCRIM = MODAL_SCRIM_ALPHA / 255.0

IMGUI_COLOR_ROLES: dict[imgui.Col_, tuple[tuple[int, int, int], float]] = {
    imgui.Col_.text: (VALUE, 1.0),
    imgui.Col_.text_disabled: (DISABLED, 1.0),
    imgui.Col_.window_bg: (BACKGROUND, 1.0),
    imgui.Col_.child_bg: (BACKGROUND, 1.0),
    imgui.Col_.popup_bg: (BACKGROUND, 1.0),
    imgui.Col_.menu_bar_bg: (BACKGROUND, 1.0),
    imgui.Col_.border: (BORDER_COLOR, 1.0),
    imgui.Col_.header: (HIGHLIGHT, _SELECTED_WASH),
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
    imgui.Col_.text_selected_bg: (HIGHLIGHT, _HIGHLIGHT_WASH),
    imgui.Col_.nav_highlight: (HIGHLIGHT, 1.0),
    imgui.Col_.modal_window_dim_bg: (BACKGROUND, _SCRIM),
}


def rgba(rgb: tuple[int, int, int], alpha: float = 1.0) -> imgui.ImVec4:
    return imgui.ImVec4(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, alpha)


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
