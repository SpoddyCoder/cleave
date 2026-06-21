"""Hold-to-repeat controller for pygame tuning and navigation keys."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

INITIAL_DELAY_SEC = 0.25
SLOW_INTERVAL_SEC = 0.08
FAST_INTERVAL_SEC = 0.03
ACCEL_AFTER_SEC = 1.0

_REPEAT_KEYS = frozenset(
    {pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN}
)


def mod_ctrl(mod: int) -> bool:
    return bool(mod & (pygame.KMOD_CTRL | pygame.KMOD_LCTRL | pygame.KMOD_RCTRL))


def mod_shift(mod: int) -> bool:
    return bool(mod & (pygame.KMOD_SHIFT | pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT))


def delete_key_pressed(event: pygame.event.Event) -> bool:
    """True for forward-delete keys (keysym or scancode; not Backspace)."""
    if event.key == pygame.K_DELETE:
        return True
    scan_delete = getattr(pygame, "KSCAN_DELETE", None)
    scancode = getattr(event, "scancode", None)
    return scan_delete is not None and scancode == scan_delete


@dataclass
class _ActiveRepeat:
    key: int
    mod: int
    on_repeat: Callable[[int, int], None]
    accel: bool = True
    held_sec: float = 0.0
    since_last_repeat_sec: float = 0.0
    fired_once: bool = False


class KeyRepeatController:
    """Arms on KEYDOWN, disarms on KEYUP; tick() fires repeat callbacks while held."""

    def __init__(self) -> None:
        self._active: _ActiveRepeat | None = None

    def on_keydown(
        self,
        key: int,
        mod: int,
        *,
        on_repeat: Callable[[int, int], None],
        accel: bool = True,
    ) -> bool:
        if key not in _REPEAT_KEYS:
            return False
        self._active = _ActiveRepeat(
            key=key, mod=mod, on_repeat=on_repeat, accel=accel
        )
        return True

    def on_keyup(self, key: int) -> None:
        if self._active is not None and self._active.key == key:
            self._active = None

    @property
    def is_armed(self) -> bool:
        return self._active is not None

    def tick(self, dt_sec: float) -> None:
        active = self._active
        if active is None:
            return

        active.held_sec += dt_sec
        if active.held_sec < INITIAL_DELAY_SEC:
            return

        if not active.fired_once:
            active.on_repeat(active.key, active.mod)
            active.fired_once = True
            active.since_last_repeat_sec = 0.0
            return

        interval = (
            SLOW_INTERVAL_SEC
            if not active.accel
            else (
                FAST_INTERVAL_SEC
                if active.held_sec >= ACCEL_AFTER_SEC
                else SLOW_INTERVAL_SEC
            )
        )
        active.since_last_repeat_sec += dt_sec
        while active.since_last_repeat_sec >= interval:
            active.on_repeat(active.key, active.mod)
            active.since_last_repeat_sec -= interval
