"""Tests for Beat This! beat and downbeat extraction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from cleave.extract import extract_beats_downbeats


@patch("cleave.extract.File2Beats")
@patch("cleave.extract.torch.cuda.is_available", return_value=False)
def test_extract_beats_downbeats_uses_file2beats(
    _cuda: object,
    mock_file2beats_cls: MagicMock,
    tmp_path: Path,
) -> None:
    path = tmp_path / "mix.wav"
    path.write_bytes(b"wav")
    instance = mock_file2beats_cls.return_value
    instance.return_value = ([0.5, 1.0, 1.5], [0.5, 1.5])

    beats, downbeats = extract_beats_downbeats(path)

    mock_file2beats_cls.assert_called_once_with(
        checkpoint_path="final0",
        device="cpu",
        dbn=False,
    )
    instance.assert_called_once_with(str(path))
    assert beats.dtype == np.float64
    assert downbeats.dtype == np.float64
    np.testing.assert_array_equal(beats, np.array([0.5, 1.0, 1.5], dtype=np.float64))
    np.testing.assert_array_equal(downbeats, np.array([0.5, 1.5], dtype=np.float64))
