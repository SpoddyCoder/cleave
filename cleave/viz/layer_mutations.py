"""Public layer and preset mutation API for live tuning."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path

from cleave.blend_modes import BLEND_MODES
from cleave.config import clamp_beat_sensitivity, clamp_effect_pct
from cleave.config_schema.layers import (
    PRESET_SWITCHING_TRIGGERS,
    PresetSwitchingTrigger,
    clamp_easter_egg,
    preset_switching_mode_for_trigger,
    preset_switching_trigger_display,
)
from cleave.preset_library import PresetCollection
from cleave.preset_playlist import (
    is_top_level_browse_dir,
    playlist_at_collection,
    playlist_at_dir,
    preset_browse_floor,
    scan_preset_playlist,
)
from cleave.choice import step_choice
from cleave.viz.edit_history import EditHistory
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.preset_list_fill import needed_preset_count
from cleave.viz.preset_switching import layer_notification
from cleave.viz.session import BrowseSnapshot, TuningSession



class LayerMutations:
    """Layer, preset, and solo mutations used by the panel field manifest."""

    def __init__(
        self,
        session: TuningSession,
        *,
        preset_root: Path,
        duration_sec: float,
        get_layer_bindings: Callable[[], LiveLayerBindings | None],
        on_notification: Callable[[str], None],
        history: EditHistory | None = None,
        on_enter_each_clip: Callable[[str, str], None] | None = None,
        confirm_each_clip: Callable[[str, Callable[[], None]], None] | None = None,
    ) -> None:
        """``on_enter_each_clip`` gives a layer's clips presets when its
        presets start changing on each clip; it runs inside the undo step
        ``history`` records for the trigger change. ``confirm_each_clip`` runs
        the change it is given, after asking when that would lose something.
        """
        self.session = session
        self.preset_root = preset_root
        self.duration_sec = duration_sec
        self._get_layer_bindings = get_layer_bindings
        self._on_notification = on_notification
        self._history = history
        self._on_enter_each_clip = on_enter_each_clip
        self._confirm_each_clip = confirm_each_clip

    def _bindings(self) -> LiveLayerBindings | None:
        return self._get_layer_bindings()

    def _notify(self, message: str) -> None:
        self._on_notification(message)

    def _publish_browse_preset(self, slot: str) -> None:
        """Point the file row at the browse playlist's current preset."""
        layer = self.session.layers[slot]
        playlist = layer.playlist
        current = playlist.current
        if current is None:
            layer.auto_preset_path = None
        elif current.exists():
            layer.auto_preset_path = current.resolve()
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_change(slot, playlist)

    def step_directory(self, slot: str, *, forward: bool) -> None:
        layer = self.session.layers[slot]
        playlist = layer.playlist
        delta = 1 if forward else -1
        if playlist.step_sibling(delta, preset_root=self.preset_root):
            # Pack hop at preset_root: move the ascent floor with the playlist
            # so Backspace still works after diving into the new pack.
            if is_top_level_browse_dir(playlist.current_dir, self.preset_root):
                layer.browse_floor = playlist.current_dir.resolve()
            self._publish_browse_preset(slot)

    def jump_to_collection(self, slot: str, collection: PresetCollection) -> None:
        if self.session.layers[slot].playlist.enter_collection(collection):
            self._publish_browse_preset(slot)

    def can_enter_directory(self, slot: str) -> bool:
        """True when the layer's folder has a subfolder holding presets."""
        layer = self.session.layers[slot]
        return layer.playlist.directory_display(
            self.preset_root, browse_floor=layer.browse_floor
        ).can_go_down

    def browse_directory(self, slot: str, folder: Path) -> None:
        """Browse *folder* (a path crumb), playing its first preset."""
        layer = self.session.layers[slot]
        playlist = layer.playlist
        resolved = folder.resolve()
        if playlist.collection is None and resolved == playlist.current_dir.resolve():
            return
        playlist.replace_with(playlist_at_dir(resolved, catalog=playlist.catalog))
        layer.browse_floor = preset_browse_floor(resolved, self.preset_root)
        self._publish_browse_preset(slot)

    def enter_directory(self, slot: str) -> None:
        layer = self.session.layers[slot]
        playlist = layer.playlist
        if playlist.enter_child(self.preset_root):
            self._publish_browse_preset(slot)

    def parent_directory(self, slot: str) -> None:
        layer = self.session.layers[slot]
        playlist = layer.playlist
        if playlist.go_parent(
            self.preset_root, browse_floor=layer.browse_floor
        ):
            self._publish_browse_preset(slot)

    def browse_snapshot(self, slot: str) -> BrowseSnapshot:
        return self.session.layers[slot].browse_snapshot()

    def browse_to_preset(
        self,
        slot: str,
        path: Path,
        *,
        collection: PresetCollection | None = None,
    ) -> None:
        """Play *path*, browsing its folder (or *collection*) from now on."""
        layer = self.session.layers[slot]
        playlist = layer.playlist
        resolved = path.resolve()
        if collection is not None:
            target = playlist_at_collection(
                collection, current_dir=playlist.current_dir, catalog=playlist.catalog
            )
            if resolved not in target.paths:
                return
            target.index = target.paths.index(resolved)
        else:
            try:
                target = scan_preset_playlist(resolved, catalog=playlist.catalog)
            except (OSError, ValueError):
                return
            layer.browse_floor = preset_browse_floor(resolved, self.preset_root)
        playlist.replace_with(target)
        self._publish_browse_preset(slot)

    def restore_browse(self, slot: str, snapshot: BrowseSnapshot) -> None:
        """Put back the browse position and preset from *snapshot*."""
        self.session.layers[slot].restore_browse(snapshot)
        self._publish_browse_preset(slot)

    def step_preset(self, slot: str, *, forward: bool, large: bool) -> None:
        layer = self.session.layers[slot]
        playlist = layer.playlist
        if not playlist.paths:
            return
        if large:
            playlist.step_by(10 if forward else -10)
        elif forward:
            playlist.next()
        else:
            playlist.prev()
        self._publish_browse_preset(slot)

    def step_preset_switching_trigger(self, slot: str, *, delta: int) -> None:
        layer = self.session.layers[slot]
        self.set_preset_switching_trigger(
            slot,
            step_choice(
                PRESET_SWITCHING_TRIGGERS, layer.preset_switching_trigger, delta
            ),
        )

    def set_preset_switching_trigger(
        self, slot: str, trigger: PresetSwitchingTrigger
    ) -> None:
        layer = self.session.layers[slot]
        previous = layer.preset_switching_trigger
        if trigger == previous:
            return
        if trigger == "timeline" and self._confirm_each_clip is not None:
            self._confirm_each_clip(
                slot, lambda: self._apply_preset_switching_trigger(slot, trigger)
            )
            return
        self._apply_preset_switching_trigger(slot, trigger)

    def _apply_preset_switching_trigger(
        self, slot: str, trigger: PresetSwitchingTrigger
    ) -> None:
        layer = self.session.layers[slot]
        previous = layer.preset_switching_trigger
        # Entering or leaving "each clip" moves presets between the list and
        # the clips, so it is one undo step with them.
        follows_clips = "timeline" in (trigger, previous)
        recording = (
            self._history.recording(f"Change presets: {preset_switching_trigger_display(trigger)}")
            if follows_clips and self._history is not None
            else nullcontext()
        )
        with recording:
            layer.preset_switching_trigger = trigger
            layer.preset_switching = preset_switching_mode_for_trigger(
                layer.preset_switching_trigger
            )
            if previous == "off":
                # The preset chosen with switching off stays the layer's
                # preset; browsing from now on only previews.
                layer.layer_preset = layer.playlist.anchor
            if trigger == "timeline" and self._on_enter_each_clip is not None:
                self._on_enter_each_clip(slot, previous)
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_switching_change(slot)
        if trigger == "off" and layer.layer_preset is not None:
            # Switching off: the layer plays its own preset again.
            layer.playlist = scan_preset_playlist(
                layer.layer_preset, catalog=layer.playlist.catalog
            )
            self._publish_browse_preset(slot)

    def step_preset_duration(
        self, slot: str, *, forward: bool, large: bool = False
    ) -> None:
        layer = self.session.layers[slot]
        step = 10.0 if large else 1.0
        delta = step if forward else -step
        layer.preset_duration = max(5.0, min(300.0, layer.preset_duration + delta))
        if (
            layer.preset_switching_trigger != "timeline"
            and layer.preset_list
            and len(layer.preset_list)
            < needed_preset_count(
                song_duration_sec=self.duration_sec,
                preset_duration=layer.preset_duration,
                trigger=layer.preset_switching_trigger,
            )
        ):
            self._notify(
                layer_notification(
                    self.session.layer_z_order,
                    slot,
                    "Preset list may need more presets",
                )
            )
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_switching_change(slot)

    def step_soft_cut_duration(
        self, slot: str, *, forward: bool, large: bool = False
    ) -> None:
        layer = self.session.layers[slot]
        step = 10.0 if large else 1.0
        delta = step if forward else -step
        layer.soft_cut_duration = max(0.0, min(60.0, layer.soft_cut_duration + delta))
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_switching_change(slot)

    def step_easter_egg(self, slot: str, *, forward: bool, large: bool = False) -> None:
        layer = self.session.layers[slot]
        step = 0.1 if large else 0.01
        delta = step if forward else -step
        layer.easter_egg = clamp_easter_egg(layer.easter_egg + delta)
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_switching_change(slot)

    def step_preset_start_clean(self, slot: str, *, forward: bool) -> None:
        layer = self.session.layers[slot]
        if layer.preset_start_clean == forward:
            return
        layer.preset_start_clean = forward
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_switching_change(slot)

    def step_hard_cut_enabled(self, slot: str, *, forward: bool) -> None:
        layer = self.session.layers[slot]
        if layer.hard_cut_enabled == forward:
            return
        layer.hard_cut_enabled = forward
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_switching_change(slot)

    def step_hard_cut_duration(
        self, slot: str, *, forward: bool, large: bool = False
    ) -> None:
        layer = self.session.layers[slot]
        step = 10.0 if large else 1.0
        delta = step if forward else -step
        layer.hard_cut_duration = max(5.0, min(300.0, layer.hard_cut_duration + delta))
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_switching_change(slot)

    def set_hard_cut_sensitivity(self, slot: str, value: float) -> None:
        layer = self.session.layers[slot]
        layer.hard_cut_sensitivity = max(0.1, min(2.0, float(value)))
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_switching_change(slot)

    def step_blend(self, slot: str, *, delta: int) -> None:
        layer = self.session.layers[slot]
        layer.blend_mode = step_choice(
            BLEND_MODES, layer.blend_mode, delta
        )

    def step_stem(self, slot: str, *, delta: int) -> None:
        layer = self.session.layers[slot]
        stem = step_choice(self.session.stem_sources, layer.stem, delta)
        if stem == layer.stem:
            return
        layer.stem = stem
        layer.effects = {}
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_stem_change(slot, layer.stem)

    def enter_solo(self, slot: str) -> None:
        if self.session.solo_slot == slot:
            return
        self.session.solo_slot = slot
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_solo_change()

    def exit_solo(self, slot: str) -> None:
        if self.session.solo_slot != slot:
            return
        self.session.solo_slot = None
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_solo_change()

    def set_enabled(self, slot: str, enabled: bool) -> None:
        if self.session.timeline.enabled:
            self._notify("Timeline controls layer visibility")
            return
        layer = self.session.layers[slot]
        if layer.enabled == enabled:
            return
        layer.enabled = enabled
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_layer_enabled_change(slot, layer.enabled)

    def set_opacity(self, slot: str, pct: int) -> None:
        layer = self.session.layers[slot]
        layer.opacity_pct = max(0, min(100, pct))
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_opacity_change(slot, layer.opacity_pct)

    def set_effect(
        self, slot: str, effect_id: str, driver_slug: str, pct: int
    ) -> None:
        layer = self.session.layers[slot]
        clamped = clamp_effect_pct(pct)
        if clamped == 0:
            drivers = layer.effects.get(effect_id)
            if drivers is not None:
                drivers.pop(driver_slug, None)
                if not drivers:
                    layer.effects.pop(effect_id, None)
        else:
            layer.effects.setdefault(effect_id, {})[driver_slug] = clamped
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_opacity_change(slot, layer.opacity_pct)

    def set_beat(self, slot: str, value: float) -> None:
        layer = self.session.layers[slot]
        layer.beat_sensitivity = clamp_beat_sensitivity(value)
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_beat_change(slot, layer.beat_sensitivity)
