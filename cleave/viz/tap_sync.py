"""Tap-to-sync inference for machine-local wireless delay."""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from cleave.viz.transport_clock import MAX_RESIDUAL_DELAY_SEC

MIN_TAP_COUNT = 4
CONSISTENCY_WINDOW = 4
MAX_DELTA_SPREAD_SEC = 0.030
MAX_ACCENT_ACCEPT_SEC = 0.75
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


def metronome_click_times(schedule: Sequence[MetronomeClick]) -> tuple[float, ...]:
    return tuple(click.time_sec for click in schedule)


def metronome_accent_times(schedule: Sequence[MetronomeClick]) -> tuple[float, ...]:
    """Return accented click times (downbeats) from a metronome schedule."""
    return tuple(click.time_sec for click in schedule if click.accented)


def _nearest_click_index(tap_sec: float, click_times: Sequence[float]) -> int | None:
    if not click_times:
        return None
    return min(range(len(click_times)), key=lambda index: abs(click_times[index] - tap_sec))


def tap_delta_sec(tap_sec: float, click_times: Sequence[float]) -> float | None:
    """Return tap minus nearest click time, or None when no clicks exist."""
    index = _nearest_click_index(tap_sec, click_times)
    if index is None:
        return None
    return tap_sec - click_times[index]


def _nearest_forward_accent_index(
    tap_sec: float,
    accent_times: Sequence[float],
    last_accent_index: int | None,
    *,
    max_accept_sec: float = MAX_ACCENT_ACCEPT_SEC,
) -> int | None:
    if not accent_times:
        return None
    start = 0 if last_accent_index is None else last_accent_index + 1
    if start >= len(accent_times):
        return None
    best_index: int | None = None
    best_distance = float("inf")
    for index in range(start, len(accent_times)):
        distance = abs(tap_sec - accent_times[index])
        if distance < best_distance:
            best_distance = distance
            best_index = index
    if best_index is None or best_distance > max_accept_sec:
        return None
    return best_index


def accept_tap_for_accent(
    tap_sec: float,
    accent_times: Sequence[float],
    last_accent_index: int | None,
    *,
    max_accept_sec: float = MAX_ACCENT_ACCEPT_SEC,
) -> tuple[int | None, float | None]:
    """Accept a tap when it maps to a new forward accent within *max_accept_sec*."""
    index = _nearest_forward_accent_index(
        tap_sec,
        accent_times,
        last_accent_index,
        max_accept_sec=max_accept_sec,
    )
    if index is None:
        return None, None
    if last_accent_index is not None and index <= last_accent_index:
        return None, None
    return index, tap_sec - accent_times[index]


def append_streak_delta(
    streak: Sequence[float],
    new_delta: float,
    *,
    max_spread_sec: float = MAX_DELTA_SPREAD_SEC,
) -> list[float]:
    """Append *new_delta* to the streak buffer, resetting when spread breaks."""
    buffer = list(streak)
    if buffer:
        trial = buffer + [new_delta]
        if max(trial) - min(trial) > max_spread_sec:
            return [new_delta]
    buffer.append(new_delta)
    return buffer


def streak_ready_to_lock(
    streak: Sequence[float],
    *,
    window: int = CONSISTENCY_WINDOW,
    max_spread_sec: float = MAX_DELTA_SPREAD_SEC,
) -> bool:
    """True when the streak buffer has *window* deltas within *max_spread_sec*."""
    if len(streak) < window:
        return False
    window_deltas = streak[-window:]
    return max(window_deltas) - min(window_deltas) <= max_spread_sec


def mean_delay_from_deltas(
    deltas: Sequence[float],
    *,
    window: int = CONSISTENCY_WINDOW,
) -> float:
    """Mean of the last *window* tap deltas."""
    return statistics.mean(deltas[-window:])


def delta_spread_sec(
    deltas: Sequence[float],
    *,
    min_count: int = 2,
) -> float | None:
    """Spread (max - min) of the streak buffer, or None when too few deltas."""
    if len(deltas) < min_count:
        return None
    return max(deltas) - min(deltas)


def infer_residual_delay_sec(
    tap_audible_zero_residual: Sequence[float],
    click_times: Sequence[float],
) -> float:
    """Infer residual delay from taps captured with residual forced to zero."""
    if len(tap_audible_zero_residual) < MIN_TAP_COUNT or not click_times:
        return 0.0

    deltas: list[float] = []
    for tap in tap_audible_zero_residual:
        delta = tap_delta_sec(tap, click_times)
        if delta is not None:
            deltas.append(delta)

    if len(deltas) < MIN_TAP_COUNT:
        return 0.0

    return max(0.0, min(statistics.median(deltas), MAX_RESIDUAL_DELAY_SEC))
