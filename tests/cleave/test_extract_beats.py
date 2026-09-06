"""Tests for Beat This! beat and downbeat extraction."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from cleave.extract import extract_beats_downbeats
from cleave.paths import model_cache_dir


def _install_fake_beat_this(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Stub torch and File2Beats without importing the real packages."""
    hub = types.ModuleType("torch.hub")
    hub.set_dir = MagicMock()
    torch_mod = types.ModuleType("torch")
    torch_mod.hub = hub
    torch_mod.cuda = types.ModuleType("torch.cuda")
    torch_mod.cuda.is_available = lambda: False
    monkeypatch.setitem(sys.modules, "torch", torch_mod)
    monkeypatch.setitem(sys.modules, "torch.hub", hub)
    monkeypatch.setitem(sys.modules, "torch.cuda", torch_mod.cuda)

    inference = types.ModuleType("beat_this.inference")
    file2beats_cls = MagicMock()
    inference.File2Beats = file2beats_cls
    beat_this = types.ModuleType("beat_this")
    monkeypatch.setitem(sys.modules, "beat_this", beat_this)
    monkeypatch.setitem(sys.modules, "beat_this.inference", inference)
    return file2beats_cls


def test_extract_beats_downbeats_uses_file2beats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLEAVE_DATA", str(tmp_path))
    mock_file2beats_cls = _install_fake_beat_this(monkeypatch)
    path = tmp_path / "mix.wav"
    path.write_bytes(b"wav")
    instance = mock_file2beats_cls.return_value
    instance.return_value = ([0.5, 1.0, 1.5], [0.5, 1.5])
    mock_ensure = MagicMock()
    monkeypatch.setattr("cleave.model_weights.ensure_weight_files", mock_ensure)

    beats, downbeats = extract_beats_downbeats(path)

    import torch

    torch.hub.set_dir.assert_called_once_with(str(model_cache_dir()))
    mock_ensure.assert_called_once()
    assert mock_ensure.call_args.args[0].label == "Beat This final0"
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
