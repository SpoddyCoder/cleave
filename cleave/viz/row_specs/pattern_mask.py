"""Pattern mask row specs for the live tuning overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.config_schema.render import (
    PATTERN_MASK_DENSITY_STEP,
    PATTERN_MASK_DENSITY_STEP_LARGE,
    PATTERN_MASK_FEATHER_PCT_STEP,
    PATTERN_MASK_FEATHER_PCT_STEP_LARGE,
    PATTERN_MASK_TRANSITION_STEP,
    PATTERN_MASK_TRANSITION_STEP_LARGE,
)
from cleave.pattern_mask import pattern_mask_invert_display
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_sections import apply_expand_toggle
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.tuning_view_state import TuningViewState

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

def _format_render_pattern_mask_type(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.render_pattern_mask.type

def _format_render_pattern_mask_feather(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_pattern_mask.feather_pct}%"

def _format_render_pattern_mask_density(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_pattern_mask.density:.1f}x"

def _format_render_pattern_mask_invert(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return pattern_mask_invert_display(state.render_pattern_mask.invert)

def _format_render_pattern_mask_transition(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_pattern_mask.transition:.1f}s"

def _format_render_pattern_mask_seed(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return str(state.render_pattern_mask.seed)

def _apply_render_pattern_mask_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    from cleave.viz.row_spec import row_spec
    if ctrl:
        if (
            controls.session.render_pattern_mask.locked
            and row_spec(desc.kind).can_enable_disable
        ):
            return
        controls.render_pattern_mask.set_enabled(forward)
        return
    apply_expand_toggle(
        controls, desc.kind, desc.slot, forward, card=desc.card
    )

def _apply_render_pattern_mask_type(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls.render_pattern_mask.cycle_type(forward=forward)

def _apply_render_pattern_mask_feather(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = (
        PATTERN_MASK_FEATHER_PCT_STEP_LARGE if ctrl else PATTERN_MASK_FEATHER_PCT_STEP
    )
    delta = step if forward else -step
    controls.render_pattern_mask.set_feather_pct(
        controls.session.render_pattern_mask.feather_pct + delta
    )

def _apply_render_pattern_mask_density(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = PATTERN_MASK_DENSITY_STEP_LARGE if ctrl else PATTERN_MASK_DENSITY_STEP
    delta = step if forward else -step
    controls.render_pattern_mask.set_density(
        controls.session.render_pattern_mask.density + delta
    )

def _apply_render_pattern_mask_invert(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls.render_pattern_mask.cycle_invert(forward=forward)

def _apply_render_pattern_mask_transition(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = (
        PATTERN_MASK_TRANSITION_STEP_LARGE if ctrl else PATTERN_MASK_TRANSITION_STEP
    )
    delta = step if forward else -step
    controls.render_pattern_mask.set_transition(
        controls.session.render_pattern_mask.transition + delta
    )

def _apply_render_pattern_mask_seed(
    controls: TuningControls,
    _desc: RowDescriptor,
    _forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls.render_pattern_mask.respin_seed()

def _visibility_pattern_mask(
    state: TuningViewState, _desc: RowDescriptor
) -> tuple[bool, bool]:
    return (state.render_pattern_mask.enabled, False)

SPECS: dict[RowKind, RowSpec] = {
    RowKind.RENDER_PATTERN_MASK_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="PATTERN MASK",
        present_style=RowPresentStyle.COMPOSITE_HEADER,
        apply_horizontal=_apply_render_pattern_mask_header,
        header_prefix="Render: ",
        header_suffix="PATTERN MASK",
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_pattern_mask,
        help_title="Pattern mask",
        help_description=(
            "Spatial territories for visible layers during composite.",
            "Feather 0% assigns each pixel to one layer; 100% blends at edges.",
        ),
        quick_nav_target=True,
        can_enable_disable=True,
    ),
    RowKind.RENDER_PATTERN_MASK_TYPE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="type",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_pattern_mask_type,
        apply_horizontal=_apply_render_pattern_mask_type,
        help_title="Type",
        help_entries=(("Left/Right", "cycle pattern type"),),
        help_description=("Pattern geometry used to partition the frame.",),
        repeatable=True,
        parent_group="render_pattern_mask",
    ),
    RowKind.RENDER_PATTERN_MASK_DENSITY: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="density",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_pattern_mask_density,
        apply_horizontal=_apply_render_pattern_mask_density,
        help_title="Density",
        help_description=(
            "Segments per active layer (1.0x = one strip/wedge/tile per layer).",
            "Higher multiplies how many segments cycle through visible layers.",
        ),
        repeatable=True,
        parent_group="render_pattern_mask",
    ),
    RowKind.RENDER_PATTERN_MASK_FEATHER: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="feather",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_pattern_mask_feather,
        apply_horizontal=_apply_render_pattern_mask_feather,
        help_title="Feather",
        help_entries=(
            ("Left/Right", "+/- 1%"),
            ("Ctrl+Left/Right", "+/- 10%"),
        ),
        help_description=(
            "0% hard territories (one layer per pixel).",
            "100% maximum segment overlap.",
        ),
        repeatable=True,
        parent_group="render_pattern_mask",
    ),
    RowKind.RENDER_PATTERN_MASK_INVERT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="invert",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_pattern_mask_invert,
        apply_horizontal=_apply_render_pattern_mask_invert,
        help_title="Invert",
        help_entries=(("Left/Right", "toggle invert on/off"),),
        help_description=("Reverse layer assignment order across the pattern.",),
        repeatable=True,
        parent_group="render_pattern_mask",
    ),
    RowKind.RENDER_PATTERN_MASK_TRANSITION: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="transition",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_pattern_mask_transition,
        apply_horizontal=_apply_render_pattern_mask_transition,
        help_title="Transition",
        help_description=(
            "Seconds to morph mask territories when layers toggle.",
            "0.0s applies the new partition instantly.",
        ),
        repeatable=True,
        parent_group="render_pattern_mask",
    ),
    RowKind.RENDER_PATTERN_MASK_SEED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="seed",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_pattern_mask_seed,
        apply_horizontal=_apply_render_pattern_mask_seed,
        help_title="Seed",
        help_entries=(("Left/Right", "respin seed"),),
        help_description=(
            "Persisted seed for plasma patterns.",
            "Left/Right picks a new random seed for a different field.",
        ),
        repeatable=True,
        parent_group="render_pattern_mask",
    ),
}
