"""Playback timing and seek helpers for the visualizer."""

from __future__ import annotations

from dataclasses import dataclass

from cleave.viz.mix_player import MixPlayer


@dataclass
class PlaybackState:
    player: MixPlayer
    paused: bool = False


def current_sec(state: PlaybackState, duration_sec: float) -> float:
    return min(state.player.audible_position_sec(), duration_sec)


def format_mmss(sec: float) -> str:
    s = max(0, int(sec))
    return f"{s // 60:02d}:{s % 60:02d}"


def seek_to(state: PlaybackState, position_sec: float, duration_sec: float) -> None:
    clamped = max(0.0, min(float(position_sec), duration_sec))
    state.player.seek(clamped)


def seek(state: PlaybackState, delta_sec: float, duration_sec: float) -> None:
    t = current_sec(state, duration_sec)
    seek_to(state, t + delta_sec, duration_sec)


def toggle_pause(state: PlaybackState, _duration_sec: float) -> None:
    if state.paused:
        state.paused = False
        state.player.pause(False)
    else:
        state.paused = True
        state.player.pause(True)


def init_playback(player: MixPlayer) -> PlaybackState:
    return PlaybackState(player=player)
