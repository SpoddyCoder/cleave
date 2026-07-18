"""Tests for cleave.viz.transport_clock."""

from __future__ import annotations

import pytest

from cleave.viz.transport_clock import TransportClock


def _clock(
    *,
    sample_rate: int = 1000,
    total_frames: int = 10_000,
    max_ahead_frames: int = 500,
    latency_frames: int = 0,
) -> TransportClock:
    return TransportClock(
        sample_rate=sample_rate,
        total_frames=total_frames,
        max_ahead_frames=max_ahead_frames,
        latency_frames=latency_frames,
    )


def test_monotonic_advance_while_playing() -> None:
    clock = _clock()
    clock.reanchor(0, wall_time=0.0)
    t0 = clock.file_position_frames(now=0.0)
    t1 = clock.file_position_frames(now=0.1)
    t2 = clock.file_position_frames(now=0.25)
    assert t0 == pytest.approx(0.0)
    assert t1 == pytest.approx(100.0)
    assert t2 == pytest.approx(250.0)
    assert t0 < t1 < t2


def test_no_overshoot_past_max_ahead_or_total() -> None:
    clock = _clock(total_frames=10_000, max_ahead_frames=200)
    clock.reanchor(1000, wall_time=0.0)
    # 1.0s would be +1000 frames; clamped to max_ahead
    assert clock.file_position_frames(now=1.0) == pytest.approx(1200.0)

    clock.reanchor(9900, wall_time=0.0)
    # past total_frames
    assert clock.file_position_frames(now=1.0) == pytest.approx(10_000.0)


def test_exact_position_after_seek_reanchor() -> None:
    clock = _clock()
    clock.reanchor(0, wall_time=0.0)
    clock.reanchor(4410, wall_time=5.0)
    assert clock.file_position_frames(now=5.0) == pytest.approx(4410.0)
    assert clock.file_position_sec(now=5.0) == pytest.approx(4.41)


def test_pause_freezes_resume_continues_without_jump() -> None:
    clock = _clock()
    clock.reanchor(0, wall_time=0.0)
    pos_before = clock.file_position_frames(now=0.5)
    assert pos_before == pytest.approx(500.0)

    clock.set_paused(True, wall_time=0.5)
    assert clock.file_position_frames(now=0.5) == pytest.approx(500.0)
    assert clock.file_position_frames(now=2.0) == pytest.approx(500.0)
    assert clock.file_position_sec(now=99.0) == pytest.approx(0.5)

    clock.set_paused(False, wall_time=2.0)
    assert clock.file_position_frames(now=2.0) == pytest.approx(500.0)
    assert clock.file_position_frames(now=2.1) == pytest.approx(600.0)


def test_audible_subtracts_latency_and_floors_at_zero() -> None:
    clock = _clock(latency_frames=200)
    clock.reanchor(500, wall_time=0.0)
    assert clock.file_position_sec(now=0.0) == pytest.approx(0.5)
    assert clock.audible_position_sec(now=0.0) == pytest.approx(0.3)

    clock.reanchor(50, wall_time=1.0)
    assert clock.audible_position_sec(now=1.0) == pytest.approx(0.0)


def test_determinism_same_anchors_and_now_sequence() -> None:
    def run() -> list[float]:
        clock = _clock(latency_frames=100)
        clock.reanchor(0, wall_time=10.0)
        out = [clock.file_position_sec(now=10.0)]
        out.append(clock.file_position_sec(now=10.2))
        clock.reanchor(400, wall_time=10.4)
        out.append(clock.audible_position_sec(now=10.4))
        clock.set_paused(True, wall_time=10.5)
        out.append(clock.file_position_sec(now=11.0))
        clock.set_paused(False, wall_time=12.0)
        out.append(clock.file_position_sec(now=12.05))
        return out

    assert run() == run()
