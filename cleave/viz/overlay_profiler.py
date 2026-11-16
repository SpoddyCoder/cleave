"""Whole-frame timer for the live editor.

**F3** toggles it, and ``CLEAVE_OVERLAY_PROFILE=1`` starts with it on. Section
times are averaged over ``CLEAVE_OVERLAY_PROFILE_INTERVAL`` frames (default 30)
and shown in a panel over the visualiser (``profiler_panel.py``).

Sections nest: a section's time excludes the sections timed inside it, so the
rows add up to the frame, with the untimed remainder reported as Other.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

from cleave.viz.overlay_upload import UploadPlan

_DEFAULT_WINDOW_FRAMES = 30

# Section name to panel label, in frame order.
SECTION_LABELS: dict[str, str] = {
    "events": "Events",
    "tick": "Controller ticks",
    "layers": "Layer render",
    "composite": "Composite, post-FX",
    "strip_compose": "Strip compose",
    "strip_upload": "Strip upload",
    "ui_build": "ImGui build",
    "ui_render": "ImGui render",
    "flip": "Flip",
}


@dataclass(frozen=True)
class UploadCounts:
    """Timeline strip texture uploads over one averaging window."""

    skipped: int = 0
    partial: int = 0
    full: int = 0
    texture_reallocs: int = 0


@dataclass(frozen=True)
class FrameReport:
    """Averages over one window of frames. Times are milliseconds per frame."""

    frames: int
    frame_ms: float
    sections: tuple[tuple[str, float], ...]
    uploads: UploadCounts = UploadCounts()
    pm_fps: int | None = None

    @property
    def other_ms(self) -> float:
        """Frame time no section covers."""
        return max(0.0, self.frame_ms - sum(ms for _name, ms in self.sections))

    @property
    def fps(self) -> float:
        return 1000.0 / self.frame_ms if self.frame_ms > 0.0 else 0.0


def report_rows(report: FrameReport | None) -> list[tuple[str, str]]:
    """Panel rows as ``(label, value)``; a pending first window says so."""
    if report is None:
        return [("Frame", "measuring")]
    rows = [("Frame", f"{report.frame_ms:.2f} ms  {report.fps:.0f} fps")]
    for name, ms in report.sections:
        rows.append((SECTION_LABELS[name], f"{ms:.2f} ms"))
    rows.append(("Other", f"{report.other_ms:.2f} ms"))
    uploads = report.uploads
    upload_text = (
        f"skip {uploads.skipped}  part {uploads.partial}  full {uploads.full}"
    )
    if uploads.texture_reallocs:
        upload_text += f"  realloc {uploads.texture_reallocs}"
    rows.append((f"Strip uploads / {report.frames}", upload_text))
    if report.pm_fps is not None:
        rows.append(("projectM target", f"{report.pm_fps} fps"))
    return rows


@dataclass
class OverlayProfiler:
    enabled: bool
    window_frames: int = _DEFAULT_WINDOW_FRAMES
    report: FrameReport | None = field(default=None, init=False)
    _section_ms: dict[str, float] = field(default_factory=dict, init=False, repr=False)
    # Time spent in child sections, one entry per open section.
    _open: list[float] = field(default_factory=list, init=False, repr=False)
    _frames: int = field(default=0, init=False, repr=False)
    _window_start: float | None = field(default=None, init=False, repr=False)
    _uploads: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _pm_fps: int | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_env(cls) -> OverlayProfiler:
        enabled = os.environ.get("CLEAVE_OVERLAY_PROFILE", "") == "1"
        window = _DEFAULT_WINDOW_FRAMES
        raw_window = os.environ.get("CLEAVE_OVERLAY_PROFILE_INTERVAL")
        if raw_window is not None:
            window = max(1, int(raw_window))
        return cls(enabled=enabled, window_frames=window)

    def note_projectm_fps(self, target: int) -> None:
        self._pm_fps = target

    def note_upload_plan(self, plan: UploadPlan) -> None:
        if not self.enabled:
            return
        key = {"skip": "skipped", "partial": "partial", "full": "full"}.get(plan.mode)
        if key is not None:
            self._uploads[key] = self._uploads.get(key, 0) + 1

    def note_texture_reallocs(self, count: int) -> None:
        if self.enabled and count:
            self._uploads["texture_reallocs"] = (
                self._uploads.get("texture_reallocs", 0) + count
            )

    @contextmanager
    def time_section(self, name: str) -> Iterator[None]:
        if name not in SECTION_LABELS:
            raise ValueError(f"unknown frame timer section: {name!r}")
        if not self.enabled:
            yield
            return
        start = time.perf_counter()
        self._open.append(0.0)
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            inner_ms = self._open.pop()
            self._section_ms[name] = (
                self._section_ms.get(name, 0.0) + elapsed_ms - inner_ms
            )
            if self._open:
                self._open[-1] += elapsed_ms

    def end_frame(self) -> None:
        """Mark a frame boundary. Call once per frame, after the flip."""
        if not self.enabled:
            return
        now = time.perf_counter()
        if self._window_start is None:
            # First boundary since it was switched on: sections so far are a
            # partial frame.
            self._reset_window(now)
            return
        self._frames += 1
        if self._frames < self.window_frames:
            return
        frames = self._frames
        self.report = FrameReport(
            frames=frames,
            frame_ms=(now - self._window_start) * 1000.0 / frames,
            sections=tuple(
                (name, self._section_ms.get(name, 0.0) / frames)
                for name in SECTION_LABELS
            ),
            uploads=UploadCounts(**self._uploads),
            pm_fps=self._pm_fps,
        )
        self._reset_window(now)

    def toggle(self) -> None:
        self.enabled = not self.enabled
        self.report = None
        self._open.clear()
        self._reset_window(None)

    def _reset_window(self, start: float | None) -> None:
        self._window_start = start
        self._frames = 0
        self._section_ms.clear()
        self._uploads.clear()
