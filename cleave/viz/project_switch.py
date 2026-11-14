"""In-session File > New and File > Open.

Holds the picker and the accepted target. Leaving the session is a pending
switch on :class:`ConfigSaveController`; this controller does not tear the
live session down.
"""

from __future__ import annotations

import pygame

from cleave.open_target import OpenTarget
from cleave.viz.config_save import ConfigSaveController
from cleave.viz.file_picker import (
    CANCEL_LABEL,
    FilePicker,
    PickerAction,
    PickerMode,
    PickerViewState,
)
from cleave.viz.file_picker_host import picker_action_for
from cleave.viz.file_picker_surface import PickerPointerIntent, apply_picker_pointer
from cleave.viz.key_repeat import KeyRepeatController
from cleave.viz.modal import ModalHost

_ARROW_KEYS = (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT)


class ProjectSwitchController:
    """File picker for switching the live project, plus the accepted target."""

    def __init__(
        self,
        config_save: ConfigSaveController,
        modal_host: ModalHost,
    ) -> None:
        self._config_save = config_save
        self._modal = modal_host
        self._picker: FilePicker | None = None
        self._accepted: OpenTarget | None = None
        self._repeat = KeyRepeatController()

    @property
    def active(self) -> bool:
        """True while the picker is on screen."""
        return self._picker is not None

    @property
    def key_repeat_armed(self) -> bool:
        return self._repeat.is_armed

    def view_state(self) -> PickerViewState | None:
        if self._picker is None:
            return None
        return self._picker.view_state()

    def prompt_open(self) -> None:
        """Browse for an existing project. Replaces a picker already up."""
        self._prompt(PickerMode.OPEN_PROJECT)

    def prompt_new(self) -> None:
        """Browse for audio to create a project. Replaces a picker already up."""
        self._prompt(PickerMode.NEW_PROJECT)

    def cancel(self) -> None:
        """Close the picker. The session stays; nothing is destroyed."""
        if self._picker is None:
            return
        self._picker.cancelled = True
        self._picker = None
        self._repeat.disarm()

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Apply one key. True when the picker consumed it."""
        picker = self._picker
        if picker is None or event.type != pygame.KEYDOWN:
            return False
        action = picker_action_for(event.key, event.mod)
        accepted: OpenTarget | None = None
        if action is not None:
            accepted = picker.handle(action)
        if picker.cancelled:
            self.cancel()
            return True
        if accepted is not None:
            self._finish_accept(accepted)
            return True
        if event.key in _ARROW_KEYS:
            self._repeat.on_keydown(
                event.key,
                event.mod,
                on_repeat=self._on_repeat,
            )
        return True

    def handle_keyup(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYUP:
            self._repeat.on_keyup(event.key)

    def tick(self, dt_sec: float) -> None:
        self._repeat.tick(dt_sec)

    def apply_pointer(self, intent: PickerPointerIntent | None) -> None:
        """Apply one recorded pointer intent. Does not return the target."""
        picker = self._picker
        if picker is None:
            return
        accepted = apply_picker_pointer(picker, intent)
        if picker.cancelled:
            self.cancel()
            return
        if accepted is not None:
            self._finish_accept(accepted)

    def take_accepted(self) -> OpenTarget | None:
        """Return the accepted target once. The pending switch is separate."""
        target = self._accepted
        self._accepted = None
        return target

    def _prompt(self, mode: PickerMode) -> None:
        if self._modal.active:
            return
        self._config_save.clear_pending_switch()
        self._accepted = None
        self._repeat.disarm()
        self._picker = FilePicker(mode=mode, cancel_label=CANCEL_LABEL)

    def _finish_accept(self, target: OpenTarget) -> None:
        self._accepted = target
        self._picker = None
        self._repeat.disarm()
        if not self._config_save.commit_switch(on_cancel=self._drop_accepted):
            self._drop_accepted()

    def _drop_accepted(self) -> None:
        self._accepted = None

    def _on_repeat(self, key: int, mod: int) -> None:
        picker = self._picker
        if picker is None:
            return
        action = picker_action_for(key, mod)
        if action is None or action is PickerAction.ACCEPT:
            return
        accepted = picker.handle(action)
        if accepted is not None:
            self._finish_accept(accepted)
