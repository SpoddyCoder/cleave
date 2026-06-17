"""Reusable yes/no confirm dialog for live tuning UI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from cleave.viz.theme import DISABLED, FOCUS_ROW_BG_ALPHA, HIGHLIGHT, VALUE


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

        msg_surf = font.render(message, True, VALUE)
        if text_alpha >= 2:
            msg_surf.set_alpha(text_alpha)
            surface.blit(msg_surf, (x, cur_y))
        cur_y += line_h + line_gap

        yes_color = HIGHLIGHT if focus_yes else DISABLED
        no_color = HIGHLIGHT if not focus_yes else DISABLED
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


@dataclass
class SaveChoiceRequest:
    on_overwrite: Callable[[], None]
    on_save_as_new: Callable[[], None]


class SaveChoiceDialog:
    """Modal OVERWRITE / SAVE AS NEW picker; consumes keys while active."""

    _OVERWRITE_LABEL = "OVERWRITE"
    _SAVE_AS_NEW_LABEL = "SAVE AS NEW"

    def __init__(self) -> None:
        self._request: SaveChoiceRequest | None = None
        self._focus_overwrite = True

    @property
    def active(self) -> bool:
        return self._request is not None

    @property
    def focus_overwrite(self) -> bool:
        return self._focus_overwrite

    def prompt(self, request: SaveChoiceRequest) -> None:
        self._request = request
        self._focus_overwrite = True

    def cancel(self) -> None:
        self._request = None
        self._focus_overwrite = True

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Return True when the event is consumed (including while blocking)."""
        if not self.active or event.type != pygame.KEYDOWN:
            return False

        if event.key == pygame.K_ESCAPE:
            self.cancel()
            return True

        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self._focus_overwrite = not self._focus_overwrite
            return True

        if event.key == pygame.K_RETURN:
            request = self._request
            focus_overwrite = self._focus_overwrite
            self._request = None
            self._focus_overwrite = True
            if request is not None:
                if focus_overwrite:
                    request.on_overwrite()
                else:
                    request.on_save_as_new()
            return True

        return True

    def measure_height(self, font: pygame.font.Font) -> int:
        return font.get_linesize()

    def measure_width(self, font: pygame.font.Font) -> int:
        overwrite_w = font.size(f"> {self._OVERWRITE_LABEL}")[0]
        save_as_new_w = font.size(f"  {self._SAVE_AS_NEW_LABEL}")[0]
        return overwrite_w + 16 + save_as_new_w

    def draw(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        *,
        x: int,
        y: int,
        focus_overwrite: bool,
        text_alpha: int,
    ) -> int:
        """Draw save choice at (x, y). Returns total height used."""
        line_h = font.get_linesize()
        overwrite_color = HIGHLIGHT if focus_overwrite else DISABLED
        save_as_new_color = HIGHLIGHT if not focus_overwrite else DISABLED
        overwrite_prefix = ">" if focus_overwrite else " "
        save_as_new_prefix = ">" if not focus_overwrite else " "

        overwrite_surf = font.render(
            f"{overwrite_prefix} {self._OVERWRITE_LABEL}", True, overwrite_color
        )
        save_as_new_surf = font.render(
            f"{save_as_new_prefix} {self._SAVE_AS_NEW_LABEL}",
            True,
            save_as_new_color,
        )
        gap = 16
        if text_alpha >= 2:
            overwrite_surf.set_alpha(text_alpha)
            save_as_new_surf.set_alpha(text_alpha)
            surface.blit(overwrite_surf, (x, y))
            surface.blit(
                save_as_new_surf, (x + overwrite_surf.get_width() + gap, y)
            )
        return line_h


@dataclass
class UnsavedQuitRequest:
    on_save: Callable[[], None]
    on_discard: Callable[[], None]
    on_cancel: Callable[[], None] | None = None


