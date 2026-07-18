"""Tests for cleave.viz.mix_player."""

from __future__ import annotations

import numpy as np
import pytest

from cleave.viz.mix_player import (
    DEFAULT_CHUNKSIZE,
    FREQUENCY_HZ,
    MixPlayer,
    copy_mono_pcm_chunk_as_stereo,
    copy_stereo_pcm_chunk,
    estimate_output_latency_frames,
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


def test_copy_mono_pcm_chunk_as_stereo_duplicates_channels() -> None:
    pcm_mono = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
    out = np.zeros(6, dtype=np.float32)
    frames_written, new_index = copy_mono_pcm_chunk_as_stereo(
        pcm_mono, read_index=1, out=out, total_frames=4
    )
    assert frames_written == 3
    assert new_index == 4
    np.testing.assert_array_equal(out[:6], [2.0, 2.0, 3.0, 3.0, 4.0, 4.0])


def test_copy_mono_pcm_chunk_as_stereo_zero_pads_past_end() -> None:
    pcm_mono = np.array([1.0, 2.0], dtype=np.float32)
    out = np.zeros(6, dtype=np.float32)
    frames_written, new_index = copy_mono_pcm_chunk_as_stereo(
        pcm_mono, read_index=1, out=out, total_frames=2
    )
    assert frames_written == 1
    assert new_index == 2
    np.testing.assert_array_equal(out[:2], [2.0, 2.0])
    assert np.all(out[2:] == 0.0)


def test_mix_player_solo_source_routes_mono_pcm() -> None:
    mix = np.array([9.0, 9.0, 9.0, 9.0], dtype=np.float32)
    drums = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
    player = MixPlayer(mix, FREQUENCY_HZ)
    player.set_stem_pcm({"drums": (drums, 1)})
    player.set_solo_source("drums")
    player.seek(0.0)

    out = np.zeros(4, dtype=np.float32)
    with player._lock:
        read_index = player._read_index
        solo_source = player._solo_source
        stem_pcm = player._stem_pcm.get(solo_source) if solo_source else None
    assert stem_pcm is not None
    frames_written, _ = copy_mono_pcm_chunk_as_stereo(
        stem_pcm, read_index, out, total_frames=len(drums)
    )
    assert frames_written == 2
    np.testing.assert_array_equal(out, [1.0, 1.0, 2.0, 2.0])


def test_mix_player_solo_source_routes_stereo_pcm() -> None:
    mix = np.array([9.0, 9.0, 9.0, 9.0], dtype=np.float32)
    drums = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32)
    player = MixPlayer(mix, FREQUENCY_HZ)
    player.set_stem_pcm({"drums": (drums, 2)})
    player.set_solo_source("drums")
    player.seek(0.0)

    out = np.zeros(4, dtype=np.float32)
    with player._lock:
        read_index = player._read_index
        solo_source = player._solo_source
        stem_pcm = player._stem_pcm.get(solo_source) if solo_source else None
        stem_channels = player._stem_channels.get(solo_source, 1) if solo_source else 1
    assert stem_pcm is not None
    assert stem_channels == 2
    frames_written, _ = copy_stereo_pcm_chunk(
        stem_pcm, read_index, out, total_frames=len(drums) // 2
    )
    assert frames_written == 2
    np.testing.assert_array_equal(out, drums)


def test_copy_stereo_pcm_chunk_at_end_writes_silence() -> None:
    pcm = np.array([1.0, 2.0], dtype=np.float32)
    out = np.zeros(4, dtype=np.float32)
    frames_written, new_index = copy_stereo_pcm_chunk(
        pcm, read_index=1, out=out, total_frames=1
    )
    assert frames_written == 0
    assert new_index == 1
    assert np.all(out == 0.0)


def test_estimate_output_latency_frames_prefers_obtained() -> None:
    assert estimate_output_latency_frames(512, 4096) == 512
    assert estimate_output_latency_frames(256, 256) == 256


def test_estimate_output_latency_frames_falls_back_to_requested() -> None:
    assert estimate_output_latency_frames(None, 4096) == 4096
    assert estimate_output_latency_frames(0, 256) == 256
    assert estimate_output_latency_frames(-1, 128) == 128


def test_estimate_output_latency_frames_clamps_negative_requested() -> None:
    assert estimate_output_latency_frames(None, -10) == 0


def test_mix_player_seek_file_and_audible_match_at_latency_zero() -> None:
    pcm = np.zeros(FREQUENCY_HZ * 2 * 2, dtype=np.float32)
    player = MixPlayer(pcm, FREQUENCY_HZ)
    player.pause(True)
    player.seek(1.5)
    assert player.file_position_sec() == pytest.approx(1.5)
    assert player.audible_position_sec() == pytest.approx(1.5)


def test_mix_player_file_vs_audible_offset_with_latency() -> None:
    latency_frames = 256
    pcm = np.zeros(FREQUENCY_HZ * 2 * 2, dtype=np.float32)
    player = MixPlayer(pcm, FREQUENCY_HZ)
    with player._lock:
        player._clock.set_latency_frames(latency_frames)
    player.pause(True)
    player.seek(1.0)
    assert player.file_position_sec() == pytest.approx(1.0)
    assert player.audible_position_sec() == pytest.approx(
        1.0 - latency_frames / FREQUENCY_HZ
    )


