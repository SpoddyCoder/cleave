"""Click track shared by the latency calibrations.

Both calibrations pause the transport, clear the shell around the preview,
and play a metronome on its own while the song stays silent. This owns that
setup and puts everything back afterwards.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from cleave.viz.focus_nav import FocusCursor
from cleave.viz.playback import PlaybackState, toggle_pause
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.tap_sync import MetronomeClick, build_metronome_schedule


@dataclass(frozen=True)
class CalibrationUiSnapshot:
    help_visible: bool
    timeline_panel_open: bool
    focus_cursor: FocusCursor
    shell_region: ShellRegion


class CalibrationClicks:
    """Runs the click track for one calibration at a time."""

    def __init__(
        self,
        playback: PlaybackState,
        duration_sec: float,
        *,
        on_ui_begin: Callable[[], CalibrationUiSnapshot],
        on_ui_restore: Callable[[CalibrationUiSnapshot], None],
    ) -> None:
        self.playback = playback
        self.duration_sec = duration_sec
        self._on_ui_begin = on_ui_begin
        self._on_ui_restore = on_ui_restore
        self._ui_snapshot: CalibrationUiSnapshot | None = None

    def pause_transport(self) -> None:
        if not self.playback.paused:
            toggle_pause(self.playback, self.duration_sec)

    def begin(self, *, accents_only: bool = False) -> tuple[MetronomeClick, ...]:
        """Clear the shell and start the clicks from the paused playhead.

        The transport stays paused; only the audio device runs, playing
        clicks instead of the song. Returns the schedule, in song time.
        """
        self.pause_transport()
        self._ui_snapshot = self._on_ui_begin()
        start_sec = self.playback.player.file_position_sec()
        schedule = build_metronome_schedule(start_sec, self.duration_sec)
        if accents_only:
            schedule = tuple(click for click in schedule if click.accented)
        player = self.playback.player
        player.set_click_only(True)
        player.set_click_schedule(
            tuple((click.time_sec, click.accented) for click in schedule)
        )
        player.pause(False)
        return schedule

    def stop_clicks(self) -> None:
        """Silence the clicks and leave the transport paused."""
        player = self.playback.player
        player.set_click_schedule(None)
        player.set_click_only(False)
        self.playback.paused = True
        player.pause(True)

    def restore_ui(self) -> None:
        snapshot = self._ui_snapshot
        self._ui_snapshot = None
        if snapshot is not None:
            self._on_ui_restore(snapshot)

    def end(self) -> None:
        self.stop_clicks()
        self.restore_ui()
