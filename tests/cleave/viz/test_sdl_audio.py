"""GIL-free SDL audio pause."""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from cleave.viz import sdl_audio


def test_pause_without_sdl_returns_false(monkeypatch) -> None:
    monkeypatch.setattr(sdl_audio, "_sdl_lib", None)
    monkeypatch.setattr(sdl_audio, "_sdl_library_candidates", lambda: [])

    class _Device:
        deviceid = 1

    assert sdl_audio.pause_device_without_gil(_Device()) is False


def test_stop_does_not_deadlock_while_callback_waits_for_gil(monkeypatch) -> None:
    """Close while the main thread holds the GIL and the callback wants it."""
    import pygame
    from pygame._sdl2 import INIT_AUDIO

    from cleave.viz.mix_player import FREQUENCY_HZ, MixPlayer

    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    try:
        pygame._sdl2.init_subsystem(INIT_AUDIO)
    except pygame.error:
        pytest.skip("SDL audio unavailable")

    player = MixPlayer(np.zeros(FREQUENCY_HZ * 2, dtype=np.float32), chunksize=256)
    try:
        player.start()
    except pygame.error:
        pytest.skip("no audio output device")
    assert sdl_audio._sdl_library() is not None

    done = threading.Event()

    def _stop() -> None:
        player.stop()
        done.set()

    stopper = threading.Thread(target=_stop, daemon=True)
    stopper.start()
    stopper.join(timeout=5.0)
    assert done.is_set(), "MixPlayer.stop() deadlocked"
    time.sleep(0.01)
