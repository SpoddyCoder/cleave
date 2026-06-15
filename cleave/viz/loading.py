"""Centered loading message during visualizer boot."""

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

from cleave.gl_compositor import GlCompositor
from cleave.viz.theme import BACKGROUND, VALUE

_FONT_SIZE = 28
_loading_font: pygame.font.Font | None = None


def _loading_font_get() -> pygame.font.Font:
    global _loading_font
    if _loading_font is None:
        if not pygame.font.get_init():
            pygame.font.init()
        _loading_font = pygame.font.SysFont("monospace", _FONT_SIZE)
    return _loading_font


def draw_loading_screen(
    compositor: GlCompositor,
    message: str,
    display_width: int,
    display_height: int,
) -> None:
    font = _loading_font_get()
    text_surface = font.render(message, True, VALUE)
    surface = pygame.Surface((display_width, display_height), pygame.SRCALPHA)
    x = (display_width - text_surface.get_width()) // 2
    y = (display_height - text_surface.get_height()) // 2
    surface.blit(text_surface, (x, y))

    texture_id = compositor.upload_overlay_texture(surface)

    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    glViewport(0, 0, display_width, display_height)
    r, g, b = BACKGROUND
    glClearColor(r / 255.0, g / 255.0, b / 255.0, 1.0)
    glClear(GL_COLOR_BUFFER_BIT)

    compositor.draw_overlay(texture_id, 0, 0, display_width, display_height)
    pygame.display.flip()
