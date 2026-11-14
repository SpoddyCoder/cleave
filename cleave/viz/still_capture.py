"""Grab Still: save the composited preview frame as a PNG at project resolution.

The live preview is fitted to the window and its quality tier can shrink
lower layers, so a request runs the live pipeline at ``output`` quality
(``VisualiserResolutionSync.set_quality_override``) for a few frames, reads
the content framebuffer, and puts the setting back. The saved setting never
changes. Files go to ``<project>/captures/`` named for the project, the song
playhead when the still was asked for, and the next free id.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import pygame
from OpenGL.error import Error as GLError

from cleave.viz.modal import ModalHost, ModalLabeledLine
from cleave.viz.visualiser_resolution import VisualiserResolutionSync

CAPTURES_DIRNAME = "captures"
# Frames rendered at the capture size before the read, so the resized
# projectM and post-FX buffers hold a settled frame.
STILL_WARMUP_FRAMES = 3

_FAILED_MESSAGE = "Grab still failed"


class ContentFrameSource(Protocol):
    def read_content_rgba(self) -> tuple[bytes, int, int]: ...


def still_filename(slug: str, t_sec: float, index: int) -> str:
    """``<slug>_<MM>m<SS>s<mmm>_<NNN>.png`` for song time *t_sec*."""
    total_ms = max(0, round(t_sec * 1000.0))
    minutes, rest_ms = divmod(total_ms, 60_000)
    seconds, millis = divmod(rest_ms, 1000)
    return f"{slug}_{minutes:02d}m{seconds:02d}s{millis:03d}_{index:03d}.png"


def next_still_index(captures_dir: Path, slug: str) -> int:
    """One past the highest id among *slug*'s stills in *captures_dir* (from 1)."""
    pattern = re.compile(rf"^{re.escape(slug)}_\d+m\d{{2}}s\d{{3}}_(\d+)\.png$")
    highest = 0
    try:
        names = [entry.name for entry in captures_dir.iterdir()]
    except OSError:
        return 1
    for name in names:
        match = pattern.match(name)
        if match is not None:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def write_rgba_png(path: Path, data: bytes, width: int, height: int) -> None:
    surface = pygame.image.frombuffer(data, (width, height), "RGBA")
    pygame.image.save(surface, str(path))


class StillCaptureController:
    """Request a still; the live loop calls ``after_frame`` once per composited frame."""

    def __init__(
        self,
        resolution: VisualiserResolutionSync,
        modal_host: ModalHost,
        *,
        project_dir: Path | None,
        project_slug: str,
        playhead_sec: Callable[[], float],
        on_notification: Callable[[str], None],
        write_png: Callable[[Path, bytes, int, int], None] = write_rgba_png,
    ) -> None:
        self._resolution = resolution
        self._modal = modal_host
        self._project_dir = project_dir
        self._slug = project_slug
        self._playhead_sec = playhead_sec
        self._notify = on_notification
        self._write_png = write_png
        self._frames_left = 0
        self._t_sec = 0.0

    @property
    def available(self) -> bool:
        """False without a project folder to save into."""
        return self._project_dir is not None

    @property
    def busy(self) -> bool:
        return self._frames_left > 0

    def request(self) -> None:
        if self.busy or not self.available:
            return
        self._t_sec = self._playhead_sec()
        self._frames_left = STILL_WARMUP_FRAMES
        self._resolution.set_quality_override("output")

    def after_frame(self, source: ContentFrameSource) -> None:
        if not self.busy:
            return
        self._frames_left -= 1
        if self._frames_left > 0:
            return
        try:
            path = self._save(source)
        except (OSError, pygame.error, GLError) as exc:
            self._resolution.set_quality_override(None)
            self._prompt_error(str(exc))
            return
        self._resolution.set_quality_override(None)
        self._notify(f"Saved {CAPTURES_DIRNAME}/{path.name}")

    def _save(self, source: ContentFrameSource) -> Path:
        assert self._project_dir is not None
        data, width, height = source.read_content_rgba()
        captures = self._project_dir / CAPTURES_DIRNAME
        captures.mkdir(parents=True, exist_ok=True)
        index = next_still_index(captures, self._slug)
        path = captures / still_filename(self._slug, self._t_sec, index)
        self._write_png(path, data, width, height)
        return path

    def _prompt_error(self, detail: str) -> None:
        line = " ".join(detail.split())
        if len(line) > 96:
            line = line[:95] + "..."
        self._modal.prompt_notice(
            _FAILED_MESSAGE,
            labeled_lines=(ModalLabeledLine("error", line or "unknown error"),),
        )
