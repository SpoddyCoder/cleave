"""Render overlay row mutations for live tuning."""

from __future__ import annotations

from typing import Literal

from cleave.config import (
    RENDER_OVERLAY_ANIMATION_TYPES,
    RENDER_OVERLAY_POSITIONS,
    RENDER_OVERLAY_SLIDE_DIRECTIONS,
)
from cleave.viz.fonts import cycle_render_overlay_font
from cleave.viz.session import (
    RenderOverlayCardRuntime,
    RenderOverlayClosingAnimationRuntime,
    TuningSession,
)

CardName = Literal["opening_card", "closing_card"]


class RenderOverlayCardControls:
    """Mutations for one overlay card's rows."""

    def __init__(self, session: TuningSession, card: CardName) -> None:
        self.session = session
        self._card_name = card

    def _card(self) -> RenderOverlayCardRuntime:
        return getattr(self.session.render_overlays, self._card_name)

    def set_expanded(self, expanded: bool) -> None:
        card = self._card()
        if card.expanded == expanded:
            return
        card.expanded = expanded

    def set_enabled(self, enabled: bool) -> None:
        card = self._card()
        if card.enabled == enabled:
            return
        card.enabled = enabled
        if not enabled:
            card.expanded = False
            overlays = self.session.render_overlays
            if (
                not overlays.opening_card.enabled
                and not overlays.closing_card.enabled
            ):
                self.session.render_overlay_solo = False

    def cycle_position(self, *, forward: bool) -> None:
        card = self._card()
        positions = RENDER_OVERLAY_POSITIONS
        try:
            index = positions.index(card.position)
        except ValueError:
            index = 0
        if forward:
            card.position = positions[(index + 1) % len(positions)]
        else:
            card.position = positions[(index - 1) % len(positions)]

    def set_title_expanded(self, expanded: bool) -> None:
        card = self._card()
        if card.title_expanded == expanded:
            return
        card.title_expanded = expanded

    def set_body_expanded(self, expanded: bool) -> None:
        card = self._card()
        if card.body_expanded == expanded:
            return
        card.body_expanded = expanded

    def set_animation_expanded(self, expanded: bool) -> None:
        card = self._card()
        if card.animation_expanded == expanded:
            return
        card.animation_expanded = expanded

    def cycle_animation_type(self, *, forward: bool) -> None:
        anim = self._card().animation
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
        anim = self._card().animation
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
        self._card().title_font_size = max(1, size)

    def cycle_title_font(self, *, forward: bool) -> None:
        card = self._card()
        card.title_font = cycle_render_overlay_font(card.title_font, forward=forward)

    def set_title_margin_bottom(self, margin: int) -> None:
        self._card().title_margin_bottom = max(0, margin)

    def set_body_font_size(self, size: int) -> None:
        self._card().body_font_size = max(1, size)

    def cycle_body_font(self, *, forward: bool) -> None:
        card = self._card()
        card.body_font = cycle_render_overlay_font(card.body_font, forward=forward)

    def set_opacity(self, pct: int) -> None:
        self._card().opacity_pct = max(0, min(100, pct))

    def set_border_width(self, width: int) -> None:
        self._card().border_width = max(0, width)

    def set_appear_at(self, appear_at: float) -> None:
        anim = self._card().animation
        if isinstance(anim, RenderOverlayClosingAnimationRuntime):
            return
        anim.appear_at = max(0.0, appear_at)

    def set_disappear_at(self, disappear_at: float) -> None:
        anim = self._card().animation
        if not isinstance(anim, RenderOverlayClosingAnimationRuntime):
            return
        anim.disappear_at = max(0.0, disappear_at)

    def set_display_time(self, display_time: float) -> None:
        self._card().animation.display_time = max(0.0, display_time)


class RenderOverlaysControls:
    """Parent overlays section mutations plus per-card controllers."""

    def __init__(self, session: TuningSession) -> None:
        self.session = session
        self.opening_card = RenderOverlayCardControls(session, "opening_card")
        self.closing_card = RenderOverlayCardControls(session, "closing_card")

    def set_expanded(self, expanded: bool) -> None:
        overlays = self.session.render_overlays
        if overlays.expanded == expanded:
            return
        overlays.expanded = expanded

    def set_enabled(self, enabled: bool) -> None:
        """Bulk-enable or disable both cards."""
        self.opening_card.set_enabled(enabled)
        self.closing_card.set_enabled(enabled)
        if not enabled:
            self.session.render_overlays.expanded = False
            self.session.render_overlay_solo = False

    def set_locked(self, locked: bool) -> None:
        overlays = self.session.render_overlays
        if overlays.locked == locked:
            return
        overlays.locked = locked

    def toggle_locked(self) -> None:
        overlays = self.session.render_overlays
        overlays.locked = not overlays.locked

    def any_card_enabled(self) -> bool:
        overlays = self.session.render_overlays
        return overlays.opening_card.enabled or overlays.closing_card.enabled

    def enter_solo(self) -> None:
        if self.session.render_overlay_solo:
            return
        self.session.render_overlay_solo = True

    def exit_solo(self) -> None:
        if not self.session.render_overlay_solo:
            return
        self.session.render_overlay_solo = False
