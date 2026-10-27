"""Idle hold and linear fade for the live editor shell."""

from __future__ import annotations

from cleave.config_schema.editor import DEFAULT_UI_FADE_SEC
from cleave.viz.theme import FADE_DURATION_SEC


class UiFade:
    """Holds the shell visible after input, then fades it out."""

    def __init__(self, hold_idle_sec: float | None = None) -> None:
        self._hold_idle_sec = (
            DEFAULT_UI_FADE_SEC if hold_idle_sec is None else max(0.0, hold_idle_sec)
        )
        self._fade_duration_sec = FADE_DURATION_SEC
        self._idle_sec = self._hold_idle_sec + self._fade_duration_sec + 1.0
        self._visibility = 0.0

    def set_hold_idle_sec(self, sec: float) -> None:
        if not isinstance(sec, (int, float)):
            return
        sec = max(0.0, sec)
        was_disabled = self._hold_idle_sec <= 0
        self._hold_idle_sec = sec
        if sec <= 0:
            if self._visibility > 0:
                self._visibility = 1.0
                self._idle_sec = 0.0
        elif was_disabled and self._visibility > 0:
            self._idle_sec = 0.0

    def notify_input(self) -> None:
        self._idle_sec = 0.0
        self._visibility = 1.0

    def hide_immediately(self) -> None:
        self._idle_sec = self._hold_idle_sec + self._fade_duration_sec + 1.0
        self._visibility = 0.0

    def is_visible(self) -> bool:
        return self._visibility > 0.01

    @property
    def visibility(self) -> float:
        return self._visibility

    def update(self, dt_sec: float) -> None:
        hold_idle_sec = self._hold_idle_sec
        if hold_idle_sec <= 0:
            return
        self._idle_sec += dt_sec
        if self._idle_sec <= hold_idle_sec:
            self._visibility = 1.0
        elif self._fade_duration_sec <= 0:
            self._visibility = 0.0
        elif self._idle_sec <= hold_idle_sec + self._fade_duration_sec:
            fade_t = (self._idle_sec - hold_idle_sec) / self._fade_duration_sec
            self._visibility = 1.0 - fade_t
        else:
            self._visibility = 0.0
