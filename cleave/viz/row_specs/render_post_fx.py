"""Render post-FX row specs for the live tuning overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.config_schema.render import (
    CHROMA_BOOST_APPLY_MODE_HELP_ENTRIES,
    CHROMA_BOOST_VARIANT_HELP_ENTRIES,
    HIGHLIGHT_ROLLOFF_APPLY_MODE_HELP_ENTRIES,
    HIGHLIGHT_ROLLOFF_CURVE_HELP_ENTRIES,
)
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_sections import apply_expand_toggle
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.row_specs.common import apply_expand_subheader
from cleave.viz.tuning_view_state import TuningViewState

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

def _format_render_post_fx_fade_in(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.fade_in:.1f}s"

def _format_render_post_fx_fade_out(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.fade_out:.1f}s"

def _format_render_post_fx_highlight_rolloff_mode(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.render_post_fx.highlight_rolloff.mode

def _format_render_post_fx_highlight_rolloff_curve(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.render_post_fx.highlight_rolloff.curve

def _format_render_post_fx_highlight_rolloff_threshold(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.highlight_rolloff.threshold_pct}%"

def _format_render_post_fx_highlight_rolloff_ceiling(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.highlight_rolloff.ceiling_pct}%"

def _format_render_post_fx_highlight_rolloff_strength(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.highlight_rolloff.strength_pct}%"

def _format_render_post_fx_highlight_rolloff_softness(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.highlight_rolloff.softness_pct}%"

def _format_render_post_fx_highlight_rolloff_desaturation(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.highlight_rolloff.desaturation_pct}%"

def _format_render_post_fx_chroma_boost_mode(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.render_post_fx.chroma_boost.mode

def _format_render_post_fx_chroma_boost_variant(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.render_post_fx.chroma_boost.variant

def _format_render_post_fx_chroma_boost_amount(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.chroma_boost.amount_pct}%"

def _apply_render_post_fx_fade_in(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10.0 if ctrl else 1.0
    delta = step if forward else -step
    controls.render_post_fx.set_fade_in(
        controls.session.render_post_fx.fade_in + delta
    )

def _apply_render_post_fx_fade_out(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10.0 if ctrl else 1.0
    delta = step if forward else -step
    controls.render_post_fx.set_fade_out(
        controls.session.render_post_fx.fade_out + delta
    )

def _apply_render_post_fx_highlight_rolloff_mode(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls.render_post_fx.cycle_highlight_rolloff_mode(forward=forward)

def _apply_render_post_fx_highlight_rolloff_curve(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls.render_post_fx.cycle_highlight_rolloff_curve(forward=forward)

def _apply_render_post_fx_highlight_rolloff_threshold(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    hr = controls.session.render_post_fx.highlight_rolloff
    controls.render_post_fx.set_highlight_rolloff_threshold_pct(
        hr.threshold_pct + delta
    )

def _apply_render_post_fx_highlight_rolloff_ceiling(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    hr = controls.session.render_post_fx.highlight_rolloff
    controls.render_post_fx.set_highlight_rolloff_ceiling_pct(
        hr.ceiling_pct + delta
    )

def _apply_render_post_fx_highlight_rolloff_strength(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    hr = controls.session.render_post_fx.highlight_rolloff
    controls.render_post_fx.set_highlight_rolloff_strength_pct(
        hr.strength_pct + delta
    )

def _apply_render_post_fx_highlight_rolloff_softness(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    hr = controls.session.render_post_fx.highlight_rolloff
    controls.render_post_fx.set_highlight_rolloff_softness_pct(
        hr.softness_pct + delta
    )

def _apply_render_post_fx_highlight_rolloff_desaturation(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    hr = controls.session.render_post_fx.highlight_rolloff
    controls.render_post_fx.set_highlight_rolloff_desaturation_pct(
        hr.desaturation_pct + delta
    )

def _apply_render_post_fx_chroma_boost_mode(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls.render_post_fx.cycle_chroma_boost_mode(forward=forward)

def _apply_render_post_fx_chroma_boost_variant(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls.render_post_fx.cycle_chroma_boost_variant(forward=forward)

def _apply_render_post_fx_chroma_boost_amount(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    cb = controls.session.render_post_fx.chroma_boost
    controls.render_post_fx.set_chroma_boost_amount_pct(cb.amount_pct + delta)

def _apply_render_post_fx_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    from cleave.viz.row_spec import row_spec
    if ctrl:
        if (
            controls.session.render_post_fx.locked
            and row_spec(desc.kind).can_enable_disable
        ):
            return
        controls.render_post_fx.set_enabled(forward)
        return
    apply_expand_toggle(
        controls, desc.kind, desc.slot, forward, card=desc.card
    )

def _visibility_post_fx(
    state: TuningViewState, _desc: RowDescriptor
) -> tuple[bool, bool]:
    block = state.render_post_fx
    return (block.enabled, block.solo)

SPECS: dict[RowKind, RowSpec] = {
    RowKind.RENDER_POST_FX_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="POST FX",
        present_style=RowPresentStyle.COMPOSITE_HEADER,
        apply_horizontal=_apply_render_post_fx_header,
        header_prefix="Render: ",
        header_suffix="POST FX",
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_post_fx,
        help_title="Post FX",
        help_description=(
            "Post-processing effects applied during final compositing.",
        ),
        quick_nav_target=True,
        can_enable_disable=True,
    ),
    RowKind.RENDER_POST_FX_FADE_IN: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="fade in",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_fade_in,
        apply_horizontal=_apply_render_post_fx_fade_in,
        help_title="Fade in",
        help_description=(
            "Duration of the fade-in at the start of the render.",
        ),
        repeatable=True,
        parent_group="render_post_fx",
    ),
    RowKind.RENDER_POST_FX_FADE_OUT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="fade out",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_fade_out,
        apply_horizontal=_apply_render_post_fx_fade_out,
        help_title="Fade out",
        help_description=(
            "Duration of the fade-out at the end of the render.",
        ),
        repeatable=True,
        parent_group="render_post_fx",
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="highlight rolloff",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="Highlight rolloff",
        help_description=(
            "Compresses bright hotspots during layer compositing.",
            "Prevents stacked black-key layers from washing out to white.",
            "Preserves hue by scaling RGB to the compressed luminance.",
            "With render.hdr_compositing enabled, a baseline display shoulder",
            "runs automatically; composite rolloff here is extra control.",
            "Per-layer rolloff is optional and can stay light.",
        ),
        is_sub_header=True,
        parent_group="render_post_fx",
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_MODE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="mode",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_highlight_rolloff_mode,
        apply_horizontal=_apply_render_post_fx_highlight_rolloff_mode,
        help_title="Mode",
        help_entries=(("Left/Right", "cycle mode"),),
        help_description=("Where highlight rolloff is applied.",),
        help_mode_entries=HIGHLIGHT_ROLLOFF_APPLY_MODE_HELP_ENTRIES,
        repeatable=True,
        parent_group="render_post_fx_highlight_rolloff",
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CURVE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="curve",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_highlight_rolloff_curve,
        apply_horizontal=_apply_render_post_fx_highlight_rolloff_curve,
        help_title="Curve",
        help_entries=(("Left/Right", "cycle curve"),),
        help_description=("Shoulder curve used above the soft knee.",),
        help_mode_entries=HIGHLIGHT_ROLLOFF_CURVE_HELP_ENTRIES,
        repeatable=True,
        parent_group="render_post_fx_highlight_rolloff",
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="threshold",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_highlight_rolloff_threshold,
        apply_horizontal=_apply_render_post_fx_highlight_rolloff_threshold,
        help_title="Threshold",
        help_description=(
            "Rec.709 luminance level where compression begins.",
            "Lower = compression starts earlier, more of the image affected.",
            "Higher = only the brightest peaks are compressed.",
        ),
        repeatable=True,
        parent_group="render_post_fx_highlight_rolloff",
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CEILING: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="ceiling",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_highlight_rolloff_ceiling,
        apply_horizontal=_apply_render_post_fx_highlight_rolloff_ceiling,
        help_title="Ceiling",
        help_description=(
            "Luminance target for fully compressed highlights.",
            "At full strength, saturated whites are pulled down to this level.",
            "Must be at or below threshold (e.g. threshold 78%, ceiling 65%).",
        ),
        repeatable=True,
        parent_group="render_post_fx_highlight_rolloff",
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_STRENGTH: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="strength",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_highlight_rolloff_strength,
        apply_horizontal=_apply_render_post_fx_highlight_rolloff_strength,
        help_title="Strength",
        help_description=(
            "How strongly highlights above the threshold are compressed.",
            "100% = full compression toward the ceiling.",
            "Above 100% (up to 200%) = extra aggressive pull toward the ceiling.",
            "Lower = gentler rolloff with more retained brightness.",
        ),
        repeatable=True,
        parent_group="render_post_fx_highlight_rolloff",
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_SOFTNESS: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="softness",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_highlight_rolloff_softness,
        apply_horizontal=_apply_render_post_fx_highlight_rolloff_softness,
        help_title="Softness",
        help_description=(
            "Width of the soft knee above the threshold.",
            "Higher = wider, more gradual transition into compression.",
            "Lower = tighter transition right at the threshold.",
        ),
        repeatable=True,
        parent_group="render_post_fx_highlight_rolloff",
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_DESATURATION: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="desaturation",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_highlight_rolloff_desaturation,
        apply_horizontal=_apply_render_post_fx_highlight_rolloff_desaturation,
        help_title="Desaturation",
        help_description=(
            "How much compressed highlights lose color purity.",
            "Higher = less pure white, more tinted or muted highlights.",
            "Hue is preserved during luminance scaling, then pulled toward gray.",
        ),
        repeatable=True,
        parent_group="render_post_fx_highlight_rolloff",
    ),
    RowKind.RENDER_POST_FX_CHROMA_BOOST_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="chroma boost",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="Chroma boost",
        help_description=(
            "Boosts saturation or vibrance around Rec.709 luma.",
            "Useful after highlight compression to restore perceived color.",
            "Vibrance spares already-saturated pixels to avoid clipping primaries.",
        ),
        is_sub_header=True,
        parent_group="render_post_fx",
    ),
    RowKind.RENDER_POST_FX_CHROMA_BOOST_MODE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="mode",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_chroma_boost_mode,
        apply_horizontal=_apply_render_post_fx_chroma_boost_mode,
        help_title="Mode",
        help_entries=(("Left/Right", "cycle mode"),),
        help_description=("Where chroma boost is applied.",),
        help_mode_entries=CHROMA_BOOST_APPLY_MODE_HELP_ENTRIES,
        repeatable=True,
        parent_group="render_post_fx_chroma_boost",
    ),
    RowKind.RENDER_POST_FX_CHROMA_BOOST_VARIANT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="variant",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_chroma_boost_variant,
        apply_horizontal=_apply_render_post_fx_chroma_boost_variant,
        help_title="Variant",
        help_entries=(("Left/Right", "cycle variant"),),
        help_description=("Saturation vs vibrance weighting.",),
        help_mode_entries=CHROMA_BOOST_VARIANT_HELP_ENTRIES,
        repeatable=True,
        parent_group="render_post_fx_chroma_boost",
    ),
    RowKind.RENDER_POST_FX_CHROMA_BOOST_AMOUNT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="amount",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_chroma_boost_amount,
        apply_horizontal=_apply_render_post_fx_chroma_boost_amount,
        help_title="Amount",
        help_description=(
            "Chroma boost strength as a percentage.",
            "0% disables the pass even when mode is not off.",
        ),
        repeatable=True,
        parent_group="render_post_fx_chroma_boost",
    ),
}
