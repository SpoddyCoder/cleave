"""Public layer and preset mutation API for live tuning."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cleave.blend_modes import BLEND_MODES
from cleave.config import clamp_beat_sensitivity, clamp_effect_pct
from cleave.config_schema import (
    PRESET_SWITCHING_MODES,
    PRESET_SWITCHING_TRIGGERS,
    clamp_easter_egg,
)
from cleave.extract import STEM_SOURCES
from cleave.preset_playlist import is_top_level_browse_dir
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.preset_list_populate import needed_preset_count
from cleave.viz.session import TuningSession

NOTIFICATION_TIMELINE_TRIGGER_DISABLED_TEXT = (
    "Timeline is disabled; enable Render: TIMELINE to switch presets"
)


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
    ) -> None:
        self.session = session
        self.preset_root = preset_root
        self.duration_sec = duration_sec
        self._get_layer_bindings = get_layer_bindings
        self._on_notification = on_notification

    def _bindings(self) -> LiveLayerBindings | None:
        return self._get_layer_bindings()

    def _notify(self, message: str) -> None:
        self._on_notification(message)

    def _warn_if_timeline_trigger_disabled(self, slot: str) -> bool:
        layer = self.session.layers[slot]
        if (
            layer.preset_switching == "on"
            and layer.preset_switching_trigger == "timeline"
            and not self.session.timeline.enabled
        ):
            self._notify(NOTIFICATION_TIMELINE_TRIGGER_DISABLED_TEXT)
            return True
        return False

    def step_directory(self, slot: str, *, forward: bool) -> None:
        layer = self.session.layers[slot]
        playlist = layer.playlist
        delta = 1 if forward else -1
        if playlist.step_sibling(delta, preset_root=self.preset_root):
            # Pack hop at preset_root: move the ascent floor with the playlist
            # so Ctrl+Left still works after diving into the new pack.
            if is_top_level_browse_dir(playlist.current_dir, self.preset_root):
                layer.browse_floor = playlist.current_dir.resolve()
            bindings = self._bindings()
            if bindings is not None:
                bindings.on_preset_change(slot, playlist)

    def enter_directory(self, slot: str) -> None:
        layer = self.session.layers[slot]
        playlist = layer.playlist
        if playlist.enter_child(self.preset_root):
            bindings = self._bindings()
            if bindings is not None:
                bindings.on_preset_change(slot, playlist)

    def parent_directory(self, slot: str) -> None:
        layer = self.session.layers[slot]
        playlist = layer.playlist
        if playlist.go_parent(
            self.preset_root, browse_floor=layer.browse_floor
        ):
            bindings = self._bindings()
            if bindings is not None:
                bindings.on_preset_change(slot, playlist)

    def step_preset(self, slot: str, *, forward: bool, ctrl: bool) -> None:
        layer = self.session.layers[slot]
        playlist = layer.playlist
        if not playlist.paths:
            return
        if ctrl:
            playlist.step_by(10 if forward else -10)
        elif forward:
            playlist.next()
        else:
            playlist.prev()
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_change(slot, playlist)

    def cycle_preset_switching(self, slot: str, *, forward: bool) -> None:
        layer = self.session.layers[slot]
        modes = PRESET_SWITCHING_MODES
        try:
            index = modes.index(layer.preset_switching)
        except ValueError:
            index = 0
        if forward:
            layer.preset_switching = modes[(index + 1) % len(modes)]
        else:
            layer.preset_switching = modes[(index - 1) % len(modes)]
        if layer.preset_switching == "on":
            layer.preset_list_expanded = True
        self._warn_if_timeline_trigger_disabled(slot)
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_switching_change(slot)

    def cycle_preset_switching_trigger(self, slot: str, *, forward: bool) -> None:
        layer = self.session.layers[slot]
        options = PRESET_SWITCHING_TRIGGERS
        try:
            index = options.index(layer.preset_switching_trigger)
        except ValueError:
            index = 0
        if forward:
            layer.preset_switching_trigger = options[(index + 1) % len(options)]
        else:
            layer.preset_switching_trigger = options[(index - 1) % len(options)]
        if not self._warn_if_timeline_trigger_disabled(slot) and layer.preset_list:
            self._notify("Preset list may need adjusting")
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_switching_change(slot)

    def step_preset_duration(
        self, slot: str, *, forward: bool, ctrl: bool = False
    ) -> None:
        layer = self.session.layers[slot]
        step = 10.0 if ctrl else 1.0
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
            self._notify("Preset list may need more presets")
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_switching_change(slot)

    def step_soft_cut_duration(
        self, slot: str, *, forward: bool, ctrl: bool = False
    ) -> None:
        layer = self.session.layers[slot]
        step = 10.0 if ctrl else 1.0
        delta = step if forward else -step
        layer.soft_cut_duration = max(0.0, min(60.0, layer.soft_cut_duration + delta))
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_switching_change(slot)

    def step_easter_egg(self, slot: str, *, forward: bool, ctrl: bool = False) -> None:
        layer = self.session.layers[slot]
        step = 0.1 if ctrl else 0.01
        delta = step if forward else -step
        layer.easter_egg = clamp_easter_egg(layer.easter_egg + delta)
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_switching_change(slot)

    def cycle_preset_start_clean(self, slot: str, *, forward: bool) -> None:
        del forward
        layer = self.session.layers[slot]
        layer.preset_start_clean = not layer.preset_start_clean
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_switching_change(slot)

    def cycle_hard_cut_enabled(self, slot: str, *, forward: bool) -> None:
        del forward
        layer = self.session.layers[slot]
        layer.hard_cut_enabled = not layer.hard_cut_enabled
        bindings = self._bindings()
        if bindings is not None:
            bindings.on_preset_switching_change(slot)

    def step_hard_cut_duration(
        self, slot: str, *, forward: bool, ctrl: bool = False
    ) -> None:
        layer = self.session.layers[slot]
        step = 10.0 if ctrl else 1.0
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

    def cycle_blend(self, slot: str, *, forward: bool) -> None:
        layer = self.session.layers[slot]
        try:
            index = BLEND_MODES.index(layer.blend_mode)
        except ValueError:
            index = 0
        if forward:
            layer.blend_mode = BLEND_MODES[(index + 1) % len(BLEND_MODES)]
        else:
            layer.blend_mode = BLEND_MODES[(index - 1) % len(BLEND_MODES)]

    def cycle_stem(self, slot: str, *, forward: bool) -> None:
        layer = self.session.layers[slot]
        try:
            index = STEM_SOURCES.index(layer.stem)
        except ValueError:
            index = 0
        if forward:
            layer.stem = STEM_SOURCES[(index + 1) % len(STEM_SOURCES)]
        else:
            layer.stem = STEM_SOURCES[(index - 1) % len(STEM_SOURCES)]
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
        if not enabled:
            layer.expanded = False
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
