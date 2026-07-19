"""Shared colors and layout constants for Milkdrop live tuning UI panels.

Typography roles for the live tuning overlay:
  LABEL    — light blue text for row labels and prefixes
  VALUE    — white text for values and state indicators (default)
  ACTION   — dark mint text for action rows and staged action-parameter labels
  DISABLED — dimmed text when a row or control is inactive
  LOCKED   — tinted text for locked sub-rows that cannot be edited

Accent colors for modes and icons (not label/value roles):
  HIGHLIGHT, MOVE_MODE, LOCK_ICON, PRESET_ICON, PRESET_FILE_ICON,
  TIMELINE_BAR_ON, BAR_GRID, PLAYHEAD, PLAYHEAD_FLASH, SONG_MARKER, SONG_MARKER_SELECTED

Layout scales:
  UI_SCALE (1.2) — main tuning panel, help, modals, and Material Icons spacing
  TIMELINE_UI_SCALE (1.2) — bottom timeline strip typography and spacing

Timeline panel height is derived from a fixed per-row height (BASE_TIMELINE_ROW_HEIGHT)
times row count plus padding and gaps via timeline_panel_height_px().

Use tuning_ui_metrics(), timeline_ui_metrics(), and timeline_panel_height_px() for
scaled layout; BORDER_WIDTH is not scaled.

See [.cursor/rules/live-tuning-ui.mdc](../.cursor/rules/live-tuning-ui.mdc) for how
rows apply these roles, including intentional exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass

from cleave.config_schema import DEFAULT_UI_WIDTH

BASE_UI_FONT_SIZE: int = 14
UI_WIDTH_PX_FACTOR: int = 4
UI_SCALE: float = 1.2
TIMELINE_UI_SCALE: float = 1.2
BASE_TIMELINE_ROW_HEIGHT: int = 25


def scale_px(value: float, *, scale: float) -> int:
    return max(1, round(value * scale))


def panel_content_max_width_px(
    ui_width: int = DEFAULT_UI_WIDTH,
    *,
    scale: float = UI_SCALE,
) -> int:
    """Map persisted ui_width (80-200) to scaled panel content max width in pixels."""
    return scale_px(int(ui_width) * UI_WIDTH_PX_FACTOR, scale=scale)


@dataclass(frozen=True)
class TuningUiMetrics:
    font_size: int
    padding: int
    line_gap: int
    margin: int
    panel_content_max_width: int
    scrollbar_width: int
    scrollbar_content_gap: int
    tree_indent: int
    row_icon_suffix_gap: int
    icon_label_gap: int
    icon_suffix_gap: int
    visibility_icon_pad_x: int
    modal_panel_pad_x: int
    modal_panel_pad_y: int


@dataclass(frozen=True)
class TimelineUiMetrics:
    font_size: int
    padding: int
    row_height: int
    row_gap: int
    margin: int
    panel_gap: int
    bar_vertical_inset: int
    playhead_width: int
    rec_badge_gap: int
    rec_badge_pad_x: int
    rec_badge_pad_y: int
    rec_time_gap: int


def tuning_ui_metrics(
    *,
    scale: float = UI_SCALE,
    ui_width: int = DEFAULT_UI_WIDTH,
) -> TuningUiMetrics:
    return TuningUiMetrics(
        font_size=scale_px(BASE_UI_FONT_SIZE, scale=scale),
        padding=scale_px(8, scale=scale),
        line_gap=scale_px(3, scale=scale),
        margin=scale_px(10, scale=scale),
        panel_content_max_width=panel_content_max_width_px(ui_width, scale=scale),
        scrollbar_width=scale_px(15, scale=scale),
        scrollbar_content_gap=scale_px(4, scale=scale),
        tree_indent=scale_px(8, scale=scale),
        row_icon_suffix_gap=scale_px(4, scale=scale),
        icon_label_gap=scale_px(4, scale=scale),
        icon_suffix_gap=scale_px(4, scale=scale),
        visibility_icon_pad_x=scale_px(2, scale=scale),
        modal_panel_pad_x=scale_px(12, scale=scale),
        modal_panel_pad_y=scale_px(10, scale=scale),
    )


def timeline_ui_metrics(*, scale: float = TIMELINE_UI_SCALE) -> TimelineUiMetrics:
    return TimelineUiMetrics(
        font_size=scale_px(14, scale=scale),
        padding=scale_px(8, scale=scale),
        row_height=scale_px(BASE_TIMELINE_ROW_HEIGHT, scale=scale),
        row_gap=scale_px(2, scale=scale),
        margin=scale_px(10, scale=scale),
        panel_gap=scale_px(16, scale=scale),
        bar_vertical_inset=scale_px(3, scale=scale),
        playhead_width=scale_px(2, scale=scale),
        rec_badge_gap=scale_px(4, scale=scale),
        rec_badge_pad_x=scale_px(8, scale=scale),
        rec_badge_pad_y=scale_px(4, scale=scale),
        rec_time_gap=scale_px(2, scale=scale),
    )


def timeline_panel_height_px(
    row_count: int,
    *,
    scale: float = TIMELINE_UI_SCALE,
) -> int:
    """Scaled bottom timeline strip height in pixels."""
    if row_count <= 0:
        return 0
    m = timeline_ui_metrics(scale=scale)
    return m.padding * 2 + row_count * m.row_height + max(0, row_count - 1) * m.row_gap


_tuning_ui = tuning_ui_metrics()
PANEL_CONTENT_MAX_WIDTH: int = _tuning_ui.panel_content_max_width
SCROLLBAR_WIDTH: int = _tuning_ui.scrollbar_width
SCROLLBAR_CONTENT_GAP: int = _tuning_ui.scrollbar_content_gap

BACKGROUND: tuple[int, int, int] = (0, 0, 0)
BACKGROUND_ALPHA: int = int(1.0 * 255)
MODAL_SCRIM_ALPHA: int = int(0.55 * 255)
BORDER_COLOR: tuple[int, int, int] = (255, 255, 255)

LABEL: tuple[int, int, int] = (170, 210, 255)
VALUE: tuple[int, int, int] = (255, 255, 255)
ACTION: tuple[int, int, int] = (80, 190, 125)
DISABLED: tuple[int, int, int] = (140, 140, 140)
HIGHLIGHT: tuple[int, int, int] = (255, 235, 130)

PRESET_ICON: tuple[int, int, int] = (255, 195, 90)
PRESET_FILE_ICON: tuple[int, int, int] = (255, 250, 235)
MOVE_MODE: tuple[int, int, int] = (60, 120, 255)
LOCK_ICON: tuple[int, int, int] = (235, 90, 90)
LOCKED: tuple[int, int, int] = (235, 150, 150)
SOLO_BG: tuple[int, int, int] = (200, 40, 40)
OVERRIDE_BG: tuple[int, int, int] = (255, 200, 60)
CONFIG_DIRTY: tuple[int, int, int] = (255, 255, 0)
ARMED_BG: tuple[int, int, int] = SOLO_BG
OVERRIDE_GLYPH: tuple[int, int, int] = (0, 0, 0)
OVERRIDE_GLYPH_OFF: tuple[int, int, int] = DISABLED
FOCUS_ROW_BG_ALPHA: int = 130
REC_BG: tuple[int, int, int] = (220, 0, 0)
TIMELINE_BAR_ON: tuple[int, int, int] = (200, 225, 255)
BAR_GRID: tuple[int, int, int] = (70, 95, 130)
PLAYHEAD: tuple[int, int, int] = (90, 50, 130)
PLAYHEAD_FLASH: tuple[int, int, int] = (220, 170, 255)
SONG_MARKER: tuple[int, int, int] = (220, 40, 40)
SONG_MARKER_SELECTED: tuple[int, int, int] = (255, 170, 40)

BORDER_WIDTH: int = 2
SCROLLBAR_TRACK: tuple[int, int, int] = DISABLED
SCROLLBAR_THUMB: tuple[int, int, int] = TIMELINE_BAR_ON

FADE_DURATION_SEC: float = 2.0
