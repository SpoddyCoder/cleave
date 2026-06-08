"""Playback timing and seek helpers for the visualizer."""

from __future__ import annotations

from dataclasses import dataclass

from cleave.viz.mix_player import MixPlayer


@dataclass
class PlaybackState:
    player: MixPlayer
    paused: bool = False


def current_sec(state: PlaybackState, duration_sec: float) -> float:
    return min(state.player.current_sec(), duration_sec)


def format_mmss(sec: float) -> str:
    s = max(0, int(sec))
    return f"{s // 60:02d}:{s % 60:02d}"


def seek(state: PlaybackState, delta_sec: float, duration_sec: float) -> None:
    t = current_sec(state, duration_sec)
    position_sec = max(0.0, min(t + delta_sec, duration_sec))
    state.player.seek(position_sec)


def toggle_pause(state: PlaybackState, _duration_sec: float) -> None:
    if state.paused:
        state.paused = False
        state.player.pause(False)
    else:
        state.paused = True
        state.player.pause(True)


def init_playback(player: MixPlayer) -> PlaybackState:
    return PlaybackState(player=player)
