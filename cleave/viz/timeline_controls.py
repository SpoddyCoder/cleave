"""Keyboard input for the timeline panel overlay."""

from __future__ import annotations

from collections.abc import Callable

import pygame

from cleave.timeline import SlotCue, canonicalize, should_accept_toggle
from cleave.viz.controls import SEEK_LONG, SEEK_SHORT, SEEK_TINY
from cleave.viz.session import TuningSession
from cleave.viz.key_repeat import mod_ctrl, mod_shift
from cleave.viz.layer_visibility import (
    armed_recording_visible,
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
    ) -> None:
        self.session = session
        self.playback = playback
        self.duration_sec = duration_sec
        self._on_visibility_change = on_visibility_change
        self._on_close = on_close
        self._on_exit_submenu = on_exit_submenu
        self._on_seek = on_seek
        self._on_notification = on_notification
        self._last_toggle_t: dict[str, float] = {}

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if event.key in (pygame.K_ESCAPE, pygame.K_t):
            if not self.session.timeline.recording:
                self._close_panel()
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

        if event.key == pygame.K_RETURN and mod_ctrl(event.mod):
            return True

        if event.key == pygame.K_RETURN and mod_shift(event.mod):
            if not self.session.timeline.recording:
                self._toggle_override_focused_row()
            return True

        if event.key == pygame.K_RETURN:
            self._toggle_arm()
            return True

        return True

    def handle_keyup(self, event: pygame.event.Event) -> None:
        del event

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
        tl.arm_flash_start_ms[slot] = pygame.time.get_ticks()

    def _commit_recording_slot(self, slot: str) -> None:
        tl = self.session.timeline
        record_start = tl.record_start_sec
        if record_start is None or slot not in tl.record_baseline:
            return

        record_stop = current_sec(self.playback, self.duration_sec)
        punch_end = max(record_stop, tl.record_high_water_mark or record_stop)
        build_record_punch_cues(
            self.session,
            record_start,
            punch_end,
            slots={slot},
        )
        tl.record_baseline.pop(slot, None)
        tl.record_buffer.pop(slot, None)
        self._last_toggle_t.pop(slot, None)

        if not tl.armed_slots:
            tl.recording = False
            tl.record_start_sec = None
            tl.record_buffer = {}
            tl.record_baseline = {}
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
        tl.record_baseline = {
            stem: effective_layer_enabled(self.session, stem, t_sec)
            for stem in tl.armed_slots
        }

        tl.preview_active = False
        tl.monitor = {}

        if self.playback.paused:
            toggle_pause(self.playback, self.duration_sec)

        tl.recording = True
        tl.record_start_sec = t_sec
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
            tl.record_high_water_mark = None
            return

        record_stop = current_sec(self.playback, self.duration_sec)
        punch_end = max(record_stop, tl.record_high_water_mark or record_stop)
        build_record_punch_cues(self.session, record_start, punch_end)
        tl.recording = False
        tl.record_start_sec = None
        tl.record_buffer = {}
        tl.record_baseline = {}
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
        if slot not in tl.armed_slots:
            return
        if not should_accept_toggle(self._last_toggle_t.get(slot), t_sec):
            return

        current = armed_recording_visible(self.session, slot, t_sec)
        tl.record_buffer.setdefault(slot, []).append(
            SlotCue(t=t_sec, visible=not current)
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
            v = armed_recording_visible(self.session, slot, old_t)
            buf = tl.record_buffer.get(slot, [])
            kept = [
                cue for cue in buf if not (skip_start <= cue.t <= skip_end)
            ]
            tl.record_buffer[slot] = canonicalize(
                tl.record_baseline[slot],
                kept + [SlotCue(t=skip_start, visible=v)],
            )
            self._last_toggle_t.pop(slot, None)
        tl.record_high_water_mark = max(tl.record_high_water_mark or 0.0, old_t)
        if tl.record_start_sec is not None and new_t < tl.record_start_sec:
            tl.record_start_sec = new_t

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
