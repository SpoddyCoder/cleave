"""Tests for the live editor's frame timer."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cleave.viz.overlay_profiler import (
    SECTION_LABELS,
    FrameReport,
    OverlayProfiler,
    UploadCounts,
    report_rows,
)
from cleave.viz.overlay_upload import UploadPlan

_CLOCK = "cleave.viz.overlay_profiler.time.perf_counter"


def _plan(mode: str) -> UploadPlan:
    return UploadPlan(
        mode=mode,  # type: ignore[arg-type]
        dirty_rects=(),
        active_size=(100, 50),
        screen_rect=(0, 0, 100, 50),
    )


def test_from_env_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLEAVE_OVERLAY_PROFILE", raising=False)
    monkeypatch.delenv("CLEAVE_OVERLAY_PROFILE_INTERVAL", raising=False)
    profiler = OverlayProfiler.from_env()
    assert profiler.enabled is False
    assert profiler.window_frames == 30


def test_from_env_enabled_with_custom_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLEAVE_OVERLAY_PROFILE", "1")
    monkeypatch.setenv("CLEAVE_OVERLAY_PROFILE_INTERVAL", "120")
    profiler = OverlayProfiler.from_env()
    assert profiler.enabled is True
    assert profiler.window_frames == 120


def test_unknown_section_raises() -> None:
    profiler = OverlayProfiler(enabled=True)
    with pytest.raises(ValueError, match="unknown frame timer section"):
        with profiler.time_section("not_a_section"):
            pass


def test_report_averages_sections_over_the_window() -> None:
    profiler = OverlayProfiler(enabled=True, window_frames=2)
    # Boundary at 0, then two 10 ms frames, each with 2 ms of events.
    ticks = [0.0, 0.001, 0.003, 0.010, 0.011, 0.013, 0.020]
    with patch(_CLOCK, side_effect=ticks):
        profiler.end_frame()
        for _ in range(2):
            with profiler.time_section("events"):
                pass
            profiler.end_frame()

    report = profiler.report
    assert report is not None
    assert report.frames == 2
    assert report.frame_ms == pytest.approx(10.0)
    assert report.fps == pytest.approx(100.0)
    assert dict(report.sections)["events"] == pytest.approx(2.0)
    assert report.other_ms == pytest.approx(8.0)
    assert [name for name, _ms in report.sections] == list(SECTION_LABELS)


def test_nested_section_time_is_not_counted_twice() -> None:
    profiler = OverlayProfiler(enabled=True, window_frames=1)
    # build opens at 1 ms, render runs 2..5 ms, build closes at 6 ms.
    ticks = [0.0, 0.001, 0.002, 0.005, 0.006, 0.010]
    with patch(_CLOCK, side_effect=ticks):
        profiler.end_frame()
        with profiler.time_section("ui_build"):
            with profiler.time_section("ui_render"):
                pass
        profiler.end_frame()

    assert profiler.report is not None
    sections = dict(profiler.report.sections)
    assert sections["ui_build"] == pytest.approx(2.0)
    assert sections["ui_render"] == pytest.approx(3.0)
    assert profiler.report.other_ms == pytest.approx(5.0)


def test_sections_before_the_first_boundary_are_dropped() -> None:
    profiler = OverlayProfiler(enabled=True, window_frames=1)
    with patch(_CLOCK, side_effect=[0.0, 0.004, 0.005, 0.010]):
        with profiler.time_section("flip"):
            pass
        profiler.end_frame()
        profiler.end_frame()

    assert profiler.report is not None
    assert dict(profiler.report.sections)["flip"] == 0.0


def test_disabled_profiler_reports_nothing() -> None:
    profiler = OverlayProfiler(enabled=False, window_frames=1)
    with profiler.time_section("events"):
        pass
    profiler.note_upload_plan(_plan("full"))
    profiler.end_frame()
    profiler.end_frame()
    assert profiler.report is None


def test_upload_counts_cover_the_window() -> None:
    profiler = OverlayProfiler(enabled=True, window_frames=1)
    profiler.end_frame()
    profiler.note_upload_plan(_plan("skip"))
    profiler.note_upload_plan(_plan("skip"))
    profiler.note_upload_plan(_plan("partial"))
    profiler.note_upload_plan(_plan("full"))
    profiler.note_texture_reallocs(0)
    profiler.note_texture_reallocs(2)
    profiler.note_projectm_fps(45)
    profiler.end_frame()

    assert profiler.report is not None
    assert profiler.report.uploads == UploadCounts(
        skipped=2, partial=1, full=1, texture_reallocs=2
    )
    assert profiler.report.pm_fps == 45

    profiler.end_frame()
    assert profiler.report.uploads == UploadCounts()


def test_toggle_clears_the_report() -> None:
    profiler = OverlayProfiler(enabled=True, window_frames=1)
    profiler.end_frame()
    profiler.end_frame()
    assert profiler.report is not None

    profiler.toggle()
    assert profiler.enabled is False
    assert profiler.report is None

    profiler.toggle()
    assert profiler.enabled is True
    assert profiler.report is None


def test_report_rows_pending() -> None:
    assert report_rows(None) == [("Frame", "measuring")]


def test_report_rows_list_every_section_then_other() -> None:
    report = FrameReport(
        frames=30,
        frame_ms=10.0,
        sections=tuple((name, 1.0) for name in SECTION_LABELS),
        uploads=UploadCounts(skipped=28, partial=2, texture_reallocs=1),
        pm_fps=60,
    )
    rows = report_rows(report)

    assert rows[0] == ("Frame", "10.00 ms  100 fps")
    assert [label for label, _value in rows[1:10]] == list(SECTION_LABELS.values())
    assert rows[10] == ("Other", "1.00 ms")
    assert rows[11] == ("Strip uploads / 30", "skip 28  part 2  full 0  realloc 1")
    assert rows[12] == ("projectM target", "60 fps")


def test_toggle_inside_an_open_section_does_not_break_it() -> None:
    """F3 is read inside the events section, so it toggles mid-section."""
    profiler = OverlayProfiler(enabled=True)
    with profiler.time_section("events"):
        profiler.toggle()
    assert not profiler.enabled
    profiler.toggle()
    with profiler.time_section("tick"):
        with profiler.time_section("events"):
            profiler.toggle()
            profiler.toggle()
    with profiler.time_section("events"):
        pass
    profiler.end_frame()
    with profiler.time_section("events"):
        pass
    profiler.end_frame()
