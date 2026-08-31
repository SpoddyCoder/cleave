"""Render overlay card row specs for the live tuning overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.config_schema.render import (
    RENDER_OVERLAY_ANIMATION_TYPE_HELP_ENTRIES,
    RENDER_OVERLAY_SLIDE_DIRECTION_HELP_ENTRIES,
)
from cleave.viz.fonts import render_overlay_font_display
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_sections import apply_expand_toggle
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.row_specs.common import apply_expand_subheader
from cleave.viz.tuning_view_state import TuningViewState

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

def _overlay_card_block(state: TuningViewState, desc: RowDescriptor):
    assert desc.card is not None
    return getattr(state.render_overlays, desc.card)

def _overlay_card_controls(controls: TuningControls, desc: RowDescriptor):
    assert desc.card is not None
    return controls.render_overlays.card(desc.card)

def _overlay_card_block_session(controls: TuningControls, desc: RowDescriptor):
    assert desc.card is not None
    return getattr(controls.session.render_overlays, desc.card)

def overlay_card_panel_label(kind: RowKind, card: str | None) -> str | None:
    if card is None:
        return None
    if kind == RowKind.RENDER_OVERLAY_CARD_HEADER:
        return "opening card" if card == "opening_card" else "closing card"
    if kind == RowKind.RENDER_OVERLAY_CARD_TIME:
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
    return render_overlay_font_display(_overlay_card_block(state, desc).runtime.title_font)

def _format_overlay_card_title_margin_bottom(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.title_margin_bottom}px"

def _format_overlay_card_body_font_size(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.body_font_size}px"

def _format_overlay_card_body_font(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return render_overlay_font_display(_overlay_card_block(state, desc).runtime.body_font)

def _format_overlay_card_opacity(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.opacity_pct}%"

def _format_overlay_card_border_width(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.border_width}px"

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
    _ctrl: bool,
    _shift: bool,
) -> None:
    _overlay_card_controls(controls, desc).cycle_position(forward=forward)

def _apply_overlay_card_title_font_size(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_title_font_size(
        card.title_font_size + delta
    )

def _apply_overlay_card_title_font(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    _overlay_card_controls(controls, desc).cycle_title_font(forward=forward)

def _apply_overlay_card_title_margin_bottom(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_title_margin_bottom(
        card.title_margin_bottom + delta
    )

def _apply_overlay_card_body_font_size(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_body_font_size(
        card.body_font_size + delta
    )

def _apply_overlay_card_body_font(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    _overlay_card_controls(controls, desc).cycle_body_font(forward=forward)

def _apply_overlay_card_opacity(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_opacity(card.opacity_pct + delta)

def _apply_overlay_card_border_width(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_border_width(card.border_width + delta)

def _apply_overlay_card_time(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = 30.0 if ctrl else 1.0
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
    ctrl: bool,
    _shift: bool,
) -> None:
    step = 30.0 if ctrl else 1.0
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_display_time(
        card.animation.display_time + delta
    )

def _apply_overlay_card_animation_type(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    _overlay_card_controls(controls, desc).cycle_animation_type(forward=forward)

def _apply_overlay_card_slide_direction(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    _overlay_card_controls(controls, desc).cycle_slide_direction(forward=forward)

def _apply_render_overlays_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    shift: bool,
) -> None:
    from cleave.viz.row_spec import row_spec
    if shift:
        if forward:
            controls.render_overlays.enter_solo()
        else:
            controls.render_overlays.exit_solo()
        return
    if ctrl:
        if (
            controls.session.render_overlays.locked
            and row_spec(desc.kind).can_enable_disable
        ):
            return
        controls.render_overlays.set_enabled(forward)
        return
    apply_expand_toggle(
        controls, desc.kind, desc.slot, forward, card=desc.card
    )

def _apply_overlay_card_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    from cleave.viz.row_spec import row_spec
    if ctrl:
        if (
            controls.session.render_overlays.locked
            and row_spec(desc.kind).can_enable_disable
        ):
            return
        _overlay_card_controls(controls, desc).set_enabled(forward)
        return
    apply_expand_toggle(
        controls, desc.kind, desc.slot, forward, card=desc.card
    )

def _visibility_overlays(
    state: TuningViewState, _desc: RowDescriptor
) -> tuple[bool, bool]:
    block = state.render_overlays
    any_enabled = (
        block.opening_card.runtime.enabled or block.closing_card.runtime.enabled
    )
    return (any_enabled, block.solo)

SPECS: dict[RowKind, RowSpec] = {
    RowKind.RENDER_OVERLAYS_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="OVERLAYS",
        present_style=RowPresentStyle.COMPOSITE_HEADER,
        apply_horizontal=_apply_render_overlays_header,
        header_prefix="Render: ",
        header_suffix="OVERLAYS",
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_overlays,
        help_title="Credits overlays",
        help_description=(
            "Opening and closing credits cards.",
        ),
        quick_nav_target=True,
        quick_nav_always=True,
        can_enable_disable=True,
        can_solo=True,
    ),
    RowKind.RENDER_OVERLAY_CARD_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="card",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_overlay_card_header,
        fit_strategy=FitStrategy.NONE,
        help_title="Credits card",
        help_description=(
            "Opening card at the start of the song, or closing card near the end.",
        ),
        is_sub_header=True,
        can_enable_disable=True,
        parent_group="render_overlay",
    ),
    RowKind.RENDER_OVERLAY_CARD_ANIMATION_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="animation",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="Card animation",
        help_description=(
            "Entrance and exit motion for this credits card.",
        ),
        is_sub_header=True,
        parent_group="render_overlay",
    ),
    RowKind.RENDER_OVERLAY_CARD_ANIMATION_TYPE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="type",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_animation_type,
        apply_horizontal=_apply_overlay_card_animation_type,
        help_title="Animation type",
        help_entries=(("Left/Right", "cycle type"),),
        help_description=("How this credits card enters and leaves the screen.",),
        help_mode_entries=RENDER_OVERLAY_ANIMATION_TYPE_HELP_ENTRIES,
        repeatable=True,
        parent_group="render_overlay_animation",
    ),
    RowKind.RENDER_OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="slide-direction",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_slide_direction,
        apply_horizontal=_apply_overlay_card_slide_direction,
        help_title="Slide direction",
        help_entries=(("Left/Right", "cycle direction"),),
        help_description=(
            "Edge this credits card travels from on entrance (reverse on exit).",
        ),
        help_mode_entries=RENDER_OVERLAY_SLIDE_DIRECTION_HELP_ENTRIES,
        repeatable=True,
        parent_group="render_overlay_animation",
    ),
    RowKind.RENDER_OVERLAY_CARD_POSITION: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="position",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_position,
        apply_horizontal=_apply_overlay_card_position,
        help_title="Position",
        help_description=(
            "Screen corner where this credits card appears.",
        ),
        repeatable=True,
        parent_group="render_overlay",
    ),
    RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="title",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="Card title",
        help_description=("Title line of this credits card.",),
        is_sub_header=True,
        parent_group="render_overlay",
    ),
    RowKind.RENDER_OVERLAY_CARD_TITLE_FONT_SIZE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="font size",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_title_font_size,
        apply_horizontal=_apply_overlay_card_title_font_size,
        help_title="Title font size",
        help_description=("Font size of this credits card title.",),
        repeatable=True,
        parent_group="render_overlay_title",
    ),
    RowKind.RENDER_OVERLAY_CARD_TITLE_FONT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="font",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_title_font,
        apply_horizontal=_apply_overlay_card_title_font,
        fit_strategy=FitStrategy.COUNTER_LABEL,
        help_title="Title font",
        help_description=("Font used for this credits card title.",),
        repeatable=True,
        parent_group="render_overlay_title",
    ),
    RowKind.RENDER_OVERLAY_CARD_TITLE_MARGIN_BOTTOM: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="margin bottom",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_title_margin_bottom,
        apply_horizontal=_apply_overlay_card_title_margin_bottom,
        help_title="Title margin bottom",
        help_description=(
            "Gap between the title and body in this credits card box.",
        ),
        repeatable=True,
        parent_group="render_overlay_title",
    ),
    RowKind.RENDER_OVERLAY_CARD_BODY_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="body",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="Card body",
        help_description=("Body block of this credits card.",),
        is_sub_header=True,
        parent_group="render_overlay",
    ),
    RowKind.RENDER_OVERLAY_CARD_BODY_FONT_SIZE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="font size",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_body_font_size,
        apply_horizontal=_apply_overlay_card_body_font_size,
        help_title="Body font size",
        help_description=("Font size of this credits card body.",),
        repeatable=True,
        parent_group="render_overlay_body",
    ),
    RowKind.RENDER_OVERLAY_CARD_BODY_FONT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="font",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_body_font,
        apply_horizontal=_apply_overlay_card_body_font,
        fit_strategy=FitStrategy.COUNTER_LABEL,
        help_title="Body font",
        help_description=("Font used for this credits card body.",),
        repeatable=True,
        parent_group="render_overlay_body",
    ),
    RowKind.RENDER_OVERLAY_CARD_OPACITY: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="background opacity",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_opacity,
        apply_horizontal=_apply_overlay_card_opacity,
        help_title="Background opacity",
        help_description=("Background opacity of this credits card box.",),
        repeatable=True,
        parent_group="render_overlay",
    ),
    RowKind.RENDER_OVERLAY_CARD_BORDER_WIDTH: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="border width",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_border_width,
        apply_horizontal=_apply_overlay_card_border_width,
        help_title="Border width",
        help_description=(
            "Width of the border drawn around this credits card box.",
        ),
        repeatable=True,
        parent_group="render_overlay",
    ),
    RowKind.RENDER_OVERLAY_CARD_TIME: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="card time",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_time,
        apply_horizontal=_apply_overlay_card_time,
        help_title="Card time",
        help_description=(
            "Opening card: seconds after the song starts (appear at).",
            "Closing card: seconds before the song ends (disappear at).",
        ),
        repeatable=True,
        parent_group="render_overlay_animation",
    ),
    RowKind.RENDER_OVERLAY_CARD_DISPLAY_TIME: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="display time",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_display_time,
        apply_horizontal=_apply_overlay_card_display_time,
        help_title="Display time",
        help_description=(
            "Duration this credits card stays on screen including entrance and exit.",
            "0 = stays on.",
        ),
        repeatable=True,
        parent_group="render_overlay_animation",
    ),
}
