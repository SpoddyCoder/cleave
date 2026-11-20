"""Colour palettes and layout constants for the editor chrome.

A theme is a named ``Palette``: one frozen dataclass holding every colour role
below plus its alphas and shading amounts. ``ULTRAVIOLET`` is the default
built-in theme; ``CHOCOLATE`` and ``MINT`` are dark alternatives and
``DAYLIGHT`` is light. Draw code reads the live one with ``palette()`` at
draw time, never at import; ``set_palette()`` switches it and bumps
``palette_generation()`` so caches that hold drawn pixels rebuild. Roles are
named for what they do, not their colour; the colours named here are
Ultraviolet's. No role assumes a dark or light theme. User theme files
(``user_themes.py``) add palettes after the built-ins through
``set_user_palettes()``.

Typography roles for the live tuning overlay (text on the panel background):
  value    — emphasised text (white) for values and state indicators, and text
             on a selected or focused row, whose band is see-through
  label    — periwinkle text for row labels and prefixes
  muted    — blue-grey text for headings, shortcuts, and unchosen options
  disabled — cool grey text when a row, icon, or value on the panel is inactive
  off_control_text — the label, value, or chosen option on a switched-off,
             refused, or dimmed control (on button_off_bg / button_off_chosen_bg)
  off_control_muted — an unchosen option or combo caret on such a control
  locked   — tinted text for locked sub-rows that cannot be edited
  locked_muted — an unchosen option on a locked control

Text on opaque fills. Text or a glyph on a solid fill uses that fill's on_ role,
never value, so a light panel can carry dark text and a strong fill light text:
  on_hover, on_hover_muted - a plain button under the pointer or held, an open
    combo, and a LIT menu or choice list row (on_hover_muted is its shortcut)
  on_primary - a primary fill: a chosen segment and a dialog's confirm button
  on_danger - a destructive dialog's confirm button
  on_accent - a heading on the accent gradient (title bars, the inspector title)
  on_lit_icon - a glyph on a lit nav_on_bg, solo_bg, armed_bg, or rec_bg fill
  notification_on_fill, nav_lock_glyph, override_glyph, on_notice - glyphs and
    text on the notification, lock, override, and notice fills

Accent colors for modes and icons (not label/value roles):
  highlight, error_notification, notification_on_fill, move_mode, lock_icon,
  preset_icon, preset_file_icon,
  timeline_track_colors, timeline_off_segment, bar_grid, song_bound, playhead, playhead_flash,
  song_marker, song_marker_selected, calibration_flash

Buttons (fills, not text roles). Each tone has a rest fill, a lit hover fill
and border, and a pressed fill; button_paint.button_look() turns them into a
vertical gradient, border, and (primary and danger) an outer glow:
  button_bg, button_border - every plain panel button, segment, and combo box at rest
  button_hover_bg, button_hover_border, button_active_bg - a plain button, unchosen
    segment, or combo under the pointer (electric violet), and held down
  button_primary_bg (+ _border, _hover_bg, _hover_border, _active_bg) - the confirm button of
    a dialog, and a selected segment
  button_off_bg, button_off_border - the OFF tone: a button, segment, or combo on a
    switched-off or locked page, or one that refuses a press, at rest. Darker and
    recessed, so off_control_text stays readable on it; it lights like a plain
    button under the pointer
  button_off_chosen_bg, button_off_chosen_border - the chosen segment of such a
    control, a dusky blue
  button_danger_bg (+ _border, _hover_bg, _hover_border, _active_bg) - the confirm button of
    a destructive dialog
  button_sheen, button_shade - how far the top lightens and the bottom darkens
  button_glow_alpha - the outer glow around a lit primary or danger button
  The open combo list is a floating surface (below); its highlighted row is the
    LIT row look and its chosen tick is highlight
  nav_on_bg, solo_bg, nav_lock_bg - lit navigator on, solo, and lock icons
    (nav_lock_glyph is the dark lock icon on its amber fill)
  notice_bg - the lit amber icon of a layer with notices but no problem (a
    problem lights it in button_danger_bg)

Colour language. Violet is the pointer (button hover, icon hover, row hover, a
lit menu or list row). Blue is the selection and the keyboard (a selected
segment, the selected row, the focused row and panel). Yellow (highlight) is a
signal on top of those: a lit row's marker bar, a chosen tick, a caret, the live
preset, info lines, and an icon glyph under the pointer. It is never a fill.

Rows (row_paint.row_look turns them into a band, edge, and marker bar):
  hover, hover_bg_alpha - flat violet wash on a row under the pointer
  row_select_tint - the blue a selected or focused row fades from, left to right
  row_selected_alpha, row_selected_bar - the current navigator page, or a chosen
    row whose list does not hold the keys
  row_focused_alpha, row_focused_bar, row_focus_edge - the row the keys act on
    (row_focus_edge also rings a focused panel button)
  ROW_BAR_PX - marker bar width at shell scale 1.0
  The LIT look (menu and choice list rows) is the plain button hover gradient
  with a highlight bar. Text on a selected or focused row is value; on a lit
  row it is on_hover.

Floating surfaces (menus, context menus, the open choice list, dialogs, the
file picker, info panels, tooltips):
  surface_bg, surface_edge - deep ink with a violet edge; surface_text is soft
    white for unlit choice list options
  modal_scrim, modal_scrim_alpha - the wash over the shell behind a dialog
  floating_surface() in imgui_theme pushes them onto a window

Accent gradient:
  accent_from, accent_to - blue into violet, left to right: progress bar fills
    and the inspector title's new-page swipe
  Title bars (title_bar.py) fill help column section titles and modal titles
    with the full accent gradient, the title in on_accent

Shell rules (not text roles):
  panel_edge - idle navigator, inspector, and strip outline
  panel_focus_edge - outline of the panel that holds the keys
  transport_rule — rule under the menu bar and transport, and ImGui separators
  navigator_tree_line — connector lines between navigator rows
  inspector_divider — thin rule under the inspector title and above its buttons
  icon_hover_fg - glyph of an icon or text button under the pointer (highlight)
  icon_hover_bg, icon_hover_bg_alpha - violet wash behind it, complementary to the
    yellow glyph; icon_hover_edge is its opaque 1px outline
  icon_lit_hover_lift - how far a lit icon's own fill brightens under the pointer
    (negative darkens)
  icon_lit_hover_edge_lift - how far that hovered fill's outline lightens from it
    (negative darkens)

Layout scale:
  BASE_UI_SCALE (1.44) is the editor chrome at 100%. The Settings > UI > UI scale
  preference multiplies it through set_ui_scale_percent(); ui_scale() is the live
  factor for every panel, modal, help column, and the timeline strip.
  ImGui style sizes and shell pixel values are tuned at a factor of 1.0, so
  shell_scale() (SHELL_UI_SCALE 1.2 at 100%) scales them. Read metrics
  at draw time, never at import, so a scale change applies on the next frame.

The timeline strip draws at TIMELINE_SCALE of the UI scale. Its panel height is
derived from a fixed per-row height (BASE_TIMELINE_ROW_HEIGHT) times row count plus
padding and gaps via timeline_panel_height_px().

Use tuning_ui_metrics(), timeline_ui_metrics(), timeline_panel_height_px(), and
ui_px() for scaled layout; BORDER_WIDTH is not scaled.

See [live-tuning-ui](../.claude/rules/live-tuning-ui.md) for how
rows apply these roles, including intentional exceptions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from cleave.config_schema.editor import DEFAULT_UI_SCALE, clamp_ui_scale

BASE_UI_FONT_SIZE: int = 14
BASE_UI_SCALE: float = 1.44
# ImGui style and shell pixel values at 100% UI scale.
SHELL_UI_SCALE: float = 1.2
# Edge of the square mouse pointer image at 100% UI scale. The arrow fills
# most of it.
POINTER_BASE_PX: int = 24
# White outline around the pointer at 100% UI scale.
POINTER_OUTLINE_PX: float = 1.5
BASE_TIMELINE_ROW_HEIGHT: int = 25
# The timeline strip is this fraction of the UI scale at every scale.
TIMELINE_SCALE: float = 0.8

_ui_scale_percent: int = DEFAULT_UI_SCALE
_ui_scale_generation: int = 0


def scale_px(value: float, *, scale: float) -> int:
    return max(1, round(value * scale))


def set_ui_scale_percent(percent: int) -> None:
    """Set the editor UI scale. Bumps the generation when the value changes."""
    global _ui_scale_percent, _ui_scale_generation
    clamped = clamp_ui_scale(percent)
    if clamped == _ui_scale_percent:
        return
    _ui_scale_percent = clamped
    _ui_scale_generation += 1


def ui_scale_percent() -> int:
    return _ui_scale_percent


def ui_scale() -> float:
    """Live layout factor: BASE_UI_SCALE at 100%."""
    return BASE_UI_SCALE * _ui_scale_percent / 100.0


def shell_scale() -> float:
    """Live factor for ImGui style sizes and shell pixel values: SHELL_UI_SCALE at 100%."""
    return SHELL_UI_SCALE * _ui_scale_percent / 100.0


def ui_scale_generation() -> int:
    """Changes whenever the UI scale changes, so caches can rebuild."""
    return _ui_scale_generation


def ui_px(value: float) -> int:
    """A base (unscaled) pixel value at the live UI scale."""
    return scale_px(value, scale=ui_scale())


def ui_chrome_px(value: float) -> float:
    """A shell pixel value tuned at a factor of 1.0, at the live UI scale."""
    return value * shell_scale()


# Dear ImGui's default ItemSpacing.y, before the shell scale.
IMGUI_ITEM_SPACING_Y = 4.0
# Extra space above and below each navigator, inspector, menu, and dialog
# row's highlight, so it clears the text and a focused row's outline clears
# its segments, combo box, or buttons.
ROW_PAD_Y = 2.0


def row_half_pad_px() -> int:
    """Space above and below a padded row's text line, in whole pixels.

    Half the item spacing plus ROW_PAD_Y. Shell rows and dialog rows share it,
    so a row and its square icon buttons are the same height everywhere. The
    item spacing is truncated the way ImGui's ``ScaleAllSizes`` truncates it.
    """
    scale = shell_scale()
    spacing = math.trunc(IMGUI_ITEM_SPACING_Y * scale) + 2.0 * ROW_PAD_Y * scale
    return math.floor(spacing * 0.5 + 0.5)


@dataclass(frozen=True)
class TuningUiMetrics:
    font_size: int
    padding: int
    line_gap: int
    margin: int
    scrollbar_width: int
    scrollbar_content_gap: int
    tree_indent: int
    row_icon_suffix_gap: int
    icon_label_gap: int
    icon_suffix_gap: int
    modal_panel_pad_x: int
    modal_panel_pad_y: int


@dataclass(frozen=True)
class TimelineUiMetrics:
    font_size: int
    padding: int
    row_height: int
    row_gap: int
    bar_vertical_inset: int
    playhead_width: int
    rec_badge_gap: int
    rec_badge_pad_y: int
    scrollbar_height: int
    scrollbar_gap: int
    scrollbar_min_thumb: int


def tuning_ui_metrics(
    *,
    scale: float | None = None,
) -> TuningUiMetrics:
    if scale is None:
        scale = ui_scale()
    return TuningUiMetrics(
        font_size=scale_px(BASE_UI_FONT_SIZE, scale=scale),
        padding=scale_px(8, scale=scale),
        line_gap=scale_px(3, scale=scale),
        margin=scale_px(10, scale=scale),
        scrollbar_width=scale_px(15, scale=scale),
        scrollbar_content_gap=scale_px(4, scale=scale),
        tree_indent=scale_px(8, scale=scale),
        row_icon_suffix_gap=scale_px(4, scale=scale),
        icon_label_gap=scale_px(4, scale=scale),
        icon_suffix_gap=scale_px(4, scale=scale),
        modal_panel_pad_x=scale_px(12, scale=scale),
        modal_panel_pad_y=scale_px(10, scale=scale),
    )


def timeline_ui_metrics(*, scale: float | None = None) -> TimelineUiMetrics:
    """Timeline strip metrics for UI *scale* (default: the live scale)."""
    if scale is None:
        scale = ui_scale()
    scale *= TIMELINE_SCALE
    return TimelineUiMetrics(
        font_size=scale_px(14, scale=scale),
        padding=scale_px(8, scale=scale),
        row_height=scale_px(BASE_TIMELINE_ROW_HEIGHT, scale=scale),
        row_gap=scale_px(2, scale=scale),
        bar_vertical_inset=scale_px(3, scale=scale),
        playhead_width=scale_px(2, scale=scale),
        rec_badge_gap=scale_px(4, scale=scale),
        rec_badge_pad_y=scale_px(4, scale=scale),
        scrollbar_height=scale_px(8, scale=scale),
        scrollbar_gap=scale_px(3, scale=scale),
        scrollbar_min_thumb=scale_px(12, scale=scale),
    )


def timeline_panel_height_px(
    row_count: int,
    *,
    scale: float | None = None,
) -> int:
    """Scaled bottom timeline strip height in pixels: rows, then the scrollbar."""
    if row_count <= 0:
        return 0
    m = timeline_ui_metrics(scale=scale)
    rows_h = row_count * m.row_height + max(0, row_count - 1) * m.row_gap
    return m.padding * 2 + rows_h + m.scrollbar_gap + m.scrollbar_height


RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Palette:
    """Every colour role the editor chrome draws with, plus its alphas and
    shading amounts. A theme is a named palette; see the module docstring for
    what each role is for. Read the live one with ``palette()`` at draw time.
    """

    id: str
    name: str

    # Shell
    background: RGB
    background_alpha: int
    modal_scrim: RGB
    modal_scrim_alpha: int
    transport_rule: RGB
    panel_edge: RGB
    panel_focus_edge: RGB
    navigator_tree_line: RGB
    inspector_divider: RGB

    # Text roles
    label: RGB
    value: RGB
    disabled: RGB
    off_control_text: RGB
    off_control_muted: RGB
    muted: RGB
    highlight: RGB
    error_notification: RGB
    notification_on_fill: RGB

    # Text on opaque fills
    on_hover: RGB
    on_hover_muted: RGB
    on_primary: RGB
    on_danger: RGB
    on_accent: RGB
    on_lit_icon: RGB

    # Icons and modes
    preset_icon: RGB
    preset_file_icon: RGB
    move_mode: RGB
    lock_icon: RGB
    locked: RGB
    locked_muted: RGB
    solo_bg: RGB
    override_bg: RGB
    nav_on_bg: RGB
    nav_lock_bg: RGB
    nav_lock_glyph: RGB
    notice_bg: RGB
    on_notice: RGB
    config_dirty: RGB
    armed_bg: RGB
    override_glyph: RGB
    override_glyph_off: RGB
    rec_bg: RGB

    # Buttons
    button_bg: RGB
    button_border: RGB
    button_hover_bg: RGB
    button_hover_border: RGB
    button_active_bg: RGB
    button_primary_bg: RGB
    button_primary_border: RGB
    button_primary_hover_bg: RGB
    button_primary_hover_border: RGB
    button_primary_active_bg: RGB
    button_off_bg: RGB
    button_off_border: RGB
    button_off_chosen_bg: RGB
    button_off_chosen_border: RGB
    button_danger_bg: RGB
    button_danger_border: RGB
    button_danger_hover_bg: RGB
    button_danger_hover_border: RGB
    button_danger_active_bg: RGB
    button_sheen: float
    button_shade: float
    button_glow_alpha: float

    # Floating surfaces and accent gradient
    surface_bg: RGB
    surface_edge: RGB
    surface_text: RGB
    accent_from: RGB
    accent_to: RGB

    # Rows
    hover: RGB
    hover_bg_alpha: int
    row_select_tint: RGB
    # Band alpha at the row's left end, then at its right end.
    row_selected_alpha: tuple[float, float]
    row_selected_bar: RGB
    row_focused_alpha: tuple[float, float]
    row_focused_bar: RGB
    row_focus_edge: RGB

    # Icon hover
    icon_hover_fg: RGB
    icon_hover_bg: RGB
    icon_hover_bg_alpha: int
    icon_hover_edge: RGB
    icon_lit_hover_lift: float
    icon_lit_hover_edge_lift: float

    # Timeline strip
    # On-section fill of each timeline track's level bar, one per layer (max 8).
    timeline_track_colors: tuple[RGB, ...]
    # Fill of a timeline track's level bar where the layer is off.
    timeline_off_segment: RGB
    bar_grid: RGB
    # Song start and end lines below the ruler, through the timeline rows.
    song_bound: RGB
    playhead: RGB
    playhead_flash: RGB
    song_marker: RGB
    song_marker_selected: RGB
    # Flash over the preview while Measure audio latency runs.
    calibration_flash: RGB
    # Timeline strip scrollbar: a faint rail and a neutral pill, so it does not
    # read as a layer row's level bar.
    timeline_scroll_rail: RGB
    timeline_scroll_thumb: RGB

    # ImGui scrollbars
    scrollbar_track: RGB
    scrollbar_thumb: RGB
    scrollbar_thumb_hover: RGB


def _ultraviolet() -> Palette:
    """Black chrome, periwinkle labels, violet pointer, blue selection, yellow signals."""
    disabled: RGB = (124, 130, 148)
    muted: RGB = (140, 151, 176)
    highlight: RGB = (255, 235, 130)
    solo: RGB = (200, 40, 40)
    violet: RGB = (128, 84, 255)
    blue: RGB = (58, 120, 215)
    button_hover_border: RGB = (170, 140, 255)
    song_bound: RGB = (58, 66, 84)
    white: RGB = (255, 255, 255)
    surface_text: RGB = (205, 212, 228)
    return Palette(
        id="ultraviolet",
        name="Ultraviolet",
        background=(0, 0, 0),
        background_alpha=255,
        modal_scrim=(0, 0, 0),
        modal_scrim_alpha=int(0.55 * 255),
        transport_rule=(52, 58, 74),
        panel_edge=(52, 58, 74),
        panel_focus_edge=(56, 108, 205),
        navigator_tree_line=(72, 82, 108),
        inspector_divider=(44, 50, 64),
        label=(165, 198, 250),
        value=white,
        disabled=disabled,
        off_control_text=(170, 177, 196),
        off_control_muted=(124, 130, 148),
        muted=muted,
        highlight=highlight,
        error_notification=(255, 140, 140),
        notification_on_fill=(0, 0, 0),
        on_hover=white,
        on_hover_muted=surface_text,
        on_primary=white,
        on_danger=white,
        on_accent=white,
        on_lit_icon=white,
        preset_icon=(255, 195, 90),
        preset_file_icon=(255, 250, 235),
        move_mode=(60, 120, 255),
        lock_icon=(235, 90, 90),
        locked=(235, 150, 150),
        locked_muted=(170, 110, 110),
        solo_bg=solo,
        override_bg=(255, 200, 60),
        nav_on_bg=(40, 140, 75),
        nav_lock_bg=(225, 140, 40),
        nav_lock_glyph=(0, 0, 0),
        notice_bg=(245, 170, 20),
        on_notice=(0, 0, 0),
        config_dirty=(255, 255, 0),
        armed_bg=solo,
        override_glyph=(0, 0, 0),
        override_glyph_off=disabled,
        rec_bg=(220, 0, 0),
        button_bg=(48, 54, 66),
        button_border=(85, 95, 115),
        button_hover_bg=(84, 62, 168),
        button_hover_border=button_hover_border,
        button_active_bg=(52, 36, 112),
        button_primary_bg=(45, 85, 150),
        button_primary_border=(83, 116, 169),
        button_primary_hover_bg=(58, 120, 215),
        button_primary_hover_border=(150, 205, 255),
        button_primary_active_bg=(32, 64, 120),
        button_off_bg=(30, 33, 42),
        button_off_border=(62, 68, 84),
        button_off_chosen_bg=(40, 52, 78),
        button_off_chosen_border=(79, 89, 110),
        button_danger_bg=solo,
        button_danger_border=(210, 79, 79),
        button_danger_hover_bg=(238, 58, 52),
        button_danger_hover_border=(255, 175, 155),
        button_danger_active_bg=(150, 26, 26),
        button_sheen=0.14,
        button_shade=0.22,
        button_glow_alpha=0.32,
        surface_bg=(20, 18, 34),
        surface_edge=(112, 88, 210),
        surface_text=surface_text,
        accent_from=blue,
        accent_to=violet,
        hover=violet,
        hover_bg_alpha=40,
        row_select_tint=blue,
        row_selected_alpha=(0.30, 0.06),
        row_selected_bar=blue,
        row_focused_alpha=(0.50, 0.14),
        row_focused_bar=(124, 184, 255),
        row_focus_edge=(46, 94, 172),
        icon_hover_fg=highlight,
        icon_hover_bg=violet,
        icon_hover_bg_alpha=120,
        icon_hover_edge=(122, 92, 220),
        icon_lit_hover_lift=0.25,
        icon_lit_hover_edge_lift=0.45,
        timeline_track_colors=(
            (127, 209, 255),  # sky
            (183, 166, 255),  # lavender
            (255, 210, 127),  # amber
            (156, 240, 176),  # mint
            (246, 166, 200),  # pink
            (255, 163, 143),  # coral
            (212, 238, 138),  # lime
            (128, 232, 216),  # aqua
        ),
        timeline_off_segment=(40, 40, 40),
        bar_grid=(70, 95, 130),
        song_bound=song_bound,
        playhead=(90, 50, 130),
        playhead_flash=(220, 170, 255),
        song_marker=(220, 40, 40),
        song_marker_selected=(255, 170, 40),
        calibration_flash=(255, 255, 255),
        timeline_scroll_rail=song_bound,
        timeline_scroll_thumb=muted,
        scrollbar_track=(26, 29, 38),
        scrollbar_thumb=(88, 98, 126),
        scrollbar_thumb_hover=button_hover_border,
    )


def _chocolate() -> Palette:
    """Dark chocolate panels, cream text, caramel accents."""
    return Palette(
        id="chocolate",
        name="Chocolate",
        background=(14, 8, 5),
        background_alpha=255,
        modal_scrim=(0, 0, 0),
        modal_scrim_alpha=150,
        transport_rule=(74, 52, 38),
        panel_edge=(74, 52, 38),
        panel_focus_edge=(200, 129, 62),
        navigator_tree_line=(106, 76, 56),
        inspector_divider=(56, 39, 28),
        label=(236, 197, 150),
        value=(255, 247, 234),
        disabled=(140, 120, 104),
        off_control_text=(196, 176, 156),
        off_control_muted=(140, 120, 104),
        muted=(171, 146, 124),
        highlight=(255, 220, 138),
        error_notification=(255, 143, 134),
        notification_on_fill=(0, 0, 0),
        on_hover=(255, 247, 234),
        on_hover_muted=(240, 226, 208),
        on_primary=(255, 247, 234),
        on_danger=(255, 247, 234),
        on_accent=(14, 8, 5),
        on_lit_icon=(255, 247, 234),
        preset_icon=(255, 190, 98),
        preset_file_icon=(255, 246, 230),
        move_mode=(70, 196, 162),
        lock_icon=(232, 90, 80),
        locked=(236, 154, 144),
        locked_muted=(173, 114, 104),
        solo_bg=(196, 42, 40),
        override_bg=(255, 200, 68),
        nav_on_bg=(47, 140, 78),
        nav_lock_bg=(226, 134, 42),
        nav_lock_glyph=(0, 0, 0),
        notice_bg=(240, 168, 30),
        on_notice=(0, 0, 0),
        config_dirty=(255, 238, 48),
        armed_bg=(196, 42, 40),
        override_glyph=(0, 0, 0),
        override_glyph_off=(140, 120, 104),
        rec_bg=(216, 16, 16),
        button_bg=(58, 39, 28),
        button_border=(108, 80, 64),
        button_hover_bg=(110, 66, 36),
        button_hover_border=(230, 172, 108),
        button_active_bg=(74, 42, 20),
        button_primary_bg=(138, 80, 34),
        button_primary_border=(159, 112, 74),
        button_primary_hover_bg=(158, 94, 40),
        button_primary_hover_border=(255, 210, 154),
        button_primary_active_bg=(100, 58, 22),
        button_off_bg=(32, 22, 15),
        button_off_border=(74, 54, 40),
        button_off_chosen_bg=(62, 42, 26),
        button_off_chosen_border=(97, 80, 67),
        button_danger_bg=(196, 42, 40),
        button_danger_border=(207, 80, 79),
        button_danger_hover_bg=(232, 60, 52),
        button_danger_hover_border=(255, 176, 158),
        button_danger_active_bg=(146, 26, 26),
        button_sheen=0.14,
        button_shade=0.24,
        button_glow_alpha=0.3,
        surface_bg=(28, 18, 12),
        surface_edge=(168, 104, 58),
        surface_text=(240, 226, 208),
        accent_from=(168, 92, 42),
        accent_to=(240, 176, 100),
        hover=(208, 138, 68),
        hover_bg_alpha=44,
        row_select_tint=(200, 129, 62),
        row_selected_alpha=(0.3, 0.06),
        row_selected_bar=(208, 138, 68),
        row_focused_alpha=(0.5, 0.14),
        row_focused_bar=(255, 201, 138),
        row_focus_edge=(156, 96, 48),
        icon_hover_fg=(255, 226, 168),
        icon_hover_bg=(168, 100, 46),
        icon_hover_bg_alpha=130,
        icon_hover_edge=(208, 138, 68),
        icon_lit_hover_lift=0.25,
        icon_lit_hover_edge_lift=0.45,
        timeline_track_colors=(
            # An assorted box: caramel, strawberry, mint, pistachio, orange cream,
            # violet cream, vanilla, blueberry.
            (255, 194, 122),
            (245, 154, 178),
            (157, 226, 192),
            (214, 227, 140),
            (255, 160, 114),
            (200, 168, 255),
            (242, 220, 182),
            (136, 208, 234),
        ),
        timeline_off_segment=(40, 40, 40),
        bar_grid=(106, 76, 54),
        song_bound=(74, 52, 38),
        playhead=(122, 66, 32),
        playhead_flash=(255, 210, 160),
        song_marker=(220, 42, 40),
        song_marker_selected=(255, 176, 42),
        calibration_flash=(255, 255, 255),
        timeline_scroll_rail=(74, 52, 38),
        timeline_scroll_thumb=(171, 146, 124),
        scrollbar_track=(30, 20, 14),
        scrollbar_thumb=(108, 80, 64),
        scrollbar_thumb_hover=(230, 172, 108),
    )


def _mint() -> Palette:
    """Deep green-black panels, pale mint text, fresh mint accents."""
    return Palette(
        id="mint",
        name="Mint",
        background=(4, 11, 9),
        background_alpha=255,
        modal_scrim=(0, 0, 0),
        modal_scrim_alpha=150,
        transport_rule=(36, 68, 60),
        panel_edge=(36, 68, 60),
        panel_focus_edge=(60, 207, 160),
        navigator_tree_line=(53, 96, 86),
        inspector_divider=(26, 49, 43),
        label=(158, 236, 204),
        value=(242, 255, 249),
        disabled=(108, 138, 130),
        off_control_text=(168, 196, 188),
        off_control_muted=(108, 138, 130),
        muted=(134, 168, 158),
        highlight=(255, 240, 138),
        error_notification=(255, 143, 140),
        notification_on_fill=(0, 0, 0),
        on_hover=(242, 255, 249),
        on_hover_muted=(214, 242, 232),
        on_primary=(242, 255, 249),
        on_danger=(242, 255, 249),
        on_accent=(4, 11, 9),
        on_lit_icon=(242, 255, 249),
        preset_icon=(255, 195, 90),
        preset_file_icon=(242, 255, 249),
        move_mode=(76, 140, 255),
        lock_icon=(235, 90, 90),
        locked=(235, 150, 150),
        locked_muted=(170, 110, 110),
        solo_bg=(200, 40, 40),
        override_bg=(255, 200, 60),
        nav_on_bg=(74, 132, 20),
        nav_lock_bg=(225, 140, 40),
        nav_lock_glyph=(0, 0, 0),
        notice_bg=(245, 170, 20),
        on_notice=(0, 0, 0),
        config_dirty=(255, 255, 0),
        armed_bg=(200, 40, 40),
        override_glyph=(0, 0, 0),
        override_glyph_off=(108, 138, 130),
        rec_bg=(220, 0, 0),
        button_bg=(28, 51, 45),
        button_border=(62, 100, 89),
        button_hover_bg=(31, 107, 86),
        button_hover_border=(142, 240, 204),
        button_active_bg=(19, 74, 59),
        button_primary_bg=(22, 122, 94),
        button_primary_border=(64, 146, 123),
        button_primary_hover_bg=(25, 129, 95),
        button_primary_hover_border=(180, 255, 226),
        button_primary_active_bg=(15, 90, 69),
        button_off_bg=(15, 28, 24),
        button_off_border=(44, 72, 64),
        button_off_chosen_bg=(26, 58, 50),
        button_off_chosen_border=(67, 93, 87),
        button_danger_bg=(200, 40, 40),
        button_danger_border=(210, 79, 79),
        button_danger_hover_bg=(238, 58, 52),
        button_danger_hover_border=(255, 175, 155),
        button_danger_active_bg=(150, 26, 26),
        button_sheen=0.14,
        button_shade=0.22,
        button_glow_alpha=0.3,
        surface_bg=(12, 25, 21),
        surface_edge=(47, 166, 130),
        surface_text=(214, 242, 232),
        accent_from=(30, 156, 120),
        accent_to=(124, 240, 196),
        hover=(60, 207, 160),
        hover_bg_alpha=40,
        row_select_tint=(47, 184, 142),
        row_selected_alpha=(0.3, 0.06),
        row_selected_bar=(60, 207, 160),
        row_focused_alpha=(0.5, 0.14),
        row_focused_bar=(168, 255, 224),
        row_focus_edge=(35, 134, 106),
        icon_hover_fg=(255, 240, 138),
        icon_hover_bg=(36, 160, 124),
        icon_hover_bg_alpha=120,
        icon_hover_edge=(60, 207, 160),
        icon_lit_hover_lift=0.25,
        icon_lit_hover_edge_lift=0.45,
        timeline_track_colors=(
            (127, 240, 200),
            (140, 207, 255),
            (255, 210, 127),
            (246, 166, 200),
            (200, 180, 255),
            (214, 240, 138),
            (255, 163, 143),
            (230, 255, 244),
        ),
        timeline_off_segment=(40, 40, 40),
        bar_grid=(46, 90, 78),
        song_bound=(36, 68, 60),
        playhead=(26, 106, 84),
        playhead_flash=(180, 255, 226),
        song_marker=(220, 40, 40),
        song_marker_selected=(255, 170, 40),
        calibration_flash=(255, 255, 255),
        timeline_scroll_rail=(36, 68, 60),
        timeline_scroll_thumb=(134, 168, 158),
        scrollbar_track=(14, 26, 23),
        scrollbar_thumb=(62, 100, 89),
        scrollbar_thumb_hover=(142, 240, 204),
    )


def _daylight() -> Palette:
    """Near-white chrome, ink text, pale violet pointer, blue selection, amber signals."""
    white: RGB = (255, 255, 255)
    ink: RGB = (20, 22, 30)
    disabled: RGB = (128, 134, 150)
    muted: RGB = (92, 100, 122)
    highlight: RGB = (150, 92, 0)
    solo: RGB = (200, 40, 40)
    violet: RGB = (128, 84, 255)
    blue: RGB = (45, 100, 200)
    rule: RGB = (208, 213, 226)
    song_bound: RGB = (190, 196, 210)
    off_text: RGB = (80, 86, 104)
    return Palette(
        id="daylight",
        name="Daylight",
        background=(246, 247, 251),
        background_alpha=255,
        modal_scrim=(20, 22, 40),
        modal_scrim_alpha=int(0.35 * 255),
        transport_rule=rule,
        panel_edge=rule,
        panel_focus_edge=(58, 110, 210),
        navigator_tree_line=(176, 184, 204),
        inspector_divider=(222, 226, 236),
        label=(38, 72, 150),
        value=ink,
        disabled=disabled,
        off_control_text=off_text,
        off_control_muted=disabled,
        muted=muted,
        highlight=highlight,
        error_notification=(190, 30, 30),
        notification_on_fill=white,
        on_hover=(30, 20, 70),
        on_hover_muted=(90, 80, 130),
        on_primary=white,
        on_danger=white,
        on_accent=white,
        on_lit_icon=white,
        preset_icon=(200, 120, 0),
        preset_file_icon=(120, 90, 40),
        move_mode=(30, 90, 220),
        lock_icon=(200, 40, 40),
        locked=(170, 60, 60),
        locked_muted=(160, 95, 95),
        solo_bg=solo,
        override_bg=(240, 180, 40),
        nav_on_bg=(30, 130, 65),
        nav_lock_bg=(225, 140, 40),
        nav_lock_glyph=(0, 0, 0),
        notice_bg=(220, 150, 0),
        on_notice=(0, 0, 0),
        config_dirty=(200, 150, 0),
        armed_bg=solo,
        override_glyph=(0, 0, 0),
        override_glyph_off=disabled,
        rec_bg=(210, 0, 0),
        button_bg=(230, 232, 240),
        button_border=(182, 188, 204),
        button_hover_bg=(222, 212, 255),
        button_hover_border=(140, 110, 230),
        button_active_bg=(196, 180, 250),
        button_primary_bg=blue,
        button_primary_border=(30, 80, 170),
        button_primary_hover_bg=(52, 112, 212),
        button_primary_hover_border=(20, 60, 150),
        button_primary_active_bg=(32, 72, 160),
        button_off_bg=(238, 240, 245),
        button_off_border=(214, 218, 228),
        button_off_chosen_bg=(208, 216, 236),
        button_off_chosen_border=(160, 172, 204),
        button_danger_bg=(190, 30, 30),
        button_danger_border=(150, 20, 20),
        button_danger_hover_bg=(215, 40, 36),
        button_danger_hover_border=(120, 10, 10),
        button_danger_active_bg=(150, 26, 26),
        button_sheen=0.12,
        button_shade=0.10,
        button_glow_alpha=0.25,
        surface_bg=white,
        surface_edge=(128, 96, 230),
        surface_text=(50, 56, 72),
        accent_from=blue,
        accent_to=(110, 70, 220),
        hover=violet,
        hover_bg_alpha=40,
        row_select_tint=(58, 120, 215),
        row_selected_alpha=(0.18, 0.04),
        row_selected_bar=(58, 120, 215),
        row_focused_alpha=(0.28, 0.08),
        row_focused_bar=(40, 90, 190),
        row_focus_edge=(70, 120, 210),
        icon_hover_fg=(88, 40, 190),
        icon_hover_bg=violet,
        icon_hover_bg_alpha=50,
        icon_hover_edge=(150, 120, 240),
        icon_lit_hover_lift=-0.15,
        icon_lit_hover_edge_lift=-0.35,
        timeline_track_colors=(
            (30, 120, 190),  # sky
            (110, 80, 210),  # lavender
            (190, 120, 0),  # amber
            (30, 150, 80),  # mint
            (200, 60, 130),  # pink
            (210, 80, 50),  # coral
            (110, 150, 20),  # lime
            (0, 150, 140),  # aqua
        ),
        timeline_off_segment=(220, 223, 230),
        bar_grid=(190, 200, 220),
        song_bound=song_bound,
        playhead=(120, 80, 200),
        playhead_flash=(200, 150, 255),
        song_marker=(200, 40, 40),
        song_marker_selected=(230, 140, 0),
        calibration_flash=(255, 255, 255),
        timeline_scroll_rail=song_bound,
        timeline_scroll_thumb=muted,
        scrollbar_track=(232, 234, 240),
        scrollbar_thumb=(180, 186, 204),
        scrollbar_thumb_hover=(140, 110, 230),
    )


ULTRAVIOLET: Palette = _ultraviolet()
CHOCOLATE: Palette = _chocolate()
MINT: Palette = _mint()
DAYLIGHT: Palette = _daylight()
# Built-in themes, in the order the Theme setting lists them.
BUILTIN_PALETTES: tuple[Palette, ...] = (ULTRAVIOLET, CHOCOLATE, MINT, DAYLIGHT)

_palette: Palette = ULTRAVIOLET
_palette_generation: int = 0
# Themes loaded from the user's theme files; the Theme setting lists them
# after the built-ins.
_user_palettes: tuple[Palette, ...] = ()


def palette() -> Palette:
    """The live theme's palette. Call at draw time, never at import."""
    return _palette


