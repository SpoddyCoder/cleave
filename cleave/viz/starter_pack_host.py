"""Offer starter Milkdrop packs on an already-open loading window.

Prompt and error copy use the info panel. Download progress goes through
:meth:`LoadingWindow.update` so QUIT still works mid-fetch.
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

from cleave.starter_packs import (
    StarterPackCancelled,
    StarterPackError,
    download_starter_packs,
)
from cleave.viz.loading import LoadingWindow
from cleave.viz.modal_overlay import InfoPanelViewState, draw_info
from cleave.viz.overlay_primitives import overlay_font
from cleave.viz.theme import BACKGROUND

_FONT_SIZE = 20
_TICK_FPS = 60
_ERROR_FOOTER = "Press any key to continue"

_PROMPT_STATE = InfoPanelViewState(
    title_lines=("No Milkdrop presets found",),
    body_lines=(
        "Download the starter preset and texture packs (~60 MB)?",
        "Presets are required for Cleave to display visualizations.",
    ),
    footer_line="Y - download    N or Esc - skip",
)


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


def _draw_info(window: LoadingWindow, state: InfoPanelViewState) -> None:
    font = overlay_font(_FONT_SIZE)
    window.overlay_surface.fill((0, 0, 0, 0))
    draw_info(window.overlay_surface, state, font=font)
    _present(window, window.overlay_surface)


def _show_error(window: LoadingWindow, message: str) -> bool:
    """Show *message* and wait for a key. False when the user closed the window."""
    clock = pygame.time.Clock()
    state = InfoPanelViewState(
        title_lines=("Could not download starter packs",),
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
        _draw_info(window, state)


def run_starter_pack_prompt(window: LoadingWindow) -> bool | None:
    """Ask whether to download starter packs.

    Returns True after a successful download, False when the user skipped or
    a download failed, and None when the window was closed.
    """
    clock = pygame.time.Clock()
    while not window.quit_requested:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                window.quit_requested = True
                return None
            if event.type != pygame.KEYDOWN:
                continue
            if event.key in (pygame.K_y, pygame.K_RETURN, pygame.K_KP_ENTER):
                return _run_download(window)
            if event.key in (pygame.K_n, pygame.K_ESCAPE):
                return False
        clock.tick(_TICK_FPS)
        _draw_info(window, _PROMPT_STATE)
    return None


def _run_download(window: LoadingWindow) -> bool | None:
    def on_progress(message: str, fraction: float | None) -> None:
        if not window.update(message, fraction):
            raise StarterPackCancelled()

    try:
        download_starter_packs(on_progress)
    except StarterPackCancelled:
        return None
    except StarterPackError as exc:
        if window.quit_requested:
            return None
        if not _show_error(window, str(exc)):
            return None
        return False
    if window.quit_requested:
        return None
    return True
