"""Preset favourites and blacklist modal orchestration for live tuning."""

from __future__ import annotations

from pathlib import Path

from cleave.preset_curation import (
    blacklist_root,
    copy_to_favourites,
    favourites_root,
    list_destination_subdirs,
    move_to_blacklist,
    scrub_user_preset_paths,
)
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.modal import ModalHost, ModalOption
from cleave.viz.session import TuningSession

_ROOT_DEST_LABEL = "(root)"
_CANCEL_LABEL = "Cancel"


class PresetCurationController:
    """Confirm and route favourite/blacklist actions from the tuning panel."""

    def __init__(
        self,
        session: TuningSession,
        preset_root: Path,
        modal_host: ModalHost,
        layer_bindings: LiveLayerBindings | None,
    ) -> None:
        self.session = session
        self._preset_root = preset_root
        self._modal = modal_host
        self._layer_bindings = layer_bindings

    def prompt_favourite(self, slot: str, src: Path) -> None:
        self._lock_preset(slot)
        message = f"Favourite preset: {src.name}?"
        root = favourites_root(self._preset_root)
        subdirs = list_destination_subdirs(root)
        if not subdirs:
            self._modal.prompt_yes_no(
                message,
                on_confirm=lambda: self._confirm_favourite(slot, src, root),
                on_cancel=lambda: self._unlock_preset(slot),
            )
            return

        dismiss = lambda: self._unlock_preset(slot)
        options: list[ModalOption] = [
            ModalOption(
                _ROOT_DEST_LABEL,
                lambda: self._confirm_favourite(slot, src, root),
            ),
        ]
        for name in subdirs:
            dest_dir = root / name
            options.append(
                ModalOption(
                    name,
                    lambda dest=dest_dir: self._confirm_favourite(slot, src, dest),
                )
            )
        options.append(ModalOption(_CANCEL_LABEL, dismiss))
        self._modal.prompt_choice(message, options, on_dismiss=dismiss)

    def prompt_blacklist(
        self,
        slot: str,
        src: Path,
        *,
        from_user_preset: bool,
        user_preset_index: int | None,
    ) -> None:
        del user_preset_index  # reserved for hotkey wiring in a later todo
        self._lock_preset(slot)
        message = f"Blacklist preset: {src.name}?"
        root = blacklist_root(self._preset_root)
        subdirs = list_destination_subdirs(root)
        if not subdirs:
            self._modal.prompt_yes_no(
                message,
                on_confirm=lambda: self._confirm_blacklist(
                    slot, src, root, from_user_preset=from_user_preset
                ),
                on_cancel=lambda: self._unlock_preset(slot),
            )
            return

        dismiss = lambda: self._unlock_preset(slot)
        options: list[ModalOption] = [
            ModalOption(
                _ROOT_DEST_LABEL,
                lambda: self._confirm_blacklist(
                    slot, src, root, from_user_preset=from_user_preset
                ),
            ),
        ]
        for name in subdirs:
            dest_dir = root / name
            options.append(
                ModalOption(
                    name,
                    lambda dest=dest_dir: self._confirm_blacklist(
                        slot, src, dest, from_user_preset=from_user_preset
                    ),
                )
            )
        options.append(ModalOption(_CANCEL_LABEL, dismiss))
        self._modal.prompt_choice(message, options, on_dismiss=dismiss)

    def _confirm_favourite(self, slot: str, src: Path, dest_dir: Path) -> None:
        try:
            copy_to_favourites(src, dest_dir)
        finally:
            self._unlock_preset(slot)

    def _confirm_blacklist(
        self,
        slot: str,
        src: Path,
        dest_dir: Path,
        *,
        from_user_preset: bool,
    ) -> None:
        try:
            move_to_blacklist(src, dest_dir)
            playlist = self.session.layers[slot].playlist
            if not from_user_preset or (
                playlist.current is not None
                and playlist.current.resolve() == src.resolve()
            ):
                if playlist.remove_preset(src):
                    if self._layer_bindings is not None:
                        self._layer_bindings.on_preset_change(slot, playlist)
            affected = scrub_user_preset_paths(self.session.layers, src)
            if self._layer_bindings is not None:
                for affected_slot in affected:
                    self._layer_bindings.on_preset_switching_change(affected_slot)
        finally:
            self._unlock_preset(slot)

    def _lock_preset(self, slot: str) -> None:
        if self._layer_bindings is not None:
            self._layer_bindings.lock_preset_for_modal(slot)

    def _unlock_preset(self, slot: str) -> None:
        if self._layer_bindings is not None:
            self._layer_bindings.unlock_preset_after_modal(slot)
