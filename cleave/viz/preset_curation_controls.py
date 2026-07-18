"""Preset favourites and blacklist modal orchestration for live tuning."""

from __future__ import annotations

from pathlib import Path

from cleave.preset_curation import (
    PresetCurationIndex,
    blacklist_root,
    copy_to_favourites,
    curated_milk_src,
    delete_favourite_milk,
    favourites_root,
    list_destination_subdirs,
    list_restore_destination_subdirs,
    move_to_blacklist,
    relocate_curated_milk,
    resolve_blacklist_origin_dir,
    restore_from_blacklist,
    rewrite_user_preset_paths,
    scrub_user_preset_paths,
)
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.modal import ModalHost, ModalOption
from cleave.viz.session import TuningSession

_ROOT_DEST_LABEL = "(root)"
_CANCEL_LABEL = "Cancel"


def _path_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


class PresetCurationController:
    """Confirm and route favourite/blacklist actions from the tuning panel."""

    def __init__(
        self,
        session: TuningSession,
        preset_root: Path,
        modal_host: ModalHost,
        layer_bindings: LiveLayerBindings | None,
        index: PresetCurationIndex,
    ) -> None:
        self.session = session
        self._preset_root = preset_root
        self._modal = modal_host
        self._layer_bindings = layer_bindings
        self._index = index

    def prompt_restore(self, slot: str, src: Path) -> None:
        """Remove a favourite or restore a blacklisted preset (hotkey **r**)."""
        under_fav = _path_under(src, favourites_root(self._preset_root))
        under_bl = _path_under(src, blacklist_root(self._preset_root))
        if under_fav:
            self._prompt_remove_favourite(slot, src)
            return
        if under_bl:
            self._prompt_restore_blacklist(slot, src)
            return
        if src.name in self._index.favourites:
            self._prompt_remove_favourite(slot, src)
            return
        if src.name in self._index.blacklist:
            self._prompt_restore_blacklist(slot, src)

    def prompt_favourite(self, slot: str, src: Path) -> None:
        relocating = src.name in self._index.favourites
        self._lock_preset(slot)
        message = (
            f"Move favourite preset: {src.name}?"
            if relocating
            else f"Favourite preset: {src.name}?"
        )
        root = favourites_root(self._preset_root)
        subdirs = list_destination_subdirs(root)
        if not subdirs:
            self._modal.prompt_yes_no(
                message,
                on_confirm=lambda: self._confirm_favourite(
                    slot, src, root, relocating=relocating
                ),
                on_cancel=lambda: self._unlock_preset(slot),
            )
            return

        dismiss = lambda: self._unlock_preset(slot)
        options: list[ModalOption] = [
            ModalOption(
                _ROOT_DEST_LABEL,
                lambda: self._confirm_favourite(
                    slot, src, root, relocating=relocating
                ),
            ),
        ]
        for name in subdirs:
            dest_dir = root / name
            options.append(
                ModalOption(
                    name,
                    lambda dest=dest_dir: self._confirm_favourite(
                        slot, src, dest, relocating=relocating
                    ),
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
        relocating = src.name in self._index.blacklist
        self._lock_preset(slot)
        message = (
            f"Move blacklist preset: {src.name}?"
            if relocating
            else f"Blacklist preset: {src.name}?"
        )
        root = blacklist_root(self._preset_root)
        subdirs = list_destination_subdirs(root)
        if not subdirs:
            self._modal.prompt_yes_no(
                message,
                on_confirm=lambda: self._confirm_blacklist(
                    slot,
                    src,
                    root,
                    from_user_preset=from_user_preset,
                    relocating=relocating,
                ),
                on_cancel=lambda: self._unlock_preset(slot),
            )
            return

        dismiss = lambda: self._unlock_preset(slot)
        options: list[ModalOption] = [
            ModalOption(
                _ROOT_DEST_LABEL,
                lambda: self._confirm_blacklist(
                    slot,
                    src,
                    root,
                    from_user_preset=from_user_preset,
                    relocating=relocating,
                ),
            ),
        ]
        for name in subdirs:
            dest_dir = root / name
            options.append(
                ModalOption(
                    name,
                    lambda dest=dest_dir: self._confirm_blacklist(
                        slot,
                        src,
                        dest,
                        from_user_preset=from_user_preset,
                        relocating=relocating,
                    ),
                )
            )
        options.append(ModalOption(_CANCEL_LABEL, dismiss))
        self._modal.prompt_choice(message, options, on_dismiss=dismiss)

    def _confirm_favourite(
        self,
        slot: str,
        src: Path,
        dest_dir: Path,
        *,
        relocating: bool,
    ) -> None:
        try:
            if relocating:
                curated = curated_milk_src(favourites_root(self._preset_root), src)
                if curated is None:
                    return
                old = curated.resolve()
                new = relocate_curated_milk(
                    curated, dest_dir, with_textures=True
                ).resolve()
                if old != new:
                    self._rewrite_paths_after_relocate(old, new)
            else:
                self._index.mark_favourite(copy_to_favourites(src, dest_dir).name)
        finally:
            self._unlock_preset(slot)

    def _confirm_blacklist(
        self,
        slot: str,
        src: Path,
        dest_dir: Path,
        *,
        from_user_preset: bool,
        relocating: bool,
    ) -> None:
        try:
            if relocating:
                curated = curated_milk_src(blacklist_root(self._preset_root), src)
                if curated is None:
                    return
                old = curated.resolve()
                new = relocate_curated_milk(curated, dest_dir).resolve()
                if old != new:
                    self._rewrite_paths_after_relocate(old, new)
                return

            self._index.mark_blacklisted(
                move_to_blacklist(src, dest_dir, self._preset_root).name
            )
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

    def _prompt_remove_favourite(self, slot: str, src: Path) -> None:
        self._lock_preset(slot)
        self._modal.prompt_yes_no(
            f"Remove favourite: {src.name}?",
            on_confirm=lambda: self._confirm_remove_favourite(slot, src),
            on_cancel=lambda: self._unlock_preset(slot),
        )

    def _confirm_remove_favourite(self, slot: str, src: Path) -> None:
        try:
            deleted = delete_favourite_milk(self._preset_root, src)
            if deleted is not None:
                self._index.unmark_favourite(deleted.name)
                self._scrub_deleted_preset(deleted)
        finally:
            self._unlock_preset(slot)

    def _scrub_deleted_preset(self, removed: Path) -> None:
        """Drop ``removed`` from layer playlists and user preset lists."""
        for layer_slot, layer in self.session.layers.items():
            playlist = layer.playlist
            if playlist.remove_preset(removed):
                if self._layer_bindings is not None:
                    self._layer_bindings.on_preset_change(layer_slot, playlist)
        affected = scrub_user_preset_paths(self.session.layers, removed)
        if self._layer_bindings is not None:
            for affected_slot in affected:
                self._layer_bindings.on_preset_switching_change(affected_slot)

    def _prompt_restore_blacklist(self, slot: str, src: Path) -> None:
        self._lock_preset(slot)
        self._modal.prompt_yes_no(
            f"Restore blacklisted preset: {src.name}?",
            on_confirm=lambda: self._confirm_restore_blacklist(slot, src),
            on_cancel=lambda: self._unlock_preset(slot),
        )

    def _confirm_restore_blacklist(self, slot: str, src: Path) -> None:
        curated = curated_milk_src(blacklist_root(self._preset_root), src)
        if curated is None:
            self._unlock_preset(slot)
            return
        origin_dir = resolve_blacklist_origin_dir(self._preset_root, curated)
        if origin_dir is not None:
            try:
                restore_from_blacklist(curated, origin_dir)
                self._index.unmark_blacklisted(curated.name)
                self._scrub_deleted_preset(curated)
            finally:
                self._unlock_preset(slot)
            return
        self._prompt_restore_dest_choice(slot, curated)

    def _prompt_restore_dest_choice(self, slot: str, curated: Path) -> None:
        message = f"Restore blacklisted preset: {curated.name}?"
        subdirs = list_restore_destination_subdirs(self._preset_root)
        dismiss = lambda: self._unlock_preset(slot)
        options: list[ModalOption] = [
            ModalOption(
                _ROOT_DEST_LABEL,
                lambda: self._finish_restore_blacklist(
                    slot, curated, self._preset_root
                ),
            ),
        ]
        for name in subdirs:
            dest_dir = self._preset_root / name
            options.append(
                ModalOption(
                    name,
                    lambda dest=dest_dir: self._finish_restore_blacklist(
                        slot, curated, dest
                    ),
                )
            )
        options.append(ModalOption(_CANCEL_LABEL, dismiss))
        self._modal.prompt_choice(message, options, on_dismiss=dismiss)

    def _finish_restore_blacklist(
        self,
        slot: str,
        curated: Path,
        dest_dir: Path,
    ) -> None:
        try:
            restore_from_blacklist(curated, dest_dir)
            self._index.unmark_blacklisted(curated.name)
            self._scrub_deleted_preset(curated)
        finally:
            self._unlock_preset(slot)

    def _rewrite_paths_after_relocate(self, old: Path, new: Path) -> None:
        for layer_slot, layer in self.session.layers.items():
            playlist = layer.playlist
            if any(path.resolve() == old for path in playlist.paths):
                if playlist.remove_preset(old):
                    if self._layer_bindings is not None:
                        self._layer_bindings.on_preset_change(layer_slot, playlist)
        affected = rewrite_user_preset_paths(self.session.layers, old, new)
        if self._layer_bindings is not None:
            for affected_slot in affected:
                self._layer_bindings.on_preset_switching_change(affected_slot)

    def _lock_preset(self, slot: str) -> None:
        if self._layer_bindings is not None:
            self._layer_bindings.lock_preset_for_modal(slot)

    def _unlock_preset(self, slot: str) -> None:
        if self._layer_bindings is not None:
            self._layer_bindings.unlock_preset_after_modal(slot)
