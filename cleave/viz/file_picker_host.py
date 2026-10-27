"""Run the file picker on an already-open loading window.

Keys stay on this host. Mouse, buttons, and wheel go to the loading window's
ImGui host before each frame. The error panel draws on the info panel.
"""

from __future__ import annotations

import pygame

from cleave.open_target import OpenTarget
from cleave.viz.file_picker import FilePicker, PickerAction
from cleave.viz.info_panel import InfoPanelViewState
from cleave.viz.key_repeat import KeyRepeatController, mod_ctrl
from cleave.viz.loading import LoadingWindow, present_frame

_TICK_FPS = 60
_REPEAT_KEYS = (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT)
_MOUSE_EVENTS = (
    pygame.MOUSEMOTION,
    pygame.MOUSEBUTTONDOWN,
    pygame.MOUSEBUTTONUP,
    pygame.MOUSEWHEEL,
)
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
    if key == pygame.K_ESCAPE or (key == pygame.K_q and ctrl):
        return PickerAction.CANCEL
    return None


def _feed_mouse(window: LoadingWindow, event: pygame.event.Event) -> None:
    """Queue a mouse event when the window has an ImGui host."""
    host = window.imgui
    if host is None:
        return
    host.process_mouse_event(event)


def _present_info(window: LoadingWindow, state: InfoPanelViewState, dt: float) -> None:
    """Draw one info panel inside the loading frame. The scrim is already there."""
    from cleave.viz.top_layer import InfoPanelSurface

    def draw() -> None:
        InfoPanelSurface(state).draw()

    present_frame(window, draw, scrim=True, dt=dt)


def run_file_picker(window: LoadingWindow) -> OpenTarget | None:
    """Browse until the user picks something.

    Returns the accepted target, or None when the user cancelled or closed the
    window. Does not close *window*: the caller reuses it for progress, for an
    error message, and for the next attempt.
    """
    from cleave.viz.file_picker_surface import (
        FilePickerSurface,
        PickerPointerIntent,
        apply_picker_pointer,
    )

    picker = FilePicker()
    repeat = KeyRepeatController()
    clock = pygame.time.Clock()
    accepted: OpenTarget | None = None
    pending: list[PickerPointerIntent | None] = [None]

    def draw() -> None:
        surface = FilePickerSurface(picker.view_state())
        surface.draw()
        pending[0] = surface.intent

    while accepted is None and not picker.cancelled and not window.quit_requested:
        pending[0] = None
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                window.quit_requested = True
                break
            if event.type in _MOUSE_EVENTS:
                _feed_mouse(window, event)
                continue
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
        present_frame(window, draw, scrim=True, dt=dt_sec)
        accepted = apply_picker_pointer(picker, pending[0]) or accepted

    if window.quit_requested or picker.cancelled:
        return None
    return accepted


def _repeat_action(picker: FilePicker, key: int, mod: int) -> None:
    action = picker_action_for(key, mod)
    if action is not None and action is not PickerAction.ACCEPT:
        picker.handle(action)


def show_picker_error(window: LoadingWindow, message: str) -> bool:
    """Show *message* and wait for a key. False when the user closed the window."""
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
        dt_sec = clock.tick(_TICK_FPS) / 1000.0
        _present_info(window, state, dt_sec)
