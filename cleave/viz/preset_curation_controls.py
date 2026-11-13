"""Preset favourite, blacklist, and cue-role curation for live tuning.

Curation flips flags in the preset library; preset files are never touched.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from cleave.cue_roles import CUE_ROLES, CueRole
from cleave.preset_library import PresetLibrary
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.modal import ModalHost, ModalOption
from cleave.viz.session import TuningSession

_CANCEL_LABEL = "Cancel"
_NO_ROLE_LABEL = "None"

NOTIFICATION_FAVOURITED_TEXT = "Favourited"
NOTIFICATION_UNFAVOURITED_TEXT = "Removed from favourites"

_RestoreKind = Literal["favourite", "blacklist", "role"]


class PresetCurationController:
    """Route favourite / blacklist / cast / remove actions from the tuning panel."""

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

    def toggle_favourite(self, src: Path) -> None:
        """Favourite or unfavourite *src* at once (hotkey **f**)."""
        on = not self._library.is_favourite(src)
        self._library.set_favourite(src, on)
        self._refresh_collections()
        if self._on_notification is not None:
            self._on_notification(
                NOTIFICATION_FAVOURITED_TEXT if on else NOTIFICATION_UNFAVOURITED_TEXT
            )

    def prompt_blacklist(self, slot: str, src: Path) -> None:
        """Confirm, then hide *src* from browsing and picks (hotkey **b**)."""
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

    def can_restore(self, src: Path) -> bool:
        """True when *src* is favourited, cast, or blacklisted (what Remove undoes)."""
        return bool(self._memberships(src))

    def prompt_restore(self, slot: str, src: Path) -> None:
        """Remove *src* from favourites, its role, or the blacklist (hotkey **r**)."""
        memberships = self._memberships(src)
        if not memberships:
            return
        self._lock_preset(slot)
        dismiss = lambda: self._unlock_preset(slot)
        options = [
            ModalOption(
                self._membership_label(kind, src),
                lambda k=kind: self._confirm_remove(slot, src, k),
            )
            for kind in memberships
        ]
        options.append(ModalOption(_CANCEL_LABEL, dismiss))
        self._modal.prompt_choice(
            f"Remove from: {src.name}?", options, on_dismiss=dismiss
        )

    def _memberships(self, src: Path) -> list[_RestoreKind]:
        kinds: list[_RestoreKind] = []
        if self._library.is_favourite(src):
            kinds.append("favourite")
        if self._library.is_blacklisted(src):
            kinds.append("blacklist")
        if self._library.role_of(src) is not None:
            kinds.append("role")
        return kinds

    def _membership_label(self, kind: _RestoreKind, src: Path) -> str:
        if kind == "favourite":
            return "Favourites"
        if kind == "blacklist":
            return "Blacklist"
        return f"Cast ({self._library.role_of(src)})"

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

    def _confirm_cast(self, slot: str, src: Path, role: CueRole | None) -> None:
        try:
            self._library.set_role(src, role)
            self._refresh_collections()
            self._rebuild_timeline_role_rotations()
        finally:
            self._unlock_preset(slot)

    def _confirm_remove(self, slot: str, src: Path, kind: _RestoreKind) -> None:
        try:
            if kind == "favourite":
                self._library.set_favourite(src, False)
            elif kind == "blacklist":
                self._library.set_blacklisted(src, False)
            else:
                self._library.set_role(src, None)
            self._refresh_collections()
            if kind == "role":
                self._rebuild_timeline_role_rotations()
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
