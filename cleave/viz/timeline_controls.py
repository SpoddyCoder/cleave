"""Keyboard input for the timeline panel overlay."""

from __future__ import annotations

from collections.abc import Callable

import pygame

from cleave.timeline import (
    TimelineCue,
    layer_visible_at,
    punch_replace,
    should_accept_toggle,
)
from cleave.viz.controls import SEEK_LONG, SEEK_SHORT, TuningSession
from cleave.viz.key_repeat import mod_ctrl
from cleave.viz.layer import timeline_cues_for_eval, timeline_defaults
from cleave.viz.playback import PlaybackState, current_sec, seek, toggle_pause

_LAYER_KEYS = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4)


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
        on_seek: Callable[[float], None] | None = None,
        on_toast: Callable[[str], None] | None = None,
    ) -> None:
        self.session = session
        self.playback = playback
        self.duration_sec = duration_sec
        self._on_visibility_change = on_visibility_change
        self._on_close = on_close
        self._on_seek = on_seek
        self._on_toast = on_toast
        self.focused_cue_index: int | None = None
        self._last_toggle_t: dict[str, float] = {}

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_q and mod_ctrl(event.mod):
            return False

        if event.key in (pygame.K_ESCAPE, pygame.K_t):
            self._close_panel()
            return True

        if event.key == pygame.K_r:
            if self.session.timeline.recording:
                self._stop_record()
            else:
                self._start_record()
            return True

        if event.key == pygame.K_SPACE:
            toggle_pause(self.playback, self.duration_sec)
            return True

        if event.key in (pygame.K_LEFT, pygame.K_RIGHT) and mod_ctrl(event.mod):
            if not self.session.timeline.recording:
                self._do_seek(event.key == pygame.K_RIGHT, long=mod_ctrl(event.mod))
            return True

        if self.session.timeline.recording and event.key in _LAYER_KEYS:
            stem = self._stem_for_layer_key(event.key)
            if stem is not None:
                self._toggle_armed_layer_at(
                    stem, current_sec(self.playback, self.duration_sec)
                )
            return True

        if event.key == pygame.K_UP:
            self._move_focus_row(-1)
            return True
        if event.key == pygame.K_DOWN:
            self._move_focus_row(1)
            return True

        if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self._navigate_cue(forward=event.key == pygame.K_RIGHT)
            return True

        if event.key == pygame.K_RETURN and mod_ctrl(event.mod):
            self._toggle_visibility_at_playhead()
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

    def _close_panel(self) -> None:
        if self._on_close is not None:
            self._on_close()

    def _toast(self, message: str) -> None:
        if self._on_toast is not None:
            self._on_toast(message)

    def _stem_for_layer_key(self, key: int) -> str | None:
        try:
            index = _LAYER_KEYS.index(key)
        except ValueError:
            return None
        z_order = self.session.layer_z_order
        if index >= len(z_order):
            return None
        return z_order[index]

    def _row_count(self) -> int:
        return len(self.session.layer_z_order)

    def _focused_stem(self) -> str:
        return self.session.layer_z_order[self.session.timeline.focus_row]

    def _move_focus_row(self, delta: int) -> None:
        count = self._row_count()
        if count == 0:
            return
        tl = self.session.timeline
        tl.focus_row = max(0, min(count - 1, tl.focus_row + delta))

    def _sorted_cues(self) -> list[TimelineCue]:
        return sorted(self.session.timeline.cues, key=lambda cue: cue.t)

    def _navigate_cue(self, *, forward: bool) -> None:
        sorted_cues = self._sorted_cues()
        if not sorted_cues:
            return
        if self.focused_cue_index is None:
            self.focused_cue_index = 0 if forward else len(sorted_cues) - 1
            return
        next_index = self.focused_cue_index + (1 if forward else -1)
        if 0 <= next_index < len(sorted_cues):
            self.focused_cue_index = next_index

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
        stem = self._focused_stem()
        armed = self.session.timeline.armed_stems
        if stem in armed:
            armed.discard(stem)
        else:
            armed.add(stem)

    def _toggle_visibility_at_playhead(self) -> None:
        tl = self.session.timeline
        stem = self._focused_stem()
        t_sec = current_sec(self.playback, self.duration_sec)
        defaults = timeline_defaults(self.session)
        current = layer_visible_at(tl.cues, defaults, stem, t_sec)
        tl.cues.append(TimelineCue(t=t_sec, layers={stem: not current}))
        tl.cues.sort(key=lambda cue: cue.t)
        if self._on_visibility_change is not None:
            self._on_visibility_change()

    def _start_record(self) -> None:
        tl = self.session.timeline
        if not tl.armed_stems:
            self._toast("Arm at least one layer to record")
            return

        t_sec = current_sec(self.playback, self.duration_sec)
        if self.playback.paused:
            toggle_pause(self.playback, self.duration_sec)

        tl.recording = True
        tl.record_start_sec = t_sec
        tl.record_buffer = []
        self._last_toggle_t = {}

        if self._on_visibility_change is not None:
            self._on_visibility_change()

    def _stop_record(self) -> None:
        tl = self.session.timeline
        record_start = tl.record_start_sec
        if record_start is None:
            tl.recording = False
            tl.record_buffer = []
            return

        record_stop = current_sec(self.playback, self.duration_sec)
        tl.cues = punch_replace(
            tl.cues,
            tl.armed_stems,
            record_start,
            record_stop,
            tl.record_buffer,
        )
        tl.recording = False
        tl.record_start_sec = None
        tl.record_buffer = []
        self._last_toggle_t = {}

        if self._on_visibility_change is not None:
            self._on_visibility_change()

    def _toggle_armed_layer_at(self, stem: str, t_sec: float) -> None:
        tl = self.session.timeline
        if stem not in tl.armed_stems:
            return
        if not should_accept_toggle(self._last_toggle_t.get(stem), t_sec):
            return

        defaults = timeline_defaults(self.session)
        cues = timeline_cues_for_eval(self.session)
        current = layer_visible_at(cues, defaults, stem, t_sec)
        tl.record_buffer.append(TimelineCue(t=t_sec, layers={stem: not current}))
        self._last_toggle_t[stem] = t_sec

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
