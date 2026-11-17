"""Colour palettes and layout constants for the editor chrome.

A theme is a named ``Palette``: one frozen dataclass holding every colour role
below plus its alphas and shading amounts. ``ULTRAVIOLET`` is the built-in
theme. Draw code reads the live one with ``palette()`` at draw time, never at
import; ``set_palette()`` switches it and bumps ``palette_generation()`` so
caches that hold drawn pixels rebuild. Roles are named for what they do, not
their colour; the descriptions here are Ultraviolet's.

Typography roles for the live tuning overlay:
  value    — white text for values and state indicators (default), and any
             text on a selected, focused, or lit row
  label    — periwinkle text for row labels and prefixes
  muted    — blue-grey text for headings, shortcuts, and unchosen options
  disabled — cool grey text when a row, icon, or value on the black panel is inactive
  off_control_text — the label, value, or chosen option on a switched-off,
             refused, or dimmed control (on button_off_bg / button_off_chosen_bg)
  off_control_muted — an unchosen option or combo caret on such a control
  locked   — tinted text for locked sub-rows that cannot be edited
  locked_muted — an unchosen option on a locked control

Accent colors for modes and icons (not label/value roles):
  highlight, error_notification, notification_on_fill, move_mode, lock_icon,
  preset_icon, preset_file_icon,
  timeline_track_colors, bar_grid, song_bound, playhead, playhead_flash,
  song_marker, song_marker_selected

Buttons (fills, not text roles). Each tone has a rest fill, a lit hover fill
and border, and a pressed fill; button_paint.button_look() turns them into a
vertical gradient, border, and (primary and danger) an outer glow:
  button_bg, button_border - every plain panel button, segment, and combo box at rest
  button_hover_bg, button_hover_border, button_active_bg - a plain button, unchosen
    segment, or combo under the pointer (electric violet), and held down
  button_primary_bg (+ _hover_bg, _hover_border, _active_bg) - the confirm button of
    a dialog, and a selected segment
  button_off_bg, button_off_border - the OFF tone: a button, segment, or combo on a
    switched-off or locked page, or one that refuses a press, at rest. Darker and
    recessed, so off_control_text stays readable on it; it lights like a plain
    button under the pointer
  button_off_chosen_bg - the chosen segment of such a control, a dusky blue
  button_danger_bg (+ _hover_bg, _hover_border, _active_bg) - the confirm button of
    a destructive dialog
  button_sheen, button_shade - how far the top lightens and the bottom darkens
  button_glow_alpha - the outer glow around a lit primary or danger button
  The open combo list is a floating surface (below); its highlighted row is the
    LIT row look and its chosen tick is highlight
  nav_on_bg, solo_bg, nav_lock_bg - lit navigator on, solo, and lock icons
    (nav_lock_glyph is the dark lock icon on its amber fill)

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
  with a highlight bar. Text on a selected, focused, or lit row is value.

Floating surfaces (menus, context menus, the open choice list, dialogs, the
file picker, info panels, tooltips):
  surface_bg, surface_edge - deep ink with a violet edge; surface_text is soft
    white for unlit choice list options
  floating_surface() in imgui_theme pushes them onto a window

Accent gradient:
  accent_from, accent_to - blue into violet, left to right: progress bar fills
    and the inspector title's new-page swipe
  Title bars (title_bar.py) fill help column section titles and modal titles
    with the full accent gradient, the title in value

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
    button_primary_hover_bg: RGB
    button_primary_hover_border: RGB
    button_primary_active_bg: RGB
    button_off_bg: RGB
    button_off_border: RGB
    button_off_chosen_bg: RGB
    button_danger_bg: RGB
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

    # Timeline strip
    # On-section fill of each timeline track's level bar, one per layer (max 8).
    timeline_track_colors: tuple[RGB, ...]
    bar_grid: RGB
    # Song start and end lines below the ruler, through the timeline rows.
    song_bound: RGB
    playhead: RGB
    playhead_flash: RGB
    song_marker: RGB
    song_marker_selected: RGB
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
    return Palette(
        id="ultraviolet",
        name="Ultraviolet",
        background=(0, 0, 0),
        background_alpha=255,
        modal_scrim_alpha=int(0.55 * 255),
        transport_rule=(52, 58, 74),
        panel_edge=(52, 58, 74),
        panel_focus_edge=(56, 108, 205),
        navigator_tree_line=(72, 82, 108),
        inspector_divider=(44, 50, 64),
        label=(165, 198, 250),
        value=(255, 255, 255),
        disabled=disabled,
        off_control_text=(170, 177, 196),
        off_control_muted=(124, 130, 148),
        muted=muted,
        highlight=highlight,
        error_notification=(255, 140, 140),
        notification_on_fill=(0, 0, 0),
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
        button_primary_hover_bg=(58, 120, 215),
        button_primary_hover_border=(150, 205, 255),
        button_primary_active_bg=(32, 64, 120),
        button_off_bg=(30, 33, 42),
        button_off_border=(62, 68, 84),
        button_off_chosen_bg=(40, 52, 78),
        button_danger_bg=solo,
        button_danger_hover_bg=(238, 58, 52),
        button_danger_hover_border=(255, 175, 155),
        button_danger_active_bg=(150, 26, 26),
        button_sheen=0.14,
        button_shade=0.22,
        button_glow_alpha=0.32,
        surface_bg=(20, 18, 34),
        surface_edge=(112, 88, 210),
        surface_text=(205, 212, 228),
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
        bar_grid=(70, 95, 130),
        song_bound=song_bound,
        playhead=(90, 50, 130),
        playhead_flash=(220, 170, 255),
        song_marker=(220, 40, 40),
        song_marker_selected=(255, 170, 40),
        timeline_scroll_rail=song_bound,
        timeline_scroll_thumb=muted,
        scrollbar_track=(26, 29, 38),
        scrollbar_thumb=(88, 98, 126),
        scrollbar_thumb_hover=button_hover_border,
    )


ULTRAVIOLET: Palette = _ultraviolet()
# Built-in themes, in the order the Theme setting lists them.
BUILTIN_PALETTES: tuple[Palette, ...] = (ULTRAVIOLET,)

_palette: Palette = ULTRAVIOLET
_palette_generation: int = 0


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


def palette_generation() -> int:
    """Changes whenever the palette changes, so caches can rebuild."""
    return _palette_generation


BORDER_WIDTH: int = 2
# Progress bars: a thick surface_edge border and a gap before the accent fill.
PROGRESS_BAR_BORDER_WIDTH: int = 2 * BORDER_WIDTH
PROGRESS_BAR_FILL_GAP: int = 2
# Text above a progress bar draws this much larger than the shell font.
PROGRESS_LABEL_FONT_SCALE: float = 1.5
# Marker bar width of a selected, focused, or lit row at shell scale 1.0.
ROW_BAR_PX: float = 2.5

FADE_DURATION_SEC: float = 2.0
