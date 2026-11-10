"""Render overlay card row specs for the live tuning overlay."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from cleave.config_schema.descriptors import parse_hex_colour, rgb_to_hex
from cleave.config_schema.render import (
    RENDER_OVERLAY_ANIMATION_TYPE_HELP_ENTRIES,
    RENDER_OVERLAY_SLIDE_DIRECTION_HELP_ENTRIES,
)
from cleave.viz.colour_parse import (
    parse_hex_colour_or_none,
    validate_hex_colour,
    validate_optional_hex_colour,
)
from cleave.viz.fonts import overlay_font_display
from cleave.viz.inline_edit import ColourTarget
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.row_specs.common import lock_text, on_off_text
from cleave.viz.tuning_view_state import TuningViewState

from cleave.config_schema.render.overlays import RENDER_OVERLAY_ANIMATION_TYPES, RENDER_OVERLAY_POSITIONS, RENDER_OVERLAY_SLIDE_DIRECTIONS
from cleave.viz.fonts import overlay_system_fonts
from cleave.viz.row_specs.common import bool_choice, options_choice
if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

def _overlay_card_block(state: TuningViewState, desc: RowDescriptor):
    assert desc.card is not None
    return getattr(state.overlays, desc.card)

def _overlay_card_controls(controls: TuningControls, desc: RowDescriptor):
    assert desc.card is not None
    return controls.overlays.card(desc.card)

def _overlay_card_block_session(controls: TuningControls, desc: RowDescriptor):
    assert desc.card is not None
    return getattr(controls.session.overlays, desc.card)

def overlay_card_panel_label(kind: RowKind, card: str | None) -> str | None:
    if card is None:
        return None
    if kind == RowKind.OVERLAY_CARD_HEADER:
        return "opening card" if card == "opening_card" else "closing card"
    if kind == RowKind.OVERLAY_CARD_TIME:
        return "appear at" if card == "opening_card" else "disappear at"
    return None

def _format_overlay_card_position(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _overlay_card_block(state, desc).runtime.position

def _format_overlay_card_title_font_size(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.title_font_size}px"

def _format_overlay_card_title_font(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return overlay_font_display(_overlay_card_block(state, desc).runtime.title_font)

def _format_overlay_card_title_margin_bottom(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.title_margin_bottom}px"

def _format_overlay_card_title_content(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    content = _overlay_card_block(state, desc).runtime.title_content
    return content.replace("\n", " ").replace("\r", " ")

def _format_overlay_card_colour(
    state: TuningViewState, desc: RowDescriptor, field: str
) -> str:
    colour = getattr(_overlay_card_block(state, desc).runtime, field)
    if colour is None:
        return "none"
    return rgb_to_hex(colour)

def _format_overlay_card_title_colour(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _format_overlay_card_colour(state, desc, "title_colour")

def _format_overlay_card_title_background_colour(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _format_overlay_card_colour(state, desc, "title_background_colour")

def _format_overlay_card_body_font_size(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.body_font_size}px"

def _format_overlay_card_body_font(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return overlay_font_display(_overlay_card_block(state, desc).runtime.body_font)

def _format_overlay_card_body_content(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    content = _overlay_card_block(state, desc).runtime.body_content
    return content.replace("\n", " ").replace("\r", " ")

def _format_overlay_card_body_colour(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _format_overlay_card_colour(state, desc, "body_colour")

def _format_overlay_card_body_background_colour(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _format_overlay_card_colour(state, desc, "body_background_colour")

def _format_overlay_card_opacity(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.opacity_pct}%"

def _format_overlay_card_border_width(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.border_width}px"

def _format_overlay_card_background_colour(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _format_overlay_card_colour(state, desc, "background_colour")

def _format_overlay_card_background_margin(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.background_margin}px"

def _format_overlay_card_background_padding(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.background_padding}px"

def _format_overlay_card_border_colour(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _format_overlay_card_colour(state, desc, "border_colour")

def _format_overlay_card_time(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    anim = _overlay_card_block(state, desc).runtime.animation
    if desc.card == "opening_card":
        return f"{getattr(anim, 'appear_at', 0.0):.1f}s"
    return f"{getattr(anim, 'disappear_at', 0.0):.1f}s"

def _format_overlay_card_display_time(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.animation.display_time:.1f}s"

def _format_overlay_card_animation_type(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _overlay_card_block(state, desc).runtime.animation.type

def _format_overlay_card_slide_direction(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _overlay_card_block(state, desc).runtime.animation.slide_direction

def _apply_overlay_card_position(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    _overlay_card_controls(controls, desc).step_position(delta=1 if forward else -1)

def _apply_overlay_card_title_font_size(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    step = 10 if large else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_title_font_size(
        card.title_font_size + delta
    )

def _apply_overlay_card_title_font(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    _overlay_card_controls(controls, desc).step_title_font(delta=1 if forward else -1)

def _apply_overlay_card_title_margin_bottom(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    step = 10 if large else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_title_margin_bottom(
        card.title_margin_bottom + delta
    )

def _apply_overlay_card_title_text_action(
    controls: TuningControls,
    desc: RowDescriptor,
) -> None:
    card_controls = _overlay_card_controls(controls, desc)
    current_title = _overlay_card_block_session(controls, desc).title_content
    controls.inline_edit.begin_text(
        desc, current_title, card_controls.set_title_content
    )



def _colour_target(
    field: str, *, optional: bool = False
) -> Callable[[TuningControls, RowDescriptor], ColourTarget]:
    def target(controls: TuningControls, desc: RowDescriptor) -> ColourTarget:
        return ColourTarget(
            current=getattr(_overlay_card_block_session(controls, desc), field),
            apply=getattr(_overlay_card_controls(controls, desc), f"set_{field}"),
            optional=optional,
        )

    return target


def _colour_action(
    field: str, *, optional: bool = False
) -> Callable[[TuningControls, RowDescriptor], None]:
    """Edit the hex text inline. The swatch opens the picker."""

    def action(controls: TuningControls, desc: RowDescriptor) -> None:
        target = _colour_target(field, optional=optional)(controls, desc)

        def on_commit(draft: str) -> None:
            if optional:
                target.apply(parse_hex_colour_or_none(draft))
            else:
                target.apply(parse_hex_colour(draft, "colour"))

        controls.inline_edit.begin_text(
            desc,
            "" if target.current is None else rgb_to_hex(target.current),
            on_commit,
            validate=(
                validate_optional_hex_colour if optional else validate_hex_colour
            ),
        )

    return action


def _apply_overlay_card_body_font_size(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    step = 10 if large else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_body_font_size(
        card.body_font_size + delta
    )

def _apply_overlay_card_body_font(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    _overlay_card_controls(controls, desc).step_body_font(delta=1 if forward else -1)

def _apply_overlay_card_body_text_action(
    controls: TuningControls,
    desc: RowDescriptor,
) -> None:
    card_controls = _overlay_card_controls(controls, desc)
    current_body = _overlay_card_block_session(controls, desc).body_content
    controls.modal_host.prompt_text(
        cta="Change text...",
        initial=current_body,
        on_confirm=card_controls.set_body_content,
        single_line=False,
    )

def _apply_overlay_card_opacity(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    step = 10 if large else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_opacity(card.opacity_pct + delta)

def _apply_overlay_card_border_width(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    step = 10 if large else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_border_width(card.border_width + delta)

def _apply_overlay_card_background_margin(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    step = 10 if large else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_background_margin(
        card.background_margin + delta
    )

def _apply_overlay_card_background_padding(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    step = 10 if large else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_background_padding(
        card.background_padding + delta
    )

def _apply_overlay_card_time(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    step = 30.0 if large else 1.0
    delta = step if forward else -step
    card_controls = _overlay_card_controls(controls, desc)
    anim = _overlay_card_block_session(controls, desc).animation
    if desc.card == "opening_card":
        card_controls.set_appear_at(getattr(anim, "appear_at", 0.0) + delta)
        return
    card_controls.set_disappear_at(getattr(anim, "disappear_at", 0.0) + delta)

def _apply_overlay_card_display_time(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    step = 30.0 if large else 1.0
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_display_time(
        card.animation.display_time + delta
    )

def _apply_overlay_card_animation_type(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    _overlay_card_controls(controls, desc).step_animation_type(delta=1 if forward else -1)

def _apply_overlay_card_slide_direction(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    _overlay_card_controls(controls, desc).step_slide_direction(delta=1 if forward else -1)

def _toggle_overlays_enabled(
    controls: TuningControls, _desc: RowDescriptor
) -> None:
    if controls.session.overlays.locked:
        return
    controls.overlays.set_enabled(
        not controls.overlays.any_card_enabled()
    )


def _toggle_overlays_solo(
    controls: TuningControls, _desc: RowDescriptor
) -> None:
    if controls.session.overlay_solo:
        controls.overlays.exit_solo()
    else:
        controls.overlays.enter_solo()


def _format_overlays_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return on_off_text(_visibility_overlays(state, _desc)[0])


def _format_overlays_solo(state: TuningViewState, _desc: RowDescriptor) -> str:
    return on_off_text(state.overlays.solo)


def _format_overlays_locked(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return lock_text(state.overlays.locked)


def _apply_overlays_enabled(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    controls.overlays.set_enabled(forward)


def _apply_overlays_solo(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    if controls.session.overlay_solo != forward:
        _toggle_overlays_solo(controls, desc)


def _apply_overlays_locked(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    if controls.session.overlays.locked != forward:
        controls.toggle_overlay_locked()


def _format_overlay_card_enabled(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return on_off_text(_overlay_card_block(state, desc).runtime.enabled)


def _apply_overlay_card_enabled(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    _overlay_card_controls(controls, desc).set_enabled(forward)


def _toggle_overlay_card_enabled(
    controls: TuningControls, desc: RowDescriptor
) -> None:
    if controls.session.overlays.locked:
        return
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_enabled(not card.enabled)


def _visibility_overlays(
    state: TuningViewState, _desc: RowDescriptor
) -> tuple[bool, bool]:
    block = state.overlays
    any_enabled = (
        block.opening_card.runtime.enabled or block.closing_card.runtime.enabled
    )
    return (any_enabled, block.solo)

def _jump_overlay_card_animation_type(
    controls: TuningControls, desc: RowDescriptor, delta: int
) -> None:
    _overlay_card_controls(controls, desc).step_animation_type(delta=delta)

def _jump_overlay_card_slide_direction(
    controls: TuningControls, desc: RowDescriptor, delta: int
) -> None:
    _overlay_card_controls(controls, desc).step_slide_direction(delta=delta)

def _jump_overlay_card_position(
    controls: TuningControls, desc: RowDescriptor, delta: int
) -> None:
    _overlay_card_controls(controls, desc).step_position(delta=delta)

def _jump_overlay_card_title_font(
    controls: TuningControls, desc: RowDescriptor, delta: int
) -> None:
    _overlay_card_controls(controls, desc).step_title_font(delta=delta)

def _jump_overlay_card_body_font(
    controls: TuningControls, desc: RowDescriptor, delta: int
) -> None:
    _overlay_card_controls(controls, desc).step_body_font(delta=delta)

SPECS: dict[RowKind, RowSpec] = {
    RowKind.OVERLAYS_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="Overlay",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_overlays,
        help_title="Credits Overlays",
        help_description=(
            "Opening and closing credits cards.",
        ),
        toggle_enabled=_toggle_overlays_enabled,
        toggle_solo=_toggle_overlays_solo,
    ),
    RowKind.OVERLAYS_ENABLED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="enabled",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlays_enabled,
        apply_horizontal=_apply_overlays_enabled,
        choice=bool_choice(lambda s, d: _visibility_overlays(s, d)[0]),
        help_title="Overlay Enabled",
        help_description=("Turns the opening and closing cards on or off together.",),
        blocked_by_section_lock=True,
    ),
    RowKind.OVERLAYS_SOLO: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="solo",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlays_solo,
        apply_horizontal=_apply_overlays_solo,
        choice=bool_choice(lambda s, _d: s.overlays.solo),
        help_title="Overlay Solo",
        help_description=("Shows the credits cards on their own.",),
        blocked_by_section_lock=False,
    ),
    RowKind.OVERLAYS_LOCKED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="lock",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlays_locked,
        apply_horizontal=_apply_overlays_locked,
        choice=bool_choice(lambda s, _d: s.overlays.locked, lock_text),
        help_title="Overlay Lock",
        help_description=("Locked overlay settings cannot be edited.",),
        blocked_by_section_lock=False,
    ),
    RowKind.OVERLAY_CARD_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="card",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Credits Card",
        help_entries=(
            ("E", "enable/disable"),
        ),
        help_description=(
            "Opening card at the start of the song, or closing card near the end.",
        ),
        toggle_enabled=_toggle_overlay_card_enabled,
        parent_group="overlay",
    ),
    RowKind.OVERLAY_CARD_ENABLED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="enabled",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_enabled,
        apply_horizontal=_apply_overlay_card_enabled,
        choice=bool_choice(lambda s, d: _overlay_card_block(s, d).runtime.enabled),
        help_title="Card Enabled",
        help_description=("Turns this credits card on or off.",),
        parent_group="overlay",
        blocked_by_section_lock=True,
    ),
    RowKind.OVERLAY_CARD_ANIMATION_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="animation",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Card Animation",
        help_description=(
            "Entrance and exit motion for this credits card.",
        ),
        parent_group="overlay",
    ),
    RowKind.OVERLAY_CARD_ANIMATION_TYPE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="type",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_animation_type,
        apply_horizontal=_apply_overlay_card_animation_type,
        choice=options_choice(RENDER_OVERLAY_ANIMATION_TYPES, lambda s, d: _overlay_card_block(s, d).runtime.animation.type, jump=_jump_overlay_card_animation_type),
        help_title="Animation Type",
        help_entries=(("Left/Right", "choose type"),),
        help_description=("How this credits card enters and leaves the screen.",),
        help_mode_entries=RENDER_OVERLAY_ANIMATION_TYPE_HELP_ENTRIES,
        repeatable=True,
        parent_group="overlay_animation",
    ),
    RowKind.OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="slide-direction",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_slide_direction,
        apply_horizontal=_apply_overlay_card_slide_direction,
        choice=options_choice(RENDER_OVERLAY_SLIDE_DIRECTIONS, lambda s, d: _overlay_card_block(s, d).runtime.animation.slide_direction, jump=_jump_overlay_card_slide_direction),
        help_title="Slide Direction",
        help_entries=(("Left/Right", "choose direction"),),
        help_description=(
            "Edge this credits card travels from on entrance (reverse on exit).",
        ),
        help_mode_entries=RENDER_OVERLAY_SLIDE_DIRECTION_HELP_ENTRIES,
        repeatable=True,
        parent_group="overlay_animation",
    ),
    RowKind.OVERLAY_CARD_POSITION: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="position",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_position,
        apply_horizontal=_apply_overlay_card_position,
        choice=options_choice(RENDER_OVERLAY_POSITIONS, lambda s, d: _overlay_card_block(s, d).runtime.position, jump=_jump_overlay_card_position),
        help_title="Position",
        help_description=(
            "Screen corner where this credits card appears.",
        ),
        repeatable=True,
        parent_group="overlay",
    ),
    RowKind.OVERLAY_CARD_TITLE_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="title",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Card Title",
        help_description=("Title line of this credits card.",),
        parent_group="overlay",
    ),
    RowKind.OVERLAY_CARD_TITLE_FONT_SIZE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="font size",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_title_font_size,
        apply_horizontal=_apply_overlay_card_title_font_size,
        help_title="Title Font Size",
        help_description=("Font size of this credits card title.",),
        repeatable=True,
        parent_group="overlay_title",
    ),
    RowKind.OVERLAY_CARD_TITLE_FONT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="font",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_title_font,
        apply_horizontal=_apply_overlay_card_title_font,
        choice=options_choice(overlay_system_fonts, lambda s, d: _overlay_card_block(s, d).runtime.title_font, jump=_jump_overlay_card_title_font),
        fit_strategy=FitStrategy.NONE,
        help_title="Title Font",
        help_description=("Font used for this credits card title.",),
        repeatable=True,
        parent_group="overlay_title",
    ),
    RowKind.OVERLAY_CARD_TITLE_MARGIN_BOTTOM: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="margin bottom",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_title_margin_bottom,
        apply_horizontal=_apply_overlay_card_title_margin_bottom,
        help_title="Title Margin Bottom",
        help_description=(
            "Gap between the title and body in this credits card box.",
        ),
        repeatable=True,
        parent_group="overlay_title",
    ),
    RowKind.OVERLAY_CARD_TITLE_TEXT: RowSpec(
        affordance=RowAffordance.VALUE_TEXT,
        panel_label="title text",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_title_content,
        apply_action=_apply_overlay_card_title_text_action,
        help_title="Title Text",
        help_entries=(("Enter", "edit title"),),
        help_description=("Edit this card's title in place.",),
        parent_group="overlay_title",
        blocked_by_section_lock=True,
    ),
    RowKind.OVERLAY_CARD_TITLE_COLOUR: RowSpec(
        affordance=RowAffordance.VALUE_COLOUR,
        panel_label="title colour",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_title_colour,
        apply_action=_colour_action("title_colour"),
        colour_target=_colour_target("title_colour"),
        help_title="Title Colour",
        help_entries=(("Enter", "edit hex value"),),
        help_description=("Hex colour of this credits card title.",),
        parent_group="overlay_title",
        blocked_by_section_lock=True,
    ),
    RowKind.OVERLAY_CARD_TITLE_BACKGROUND_COLOUR: RowSpec(
        affordance=RowAffordance.VALUE_COLOUR,
        panel_label="title background",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_title_background_colour,
        apply_action=_colour_action("title_background_colour", optional=True),
        colour_target=_colour_target("title_background_colour", optional=True),
        help_title="Title Background",
        help_entries=(("Enter", "edit hex value"),),
        help_description=(
            "Optional hex background colour of this credits card title.",
        ),
        parent_group="overlay_title",
        blocked_by_section_lock=True,
    ),
    RowKind.OVERLAY_CARD_BODY_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="body",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Card Body",
        help_description=("Body block of this credits card.",),
        parent_group="overlay",
    ),
    RowKind.OVERLAY_CARD_BODY_FONT_SIZE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="font size",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_body_font_size,
        apply_horizontal=_apply_overlay_card_body_font_size,
        help_title="Body Font Size",
        help_description=("Font size of this credits card body.",),
        repeatable=True,
        parent_group="overlay_body",
    ),
    RowKind.OVERLAY_CARD_BODY_FONT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="font",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_body_font,
        apply_horizontal=_apply_overlay_card_body_font,
        choice=options_choice(overlay_system_fonts, lambda s, d: _overlay_card_block(s, d).runtime.body_font, jump=_jump_overlay_card_body_font),
        fit_strategy=FitStrategy.NONE,
        help_title="Body Font",
        help_description=("Font used for this credits card body.",),
        repeatable=True,
        parent_group="overlay_body",
    ),
    RowKind.OVERLAY_CARD_BODY_TEXT: RowSpec(
        affordance=RowAffordance.VALUE_TEXT,
        panel_label="body text",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_body_content,
        apply_action=_apply_overlay_card_body_text_action,
        help_title="Body Text",
        help_entries=(("Enter", "edit body"),),
        help_description=("Open a dialog to change this card's body.",),
        parent_group="overlay_body",
        blocked_by_section_lock=True,
    ),
    RowKind.OVERLAY_CARD_BODY_COLOUR: RowSpec(
        affordance=RowAffordance.VALUE_COLOUR,
        panel_label="body colour",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_body_colour,
        apply_action=_colour_action("body_colour"),
        colour_target=_colour_target("body_colour"),
        help_title="Body Colour",
        help_entries=(("Enter", "edit hex value"),),
        help_description=("Hex colour of this credits card body.",),
        parent_group="overlay_body",
        blocked_by_section_lock=True,
    ),
    RowKind.OVERLAY_CARD_BODY_BACKGROUND_COLOUR: RowSpec(
        affordance=RowAffordance.VALUE_COLOUR,
        panel_label="body background",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_body_background_colour,
        apply_action=_colour_action("body_background_colour", optional=True),
        colour_target=_colour_target("body_background_colour", optional=True),
        help_title="Body Background",
        help_entries=(("Enter", "edit hex value"),),
        help_description=(
            "Optional hex background colour of this credits card body.",
        ),
        parent_group="overlay_body",
        blocked_by_section_lock=True,
    ),
    RowKind.OVERLAY_CARD_OPACITY: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="background opacity",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_opacity,
        apply_horizontal=_apply_overlay_card_opacity,
        help_title="Background Opacity",
        help_description=("Background opacity of this credits card box.",),
        repeatable=True,
        parent_group="overlay",
    ),
    RowKind.OVERLAY_CARD_BACKGROUND_COLOUR: RowSpec(
        affordance=RowAffordance.VALUE_COLOUR,
        panel_label="background colour",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_background_colour,
        apply_action=_colour_action("background_colour"),
        colour_target=_colour_target("background_colour"),
        help_title="Background Colour",
        help_entries=(("Enter", "edit hex value"),),
        help_description=("Hex colour of this credits card box.",),
        parent_group="overlay",
        blocked_by_section_lock=True,
    ),
    RowKind.OVERLAY_CARD_BACKGROUND_MARGIN: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="background margin",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_background_margin,
        apply_horizontal=_apply_overlay_card_background_margin,
        help_title="Background Margin",
        help_description=(
            "Gap between this credits card box and the screen edge.",
        ),
        repeatable=True,
        parent_group="overlay",
    ),
    RowKind.OVERLAY_CARD_BACKGROUND_PADDING: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="background padding",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_background_padding,
        apply_horizontal=_apply_overlay_card_background_padding,
        help_title="Background Padding",
        help_description=(
            "Inner space between this credits card border and its text.",
        ),
        repeatable=True,
        parent_group="overlay",
    ),
    RowKind.OVERLAY_CARD_BORDER_WIDTH: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="border width",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_border_width,
        apply_horizontal=_apply_overlay_card_border_width,
        help_title="Border Width",
        help_description=(
            "Width of the border drawn around this credits card box.",
        ),
        repeatable=True,
        parent_group="overlay",
    ),
    RowKind.OVERLAY_CARD_BORDER_COLOUR: RowSpec(
        affordance=RowAffordance.VALUE_COLOUR,
        panel_label="border colour",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_border_colour,
        apply_action=_colour_action("border_colour"),
        colour_target=_colour_target("border_colour"),
        help_title="Border Colour",
        help_entries=(("Enter", "edit hex value"),),
        help_description=(
            "Hex colour of the border around this credits card box.",
        ),
        parent_group="overlay",
        blocked_by_section_lock=True,
    ),
    RowKind.OVERLAY_CARD_TIME: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="card time",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_time,
        apply_horizontal=_apply_overlay_card_time,
        help_title="Card Time",
        help_description=(
            "Opening card: seconds after the song starts (appear at).",
            "Closing card: seconds before the song ends (disappear at).",
        ),
        repeatable=True,
        parent_group="overlay_animation",
    ),
    RowKind.OVERLAY_CARD_DISPLAY_TIME: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="display time",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_display_time,
        apply_horizontal=_apply_overlay_card_display_time,
        help_title="Display Time",
        help_description=(
            "Duration this credits card stays on screen including entrance and exit.",
            "0 = stays on.",
        ),
        repeatable=True,
        parent_group="overlay_animation",
    ),
}
