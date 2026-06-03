"""Reusable controls help overlay for pygame visualizers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pygame

Anchor = Literal["topleft", "bottomleft"]

_TEXT = (200, 195, 190)
_TEXT_DIM = (115, 110, 105)
_PANEL = (18, 16, 22)


@dataclass(frozen=True)
class ControlRow:
    key_label: str
    name: str
    state: str | None = None


def _on_off(enabled: bool) -> str:
    return "ON" if enabled else "OFF"


def playback_rows(*, paused: bool) -> list[ControlRow]:
    return [
        ControlRow("Esc", "Quit"),
        ControlRow("Space", "Pause", "PAUSED" if paused else "PLAY"),
        ControlRow("Left", "Back 30s"),
        ControlRow("Right", "Fwd 30s"),
    ]


def layered_rows(
    *,
    show_drums: bool,
    show_bass: bool,
    show_vocals: bool,
    show_other: bool,
    paused: bool,
) -> list[ControlRow]:
    rows = list(playback_rows(paused=paused))
    rows.extend(
        [
            ControlRow("d", "Drums", _on_off(show_drums)),
            ControlRow("b", "Bass", _on_off(show_bass)),
            ControlRow("v", "Vocals", _on_off(show_vocals)),
            ControlRow("o", "Other", _on_off(show_other)),
        ]
    )
    return rows


class ControlsOverlay:
    """Multi-line key / label / state panel; holds visible, then fades out."""

    def __init__(
        self,
        rows: list[ControlRow],
        *,
        anchor: Anchor = "topleft",
        margin: tuple[int, int] = (10, 10),
        hold_idle_sec: float = 10.0,
        fade_duration_sec: float = 2.0,
        font_size: int = 14,
        panel_alpha: int = 160,
        padding: int = 8,
        line_gap: int = 3,
    ) -> None:
        self._rows = list(rows)
        self._anchor = anchor
        self._margin = margin
        self._hold_idle_sec = hold_idle_sec
        self._fade_duration_sec = fade_duration_sec
        self._font_size = font_size
        self._panel_alpha = panel_alpha
        self._padding = padding
        self._line_gap = line_gap
        self._idle_sec = 0.0
        self._visibility = 1.0
        self._font: pygame.font.Font | None = None
        self._panel_rect: tuple[int, int, int, int] | None = None

    def replace_rows(self, rows: list[ControlRow]) -> None:
        self._rows = list(rows)

    def set_row_state(self, name: str, state: str | None) -> None:
        for i, row in enumerate(self._rows):
            if row.name == name:
                self._rows[i] = ControlRow(row.key_label, row.name, state)
                return

    def notify_input(self) -> None:
        self._idle_sec = 0.0
        self._visibility = 1.0

    def update(self, dt_sec: float) -> None:
        self._idle_sec += dt_sec
        if self._idle_sec <= self._hold_idle_sec:
            self._visibility = 1.0
        elif self._fade_duration_sec <= 0:
            self._visibility = 0.0
        elif self._idle_sec <= self._hold_idle_sec + self._fade_duration_sec:
            fade_t = (self._idle_sec - self._hold_idle_sec) / self._fade_duration_sec
            self._visibility = 1.0 - fade_t
        else:
            self._visibility = 0.0

    def _font_get(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", self._font_size)
        return self._font

    def _format_line(self, row: ControlRow) -> str:
        key = f"[{row.key_label}]"
        if row.state is None:
            return f"{key:<8} {row.name}"
        return f"{key:<8} {row.name:<8} {row.state}"

    def _line_color(self, row: ControlRow) -> tuple[int, int, int]:
        if row.state == "OFF":
            return _TEXT_DIM
        return _TEXT

    @property
    def panel_rect(self) -> tuple[int, int, int, int] | None:
        """Top-left x, y, width, height of the last drawn panel, if any."""
        return self._panel_rect

    def draw(self, surface: pygame.Surface) -> None:
        self._panel_rect = None
        if self._visibility <= 0.01 or not self._rows:
            return

        font = self._font_get()
        lines = [self._format_line(row) for row in self._rows]
        rendered = [font.render(line, True, self._line_color(row)) for line, row in zip(lines, self._rows)]

        line_h = font.get_linesize()
        panel_w = max(surf.get_width() for surf in rendered) + self._padding * 2
        panel_h = (
            len(rendered) * line_h
            + (len(rendered) - 1) * self._line_gap
            + self._padding * 2
        )

        alpha = int(self._panel_alpha * self._visibility)
        if alpha < 2:
            return

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((*_PANEL, alpha))

        y = self._padding
        for surf in rendered:
            text_alpha = int(255 * self._visibility)
            if text_alpha < 2:
                continue
            surf.set_alpha(text_alpha)
            panel.blit(surf, (self._padding, y))
            y += line_h + self._line_gap

        mx, my = self._margin
        if self._anchor == "topleft":
            pos = (mx, my)
        else:
            pos = (mx, surface.get_height() - panel_h - my)

        surface.blit(panel, pos)
        self._panel_rect = (pos[0], pos[1], panel_w, panel_h)
