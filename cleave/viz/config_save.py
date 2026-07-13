"""Save and quit orchestration for live tuning."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

import pygame

from cleave.config import VIZ_CONFIG_FILENAME, CleaveConfig
from cleave.config_schema import persisted_session_payload
from cleave.project import save_song_markers
from cleave.viz.modal import ModalHost, ModalKind
from cleave.viz.session import TuningSession, allow_overwrite_for_path

_DEFAULT_SAVE_FILENAME = "unnamed-1.yaml"


class ConfigSaveController:
    """Dirty tracking, save dialogs, and deferred quit.

    Viz YAML fields use ``persisted_session_payload``. Song markers are
    project-scoped (``project.yaml``) and participate in dirty via a separate
    baseline of marker times; they flush on successful Save, not on each edit.
    """

    def __init__(
        self,
        session: TuningSession,
        cfg: CleaveConfig,
        modal_host: ModalHost,
        *,
        project_dir: Path | None = None,
        launch_config_path: Path | None = None,
        repo_root_example: Path | None = None,
        on_save_new_config: Callable[[], Path | None] | None = None,
        on_overwrite_config: Callable[[Path], str | None] | None = None,
        on_notification: Callable[[str], None] | None = None,
        move_mode_signature: Callable[[], dict[str, list[str]] | None] | None = None,
    ) -> None:
        self.session = session
        self.cfg = cfg
        self._modal = modal_host
        self._project_dir = project_dir
        self._active_config_path = launch_config_path
        self._repo_root_example = (
            repo_root_example
            if repo_root_example is not None
            else Path(VIZ_CONFIG_FILENAME)
        )
        self._on_save_new_config = on_save_new_config
        self._on_overwrite_config = on_overwrite_config
        self._on_notification = on_notification
        self._move_mode_signature = move_mode_signature

        self._saved_signature = self._persisted_signature()
        self._saved_song_markers = tuple(session.song_markers.times)
        self._pending_exit = False
        self._quit_after_save = False

    @property
    def active_config_path(self) -> Path | None:
        return self._active_config_path

    @property
    def config_dirty(self) -> bool:
        return (
            self._persisted_signature() != self._saved_signature
            or tuple(self.session.song_markers.times) != self._saved_song_markers
        )

    def clear_config_dirty(self) -> None:
        self._saved_signature = self._persisted_signature()
        self._saved_song_markers = tuple(self.session.song_markers.times)

    def _flush_song_markers(self) -> None:
        if self._project_dir is None:
            return
        save_song_markers(self._project_dir, self.session.song_markers.times)

    def _commit_save(self) -> None:
        """Flush project song markers (when available) and clear dirty baselines."""
        self._flush_song_markers()
        self.clear_config_dirty()

    def _persisted_signature(self) -> str:
        payload = persisted_session_payload(self.cfg, self.session)
        if self._move_mode_signature is not None:
            override = self._move_mode_signature()
            if override is not None:
                payload = {**payload, **override}
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def allow_overwrite(self) -> bool:
        return allow_overwrite_for_path(
            self._active_config_path,
            repo_root_example=self._repo_root_example,
        )

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

    def prompt_save(self) -> None:
        if not self.allow_overwrite():
            self._modal.prompt_save_as_new(
                on_save_as_new=self._trigger_save_new,
                on_dismiss=self._clear_quit_after_save,
            )
            return

        self._modal.prompt_save_choice(
            on_overwrite=self._prompt_overwrite,
            on_save_as_new=self._trigger_save_new,
            on_dismiss=self._clear_quit_after_save,
        )

    def _clear_quit_after_save(self) -> None:
        if self._quit_after_save:
            self._quit_after_save = False

    def _trigger_save_new(self) -> None:
        if self._on_save_new_config is not None:
            saved_path = self._on_save_new_config()
        else:
            saved_path = None
        if saved_path is None:
            filename = _DEFAULT_SAVE_FILENAME
        else:
            self._active_config_path = saved_path
            filename = saved_path.name
            self._commit_save()
        self._show_save_notification(f"Config saved to {filename}")
        self._finish_quit_after_save()

    def _quit_save(self) -> None:
        self._quit_after_save = True
        self.prompt_save()

    def _quit_discard(self) -> None:
        self._pending_exit = True

    def _finish_quit_after_save(self) -> None:
        if self._quit_after_save:
            self._quit_after_save = False
            self.clear_config_dirty()
            self._pending_exit = True

    def _prompt_overwrite(self) -> None:
        active_path = self._active_config_path
        basename = (
            active_path.name
            if active_path is not None
            else VIZ_CONFIG_FILENAME
        )
        message = f"Overwrite {basename}?"

        def on_confirm() -> None:
            target = active_path or Path(VIZ_CONFIG_FILENAME)
            if self._on_overwrite_config is not None:
                written = self._on_overwrite_config(target)
            else:
                written = basename
            if not written:
                written = basename
            self._commit_save()
            self._show_save_notification(f"Config overwritten: {written}")
            self._finish_quit_after_save()

        def on_cancel() -> None:
            self._clear_quit_after_save()

        self._modal.prompt_yes_no(
            message=message,
            on_confirm=on_confirm,
            on_cancel=on_cancel,
            cancel_label="CANCEL",
        )

    def _show_save_notification(self, message: str) -> None:
        print(message, file=sys.stderr)
        if self._on_notification is not None:
            self._on_notification(message)
