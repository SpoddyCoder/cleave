"""Tests for cleave.viz.playback."""

from __future__ import annotations

from cleave.viz.playback import (
    PlaybackState,
    current_sec,
    format_mmss,
    seek,
    toggle_pause,
)
from tests.support.viz import StubMixPlayer


class TrackingMixPlayer(StubMixPlayer):
    def __init__(self, position_sec: float = 0.0) -> None:
        super().__init__(position_sec)
        self.paused = False

    def pause(self, on: bool) -> None:
        self.paused = on


def test_format_mmss() -> None:
    assert format_mmss(0.0) == "00:00"
    assert format_mmss(65.9) == "01:05"
    assert format_mmss(-1.0) == "00:00"


def test_current_sec_clamps_to_duration() -> None:
    player = StubMixPlayer(position_sec=100.0)
    state = PlaybackState(player=player)
    assert current_sec(state, duration_sec=60.0) == 60.0


def test_seek_relative() -> None:
    player = StubMixPlayer(position_sec=10.0)
    state = PlaybackState(player=player)
    seek(state, delta_sec=5.0, duration_sec=120.0)
    assert player.current_sec() == 15.0


def test_seek_clamps_at_bounds() -> None:
    player = StubMixPlayer(position_sec=118.0)
    state = PlaybackState(player=player)
    seek(state, delta_sec=10.0, duration_sec=120.0)
    assert player.current_sec() == 120.0

    player.seek(2.0)
    seek(state, delta_sec=-10.0, duration_sec=120.0)
    assert player.current_sec() == 0.0


def test_toggle_pause_delegates_to_player() -> None:
    player = TrackingMixPlayer()
    state = PlaybackState(player=player)
    toggle_pause(state, 120.0)
    assert state.paused is True
    assert player.paused is True
    toggle_pause(state, 120.0)
    assert state.paused is False
    assert player.paused is False
