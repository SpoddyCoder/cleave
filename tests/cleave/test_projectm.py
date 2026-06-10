"""Tests for cleave.projectm PCM feeding."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from cleave.projectm import PROJECTM_MONO, ProjectM


def _mock_lib(*, max_samples: int = 480) -> MagicMock:
    lib = MagicMock()
    lib.projectm_pcm_get_max_samples.return_value = max_samples
    return lib


def test_feed_pcm_chunks_above_max_samples() -> None:
    lib = _mock_lib(max_samples=480)
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()
    samples = np.ones(1470, dtype=np.float32)

    with patch("cleave.projectm._get_lib", return_value=lib):
        pm.feed_pcm(samples)

    assert lib.projectm_pcm_add_float.call_count == 4
    counts = [call.args[2].value for call in lib.projectm_pcm_add_float.call_args_list]
    assert counts == [480, 480, 480, 30]
    for call in lib.projectm_pcm_add_float.call_args_list:
        assert call.args[3].value == PROJECTM_MONO


def test_feed_pcm_skips_empty() -> None:
    lib = _mock_lib()
    pm = ProjectM.__new__(ProjectM)
    pm._handle = MagicMock()

    with patch("cleave.projectm._get_lib", return_value=lib):
        pm.feed_pcm(np.array([], dtype=np.float32))

    lib.projectm_pcm_add_float.assert_not_called()
