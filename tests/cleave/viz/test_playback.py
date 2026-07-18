"""Tests for cleave.viz.playback."""

from __future__ import annotations

import pytest

from cleave.viz.playback import (
    PlaybackState,
    current_sec,
    format_mmss,
    seek,
    seek_to,
    toggle_pause,
)
from tests.support.viz import StubMixPlayer


class TrackingMixPlayer(StubMixPlayer):
    def __init__(self, position_sec: float = 0.0) -> None:
        super().__init__(position_sec)
        self.paused = False

    def pause(self, on: bool) -> None:
        self.paused = on


class LatencyOffsetMixPlayer(StubMixPlayer):
    """Stub where audible lags file by a fixed latency (seconds)."""

    def __init__(
        self,
        file_position_sec: float = 0.0,
        *,
        latency_sec: float = 0.0,
    ) -> None:
        super().__init__(file_position_sec)
        self._latency_sec = latency_sec

    def file_position_sec(self) -> float:
        return self._position_sec

    def audible_position_sec(self) -> float:
        return max(0.0, self._position_sec - self._latency_sec)


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
    assert player.audible_position_sec() == 15.0


def test_seek_relative_uses_file_position_not_audible() -> None:
    # Audible lags file by 0.1s; relative seek must advance file by dt,
    # not by dt minus one latency period.
    latency_sec = 0.1
    player = LatencyOffsetMixPlayer(file_position_sec=10.0, latency_sec=latency_sec)
    state = PlaybackState(player=player)
    assert player.audible_position_sec() == pytest.approx(9.9)
    seek(state, delta_sec=1.0, duration_sec=120.0)
    assert player.file_position_sec() == pytest.approx(11.0)
    assert player.audible_position_sec() == pytest.approx(10.9)


def test_seek_clamps_at_bounds() -> None:
    player = StubMixPlayer(position_sec=118.0)
    state = PlaybackState(player=player)
    seek(state, delta_sec=10.0, duration_sec=120.0)
    assert player.audible_position_sec() == 120.0

    player.seek(2.0)
    seek(state, delta_sec=-10.0, duration_sec=120.0)
    assert player.audible_position_sec() == 0.0


def test_seek_to_absolute() -> None:
    player = StubMixPlayer(position_sec=10.0)
    state = PlaybackState(player=player)
    seek_to(state, position_sec=42.5, duration_sec=120.0)
    assert player.audible_position_sec() == 42.5


def test_seek_to_clamps_at_bounds() -> None:
    player = StubMixPlayer(position_sec=10.0)
    state = PlaybackState(player=player)
    seek_to(state, position_sec=200.0, duration_sec=120.0)
    assert player.audible_position_sec() == 120.0
    seek_to(state, position_sec=-5.0, duration_sec=120.0)
    assert player.audible_position_sec() == 0.0


def test_toggle_pause_delegates_to_player() -> None:
    player = TrackingMixPlayer()
    state = PlaybackState(player=player)
    toggle_pause(state, 120.0)
    assert state.paused is True
    assert player.paused is True
    toggle_pause(state, 120.0)
    assert state.paused is False
    assert player.paused is False
