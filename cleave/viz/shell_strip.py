"""Pointer forwarding from the shell to the timeline strip."""

from __future__ import annotations

import pygame
from imgui_bundle import imgui

from cleave.viz.pointer_cursor import PointerShape
from cleave.viz.shell_context import ShellContext
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.shell_widgets import rect_has_point
from cleave.viz.timeline_pointer import TimelinePointer
from cleave.timeline import (
    TimelineClip,
    clip_shown_preset,
    clip_starting_at,
    clip_starts_preset,
)
from cleave.viz.clip_presets import is_each_clip
from cleave.viz.tooltips import show_tooltip


def strip_arm_tooltip(*, armed: bool, locked: bool) -> str:
    """Hover text for a strip row's arm button."""
    if locked:
        return "Locked: unlock the timeline to arm"
    return "Disarm" if armed else "Arm for recording"


def strip_solo_tooltip(*, solo: bool) -> str:
    """Hover text for a strip row's solo button."""
    return "End solo" if solo else "Solo this layer"


def strip_eye_tooltip(*, overridden: bool, recording: bool, armed: bool) -> str:
    """Hover text for a strip row's live visibility eye."""
    if recording:
        if armed:
            return "Click to record show / hide"
        return "Arm this row to record show / hide"
    if armed:
        return "Armed: press REC to record show / hide"
    if overridden:
        return "Override: click to show / hide"
    return "Show / hide, taking over from the timeline"


def clip_preset_tooltip(clips: list[TimelineClip], clip: TimelineClip) -> str:
    """The preset an each-clip clip plays, and whether it starts or continues it."""
    preset = clip_shown_preset(clips, clip)
    name = "no preset" if preset is None else preset.display_name
    if clip_starts_preset(clips, clip):
        return f"Starts {name}"
    return f"Continues {name}"


def strip_release_tooltip(*, recording: bool) -> str:
    """Hover text for a strip row's back-to-timeline button."""
    if recording:
        return "Stop recording to hand back to the timeline"
    return "Back to timeline"


class StripPointerRouter:
    """Forwards the pointer to the open timeline strip."""

    def __init__(
        self, context: ShellContext, pointer: TimelinePointer | None
    ) -> None:
        self._ctx = context
        self.pointer = pointer

    def has_scope(self) -> bool:
        return (
            self._ctx.controls.shell_focus.region is ShellRegion.TIMELINE
            and self._ctx.controls.session.timeline.panel_open
        )

    def under(self, x: float, y: float) -> TimelinePointer | None:
        """The strip pointer when (*x*, *y*) is on the open strip."""
        pointer = self.pointer
        layout = self._ctx.layout
        if pointer is None or layout is None:
            return None
        if not self._ctx.controls.session.timeline.panel_open:
            return None
        if layout.timeline[3] > 0 and rect_has_point(layout.timeline, x, y):
            return pointer
        return None

    def press(self, x: float, y: float, button: int = 0) -> None:
        """Press on the open strip: focus a row, select a cue, seek, or pan."""
        pointer = self.under(x, y)
        if pointer is not None:
            pointer.press(x, y, button)

    def wheel(
        self, event: pygame.event.Event, pos: tuple[float, float] | None
    ) -> bool:
        """Wheel at *pos* over the open strip zooms or pans it. False leaves it to ImGui."""
        if pos is None:
            return False
        x, y = pos
        if self._ctx.top_layer.captures_pointer(x, y):
            return False
        pointer = self.under(x, y)
        if pointer is None:
            return False
        shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        pointer.wheel(x, float(event.x), float(event.y), shift=shift)
        return True

    def cancel(self) -> None:
        if self.pointer is not None:
            self.pointer.cancel()

    def clear_hover(self) -> None:
        if self.pointer is not None:
            self.pointer.clear_hover()

    def show_button_tooltip(self) -> None:
        """Say what a row header button does on click."""
        pointer = self.pointer
        if pointer is None or pointer.scrubbing or pointer.panning:
            return
        if imgui.is_any_mouse_down():
            return
        session = self._ctx.controls.session
        timeline = session.timeline
        hover = timeline.strip_hover
        if not timeline.panel_open or hover is None:
            return
        target, row = hover
        if target not in ("arm", "solo", "eye", "release") or row is None:
            self._show_clip_tooltip()
            return
        z_order = session.layer_z_order
        if not 0 <= row < len(z_order):
            return
        slot = z_order[row]
        if target == "arm":
            text = strip_arm_tooltip(
                armed=slot in timeline.armed_slots,
                locked=timeline.locked,
            )
        elif target == "solo":
            text = strip_solo_tooltip(solo=session.solo_slot == slot)
        elif target == "release":
            if slot not in timeline.override_slots:
                return
            text = strip_release_tooltip(recording=bool(timeline.recording))
        elif target == "eye":
            text = strip_eye_tooltip(
                overridden=slot in timeline.override_slots,
                recording=bool(timeline.recording),
                armed=slot in timeline.armed_slots,
            )
        else:
            return
        show_tooltip(text)

    def _show_clip_tooltip(self) -> None:
        """Name the hovered clip's preset on a row whose presets change on each clip."""
        controls = self._ctx.controls
        session = controls.session
        hovered = session.timeline.strip_hover_clip
        if hovered is None or hovered[2] is not None:
            return
        row, start = hovered[0], hovered[1]
        z_order = session.layer_z_order
        if not 0 <= row < len(z_order) or not is_each_clip(session, z_order[row]):
            return
        clips = controls.clip_editor.clips(z_order[row])
        clip = clip_starting_at(clips, start)
        if clip is not None:
            show_tooltip(clip_preset_tooltip(clips, clip))

    def pointer_shape(self) -> PointerShape | None:
        """Hand over a strip button, left-right over the ruler, a scrub, or a clip edge, move over a clip."""
        pointer = self.pointer
        if pointer is None:
            return None
        timeline = self._ctx.controls.session.timeline
        if not timeline.panel_open:
            return None
        if pointer.panning:
            return PointerShape.MOVE
        if pointer.scrubbing or pointer.over_ruler or pointer.scrollbar_active:
            return PointerShape.RESIZE_EW
        # A clip body moves, a clip edge trims, and the middle of a boundary
        # two clips share rolls it, where clips can be edited.
        clip_gesture = pointer.clip_gesture
        if clip_gesture == "roll":
            return PointerShape.RESIZE_EW
        if clip_gesture == "trim_start":
            return PointerShape.TRIM_START
        if clip_gesture == "trim_end":
            return PointerShape.TRIM_END
        if clip_gesture == "move":
            return PointerShape.MOVE
        if pointer.hover_pressable:
            return PointerShape.HAND
        return None
