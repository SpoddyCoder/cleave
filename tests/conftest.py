"""Shared pytest fixtures for Cleave tests."""

from __future__ import annotations

import pygame
import pytest


@pytest.fixture(scope="session", autouse=True)
def _pygame_session() -> None:
    """Initialize pygame (including mixer) once for tests that toggle playback."""
    if not pygame.get_init():
        pygame.init()
    if not pygame.mixer.get_init():
        pygame.mixer.init()
