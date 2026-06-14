"""Mock GlCompositor helpers for unit tests (no OpenGL)."""

from __future__ import annotations

from unittest.mock import MagicMock


def recording_compositor() -> MagicMock:
    """MagicMock compositor with separate trackable overlay draw methods."""
    compositor = MagicMock()
    compositor.draw_content_overlay = MagicMock(name="draw_content_overlay")
    compositor.draw_overlay = MagicMock(name="draw_overlay")
    return compositor
