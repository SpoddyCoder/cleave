"""Tests for cleave.viz.tap_sync."""

from __future__ import annotations

import pytest

from cleave.viz.tap_sync import (
    CONSISTENCY_WINDOW,
    MAX_DELTA_SPREAD_SEC,
    METRONOME_BPM,
    METRONOME_QUARTER_SEC,
    MIN_TAP_COUNT,
    accept_tap_for_click,
    build_metronome_schedule,
    consecutive_deltas_consistent,
    infer_residual_delay_sec,
    mean_delay_from_deltas,
    metronome_click_times,
    tap_delta_sec,
)


def test_build_metronome_schedule_quarter_spacing() -> None:
    schedule = build_metronome_schedule(1.0, 3.0)
    times = metronome_click_times(schedule)
    assert times == pytest.approx((1.0, 1.5, 2.0, 2.5))
    assert METRONOME_QUARTER_SEC == pytest.approx(60.0 / METRONOME_BPM)


def test_build_metronome_schedule_accents_every_fourth() -> None:
    schedule = build_metronome_schedule(0.0, 2.5)
    accents = tuple(click.accented for click in schedule)
    assert accents == (True, False, False, False, True)


def test_build_metronome_schedule_empty_when_window_invalid() -> None:
    assert build_metronome_schedule(2.0, 2.0) == ()
    assert build_metronome_schedule(3.0, 1.0) == ()


def test_tap_delta_sec_nearest_click() -> None:
    clicks = (0.0, 0.5, 1.0)
    assert tap_delta_sec(0.22, clicks) == pytest.approx(0.22)
    assert tap_delta_sec(0.72, clicks) == pytest.approx(0.22)


def test_accept_tap_for_click_requires_distinct_clicks() -> None:
    clicks = (0.0, 0.5, 1.0, 1.5)
    index, delta = accept_tap_for_click(0.2, clicks, None)
    assert index == 0
    assert delta == pytest.approx(0.2)

    same_index, same_delta = accept_tap_for_click(0.21, clicks, index)
    assert same_index is None
    assert same_delta is None

    next_index, next_delta = accept_tap_for_click(0.7, clicks, index)
    assert next_index == 1
    assert next_delta == pytest.approx(0.2)


def test_consecutive_deltas_consistent_within_spread() -> None:
    deltas = (0.20, 0.21, 0.19, 0.20)
    assert consecutive_deltas_consistent(deltas) is True


def test_consecutive_deltas_consistent_rejects_wide_spread() -> None:
    deltas = (0.10, 0.20, 0.30, 0.40)
    assert consecutive_deltas_consistent(deltas) is False
    assert MAX_DELTA_SPREAD_SEC == pytest.approx(0.025)


def test_consecutive_deltas_consistent_requires_full_window() -> None:
    deltas = (0.20, 0.21, 0.19)
    assert consecutive_deltas_consistent(deltas, window=CONSISTENCY_WINDOW) is False


def test_mean_delay_from_deltas_uses_last_window() -> None:
    deltas = (0.10, 0.20, 0.21, 0.19, 0.20)
    assert mean_delay_from_deltas(deltas) == pytest.approx(0.20)


def test_infer_residual_delay_median_of_nearest_click_deltas() -> None:
    clicks = (0.0, 1.0, 2.0, 3.0)
    taps = (0.2, 1.2, 2.2, 3.2)
    assert infer_residual_delay_sec(taps, clicks) == pytest.approx(0.2)


def test_infer_residual_delay_clamps_high() -> None:
    clicks = (0.0, 10.0, 20.0, 30.0)
    taps = (5.0, 15.0, 25.0, 35.0)
    assert infer_residual_delay_sec(taps, clicks) == pytest.approx(2.0)


def test_infer_residual_delay_clamps_low() -> None:
    clicks = (1.0, 2.0, 3.0, 4.0)
    taps = (0.0, 0.1, 0.2, 0.3)
    assert infer_residual_delay_sec(taps, clicks) == pytest.approx(0.0)


def test_infer_residual_delay_requires_min_taps() -> None:
    clicks = (0.0, 1.0, 2.0, 3.0)
    assert infer_residual_delay_sec((0.2, 1.2, 2.2), clicks) == 0.0
    assert infer_residual_delay_sec((), clicks) == 0.0


def test_infer_residual_delay_empty_clicks() -> None:
    taps = tuple(0.2 + i for i in range(MIN_TAP_COUNT))
    assert infer_residual_delay_sec(taps, ()) == 0.0
