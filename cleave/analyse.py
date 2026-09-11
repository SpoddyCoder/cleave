"""Orchestrate per-stem feature extraction and write signals.json."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import librosa
import numpy as np

from cleave.stems import (
    StemSource,
    beat_detection_audio_path,
    stem_control_label,
    stem_paths,
)
from cleave.extract import (
    extract_bass,
    extract_beats_downbeats,
    extract_drums_onset,
    extract_mix_onset,
    extract_mix_rms,
    extract_other,
    extract_vocals,
)
from cleave.project import mix_path
from cleave.resample import TARGET_HZ, resample_to_100hz


def _stem_duration_sec(path: Path) -> float:
    return float(librosa.get_duration(path=str(path)))


def _nan_to_null(values: np.ndarray) -> list[float | None]:
    return [None if np.isnan(v) else float(v) for v in values]


_ANALYSE_MESSAGE = "Extracting signals..."

_ANALYSE_FRAC_DRUMS = 0.0
_ANALYSE_FRAC_BEATS = 0.05
_ANALYSE_FRAC_BASS = 0.50
_ANALYSE_FRAC_VOCALS = 0.65
_ANALYSE_FRAC_OTHER = 0.80
_ANALYSE_FRAC_MIX_ONSET = 0.85
_ANALYSE_FRAC_MIX_RMS = 0.90
_ANALYSE_FRAC_WRITE = 0.95


def _report_analyse(
    on_progress: Callable[[str, float | None], None] | None,
    fraction: float,
) -> None:
    if on_progress is not None:
        on_progress(_ANALYSE_MESSAGE, fraction)


def run_analyse(
    project_dir: Path,
    *,
    high_quality: bool,
    beat_detection_stem: StemSource = "full_mix",
    on_progress: Callable[[str, float | None], None] | None = None,
) -> Path:
    paths = stem_paths(project_dir)
    mix = mix_path(project_dir)
    beat_audio = beat_detection_audio_path(project_dir, beat_detection_stem)
    duration_sec = max(
        _stem_duration_sec(path) for path in (*paths.values(), mix)
    )

    _report_analyse(on_progress, _ANALYSE_FRAC_DRUMS)
    drums_onset = extract_drums_onset(paths["drums"])
    _report_analyse(on_progress, _ANALYSE_FRAC_BEATS)
    beats, downbeats = extract_beats_downbeats(
        beat_audio, on_progress=on_progress
    )
    _report_analyse(on_progress, _ANALYSE_FRAC_BASS)
    bass = extract_bass(paths["bass"])
    _report_analyse(on_progress, _ANALYSE_FRAC_VOCALS)
    vocals = extract_vocals(paths["vocals"], high_quality=high_quality)
    _report_analyse(on_progress, _ANALYSE_FRAC_OTHER)
    other = extract_other(paths["other"])
    _report_analyse(on_progress, _ANALYSE_FRAC_MIX_ONSET)
    mix_onset = extract_mix_onset(mix)
    _report_analyse(on_progress, _ANALYSE_FRAC_MIX_RMS)
    mix_rms = extract_mix_rms(mix)

    source_label = stem_control_label(beat_detection_stem)
    if len(beats) == 0:
        print(f"{source_label} beat detection produced no useful data")
        beat_times = []
    else:
        beat_times = [float(t) for t in beats]

    if len(downbeats) == 0:
        print(f"{source_label} downbeat detection produced no useful data")
        downbeat_times = []
    else:
        downbeat_times = [float(t) for t in downbeats]

    output: dict = {
        "version": 4,
        "sample_rate_hz": int(TARGET_HZ),
        "duration_sec": duration_sec,
        "beat_detection_stem": beat_detection_stem,
        "beat_times": beat_times,
        "downbeat_times": downbeat_times,
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
            "spectral_centroid": resample_to_100hz(
                *other["spectral_centroid"], duration_sec
            ).tolist(),
            "rms": resample_to_100hz(*other["rms"], duration_sec).tolist(),
        },
        "full_mix": {
            "onset_strength": resample_to_100hz(*mix_onset, duration_sec).tolist(),
            "rms": resample_to_100hz(*mix_rms, duration_sec).tolist(),
        },
    }

    _report_analyse(on_progress, _ANALYSE_FRAC_WRITE)
    signals_path = project_dir / "signals.json"
    with signals_path.open("w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2)
        handle.write("\n")

    _report_analyse(on_progress, 1.0)
    return signals_path
