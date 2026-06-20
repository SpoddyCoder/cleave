"""Shared colors and layout constants for Milkdrop live tuning UI panels.

Typography roles for the live tuning overlay:
  LABEL    — light blue text for row labels and prefixes
  VALUE    — white text for values and state indicators (default)
  DISABLED — dimmed text when a row or control is inactive
  LOCKED   — tinted text for locked sub-rows that cannot be edited

Accent colors for modes and icons (not label/value roles):
  HIGHLIGHT, HIGHLIGHT_MUTED, MOVE_MODE, LOCK_ICON, PRESET_ICON, PRESET_FILE_ICON,
  TIMELINE_BAR_ON, PLAYHEAD

Layout scales:
  UI_SCALE (1.5) — main tuning panel, help, modals, and Material Icons spacing
  TIMELINE_UI_SCALE (1.0) — bottom timeline strip (base metrics unchanged)

Use tuning_ui_metrics() and timeline_ui_metrics() for scaled spacing; BORDER_WIDTH
is not scaled.

See [.cursor/rules/live-tuning-ui.mdc](../.cursor/rules/live-tuning-ui.mdc) for how
rows apply these roles, including intentional exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass

BASE_UI_FONT_SIZE: int = 14
UI_SCALE: float = 1.2
TIMELINE_UI_SCALE: float = 1.1


def scale_px(value: float, *, scale: float) -> int:
    return max(1, round(value * scale))


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
    modal_option_gap: int


@dataclass(frozen=True)
class TimelineUiMetrics:
    font_size: int
    padding: int
    row_gap: int
    margin: int
    panel_gap: int
    bar_vertical_inset: int
    playhead_width: int
    rec_badge_gap: int
    rec_badge_pad_x: int
    rec_badge_pad_y: int
    rec_time_gap: int


def tuning_ui_metrics(*, scale: float = UI_SCALE) -> TuningUiMetrics:
    return TuningUiMetrics(
        font_size=scale_px(BASE_UI_FONT_SIZE, scale=scale),
        padding=scale_px(8, scale=scale),
        line_gap=scale_px(3, scale=scale),
        margin=scale_px(10, scale=scale),
        panel_content_max_width=scale_px(440, scale=scale),
        scrollbar_width=scale_px(15, scale=scale),
        scrollbar_content_gap=scale_px(4, scale=scale),
        tree_indent=scale_px(16, scale=scale),
        row_icon_suffix_gap=scale_px(4, scale=scale),
        icon_label_gap=scale_px(4, scale=scale),
        icon_suffix_gap=scale_px(4, scale=scale),
        visibility_icon_pad_x=scale_px(2, scale=scale),
        modal_panel_pad_x=scale_px(12, scale=scale),
        modal_panel_pad_y=scale_px(10, scale=scale),
        modal_option_gap=scale_px(16, scale=scale),
    )


def timeline_ui_metrics(*, scale: float = TIMELINE_UI_SCALE) -> TimelineUiMetrics:
    return TimelineUiMetrics(
        font_size=scale_px(14, scale=scale),
        padding=scale_px(8, scale=scale),
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
DISABLED: tuple[int, int, int] = (140, 140, 140)
HIGHLIGHT: tuple[int, int, int] = (255, 235, 130)
HIGHLIGHT_MUTED: tuple[int, int, int] = (175, 160, 95)

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
PLAYHEAD: tuple[int, int, int] = (90, 50, 130)

BORDER_WIDTH: int = 2
SCROLLBAR_TRACK: tuple[int, int, int] = DISABLED
SCROLLBAR_THUMB: tuple[int, int, int] = TIMELINE_BAR_ON

HOLD_IDLE_SEC: float = 10.0
FADE_DURATION_SEC: float = 2.0
