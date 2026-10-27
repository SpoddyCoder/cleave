"""Offer starter Milkdrop packs on an already-open loading window.

Prompt and error copy use the info panel. Download progress goes through
:meth:`LoadingWindow.update` so QUIT still works mid-fetch.
"""

from __future__ import annotations

import pygame

from cleave.starter_packs import (
    StarterPackCancelled,
    StarterPackError,
    download_starter_packs,
)
from cleave.viz.info_panel import InfoPanelViewState
from cleave.viz.loading import LoadingWindow, present_frame

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


def _present_info(window: LoadingWindow, state: InfoPanelViewState, dt: float) -> None:
    """Draw one info panel inside the loading frame. The scrim is already there."""
    from cleave.viz.top_layer import InfoPanelSurface

    def draw() -> None:
        InfoPanelSurface(state).draw()

    present_frame(window, draw, scrim=True, dt=dt)


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
        dt_sec = clock.tick(_TICK_FPS) / 1000.0
        _present_info(window, state, dt_sec)


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
        dt_sec = clock.tick(_TICK_FPS) / 1000.0
        _present_info(window, _PROMPT_STATE, dt_sec)
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
