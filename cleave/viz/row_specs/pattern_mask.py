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
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.row_specs.common import lock_text, on_off_text
from cleave.viz.tuning_view_state import TuningViewState

from cleave.config_schema.render import PATTERN_MASK_TYPES
from cleave.viz.row_specs.common import bool_choice, options_choice
if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

def _format_pattern_mask_type(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.pattern_mask.type

def _format_pattern_mask_feather(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.pattern_mask.feather_pct}%"

def _format_pattern_mask_density(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.pattern_mask.density:.1f}x"

def _format_pattern_mask_invert(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return pattern_mask_invert_display(state.pattern_mask.invert)

def _format_pattern_mask_transition(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.pattern_mask.transition:.1f}s"

def _format_pattern_mask_seed(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return str(state.pattern_mask.seed)

def _toggle_pattern_mask_enabled(
    controls: TuningControls, _desc: RowDescriptor
) -> None:
    if controls.session.pattern_mask.locked:
        return
    enabled = controls.session.pattern_mask.enabled
    controls.pattern_mask.set_enabled(not enabled)


def _apply_pattern_mask_type(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    controls.pattern_mask.step_type(delta=1 if forward else -1)

def _apply_pattern_mask_feather(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    step = (
        PATTERN_MASK_FEATHER_PCT_STEP_LARGE if large else PATTERN_MASK_FEATHER_PCT_STEP
    )
    delta = step if forward else -step
    controls.pattern_mask.set_feather_pct(
        controls.session.pattern_mask.feather_pct + delta
    )

def _apply_pattern_mask_density(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    step = PATTERN_MASK_DENSITY_STEP_LARGE if large else PATTERN_MASK_DENSITY_STEP
    delta = step if forward else -step
    controls.pattern_mask.set_density(
        controls.session.pattern_mask.density + delta
    )

def _apply_pattern_mask_invert(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    controls.pattern_mask.step_invert(forward=forward)

def _apply_pattern_mask_transition(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    step = (
        PATTERN_MASK_TRANSITION_STEP_LARGE if large else PATTERN_MASK_TRANSITION_STEP
    )
    delta = step if forward else -step
    controls.pattern_mask.set_transition(
        controls.session.pattern_mask.transition + delta
    )

def _apply_pattern_mask_seed(
    controls: TuningControls,
    _desc: RowDescriptor,
    _forward: bool,
    _large: bool,
) -> None:
    controls.pattern_mask.respin_seed()

def _visibility_pattern_mask(
    state: TuningViewState, _desc: RowDescriptor
) -> tuple[bool, bool]:
    return (state.pattern_mask.enabled, False)

def _format_pattern_mask_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return on_off_text(state.pattern_mask.enabled)


def _format_pattern_mask_locked(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return lock_text(state.pattern_mask.locked)


def _apply_pattern_mask_enabled(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    controls.pattern_mask.set_enabled(forward)


def _apply_pattern_mask_locked(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    if controls.session.pattern_mask.locked != forward:
        controls.toggle_pattern_mask_locked()


def _jump_pattern_mask_type(
    controls: TuningControls, _desc: RowDescriptor, delta: int
) -> None:
    controls.pattern_mask.step_type(delta=delta)

SPECS: dict[RowKind, RowSpec] = {
    RowKind.PATTERN_MASK_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="Pattern Mask",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_pattern_mask,
        help_title="Pattern mask",
        help_description=(
            "Spatial territories for visible layers during composite.",
            "Feather 0% assigns each pixel to one layer; 100% blends at edges.",
            "Replaces layer compositing, so each layer's Compositing rows (blend mode, opacity) are greyed out and ignored.",
        ),
        toggle_enabled=_toggle_pattern_mask_enabled,
    ),
    RowKind.PATTERN_MASK_PATTERN_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="pattern",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Pattern",
        help_description=(
            "Geometry that splits the frame between visible layers.",
        ),
        parent_group="pattern_mask",
    ),
    RowKind.PATTERN_MASK_EDGES_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="edges & motion",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Edges & motion",
        help_description=(
            "How soft territory edges are, and how long the layout morphs when layers toggle.",
        ),
        parent_group="pattern_mask",
    ),
    RowKind.PATTERN_MASK_ENABLED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="enabled",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_pattern_mask_enabled,
        apply_horizontal=_apply_pattern_mask_enabled,
        choice=bool_choice(lambda s, _d: s.pattern_mask.enabled),
        help_title="Pattern mask enabled",
        help_description=(
            "When on, the mask replaces each layer's Compositing rows.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.PATTERN_MASK_LOCKED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="lock",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_pattern_mask_locked,
        apply_horizontal=_apply_pattern_mask_locked,
        choice=bool_choice(lambda s, _d: s.pattern_mask.locked, lock_text),
        help_title="Pattern mask lock",
        help_description=("Locked pattern mask settings cannot be edited.",),
        blocked_by_section_lock=False,
    ),
    RowKind.PATTERN_MASK_TYPE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="type",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_pattern_mask_type,
        apply_horizontal=_apply_pattern_mask_type,
        choice=options_choice(PATTERN_MASK_TYPES, lambda s, _d: s.pattern_mask.type, jump=_jump_pattern_mask_type),
        help_title="Type",
        help_entries=(("Left/Right", "choose pattern type"),),
        help_description=("Pattern geometry used to partition the frame.",),
        repeatable=True,
        parent_group="pattern_mask",
    ),
    RowKind.PATTERN_MASK_DENSITY: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="density",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_pattern_mask_density,
        apply_horizontal=_apply_pattern_mask_density,
        help_title="Density",
        help_description=(
            "Segments per active layer (1.0x = one strip/bar/wedge/tile per layer).",
            "Higher multiplies how many segments cycle through visible layers.",
        ),
        repeatable=True,
        parent_group="pattern_mask",
    ),
    RowKind.PATTERN_MASK_FEATHER: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="feather",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_pattern_mask_feather,
        apply_horizontal=_apply_pattern_mask_feather,
        help_title="Feather",
        help_entries=(
            ("Left/Right", "+/- 1%"),
            ("PgUp/PgDn", "+/- 10%"),
        ),
        help_description=(
            "0% hard territories (one layer per pixel).",
            "100% maximum segment overlap.",
        ),
        repeatable=True,
        parent_group="pattern_mask",
    ),
    RowKind.PATTERN_MASK_INVERT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="invert",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_pattern_mask_invert,
        apply_horizontal=_apply_pattern_mask_invert,
        choice=bool_choice(lambda s, _d: s.pattern_mask.invert, pattern_mask_invert_display),
        help_title="Invert",
        help_entries=(("Left/Right", "off / on"),),
        help_description=("Reverse layer assignment order across the pattern.",),
        repeatable=True,
        parent_group="pattern_mask",
    ),
    RowKind.PATTERN_MASK_TRANSITION: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="transition",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_pattern_mask_transition,
        apply_horizontal=_apply_pattern_mask_transition,
        help_title="Transition",
        help_description=(
            "Seconds to morph mask territories when layers toggle.",
            "0.0s applies the new partition instantly.",
        ),
        repeatable=True,
        parent_group="pattern_mask",
    ),
    RowKind.PATTERN_MASK_SEED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="seed",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_pattern_mask_seed,
        apply_horizontal=_apply_pattern_mask_seed,
        help_title="Seed",
        help_entries=(("Left/Right", "respin seed"),),
        help_description=(
            "Persisted seed for plasma patterns.",
            "Left/Right picks a new random seed for a different field.",
        ),
        repeatable=True,
        parent_group="pattern_mask",
    ),
}
