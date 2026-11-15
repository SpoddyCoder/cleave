"""Run a :class:`ModalHost` dialog on an already-open loading window.

Startup prompts and errors (before any editor session exists) use the same
dialogs as the editor: the top-layer scrim, ``ModalSurface`` buttons, mouse,
and keys. Keys go to the host; mouse events go to the window's ImGui host.
"""

from __future__ import annotations

import pygame

from cleave.viz.loading import LoadingWindow, present_frame
from cleave.viz.modal import ModalHost

_TICK_FPS = 60
_MOUSE_EVENTS = (
    pygame.MOUSEMOTION,
    pygame.MOUSEBUTTONDOWN,
    pygame.MOUSEBUTTONUP,
    pygame.MOUSEWHEEL,
)


def _pump_events(window: LoadingWindow, host: ModalHost) -> None:
    for event in pygame.event.get():
        window.note_event(event)
        if event.type == pygame.QUIT:
            window.quit_requested = True
            return
        if event.type in _MOUSE_EVENTS:
            if window.imgui is not None:
                window.imgui.process_mouse_event(event)
            if event.type == pygame.MOUSEMOTION:
                host.note_pointer_motion(event)
            continue
        if event.type == pygame.KEYDOWN:
            host.handle_keydown(event)
        elif event.type == pygame.KEYUP:
            host.handle_keyup(event)


def present_modal_frame(window: LoadingWindow, host: ModalHost, dt: float) -> None:
    """Pump events, draw one frame of the open dialog, and apply its pointer.

    Safe to call from a download progress callback: the window keeps painting
    and a button press runs its action between chunks. Does nothing to the
    dialog once the user closes the window.
    """
    from cleave.viz.modal_surface import (
        ImGuiTextMeasure,
        ModalSurface,
        apply_modal_pointer,
    )
    from cleave.viz.top_layer import TopLayer

    _pump_events(window, host)
    if window.quit_requested:
        return
    host.tick(dt)
    view = host.view_state()
    surfaces: list[ModalSurface] = []

    def draw() -> None:
        if view is None:
            return
        layer = TopLayer()
        surface = ModalSurface(view, ImGuiTextMeasure())
        surfaces.append(surface)
        layer.push(surface)
        layer.draw()

    present_frame(window, draw, scrim=view is None, dt=dt)
    if surfaces:
        apply_modal_pointer(host, surfaces[0].intent)


def run_modal(window: LoadingWindow, host: ModalHost) -> bool:
    """Draw frames until the dialog closes. False when the user closed the window."""
    clock = pygame.time.Clock()
    while host.active and not window.quit_requested:
        dt_sec = clock.tick(_TICK_FPS) / 1000.0
        present_modal_frame(window, host, dt_sec)
    return not window.quit_requested


def show_notice(window: LoadingWindow, title: str, message: str) -> bool:
    """Show *message* under *title* with one OK button.

    False when the user closed the window instead.
    """
    host = ModalHost()
    host.prompt_notice(title, body=message or "unknown error")
    return run_modal(window, host)
