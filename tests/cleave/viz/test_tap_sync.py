"""Tests for cleave.viz.tap_sync."""

from __future__ import annotations

import pytest

from cleave.viz.tap_sync import (
    MIN_KEPT_TAPS,
    OUTLIER_SEC,
    SETTLED_SEC,
    TAP_HISTORY,
    estimate_tap_latency,
    kept_tap_deltas,
    push_tap_delta,
    tap_estimate_settled,
    MAX_ACCENT_ACCEPT_SEC,
    MAX_ACCENT_EARLY_SEC,
    METRONOME_BPM,
    METRONOME_QUARTER_SEC,
    accept_tap_for_accent,
    build_metronome_schedule,
    metronome_accent_times,
)


def test_build_metronome_schedule_quarter_spacing() -> None:
    schedule = build_metronome_schedule(1.0, 3.0)
    times = tuple(click.time_sec for click in schedule)
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


def test_accept_tap_for_accent_late_tap_stays_on_accent_not_quiet() -> None:
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


def test_accept_tap_for_accent_ignores_short_click_before_long_tone() -> None:
    """The short click one beat before the long tone must not take that tone."""
    bar_sec = 4.0 * 60.0 / METRONOME_BPM
    quarter = bar_sec / 4.0
    accents = (0.0, bar_sec, 2 * bar_sec)
    index, delta = accept_tap_for_accent(0.05, accents, None)
    assert index == 0
    assert delta == pytest.approx(0.05)

    stolen_index, stolen_delta = accept_tap_for_accent(
        bar_sec - quarter, accents, index
    )
    assert stolen_index is None
    assert stolen_delta is None

    next_index, next_delta = accept_tap_for_accent(bar_sec + 0.05, accents, index)
    assert next_index == 1
    assert next_delta == pytest.approx(0.05)
    assert quarter > MAX_ACCENT_EARLY_SEC


def test_short_click_before_long_tone_does_not_match_on_its_own() -> None:
    bar_sec = 4.0 * 60.0 / METRONOME_BPM
    quarter = bar_sec / 4.0
    accents = (0.0, bar_sec, 2 * bar_sec)
    index, delta = accept_tap_for_accent(bar_sec - quarter, accents, None)
    assert index is None
    assert delta is None


def test_accept_tap_for_accent_rejects_taps_beyond_max_distance() -> None:
    bar_sec = 4.0 * 60.0 / METRONOME_BPM
    accents = (0.0, bar_sec, 2 * bar_sec, 3 * bar_sec)
    index, _delta = accept_tap_for_accent(0.2, accents, None)
    assert index == 0

    far_index, far_delta = accept_tap_for_accent(bar_sec * 0.5, accents, index)
    assert far_index is None
    assert far_delta is None
    assert MAX_ACCENT_ACCEPT_SEC == pytest.approx(0.75)


def test_push_tap_delta_keeps_only_the_most_recent_taps() -> None:
    history: list[float] = []
    for index in range(TAP_HISTORY + 3):
        history = push_tap_delta(history, float(index))
    assert len(history) == TAP_HISTORY
    assert history[0] == 3.0
    assert history[-1] == float(TAP_HISTORY + 2)


def test_kept_tap_deltas_sets_aside_a_stray_tap() -> None:
    history = [0.20, 0.21, 0.19, 0.20, 0.45, 0.205]
    kept = kept_tap_deltas(history)
    assert 0.45 not in kept
    assert len(kept) == 5
    assert OUTLIER_SEC == pytest.approx(0.05)


def test_estimate_is_the_mean_of_kept_taps_with_its_standard_error() -> None:
    history = [0.18, 0.22, 0.18, 0.22]
    estimate = estimate_tap_latency(history)
    assert estimate.taps == 4
    assert estimate.kept == 4
    assert estimate.latency_sec == pytest.approx(0.20)
    # stdev 0.0231 over sqrt(4)
    assert estimate.margin_sec == pytest.approx(0.011547, abs=1e-5)


def test_estimate_with_one_tap_has_no_margin() -> None:
    estimate = estimate_tap_latency([0.2])
    assert estimate.latency_sec == pytest.approx(0.2)
    assert estimate.margin_sec is None
    assert estimate_tap_latency([]).latency_sec is None


def test_a_stray_tap_does_not_move_the_estimate() -> None:
    steady = [0.20, 0.21, 0.19, 0.20, 0.21, 0.19]
    estimate = estimate_tap_latency([*steady[:3], 0.60, *steady[3:]])
    assert estimate.kept == len(steady)
    assert estimate.latency_sec == pytest.approx(0.20)
    assert tap_estimate_settled(estimate) is True


def test_settled_needs_enough_kept_taps() -> None:
    estimate = estimate_tap_latency([0.20] * (MIN_KEPT_TAPS - 1))
    assert tap_estimate_settled(estimate) is False
    estimate = estimate_tap_latency([0.20] * MIN_KEPT_TAPS)
    assert tap_estimate_settled(estimate) is True


def test_loose_taps_settle_once_there_are_enough_of_them() -> None:
    # Taps 20 ms either side of 0.2 s: six do not agree closely enough,
    # but the standard error shrinks as more arrive.
    loose = [0.18, 0.22] * 3
    estimate = estimate_tap_latency(loose)
    assert estimate.margin_sec > SETTLED_SEC
    assert tap_estimate_settled(estimate) is False
    estimate = estimate_tap_latency([0.18, 0.22] * 5)
    assert estimate.margin_sec <= SETTLED_SEC
    assert tap_estimate_settled(estimate) is True
    assert estimate.latency_sec == pytest.approx(0.20)


def test_a_full_history_settles_even_when_loose() -> None:
    wide = [0.16, 0.24] * (TAP_HISTORY // 2)
    estimate = estimate_tap_latency(wide)
    assert estimate.margin_sec > SETTLED_SEC
    assert tap_estimate_settled(estimate) is True


def test_negative_taps_settle_below_zero() -> None:
    estimate = estimate_tap_latency([-0.03, -0.02, -0.04, -0.03, -0.025, -0.035])
    assert tap_estimate_settled(estimate) is True
    assert estimate.latency_sec == pytest.approx(-0.03)
