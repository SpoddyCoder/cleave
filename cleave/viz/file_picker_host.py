"""Run the file picker on an already-open loading window.

Everything pygame lives here: the event pump, key mapping, key repeat, and
presenting through the loading compositor. :meth:`LoadingWindow.update` stays
progress-only.
"""

from __future__ import annotations

import pygame
from OpenGL.GL import (
    GL_COLOR_BUFFER_BIT,
    GL_FRAMEBUFFER,
    glBindFramebuffer,
    glClear,
    glClearColor,
    glViewport,
)

from cleave.open_target import OpenTarget
from cleave.viz import file_picker_overlay
from cleave.viz.file_picker import FilePicker, PickerAction
from cleave.viz.key_repeat import KeyRepeatController, mod_ctrl
from cleave.viz.loading import LoadingWindow
from cleave.viz.modal_overlay import InfoPanelViewState, draw_info
from cleave.viz.overlay_primitives import overlay_font
from cleave.viz.theme import BACKGROUND

PICKER_FONT_SIZE = 20
_TICK_FPS = 60
_REPEAT_KEYS = (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT)
_ERROR_FOOTER = "Press any key to choose another file"


def picker_action_for(key: int, mod: int) -> PickerAction | None:
    """Map a pygame key and modifier state onto a picker action."""
    ctrl = mod_ctrl(mod)
    if key == pygame.K_UP:
        return PickerAction.PAGE_UP if ctrl else PickerAction.MOVE_UP
    if key == pygame.K_DOWN:
        return PickerAction.PAGE_DOWN if ctrl else PickerAction.MOVE_DOWN
    if key == pygame.K_PAGEUP:
        return PickerAction.PAGE_UP
    if key == pygame.K_PAGEDOWN:
        return PickerAction.PAGE_DOWN
    if key in (pygame.K_LEFT, pygame.K_BACKSPACE):
        return PickerAction.PARENT
    if key == pygame.K_RIGHT:
        return PickerAction.ENTER
    if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return PickerAction.ACCEPT
    if key == pygame.K_TAB:
        return PickerAction.TOGGLE_FOCUS
    if key == pygame.K_ESCAPE:
        return PickerAction.CANCEL
    return None


def _present(window: LoadingWindow, surface: pygame.Surface) -> None:
    texture_id = window.compositor.upload_overlay_texture(surface)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    glViewport(0, 0, window.display_width, window.display_height)
    red, green, blue = BACKGROUND
    glClearColor(red / 255.0, green / 255.0, blue / 255.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT)
    window.compositor.draw_overlay(
        texture_id, 0, 0, window.display_width, window.display_height
    )
    pygame.display.flip()


def run_file_picker(window: LoadingWindow) -> OpenTarget | None:
    """Browse until the user picks something.

    Returns the accepted target, or None when the user cancelled or closed the
    window. Does not close *window*: the caller reuses it for progress, for an
    error message, and for the next attempt.
    """
    picker = FilePicker()
    repeat = KeyRepeatController()
    clock = pygame.time.Clock()
    font = overlay_font(PICKER_FONT_SIZE)
    accepted: OpenTarget | None = None

    while accepted is None and not picker.cancelled and not window.quit_requested:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                window.quit_requested = True
                break
            if event.type == pygame.KEYUP:
                repeat.on_keyup(event.key)
                continue
            if event.type != pygame.KEYDOWN:
                continue
            action = picker_action_for(event.key, event.mod)
            if action is None:
                continue
            accepted = picker.handle(action) or accepted
            if event.key in _REPEAT_KEYS:
                repeat.on_keydown(
                    event.key,
                    event.mod,
                    on_repeat=lambda key, mod: _repeat_action(picker, key, mod),
                )

        if accepted is not None or picker.cancelled or window.quit_requested:
            break

        dt_sec = clock.tick(_TICK_FPS) / 1000.0
        repeat.tick(dt_sec)
        window.overlay_surface.fill((0, 0, 0, 0))
        file_picker_overlay.draw(window.overlay_surface, picker.view_state(), font=font)
        _present(window, window.overlay_surface)

    if window.quit_requested or picker.cancelled:
        return None
    return accepted


def _repeat_action(picker: FilePicker, key: int, mod: int) -> None:
    action = picker_action_for(key, mod)
    if action is not None and action is not PickerAction.ACCEPT:
        picker.handle(action)


def show_picker_error(window: LoadingWindow, message: str) -> bool:
    """Show *message* and wait for a key. False when the user closed the window."""
    font = overlay_font(PICKER_FONT_SIZE)
    clock = pygame.time.Clock()
    state = InfoPanelViewState(
        title_lines=("Could not open that file",),
        body_lines=tuple(message.splitlines() or ("unknown error",)),
        footer_line=_ERROR_FOOTER,
    )

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                window.quit_requested = True
                return False
            if event.type == pygame.KEYDOWN:
                return True
        clock.tick(_TICK_FPS)
        window.overlay_surface.fill((0, 0, 0, 0))
        draw_info(window.overlay_surface, state, font=font)
        _present(window, window.overlay_surface)