def test_mix_player_seek_clamps_to_duration() -> None:
    pcm = np.zeros(FREQUENCY_HZ * 2, dtype=np.float32)
    player = MixPlayer(pcm, FREQUENCY_HZ)
    player.pause(True)
    player.seek(99.0)
    assert player.file_position_sec() == pytest.approx(1.0)
    assert player.audible_position_sec() == pytest.approx(1.0)
    assert player.finished()


def test_mix_player_finished_false_before_end() -> None:
    pcm = np.zeros(FREQUENCY_HZ * 4, dtype=np.float32)
    player = MixPlayer(pcm, FREQUENCY_HZ)
    player.pause(True)
    player.seek(0.5)
    assert not player.finished()


def test_mix_player_pause_freezes_audible_across_wall_time_gap() -> None:
    pcm = np.zeros(FREQUENCY_HZ * 4, dtype=np.float32)
    player = MixPlayer(pcm, FREQUENCY_HZ)
    player.pause(True)
    player.seek(0.5)
    frozen = player.audible_position_sec()
    assert frozen == pytest.approx(0.5)
    # Wall time advances while paused; audible must stay put.
    player._clock.anchor_wall_time -= 5.0
    assert player.audible_position_sec() == pytest.approx(frozen)


def test_mix_player_default_chunksize() -> None:
    pcm = np.zeros(8, dtype=np.float32)
    player = MixPlayer(pcm)
    assert player._chunksize == DEFAULT_CHUNKSIZE


def _require_sdl_audio() -> None:
    import pygame
    from pygame._sdl2 import INIT_AUDIO, get_audio_device_names

    pygame.init()
    try:
        pygame._sdl2.init_subsystem(INIT_AUDIO)
        if not get_audio_device_names(False):
            pytest.skip("no audio output device")
    except pygame.error:
        pytest.skip("SDL audio unavailable")


def test_mix_player_start_stop_smoke() -> None:
    _require_sdl_audio()
    pcm = np.zeros(FREQUENCY_HZ, dtype=np.float32)
    player = MixPlayer(pcm, FREQUENCY_HZ, chunksize=256)
    player.start()
    player.pause(True)
    player.pause(False)
    player.stop()


def test_mix_player_start_sets_latency_from_chunksize() -> None:
    _require_sdl_audio()
    pcm = np.zeros(FREQUENCY_HZ, dtype=np.float32)
    player = MixPlayer(pcm, FREQUENCY_HZ, chunksize=256)
    player.start()
    try:
        assert player._clock.latency_frames == 256
    finally:
        player.stop()


def test_mix_player_click_only_zeros_mix_pcm() -> None:
    mix = np.full(FREQUENCY_HZ * 2, 0.75, dtype=np.float32)
    player = MixPlayer(mix, FREQUENCY_HZ)
    player.set_click_only(True)
    out = np.zeros(DEFAULT_CHUNKSIZE * 2, dtype=np.float32)
    player._fill_output_buffer(out)
    assert np.all(out == 0.0)


def test_mix_player_click_only_mixes_loud_accent_click() -> None:
    mix = np.full(FREQUENCY_HZ * 2, 0.75, dtype=np.float32)
    player = MixPlayer(mix, FREQUENCY_HZ)
    player.set_click_only(True)
    player.set_click_schedule(((0.0, True),))
    out = np.zeros(DEFAULT_CHUNKSIZE * 2, dtype=np.float32)
    player._fill_output_buffer(out)
    assert np.max(np.abs(out)) > 0.5


def test_mix_player_click_only_quiet_click_is_softer_than_accent() -> None:
    mix = np.full(FREQUENCY_HZ * 2, 0.75, dtype=np.float32)
    accent_player = MixPlayer(mix, FREQUENCY_HZ)
    quiet_player = MixPlayer(mix, FREQUENCY_HZ)
    accent_player.set_click_only(True)
    quiet_player.set_click_only(True)
    accent_player.set_click_schedule(((0.0, True),))
    quiet_player.set_click_schedule(((0.0, False),))
    accent_out = np.zeros(DEFAULT_CHUNKSIZE * 2, dtype=np.float32)
    quiet_out = np.zeros(DEFAULT_CHUNKSIZE * 2, dtype=np.float32)
    accent_player._fill_output_buffer(accent_out)
    quiet_player._fill_output_buffer(quiet_out)
    assert np.max(np.abs(accent_out)) > np.max(np.abs(quiet_out))


def test_mix_player_click_only_ignores_solo_stem() -> None:
    mix = np.zeros(FREQUENCY_HZ * 2, dtype=np.float32)
    drums = np.full(FREQUENCY_HZ, 0.9, dtype=np.float32)
    player = MixPlayer(mix, FREQUENCY_HZ)
    player.set_stem_pcm({"drums": (drums, 1)})
    player.set_solo_source("drums")
    player.set_click_only(True)
    out = np.zeros(DEFAULT_CHUNKSIZE * 2, dtype=np.float32)
    player._fill_output_buffer(out)
    assert player._read_index > 0
    assert np.all(out == 0.0)


def test_mix_player_click_only_advances_transport_without_audible_mix() -> None:
    mix = np.full(FREQUENCY_HZ * 4, 0.8, dtype=np.float32)
    player = MixPlayer(mix, FREQUENCY_HZ, chunksize=256)
    player.set_click_only(True)
    player.pause(True)
    player.seek(0.0)
    out = np.zeros(512, dtype=np.float32)
    player._fill_output_buffer(out)
    assert player._read_index == 256
    assert player.file_position_sec() == pytest.approx(256 / FREQUENCY_HZ)
