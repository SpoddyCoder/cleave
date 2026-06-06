"""Reusable yes/no confirm dialog for live tuning UI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from cleave.viz_theme import HIGHLIGHT, TEXT, TEXT_DIM


@dataclass
class ConfirmRequest:
    message: str
    on_confirm: Callable[[], None]
    on_cancel: Callable[[], None] | None = None


class ConfirmDialog:
    """Modal yes/no prompt; consumes keys while active."""

    def __init__(self) -> None:
        self._request: ConfirmRequest | None = None
        self._focus_yes = True

    @property
    def active(self) -> bool:
        return self._request is not None

    @property
    def message(self) -> str | None:
        if self._request is None:
            return None
        return self._request.message

    @property
    def focus_yes(self) -> bool:
        return self._focus_yes

    def prompt(self, request: ConfirmRequest) -> None:
        self._request = request
        self._focus_yes = True

    def cancel(self) -> None:
        if self._request is not None and self._request.on_cancel is not None:
            self._request.on_cancel()
        self._request = None
        self._focus_yes = True

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Return True when the event is consumed (including while blocking)."""
        if not self.active or event.type != pygame.KEYDOWN:
            return False

        if event.key == pygame.K_ESCAPE:
            self.cancel()
            return True

        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self._focus_yes = not self._focus_yes
            return True

        if event.key == pygame.K_y:
            self._focus_yes = True
            return True
        if event.key == pygame.K_n:
            self._focus_yes = False
            return True

        if event.key == pygame.K_RETURN:
            if self._focus_yes:
                request = self._request
                self._request = None
                self._focus_yes = True
                if request is not None:
                    request.on_confirm()
            else:
                self.cancel()
            return True

        return True

    def measure_height(
        self,
        font: pygame.font.Font,
        message: str,
        *,
        line_gap: int,
    ) -> int:
        line_h = font.get_linesize()
        return line_h + line_gap + line_h

    def measure_width(self, font: pygame.font.Font, message: str) -> int:
        msg_w = font.size(message)[0]
        yes_w = font.size("> Yes")[0]
        no_w = font.size("  No")[0]
        options_w = yes_w + 16 + no_w
        return max(msg_w, options_w)

    def draw(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        *,
        x: int,
        y: int,
        message: str,
        focus_yes: bool,
        text_alpha: int,
        line_gap: int,
    ) -> int:
        """Draw confirm prompt at (x, y). Returns total height used."""
        line_h = font.get_linesize()
        cur_y = y

        msg_surf = font.render(message, True, TEXT)
        if text_alpha >= 2:
            msg_surf.set_alpha(text_alpha)
            surface.blit(msg_surf, (x, cur_y))
        cur_y += line_h + line_gap

        yes_color = HIGHLIGHT if focus_yes else TEXT_DIM
        no_color = HIGHLIGHT if not focus_yes else TEXT_DIM
        yes_prefix = ">" if focus_yes else " "
        no_prefix = ">" if not focus_yes else " "

        yes_surf = font.render(f"{yes_prefix} Yes", True, yes_color)
        no_surf = font.render(f"{no_prefix} No", True, no_color)
        gap = 16
        if text_alpha >= 2:
            yes_surf.set_alpha(text_alpha)
            no_surf.set_alpha(text_alpha)
            surface.blit(yes_surf, (x, cur_y))
            surface.blit(no_surf, (x + yes_surf.get_width() + gap, cur_y))

        return (cur_y - y) + line_h
