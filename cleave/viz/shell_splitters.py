"""Splitter drags between the shell's columns, navigator, and timeline."""

from __future__ import annotations

from cleave.viz.shell_context import ShellContext
from cleave.viz.shell_layout import (
    clamp_timeline_band_height,
    splitter_hit,
    splitter_request_height,
    splitter_request_timeline_height,
    splitter_request_width,
)
from cleave.viz.timeline_overlay import timeline_band_height_px


class SplitterDrag:
    """Column, navigator, and timeline splitter drags.

    The four requests are live sizes while a drag is held. A drag that
    moves at least 1px persists its size on release, then clears them.
    """

    def __init__(self, context: ShellContext) -> None:
        self._ctx = context
        self.insp_width: int | None = None
        self.help_width: int | None = None
        self.navigator_height: int | None = None
        self.timeline_height: int | None = None
        self.active: str | None = None
        self._down = (0.0, 0.0)
        # Pointer distance below the timeline's top edge at the press, so the
        # edge does not jump to the pointer when the drag starts.
        self._timeline_grab_dy = 0.0

    def at(self, x: float, y: float) -> str | None:
        layout = self._ctx.layout
        if layout is None:
            return None
        return splitter_hit(layout, x, y)

    def _assign_request(
        self, which: str, pointer: tuple[float, float]
    ) -> None:
        layout = self._ctx.layout
        if layout is None:
            return
        if which == "nav":
            self.navigator_height = splitter_request_height(layout, pointer[1])
            return
        if which == "timeline":
            self.timeline_height = splitter_request_timeline_height(
                layout, pointer[1] - self._timeline_grab_dy
            )
            return
        width = splitter_request_width(layout, which, pointer[0])
        if which == "help":
            self.help_width = width
        elif which == "insp":
            self.insp_width = width

    def begin(self, pos: tuple[float, float]) -> bool:
        which = self.at(float(pos[0]), float(pos[1]))
        if which is None:
            return False
        self.active = which
        self._down = (float(pos[0]), float(pos[1]))
        layout = self._ctx.layout
        self._timeline_grab_dy = (
            float(pos[1]) - float(layout.timeline[1])
            if which == "timeline" and layout is not None
            else 0.0
        )
        return True

    def end(self, pos: tuple[float, float]) -> None:
        which = self.active
        pointer = (float(pos[0]), float(pos[1]))
        axis = 1 if which in ("nav", "timeline") else 0
        moved = abs(pointer[axis] - self._down[axis]) >= 1.0
        if which == "timeline" and moved:
            self._assign_request(which, pointer)
            if self.timeline_height is not None:
                self._ctx.controls.settings.set_timeline_height(
                    self._drawn_timeline_height(self.timeline_height)
                )
            self.timeline_height = None
        elif which == "nav" and moved:
            self._assign_request(which, pointer)
            if self.navigator_height is not None:
                self._ctx.controls.settings.set_navigator_height(
                    self.navigator_height
                )
            self.navigator_height = None
        elif which is not None and moved:
            self._assign_request(which, pointer)
            editor = self._ctx.controls.cfg.editor
            insp = (
                self.insp_width
                if self.insp_width is not None
                else editor.inspector_width
            )
            help_w = (
                self.help_width
                if self.help_width is not None
                else editor.help_width
            )
            self._ctx.controls.settings.set_shell_column_widths(insp, help_w)
            self.insp_width = None
            self.help_width = None
        self.active = None

    def _drawn_timeline_height(self, requested: int) -> int:
        """Saved timeline height for *requested*: 0 at the fit, else the clamp."""
        layout = self._ctx.layout
        if layout is None:
            return requested
        rows = len(self._ctx.controls.session.layer_z_order)
        fit_h = timeline_band_height_px(rows)
        top_h = layout.menu[3] + layout.transport[3]
        display_h = layout.timeline[1] + layout.timeline[3]
        height = clamp_timeline_band_height(
            requested, fit_h, display_h=display_h, top_h=top_h
        )
        return 0 if height <= fit_h else height

    def cancel(self) -> None:
        self.active = None
        self.navigator_height = None
        self.timeline_height = None

    def track_motion(self, x: float, y: float) -> None:
        if self.active is not None:
            self._assign_request(self.active, (x, y))
