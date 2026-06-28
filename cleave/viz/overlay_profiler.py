"""Per-frame overlay draw profiling for the live tuning UI.

Enable at runtime with **F3** (toggle) or start enabled via
``CLEAVE_OVERLAY_PROFILE=1``. Results print to the terminal stdout every
``CLEAVE_OVERLAY_PROFILE_INTERVAL`` frames (default 30). When the tuning panel
is visible, the latest sample also appears on the panel bottom-left.

Phase 1 baselines: record stdout for hidden, collapsed, and one-layer-expanded
panel states.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

from cleave.viz.overlay_upload import UploadPlan

_DEFAULT_EMIT_INTERVAL = 30

_SECTION_NAMES = frozenset(
    {"view_state_build", "panel_draw", "upload", "overlay_present"}
)


@dataclass
class OverlayDrawCounters:
    surface_builds: int = 0
    font_renders: int = 0
    row_cache_hits: int = 0
    row_cache_misses: int = 0
    upload_skipped: int = 0
    upload_partial: int = 0
    upload_full: int = 0
    upload_partial_rects: int = 0
    texture_reallocs: int = 0


@dataclass
class OverlayFrameSample:
    view_state_build_ms: float
    panel_draw_ms: float
    upload_ms: float
    overlay_present_ms: float
    surface_builds: int
    font_renders: int
    row_cache_hits: int
    row_cache_misses: int
    upload_skipped: int
    upload_partial: int
    upload_full: int
    upload_partial_rects: int
    texture_reallocs: int
    skipped: bool
    pm_fps: int | None = None


def _upload_stats_suffix(sample: OverlayFrameSample) -> str:
    if not (
        sample.upload_skipped
        or sample.upload_partial
        or sample.upload_full
        or sample.texture_reallocs
    ):
        return ""
    parts: list[str] = []
    if sample.upload_skipped:
        parts.append(f"uskip={sample.upload_skipped}")
    if sample.upload_partial:
        rect_suffix = (
            f"/{sample.upload_partial_rects}"
            if sample.upload_partial_rects
            else ""
        )
        parts.append(f"upart={sample.upload_partial}{rect_suffix}")
    if sample.upload_full:
        parts.append(f"ufull={sample.upload_full}")
    if sample.texture_reallocs:
        parts.append(f"urealloc={sample.texture_reallocs}")
    return " " + " ".join(parts)


def _format_sample_line(sample: OverlayFrameSample) -> str:
    if sample.skipped:
        return "overlay: skip"
    line = (
        f"overlay: vs={sample.view_state_build_ms:.1f}ms"
        f" draw={sample.panel_draw_ms:.1f}ms"
        f" surf={sample.surface_builds}"
        f" font={sample.font_renders}"
        f" rcache={sample.row_cache_hits}/{sample.row_cache_misses}"
        f" up={sample.upload_ms:.1f}ms"
        f"{_upload_stats_suffix(sample)}"
    )
    if sample.pm_fps is not None:
        line += f" pm={sample.pm_fps}"
    return line


@dataclass
class OverlayProfiler:
    enabled: bool
    emit_interval_frames: int = _DEFAULT_EMIT_INTERVAL
    _section_ms: dict[str, float] = field(default_factory=dict, init=False, repr=False)
    _counters: OverlayDrawCounters = field(
        default_factory=OverlayDrawCounters, init=False, repr=False
    )
    _skipped: bool = field(default=False, init=False, repr=False)
    _pm_fps: int | None = field(default=None, init=False, repr=False)
    _frames_since_emit: int = field(default=0, init=False, repr=False)
    _emit_next_frame: bool = field(default=False, init=False, repr=False)
    last_line: str | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_env(cls) -> OverlayProfiler:
        enabled = os.environ.get("CLEAVE_OVERLAY_PROFILE", "") == "1"
        interval = _DEFAULT_EMIT_INTERVAL
        raw_interval = os.environ.get("CLEAVE_OVERLAY_PROFILE_INTERVAL")
        if raw_interval is not None:
            interval = int(raw_interval)
        profiler = cls(enabled=enabled, emit_interval_frames=interval)
        if enabled:
            profiler._emit_next_frame = True
            print(
                f"overlay profiler: on (logging to terminal every "
                f"{interval} frames; latest on panel when open)",
                flush=True,
            )
        return profiler

    def counters(self) -> OverlayDrawCounters:
        return self._counters

    def note_skipped_frame(self) -> None:
        self._skipped = True

    def note_projectm_fps(self, target: int) -> None:
        self._pm_fps = target

    def note_upload_plan(self, plan: UploadPlan) -> None:
        if not self.enabled:
            return
        if plan.mode == "skip":
            self._counters.upload_skipped += 1
        elif plan.mode == "partial":
            self._counters.upload_partial += 1
            self._counters.upload_partial_rects += len(plan.dirty_rects)
        elif plan.mode == "full":
            self._counters.upload_full += 1

    @contextmanager
    def time_section(self, name: str) -> Iterator[None]:
        if name not in _SECTION_NAMES:
            raise ValueError(f"unknown overlay profiler section: {name!r}")
        if not self.enabled:
            yield
            return
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self._section_ms[name] = self._section_ms.get(name, 0.0) + elapsed_ms

    def finish_frame(self) -> OverlayFrameSample | None:
        if not self.enabled:
            self._reset_frame()
            return None

        sample = OverlayFrameSample(
            view_state_build_ms=self._section_ms.get("view_state_build", 0.0),
            panel_draw_ms=self._section_ms.get("panel_draw", 0.0),
            upload_ms=self._section_ms.get("upload", 0.0),
            overlay_present_ms=self._section_ms.get("overlay_present", 0.0),
            surface_builds=self._counters.surface_builds,
            font_renders=self._counters.font_renders,
            row_cache_hits=self._counters.row_cache_hits,
            row_cache_misses=self._counters.row_cache_misses,
            upload_skipped=self._counters.upload_skipped,
            upload_partial=self._counters.upload_partial,
            upload_full=self._counters.upload_full,
            upload_partial_rects=self._counters.upload_partial_rects,
            texture_reallocs=self._counters.texture_reallocs,
            skipped=self._skipped,
            pm_fps=self._pm_fps,
        )

        line = _format_sample_line(sample)
        self.last_line = line

        self._frames_since_emit += 1
        should_emit = self._emit_next_frame or (
            self._frames_since_emit >= self.emit_interval_frames
        )
        if should_emit:
            print(line, flush=True)
            self._frames_since_emit = 0
            self._emit_next_frame = False

        self._reset_frame()
        return sample

    def toggle(self) -> None:
        self.enabled = not self.enabled
        if self.enabled:
            self._frames_since_emit = 0
            self._emit_next_frame = True
            self.last_line = "overlay: …"
            print(
                f"overlay profiler: on (logging to terminal every "
                f"{self.emit_interval_frames} frames; latest on panel when open)",
                flush=True,
            )
        else:
            self.last_line = None
            self._reset_frame()
            print("overlay profiler: off", flush=True)

    def _reset_frame(self) -> None:
        self._section_ms.clear()
        self._counters = OverlayDrawCounters()
        self._skipped = False
        self._pm_fps = None
