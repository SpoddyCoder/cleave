"""Save and quit orchestration for live tuning."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

from cleave.config import CleaveConfig
from cleave.config_schema.persist import persisted_session_payload
from cleave.project import (
    save_compositor_settings,
    save_milkdrop_settings,
    save_render_settings,
    save_song_markers,
)
from cleave.viz.modal import ModalHost, ModalKind
from cleave.viz.session import TuningSession


class ConfigSaveController:
    """Dirty tracking, immediate Save, and deferred quit.

    Viz YAML fields use ``persisted_session_payload``. Song markers,
    milkdrop beat sensitivity, compositor hdr, and render width/height/fps
    are project-scoped (``project.yaml``) and participate in dirty via
    separate baselines; they flush on successful Save, not on each edit.
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
        self._saved_song_markers = tuple(session.song_markers.markers)
        self._saved_milkdrop_beat = session.project.milkdrop_beat_sensitivity
        self._saved_compositor_hdr = session.project.compositor_hdr
        self._saved_render_width = session.project.render.width
        self._saved_render_height = session.project.render.height
        self._saved_render_fps = session.project.render.fps
        self._pending_exit = False
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

    @property
    def config_dirty(self) -> bool:
        return (
            self._persisted_signature() != self._saved_signature
            or tuple(self.session.song_markers.markers) != self._saved_song_markers
            or (
                self.session.project.milkdrop_beat_sensitivity
                != self._saved_milkdrop_beat
            )
            or self.session.project.compositor_hdr != self._saved_compositor_hdr
            or self.session.project.render.width != self._saved_render_width
            or self.session.project.render.height != self._saved_render_height
            or self.session.project.render.fps != self._saved_render_fps
        )

    def clear_config_dirty(self) -> None:
        self._saved_signature = self._persisted_signature()
        self._saved_song_markers = tuple(self.session.song_markers.markers)
        self._saved_milkdrop_beat = self.session.project.milkdrop_beat_sensitivity
        self._saved_compositor_hdr = self.session.project.compositor_hdr
        self._saved_render_width = self.session.project.render.width
        self._saved_render_height = self.session.project.render.height
        self._saved_render_fps = self.session.project.render.fps

    def _flush_song_markers(self) -> None:
        if self._project_dir is None:
            return
        save_song_markers(self._project_dir, self.session.song_markers.markers)

    def _flush_milkdrop(self) -> None:
        if self._project_dir is None:
            return
        save_milkdrop_settings(
            self._project_dir, self.session.project.milkdrop_beat_sensitivity
        )

    def _flush_compositor(self) -> None:
        if self._project_dir is None:
            return
        save_compositor_settings(
            self._project_dir, self.session.project.compositor_hdr
        )

    def _flush_render(self) -> None:
        if self._project_dir is None:
            return
        render = self.session.project.render
        save_render_settings(
            self._project_dir,
            width=render.width,
            height=render.height,
            fps=render.fps,
        )

    def _commit_save(self) -> None:
        """Flush project.yaml fields (when available) and clear dirty baselines."""
        self._flush_song_markers()
        self._flush_milkdrop()
        self._flush_compositor()
        self._flush_render()
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
        return self._pending_exit

    def consume_pending_exit(self) -> bool:
        """Return True once when quit was deferred (e.g. Don't save from unsaved dialog)."""
        if self._pending_exit:
            self._pending_exit = False
            return True
        return False

    def try_quit(self) -> bool:
        """Handle a quit request. Return True when the app should exit now."""
        if self._pending_exit:
            return True
        if not self.config_dirty:
            return True
        view_state = self._modal.view_state()
        if view_state is None or view_state.kind != ModalKind.UNSAVED_QUIT:
            self._modal.prompt_unsaved_quit(
                on_save=self._quit_save,
                on_discard=self._quit_discard,
            )
        return False

    def save(self) -> None:
        """Write the active creative YAML and flush project.yaml session fields."""
        target = self._save_destination()
        if self._on_save_config is not None:
            self._on_save_config(target)
        self._commit_save()
        self._show_save_notification("Saved")

    def _quit_save(self) -> None:
        self.save()
        self._pending_exit = True

    def _quit_discard(self) -> None:
        self._pending_exit = True

    def _show_save_notification(self, message: str) -> None:
        print(message, file=sys.stderr)
        if self._on_notification is not None:
            self._on_notification(message)
