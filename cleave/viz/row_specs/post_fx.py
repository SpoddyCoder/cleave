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

def _format_post_fx_fade_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return on_off_text(state.post_fx.fade.enabled)

def _apply_post_fx_fade_enabled(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.post_fx.set_fade_enabled(forward)

def _toggle_post_fx_fade_enabled(
    controls: TuningControls, _desc: RowDescriptor
) -> None:
    if controls.session.post_fx.locked:
        return
    controls.post_fx.set_fade_enabled(not controls.session.post_fx.fade.enabled)

def _format_post_fx_highlight_rolloff_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return on_off_text(state.post_fx.highlight_rolloff.enabled)

def _apply_post_fx_highlight_rolloff_enabled(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.post_fx.set_highlight_rolloff_enabled(forward)

def _toggle_post_fx_highlight_rolloff_enabled(
    controls: TuningControls, _desc: RowDescriptor
) -> None:
    if controls.session.post_fx.locked:
        return
    controls.post_fx.set_highlight_rolloff_enabled(
        not controls.session.post_fx.highlight_rolloff.enabled
    )

def _format_post_fx_chroma_boost_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return on_off_text(state.post_fx.chroma_boost.enabled)

def _apply_post_fx_chroma_boost_enabled(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.post_fx.set_chroma_boost_enabled(forward)

def _toggle_post_fx_chroma_boost_enabled(
    controls: TuningControls, _desc: RowDescriptor
) -> None:
    if controls.session.post_fx.locked:
        return
    controls.post_fx.set_chroma_boost_enabled(
        not controls.session.post_fx.chroma_boost.enabled
    )

def _toggle_post_fx_limiter_enabled(
    controls: TuningControls, _desc: RowDescriptor
) -> None:
    controls.post_fx.set_limiter_enabled(
        not controls.session.post_fx.limiter.enabled
    )

def _format_post_fx_locked(state: TuningViewState, _desc: RowDescriptor) -> str:
    return lock_text(state.post_fx.locked)


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
        help_title="Post FX",
        help_description=(
            "Finishing effects applied to the combined picture, each with its own switch: fades, highlight control, colour, and a limiter for busy passages.",
        ),
    ),
    RowKind.POST_FX_LOCKED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="lock",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_locked,
        apply_horizontal=_apply_post_fx_locked,
        choice=bool_choice(lambda s, _d: s.post_fx.locked, lock_text),
        help_title="Post FX Lock",
        help_description=(
            "Protects the Post FX settings from accidental edits.",
        ),
        blocked_by_section_lock=False,
    ),
    RowKind.POST_FX_FADE_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="fade",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Fade",
        help_description=(
            "Fades the picture up from black at the start of the song and down to black at the end.",
        ),
        help_entries=(("E", "enable/disable"),),
        toggle_enabled=_toggle_post_fx_fade_enabled,
        parent_group="post_fx",
    ),
    RowKind.POST_FX_FADE_ENABLED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="enabled",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_fade_enabled,
        apply_horizontal=_apply_post_fx_fade_enabled,
        choice=bool_choice(lambda s, _d: s.post_fx.fade.enabled),
        help_title="Fade Enabled",
        help_description=(
            "Switches both the fade-in and the fade-out.",
        ),
        parent_group="post_fx_fade",
    ),
    RowKind.POST_FX_FADE_IN_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="fade in",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Fade In",
        help_description=(
            "The fade-in runs from Start to End, both measured in seconds from the start of the song.",
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
            "When the fade-in begins, in seconds from the start of the song.",
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
            "When the picture reaches full brightness, in seconds from the start of the song. It cannot come before Start.",
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
        help_description=(
            "The fade curve.",
        ),
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
            "The fade-out runs from Start to End, both measured in seconds back from the end of the song, so Start is the larger number.",
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
            "When the fade-out begins, in seconds before the song ends. It is always larger than End.",
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
            "When the picture reaches black, in seconds before the song ends.",
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
            "The fade curve.",
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
            "Compresses highlights so stacked layers, black-key layers especially, do not clip to flat white. Hue is preserved. With HDR Compositing on, a gentle rolloff always runs and these settings add to it.",
        ),
        help_entries=(("E", "enable/disable"),),
        toggle_enabled=_toggle_post_fx_highlight_rolloff_enabled,
        parent_group="post_fx",
    ),
    RowKind.POST_FX_HIGHLIGHT_ROLLOFF_ENABLED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="enabled",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_highlight_rolloff_enabled,
        apply_horizontal=_apply_post_fx_highlight_rolloff_enabled,
        choice=bool_choice(lambda s, _d: s.post_fx.highlight_rolloff.enabled),
        help_title="Highlight Rolloff Enabled",
        help_description=(
            "Switches the highlight rolloff on or off.",
        ),
        parent_group="post_fx_highlight_rolloff",
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
        help_description=(
            "Where in the chain the rolloff runs.",
        ),
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
        help_description=(
            "The tone curve applied above the threshold.",
        ),
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
            "The brightness where compression begins. Lower values touch more of the image; higher values affect only the hottest highlights.",
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
            "The brightness highlights are compressed towards; at 100% strength they land exactly on it. Keep it at or below the threshold.",
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
            "How far highlights are pulled towards the ceiling. 100% reaches it, values above push harder, and lower values keep more of the original brightness.",
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
            "Width of the knee at the threshold. Higher values ease into compression; lower values give a hard knee.",
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
            "How much saturation the compressed highlights lose. Higher values push them towards white-grey, as film does.",
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
            "Increases colour intensity. Useful after Highlight Rolloff to win back saturation the compression took out.",
        ),
        help_entries=(("E", "enable/disable"),),
        toggle_enabled=_toggle_post_fx_chroma_boost_enabled,
        parent_group="post_fx",
    ),
    RowKind.POST_FX_CHROMA_BOOST_ENABLED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="enabled",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_post_fx_chroma_boost_enabled,
        apply_horizontal=_apply_post_fx_chroma_boost_enabled,
        choice=bool_choice(lambda s, _d: s.post_fx.chroma_boost.enabled),
        help_title="Chroma Boost Enabled",
        help_description=(
            "Switches the chroma boost on or off.",
        ),
        parent_group="post_fx_chroma_boost",
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
        help_description=(
            "Where in the chain the boost runs.",
        ),
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
        help_description=(
            "How the boost treats different colours.",
        ),
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
            "Boost intensity. 0% bypasses it.",
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
            "Works like an audio compressor for visual density: when the composite gets too busy, it pulls the layers down. With the timeline on, clip roles decide which layers give way most. Post FX solo and lock do not affect it.",
        ),
        help_entries=(("E", "enable/disable"),),
        toggle_enabled=_toggle_post_fx_limiter_enabled,
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
            "Switches the visual limiter on or off.",
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
            "The level of visual activity where the limiter starts dimming layers.",
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
            "How hard the limiter dims once activity passes the threshold. Higher ratios clamp busy passages harder.",
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
            "How long, in seconds, the layers take to recover after the limiter lets go.",
        ),
        repeatable=True,
        parent_group="post_fx_limiter",
        blocked_by_section_lock=False,
    ),
}
