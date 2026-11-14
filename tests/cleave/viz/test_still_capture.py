"""Grab Still: file naming, the capture-quality override, save and failure."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

from cleave.viz.session import TuningSession
from cleave.viz.still_capture import (
    STILL_WARMUP_FRAMES,
    StillCaptureController,
    next_still_index,
    still_filename,
)
from cleave.viz.visualiser_resolution import VisualiserResolutionSync
from tests.support.viz import make_test_cfg


def test_still_filename_stamps_song_time_and_id() -> None:
    assert still_filename("song", 83.45, 3) == "song_01m23s450_003.png"
    assert still_filename("song", 0.0, 1) == "song_00m00s000_001.png"
    assert still_filename("song", 3725.0, 12) == "song_62m05s000_012.png"


def test_next_still_index_counts_only_this_projects_stills(tmp_path: Path) -> None:
    assert next_still_index(tmp_path / "missing", "song") == 1
    for name in (
        "song_00m01s000_001.png",
        "song_00m09s250_007.png",
        "other_00m01s000_042.png",
        "song_notes.txt",
    ):
        (tmp_path / name).write_bytes(b"")
    assert next_still_index(tmp_path, "song") == 8


class _Source:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.reads = 0

    def read_content_rgba(self) -> tuple[bytes, int, int]:
        self.reads += 1
        if self.error is not None:
            raise self.error
        return b"\x00" * (4 * 2 * 2), 2, 2


def _controller(project_dir: Path | None, playhead: float = 83.45):
    cfg = make_test_cfg(("layer_1",))
    cfg = replace(cfg, editor=replace(cfg.editor, preview_quality="balanced"))
    session = TuningSession(layer_z_order=[], layers={})
    session.project.resolution.width, session.project.resolution.height = (3840, 2160)
    apply = MagicMock()
    sync = VisualiserResolutionSync(session, cfg, apply)
    sync.note_draw_rect((0, 0, 1600, 900))
    sync.tick(0.0)
    apply.reset_mock()
    modal = MagicMock()
    notices: list[str] = []
    writes: list[tuple[Path, int, int]] = []
    controller = StillCaptureController(
        sync,
        modal,
        project_dir=project_dir,
        project_slug="song",
        playhead_sec=lambda: playhead,
        on_notification=notices.append,
        write_png=lambda path, _data, w, h: writes.append((path, w, h)),
    )
    return controller, sync, apply, modal, notices, writes


def test_request_runs_at_output_then_saves_and_restores(tmp_path: Path) -> None:
    controller, sync, apply, _modal, notices, writes = _controller(tmp_path)
    controller.request()
    assert controller.busy
    assert sync.preview_quality == "output"
    apply.assert_called_once_with((3840, 2160))

    source = _Source()
    for _ in range(STILL_WARMUP_FRAMES - 1):
        controller.after_frame(source)
    assert source.reads == 0
    controller.after_frame(source)

    assert source.reads == 1
    assert not controller.busy
    assert sync.preview_quality == "balanced"
    assert apply.call_args.args == (sync.target_size(),)
    expected = tmp_path / "captures" / "song_01m23s450_001.png"
    assert writes == [(expected, 2, 2)]
    assert notices == ["Saved captures/song_01m23s450_001.png"]


def test_after_frame_without_a_request_does_nothing(tmp_path: Path) -> None:
    controller, _sync, apply, _modal, _notices, writes = _controller(tmp_path)
    controller.after_frame(_Source())
    apply.assert_not_called()
    assert writes == []


def test_failed_read_opens_a_notice_and_restores_quality(tmp_path: Path) -> None:
    controller, sync, _apply, modal, notices, writes = _controller(tmp_path)
    controller.request()
    source = _Source(OSError("disk full"))
    for _ in range(STILL_WARMUP_FRAMES):
        controller.after_frame(source)
    assert sync.preview_quality == "balanced"
    assert not controller.busy
    assert writes == [] and notices == []
    modal.prompt_notice.assert_called_once()
    assert modal.prompt_notice.call_args.args[0] == "Grab still failed"


def test_no_project_folder_ignores_the_request() -> None:
    controller, sync, apply, *_ = _controller(None)
    assert not controller.available
    controller.request()
    assert not controller.busy
    apply.assert_not_called()
    assert sync.preview_quality == "balanced"
