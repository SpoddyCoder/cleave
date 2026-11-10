"""Keyboard input for the timeline panel overlay."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pygame

from cleave.blend_modes import BLEND_MODES, BlendMode
from cleave.cue_roles import CUE_ROLES, CueRole
from cleave.cut_types import CUT_TYPES, CutType
from cleave.timeline import (
    LEVEL_EPS,
    SlotCue,
    canonicalize,
    empty_lane,
    navigable_cue_times,
    should_accept_toggle,
    snap_placement_time,
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
from cleave.viz.timeline_cue_edits import (
    cue_edits_allowed,
    cue_selection_allowed,
    nudge_cue_level,
    select_cue,
    selected_cue,
    set_cue_blend,
    set_cue_cut,
    set_cue_role,
    step_cue_selection,
)

def _next_option(options: tuple, current: object) -> object:
    """Option after *current*, wrapping; the first when *current* is not listed."""
    try:
        index = options.index(current)
    except ValueError:
        index = 0
    return options[(index + 1) % len(options)]


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
        on_focus_row: Callable[[int], None] | None = None,
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
        self._on_focus_row = on_focus_row
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
            bar_phase=self.session.timeline.bar_phase_offset,
        )

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_ESCAPE:
            if not self.session.timeline.recording:
                self._close_panel()
            return True

        if event.key in (pygame.K_UP, pygame.K_DOWN):
            delta = -1 if event.key == pygame.K_UP else 1
            self._step_focus_row(delta)
            self._key_repeat.on_keydown(
                event.key,
                event.mod,
                accel=False,
                on_repeat=lambda key, _mod: self._step_focus_row(
                    -1 if key == pygame.K_UP else 1
                ),
            )
            return True

        if self.session.timeline.locked:
            # Locked: strip stays viewable; Left/Right select cues, Enter seeks
            # to the selected cue, and Space still toggles transport. Cue/record
            # mutations stay blocked.
            locked_allowed = event.key in (pygame.K_LEFT, pygame.K_RIGHT)
            if event.key == pygame.K_RETURN and not mod_shift(event.mod):
                locked_allowed = True
            if event.key == pygame.K_SPACE and not mod_ctrl(event.mod):
                locked_allowed = True
            if not locked_allowed:
                return True

        if event.key == pygame.K_r:
            self.toggle_record()
            return True

        if event.key == pygame.K_SPACE and mod_ctrl(event.mod):
            if self.session.timeline.recording:
                self._stop_record_and_pause()
            else:
                self._start_record()
            return True

        if event.key == pygame.K_SPACE:
            self.toggle_transport()
            return True

        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            forward = event.key == pygame.K_RIGHT
            if self.session.timeline.recording:
                self.seek_step(forward)
            else:
                self._step_selected_cue(forward=forward)
                self._key_repeat.on_keydown(
                    event.key,
                    event.mod,
                    accel=False,
                    on_repeat=lambda key, _mod: self._step_selected_cue(
                        forward=key == pygame.K_RIGHT
                    ),
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

            slot = self._slot_for_layer_index(_LAYER_KEY_INDEX[event.key])
            if slot is not None:
                self._toggle_slot_visibility(slot)
            return True

        if event.key == pygame.K_RETURN and mod_shift(event.mod):
            if not self.session.timeline.recording:
                self._toggle_override_focused_row()
            return True

        if event.key == pygame.K_RETURN:
            if not self.session.timeline.recording:
                self._seek_to_selected_cue()
            return True

        if event.key == pygame.K_a:
            self._toggle_arm(self._focused_slot())
            return True

        if event.key == pygame.K_COMMA:
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
            return True

        if event.key == pygame.K_PERIOD:
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

    def arm_key_repeat(
        self,
        key: int,
        mod: int,
        *,
        on_repeat: Callable[[int, int], None],
        accel: bool = True,
    ) -> None:
        self._key_repeat.on_keydown(key, mod, on_repeat=on_repeat, accel=accel)

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

    def _step_focus_row(self, delta: int) -> None:
        """Move the strip lane within ``layer_z_order``. Does not wrap."""
        count = len(self.session.layer_z_order)
        if count <= 0:
            return
        row = self.session.timeline.focus_row
        if row < 0:
            row = 0
        elif row >= count:
            row = count - 1
        nxt = row + delta
        if nxt < 0:
            nxt = 0
        elif nxt >= count:
            nxt = count - 1
        if nxt == self.session.timeline.focus_row:
            return
        if self._on_focus_row is not None:
            self._on_focus_row(nxt)
            return
        self.session.timeline.focus_row = nxt

    def focus_row(self, row: int) -> None:
        """Put the strip lane on *row* (clamped), as a pointer click does."""
        count = len(self.session.layer_z_order)
        if count <= 0:
            return
        row = max(0, min(count - 1, row))
        if self._on_focus_row is not None:
            self._on_focus_row(row)
            return
        self.session.timeline.focus_row = row

    def select_cue_near(self, slot: str, t_sec: float, tolerance_sec: float) -> bool:
        """Select the cue on *slot* nearest *t_sec* within *tolerance_sec*."""
        if not cue_selection_allowed(self.session):
            return False
        times = navigable_cue_times(self.session.timeline.lanes.get(slot) or empty_lane())
        if not times:
            return False
        nearest = min(times, key=lambda t: abs(t - t_sec))
        if abs(nearest - t_sec) > tolerance_sec:
            return False
        select_cue(self.session, slot, nearest)
        return True

    def toggle_transport(self) -> None:
        """Play or pause (Space). Pausing while recording stops the take first."""
        if self.session.timeline.recording and not self.playback.paused:
            self._stop_record_and_pause()
            return
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

    def toggle_record(self) -> None:
        """Start or stop recording armed rows (R). Blocked while locked."""
        if self.session.timeline.locked:
            return
        if self.session.timeline.recording:
            self._stop_record()
        else:
            self._start_record()

    def toggle_arm_row(self, row: int) -> None:
        """Focus *row* and toggle its arm, as A does. Blocked while locked."""
        self.focus_row(row)
        if self.session.timeline.locked:
            return
        slot = self._slot_for_layer_index(row)
        if slot is not None:
            self._toggle_arm(slot)

    def toggle_row_visibility(self, row: int) -> None:
        """Focus *row* and toggle its visibility, as its number key does."""
        self.focus_row(row)
        slot = self._slot_for_layer_index(row)
        if slot is not None:
            self._toggle_slot_visibility(slot)

    def row_visibility_toggleable(self, row: int) -> bool:
        """Whether ``toggle_row_visibility`` would change *row* right now.

        True while paused, for an armed row while recording, and for a row
        with a visibility override. Plain playback leaves the row alone.
        """
        slot = self._slot_for_layer_index(row)
        if slot is None:
            return False
        tl = self.session.timeline
        if tl.recording:
            return slot in tl.armed_slots and slot in tl.record_baseline
        return bool(self.playback.paused) or slot in tl.override_slots

    def _toggle_slot_visibility(self, slot: str) -> None:
        tl = self.session.timeline
        if tl.recording:
            self._toggle_armed_layer_at(
                slot, current_sec(self.playback, self.duration_sec)
            )
        elif self.playback.paused:
            self._toggle_paused_stem_visibility(slot)
        elif slot in tl.override_slots:
            tl.override_visible[slot] = not tl.override_visible.get(slot, True)
            self._refresh_visibility()

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
        return cue_edits_allowed(self.session)

    def _step_selected_cue(self, *, forward: bool) -> None:
        step_cue_selection(
            self.session,
            self._focused_slot(),
            forward=forward,
            playhead_sec=current_sec(self.playback, self.duration_sec),
        )

    def _seek_to_selected_cue(self) -> None:
        if not cue_selection_allowed(self.session):
            return
        target = self.session.timeline.selected_cue_t.get(self._focused_slot())
        if target is None:
            return
        current = current_sec(self.playback, self.duration_sec)
        delta = target - current
        if self._on_seek is not None:
            self._on_seek(delta)
        else:
            seek(self.playback, delta, self.duration_sec)

    def _nudge_selected_cue_level(self, *, forward: bool, large: bool) -> None:
        """Adjust selected on-cue timeline opacity (multiplies into layer opacity)."""
        nudge_cue_level(self.session, self._focused_slot(), forward=forward, large=large)

    def _cycle_selected_cue_blend(self) -> None:
        slot = self._focused_slot()
        cue = selected_cue(self.session, slot)
        if cue is None:
            return
        options: tuple[BlendMode | None, ...] = (None, *BLEND_MODES)
        set_cue_blend(self.session, slot, _next_option(options, cue.blend))

    def _cycle_selected_cue_role(self) -> None:
        slot = self._focused_slot()
        cue = selected_cue(self.session, slot)
        if cue is None:
            return
        options: tuple[CueRole | None, ...] = (None, *CUE_ROLES)
        set_cue_role(self.session, slot, _next_option(options, cue.role))

    def _cycle_selected_cue_cut(self) -> None:
        slot = self._focused_slot()
        cue = selected_cue(self.session, slot)
        if cue is None:
            return
        current: CutType = cue.cut if cue.cut in CUT_TYPES else "none"
        set_cue_cut(self.session, slot, _next_option(CUT_TYPES, current))

    def _toggle_arm(self, slot: str) -> None:
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

        snapped = self._snap_placement(t_sec)
        # A press snapped ahead of the playhead still flips the pending state.
        pending_t = max(t_sec, snapped)
        current_on = (
            armed_recording_level(self.session, slot, pending_t) > LEVEL_EPS
        )
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

        snapped = self._snap_placement(t_sec)
        level = armed_recording_level(self.session, slot, max(t_sec, snapped))
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

    def seek_step(self, forward: bool, *, long: bool = False, tiny: bool = False) -> None:
        if long:
            delta_sec = SEEK_LONG
        elif tiny:
            delta_sec = SEEK_TINY
        else:
            delta_sec = SEEK_SHORT
        if not forward:
            delta_sec = -delta_sec
        self._seek_by(delta_sec)

    def seek_to(self, t_sec: float) -> None:
        """Move the playhead to *t_sec*; recording fills the skipped range."""
        target = max(0.0, min(self.duration_sec, t_sec))
        delta_sec = target - current_sec(self.playback, self.duration_sec)
        if abs(delta_sec) < 1e-6:
            return
        self._seek_by(delta_sec)

    def _seek_by(self, delta_sec: float) -> None:
        if self.session.timeline.recording:
            old_t = current_sec(self.playback, self.duration_sec)
            new_t = max(0.0, min(self.duration_sec, old_t + delta_sec))
            self._fill_record_at_seek(old_t, new_t)
            self._refresh_visibility()
        if self._on_seek is not None:
            self._on_seek(delta_sec)
        else:
            seek(self.playback, delta_sec, self.duration_sec)
