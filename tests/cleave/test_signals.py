"""Tests for cleave.signals."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from cleave.signals import Signals, load_signals, resolve_signals_path
from tests.support.signals import make_signals


def test_resolve_signals_path_file(tmp_path: Path) -> None:
    signals_file = tmp_path / "signals.json"
    signals_file.write_text("{}", encoding="utf-8")
    assert resolve_signals_path(signals_file) == signals_file.resolve()


def test_resolve_signals_path_directory(tmp_path: Path) -> None:
    project = tmp_path / "my-track"
    project.mkdir()
    signals_file = project / "signals.json"
    signals_file.write_text("{}", encoding="utf-8")
    assert resolve_signals_path(project) == signals_file.resolve()


def test_load_signals_minimal_fixture(
    minimal_signals_json_path: Path,
) -> None:
    raw = json.loads(minimal_signals_json_path.read_text(encoding="utf-8"))
    assert raw["version"] == 1

    signals = load_signals(minimal_signals_json_path)

    assert signals.path == minimal_signals_json_path.resolve()
    assert signals.sample_rate_hz == 100.0
    assert signals.duration_sec == pytest.approx(0.14)
    assert signals.source is None

    pitch = signals.array("vocals", "pitch_hz")
    assert math.isnan(pitch[2])
    assert pitch[0] == pytest.approx(220.0)


def test_sample_clamps_below_zero(minimal_signals: Signals) -> None:
    assert minimal_signals.sample("drums", "onset_strength", -1.0) == pytest.approx(
        0.0
    )


def test_sample_clamps_past_end(minimal_signals: Signals) -> None:
    at_end = minimal_signals.sample("drums", "onset_strength", 0.02)
    past_end = minimal_signals.sample("drums", "onset_strength", 99.0)
    assert past_end == pytest.approx(at_end)


def test_sample_interpolates(minimal_signals: Signals) -> None:
    # [0.0, 0.5, 1.0] at 100 Hz: t=0.005 is halfway between index 0 and 1
    value = minimal_signals.sample("drums", "onset_strength", 0.005)
    assert value == pytest.approx(0.25)


def test_normalized_percentile_scaling() -> None:
    signals = make_signals("drums", "onset_strength", [0.0, 50.0, 100.0])
    normed = signals.normalized("drums", "onset_strength", percentile=99.0)
    scale = float(np.percentile(signals.array("drums", "onset_strength"), 99.0))
    expected = signals.array("drums", "onset_strength") / scale
    np.testing.assert_allclose(normed, expected)


def test_normalized_empty_array() -> None:
    signals = make_signals("drums", "onset_strength", [])
    normed = signals.normalized("drums", "onset_strength")
    assert normed.size == 0


def test_normalized_uses_cache() -> None:
    signals = make_signals("drums", "onset_strength", [0.0, 1.0, 2.0])
    first = signals.normalized("drums", "onset_strength", percentile=99.0)
    second = signals.normalized("drums", "onset_strength", percentile=99.0)
    assert first is second
