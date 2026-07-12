"""Load and sample per-stem signals from signals.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_META_KEYS = frozenset(
    {"version", "sample_rate_hz", "duration_sec", "beat_times", "downbeat_times"}
)
SIGNALS_VERSION = 3
_EXPECTED_STEMS = frozenset({"drums", "bass", "vocals", "other", "full_mix"})
_FULL_MIX_KEYS = frozenset({"onset_strength", "rms"})


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
    path: Path
    stems: dict[str, dict[str, np.ndarray]] = field(repr=False)
    beat_times: tuple[float, ...] = ()
    downbeat_times: tuple[float, ...] = ()
    _normalized_cache: dict[tuple[str, str, float], np.ndarray] = field(
        default_factory=dict, init=False, repr=False
    )

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

    def normalized(
        self, stem: str, key: str, percentile: float = 99.0
    ) -> np.ndarray:
        cache_key = (stem, key, percentile)
        cached = self._normalized_cache.get(cache_key)
        if cached is not None:
            return cached

        values = self.array(stem, key)
        if len(values) == 0 or percentile <= 0:
            result = np.zeros_like(values)
        else:
            scale = float(np.percentile(values, percentile))
            result = np.zeros_like(values) if scale <= 0.0 else values / scale

        self._normalized_cache[cache_key] = result
        return result

    @property
    def onset_normalized(self) -> np.ndarray:
        return self.normalized("drums", "onset_strength")


def _validate_signals_data(data: dict, stems: dict[str, dict[str, np.ndarray]]) -> None:
    version = data.get("version")
    if version != SIGNALS_VERSION:
        raise ValueError(
            f"unsupported signals.json version {version!r}; "
            f"re-run: python -m cleave analyse <project>"
        )

    missing_stems = _EXPECTED_STEMS - set(stems)
    if missing_stems:
        missing = ", ".join(sorted(missing_stems))
        raise ValueError(f"signals.json missing stem section(s): {missing}")

    if "mix_onset_strength" in stems.get("drums", {}):
        raise ValueError(
            "signals.json drums.mix_onset_strength is obsolete; "
            "re-run: python -m cleave analyse <project>"
        )

    full_mix_keys = set(stems.get("full_mix", {}))
    missing_full_mix = _FULL_MIX_KEYS - full_mix_keys
    if missing_full_mix:
        missing = ", ".join(sorted(missing_full_mix))
        raise ValueError(f"signals.json full_mix missing key(s): {missing}")


def load_signals(path: Path) -> Signals:
    signals_path = resolve_signals_path(path)
    if not signals_path.is_file():
        raise FileNotFoundError(signals_path)

    with signals_path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    stems: dict[str, dict[str, np.ndarray]] = {}
    for stem_name, signals in data.items():
        if stem_name in _META_KEYS or not isinstance(signals, dict):
            continue
        stems[stem_name] = {
            key: _list_to_array(values) for key, values in signals.items()
        }

    _validate_signals_data(data, stems)

    raw_beats = data.get("beat_times", [])
    beat_times = tuple(float(t) for t in raw_beats)
    raw_downbeats = data.get("downbeat_times", [])
    downbeat_times = tuple(float(t) for t in raw_downbeats)

    return Signals(
        sample_rate_hz=float(data["sample_rate_hz"]),
        duration_sec=float(data["duration_sec"]),
        path=signals_path,
        stems=stems,
        beat_times=beat_times,
        downbeat_times=downbeat_times,
    )
