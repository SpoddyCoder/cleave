"""Editor window commands that the session loop carries out on the GL window."""

from __future__ import annotations


class WindowControls:
    """Fullscreen request and state for the menu.

    Commands only request a toggle. The live loop owns the window, consumes
    the request, and mirrors the resulting state back into ``fullscreen``.
    """

    def __init__(self) -> None:
        self.fullscreen = False
        self._toggle_requested = False

    def request_fullscreen_toggle(self) -> None:
        self._toggle_requested = True

    def consume_fullscreen_toggle(self) -> bool:
        requested = self._toggle_requested
        self._toggle_requested = False
        return requested
