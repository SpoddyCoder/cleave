"""Playback timing and seek helpers for pygame visualizers."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

SKIP_SEC = 30.0


@dataclass
class PlaybackState:
    position_sec: float = 0.0
    start_ms: int = 0
    paused_ms: int = 0
    pause_at: int = 0
    paused: bool = False
    reposition_on_resume: bool = False


def elapsed_ms(state: PlaybackState) -> int:
    now = pygame.time.get_ticks()
    if state.paused:
        return state.pause_at - state.start_ms - state.paused_ms
    return now - state.start_ms - state.paused_ms


def current_sec(state: PlaybackState, duration_sec: float) -> float:
    return min(state.position_sec + elapsed_ms(state) / 1000.0, duration_sec)


def format_mmss(sec: float) -> str:
    s = max(0, int(sec))
    return f"{s // 60:02d}:{s % 60:02d}"


def seek(state: PlaybackState, delta_sec: float, duration_sec: float) -> None:
    t = current_sec(state, duration_sec)
    state.position_sec = max(0.0, min(t + delta_sec, duration_sec))
    now = pygame.time.get_ticks()
    state.start_ms = now
    state.paused_ms = 0
    if state.paused:
        state.pause_at = now
        pygame.mixer.music.stop()
        state.reposition_on_resume = True
    else:
        pygame.mixer.music.stop()
        pygame.mixer.music.play(start=state.position_sec)
        state.reposition_on_resume = False


def toggle_pause(state: PlaybackState, duration_sec: float) -> None:
    if state.paused:
        state.start_ms = pygame.time.get_ticks()
        state.paused = False
        if state.reposition_on_resume:
            pygame.mixer.music.play(start=state.position_sec)
            state.reposition_on_resume = False
        else:
            pygame.mixer.music.unpause()
    else:
        state.position_sec = current_sec(state, duration_sec)
        state.pause_at = pygame.time.get_ticks()
        state.start_ms = state.pause_at
        state.paused_ms = 0
        state.paused = True
        pygame.mixer.music.pause()


def init_playback() -> PlaybackState:
    state = PlaybackState(start_ms=pygame.time.get_ticks())
    return state
