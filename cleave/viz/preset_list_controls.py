"""Per-layer preset lists: browse, populate, reorder, and edit.

Every change to a list records one step in :class:`EditHistory`, scoped to
the layer, so Ctrl+Z puts it back. Removing an entry leaves its project copy
on disk so an undo can restore it; copies nothing refers to are removed when
the editor closes.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable
from contextlib import AbstractContextManager
from pathlib import Path

from cleave.preset_library import UNFILTERED_CATALOG, PresetCatalog
from cleave.preset_list_entry import PresetListEntry
from cleave.preset_playlist import scan_preset_playlist
from cleave.viz.edit_history import EditHistory, preset_list_scope
from cleave.viz.layer import StemLayer
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.modal import FormField, FormSpec, ModalHost
from cleave.preset_list_fill import needed_preset_count
from cleave.viz.clip_presets import is_each_clip
from cleave.viz.preset_list_populate import (
    browse_pool,
    catalog_has_role_presets,
    on_segment_populate_count,
    populate_from_cue_marker_roles,
    populate_from_directory,
    repopulate_preset_lists,
)
from cleave.viz.preset_switching import (
    layer_notification,
    playing_switching_preset_path,
    switching_list_index,
)
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.session import TuningSession
from cleave.viz.user_presets import (
    USER_PRESETS_DIRNAME,
    copy_with_dedup,
    preview_anchor,
)

PresetSource = PresetListEntry | Path



# Why an each-clip layer's list cannot grow or shrink: it holds its clips' presets.
EACH_CLIP_LIST_HINT = "Each clip holds one preset: add or delete clips on the timeline"

class PresetListController:
    """Mutations for per-layer user preset lists."""

    def __init__(
        self,
        session: TuningSession,
        preset_root: Path,
        project_dir: Path | None,
        duration_sec: float,
        modal_host: ModalHost,
        layer_bindings: LiveLayerBindings | None,
        *,
        on_notification: Callable[[str], None] | None = None,
        history: EditHistory | None = None,
        on_focus_preset_item: Callable[[str, int], None] | None = None,
        on_move_preset_selection: Callable[[str, int], None] | None = None,
        layers_by_slot: dict[str, StemLayer] | None = None,
        catalog: PresetCatalog = UNFILTERED_CATALOG,
    ) -> None:
        self.session = session
        self.preset_root = preset_root
        self._catalog = catalog
        # Populate's last source, by mode, for this session.
        self._last_populate_mode: str | None = None
        self.project_dir = project_dir
        self.duration_sec = duration_sec
        self._modal = modal_host
        self._layer_bindings = layer_bindings
        self._on_notification = on_notification
        self._history = history if history is not None else EditHistory(session)
        self._on_focus_preset_item = on_focus_preset_item
        self._on_move_preset_selection = on_move_preset_selection
        self._layers_by_slot = layers_by_slot
        self.move_mode_preset: tuple[str, int] | None = None
        self._move_mode_original_preset_list: list[PresetListEntry] | None = None

    def current_preset_path(self, slot: str) -> Path | None:
        """Playing auto-switch preset when set, otherwise the browse selection."""
        if isinstance(self._layers_by_slot, dict):
            stem = self._layers_by_slot.get(slot)
            if stem is not None:
                playing = playing_switching_preset_path(stem)
                if playing is not None:
                    return playing
        layer = self.session.layers[slot]
        if layer.auto_preset_path is not None:
            return layer.auto_preset_path
        return layer.playlist.current

    def resolve_file_path(
        self, slot: str, kind: RowKind, desc: RowDescriptor
    ) -> Path | None:
        layer = self.session.layers[slot]
        if kind == RowKind.TRACK_PRESET:
            return self.current_preset_path(slot)
        if kind == RowKind.TRACK_PRESET_LIST_ITEM:
            index = desc.preset_index
            if index is None or index < 0 or index >= len(layer.preset_list):
                return None
            return layer.preset_list[index].file
        return None

    def enter_move_mode(self, slot: str, index: int) -> None:
        layer = self.session.layers[slot]
        if index < 0 or index >= len(layer.preset_list):
            return
        self._move_mode_original_preset_list = list(layer.preset_list)
        self.move_mode_preset = (slot, index)
        self._history.begin("Move preset", scope=preset_list_scope(slot))

    def swap_item(self, direction: int) -> None:
        if self.move_mode_preset is None:
            return
        _slot, index = self.move_mode_preset
        self.move_item_to(index + direction)

    def move_item_to(self, target: int) -> None:
        """Move the item in move mode to *target*; out-of-range is ignored."""
        if self.move_mode_preset is None:
            return
        slot, index = self.move_mode_preset
        presets = self.session.layers[slot].preset_list
        if target == index or target < 0 or target >= len(presets):
            return
        presets.insert(target, presets.pop(index))
        self.move_mode_preset = (slot, target)
        if self._on_focus_preset_item is not None:
            self._on_focus_preset_item(slot, target)

    def move_item(self, slot: str, index: int, delta: int) -> None:
        """Move one item by *delta* places, outside move mode; out-of-range is ignored."""
        presets = self.session.layers[slot].preset_list
        target = index + delta
        if not 0 <= index < len(presets) or not 0 <= target < len(presets):
            return
        if target == index:
            return
        with self._record("Move preset", slot, merge_key=("preset_list.move", slot)):
            presets.insert(target, presets.pop(index))
        self.refresh_switching(slot)
        if self._on_focus_preset_item is not None:
            self._on_focus_preset_item(slot, target)

    def confirm_move_mode(self) -> None:
        if self.move_mode_preset is None:
            return
        slot, _index = self.move_mode_preset
        self.move_mode_preset = None
        self._move_mode_original_preset_list = None
        self._history.commit()
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_switching_change(slot)

    def cancel_move_mode(self) -> None:
        if (
            self.move_mode_preset is not None
            and self._move_mode_original_preset_list is not None
        ):
            slot, _index = self.move_mode_preset
            self.session.layers[slot].preset_list[:] = (
                self._move_mode_original_preset_list
            )
            self._history.cancel()
        self.move_mode_preset = None
        self._move_mode_original_preset_list = None

    def refresh_switching(self, slot: str) -> None:
        """Tell the live layer its preset list changed."""
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_switching_change(slot)

    def has_role_presets(self) -> bool:
        """Whether the preset library gives any preset a clip role."""
        return catalog_has_role_presets(self._catalog)

    def repopulate(self) -> None:
        if self.project_dir is None:
            return
        repopulate_preset_lists(
            self.session,
            mode=self.session.timeline.timeline_preset_repopulate,
            project_dir=self.project_dir,
            catalog=self._catalog,
        )
        if self._layer_bindings is None:
            return
        for slot in self.session.layer_z_order:
            if self.session.layers[slot].preset_switching == "on":
                self._layer_bindings.on_preset_switching_change(slot)

    def prompt_populate(self, slot: str) -> None:
        if self.project_dir is None:
            return
        if self._layer_bindings is not None:
            self._layer_bindings.lock_preset_for_modal(slot)
        layer = self.session.layers[slot]
        sources: list[tuple[str, str, str]] = []
        if layer.preset_switching_trigger == "timeline":
            populate_count = on_segment_populate_count(self.session, slot)
            if self.has_role_presets():
                sources.append(
                    (
                        "clip roles",
                        "cue_roles",
                        "one preset for each clip, picked at random from "
                        "presets with that clip's role.",
                    )
                )
        else:
            needed = needed_preset_count(
                song_duration_sec=self.duration_sec,
                preset_duration=layer.preset_duration,
                trigger=layer.preset_switching_trigger,
            )
            available = len(browse_pool(layer.playlist))
            populate_count = min(needed, available)
        if self.length_fixed(slot):
            body = (
                "Gives the layer's clip a new preset."
                if populate_count == 1
                else f"Gives each of the layer's {populate_count} clips a new preset."
            )
        else:
            noun = "1 preset" if populate_count == 1 else f"{populate_count} presets"
            body = f"Replaces the whole list with {noun}."
        sources.append(
            (
                "shuffled (current directory)",
                "directory_random",
                "presets from the layer's preset directory, shuffled.",
            )
        )
        sources.append(
            (
                "in order (current directory)",
                "directory_sequential",
                "presets from the layer's preset directory, in directory order.",
            )
        )
        self._modal.prompt_form(
            FormSpec(
                title="Populate preset list",
                body=body,
                fields=(
                    FormField(
                        "source",
                        "pick from",
                        tuple(label for label, _mode, _help in sources),
                        next(
                            (
                                index
                                for index, (_label, mode, _help) in enumerate(sources)
                                if mode == self._last_populate_mode
                            ),
                            0,
                        ),
                        help=("Where the new presets come from, and in what order.",),
                        option_help=tuple(help for _label, _mode, help in sources),
                        vertical=True,
                    ),
                ),
                confirm_label="Populate",
                on_confirm=lambda values: self._confirm_populate_source(
                    slot, sources[values["source"]][1]
                ),
                on_cancel=lambda: self._unlock_preset_after_modal(slot),
                help=(
                    "Replaces the layer's entire preset list; switching then cycles through the new one.",
                ),
            )
        )

    def _confirm_populate_source(self, slot: str, mode: str) -> None:
        self._last_populate_mode = mode
        self.confirm_populate(slot, mode)

    def confirm_populate(self, slot: str, mode: str) -> None:
        try:
            if self.project_dir is None:
                return
            layer = self.session.layers[slot]
            timeline_trigger_disabled = (
                layer.preset_switching_trigger == "timeline"
                and not self.session.timeline.enabled
            )
            with self._record("Populate preset list", slot):
                self._populate(slot, mode, self.project_dir)
            if self._layer_bindings is not None:
                self._layer_bindings.on_preset_switching_change(slot)
            count = len(layer.preset_list)
            if self._on_notification is not None:
                if timeline_trigger_disabled:
                    self._on_notification(
                        layer_notification(
                            self.session.layer_z_order,
                            slot,
                            f"Populated {count} presets; "
                            "enable Timeline to switch",
                        )
                    )
                else:
                    self._on_notification(
                        layer_notification(
                            self.session.layer_z_order,
                            slot,
                            f"Populated {count} presets",
                        )
                    )
        finally:
            self._unlock_preset_after_modal(slot)

    def _populate(self, slot: str, mode: str, project_dir: Path) -> None:
        layer = self.session.layers[slot]
        if mode in ("directory_random", "directory_sequential"):
            max_count: int | None = None
            if layer.preset_switching_trigger != "timeline":
                max_count = needed_preset_count(
                    song_duration_sec=self.duration_sec,
                    preset_duration=layer.preset_duration,
                    trigger=layer.preset_switching_trigger,
                )
            order = "sequential" if mode == "directory_sequential" else "random"
            populate_from_directory(
                self.session,
                slot,
                project_dir=project_dir,
                max_count=max_count,
                order=order,
            )
        else:
            populate_from_cue_marker_roles(
                self.session,
                slot,
                project_dir=project_dir,
                catalog=self._catalog,
            )

    def active_list_index(self, slot: str) -> int | None:
        """List entry scheduled to play now, or None when switching is not running."""
        if isinstance(self._layers_by_slot, dict):
            stem = self._layers_by_slot.get(slot)
            if stem is not None:
                return switching_list_index(stem)
        return self.session.layers[slot].switching_list_index

    def _previewing(self, slot: str) -> bool:
        if isinstance(self._layers_by_slot, dict):
            stem = self._layers_by_slot.get(slot)
            if stem is not None:
                return stem.switching_paused
        return self.session.layers[slot].switching_paused

    def resume(self, slot: str) -> None:
        """End the layer's preview. A selection on the layer's list moves to
        the scheduled entry, so the user sees where switching picked up."""
        if self._layer_bindings is None:
            return
        self._layer_bindings.on_switching_resume(slot)
        index = self.active_list_index(slot)
        if index is not None and self._on_move_preset_selection is not None:
            self._on_move_preset_selection(slot, index)

    def audition(self, slot: str, index: int) -> None:
        """Preview list entry *index*. The scheduled entry is not a preview:
        it does nothing while switching runs, and resumes while previewing."""
        layer = self.session.layers[slot]
        if index < 0 or index >= len(layer.preset_list):
            return
        if index == self.active_list_index(slot):
            if self._previewing(slot):
                self.resume(slot)
            return
        playlist = scan_preset_playlist(
            preview_anchor(layer.preset_list[index]),
            catalog=layer.playlist.catalog,
        )
        layer.playlist = playlist
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_change(slot, playlist)

    def add_current(self, slot: str) -> None:
        """Append the layer's current preset to the end of its list."""
        src_path = self.current_preset_path(slot)
        if src_path is None:
            return
        self.insert(
            slot,
            len(self.session.layers[slot].preset_list),
            src_path,
            label="Add preset",
            verb="Added",
        )

    def replace_with_current(self, slot: str, index: int) -> None:
        src_path = self.current_preset_path(slot)
        if src_path is not None:
            self.replace(slot, index, src_path)

    def insert_current_after(self, slot: str, index: int) -> None:
        src_path = self.current_preset_path(slot)
        if src_path is not None and self._valid(slot, index):
            self.insert(slot, index + 1, src_path)

    def replace(
        self,
        slot: str,
        index: int,
        source: PresetSource,
        *,
        label: str = "Replace preset",
        verb: str = "Replaced",
    ) -> bool:
        """Put *source* in place of entry *index*. False when nothing changed."""
        if not self._valid(slot, index):
            return False
        entry = self._adopt(source)
        if entry is None:
            return False
        with self._record(label, slot):
            self.session.layers[slot].preset_list[index] = entry
        self._after_edit(slot, index, f"{verb} preset: {entry.display_name}")
        return True

    def insert(
        self,
        slot: str,
        index: int,
        source: PresetSource,
        *,
        label: str = "Insert preset",
        verb: str = "Inserted",
    ) -> bool:
        """Insert *source* before entry *index* (the list length appends)."""
        presets = self.session.layers[slot].preset_list
        if not 0 <= index <= len(presets) or self._refuse_length_change(slot):
            return False
        entry = self._adopt(source)
        if entry is None:
            return False
        with self._record(label, slot):
            presets.insert(index, entry)
        self._after_edit(slot, index, f"{verb} preset: {entry.display_name}")
        return True

    def duplicate(self, slot: str, index: int) -> None:
        """Insert a second copy of entry *index* right after it."""
        if not self._valid(slot, index) or self._refuse_length_change(slot):
            return
        presets = self.session.layers[slot].preset_list
        entry = presets[index]
        with self._record("Duplicate preset", slot):
            presets.insert(index + 1, entry)
        self._after_edit(slot, index + 1, f"Duplicated preset: {entry.display_name}")

    def remove(
        self,
        slot: str,
        index: int,
        *,
        label: str = "Remove preset",
        verb: str = "Removed",
    ) -> None:
        """Take entry *index* out of the list. Undo puts it back."""
        if not self._valid(slot, index) or self._refuse_length_change(slot):
            return
        presets = self.session.layers[slot].preset_list
        with self._record(label, slot):
            removed = presets.pop(index)
        self.refresh_switching(slot)
        if presets and self._on_focus_preset_item is not None:
            self._on_focus_preset_item(slot, min(index, len(presets) - 1))
        self._notify(slot, f"{verb} preset: {removed.display_name}")

    def prompt_clear(self, slot: str) -> None:
        """Confirm, then empty the layer's preset list."""
        count = len(self.session.layers[slot].preset_list)
        if count == 0 or self._refuse_length_change(slot):
            return
        if self._layer_bindings is not None:
            self._layer_bindings.lock_preset_for_modal(slot)
        noun = "1 preset" if count == 1 else f"{count} presets"
        self._modal.prompt_confirm(
            "Clear preset list?",
            "Clear",
            lambda: self._confirm_clear(slot),
            lambda: self._unlock_preset_after_modal(slot),
            body=f"Removes all {noun} from the list. Undo puts them back.",
            destructive=True,
        )

    def _confirm_clear(self, slot: str) -> None:
        try:
            self.clear(slot)
        finally:
            self._unlock_preset_after_modal(slot)

    def clear(self, slot: str) -> None:
        """Empty the layer's preset list. Undo puts it back."""
        presets = self.session.layers[slot].preset_list
        if not presets or self._refuse_length_change(slot):
            return
        count = len(presets)
        with self._record("Clear preset list", slot):
            presets.clear()
        self.refresh_switching(slot)
        noun = "1 preset" if count == 1 else f"{count} presets"
        self._notify(slot, f"Cleared {noun}")

    def length_fixed(self, slot: str) -> bool:
        """True when the list holds one preset per clip, so entries cannot be added or removed."""
        return is_each_clip(self.session, slot)

    def _refuse_length_change(self, slot: str) -> bool:
        if not self.length_fixed(slot):
            return False
        self._notify(slot, EACH_CLIP_LIST_HINT)
        return True

    def entry(self, slot: str, index: int) -> PresetListEntry | None:
        if not self._valid(slot, index):
            return None
        return self.session.layers[slot].preset_list[index]

    def _valid(self, slot: str, index: int) -> bool:
        layer = self.session.layers.get(slot)
        return layer is not None and 0 <= index < len(layer.preset_list)

    def _adopt(self, source: PresetSource) -> PresetListEntry | None:
        """The list entry for *source*, copying it into this project when needed.

        An entry already in this project's ``presets/`` is used as is, so a
        pasted entry keeps its origin; anything else is copied in.
        """
        dest_dir = self._user_presets_dir()
        if dest_dir is None:
            return None
        if isinstance(source, Path):
            return copy_with_dedup(dest_dir, source)
        try:
            source.file.resolve().relative_to(dest_dir.resolve())
        except ValueError:
            copied = copy_with_dedup(dest_dir, source.file)
            return PresetListEntry(
                path=copied.path, source=source.source or copied.source
            )
        return source

    def _record(
        self, label: str, slot: str, *, merge_key: Hashable | None = None
    ) -> AbstractContextManager[None]:
        return self._history.recording(
            label, merge_key=merge_key, scope=preset_list_scope(slot)
        )

    def _after_edit(self, slot: str, index: int, message: str) -> None:
        self.refresh_switching(slot)
        if self._on_focus_preset_item is not None:
            self._on_focus_preset_item(slot, index)
        self._notify(slot, message)

    def _notify(self, slot: str, message: str) -> None:
        if self._on_notification is not None:
            self._on_notification(
                layer_notification(self.session.layer_z_order, slot, message)
            )

    def _user_presets_dir(self) -> Path | None:
        if self.project_dir is None:
            return None
        return self.project_dir / USER_PRESETS_DIRNAME

    def _unlock_preset_after_modal(self, slot: str) -> None:
        if self._layer_bindings is not None:
            self._layer_bindings.unlock_preset_after_modal(slot)
