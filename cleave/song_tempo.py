"""The song's beat and bar length, for settings counted in beats or bars."""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from cleave.signals import Signals

# 120 BPM in 4/4, for a song with no beat analysis.
FALLBACK_BEAT_SEC = 0.5
BEATS_PER_BAR = 4


@dataclass(frozen=True)
class SongTempo:
    beat_sec: float = FALLBACK_BEAT_SEC
    bar_sec: float = FALLBACK_BEAT_SEC * BEATS_PER_BAR


def _median_gap(times: Sequence[float]) -> float | None:
    gaps = [b - a for a, b in zip(times, times[1:]) if b > a]
    return statistics.median(gaps) if gaps else None


def song_tempo_from_signals(signals: Signals | None) -> SongTempo:
    """The median beat and bar of *signals*; a bar is four beats when unknown."""
    if signals is None:
        return SongTempo()
    beat_sec = _median_gap(signals.beat_times) or FALLBACK_BEAT_SEC
    bar_sec = _median_gap(signals.downbeat_times) or beat_sec * BEATS_PER_BAR
    return SongTempo(beat_sec=beat_sec, bar_sec=bar_sec)
