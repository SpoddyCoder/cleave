"""Shared colors and layout constants for Milkdrop live tuning UI panels."""

from __future__ import annotations

BACKGROUND: tuple[int, int, int] = (0, 0, 0)
BACKGROUND_ALPHA: int = int(0.8 * 255)
BORDER_COLOR: tuple[int, int, int] = (255, 255, 255)
TEXT: tuple[int, int, int] = (255, 255, 255)
TEXT_DIM: tuple[int, int, int] = (140, 140, 140)
HIGHLIGHT: tuple[int, int, int] = (255, 165, 0)
CONFIG_HEADER_TEXT: tuple[int, int, int] = (170, 210, 255)
PRESET_ICON: tuple[int, int, int] = (255, 195, 90)
PRESET_FILE_ICON: tuple[int, int, int] = (255, 250, 235)
MOVE_MODE: tuple[int, int, int] = (60, 120, 255)
LOCK_ICON: tuple[int, int, int] = (235, 90, 90)
LOCK_TEXT: tuple[int, int, int] = (235, 150, 150)

BORDER_WIDTH: int = 2
PANEL_CONTENT_MAX_WIDTH: int = 440

HOLD_IDLE_SEC: float = 10.0
FADE_DURATION_SEC: float = 2.0
