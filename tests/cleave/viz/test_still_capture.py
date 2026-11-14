"""Grab Still: file naming, save, and failure."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from cleave.viz.still_capture import (
    StillCaptureController,
    next_still_index,
    still_filename,
)


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
    modal = MagicMock()
    notices: list[str] = []
    writes: list[tuple[Path, int, int]] = []
    controller = StillCaptureController(
        modal,
        project_dir=project_dir,
        project_slug="song",
        playhead_sec=lambda: playhead,
        on_notification=notices.append,
        write_png=lambda path, _data, w, h: writes.append((path, w, h)),
    )
    return controller, modal, notices, writes


def test_request_saves_the_next_composited_frame(tmp_path: Path) -> None:
    controller, _modal, notices, writes = _controller(tmp_path)
    controller.request()
    assert controller.busy

    source = _Source()
    controller.after_frame(source)

    assert source.reads == 1
    assert not controller.busy
    expected = tmp_path / "captures" / "song_01m23s450_001.png"
    assert writes == [(expected, 2, 2)]
    assert notices == ["Saved captures/song_01m23s450_001.png"]
    controller.after_frame(source)
    assert source.reads == 1


def test_after_frame_without_a_request_does_nothing(tmp_path: Path) -> None:
    controller, _modal, _notices, writes = _controller(tmp_path)
    source = _Source()
    controller.after_frame(source)
    assert source.reads == 0
    assert writes == []


def test_failed_read_opens_a_notice(tmp_path: Path) -> None:
    controller, modal, notices, writes = _controller(tmp_path)
    controller.request()
    controller.after_frame(_Source(OSError("disk full")))
    assert not controller.busy
    assert writes == [] and notices == []
    modal.prompt_notice.assert_called_once()
    assert modal.prompt_notice.call_args.args[0] == "Grab still failed"


def test_no_project_folder_ignores_the_request() -> None:
    controller, *_ = _controller(None)
    assert not controller.available
    controller.request()
    assert not controller.busy
