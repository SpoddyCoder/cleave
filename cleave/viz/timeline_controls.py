"""Keyboard input for the timeline panel overlay."""

from __future__ import annotations

from collections.abc import Callable

import pygame

from cleave.timeline import (
    TimelineCue,
    punch_replace,
    should_accept_toggle,
)
from cleave.viz.controls import SEEK_LONG, SEEK_SHORT
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
    pygame.K_KP1: 0,
    pygame.K_KP2: 1,
    pygame.K_KP3: 2,
    pygame.K_KP4: 3,
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
        on_toast: Callable[[str], None] | None = None,
    ) -> None:
        self.session = session
        self.playback = playback
        self.duration_sec = duration_sec
        self._on_visibility_change = on_visibility_change
        self._on_close = on_close
        self._on_exit_submenu = on_exit_submenu
        self._on_seek = on_seek
        self._on_toast = on_toast
        self.focused_cue_index: int | None = None
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
            if not self.session.timeline.recording:
                self._do_seek(
                    event.key == pygame.K_RIGHT,
                    long=mod_ctrl(event.mod),
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

        if event.key == pygame.K_BACKSPACE:
            self._delete_focused_cue()
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

    def _toast(self, message: str) -> None:
        if self._on_toast is not None:
            self._on_toast(message)

    def _slot_for_layer_index(self, index: int) -> str | None:
        z_order = self.session.layer_z_order
        if index >= len(z_order):
            return None
        return z_order[index]

    def _focused_slot(self) -> str:
        return self.session.layer_z_order[self.session.timeline.focus_row]

    def _sorted_cues(self) -> list[TimelineCue]:
        return sorted(self.session.timeline.cues, key=lambda cue: cue.t)

    def _nearest_cue_index(self, t_sec: float) -> int | None:
        sorted_cues = self._sorted_cues()
        if not sorted_cues:
            return None
        return min(
            range(len(sorted_cues)),
            key=lambda index: abs(sorted_cues[index].t - t_sec),
        )

    def _delete_focused_cue(self) -> None:
        tl = self.session.timeline
        sorted_cues = self._sorted_cues()
        if not sorted_cues:
            self._toast("No cues")
            return

        delete_index = self.focused_cue_index
        if delete_index is None:
            delete_index = self._nearest_cue_index(
                current_sec(self.playback, self.duration_sec)
            )
        if delete_index is None:
            self._toast("No cues")
            return

        cue_to_remove = sorted_cues[delete_index]
        tl.cues = [cue for cue in tl.cues if cue is not cue_to_remove]
        tl.cues.sort(key=lambda cue: cue.t)

        if self.focused_cue_index is not None:
            if delete_index < self.focused_cue_index:
                self.focused_cue_index -= 1
            elif delete_index == self.focused_cue_index:
                if tl.cues:
                    self.focused_cue_index = min(
                        delete_index, len(self._sorted_cues()) - 1
                    )
                else:
                    self.focused_cue_index = None

        if self._on_visibility_change is not None:
            self._on_visibility_change()

    def _toggle_arm(self) -> None:
        slot = self._focused_slot()
        armed = self.session.timeline.armed_slots
        if slot in armed:
            armed.discard(slot)
        else:
            armed.add(slot)

    def _start_record(self) -> None:
        tl = self.session.timeline
        if not tl.armed_slots:
            self._toast("Arm at least one layer to record")
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
        tl.record_buffer = []
        self._last_toggle_t = {}

        self._refresh_visibility()

    def _stop_record(self) -> None:
        tl = self.session.timeline
        record_start = tl.record_start_sec
        if record_start is None:
            tl.recording = False
            tl.record_buffer = []
            tl.record_baseline = {}
            return

        record_stop = current_sec(self.playback, self.duration_sec)
        tl.cues = punch_replace(
            tl.cues,
            tl.armed_slots,
            record_start,
            record_stop,
            build_record_punch_cues(self.session, record_start, record_stop),
        )
        tl.recording = False
        tl.record_start_sec = None
        tl.record_buffer = []
        tl.record_baseline = {}
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
        tl.record_buffer.append(TimelineCue(t=t_sec, layers={slot: not current}))
        self._last_toggle_t[slot] = t_sec

        if self._on_visibility_change is not None:
            self._on_visibility_change()

    def _do_seek(self, forward: bool, *, long: bool) -> None:
        delta_sec = SEEK_LONG if long else SEEK_SHORT
        if not forward:
            delta_sec = -delta_sec
        if self._on_seek is not None:
            self._on_seek(delta_sec)
        else:
            seek(self.playback, delta_sec, self.duration_sec)
