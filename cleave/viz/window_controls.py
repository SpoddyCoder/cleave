"""Editor window commands that the session loop carries out on the GL window."""

from __future__ import annotations

# Seconds without mouse motion before Play Full Screen hides the pointer.
PLAY_POINTER_IDLE_SEC = 1.5


class WindowControls:
    """Full Screen Editor and Play Full Screen requests and state.

    Commands only request a change. The live loop owns the window, consumes
    the request, and mirrors the window state back into ``fullscreen``.

    Full Screen Editor puts the whole editor window in desktop fullscreen.
    Play Full Screen shows only the visualiser across the display; it puts
    the window in desktop fullscreen too, and on leaving it restores the
    window only when it was the one that went fullscreen.
    """

    def __init__(self) -> None:
        self.fullscreen = False
        self.play_fullscreen = False
        # True when entering Play Full Screen took the window fullscreen.
        self.play_restores_window = False
        self._toggle_requested = False
        self._play_request: bool | None = None
        self._last_pointer_motion_sec: float | None = None

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

    def note_pointer_motion(self, now_sec: float) -> None:
        self._last_pointer_motion_sec = now_sec

    def play_pointer_visible(self, now_sec: float) -> bool:
        """While playing full screen, the pointer shows only just after it moves."""
        last = self._last_pointer_motion_sec
        return last is not None and now_sec - last < PLAY_POINTER_IDLE_SEC