def set_palette(value: Palette) -> None:
    """Switch the live palette. Bumps the generation when it changes."""
    global _palette, _palette_generation
    if value == _palette:
        return
    _palette = value
    _palette_generation += 1


def set_user_palettes(values: tuple[Palette, ...]) -> None:
    """Replace the themes loaded from user theme files."""
    global _user_palettes
    _user_palettes = tuple(values)


def all_palettes() -> tuple[Palette, ...]:
    """Built-in themes, then user themes, in the order the Theme setting lists them."""
    return BUILTIN_PALETTES + _user_palettes


def palette_for_theme(theme_id: str) -> Palette:
    """The palette with *theme_id*, or Ultraviolet for an unknown id."""
    for candidate in all_palettes():
        if candidate.id == theme_id:
            return candidate
    return ULTRAVIOLET


def theme_ids() -> tuple[str, ...]:
    """Every theme the Theme setting offers, in order."""
    return tuple(candidate.id for candidate in all_palettes())


def theme_label(theme_id: str) -> str:
    """The name the Theme setting shows for *theme_id*."""
    return palette_for_theme(theme_id).name


def palette_generation() -> int:
    """Changes whenever the palette changes, so caches can rebuild."""
    return _palette_generation


BORDER_WIDTH: int = 2
# Progress bars: a thick surface_edge border and a gap before the accent fill.
PROGRESS_BAR_BORDER_WIDTH: int = 2 * BORDER_WIDTH
PROGRESS_BAR_FILL_GAP: int = 2
# Marker bar width of a selected, focused, or lit row at shell scale 1.0.
ROW_BAR_PX: float = 2.5

FADE_DURATION_SEC: float = 2.0
