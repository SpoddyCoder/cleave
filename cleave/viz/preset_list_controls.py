"""User preset-list browsing, populate, and reorder for live tuning."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from cleave.preset_playlist import milk_files_in_dir
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.modal import ModalHost, ModalOption
from cleave.viz.preset_list_populate import (
    needed_preset_count,
    on_segment_populate_count,
    populate_from_cue_marker_roles,
    populate_from_directory,
    repopulate_preset_lists,
)
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.session import TuningSession
from cleave.viz.user_presets import (
    USER_PRESETS_DIRNAME,
    preset_list_item_display_name,
    resolve_user_preset_dest,
    user_preset_referenced_on_disk,
)


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
        get_active_config_path: Callable[[], Path | None] | None = None,
        on_focus_preset_item: Callable[[str, int], None] | None = None,
    ) -> None:
        self.session = session
        self.preset_root = preset_root
        self.project_dir = project_dir
        self.duration_sec = duration_sec
        self._modal = modal_host
        self._layer_bindings = layer_bindings
        self._on_notification = on_notification
        self._get_active_config_path = get_active_config_path
        self._on_focus_preset_item = on_focus_preset_item
        self.move_mode_preset: tuple[str, int] | None = None
        self._move_mode_original_preset_list: list[str] | None = None

    def resolve_file_path(
        self, slot: str, kind: RowKind, desc: RowDescriptor
    ) -> Path | None:
        layer = self.session.layers[slot]
        if kind == RowKind.TRACK_PRESET:
            return layer.playlist.current
        if kind == RowKind.TRACK_PRESET_LIST_ITEM:
            index = desc.preset_index
            if index is None or index < 0 or index >= len(layer.preset_list):
                return None
            return Path(layer.preset_list[index])
        return None

    def enter_move_mode(self, slot: str, index: int) -> None:
        layer = self.session.layers[slot]
        if index < 0 or index >= len(layer.preset_list):
            return
        self._move_mode_original_preset_list = list(layer.preset_list)
        self.move_mode_preset = (slot, index)

    def swap_item(self, direction: int) -> None:
        if self.move_mode_preset is None:
            return
        slot, index = self.move_mode_preset
        presets = self.session.layers[slot].preset_list
        target = index + direction
        if target < 0 or target >= len(presets):
            return
        presets[index], presets[target] = presets[target], presets[index]
        self.move_mode_preset = (slot, target)
        if self._on_focus_preset_item is not None:
            self._on_focus_preset_item(slot, target)

    def confirm_move_mode(self) -> None:
        if self.move_mode_preset is None:
            return
        slot, _index = self.move_mode_preset
        self.move_mode_preset = None
        self._move_mode_original_preset_list = None
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
        self.move_mode_preset = None
        self._move_mode_original_preset_list = None

    def repopulate(self) -> None:
        if self.project_dir is None:
            return
        repopulate_preset_lists(
            self.session,
            mode=self.session.timeline.timeline_preset_repopulate,
            project_dir=self.project_dir,
            preset_root=self.preset_root,
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
        options: list[ModalOption] = []
        layer = self.session.layers[slot]
        timeline_trigger = layer.preset_switching_trigger == "timeline"
        if timeline_trigger:
            populate_count = on_segment_populate_count(self.session, slot)
            options.append(
                ModalOption(
                    "Using Cue Marker Roles (random)",
                    action=lambda: self.confirm_populate(slot, "cue_roles"),
                )
            )
        else:
            needed = needed_preset_count(
                song_duration_sec=self.duration_sec,
                preset_duration=layer.preset_duration,
                trigger=layer.preset_switching_trigger,
            )
            available = len(milk_files_in_dir(layer.playlist.current_dir))
            populate_count = min(needed, available)
        options.extend(
            [
                ModalOption(
                    "From Current Directory (random)",
                    action=lambda: self.confirm_populate(slot, "directory_random"),
                ),
                ModalOption(
                    "From Current Directory (sequential)",
                    action=lambda: self.confirm_populate(
                        slot, "directory_sequential"
                    ),
                ),
            ]
        )
        options.append(
            ModalOption(
                "Cancel",
                action=lambda: self._unlock_preset_after_modal(slot),
            )
        )
        self._modal.prompt_choice(
            f"Populate the preset list with {populate_count} presets?",
            options,
            on_dismiss=lambda: self._unlock_preset_after_modal(slot),
        )

    def confirm_populate(self, slot: str, mode: str) -> None:
        try:
            if self.project_dir is None:
                return
            layer = self.session.layers[slot]
            timeline_trigger_disabled = (
                layer.preset_switching_trigger == "timeline"
                and not self.session.timeline.enabled
            )
            if mode in ("directory_random", "directory_sequential"):
                max_count: int | None = None
                if layer.preset_switching_trigger != "timeline":
                    max_count = needed_preset_count(
                        song_duration_sec=self.duration_sec,
                        preset_duration=layer.preset_duration,
                        trigger=layer.preset_switching_trigger,
                    )
                order = (
                    "sequential" if mode == "directory_sequential" else "random"
                )
                populate_from_directory(
                    self.session,
                    slot,
                    project_dir=self.project_dir,
                    max_count=max_count,
                    order=order,
                )
            else:
                populate_from_cue_marker_roles(
                    self.session,
                    slot,
                    project_dir=self.project_dir,
                    preset_root=self.preset_root,
                )
            layer.preset_list_expanded = True
            if self._layer_bindings is not None:
                self._layer_bindings.on_preset_switching_change(slot)
            count = len(layer.preset_list)
            if self._on_notification is not None:
                if timeline_trigger_disabled:
                    self._on_notification(
                        f"Populated {count} presets; "
                        "enable Render: TIMELINE to switch"
                    )
                else:
                    self._on_notification(f"Populated {count} presets")
        finally:
            self._unlock_preset_after_modal(slot)

    def add_current(self, slot: str) -> None:
        playlist = self.session.layers[slot].playlist
        if playlist.current is None:
            return
        src_path = playlist.current
        if self._layer_bindings is not None:
            self._layer_bindings.lock_preset_for_modal(slot)
        self._modal.prompt_yes_no(
            f"Add preset: {src_path.name}?",
            on_confirm=lambda: self.confirm_add(slot, src_path),
            on_cancel=lambda: self._unlock_preset_after_modal(slot),
        )

    def confirm_add(self, slot: str, src_path: Path) -> None:
        try:
            dest_dir = self._user_presets_dir()
            if dest_dir is None:
                return
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path, needs_copy = resolve_user_preset_dest(dest_dir, src_path)
            if needs_copy:
                shutil.copy2(src_path, dest_path)
            self.session.layers[slot].preset_list.append(str(dest_path.resolve()))
            if self._layer_bindings is not None:
                self._layer_bindings.on_preset_switching_change(slot)
        finally:
            self._unlock_preset_after_modal(slot)

    def prompt_delete(self, slot: str, index: int) -> None:
        layer = self.session.layers[slot]
        if index < 0 or index >= len(layer.preset_list):
            return
        label = preset_list_item_display_name(layer.preset_list, index)
        self._modal.prompt_yes_no(
            f"Remove preset: {label}?",
            on_confirm=lambda: self.confirm_delete(slot, index),
        )

    def confirm_delete(self, slot: str, index: int) -> None:
        layer = self.session.layers[slot]
        if index < 0 or index >= len(layer.preset_list):
            return
        removed = layer.preset_list.pop(index)
        removed_path = Path(removed).resolve()
        presets_dir = self._user_presets_dir()
        if presets_dir is not None:
            try:
                removed_path.relative_to(presets_dir.resolve())
            except ValueError:
                pass
            else:
                still_needed = self._preset_list_path_referenced(removed)
                if not still_needed and self.project_dir is not None:
                    skip_config = (
                        self._get_active_config_path()
                        if self._get_active_config_path is not None
                        else None
                    )
                    still_needed = user_preset_referenced_on_disk(
                        self.project_dir,
                        removed_path,
                        skip_config=skip_config,
                    )
                if not still_needed:
                    removed_path.unlink(missing_ok=True)
        if self._layer_bindings is not None:
            self._layer_bindings.on_preset_switching_change(slot)

    def _user_presets_dir(self) -> Path | None:
        if self.project_dir is None:
            return None
        return self.project_dir / USER_PRESETS_DIRNAME

    def _preset_list_path_referenced(self, path: str) -> bool:
        target = Path(path).resolve()
        for layer in self.session.layers.values():
            for other in layer.preset_list:
                if Path(other).resolve() == target:
                    return True
        return False

    def _unlock_preset_after_modal(self, slot: str) -> None:
        if self._layer_bindings is not None:
            self._layer_bindings.unlock_preset_after_modal(slot)
