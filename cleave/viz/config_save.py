"""Save and quit orchestration for live tuning."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from cleave.config import CleaveConfig
from cleave.config_schema.persist import persisted_session_payload
from cleave.project import (
    save_compositor_settings,
    save_milkdrop_settings,
    save_render_settings,
    save_resolution_settings,
    save_song_markers,
)
from cleave.song_markers import SongMarker
from cleave.viz.modal import ModalHost, ModalKind
from cleave.viz.session import TuningSession


class PendingAction(Enum):
    """Why the live session should leave, once the app loop consumes it."""

    NONE = "none"
    EXIT = "exit"
    SWITCH = "switch"


@dataclass(frozen=True)
class ProjectSavedState:
    """Project values outside the viz YAML that Save writes to ``project.yaml``.

    Dirty tracking compares one of these with the one taken at the last save,
    so a new project setting needs only a field here and its line in
    ``write_project_saved_state``.
    """

    song_markers: tuple[SongMarker, ...]
    milkdrop_beat_sensitivity: float
    compositor_hdr: bool
    resolution_width: int
    resolution_height: int
    render_fps: int


def project_saved_state(session: TuningSession) -> ProjectSavedState:
    project = session.project
    return ProjectSavedState(
        song_markers=tuple(session.song_markers.markers),
        milkdrop_beat_sensitivity=project.milkdrop_beat_sensitivity,
        compositor_hdr=project.compositor_hdr,
        resolution_width=project.resolution.width,
        resolution_height=project.resolution.height,
        render_fps=project.render.fps,
    )


def write_project_saved_state(project_dir: Path, state: ProjectSavedState) -> None:
    """Write every ``ProjectSavedState`` field to ``project.yaml``."""
    save_song_markers(project_dir, state.song_markers)
    save_milkdrop_settings(project_dir, state.milkdrop_beat_sensitivity)
    save_compositor_settings(project_dir, state.compositor_hdr)
    save_resolution_settings(
        project_dir,
        width=state.resolution_width,
        height=state.resolution_height,
    )
    save_render_settings(project_dir, fps=state.render_fps)


class ConfigSaveController:
    """Dirty tracking, immediate Save, and one deferred leave (quit or switch).

    Viz YAML fields use ``persisted_session_payload``. Project-scoped
    values (``project.yaml``) are compared as one ``ProjectSavedState``;
    they flush on successful Save, not on each edit.

    ``config_dirty`` is what the window shows. Once the frame loop calls
    ``tick``, it is worked out on the first read after each tick and reused
    until the next, so it can trail an edit by a frame. Anything that acts
    on the answer (quit, project switch, mode change) calls
    ``compute_config_dirty``, which always compares the live session.
    """

    def __init__(
        self,
        session: TuningSession,
        cfg: CleaveConfig,
        modal_host: ModalHost,
        *,
        project_dir: Path | None = None,
        launch_config_path: Path | None = None,
        on_save_config: Callable[[Path], str | None] | None = None,
        on_notification: Callable[[str], None] | None = None,
        move_mode_signature: Callable[[], dict[str, list[str]] | None] | None = None,
    ) -> None:
        self.session = session
        self.cfg = cfg
        self._modal = modal_host
        self._project_dir = project_dir
        self._active_config_path = launch_config_path
        self._on_save_config = on_save_config
        self._on_notification = on_notification
        self._move_mode_signature = move_mode_signature

        self._saved_signature = self._persisted_signature()
        self._saved_project = project_saved_state(session)
        self._pending = PendingAction.NONE
        self._frame_cache_on = False
        self._frame_dirty: bool | None = None
        self._on_commit_save: list[Callable[[], None]] = []

    def add_on_commit_save(self, callback: Callable[[], None]) -> None:
        self._on_commit_save.append(callback)

    @property
    def active_config_path(self) -> Path | None:
        return self._active_config_path

    def _save_destination(self) -> Path:
        if self._active_config_path is not None:
            return self._active_config_path
        return self.cfg.config_path

    def tick(self) -> None:
        """Start a frame: the next ``config_dirty`` read compares again."""
        self._frame_cache_on = True
        self._frame_dirty = None

    @property
    def config_dirty(self) -> bool:
        if self._frame_cache_on and self._frame_dirty is not None:
            return self._frame_dirty
        return self.compute_config_dirty()

    def compute_config_dirty(self) -> bool:
        """Compare the live session with the saved baselines, right now."""
        dirty = self._differs_from_saved()
        if self._frame_cache_on:
            self._frame_dirty = dirty
        return dirty

    def _differs_from_saved(self) -> bool:
        return (
            project_saved_state(self.session) != self._saved_project
            or self._persisted_signature() != self._saved_signature
        )

    def clear_config_dirty(self) -> None:
        self._saved_signature = self._persisted_signature()
        self._saved_project = project_saved_state(self.session)
        self._frame_dirty = None

    def _commit_save(self) -> None:
        """Flush project.yaml fields (when available) and clear dirty baselines."""
        if self._project_dir is not None:
            write_project_saved_state(
                self._project_dir, project_saved_state(self.session)
            )
        self.clear_config_dirty()
        for callback in self._on_commit_save:
            callback()

    def _persisted_signature(self) -> str:
        payload = persisted_session_payload(self.cfg, self.session)
        if self._move_mode_signature is not None:
            override = self._move_mode_signature()
            if override is not None:
                payload = {**payload, **override}
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @property
    def pending_exit(self) -> bool:
        return self._pending is PendingAction.EXIT

    def consume_pending_exit(self) -> bool:
        """Return True once when quit was deferred (e.g. Don't save from unsaved dialog)."""
        if self._pending is PendingAction.EXIT:
            self._pending = PendingAction.NONE
            return True
        return False

    def consume_pending_switch(self) -> bool:
        """Return True once when a project switch was deferred."""
        if self._pending is PendingAction.SWITCH:
            self._pending = PendingAction.NONE
            return True
        return False

    def mark_pending_exit(self) -> None:
        """Ask the app loop to leave via ``consume_pending_exit``."""
        self._pending = PendingAction.EXIT

    def clear_pending_switch(self) -> None:
        """Drop a switch the session loop has not consumed."""
        if self._pending is PendingAction.SWITCH:
            self._pending = PendingAction.NONE

    def _unsaved_prompt_active(self) -> bool:
        view_state = self._modal.view_state()
        return view_state is not None and view_state.kind == ModalKind.UNSAVED_QUIT

    def try_quit(self) -> bool:
        """Handle a quit request. Return True when the app should exit now."""
        if self._pending is PendingAction.EXIT:
            return True
        if not self.compute_config_dirty():
            return True
        if not self._unsaved_prompt_active():
            self._modal.prompt_unsaved_quit(
                on_save=self._quit_save,
                on_discard=self._quit_discard,
            )
        return False

    def commit_switch(self, *, on_cancel: Callable[[], None] | None = None) -> bool:
        """Ask the app loop to switch projects.

        The open target stays with the caller. A clean project marks
        ``SWITCH`` now. A dirty project reuses the unsaved prompt; save and
        discard mark ``SWITCH``, and cancel leaves the pending action none.
        Returns False when a quit is already pending or the unsaved prompt is
        already up, so the caller can drop a target that was not committed.
        """
        if self._pending is PendingAction.EXIT:
            return False
        if self._unsaved_prompt_active():
            return False
        if self._pending is PendingAction.SWITCH:
            return True
        if not self.compute_config_dirty():
            self._pending = PendingAction.SWITCH
            return True
        self._modal.prompt_unsaved_quit(
            on_save=self._switch_save,
            on_discard=self._switch_discard,
            on_cancel=on_cancel,
        )
        return True

    def save(self) -> None:
        """Write the active creative YAML and flush project.yaml session fields."""
        target = self._save_destination()
        if self._on_save_config is not None:
            self._on_save_config(target)
        self._commit_save()
        self._show_save_notification("Saved")

    def _quit_save(self) -> None:
        self.save()
        self._pending = PendingAction.EXIT

    def _quit_discard(self) -> None:
        self._pending = PendingAction.EXIT

    def _switch_save(self) -> None:
        self.save()
        self._pending = PendingAction.SWITCH

    def _switch_discard(self) -> None:
        self._pending = PendingAction.SWITCH

    def _show_save_notification(self, message: str) -> None:
        print(message, file=sys.stderr)
        if self._on_notification is not None:
            self._on_notification(message)
