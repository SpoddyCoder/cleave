"""Render post-FX row specs for the live tuning overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.config_schema.render import (
    CHROMA_BOOST_APPLY_MODE_HELP_ENTRIES,
    CHROMA_BOOST_VARIANT_HELP_ENTRIES,
    FADE_CURVE_HELP_ENTRIES,
    HIGHLIGHT_ROLLOFF_APPLY_MODE_HELP_ENTRIES,
    HIGHLIGHT_ROLLOFF_CURVE_HELP_ENTRIES,
    VISUAL_LIMITER_RATIO_STEP,
    VISUAL_LIMITER_RELEASE_STEP,
    VISUAL_LIMITER_THRESHOLD_STEP,
)
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.row_specs.common import lock_text, on_off_text
from cleave.viz.tuning_view_state import TuningViewState

from cleave.config_schema.render import CHROMA_BOOST_APPLY_MODES, CHROMA_BOOST_VARIANTS, FADE_CURVES, HIGHLIGHT_ROLLOFF_APPLY_MODES, HIGHLIGHT_ROLLOFF_CURVES
from cleave.viz.row_specs.common import bool_choice, options_choice
if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

def _format_fade_seconds(value: float) -> str:
    return f"{value:.1f}s"

def _format_post_fx_fade_in_start(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return _format_fade_seconds(state.post_fx.fade.fade_in.start)

def _format_post_fx_fade_in_end(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return _format_fade_seconds(state.post_fx.fade.fade_in.end)

def _format_post_fx_fade_in_type(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.post_fx.fade.fade_in.type

def _format_post_fx_fade_out_start(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return _format_fade_seconds(state.post_fx.fade.fade_out.start)

def _format_post_fx_fade_out_end(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return _format_fade_seconds(state.post_fx.fade.fade_out.end)

def _format_post_fx_fade_out_type(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.post_fx.fade.fade_out.type

def _format_post_fx_highlight_rolloff_mode(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.post_fx.highlight_rolloff.mode

def _format_post_fx_highlight_rolloff_curve(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.post_fx.highlight_rolloff.curve

def _format_post_fx_highlight_rolloff_threshold(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.post_fx.highlight_rolloff.threshold_pct}%"

def _format_post_fx_highlight_rolloff_ceiling(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.post_fx.highlight_rolloff.ceiling_pct}%"

def _format_post_fx_highlight_rolloff_strength(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.post_fx.highlight_rolloff.strength_pct}%"

def _format_post_fx_highlight_rolloff_softness(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.post_fx.highlight_rolloff.softness_pct}%"

def _format_post_fx_highlight_rolloff_desaturation(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.post_fx.highlight_rolloff.desaturation_pct}%"

def _format_post_fx_chroma_boost_mode(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.post_fx.chroma_boost.mode

def _format_post_fx_chroma_boost_variant(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.post_fx.chroma_boost.variant

def _format_post_fx_chroma_boost_amount(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.post_fx.chroma_boost.amount_pct}%"

def _fade_step(forward: bool, large: bool) -> float:
    step = 10.0 if large else 1.0
    return step if forward else -step

def _apply_post_fx_fade_in_start(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    fin = controls.session.post_fx.fade.fade_in
    controls.post_fx.set_fade_start(
        "fade_in", fin.start + _fade_step(forward, large)
    )

def _apply_post_fx_fade_in_end(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    fin = controls.session.post_fx.fade.fade_in
    controls.post_fx.set_fade_end(
        "fade_in", fin.end + _fade_step(forward, large)
    )

def _apply_post_fx_fade_in_type(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.post_fx.step_fade_type("fade_in", delta=1 if forward else -1)

def _apply_post_fx_fade_out_start(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    fout = controls.session.post_fx.fade.fade_out
    controls.post_fx.set_fade_start(
        "fade_out", fout.start + _fade_step(forward, large)
    )

def _apply_post_fx_fade_out_end(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    fout = controls.session.post_fx.fade.fade_out
    controls.post_fx.set_fade_end(
        "fade_out", fout.end + _fade_step(forward, large)
    )

def _apply_post_fx_fade_out_type(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.post_fx.step_fade_type("fade_out", delta=1 if forward else -1)

def _apply_post_fx_highlight_rolloff_mode(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.post_fx.step_highlight_rolloff_mode(forward=forward)

def _apply_post_fx_highlight_rolloff_curve(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.post_fx.step_highlight_rolloff_curve(forward=forward)

def _apply_post_fx_highlight_rolloff_threshold(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    step = 10 if large else 1
    delta = step if forward else -step
    hr = controls.session.post_fx.highlight_rolloff
    controls.post_fx.set_highlight_rolloff_threshold_pct(
        hr.threshold_pct + delta
    )

def _apply_post_fx_highlight_rolloff_ceiling(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    step = 10 if large else 1
    delta = step if forward else -step
    hr = controls.session.post_fx.highlight_rolloff
    controls.post_fx.set_highlight_rolloff_ceiling_pct(
        hr.ceiling_pct + delta
    )

def _apply_post_fx_highlight_rolloff_strength(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    step = 10 if large else 1
    delta = step if forward else -step
    hr = controls.session.post_fx.highlight_rolloff
    controls.post_fx.set_highlight_rolloff_strength_pct(
        hr.strength_pct + delta
    )

def _apply_post_fx_highlight_rolloff_softness(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    step = 10 if large else 1
    delta = step if forward else -step
    hr = controls.session.post_fx.highlight_rolloff
    controls.post_fx.set_highlight_rolloff_softness_pct(
        hr.softness_pct + delta
    )

def _apply_post_fx_highlight_rolloff_desaturation(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    step = 10 if large else 1
    delta = step if forward else -step
    hr = controls.session.post_fx.highlight_rolloff
    controls.post_fx.set_highlight_rolloff_desaturation_pct(
        hr.desaturation_pct + delta
    )

def _apply_post_fx_chroma_boost_mode(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.post_fx.step_chroma_boost_mode(forward=forward)

def _apply_post_fx_chroma_boost_variant(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.post_fx.step_chroma_boost_variant(forward=forward)

def _apply_post_fx_chroma_boost_amount(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    step = 10 if large else 1
    delta = step if forward else -step
    cb = controls.session.post_fx.chroma_boost
    controls.post_fx.set_chroma_boost_amount_pct(cb.amount_pct + delta)

def _format_post_fx_limiter_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return "on" if state.post_fx.limiter.enabled else "off"

def _apply_post_fx_limiter_enabled(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    controls.post_fx.set_limiter_enabled(forward)

def _format_post_fx_limiter_threshold(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{int(round(state.post_fx.limiter.threshold * 100))}%"

def _apply_post_fx_limiter_threshold(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    del _large
    lim = controls.session.post_fx.limiter
    delta = VISUAL_LIMITER_THRESHOLD_STEP if forward else -VISUAL_LIMITER_THRESHOLD_STEP
    controls.post_fx.set_limiter_threshold(round(lim.threshold + delta, 2))

def _format_post_fx_limiter_ratio(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.post_fx.limiter.ratio:.1f}:1"

def _apply_post_fx_limiter_ratio(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    del _large
    lim = controls.session.post_fx.limiter
    delta = VISUAL_LIMITER_RATIO_STEP if forward else -VISUAL_LIMITER_RATIO_STEP
    controls.post_fx.set_limiter_ratio(round(lim.ratio + delta, 1))

def _format_post_fx_limiter_release(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.post_fx.limiter.release:.1f}s"

def _apply_post_fx_limiter_release(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    del _large
    lim = controls.session.post_fx.limiter
    delta = VISUAL_LIMITER_RELEASE_STEP if forward else -VISUAL_LIMITER_RELEASE_STEP
    controls.post_fx.set_limiter_release(round(lim.release + delta, 1))

def _toggle_post_fx_enabled(
    controls: TuningControls, _desc: RowDescriptor
) -> None:
    if controls.session.post_fx.locked:
        return
    enabled = controls.session.post_fx.enabled
    controls.post_fx.set_enabled(not enabled)


def _visibility_post_fx(
    state: TuningViewState, _desc: RowDescriptor
) -> tuple[bool, bool]:
    block = state.post_fx
    return (block.enabled, block.solo)

def _format_post_fx_enabled(state: TuningViewState, _desc: RowDescriptor) -> str:
    return on_off_text(state.post_fx.enabled)


def _format_post_fx_locked(state: TuningViewState, _desc: RowDescriptor) -> str:
    return lock_text(state.post_fx.locked)


def _apply_post_fx_enabled(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    controls.post_fx.set_enabled(forward)


def _apply_post_fx_locked(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    if controls.session.post_fx.locked != forward:
        controls.toggle_post_fx_locked()


def _jump_post_fx_fade_in_type(
    controls: TuningControls, _desc: RowDescriptor, delta: int
) -> None:
    controls.post_fx.step_fade_type("fade_in", delta=delta)

def _jump_post_fx_fade_out_type(
    controls: TuningControls, _desc: RowDescriptor, delta: int
) -> None:
    controls.post_fx.step_fade_type("fade_out", delta=delta)

SPECS: dict[RowKind, RowSpec] = {
    RowKind.POST_FX_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="Post-FX",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_post_fx,
        help_title="Post FX",
        help_description=(
            "Post-processing effects on the final picture.",
        ),
        toggle_enabled=_toggle_post_fx_enabled,
    ),
    RowKind.POST_FX_ENABLED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="enabled",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_enabled,
        apply_horizontal=_apply_post_fx_enabled,
        choice=bool_choice(lambda s, _d: s.post_fx.enabled),
        help_title="Post FX Enabled",
        help_description=(
            "Turns fade, highlight rolloff, and chroma boost on or off.",
            "The visual limiter has its own switch.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.POST_FX_LOCKED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="lock",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_locked,
        apply_horizontal=_apply_post_fx_locked,
        choice=bool_choice(lambda s, _d: s.post_fx.locked, lock_text),
        help_title="Post FX Lock",
        help_description=("When locked, you cannot change the Post FX settings.",),
        blocked_by_section_lock=False,
    ),
    RowKind.POST_FX_FADE_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="fade",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Fade",
        help_description=(
            "Fades the picture in at the start of the song and out at the end.",
        ),
        parent_group="post_fx",
    ),
    RowKind.POST_FX_FADE_IN_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="fade in",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Fade In",
        help_description=(
            "Times count from the start of the song.",
            "The picture fades in between Start and End.",
        ),
        parent_group="post_fx_fade",
    ),
    RowKind.POST_FX_FADE_IN_START: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="start",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_fade_in_start,
        apply_horizontal=_apply_post_fx_fade_in_start,
        help_title="Start",
        help_description=(
            "The fade-in starts this many seconds after the song starts.",
        ),
        repeatable=True,
        parent_group="post_fx_fade_in",
    ),
    RowKind.POST_FX_FADE_IN_END: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="end",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_fade_in_end,
        apply_horizontal=_apply_post_fx_fade_in_end,
        help_title="End",
        help_description=(
            "The fade-in ends this many seconds after the song starts.",
            "It cannot be before Start.",
        ),
        repeatable=True,
        parent_group="post_fx_fade_in",
    ),
    RowKind.POST_FX_FADE_IN_TYPE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="type",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_fade_in_type,
        apply_horizontal=_apply_post_fx_fade_in_type,
        choice=options_choice(FADE_CURVES, lambda s, _d: s.post_fx.fade.fade_in.type, jump=_jump_post_fx_fade_in_type),
        help_title="Type",
        help_entries=(("Left/Right", "choose type"),),
        help_description=("The shape of the fade.",),
        help_mode_entries=FADE_CURVE_HELP_ENTRIES,
        repeatable=True,
        parent_group="post_fx_fade_in",
    ),
    RowKind.POST_FX_FADE_OUT_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="fade out",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Fade Out",
        help_description=(
            "Times count back from the end of the song.",
            "The picture fades out between Start and End.",
            "Start is a larger number than End.",
        ),
        parent_group="post_fx_fade",
    ),
    RowKind.POST_FX_FADE_OUT_START: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="start",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_fade_out_start,
        apply_horizontal=_apply_post_fx_fade_out_start,
        help_title="Start",
        help_description=(
            "The fade-out starts this many seconds before the song ends.",
            "Start is a larger number than End.",
        ),
        repeatable=True,
        parent_group="post_fx_fade_out",
    ),
    RowKind.POST_FX_FADE_OUT_END: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="end",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_fade_out_end,
        apply_horizontal=_apply_post_fx_fade_out_end,
        help_title="End",
        help_description=(
            "The fade-out ends this many seconds before the song ends.",
        ),
        repeatable=True,
        parent_group="post_fx_fade_out",
    ),
    RowKind.POST_FX_FADE_OUT_TYPE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="type",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_fade_out_type,
        apply_horizontal=_apply_post_fx_fade_out_type,
        choice=options_choice(FADE_CURVES, lambda s, _d: s.post_fx.fade.fade_out.type, jump=_jump_post_fx_fade_out_type),
        help_title="Type",
        help_entries=(("Left/Right", "choose type"),),
        help_description=(
            "The shape of the fade.",
        ),
        help_mode_entries=FADE_CURVE_HELP_ENTRIES,
        repeatable=True,
        parent_group="post_fx_fade_out",
    ),
    RowKind.POST_FX_HIGHLIGHT_ROLLOFF_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="highlight rolloff",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Highlight Rolloff",
        help_description=(
            "Makes very bright areas less bright when the layers are combined.",
            "This stops stacked black-key layers from becoming flat white.",
            "Colours keep their hue.",
            "When HDR Compositing is on, a light rolloff always runs.",
            "These settings add to it.",
        ),
        parent_group="post_fx",
    ),
    RowKind.POST_FX_HIGHLIGHT_ROLLOFF_MODE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="mode",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_highlight_rolloff_mode,
        apply_horizontal=_apply_post_fx_highlight_rolloff_mode,
        choice=options_choice(HIGHLIGHT_ROLLOFF_APPLY_MODES, lambda s, _d: s.post_fx.highlight_rolloff.mode),
        help_title="Mode",
        help_entries=(("Left/Right", "choose mode"),),
        help_description=("Where the rolloff applies.",),
        help_mode_entries=HIGHLIGHT_ROLLOFF_APPLY_MODE_HELP_ENTRIES,
        repeatable=True,
        parent_group="post_fx_highlight_rolloff",
    ),
    RowKind.POST_FX_HIGHLIGHT_ROLLOFF_CURVE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="curve",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_highlight_rolloff_curve,
        apply_horizontal=_apply_post_fx_highlight_rolloff_curve,
        choice=options_choice(HIGHLIGHT_ROLLOFF_CURVES, lambda s, _d: s.post_fx.highlight_rolloff.curve),
        help_title="Curve",
        help_entries=(("Left/Right", "choose curve"),),
        help_description=("The shape of the rolloff above the threshold.",),
        help_mode_entries=HIGHLIGHT_ROLLOFF_CURVE_HELP_ENTRIES,
        repeatable=True,
        parent_group="post_fx_highlight_rolloff",
    ),
    RowKind.POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="threshold",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_highlight_rolloff_threshold,
        apply_horizontal=_apply_post_fx_highlight_rolloff_threshold,
        help_title="Threshold",
        help_description=(
            "The brightness where the rolloff starts.",
            "A lower value changes more of the picture.",
            "A higher value changes only the brightest areas.",
        ),
        repeatable=True,
        parent_group="post_fx_highlight_rolloff",
    ),
    RowKind.POST_FX_HIGHLIGHT_ROLLOFF_CEILING: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="ceiling",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_highlight_rolloff_ceiling,
        apply_horizontal=_apply_post_fx_highlight_rolloff_ceiling,
        help_title="Ceiling",
        help_description=(
            "The maximum brightness after the rolloff.",
            "At 100% strength, the brightest areas go down to this level.",
            "Set it at or below the threshold.",
        ),
        repeatable=True,
        parent_group="post_fx_highlight_rolloff",
    ),
    RowKind.POST_FX_HIGHLIGHT_ROLLOFF_STRENGTH: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="strength",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_highlight_rolloff_strength,
        apply_horizontal=_apply_post_fx_highlight_rolloff_strength,
        help_title="Strength",
        help_description=(
            "How much the rolloff pulls bright areas down to the ceiling.",
            "At 100%, bright areas go fully to the ceiling.",
            "Above 100%, the pull is stronger.",
            "A lower value keeps more brightness.",
        ),
        repeatable=True,
        parent_group="post_fx_highlight_rolloff",
    ),
    RowKind.POST_FX_HIGHLIGHT_ROLLOFF_SOFTNESS: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="softness",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_highlight_rolloff_softness,
        apply_horizontal=_apply_post_fx_highlight_rolloff_softness,
        help_title="Softness",
        help_description=(
            "How gradually the rolloff starts above the threshold.",
            "A higher value gives a smoother start.",
            "A lower value gives a sharp start at the threshold.",
        ),
        repeatable=True,
        parent_group="post_fx_highlight_rolloff",
    ),
    RowKind.POST_FX_HIGHLIGHT_ROLLOFF_DESATURATION: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="desaturation",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_highlight_rolloff_desaturation,
        apply_horizontal=_apply_post_fx_highlight_rolloff_desaturation,
        help_title="Desaturation",
        help_description=(
            "How much colour the bright areas lose.",
            "A higher value moves the bright areas toward grey.",
        ),
        repeatable=True,
        parent_group="post_fx_highlight_rolloff",
    ),
    RowKind.POST_FX_CHROMA_BOOST_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="chroma boost",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Chroma Boost",
        help_description=(
            "Makes colours stronger.",
            "Use it after Highlight Rolloff to bring back colour.",
        ),
        parent_group="post_fx",
    ),
    RowKind.POST_FX_CHROMA_BOOST_MODE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="mode",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_chroma_boost_mode,
        apply_horizontal=_apply_post_fx_chroma_boost_mode,
        choice=options_choice(CHROMA_BOOST_APPLY_MODES, lambda s, _d: s.post_fx.chroma_boost.mode),
        help_title="Mode",
        help_entries=(("Left/Right", "choose mode"),),
        help_description=("Where the boost applies.",),
        help_mode_entries=CHROMA_BOOST_APPLY_MODE_HELP_ENTRIES,
        repeatable=True,
        parent_group="post_fx_chroma_boost",
    ),
    RowKind.POST_FX_CHROMA_BOOST_VARIANT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="variant",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_chroma_boost_variant,
        apply_horizontal=_apply_post_fx_chroma_boost_variant,
        choice=options_choice(CHROMA_BOOST_VARIANTS, lambda s, _d: s.post_fx.chroma_boost.variant),
        help_title="Variant",
        help_entries=(("Left/Right", "choose variant"),),
        help_description=("How the boost changes different colours.",),
        help_mode_entries=CHROMA_BOOST_VARIANT_HELP_ENTRIES,
        repeatable=True,
        parent_group="post_fx_chroma_boost",
    ),
    RowKind.POST_FX_CHROMA_BOOST_AMOUNT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="amount",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_chroma_boost_amount,
        apply_horizontal=_apply_post_fx_chroma_boost_amount,
        help_title="Amount",
        help_description=(
            "The strength of the boost.",
            "0% turns it off.",
        ),
        repeatable=True,
        parent_group="post_fx_chroma_boost",
    ),
    RowKind.POST_FX_LIMITER_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="visual limiter",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Visual Limiter",
        help_description=(
            "Makes the layers dimmer when the combined picture is too busy.",
            "It works with or without the timeline.",
            "When the timeline is on, cue roles change how much each layer dims.",
            "The Post FX switch and solo do not change it.",
        ),
        parent_group="post_fx",
        blocked_by_section_lock=False,
    ),
    RowKind.POST_FX_LIMITER_ENABLED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="enabled",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_limiter_enabled,
        apply_horizontal=_apply_post_fx_limiter_enabled,
        choice=bool_choice(lambda s, _d: s.post_fx.limiter.enabled),
        help_title="Visual Limiter Enabled",
        help_entries=(("Left/Right", "off / on"),),
        help_description=(
            "Turns the visual limiter on or off.",
            "The Post FX switch does not change it.",
        ),
        parent_group="post_fx_limiter",
        blocked_by_section_lock=False,
    ),
    RowKind.POST_FX_LIMITER_THRESHOLD: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="threshold",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_limiter_threshold,
        apply_horizontal=_apply_post_fx_limiter_threshold,
        help_title="Visual Limiter Threshold",
        help_entries=(
            ("Left/Right", "decrease / increase"),
        ),
        help_description=(
            "The busyness level where the limiter starts to dim the layers.",
        ),
        repeatable=True,
        parent_group="post_fx_limiter",
        blocked_by_section_lock=False,
    ),
    RowKind.POST_FX_LIMITER_RATIO: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="ratio",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_limiter_ratio,
        apply_horizontal=_apply_post_fx_limiter_ratio,
        help_title="Visual Limiter Ratio",
        help_entries=(
            ("Left/Right", "decrease / increase"),
        ),
        help_description=(
            "How much the limiter dims the layers above the threshold.",
            "A higher ratio dims busy layers more.",
        ),
        repeatable=True,
        parent_group="post_fx_limiter",
        blocked_by_section_lock=False,
    ),
    RowKind.POST_FX_LIMITER_RELEASE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="release",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_limiter_release,
        apply_horizontal=_apply_post_fx_limiter_release,
        help_title="Visual Limiter Release",
        help_entries=(
            ("Left/Right", "decrease / increase"),
        ),
        help_description=(
            "Seconds that the layers take to become bright again after the limiter dims them.",
        ),
        repeatable=True,
        parent_group="post_fx_limiter",
        blocked_by_section_lock=False,
    ),
}
