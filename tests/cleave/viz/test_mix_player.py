"""Tests for cleave.viz.mix_player."""

from __future__ import annotations

import numpy as np
import pytest

from cleave.viz.mix_player import (
    DEFAULT_CHUNKSIZE,
    FREQUENCY_HZ,
    MixPlayer,
    copy_stereo_pcm_chunk,
)


def test_copy_stereo_pcm_chunk_mid_buffer() -> None:
    pcm = np.arange(20, dtype=np.float32)
    out = np.zeros(8, dtype=np.float32)
    frames_written, new_index = copy_stereo_pcm_chunk(
        pcm, read_index=2, out=out, total_frames=10
    )
    assert frames_written == 4
    assert new_index == 6
    np.testing.assert_array_equal(out, pcm[4:12])


def test_copy_stereo_pcm_chunk_zero_pads_past_end() -> None:
    pcm = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
    out = np.zeros(6, dtype=np.float32)
    frames_written, new_index = copy_stereo_pcm_chunk(
        pcm, read_index=1, out=out, total_frames=2
    )
    assert frames_written == 1
    assert new_index == 2
    np.testing.assert_array_equal(out[:2], pcm[2:4])
    assert np.all(out[2:] == 0.0)


def test_copy_stereo_pcm_chunk_at_end_writes_silence() -> None:
    pcm = np.array([1.0, 2.0], dtype=np.float32)
    out = np.zeros(4, dtype=np.float32)
    frames_written, new_index = copy_stereo_pcm_chunk(
        pcm, read_index=1, out=out, total_frames=1
    )
    assert frames_written == 0
    assert new_index == 1
    assert np.all(out == 0.0)


def test_mix_player_current_sec_from_samples_played() -> None:
    pcm = np.zeros(FREQUENCY_HZ * 2 * 2, dtype=np.float32)
    player = MixPlayer(pcm, FREQUENCY_HZ)
    player.seek(1.5)
    assert player.current_sec() == pytest.approx(1.5)


def test_mix_player_seek_clamps_to_duration() -> None:
    pcm = np.zeros(FREQUENCY_HZ * 2, dtype=np.float32)
    player = MixPlayer(pcm, FREQUENCY_HZ)
    player.seek(99.0)
    assert player.current_sec() == pytest.approx(1.0)
    assert player.finished()


def test_mix_player_finished_false_before_end() -> None:
    pcm = np.zeros(FREQUENCY_HZ * 4, dtype=np.float32)
    player = MixPlayer(pcm, FREQUENCY_HZ)
    player.seek(0.5)
    assert not player.finished()


def test_mix_player_default_chunksize() -> None:
    pcm = np.zeros(8, dtype=np.float32)
    player = MixPlayer(pcm)
    assert player._chunksize == DEFAULT_CHUNKSIZE


def test_mix_player_start_stop_smoke() -> None:
    import pygame
    from pygame._sdl2 import INIT_AUDIO, get_audio_device_names

    pygame.init()
    try:
        pygame._sdl2.init_subsystem(INIT_AUDIO)
        if not get_audio_device_names(False):
            pytest.skip("no audio output device")
    except pygame.error:
        pytest.skip("SDL audio unavailable")

    pcm = np.zeros(FREQUENCY_HZ, dtype=np.float32)
    player = MixPlayer(pcm, FREQUENCY_HZ, chunksize=256)
    player.start()
    player.pause(True)
    player.pause(False)
    player.stop()
