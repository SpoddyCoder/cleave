"""Hold-to-repeat controller for pygame tuning and navigation keys."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pygame

INITIAL_DELAY_SEC = 0.25
SLOW_INTERVAL_SEC = 0.08
FAST_INTERVAL_SEC = 0.03
ACCEL_AFTER_SEC = 1.0

_REPEAT_KEYS = frozenset(
    {
        pygame.K_LEFT,
        pygame.K_RIGHT,
        pygame.K_PAGEUP,
        pygame.K_PAGEDOWN,
        pygame.K_UP,
        pygame.K_DOWN,
        pygame.K_COMMA,
        pygame.K_PERIOD,
        pygame.K_BACKSPACE,
    }
)


def mod_ctrl(mod: int) -> bool:
    return bool(mod & (pygame.KMOD_CTRL | pygame.KMOD_LCTRL | pygame.KMOD_RCTRL))


def mod_shift(mod: int) -> bool:
    return bool(mod & (pygame.KMOD_SHIFT | pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT))


def mod_alt(mod: int) -> bool:
    return bool(mod & (pygame.KMOD_ALT | pygame.KMOD_LALT | pygame.KMOD_RALT))


def delete_key_pressed(event: pygame.event.Event) -> bool:
    """True for forward-delete keys (keysym or scancode; not Backspace)."""
    if event.key == pygame.K_DELETE:
        return True
    scan_delete = getattr(pygame, "KSCAN_DELETE", None)
    scancode = getattr(event, "scancode", None)
    return scan_delete is not None and scancode == scan_delete


def add_current_preset_key_pressed(key: int, mod: int) -> bool:
    """True for the P key that adds the current preset in user-defined mode."""
    del mod
    return key == pygame.K_p


class RepeatClock:
    """Delay, then repeating fires. Reports how many times to fire each tick."""

    def __init__(self) -> None:
        self.held_sec = 0.0
        self.since_last_repeat_sec = 0.0
        self.fired_once = False

    def tick(self, dt_sec: float, *, accel: bool = True) -> int:
        self.held_sec += dt_sec
        if self.held_sec < INITIAL_DELAY_SEC:
            return 0

        if not self.fired_once:
            self.fired_once = True
            self.since_last_repeat_sec = 0.0
            return 1

        interval = (
            SLOW_INTERVAL_SEC
            if not accel
            else (
                FAST_INTERVAL_SEC
                if self.held_sec >= ACCEL_AFTER_SEC
                else SLOW_INTERVAL_SEC
            )
        )
        self.since_last_repeat_sec += dt_sec
        fires = 0
        while self.since_last_repeat_sec >= interval:
            fires += 1
            self.since_last_repeat_sec -= interval
        return fires


@dataclass
class _ActiveRepeat:
    key: int
    mod: int
    on_repeat: Callable[[int, int], None]
    accel: bool = True
    clock: RepeatClock = field(default_factory=RepeatClock)


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

    def disarm(self) -> None:
        self._active = None

    @property
    def is_armed(self) -> bool:
        return self._active is not None

    def tick(self, dt_sec: float) -> None:
        active = self._active
        if active is None:
            return
        for _ in range(active.clock.tick(dt_sec, accel=active.accel)):
            active.on_repeat(active.key, active.mod)
