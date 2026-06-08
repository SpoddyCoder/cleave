"""Orchestrate per-stem feature extraction and write signals.json."""

from __future__ import annotations

import json
from pathlib import Path

import librosa
import numpy as np

from cleave.extract import (
    extract_bass,
    extract_drums_onset,
    extract_mix_onset,
    extract_other,
    extract_vocals,
    stem_paths,
)
from cleave.resample import TARGET_HZ, resample_to_100hz


def _stem_duration_sec(path: Path) -> float:
    return float(librosa.get_duration(path=str(path)))


def _nan_to_null(values: np.ndarray) -> list[float | None]:
    return [None if np.isnan(v) else float(v) for v in values]


def run_analyse(project_dir: Path, *, source: Path | None, slow: bool) -> Path:
    paths = stem_paths(project_dir)
    duration_sec = max(_stem_duration_sec(path) for path in paths.values())

    drums_onset = extract_drums_onset(paths["drums"])
    bass = extract_bass(paths["bass"])
    vocals = extract_vocals(paths["vocals"], slow=slow)
    other = extract_other(paths["other"])
    mix_onset = extract_mix_onset(source) if source is not None else None

    output: dict = {
        "version": 1,
        "sample_rate_hz": int(TARGET_HZ),
        "duration_sec": duration_sec,
        "source": str(source) if source is not None else None,
        "drums": {
            "onset_strength": resample_to_100hz(
                *drums_onset, duration_sec
            ).tolist(),
        },
        "bass": {
            "rms": resample_to_100hz(*bass["rms"], duration_sec).tolist(),
            "sub_bass": resample_to_100hz(*bass["sub_bass"], duration_sec).tolist(),
            "mid_bass": resample_to_100hz(*bass["mid_bass"], duration_sec).tolist(),
        },
        "vocals": {
            "rms": resample_to_100hz(*vocals["rms"], duration_sec).tolist(),
            "pitch_hz": _nan_to_null(
                resample_to_100hz(*vocals["pitch_hz"], duration_sec)
            ),
        },
        "other": {
            "spectral_centroid": resample_to_100hz(*other, duration_sec).tolist(),
        },
    }

    if mix_onset is not None:
        output["drums"]["mix_onset_strength"] = resample_to_100hz(
            *mix_onset, duration_sec
        ).tolist()

    signals_path = project_dir / "signals.json"
    with signals_path.open("w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)
        handle.write("\n")

    return signals_path
