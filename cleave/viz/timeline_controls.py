"""Keyboard input for the timeline panel overlay."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pygame

from cleave.blend_modes import BLEND_MODES, BlendMode
from cleave.cue_roles import CUE_ROLES, CueRole
from cleave.cut_types import CUT_TYPES, CutType
from cleave.timeline import (
    LEVEL_EDIT_MIN,
    LEVEL_EPS,
    LEVEL_STEP_LARGE,
    LEVEL_STEP_SMALL,
    SlotCue,
    canonicalize,
    cue_at_time,
    cue_editable_for_blend_role,
    empty_lane,
    levels_equal,
    navigable_cue_times,
    should_accept_toggle,
    snap_placement_time,
    update_lane_cue,
)
from cleave.viz.controls import SEEK_LONG, SEEK_SHORT, SEEK_TINY
from cleave.viz.session import TuningSession
from cleave.viz.key_repeat import KeyRepeatController, mod_ctrl, mod_shift
from cleave.viz.layer_visibility import (
    armed_recording_level,
    build_record_punch_cues,
    effective_layer_enabled,
    snapshot_monitor_from_output,
)
from cleave.viz.playback import PlaybackState, current_sec, seek, toggle_pause

_LAYER_KEY_INDEX: dict[int, int] = {
    pygame.K_1: 0,
    pygame.K_2: 1,
    pygame.K_3: 2,
    pygame.K_4: 3,
    pygame.K_5: 4,
    pygame.K_6: 5,
    pygame.K_7: 6,
    pygame.K_8: 7,
    pygame.K_KP1: 0,
    pygame.K_KP2: 1,
    pygame.K_KP3: 2,
    pygame.K_KP4: 3,
    pygame.K_KP5: 4,
    pygame.K_KP6: 5,
    pygame.K_KP7: 6,
    pygame.K_KP8: 7,
}


class TimelineControls:
    """Keyboard focus for the bottom timeline strip when the panel is open."""

    def __init__(
        self,
        session: TuningSession,
        playback: PlaybackState,
        duration_sec: float,
        *,
        on_visibility_change: Callable[[], None] | None = None,
        on_close: Callable[[], None] | None = None,
        on_exit_submenu: Callable[[], None] | None = None,
        on_seek: Callable[[float], None] | None = None,
        on_notification: Callable[[str], None] | None = None,
        beat_times: Sequence[float] = (),
        bar_times: Sequence[float] = (),
    ) -> None:
        self.session = session
        self.playback = playback
        self.duration_sec = duration_sec
        self._beat_times = tuple(beat_times)
        self._bar_times = tuple(bar_times)
        self._on_visibility_change = on_visibility_change
        self._on_close = on_close
        self._on_exit_submenu = on_exit_submenu
        self._on_seek = on_seek
        self._on_notification = on_notification
        self._last_toggle_t: dict[str, float] = {}
        self._key_repeat = KeyRepeatController()

    def _snap_placement(self, t_sec: float) -> float:
        return snap_placement_time(
            t_sec,
            self.session.timeline.placement_snap,
            beat_times=self._beat_times,
            bar_times=self._bar_times,
        )

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if event.key in (pygame.K_ESCAPE, pygame.K_t):
            if not self.session.timeline.recording:
                self._close_panel()
            return True

        if self.session.timeline.locked:
            # Locked: strip stays viewable/seekable and Space still toggles
            # transport. Cue/record mutations stay blocked.
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                self._do_seek(
                    event.key == pygame.K_RIGHT,
                    long=mod_ctrl(event.mod),
                    tiny=mod_shift(event.mod),
                )
                return True
            if not (event.key == pygame.K_SPACE and not mod_ctrl(event.mod)):
                return True

        if event.key == pygame.K_r:
            if self.session.timeline.recording:
                self._stop_record()
            else:
                self._start_record()
            return True

        if event.key == pygame.K_SPACE and mod_ctrl(event.mod):
            if self.session.timeline.recording:
                self._stop_record_and_pause()
            else:
                self._start_record()
            return True

        if event.key == pygame.K_SPACE:
            if self.session.timeline.recording and not self.playback.paused:
                self._stop_record_and_pause()
                return True
            was_paused = self.playback.paused
            toggle_pause(self.playback, self.duration_sec)
            tl = self.session.timeline
            if was_paused:
                tl.preview_active = False
                tl.monitor = {}
            else:
                t_sec = current_sec(self.playback, self.duration_sec)
                tl.monitor = snapshot_monitor_from_output(self.session, t_sec)
                tl.preview_active = True
            self._refresh_visibility()
            return True

        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self._do_seek(
                event.key == pygame.K_RIGHT,
                long=mod_ctrl(event.mod),
                tiny=mod_shift(event.mod),
            )
            return True

        if event.key in _LAYER_KEY_INDEX:
            tl = self.session.timeline
            if mod_ctrl(event.mod):
                if tl.recording:
                    slot = self._slot_for_layer_index(_LAYER_KEY_INDEX[event.key])
                    if slot is not None:
                        self._drop_hold_cue_at(
                            slot, current_sec(self.playback, self.duration_sec)
                        )
                return True

            if tl.recording:
                slot = self._slot_for_layer_index(_LAYER_KEY_INDEX[event.key])
                if slot is not None:
                    self._toggle_armed_layer_at(
                        slot, current_sec(self.playback, self.duration_sec)
                    )
                return True

            slot = self._slot_for_layer_index(_LAYER_KEY_INDEX[event.key])
            if slot is None:
                return True

            if self.playback.paused:
                self._toggle_paused_stem_visibility(slot)
                return True

            if slot in tl.override_slots:
                tl.override_visible[slot] = not tl.override_visible.get(slot, True)
                self._refresh_visibility()
            return True

        if event.key == pygame.K_RETURN and mod_shift(event.mod):
            if not self.session.timeline.recording:
                self._toggle_override_focused_row()
            return True

        if event.key == pygame.K_a:
            self._toggle_arm()
            return True

        if event.key == pygame.K_COMMA:
            if mod_ctrl(event.mod) or mod_shift(event.mod):
                self._nudge_selected_cue_level(
                    forward=False, large=mod_ctrl(event.mod)
                )
                if self._cue_edits_allowed():
                    self._key_repeat.on_keydown(
                        event.key,
                        event.mod,
                        on_repeat=lambda key, mod: self._nudge_selected_cue_level(
                            forward=False, large=mod_ctrl(mod)
                        ),
                    )
            else:
                self._step_selected_cue(forward=False)
            return True

        if event.key == pygame.K_PERIOD:
            if mod_ctrl(event.mod) or mod_shift(event.mod):
                self._nudge_selected_cue_level(
                    forward=True, large=mod_ctrl(event.mod)
                )
                if self._cue_edits_allowed():
                    self._key_repeat.on_keydown(
                        event.key,
                        event.mod,
                        on_repeat=lambda key, mod: self._nudge_selected_cue_level(
                            forward=True, large=mod_ctrl(mod)
                        ),
                    )
            else:
                self._step_selected_cue(forward=True)
            return True

        if event.key == pygame.K_b:
            self._cycle_selected_cue_blend()
            return True

        if event.key == pygame.K_o:
            self._cycle_selected_cue_role()
            return True

        if event.key == pygame.K_c:
            self._cycle_selected_cue_cut()
            return True

        return True

    def handle_keyup(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYUP:
            self._key_repeat.on_keyup(event.key)

    @property
    def key_repeat_armed(self) -> bool:
        return self._key_repeat.is_armed

    def tick(self, dt_sec: float) -> None:
        self._key_repeat.tick(dt_sec)

    def stop_recording(self) -> None:
        """Stop an in-progress timeline take without closing the panel."""
        self._stop_record()

    def _close_panel(self) -> None:
        if self._on_close is not None:
            self._on_close()

    def _notify(self, message: str) -> None:
        if self._on_notification is not None:
            self._on_notification(message)

    def _slot_for_layer_index(self, index: int) -> str | None:
        z_order = self.session.layer_z_order
        if index >= len(z_order):
            return None
        return z_order[index]

    def _focused_slot(self) -> str:
        return self.session.layer_z_order[self.session.timeline.focus_row]

    def _cue_edits_allowed(self) -> bool:
        tl = self.session.timeline
        return not tl.locked and not tl.recording

    def _step_selected_cue(self, *, forward: bool) -> None:
        if not self._cue_edits_allowed():
            return
        tl = self.session.timeline
        slot = self._focused_slot()
        lane = tl.lanes.get(slot) or empty_lane()
        times = navigable_cue_times(lane)
        if not times:
            return
        selected = tl.selected_cue_t.get(slot)
        if selected is None or selected not in times:
            playhead = current_sec(self.playback, self.duration_sec)
            nearest = min(times, key=lambda t: (abs(t - playhead), t))
            self._set_selected_cue(slot, nearest)
            return
        index = times.index(selected)
        if forward:
            index = min(index + 1, len(times) - 1)
        else:
            index = max(index - 1, 0)
        self._set_selected_cue(slot, times[index])

    def _set_selected_cue(self, slot: str, cue_t: float) -> None:
        tl = self.session.timeline
        if tl.selected_cue_t.get(slot) == cue_t:
            return
        tl.selected_cue_t[slot] = cue_t
        tl.selected_cue_flash_start_ms = pygame.time.get_ticks()

    def _selected_cue(self) -> tuple[str, SlotCue] | None:
        tl = self.session.timeline
        slot = self._focused_slot()
        selected = tl.selected_cue_t.get(slot)
        if selected is None:
            return None
        lane = tl.lanes.get(slot) or empty_lane()
        cue = cue_at_time(lane, selected)
        if cue is None:
            return None
        return slot, cue

    def _nudge_selected_cue_level(self, *, forward: bool, large: bool) -> None:
        """Adjust selected on-cue timeline opacity (multiplies into layer opacity)."""
        if not self._cue_edits_allowed():
            return
        selected = self._selected_cue()
        if selected is None:
            return
        slot, cue = selected
        if not cue_editable_for_blend_role(cue):
            return
        # Integer percent math matches the layer opacity fader (1% / 10%).
        step_pct = int(round(
            (LEVEL_STEP_LARGE if large else LEVEL_STEP_SMALL) * 100.0
        ))
        min_pct = int(round(LEVEL_EDIT_MIN * 100.0))
        pct = int(round(float(cue.level) * 100.0))
        new_pct = max(min_pct, min(100, pct + (step_pct if forward else -step_pct)))
        new_level = new_pct / 100.0
        if levels_equal(new_level, cue.level):
            return
        self._apply_selected_cue_update(
            slot,
            cue.t,
            blend=cue.blend,
            role=cue.role,
            cut=cue.cut,
            level=new_level,
        )

    def _cycle_selected_cue_blend(self) -> None:
        if not self._cue_edits_allowed():
            return
        selected = self._selected_cue()
        if selected is None:
            return
        slot, cue = selected
        if not cue_editable_for_blend_role(cue):
            return
        options: tuple[BlendMode | None, ...] = (None, *BLEND_MODES)
        try:
            index = options.index(cue.blend)
        except ValueError:
            index = 0
        index = (index + 1) % len(options)
        self._apply_selected_cue_update(
            slot, cue.t, blend=options[index], role=cue.role, cut=cue.cut
        )

    def _cycle_selected_cue_role(self) -> None:
        if not self._cue_edits_allowed():
            return
        selected = self._selected_cue()
        if selected is None:
            return
        slot, cue = selected
        if not cue_editable_for_blend_role(cue):
            return
        options: tuple[CueRole | None, ...] = (None, *CUE_ROLES)
        try:
            index = options.index(cue.role)
        except ValueError:
            index = 0
        index = (index + 1) % len(options)
        self._apply_selected_cue_update(
            slot, cue.t, blend=cue.blend, role=options[index], cut=cue.cut
        )

    def _cycle_selected_cue_cut(self) -> None:
        if not self._cue_edits_allowed():
            return
        selected = self._selected_cue()
        if selected is None:
            return
        slot, cue = selected
        current: CutType = cue.cut if cue.cut in CUT_TYPES else "none"
        index = (CUT_TYPES.index(current) + 1) % len(CUT_TYPES)
        self._apply_selected_cue_update(
            slot, cue.t, blend=cue.blend, role=cue.role, cut=CUT_TYPES[index]
        )

    def _apply_selected_cue_update(
        self,
        slot: str,
        cue_t: float,
        *,
        blend: BlendMode | None,
        role: CueRole | None,
        cut: CutType | None = None,
        level: float | None = None,
    ) -> None:
        tl = self.session.timeline
        lane = tl.lanes.get(slot) or empty_lane()
        updated = update_lane_cue(
            lane, cue_t, blend=blend, role=role, level=level, cut=cut
        )
        tl.lanes[slot] = updated
        if cue_t not in navigable_cue_times(updated):
            tl.selected_cue_t.pop(slot, None)
            tl.selected_cue_flash_start_ms = None

    def _toggle_arm(self) -> None:
        slot = self._focused_slot()
        tl = self.session.timeline
        armed = tl.armed_slots
        if slot in armed:
            armed.discard(slot)
            if tl.recording and slot in tl.record_baseline:
                self._commit_recording_slot(slot)
        else:
            armed.add(slot)
            if tl.recording:
                t_sec = current_sec(self.playback, self.duration_sec)
                tl.record_baseline[slot] = (
                    1.0
                    if effective_layer_enabled(self.session, slot, t_sec)
                    else 0.0
                )
                tl.record_slot_start_sec[slot] = self._snap_placement(t_sec)
                self._last_toggle_t.pop(slot, None)
                self._refresh_visibility()
        tl.arm_flash_start_ms[slot] = pygame.time.get_ticks()

    def _commit_recording_slot(self, slot: str) -> None:
        tl = self.session.timeline
        record_start = tl.record_start_sec
        if record_start is None or slot not in tl.record_baseline:
            return

        record_stop = self._snap_placement(
            current_sec(self.playback, self.duration_sec)
        )
        punch_end = self._snap_placement(
            max(record_stop, tl.record_high_water_mark or record_stop)
        )
        build_record_punch_cues(
            self.session,
            record_start,
            punch_end,
            slots={slot},
        )
        tl.record_baseline.pop(slot, None)
        tl.record_buffer.pop(slot, None)
        tl.record_slot_start_sec.pop(slot, None)
        self._last_toggle_t.pop(slot, None)

        if not tl.armed_slots:
            tl.recording = False
            tl.record_start_sec = None
            tl.record_buffer = {}
            tl.record_baseline = {}
            tl.record_slot_start_sec = {}
            tl.record_high_water_mark = None
            self._last_toggle_t = {}

        if self._on_visibility_change is not None:
            self._on_visibility_change()

    def _start_record(self) -> None:
        tl = self.session.timeline
        if not tl.armed_slots:
            self._notify("Arm at least one layer to record")
            return

        t_sec = current_sec(self.playback, self.duration_sec)
        snapped = self._snap_placement(t_sec)
        tl.record_baseline = {
            stem: (
                1.0
                if effective_layer_enabled(self.session, stem, t_sec)
                else 0.0
            )
            for stem in tl.armed_slots
        }
        tl.record_slot_start_sec = {stem: snapped for stem in tl.armed_slots}

        tl.preview_active = False
        tl.monitor = {}

        if self.playback.paused:
            toggle_pause(self.playback, self.duration_sec)

        tl.recording = True
        tl.record_start_sec = snapped
        tl.record_buffer = {}
        tl.record_high_water_mark = None
        self._last_toggle_t = {}

        self._refresh_visibility()

    def _stop_record(self) -> None:
        tl = self.session.timeline
        record_start = tl.record_start_sec
        if record_start is None:
            tl.recording = False
            tl.record_buffer = {}
            tl.record_baseline = {}
            tl.record_slot_start_sec = {}
            tl.record_high_water_mark = None
            return

        record_stop = self._snap_placement(
            current_sec(self.playback, self.duration_sec)
        )
        punch_end = self._snap_placement(
            max(record_stop, tl.record_high_water_mark or record_stop)
        )
        build_record_punch_cues(self.session, record_start, punch_end)
        tl.recording = False
        tl.record_start_sec = None
        tl.record_buffer = {}
        tl.record_baseline = {}
        tl.record_slot_start_sec = {}
        tl.record_high_water_mark = None
        self._last_toggle_t = {}

        if self._on_visibility_change is not None:
            self._on_visibility_change()

    def _stop_record_and_pause(self) -> None:
        tl = self.session.timeline
        tl.preview_active = False
        tl.monitor = {}
        self._stop_record()
        if not self.playback.paused:
            toggle_pause(self.playback, self.duration_sec)

    def _refresh_visibility(self) -> None:
        if self._on_visibility_change is not None:
            self._on_visibility_change()

    def _toggle_override_focused_row(self) -> None:
        slot = self._focused_slot()
        tl = self.session.timeline
        if slot in tl.override_slots:
            tl.override_slots.discard(slot)
            tl.override_visible.pop(slot, None)
        else:
            t_sec = current_sec(self.playback, self.duration_sec)
            tl.override_visible[slot] = effective_layer_enabled(
                self.session, slot, t_sec
            )
            tl.preview_active = False
            tl.monitor = {}
            tl.override_slots.add(slot)
        self._refresh_visibility()

    def _toggle_paused_stem_visibility(self, slot: str) -> None:
        tl = self.session.timeline
        if tl.preview_active:
            tl.monitor[slot] = not tl.monitor[slot]
        elif slot in tl.override_slots:
            tl.override_visible[slot] = not tl.override_visible.get(slot, True)
        else:
            t_sec = current_sec(self.playback, self.duration_sec)
            tl.override_visible[slot] = not effective_layer_enabled(
                self.session, slot, t_sec
            )
            tl.override_slots.add(slot)
        self._refresh_visibility()

    def _toggle_armed_layer_at(self, slot: str, t_sec: float) -> None:
        tl = self.session.timeline
        if slot not in tl.armed_slots or slot not in tl.record_baseline:
            return
        if not should_accept_toggle(self._last_toggle_t.get(slot), t_sec):
            return

        current_on = armed_recording_level(self.session, slot, t_sec) > LEVEL_EPS
        snapped = self._snap_placement(t_sec)
        tl.record_buffer.setdefault(slot, []).append(
            SlotCue(t=snapped, level=0.0 if current_on else 1.0)
        )
        self._last_toggle_t[slot] = t_sec

        if self._on_visibility_change is not None:
            self._on_visibility_change()

    def _drop_hold_cue_at(self, slot: str, t_sec: float) -> None:
        tl = self.session.timeline
        if slot not in tl.armed_slots or slot not in tl.record_baseline:
            return
        if not should_accept_toggle(self._last_toggle_t.get(slot), t_sec):
            return

        level = armed_recording_level(self.session, slot, t_sec)
        snapped = self._snap_placement(t_sec)
        tl.record_buffer.setdefault(slot, []).append(
            SlotCue(t=snapped, level=level, anchor=True)
        )
        self._last_toggle_t[slot] = t_sec

        if self._on_visibility_change is not None:
            self._on_visibility_change()

    def _fill_record_at_seek(self, old_t: float, new_t: float) -> None:
        tl = self.session.timeline
        skip_start = min(old_t, new_t)
        skip_end = max(old_t, new_t)
        for slot in list(tl.armed_slots):
            if slot not in tl.record_baseline:
                continue
            level = armed_recording_level(self.session, slot, old_t)
            buf = tl.record_buffer.get(slot, [])
            kept = [
                cue for cue in buf if not (skip_start <= cue.t <= skip_end)
            ]
            tl.record_buffer[slot] = canonicalize(
                tl.record_baseline[slot],
                kept + [SlotCue(t=skip_start, level=level)],
            )
            self._last_toggle_t.pop(slot, None)
        tl.record_high_water_mark = max(tl.record_high_water_mark or 0.0, old_t)
        if tl.record_start_sec is not None and new_t < tl.record_start_sec:
            prior_start = tl.record_start_sec
            tl.record_start_sec = new_t
            for slot, slot_start in list(tl.record_slot_start_sec.items()):
                if slot_start == prior_start:
                    tl.record_slot_start_sec[slot] = new_t

    def _do_seek(self, forward: bool, *, long: bool = False, tiny: bool = False) -> None:
        if long:
            delta_sec = SEEK_LONG
        elif tiny:
            delta_sec = SEEK_TINY
        else:
            delta_sec = SEEK_SHORT
        if not forward:
            delta_sec = -delta_sec
        if self.session.timeline.recording:
            old_t = current_sec(self.playback, self.duration_sec)
            new_t = max(0.0, min(self.duration_sec, old_t + delta_sec))
            self._fill_record_at_seek(old_t, new_t)
            self._refresh_visibility()
        if self._on_seek is not None:
            self._on_seek(delta_sec)
        else:
            seek(self.playback, delta_sec, self.duration_sec)
