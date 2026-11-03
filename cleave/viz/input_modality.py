"""Pointer vs keyboard focus for modals and the file picker."""

from __future__ import annotations

from enum import Enum

import pygame


class InputModality(Enum):
    POINTER = "pointer"
    KEYBOARD = "keyboard"


class PointerMotionTracker:
    """Detect real pointer movement from pygame MOUSEMOTION events."""

    def __init__(self) -> None:
        self._last_pos: tuple[int, int] | None = None

    def reset(self) -> None:
        self._last_pos = None

    def moved(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.MOUSEMOTION:
            return False
        pos = event.pos
        rel = event.rel
        if rel[0] != 0 or rel[1] != 0:
            self._last_pos = pos
            return True
        if self._last_pos is not None and pos != self._last_pos:
            self._last_pos = pos
            return True
        self._last_pos = pos
        return False
