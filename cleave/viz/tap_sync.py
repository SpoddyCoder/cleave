"""Tap timing calibration: how late key presses land after the heard beat."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

# Recent taps the estimate draws on.
TAP_HISTORY = 16
# A tap this far from the median of recent taps is a slip and is set aside.
OUTLIER_SEC = 0.050
# Fewest kept taps before a result can be reported.
MIN_KEPT_TAPS = 6
# Lock in once the estimate's standard error is this small.
SETTLED_SEC = 0.007
# Late taps still belong to the long bar tone (output latency).
MAX_ACCENT_ACCEPT_SEC = 0.75
# Early window stays inside one quarter (140 BPM quarter is ~0.43s) so the
# short click before the bar tone cannot claim it.
MAX_ACCENT_EARLY_SEC = 0.25
METRONOME_BPM = 140
METRONOME_BEATS_PER_BAR = 4
METRONOME_QUARTER_SEC = 60.0 / METRONOME_BPM


@dataclass(frozen=True)
class MetronomeClick:
    time_sec: float
    accented: bool


def build_metronome_schedule(
    start_sec: float,
    end_sec: float,
    *,
    bpm: float = METRONOME_BPM,
    beats_per_bar: int = METRONOME_BEATS_PER_BAR,
) -> tuple[MetronomeClick, ...]:
    """Return quarter-note click times from *start_sec* up to *end_sec*."""
    if end_sec <= start_sec:
        return ()
    interval = 60.0 / bpm
    clicks: list[MetronomeClick] = []
    index = 0
    while True:
        time_sec = start_sec + index * interval
        if time_sec >= end_sec:
            break
        clicks.append(MetronomeClick(time_sec, index % beats_per_bar == 0))
        index += 1
    return tuple(clicks)


def metronome_accent_times(schedule: Sequence[MetronomeClick]) -> tuple[float, ...]:
    """Return accented click times (downbeats) from a metronome schedule."""
    return tuple(click.time_sec for click in schedule if click.accented)


def _nearest_forward_accent_index(
    tap_sec: float,
    accent_times: Sequence[float],
    last_accent_index: int | None,
    *,
    max_early_sec: float = MAX_ACCENT_EARLY_SEC,
    max_late_sec: float = MAX_ACCENT_ACCEPT_SEC,
) -> int | None:
    if not accent_times:
        return None
    start = 0 if last_accent_index is None else last_accent_index + 1
    if start >= len(accent_times):
        return None
    best_index: int | None = None
    best_distance = float("inf")
    for index in range(start, len(accent_times)):
        delta = tap_sec - accent_times[index]
        if delta < -max_early_sec or delta > max_late_sec:
            continue
        distance = abs(delta)
        if distance < best_distance:
            best_distance = distance
            best_index = index
    return best_index


def accept_tap_for_accent(
    tap_sec: float,
    accent_times: Sequence[float],
    last_accent_index: int | None,
    *,
    max_early_sec: float = MAX_ACCENT_EARLY_SEC,
    max_late_sec: float = MAX_ACCENT_ACCEPT_SEC,
) -> tuple[int | None, float | None]:
    """Accept a tap when it maps to a new forward accent.

    Early taps must fall inside *max_early_sec* (less than one quarter, so the
    short click before the long bar tone does not take it). Late taps may be
    as far as *max_late_sec* to cover output latency.
    """
    index = _nearest_forward_accent_index(
        tap_sec,
        accent_times,
        last_accent_index,
        max_early_sec=max_early_sec,
        max_late_sec=max_late_sec,
    )
    if index is None:
        return None, None
    if last_accent_index is not None and index <= last_accent_index:
        return None, None
    return index, tap_sec - accent_times[index]


@dataclass(frozen=True)
class TapEstimate:
    """Where recent taps put the tap latency, and how settled that is.

    ``latency_sec`` is the mean of the kept taps; ``margin_sec`` is its
    standard error (None with fewer than two kept taps).
    """

    taps: int
    kept: int
    latency_sec: float | None
    margin_sec: float | None


def push_tap_delta(
    history: Sequence[float],
    delta: float,
    *,
    limit: int = TAP_HISTORY,
) -> list[float]:
    """Append *delta*, keeping only the last *limit* taps."""
    return [*history, delta][-limit:]


def kept_tap_deltas(
    history: Sequence[float],
    *,
    outlier_sec: float = OUTLIER_SEC,
) -> list[float]:
    """Taps within *outlier_sec* of the median; the rest are slips."""
    if not history:
        return []
    centre = statistics.median(history)
    return [delta for delta in history if abs(delta - centre) <= outlier_sec]


def estimate_tap_latency(history: Sequence[float]) -> TapEstimate:
    kept = kept_tap_deltas(history)
    if not kept:
        return TapEstimate(len(history), 0, None, None)
    latency = statistics.fmean(kept)
    margin = (
        statistics.stdev(kept) / math.sqrt(len(kept)) if len(kept) >= 2 else None
    )
    return TapEstimate(len(history), len(kept), latency, margin)


def tap_estimate_settled(
    estimate: TapEstimate,
    *,
    min_kept: int = MIN_KEPT_TAPS,
    settled_sec: float = SETTLED_SEC,
    history_limit: int = TAP_HISTORY,
) -> bool:
    """True when enough taps are kept and either agree closely, or the
    history is full (a steady but loose tapper still gets a result)."""
    if estimate.kept < min_kept or estimate.margin_sec is None:
        return False
    return estimate.margin_sec <= settled_sec or estimate.taps >= history_limit
