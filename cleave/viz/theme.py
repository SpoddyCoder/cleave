"""Shared colors and layout constants for Milkdrop live tuning UI panels.

Typography roles for the live tuning overlay:
  LABEL    — light blue text for row labels and prefixes
  VALUE    — white text for values and state indicators (default)
  DISABLED — dimmed text when a row or control is inactive
  LOCKED   — tinted text for locked sub-rows that cannot be edited

Accent colors for modes and icons (not label/value roles):
  HIGHLIGHT, MOVE_MODE, LOCK_ICON, PRESET_ICON, PRESET_FILE_ICON

See [.cursor/rules/live-tuning-ui.mdc](../.cursor/rules/live-tuning-ui.mdc) for how
rows apply these roles, including intentional exceptions.
"""

from __future__ import annotations

BACKGROUND: tuple[int, int, int] = (0, 0, 0)
BACKGROUND_ALPHA: int = int(0.8 * 255)
BORDER_COLOR: tuple[int, int, int] = (255, 255, 255)

LABEL: tuple[int, int, int] = (170, 210, 255)
VALUE: tuple[int, int, int] = (255, 255, 255)
DISABLED: tuple[int, int, int] = (140, 140, 140)
HIGHLIGHT: tuple[int, int, int] = (255, 165, 0)

PRESET_ICON: tuple[int, int, int] = (255, 195, 90)
PRESET_FILE_ICON: tuple[int, int, int] = (255, 250, 235)
MOVE_MODE: tuple[int, int, int] = (60, 120, 255)
LOCK_ICON: tuple[int, int, int] = (235, 90, 90)
LOCKED: tuple[int, int, int] = (235, 150, 150)
SOLO_BG: tuple[int, int, int] = (200, 40, 40)
OVERRIDE_BG: tuple[int, int, int] = (255, 200, 60)
ARMED_BG: tuple[int, int, int] = SOLO_BG
OVERRIDE_GLYPH: tuple[int, int, int] = (0, 0, 0)
OVERRIDE_GLYPH_OFF: tuple[int, int, int] = DISABLED
TIMELINE_FOCUS_BG: tuple[int, int, int] = (90, 160, 240)
REC_BG: tuple[int, int, int] = (220, 0, 0)

BORDER_WIDTH: int = 2
PANEL_CONTENT_MAX_WIDTH: int = 440

HOLD_IDLE_SEC: float = 10.0
FADE_DURATION_SEC: float = 2.0
