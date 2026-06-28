"""Tests for live overlay draw profiling."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cleave.viz.overlay_profiler import (
    OverlayDrawCounters,
    OverlayFrameSample,
    OverlayProfiler,
    _format_sample_line,
)


def test_from_env_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLEAVE_OVERLAY_PROFILE", raising=False)
    profiler = OverlayProfiler.from_env()
    assert profiler.enabled is False
    assert profiler.emit_interval_frames == 30


def test_from_env_enabled_prints_banner(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("CLEAVE_OVERLAY_PROFILE", "1")
    profiler = OverlayProfiler.from_env()
    assert profiler.enabled is True
    assert "overlay profiler: on" in capsys.readouterr().out


def test_from_env_custom_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLEAVE_OVERLAY_PROFILE", "1")
    monkeypatch.setenv("CLEAVE_OVERLAY_PROFILE_INTERVAL", "120")
    profiler = OverlayProfiler.from_env()
    assert profiler.emit_interval_frames == 120


def test_format_sample_line_full() -> None:
    sample = OverlayFrameSample(
        view_state_build_ms=0.4,
        panel_draw_ms=2.1,
        upload_ms=0.3,
        overlay_present_ms=0.05,
        surface_builds=18,
        font_renders=42,
        row_cache_hits=10,
        row_cache_misses=2,
        skipped=False,
    )
    assert (
        _format_sample_line(sample)
        == "overlay: vs=0.4ms draw=2.1ms surf=18 font=42 rcache=10/2 up=0.3ms"
    )


def test_format_sample_line_skip() -> None:
    sample = OverlayFrameSample(
        view_state_build_ms=0.0,
        panel_draw_ms=0.0,
        upload_ms=0.0,
        overlay_present_ms=0.0,
        surface_builds=0,
        font_renders=0,
        row_cache_hits=0,
        row_cache_misses=0,
        skipped=True,
    )
    assert _format_sample_line(sample) == "overlay: skip"


def test_finish_frame_prints_compact_line(capsys: pytest.CaptureFixture[str]) -> None:
    profiler = OverlayProfiler(enabled=True, emit_interval_frames=1)
    profiler._section_ms["view_state_build"] = 0.4
    profiler._section_ms["panel_draw"] = 2.1
    profiler._section_ms["upload"] = 0.3
    profiler._counters.surface_builds = 18
    profiler._counters.font_renders = 42

    sample = profiler.finish_frame()

    assert sample is not None
    assert sample.view_state_build_ms == pytest.approx(0.4)
    assert sample.panel_draw_ms == pytest.approx(2.1)
    assert sample.upload_ms == pytest.approx(0.3)
    assert sample.surface_builds == 18
    assert sample.font_renders == 42
    assert capsys.readouterr().out.strip() == (
        "overlay: vs=0.4ms draw=2.1ms surf=18 font=42 rcache=0/0 up=0.3ms"
    )


def test_finish_frame_disabled_returns_none() -> None:
    profiler = OverlayProfiler(enabled=False)
    assert profiler.finish_frame() is None


def test_counter_increments() -> None:
    profiler = OverlayProfiler(enabled=True)
    counters = profiler.counters()
    counters.surface_builds += 3
    counters.font_renders += 7

    sample = profiler.finish_frame()

    assert sample is not None
    assert sample.surface_builds == 3
    assert sample.font_renders == 7


def test_time_section_accumulates() -> None:
    profiler = OverlayProfiler(enabled=True, emit_interval_frames=999)
    with patch(
        "cleave.viz.overlay_profiler.time.perf_counter",
        side_effect=[0.0, 0.001, 0.001, 0.003],
    ):
        with profiler.time_section("view_state_build"):
            pass
        with profiler.time_section("view_state_build"):
            pass

    sample = profiler.finish_frame()

    assert sample is not None
    assert sample.view_state_build_ms == pytest.approx(3.0)


def test_time_section_unknown_name_raises() -> None:
    profiler = OverlayProfiler(enabled=True)
    with pytest.raises(ValueError, match="unknown overlay profiler section"):
        with profiler.time_section("not_a_section"):
            pass


def test_note_skipped_frame(capsys: pytest.CaptureFixture[str]) -> None:
    profiler = OverlayProfiler(enabled=True, emit_interval_frames=1)
    profiler.note_skipped_frame()

    sample = profiler.finish_frame()

    assert sample is not None
    assert sample.skipped is True
    assert capsys.readouterr().out.strip() == "overlay: skip"


def test_toggle_enables_and_emits_next_frame(capsys: pytest.CaptureFixture[str]) -> None:
    profiler = OverlayProfiler(enabled=False, emit_interval_frames=30)
    profiler.toggle()
    assert profiler.enabled is True
    assert profiler.last_line == "overlay: …"
    banner = capsys.readouterr().out
    assert "overlay profiler: on" in banner

    profiler.note_skipped_frame()
    sample = profiler.finish_frame()
    assert sample is not None
    assert sample.skipped is True
    out = capsys.readouterr().out.strip()
    assert out == "overlay: skip"
    assert profiler.last_line == "overlay: skip"


def test_toggle_disables_and_clears_state() -> None:
    profiler = OverlayProfiler(enabled=True)
    profiler.counters().surface_builds = 5
    profiler.note_skipped_frame()

    profiler.toggle()

    assert profiler.enabled is False
    assert profiler.last_line is None
    assert profiler.finish_frame() is None
    assert profiler.counters() == OverlayDrawCounters()
