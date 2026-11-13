"""Preset favourite, blacklist, and cue-role curation for live tuning.

Curation flips flags in the preset library; preset files are never touched.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from cleave.cue_roles import CUE_ROLES, CueRole
from cleave.preset_library import PresetLibrary
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.modal import ModalHost, ModalOption
from cleave.viz.session import TuningSession

_CANCEL_LABEL = "Cancel"
_NO_ROLE_LABEL = "None"

NOTIFICATION_FAVOURITED_TEXT = "Favourited"
NOTIFICATION_UNFAVOURITED_TEXT = "Removed from favourites"
NOTIFICATION_UNBLACKLISTED_TEXT = "Removed from blacklist"

class PresetCurationController:
    """Route favourite / blacklist / role actions from the tuning panel.

    Each action undoes itself: F and B toggle, and the role choice includes None.
    """

    def __init__(
        self,
        session: TuningSession,
        modal_host: ModalHost,
        layer_bindings: LiveLayerBindings | None,
        library: PresetLibrary,
        *,
        on_notification: Callable[[str], None] | None = None,
    ) -> None:
        self.session = session
        self._modal = modal_host
        self._layer_bindings = layer_bindings
        self._library = library
        self._on_notification = on_notification

    def is_favourite(self, src: Path) -> bool:
        return self._library.is_favourite(src)

    def is_blacklisted(self, src: Path) -> bool:
        return self._library.is_blacklisted(src)

    def role_of(self, src: Path) -> CueRole | None:
        return self._library.role_of(src)

    def toggle_favourite(self, src: Path) -> None:
        """Favourite or unfavourite *src* at once (hotkey **f**)."""
        on = not self._library.is_favourite(src)
        self._library.set_favourite(src, on)
        self._refresh_collections()
        if self._on_notification is not None:
            self._on_notification(
                NOTIFICATION_FAVOURITED_TEXT if on else NOTIFICATION_UNFAVOURITED_TEXT
            )

    def toggle_blacklist(self, slot: str, src: Path) -> None:
        """Blacklist *src* after a confirm, or unblacklist it at once (hotkey **b**)."""
        if not self._library.is_blacklisted(src):
            self.prompt_blacklist(slot, src)
            return
        self._library.set_blacklisted(src, False)
        self._refresh_collections()
        if self._on_notification is not None:
            self._on_notification(NOTIFICATION_UNBLACKLISTED_TEXT)

    def prompt_blacklist(self, slot: str, src: Path) -> None:
        """Confirm, then hide *src* from browsing and picks."""
        if self._library.is_blacklisted(src):
            return
        self._lock_preset(slot)
        self._modal.prompt_confirm(
            f"Blacklist preset: {src.name}?",
            "Blacklist",
            lambda: self._confirm_blacklist(slot, src),
            lambda: self._unlock_preset(slot),
        )

    def prompt_cast(self, slot: str, src: Path) -> None:
        """Choose the cue role for *src*, or None (hotkey **c**)."""
        current = self._library.role_of(src)
        self._lock_preset(slot)
        dismiss = lambda: self._unlock_preset(slot)
        options: list[ModalOption] = [
            ModalOption(
                f"{role} (current)" if role == current else role,
                lambda r=role: self._confirm_cast(slot, src, r),
            )
            for role in CUE_ROLES
        ]
        if current is not None:
            options.append(
                ModalOption(
                    _NO_ROLE_LABEL, lambda: self._confirm_cast(slot, src, None)
                )
            )
        options.append(ModalOption(_CANCEL_LABEL, dismiss))
        self._modal.prompt_choice(
            f"Cast preset: {src.name}?", options, on_dismiss=dismiss
        )

    def _confirm_blacklist(self, slot: str, src: Path) -> None:
        try:
            self._library.set_blacklisted(src, True)
            playlist = self.session.layers[slot].playlist
            if playlist.collection is None and playlist.remove_preset(src):
                if self._layer_bindings is not None:
                    self._layer_bindings.on_preset_change(slot, playlist)
            self._refresh_collections()
        finally:
            self._unlock_preset(slot)

    def set_role(self, src: Path, role: CueRole | None) -> None:
        """Cast *src* as *role*, or clear its role with None."""
        if self._library.role_of(src) == role:
            return
        self._library.set_role(src, role)
        self._refresh_collections()
        self._rebuild_timeline_role_rotations()

    def _confirm_cast(self, slot: str, src: Path, role: CueRole | None) -> None:
        try:
            self.set_role(src, role)
        finally:
            self._unlock_preset(slot)

    def _refresh_collections(self) -> None:
        """Re-read membership for layers browsing a collection."""
        for layer_slot, layer in self.session.layers.items():
            if layer.playlist.refresh_collection():
                if self._layer_bindings is not None:
                    self._layer_bindings.on_preset_change(layer_slot, layer.playlist)

    def _rebuild_timeline_role_rotations(self) -> None:
        if self._layer_bindings is None:
            return
        for layer_slot, layer in self.session.layers.items():
            if layer.preset_switching == "on":
                self._layer_bindings.on_preset_switching_change(layer_slot)

    def _lock_preset(self, slot: str) -> None:
        if self._layer_bindings is not None:
            self._layer_bindings.lock_preset_for_modal(slot)

    def _unlock_preset(self, slot: str) -> None:
        if self._layer_bindings is not None:
            self._layer_bindings.unlock_preset_after_modal(slot)
