"""Render overlay row mutations for live tuning."""

from __future__ import annotations

from cleave.config import (
    RENDER_OVERLAY_ANIMATION_TYPES,
    RENDER_OVERLAY_POSITIONS,
    RENDER_OVERLAY_SLIDE_DIRECTIONS,
)
from cleave.viz.fonts import cycle_render_overlay_font
from cleave.viz.session import TuningSession


class RenderOverlayControls:
    """Mutations for render overlay rows."""

    def __init__(self, session: TuningSession) -> None:
        self.session = session

    def set_expanded(self, expanded: bool) -> None:
        ro = self.session.render_overlay
        if ro.expanded == expanded:
            return
        ro.expanded = expanded

    def set_enabled(self, enabled: bool) -> None:
        ro = self.session.render_overlay
        if ro.enabled == enabled:
            return
        ro.enabled = enabled
        if not enabled:
            self.session.render_overlay_solo = False
            ro.expanded = False

    def enter_solo(self) -> None:
        if self.session.render_overlay_solo:
            return
        self.session.render_overlay_solo = True

    def exit_solo(self) -> None:
        if not self.session.render_overlay_solo:
            return
        self.session.render_overlay_solo = False

    def cycle_position(self, *, forward: bool) -> None:
        ro = self.session.render_overlay
        positions = RENDER_OVERLAY_POSITIONS
        try:
            index = positions.index(ro.position)
        except ValueError:
            index = 0
        if forward:
            ro.position = positions[(index + 1) % len(positions)]
        else:
            ro.position = positions[(index - 1) % len(positions)]

    def set_title_expanded(self, expanded: bool) -> None:
        ro = self.session.render_overlay
        if ro.title_expanded == expanded:
            return
        ro.title_expanded = expanded

    def set_body_expanded(self, expanded: bool) -> None:
        ro = self.session.render_overlay
        if ro.body_expanded == expanded:
            return
        ro.body_expanded = expanded

    def set_animation_expanded(self, expanded: bool) -> None:
        ro = self.session.render_overlay
        if ro.animation_expanded == expanded:
            return
        ro.animation_expanded = expanded

    def cycle_animation_type(self, *, forward: bool) -> None:
        anim = self.session.render_overlay.animation
        types = RENDER_OVERLAY_ANIMATION_TYPES
        try:
            index = types.index(anim.type)
        except ValueError:
            index = 0
        if forward:
            anim.type = types[(index + 1) % len(types)]
        else:
            anim.type = types[(index - 1) % len(types)]

    def cycle_slide_direction(self, *, forward: bool) -> None:
        anim = self.session.render_overlay.animation
        directions = RENDER_OVERLAY_SLIDE_DIRECTIONS
        try:
            index = directions.index(anim.slide_direction)
        except ValueError:
            index = 0
        if forward:
            anim.slide_direction = directions[(index + 1) % len(directions)]
        else:
            anim.slide_direction = directions[(index - 1) % len(directions)]

    def set_title_font_size(self, size: int) -> None:
        self.session.render_overlay.title_font_size = max(1, size)

    def cycle_title_font(self, *, forward: bool) -> None:
        ro = self.session.render_overlay
        ro.title_font = cycle_render_overlay_font(ro.title_font, forward=forward)

    def set_title_margin_bottom(self, margin: int) -> None:
        self.session.render_overlay.title_margin_bottom = max(0, margin)

    def set_body_font_size(self, size: int) -> None:
        self.session.render_overlay.body_font_size = max(1, size)

    def cycle_body_font(self, *, forward: bool) -> None:
        ro = self.session.render_overlay
        ro.body_font = cycle_render_overlay_font(ro.body_font, forward=forward)

    def set_opacity(self, pct: int) -> None:
        self.session.render_overlay.opacity_pct = max(0, min(100, pct))

    def set_border_width(self, width: int) -> None:
        self.session.render_overlay.border_width = max(0, width)

    def set_start_delay(self, start_delay: float) -> None:
        self.session.render_overlay.animation.start_delay = max(0.0, start_delay)

    def set_display_time(self, display_time: float) -> None:
        self.session.render_overlay.animation.display_time = max(0.0, display_time)
