"""Tests for cleave.viz.tap_sync."""

from __future__ import annotations

import pytest

from cleave.viz.tap_sync import (
    CONSISTENCY_WINDOW,
    MAX_ACCENT_ACCEPT_SEC,
    MAX_DELTA_SPREAD_SEC,
    METRONOME_BPM,
    METRONOME_QUARTER_SEC,
    MIN_TAP_COUNT,
    accept_tap_for_accent,
    append_streak_delta,
    build_metronome_schedule,
    delta_spread_sec,
    infer_residual_delay_sec,
    mean_delay_from_deltas,
    metronome_accent_times,
    metronome_click_times,
    streak_ready_to_lock,
    tap_delta_sec,
)


def test_build_metronome_schedule_quarter_spacing() -> None:
    schedule = build_metronome_schedule(1.0, 3.0)
    times = metronome_click_times(schedule)
    quarter = 60.0 / METRONOME_BPM
    assert times == pytest.approx(tuple(1.0 + index * quarter for index in range(len(times))))
    assert METRONOME_QUARTER_SEC == pytest.approx(60.0 / METRONOME_BPM)


def test_build_metronome_schedule_accents_every_fourth() -> None:
    schedule = build_metronome_schedule(0.0, 2.5)
    accents = tuple(click.accented for click in schedule)
    assert accents[0] is True
    assert all(not accented for accented in accents[1:4])
    assert accents[4] is True


def test_build_metronome_schedule_empty_when_window_invalid() -> None:
    assert build_metronome_schedule(2.0, 2.0) == ()
    assert build_metronome_schedule(3.0, 1.0) == ()


def test_metronome_accent_times_every_bar_at_140_bpm() -> None:
    schedule = build_metronome_schedule(0.0, 8.0)
    bar_sec = 4.0 * 60.0 / METRONOME_BPM
    expected = tuple(
        click.time_sec for click in schedule if click.accented
    )
    assert metronome_accent_times(schedule) == pytest.approx(expected)
    assert expected[0] == pytest.approx(0.0)
    assert expected[1] - expected[0] == pytest.approx(bar_sec)


def test_tap_delta_sec_nearest_click() -> None:
    clicks = (0.0, 0.5, 1.0)
    assert tap_delta_sec(0.22, clicks) == pytest.approx(0.22)
    assert tap_delta_sec(0.72, clicks) == pytest.approx(0.22)


def test_accept_tap_for_accent_maps_to_nearest_forward_accent() -> None:
    bar_sec = 4.0 * 60.0 / METRONOME_BPM
    accents = (0.0, bar_sec, 2 * bar_sec, 3 * bar_sec)
    index, delta = accept_tap_for_accent(0.2, accents, None)
    assert index == 0
    assert delta == pytest.approx(0.2)

    same_index, same_delta = accept_tap_for_accent(0.21, accents, index)
    assert same_index is None
    assert same_delta is None

    next_index, next_delta = accept_tap_for_accent(bar_sec + 0.2, accents, index)
    assert next_index == 1
    assert next_delta == pytest.approx(0.2)


def test_accept_tap_for_accent_rejects_quiet_quarter_nearby() -> None:
    bar_sec = 4.0 * 60.0 / METRONOME_BPM
    accents = (0.0, bar_sec, 2 * bar_sec, 3 * bar_sec)
    index, delta = accept_tap_for_accent(0.2, accents, None)
    assert index == 0

    quiet_tap_index, quiet_tap_delta = accept_tap_for_accent(0.7, accents, index)
    assert quiet_tap_index is None
    assert quiet_tap_delta is None


def test_accept_tap_for_accent_high_residual_stays_on_accent_not_quiet() -> None:
    bar_sec = 4.0 * 60.0 / METRONOME_BPM
    accents = (0.0, bar_sec, 2 * bar_sec, 3 * bar_sec)
    index, delta = accept_tap_for_accent(0.3, accents, None)
    assert index == 0
    assert delta == pytest.approx(0.3)

    next_index, next_delta = accept_tap_for_accent(bar_sec + 0.3, accents, index)
    assert next_index == 1
    assert next_delta == pytest.approx(0.3)


def test_accept_tap_for_accent_enforces_strictly_increasing_indices() -> None:
    bar_sec = 4.0 * 60.0 / METRONOME_BPM
    accents = (0.0, bar_sec, 2 * bar_sec, 3 * bar_sec)
    index, _delta = accept_tap_for_accent(0.2, accents, None)
    assert index == 0

    late_index, late_delta = accept_tap_for_accent(2 * bar_sec - 0.2, accents, index)
    assert late_index == 2
    assert late_delta == pytest.approx(-0.2)

    rewind_index, rewind_delta = accept_tap_for_accent(bar_sec + 0.2, accents, late_index)
    assert rewind_index is None
    assert rewind_delta is None


def test_accept_tap_for_accent_rejects_taps_beyond_max_distance() -> None:
    bar_sec = 4.0 * 60.0 / METRONOME_BPM
    accents = (0.0, bar_sec, 2 * bar_sec, 3 * bar_sec)
    index, _delta = accept_tap_for_accent(0.2, accents, None)
    assert index == 0

    far_index, far_delta = accept_tap_for_accent(bar_sec * 0.5, accents, index)
    assert far_index is None
    assert far_delta is None
    assert MAX_ACCENT_ACCEPT_SEC == pytest.approx(0.75)


def test_append_streak_delta_grows_when_consistent() -> None:
    streak = append_streak_delta([], 0.20)
    streak = append_streak_delta(streak, 0.21)
    streak = append_streak_delta(streak, 0.19)
    assert streak == pytest.approx([0.20, 0.21, 0.19])


def test_append_streak_delta_resets_when_spread_breaks() -> None:
    streak = append_streak_delta([], 0.20)
    streak = append_streak_delta(streak, 0.21)
    streak = append_streak_delta(streak, 0.50)
    assert streak == pytest.approx([0.50])


def test_streak_ready_to_lock_within_spread() -> None:
    streak = [0.20, 0.21, 0.19, 0.20]
    assert streak_ready_to_lock(streak) is True
    assert MAX_DELTA_SPREAD_SEC == pytest.approx(0.030)


def test_streak_ready_to_lock_rejects_wide_spread() -> None:
    streak = [0.10, 0.20, 0.30, 0.40]
    assert streak_ready_to_lock(streak) is False


def test_streak_ready_to_lock_requires_full_window() -> None:
    streak = [0.20, 0.21, 0.19]
    assert streak_ready_to_lock(streak, window=CONSISTENCY_WINDOW) is False


def test_mean_delay_from_deltas_uses_last_window() -> None:
    deltas = (0.10, 0.20, 0.21, 0.19, 0.20)
    assert mean_delay_from_deltas(deltas) == pytest.approx(0.20)


def test_delta_spread_sec_requires_at_least_two_deltas() -> None:
    deltas = (0.20,)
    assert delta_spread_sec(deltas) is None


def test_delta_spread_sec_uses_full_streak_buffer() -> None:
    deltas = (0.10, 0.20, 0.21, 0.19, 0.20)
    assert delta_spread_sec(deltas) == pytest.approx(0.11)


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
