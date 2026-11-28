"""Preset favourite, tag, blacklist, and cue-role curation for live tuning.

Curation flips flags in the preset library; preset files are never touched.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from cleave.cue_roles import CUE_ROLES, CueRole
from cleave.preset_library import PresetLibrary
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.modal import ButtonRole, ModalHost, ModalLabeledLine, ModalOption
from cleave.viz.session import TuningSession

_CANCEL_LABEL = "Cancel"
_NO_ROLE_LABEL = "None"
_NO_TAGS_LABEL = "none"
NEW_TAG_LABEL = "New tag…"

NOTIFICATION_FAVOURITED_TEXT = "Favourited"
NOTIFICATION_UNFAVOURITED_TEXT = "Removed from favourites"
NOTIFICATION_UNBLACKLISTED_TEXT = "Removed from blacklist"


def unfavourited_text(tags_removed: int) -> str:
    """``Removed from favourites``, naming how many tags went with it."""
    if tags_removed == 0:
        return NOTIFICATION_UNFAVOURITED_TEXT
    noun = "tag" if tags_removed == 1 else "tags"
    return f"{NOTIFICATION_UNFAVOURITED_TEXT} and {tags_removed} {noun}"


def tag_untag_label(tag: str) -> str:
    return f"Remove {tag}"

class PresetCurationController:
    """Route favourite / tag / blacklist / role actions from the tuning panel.

    Each action undoes itself: F, B, and each tag toggle, and the role choice
    includes None.
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

    def tags(self) -> tuple[str, ...]:
        return self._library.tags()

    def tags_of(self, src: Path) -> tuple[str, ...]:
        return self._library.tags_of(src)

    def _notify(self, text: str) -> None:
        if self._on_notification is not None:
            self._on_notification(text)

    def toggle_favourite(self, src: Path) -> None:
        """Favourite or unfavourite *src* at once (hotkey **f**).

        Unfavouriting also takes off the preset's tags.
        """
        on = not self._library.is_favourite(src)
        removed = self._library.set_favourite(src, on)
        self._refresh_collections()
        self._notify(NOTIFICATION_FAVOURITED_TEXT if on else unfavourited_text(removed))

    def toggle_tag(self, src: Path, tag: str) -> None:
        """Put *tag* on *src*, favouriting it, or take it off."""
        on = tag not in self._library.tags_of(src)
        was_favourite = self._library.is_favourite(src)
        self._library.set_tagged(src, tag, on)
        self._refresh_collections()
        if not on:
            self._notify(f"Removed tag {tag}")
        elif was_favourite:
            self._notify(f"Tagged {tag}")
        else:
            self._notify(f"Favourited and tagged {tag}")

    def prompt_new_tag(self, slot: str, src: Path) -> None:
        """Name a new tag, then put it on *src*."""
        self._lock_preset(slot)

        def validate(text: str) -> str | None:
            try:
                self._library.new_tag_name(text)
            except ValueError as exc:
                return str(exc)
            return None

        def confirm(text: str) -> None:
            try:
                tag = self._library.add_tag(text)
                self.toggle_tag(src, tag)
            finally:
                self._unlock_preset(slot)

        self._modal.prompt_text(
            "New tag",
            "",
            confirm,
            lambda: self._unlock_preset(slot),
            single_line=True,
            validate=validate,
        )

    def prompt_tag(self, slot: str, src: Path) -> None:
        """Put a tag on *src* or take one off, or make a new one (hotkey **t**).

        One button per tag; a tag the preset has reads *Remove <tag>*.
        """
        current = self._library.tags_of(src)
        self._lock_preset(slot)
        dismiss = lambda: self._unlock_preset(slot)

        def choose(tag: str) -> None:
            try:
                self.toggle_tag(src, tag)
            finally:
                self._unlock_preset(slot)

        def new_tag() -> None:
            self._unlock_preset(slot)
            self.prompt_new_tag(slot, src)

        options: list[ModalOption] = [
            ModalOption(
                tag_untag_label(tag) if tag in current else tag,
                lambda t=tag: choose(t),
            )
            for tag in self._library.tags()
        ]
        options.append(ModalOption(NEW_TAG_LABEL, new_tag))
        options.append(ModalOption(_CANCEL_LABEL, dismiss))
        self._modal.prompt_buttons(
            f"Tag preset: {src.name}?",
            options,
            on_dismiss=dismiss,
            labeled_lines=(
                ModalLabeledLine(
                    "tags", ", ".join(current) if current else _NO_TAGS_LABEL
                ),
            ),
        )

    def toggle_blacklist(self, slot: str, src: Path) -> None:
        """Blacklist *src* after a confirm, or unblacklist it at once (hotkey **b**)."""
        if not self._library.is_blacklisted(src):
            self.prompt_blacklist(slot, src)
            return
        self._library.set_blacklisted(src, False)
        self._refresh_collections()
        self._notify(NOTIFICATION_UNBLACKLISTED_TEXT)

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
        """Choose the cue role for *src*, or None (hotkey **c**).

        One button per role. The current role is filled and starts focused.
        """
        current = self._library.role_of(src)
        self._lock_preset(slot)
        dismiss = lambda: self._unlock_preset(slot)
        options: list[ModalOption] = [
            ModalOption(
                role,
                lambda r=role: self._confirm_cast(slot, src, r),
                ButtonRole.PRIMARY if role == current else ButtonRole.PLAIN,
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
        self._modal.prompt_buttons(
            f"Cast preset: {src.name}?",
            options,
            on_dismiss=dismiss,
            initial_focus_index=(
                0 if current is None else CUE_ROLES.index(current)
            ),
            labeled_lines=(
                ModalLabeledLine(
                    "role", _NO_ROLE_LABEL if current is None else current
                ),
            ),
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
