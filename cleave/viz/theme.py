"""Shared colors and layout constants for Milkdrop live tuning UI panels.

Typography roles for the live tuning overlay:
  VALUE    — white text for values and state indicators (default), and any
             text on a selected, focused, or lit row
  LABEL    — periwinkle text for row labels and prefixes
  MUTED    — blue-grey text for headings, shortcuts, and unchosen options
  DISABLED — cool grey text when a row, icon, or value on the black panel is inactive
  OFF_CONTROL_TEXT — the label, value, or chosen option on a switched-off,
             refused, or dimmed control (on BUTTON_OFF_BG / BUTTON_OFF_CHOSEN_BG)
  OFF_CONTROL_MUTED — an unchosen option or combo caret on such a control
  LOCKED   — tinted text for locked sub-rows that cannot be edited
  LOCKED_MUTED — an unchosen option on a locked control

Accent colors for modes and icons (not label/value roles):
  HIGHLIGHT, ERROR_NOTIFICATION, NOTIFICATION_ON_FILL, MOVE_MODE, LOCK_ICON,
  PRESET_ICON, PRESET_FILE_ICON,
  TIMELINE_TRACK_COLORS, BAR_GRID, SONG_BOUND, PLAYHEAD, PLAYHEAD_FLASH, SONG_MARKER, SONG_MARKER_SELECTED

Buttons (fills, not text roles). Each tone has a rest fill, a lit hover fill
and border, and a pressed fill; button_paint.button_look() turns them into a
vertical gradient, border, and (primary and danger) an outer glow:
  BUTTON_BG, BUTTON_BORDER - every plain panel button, segment, and combo box at rest
  BUTTON_HOVER_BG, BUTTON_HOVER_BORDER, BUTTON_ACTIVE_BG - a plain button, unchosen
    segment, or combo under the pointer (electric violet), and held down
  BUTTON_PRIMARY_BG (+ _HOVER_BG, _HOVER_BORDER, _ACTIVE_BG) - the confirm button of
    a dialog, and a selected segment
  BUTTON_OFF_BG, BUTTON_OFF_BORDER - the OFF tone: a button, segment, or combo on a
    switched-off or locked page, or one that refuses a press, at rest. Darker and
    recessed, so OFF_CONTROL_TEXT stays readable on it; it lights like a plain
    button under the pointer
  BUTTON_OFF_CHOSEN_BG - the chosen segment of such a control, a dusky blue
  BUTTON_DANGER_BG (+ _HOVER_BG, _HOVER_BORDER, _ACTIVE_BG) - the confirm button of
    a destructive dialog
  BUTTON_SHEEN, BUTTON_SHADE - how far the top lightens and the bottom darkens
  BUTTON_GLOW_ALPHA - the outer glow around a lit primary or danger button
  The open combo list is a floating surface (below); its highlighted row is the
    LIT row look and its chosen tick is HIGHLIGHT
  NAV_ON_BG, SOLO_BG, NAV_LOCK_BG - lit navigator on, solo, and lock icons
    (NAV_LOCK_GLYPH is the dark lock icon on its amber fill)

Colour language. Violet is the pointer (button hover, icon hover, row hover, a
lit menu or list row). Blue is the selection and the keyboard (a selected
segment, the selected row, the focused row and panel). Yellow (HIGHLIGHT) is a
signal on top of those: a lit row's marker bar, a chosen tick, a caret, the live
preset, info lines, and an icon glyph under the pointer. It is never a fill.

Rows (row_paint.row_look turns them into a band, edge, and marker bar):
  HOVER, HOVER_BG_ALPHA - flat violet wash on a row under the pointer
  ROW_SELECT_TINT - the blue a selected or focused row fades from, left to right
  ROW_SELECTED_ALPHA, ROW_SELECTED_BAR - the current navigator page, or a chosen
    row whose list does not hold the keys
  ROW_FOCUSED_ALPHA, ROW_FOCUSED_BAR, ROW_FOCUS_EDGE - the row the keys act on
    (ROW_FOCUS_EDGE also rings a focused panel button)
  ROW_BAR_PX - marker bar width at shell scale 1.0
  The LIT look (menu and choice list rows) is the plain button hover gradient
  with a HIGHLIGHT bar. Text on a selected, focused, or lit row is VALUE.

Floating surfaces (menus, context menus, the open choice list, dialogs, the
file picker, info panels, tooltips):
  SURFACE_BG, SURFACE_EDGE - deep ink with a violet edge; SURFACE_TEXT is soft
    white for unlit choice list options
  floating_surface() in imgui_theme pushes them onto a window

Accent gradient:
  ACCENT_FROM, ACCENT_TO - blue into violet, left to right: progress bar fills
    and the inspector title's new-page swipe
  HEADING - lavender help column section titles

Shell rules (not text roles):
  PANEL_EDGE - idle navigator, inspector, and strip outline
  PANEL_FOCUS_EDGE - outline of the panel that holds the keys
  TRANSPORT_RULE — rule under the menu bar and transport, and ImGui separators
  NAVIGATOR_TREE_LINE — connector lines between navigator rows
  INSPECTOR_DIVIDER — thin rule under the inspector title and above its buttons
  ICON_HOVER_FG - glyph of an icon or text button under the pointer (HIGHLIGHT)
  ICON_HOVER_BG, ICON_HOVER_BG_ALPHA - violet wash behind it, complementary to the
    yellow glyph; ICON_HOVER_EDGE is its opaque 1px outline
  ICON_LIT_HOVER_LIFT - how far a lit icon's own fill brightens under the pointer

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


BACKGROUND: tuple[int, int, int] = (0, 0, 0)
BACKGROUND_ALPHA: int = int(1.0 * 255)
MODAL_SCRIM_ALPHA: int = int(0.55 * 255)
TRANSPORT_RULE: tuple[int, int, int] = (52, 58, 74)
PANEL_EDGE: tuple[int, int, int] = (52, 58, 74)
PANEL_FOCUS_EDGE: tuple[int, int, int] = (56, 108, 205)
NAVIGATOR_TREE_LINE: tuple[int, int, int] = (72, 82, 108)
INSPECTOR_DIVIDER: tuple[int, int, int] = (44, 50, 64)

LABEL: tuple[int, int, int] = (165, 198, 250)
VALUE: tuple[int, int, int] = (255, 255, 255)
DISABLED: tuple[int, int, int] = (124, 130, 148)
OFF_CONTROL_TEXT: tuple[int, int, int] = (170, 177, 196)
OFF_CONTROL_MUTED: tuple[int, int, int] = (124, 130, 148)
MUTED: tuple[int, int, int] = (140, 151, 176)
HEADING: tuple[int, int, int] = (196, 182, 255)
HIGHLIGHT: tuple[int, int, int] = (255, 235, 130)
ERROR_NOTIFICATION: tuple[int, int, int] = (255, 140, 140)
NOTIFICATION_ON_FILL: tuple[int, int, int] = (0, 0, 0)

PRESET_ICON: tuple[int, int, int] = (255, 195, 90)
PRESET_FILE_ICON: tuple[int, int, int] = (255, 250, 235)
MOVE_MODE: tuple[int, int, int] = (60, 120, 255)
LOCK_ICON: tuple[int, int, int] = (235, 90, 90)
LOCKED: tuple[int, int, int] = (235, 150, 150)
LOCKED_MUTED: tuple[int, int, int] = (170, 110, 110)
SOLO_BG: tuple[int, int, int] = (200, 40, 40)
OVERRIDE_BG: tuple[int, int, int] = (255, 200, 60)
NAV_ON_BG: tuple[int, int, int] = (40, 140, 75)
NAV_LOCK_BG: tuple[int, int, int] = (225, 140, 40)
NAV_LOCK_GLYPH: tuple[int, int, int] = (0, 0, 0)
CONFIG_DIRTY: tuple[int, int, int] = (255, 255, 0)
ARMED_BG: tuple[int, int, int] = SOLO_BG
BUTTON_BG: tuple[int, int, int] = (48, 54, 66)
BUTTON_BORDER: tuple[int, int, int] = (85, 95, 115)
BUTTON_HOVER_BG: tuple[int, int, int] = (84, 62, 168)
BUTTON_HOVER_BORDER: tuple[int, int, int] = (170, 140, 255)
BUTTON_ACTIVE_BG: tuple[int, int, int] = (52, 36, 112)
BUTTON_PRIMARY_BG: tuple[int, int, int] = (45, 85, 150)
BUTTON_PRIMARY_HOVER_BG: tuple[int, int, int] = (58, 120, 215)
BUTTON_PRIMARY_HOVER_BORDER: tuple[int, int, int] = (150, 205, 255)
BUTTON_PRIMARY_ACTIVE_BG: tuple[int, int, int] = (32, 64, 120)
BUTTON_OFF_BG: tuple[int, int, int] = (30, 33, 42)
BUTTON_OFF_BORDER: tuple[int, int, int] = (62, 68, 84)
BUTTON_OFF_CHOSEN_BG: tuple[int, int, int] = (40, 52, 78)
BUTTON_DANGER_BG: tuple[int, int, int] = SOLO_BG
BUTTON_DANGER_HOVER_BG: tuple[int, int, int] = (238, 58, 52)
BUTTON_DANGER_HOVER_BORDER: tuple[int, int, int] = (255, 175, 155)
BUTTON_DANGER_ACTIVE_BG: tuple[int, int, int] = (150, 26, 26)
BUTTON_SHEEN: float = 0.14
BUTTON_SHADE: float = 0.22
BUTTON_GLOW_ALPHA: float = 0.32
SURFACE_BG: tuple[int, int, int] = (20, 18, 34)
SURFACE_EDGE: tuple[int, int, int] = (112, 88, 210)
SURFACE_TEXT: tuple[int, int, int] = (205, 212, 228)
ACCENT_FROM: tuple[int, int, int] = (58, 120, 215)
ACCENT_TO: tuple[int, int, int] = (128, 84, 255)
OVERRIDE_GLYPH: tuple[int, int, int] = (0, 0, 0)
OVERRIDE_GLYPH_OFF: tuple[int, int, int] = DISABLED
HOVER: tuple[int, int, int] = (128, 84, 255)
HOVER_BG_ALPHA: int = 40
ROW_SELECT_TINT: tuple[int, int, int] = (58, 120, 215)
# Band alpha at the row's left end, then at its right end.
ROW_SELECTED_ALPHA: tuple[float, float] = (0.30, 0.06)
ROW_SELECTED_BAR: tuple[int, int, int] = (58, 120, 215)
ROW_FOCUSED_ALPHA: tuple[float, float] = (0.50, 0.14)
ROW_FOCUSED_BAR: tuple[int, int, int] = (124, 184, 255)
ROW_FOCUS_EDGE: tuple[int, int, int] = (46, 94, 172)
ROW_BAR_PX: float = 2.5
ICON_HOVER_FG: tuple[int, int, int] = HIGHLIGHT
ICON_HOVER_BG: tuple[int, int, int] = (128, 84, 255)
ICON_HOVER_BG_ALPHA: int = 120
ICON_HOVER_EDGE: tuple[int, int, int] = (122, 92, 220)
ICON_LIT_HOVER_LIFT: float = 0.25
REC_BG: tuple[int, int, int] = (220, 0, 0)
# On-section fill of each timeline track's level bar, one per layer (max 8).
TIMELINE_TRACK_COLORS: tuple[tuple[int, int, int], ...] = (
    (127, 209, 255),  # sky
    (183, 166, 255),  # lavender
    (255, 210, 127),  # amber
    (156, 240, 176),  # mint
    (246, 166, 200),  # pink
    (255, 163, 143),  # coral
    (212, 238, 138),  # lime
    (128, 232, 216),  # aqua
)
BAR_GRID: tuple[int, int, int] = (70, 95, 130)
# Song start and end lines below the ruler, through the timeline rows.
SONG_BOUND: tuple[int, int, int] = (58, 66, 84)
PLAYHEAD: tuple[int, int, int] = (90, 50, 130)
PLAYHEAD_FLASH: tuple[int, int, int] = (220, 170, 255)
SONG_MARKER: tuple[int, int, int] = (220, 40, 40)
SONG_MARKER_SELECTED: tuple[int, int, int] = (255, 170, 40)

BORDER_WIDTH: int = 2
# Progress bars: a thick SURFACE_EDGE border and a gap before the accent fill.
PROGRESS_BAR_BORDER_WIDTH: int = 2 * BORDER_WIDTH
PROGRESS_BAR_FILL_GAP: int = 2
# Text above a progress bar draws this much larger than the shell font.
PROGRESS_LABEL_FONT_SCALE: float = 1.5
# ImGui scrollbars: a slate thumb that lights violet under the pointer.
SCROLLBAR_TRACK: tuple[int, int, int] = (26, 29, 38)
SCROLLBAR_THUMB: tuple[int, int, int] = (88, 98, 126)
SCROLLBAR_THUMB_HOVER: tuple[int, int, int] = BUTTON_HOVER_BORDER
# Timeline strip scrollbar: a faint rail and a neutral pill, so it does not
# read as a layer row's level bar.
TIMELINE_SCROLL_RAIL: tuple[int, int, int] = SONG_BOUND
TIMELINE_SCROLL_THUMB: tuple[int, int, int] = MUTED

FADE_DURATION_SEC: float = 2.0
