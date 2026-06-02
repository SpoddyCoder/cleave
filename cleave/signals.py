"""Load and sample per-stem signals from signals.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_META_KEYS = frozenset({"version", "sample_rate_hz", "duration_sec", "source"})


def resolve_signals_path(path: Path) -> Path:
    path = path.resolve()
    return path / "signals.json" if path.is_dir() else path


def _list_to_array(values: list[float | None]) -> np.ndarray:
    out = np.empty(len(values), dtype=np.float64)
    for i, v in enumerate(values):
        out[i] = np.nan if v is None else float(v)
    return out


@dataclass
class Signals:
    sample_rate_hz: float
    duration_sec: float
    source: Path | None
    path: Path
    stems: dict[str, dict[str, np.ndarray]] = field(repr=False)
    _onset_max: float | None = field(default=None, init=False, repr=False)

    def array(self, stem: str, key: str) -> np.ndarray:
        return self.stems[stem][key]

    def sample(self, stem: str, key: str, t_sec: float) -> float:
        values = self.array(stem, key)
        if len(values) == 0:
            return 0.0

        t_max = (len(values) - 1) / self.sample_rate_hz
        t = min(max(t_sec, 0.0), t_max)
        pos = t * self.sample_rate_hz
        i = int(pos)
        if i >= len(values) - 1:
            return float(values[-1])
        frac = pos - i
        return float(values[i] * (1.0 - frac) + values[i + 1] * frac)

    @property
    def onset_normalized(self) -> np.ndarray:
        onset = self.array("drums", "onset_strength")
        if self._onset_max is None:
            self._onset_max = (
                float(np.percentile(onset, 99)) if len(onset) > 0 else 0.0
            )
        if self._onset_max <= 0.0:
            return np.zeros_like(onset)
        return onset / self._onset_max


def load_signals(path: Path) -> Signals:
    signals_path = resolve_signals_path(path)
    if not signals_path.is_file():
        raise FileNotFoundError(signals_path)

    with signals_path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    source_raw = data.get("source")
    stems: dict[str, dict[str, np.ndarray]] = {}
    for stem_name, signals in data.items():
        if stem_name in _META_KEYS or not isinstance(signals, dict):
            continue
        stems[stem_name] = {
            key: _list_to_array(values) for key, values in signals.items()
        }

    return Signals(
        sample_rate_hz=float(data["sample_rate_hz"]),
        duration_sec=float(data["duration_sec"]),
        source=Path(source_raw) if source_raw is not None else None,
        path=signals_path,
        stems=stems,
    )
