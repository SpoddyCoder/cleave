"""One loading window, many editor sessions.

Cold start, an explicit play target, and File > New / Open all come through
here. The window closes once, when the user quits or cancels with nothing
left to open.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from cleave.open_target import OpenTarget, OpenTargetKind
from cleave.stems import StemSource
from cleave.viz.file_picker import PickerMode
from cleave.viz.loading import LoadingWindow

NEW_PROJECT_TITLE = "Creating project"
"""Progress dialog title while a new project's stems are split."""
RESEPARATE_PROGRESS_TITLE = "Re-separating stems"
"""Progress dialog title while an open project's stems are split again."""


def run_editor_sessions(
    window: LoadingWindow,
    target: OpenTarget | None,
    *,
    config: Path | None = None,
    high_quality: bool = False,
    beat_detection_stem: StemSource | None = None,
) -> None:
    """Separate when needed, launch, and repeat when the session switches project.

    ``target`` None starts at the cold-start picker. An audio target is stem-split
    on the loading window. A project target launches that directory. A switch
    request from the live session becomes the next target on the same window.
    """
    try:
        _run_sessions(
            window,
            target,
            config=config,
            high_quality=high_quality,
            beat_detection_stem=beat_detection_stem,
        )
    finally:
        if getattr(window, "video_quit", False) is not True:
            window.close()


def _run_sessions(
    window: LoadingWindow,
    target: OpenTarget | None,
    *,
    config: Path | None,
    high_quality: bool,
    beat_detection_stem: StemSource | None,
) -> None:
    from cleave.viz import continue_launch
    from cleave.viz.file_picker_host import run_file_picker, show_picker_error

    current = target
    picker_mode = PickerMode.COLD_START
    while True:
        if current is None:
            current = run_file_picker(window, mode=picker_mode)
            if current is None or window.quit_requested:
                return
        if current.kind is OpenTargetKind.AUDIO and current.stem_count is None:
            chosen = _ask_stem_count(window)
            if window.quit_requested:
                return
            if chosen is _CANCELLED:
                picker_mode = PickerMode.NEW_PROJECT
                current = None
                continue
            current = replace(current, stem_count=chosen)
        try:
            project_dir = _project_dir_for(
                window,
                current,
                high_quality=high_quality,
                beat_detection_stem=beat_detection_stem,
            )
            if project_dir is None:
                return
            request = continue_launch(window, project_dir, config=config)
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            if getattr(window, "video_quit", False) is True:
                raise
            if window.quit_requested:
                return
            if not show_picker_error(window, str(exc)):
                return
            picker_mode = _picker_mode_after_failure(current)
            current = None
            continue
        if isinstance(request, OpenTarget):
            current = request
            continue
        return


def _project_dir_for(
    window: LoadingWindow,
    target: OpenTarget,
    *,
    high_quality: bool,
    beat_detection_stem: StemSource | None,
) -> Path | None:
    """Return the project directory, or None when the user closed the window."""
    window.ensure_imgui()
    if target.kind is OpenTargetKind.PROJECT:
        return target.path
    from cleave.separate import run_separate

    reseparate = target.kind is OpenTargetKind.RESEPARATE
    title = RESEPARATE_PROGRESS_TITLE if reseparate else NEW_PROJECT_TITLE
    project_dir = run_separate(
        target.path,
        high_quality=high_quality,
        force=reseparate,
        stem_count=target.stem_count,
        beat_detection_stem=beat_detection_stem,
        on_progress=lambda message, fraction: window.update(
            title, message, fraction
        ),
    )
    if window.quit_requested:
        return None
    return project_dir


_CANCELLED = object()


def _ask_stem_count(window: LoadingWindow) -> object:
    """A new project's stem count, or ``_CANCELLED``.

    Without stem split installed there is nothing to choose; the split
    reports that itself, so the default count goes through.
    """
    from cleave.separate import stem_split_available
    from cleave.stems import DEFAULT_STEM_COUNT
    from cleave.viz.loading_modal import choose_stem_count

    if not stem_split_available():
        return DEFAULT_STEM_COUNT
    window.ensure_imgui()
    chosen = choose_stem_count(window)
    return _CANCELLED if chosen is None else chosen


def _picker_mode_after_failure(target: OpenTarget | None) -> PickerMode:
    """Picker mode to offer after a failed open.

    Audio returns to new-project, a project directory to open-project.
    A cold start that never accepted a target stays on cold start.
    """
    if target is None:
        return PickerMode.COLD_START
    if target.kind is OpenTargetKind.AUDIO:
        return PickerMode.NEW_PROJECT
    if target.kind in (OpenTargetKind.PROJECT, OpenTargetKind.RESEPARATE):
        return PickerMode.OPEN_PROJECT
    return PickerMode.COLD_START
