"""Editor settings and config-path row specs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.config_schema.editor import (
    EDITOR_PREVIEW_QUALITY_HELP_ENTRIES,
    ui_fade_display,
)
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_sections import apply_expand_toggle
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.row_specs.common import apply_expand_subheader
from cleave.viz.tuning_view_state import TuningViewState

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

def _format_settings_preview_quality(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.settings.preview_quality

def _format_settings_editor_mode(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    from cleave.viz.session import EDITOR_MODE_PANEL_LABELS

    return EDITOR_MODE_PANEL_LABELS[state.settings.editor_mode_selection]  # type: ignore[index]

def editor_mode_confirm_pending(state: TuningViewState) -> bool:
    """True when Left/Right staged a mode that still needs Enter."""
    return state.settings.editor_mode_selection != state.settings.editor_mode

def _format_settings_ui_width_mode(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.settings.ui_width_mode

def _format_settings_ui_width(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return str(state.settings.ui_width)

def _format_settings_ui_fade(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return ui_fade_display(state.settings.ui_fade)

def _format_settings_residual_latency_ms(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.settings.residual_latency_ms} ms"

def _format_settings_measure_latency(
    _state: TuningViewState, _desc: RowDescriptor
) -> str:
    return "measure latency"

def _apply_settings_editor_mode(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls.editor_mode.cycle_editor_mode_selection(forward=forward)

def _apply_settings_preview_quality(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls.settings.cycle_preview_quality(forward=forward)
    controls.layer_lifecycle.apply_preview_resolutions()

def _apply_settings_ui_width_mode(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls.settings.cycle_ui_width_mode(forward=forward)

def _apply_settings_ui_width(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    controls.settings.adjust_ui_width(forward=forward, ctrl=ctrl)

def _apply_settings_ui_fade(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    controls.settings.adjust_ui_fade(forward=forward, ctrl=ctrl)

def _apply_settings_residual_latency_ms(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    controls.settings.adjust_residual_latency_ms(forward=forward, ctrl=ctrl)
    controls.on_residual_latency_changed()

def _apply_settings_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    apply_expand_toggle(
        controls, desc.kind, desc.slot, forward, card=desc.card
    )

def _format_config_header(state: TuningViewState, _desc: RowDescriptor) -> str:
    return state.active_config_label

SPECS: dict[RowKind, RowSpec] = {
    RowKind.CONFIG_HEADER: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_config_header,
        fit_strategy=FitStrategy.PATH,
        shows_enter_icon=True,
        help_title="Save",
        help_description=(
            "Active config file.",
            "Enter or Ctrl+S saves the current session settings.",
        ),
        is_header=True,
    ),
    RowKind.SETTINGS_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="Editor Settings",
        present_style=RowPresentStyle.COMPOSITE_HEADER,
        apply_horizontal=_apply_settings_header,
        fit_strategy=FitStrategy.NONE,
        help_title="Editor Settings",
        help_description=("Global editor settings (applies to all projects)",),
        quick_nav_target=True,
        quick_nav_always=True,
        is_header=True,
    ),
    RowKind.SETTINGS_EDITOR_MODE: RowSpec(
        affordance=RowAffordance.ACTION_PARAMETER,
        panel_label="editor mode",
        present_style=RowPresentStyle.ACTION_PARAMETER,
        format_value=_format_settings_editor_mode,
        apply_horizontal=_apply_settings_editor_mode,
        shows_enter_icon=True,
        help_title="Editor mode",
        help_entries=(
            ("Left/Right", "cycle mode"),
            ("Enter", "confirm switch"),
        ),
        help_description=(
            "Visualizer mode exposes the full tuning panel.",
            "Preset curation mode limits the panel to preset favourites and blacklist.",
            "Left/Right stages a mode; Enter confirms the switch.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings",
    ),
    RowKind.SETTINGS_PREVIEW_QUALITY: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="preview quality",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_preview_quality,
        apply_horizontal=_apply_settings_preview_quality,
        help_title="Preview quality",
        help_entries=(("Left/Right", "cycle mode"),),
        help_description=(
            "Trade-off between visual quality and CPU/GPU load.",
            "Affects layer resolution scaling in the live view only.",
        ),
        help_mode_entries=EDITOR_PREVIEW_QUALITY_HELP_ENTRIES,
        is_pinned=True,
        repeatable=True,
        parent_group="settings",
    ),
    RowKind.SETTINGS_UI_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="UI",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="UI",
        help_description=("Panel width and auto-fade for the main tuning overlay.",),
        is_sub_header=True,
        is_pinned=True,
        parent_group="settings",
    ),
    RowKind.SETTINGS_UI_FADE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="auto-fade",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_ui_fade,
        apply_horizontal=_apply_settings_ui_fade,
        help_title="Auto-fade",
        help_entries=(
            ("Left/Right", "adjust delay before UI fades"),
            ("Ctrl + Left/Right", "large step"),
            ("0", "disabled; UI stays until Esc"),
        ),
        help_description=(
            "Delay before the overlay panel fades out.",
            "0 keeps it always visible.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_UI_WIDTH_MODE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="width mode",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_ui_width_mode,
        apply_horizontal=_apply_settings_ui_width_mode,
        help_title="Width mode",
        help_entries=(("Left/Right", "cycle mode"),),
        help_description=(
            "Flexible shrinks the panel to fit content up to the max width.",
            "Fixed keeps the panel at the max width always.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_UI_WIDTH: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="max width",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_ui_width,
        apply_horizontal=_apply_settings_ui_width,
        help_title="Max width",
        help_entries=(
            ("Left/Right", "adjust max panel width"),
            ("Ctrl + Left/Right", "large step"),
        ),
        help_description=(
            "Maximum width of the main tuning panel.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_LATENCY_COMPENSATION_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="Latency Compensation",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="Latency Compensation",
        help_description=(
            "Use this to correct for bluetooth/wireless latency.",
            "Affects new timeline cue & song marker placements only.",
            "Already saved markers and cues do not move when you change this."
        ),
        is_sub_header=True,
        is_pinned=True,
        parent_group="settings",
    ),
    RowKind.SETTINGS_RESIDUAL_LATENCY_MS: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="residual latency",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_residual_latency_ms,
        apply_horizontal=_apply_settings_residual_latency_ms,
        help_title="Residual latency",
        help_entries=(
            ("Left/Right", "adjust latency (10 ms)"),
            ("Ctrl + Left/Right", "large step (50 ms)"),
        ),
        help_description=(
            "Compensates for unmeasurable input/output lag for live monitoring",
            "and timeline cue/song marker placement.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_latency_compensation",
    ),
    RowKind.SETTINGS_MEASURE_LATENCY: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="measure latency",
        present_style=RowPresentStyle.FULL_LINE,
        format_value=_format_settings_measure_latency,
        fit_strategy=FitStrategy.NONE,
        shows_enter_icon=True,
        help_title="Measure latency",
        help_entries=(
            ("Enter", "start calibration / tap on each bar beat"),
            ("Esc", "cancel"),
        ),
        help_description=(
            "Plays a 140 BPM click track.",
            "Measurement is confirmed when four consistent taps are detected.",
        ),
        is_pinned=True,
        parent_group="settings_latency_compensation",
    ),
}