class UnsavedQuitDialog:
    """Modal SAVE / DON'T SAVE / CANCEL prompt for quitting with dirty config."""

    _MESSAGE = "Unsaved changes - save changes before exit?"
    _SAVE_LABEL = "SAVE"
    _DISCARD_LABEL = "DON'T SAVE"
    _CANCEL_LABEL = "CANCEL"
    _OPTION_COUNT = 3
    _MSG_PAD_X = 4
    _MSG_PAD_Y = 2
    _MSG_BG_ALPHA = max(FOCUS_ROW_BG_ALPHA, 90)

    def __init__(self) -> None:
        self._request: UnsavedQuitRequest | None = None
        self._focus_index = 0

    @property
    def active(self) -> bool:
        return self._request is not None

    @property
    def message(self) -> str:
        return self._MESSAGE

    @property
    def focus_index(self) -> int:
        return self._focus_index

    def prompt(self, request: UnsavedQuitRequest) -> None:
        self._request = request
        self._focus_index = 0

    def cancel(self) -> None:
        if self._request is not None and self._request.on_cancel is not None:
            self._request.on_cancel()
        self._request = None
        self._focus_index = 0

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Return True when the event is consumed (including while blocking)."""
        if not self.active or event.type != pygame.KEYDOWN:
            return False

        if event.key == pygame.K_ESCAPE:
            self.cancel()
            return True

        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            delta = -1 if event.key == pygame.K_LEFT else 1
            self._focus_index = (self._focus_index + delta) % self._OPTION_COUNT
            return True

        if event.key == pygame.K_RETURN:
            request = self._request
            focus_index = self._focus_index
            self._request = None
            self._focus_index = 0
            if request is not None:
                if focus_index == 0:
                    request.on_save()
                elif focus_index == 1:
                    request.on_discard()
                elif request.on_cancel is not None:
                    request.on_cancel()
            return True

        return True

    def measure_height(
        self,
        font: pygame.font.Font,
        *,
        line_gap: int,
    ) -> int:
        line_h = font.get_linesize()
        msg_h = line_h + self._MSG_PAD_Y * 2
        return msg_h + line_gap + line_h

    def measure_width(self, font: pygame.font.Font) -> int:
        msg_w = font.size(self._MESSAGE)[0] + self._MSG_PAD_X * 2
        option_widths = [
            font.size(f"> {label}")[0]
            for label in (self._SAVE_LABEL, self._DISCARD_LABEL, self._CANCEL_LABEL)
        ]
        options_w = sum(option_widths) + 16 * (self._OPTION_COUNT - 1)
        return max(msg_w, options_w)

    def draw(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        *,
        x: int,
        y: int,
        focus_index: int,
        text_alpha: int,
        line_gap: int,
    ) -> int:
        """Draw unsaved quit prompt at (x, y). Returns total height used."""
        line_h = font.get_linesize()
        cur_y = y

        msg_surf = font.render(self._MESSAGE, True, HIGHLIGHT)
        msg_w, msg_h = msg_surf.get_size()
        bg_w = msg_w + self._MSG_PAD_X * 2
        bg_h = msg_h + self._MSG_PAD_Y * 2
        if text_alpha >= 2:
            bg_alpha = int(self._MSG_BG_ALPHA * text_alpha / 255)
            if bg_alpha >= 2:
                bg_surf = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
                bg_surf.fill((*HIGHLIGHT, bg_alpha))
                surface.blit(bg_surf, (x, cur_y))
            msg_surf.set_alpha(text_alpha)
            surface.blit(
                msg_surf, (x + self._MSG_PAD_X, cur_y + self._MSG_PAD_Y)
            )
        cur_y += bg_h + line_gap

        labels = (self._SAVE_LABEL, self._DISCARD_LABEL, self._CANCEL_LABEL)
        gap = 16
        option_x = x
        for index, label in enumerate(labels):
            focused = index == focus_index
            color = HIGHLIGHT if focused else DISABLED
            prefix = ">" if focused else " "
            option_surf = font.render(f"{prefix} {label}", True, color)
            if text_alpha >= 2:
                option_surf.set_alpha(text_alpha)
                surface.blit(option_surf, (option_x, cur_y))
            option_x += option_surf.get_width() + gap

        return (cur_y - y) + line_h
