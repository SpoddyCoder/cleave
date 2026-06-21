"""Tests for cleave.projectm PCM feeding."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from cleave.projectm import PROJECTM_MONO, PROJECTM_STEREO, ProjectM


def _mock_lib(*, max_samples: int = 480) -> MagicMock:
    lib = MagicMock()
    lib.projectm_pcm_get_max_samples.return_value = max_samples
    return lib


def test_feed_pcm_chunks_above_max_samples() -> None:
    lib = _mock_lib(max_samples=480)
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    pm._beat_sensitivity = 1.0
    pm._pcm_channels = 1
    samples = np.ones(1470, dtype=np.float32)

    with patch("cleave.projectm._get_lib", return_value=lib):
        pm.feed_pcm(samples)

    assert lib.projectm_pcm_add_float.call_count == 4
    counts = [call.args[2].value for call in lib.projectm_pcm_add_float.call_args_list]
    assert counts == [480, 480, 480, 30]
    for call in lib.projectm_pcm_add_float.call_args_list:
        assert call.args[3].value == PROJECTM_MONO


def test_feed_pcm_stereo_chunks_on_even_boundaries() -> None:
    lib = _mock_lib(max_samples=480)
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    pm._beat_sensitivity = 1.0
    pm._pcm_channels = 1
    samples = np.ones(1470, dtype=np.float32)

    with patch("cleave.projectm._get_lib", return_value=lib):
        pm.feed_pcm(samples, channels=2)

    assert lib.projectm_pcm_add_float.call_count == 4
    counts = [call.args[2].value for call in lib.projectm_pcm_add_float.call_args_list]
    assert counts == [240, 240, 240, 15]
    for call in lib.projectm_pcm_add_float.call_args_list:
        assert call.args[3].value == PROJECTM_STEREO


def test_feed_pcm_skips_empty() -> None:
    lib = _mock_lib()
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    pm._beat_sensitivity = 1.0
    pm._pcm_channels = 1

    with patch("cleave.projectm._get_lib", return_value=lib):
        pm.feed_pcm(np.array([], dtype=np.float32))

    lib.projectm_pcm_add_float.assert_not_called()


def test_feed_pcm_scales_by_beat_sensitivity() -> None:
    lib = _mock_lib(max_samples=480)
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    pm._beat_sensitivity = 2.0
    pm._pcm_channels = 1
    samples = np.full(4, 0.5, dtype=np.float32)

    with patch("cleave.projectm._get_lib", return_value=lib):
        pm.feed_pcm(samples)

    sent = lib.projectm_pcm_add_float.call_args.args[1]
    expected = np.full(4, 1.0, dtype=np.float32)
    np.testing.assert_array_almost_equal(
        np.ctypeslib.as_array(sent, shape=(4,)),
        expected,
    )


def test_flush_pcm_uses_last_channel_layout() -> None:
    lib = _mock_lib(max_samples=480)
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    pm._beat_sensitivity = 1.0
    pm._pcm_channels = 2

    with patch("cleave.projectm._get_lib", return_value=lib):
        pm.flush_pcm()

    call = lib.projectm_pcm_add_float.call_args
    assert call.args[2].value == 240
    assert call.args[3].value == PROJECTM_STEREO


def test_set_beat_sensitivity_clamps_and_stores() -> None:
    lib = _mock_lib()
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    pm._beat_sensitivity = 1.0

    with patch("cleave.projectm._get_lib", return_value=lib):
        pm.set_beat_sensitivity(3.0)
        assert pm.get_beat_sensitivity() == 3.0
        lib.projectm_set_beat_sensitivity.assert_called_once()
        assert lib.projectm_set_beat_sensitivity.call_args.args[1].value == 3.0

        lib.projectm_set_beat_sensitivity.reset_mock()
        pm.set_beat_sensitivity(6.0)
        assert pm.get_beat_sensitivity() == 5.0
        assert lib.projectm_set_beat_sensitivity.call_args.args[1].value == 5.0
