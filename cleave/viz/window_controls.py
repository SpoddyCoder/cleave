"""Editor window commands that the session loop carries out on the GL window."""

from __future__ import annotations

class WindowControls:
    """Full screen editor and Play full screen requests and state.

    Commands only request a change. The live loop owns the window, consumes
    the request, and mirrors the window state back into ``fullscreen``.

    Full screen editor puts the whole editor window in desktop fullscreen.
    Play full screen shows only the visualiser across the display; it puts
    the window in desktop fullscreen too, and on leaving it restores the
    window only when it was the one that went fullscreen.
    """

    def __init__(self) -> None:
        self.fullscreen = False
        self.play_fullscreen = False
        # True when entering Play full screen took the window fullscreen.
        self.play_restores_window = False
        self._toggle_requested = False
        self._play_request: bool | None = None

    def request_fullscreen_toggle(self) -> None:
        self._toggle_requested = True

    def consume_fullscreen_toggle(self) -> bool:
        requested = self._toggle_requested
        self._toggle_requested = False
        return requested

    def request_play_fullscreen(self, on: bool) -> None:
        self._play_request = bool(on)

    def request_play_fullscreen_toggle(self) -> None:
        self.request_play_fullscreen(not self.play_fullscreen)

    def consume_play_fullscreen(self) -> bool | None:
        """True to enter, False to leave, None when nothing changes."""
        request = self._play_request
        self._play_request = None
        if request is None or request == self.play_fullscreen:
            return None
        return request
