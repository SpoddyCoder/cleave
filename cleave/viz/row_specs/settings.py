"""Editor settings row specs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.config_schema.editor import (
    EDITOR_PREVIEW_QUALITY_HELP_ENTRIES,
    navigator_height_label,
    ui_scale_label,
    notification_display_label,
)
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.tuning_view_state import TuningViewState

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

def _format_settings_preview_quality(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.settings.preview_quality

def _format_settings_visualiser_width(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return str(state.settings.visualiser_width)

def _format_settings_visualiser_height(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return str(state.settings.visualiser_height)

def _format_settings_navigator_side(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.settings.navigator_side

def _format_settings_help_side(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.settings.help_side

def _format_settings_ui_notification_display(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return notification_display_label(state.settings.notification_display_sec)

def _format_settings_ui_scale(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return ui_scale_label(state.settings.ui_scale)

def _format_settings_ui_navigator_height(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return navigator_height_label(state.settings.navigator_height)

def _format_settings_residual_latency_ms(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.settings.residual_latency_ms} ms"

def _apply_settings_preview_quality(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    controls.settings.cycle_preview_quality(forward=forward)
    controls.layer_lifecycle.apply_preview_resolutions()

def _apply_settings_visualiser_width(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    controls.settings.adjust_visualiser_width(forward=forward, large=large)

def _apply_settings_visualiser_height(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    controls.settings.adjust_visualiser_height(forward=forward, large=large)

def _apply_settings_navigator_side(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.settings.cycle_navigator_side(forward=forward)

def _apply_settings_help_side(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.settings.cycle_help_side(forward=forward)

def _apply_settings_ui_notification_display(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    controls.settings.adjust_notification_display_sec(forward=forward, large=large)

def _apply_settings_ui_scale(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    controls.settings.adjust_ui_scale(forward=forward, large=large)

def _apply_settings_ui_navigator_height(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    controls.settings.adjust_navigator_height(forward=forward, large=large)

def _apply_settings_residual_latency_ms(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    controls.settings.adjust_residual_latency_ms(forward=forward, large=large)
    controls.on_residual_latency_changed()

SPECS: dict[RowKind, RowSpec] = {
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
        parent_group="settings_editor_window",
    ),
    RowKind.SETTINGS_EDITOR_WINDOW_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="Editor Window",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Editor Window",
        help_description=(
            "Live preview quality, visualiser resolution, and column sides.",
            "Drag the window edges, maximise it, or press F11 to set its size.",
        ),
        is_pinned=True,
        parent_group="settings",
    ),
    RowKind.SETTINGS_VISUALISER_WIDTH: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="visualiser width",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_visualiser_width,
        apply_horizontal=_apply_settings_visualiser_width,
        help_title="Visualiser width",
        help_entries=(
            ("Left/Right", "adjust width (10 px)"),
            ("PgUp/PgDn", "large step (100 px)"),
        ),
        help_description=(
            "Visualiser render width in pixels. Applies live.",
            "The window size is separate.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_editor_window",
    ),
    RowKind.SETTINGS_VISUALISER_HEIGHT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="visualiser height",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_visualiser_height,
        apply_horizontal=_apply_settings_visualiser_height,
        help_title="Visualiser height",
        help_entries=(
            ("Left/Right", "adjust height (10 px)"),
            ("PgUp/PgDn", "large step (100 px)"),
        ),
        help_description=(
            "Visualiser render height in pixels. Applies live.",
            "The window size is separate.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_editor_window",
    ),
    RowKind.SETTINGS_NAVIGATOR_SIDE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="navigator",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_navigator_side,
        apply_horizontal=_apply_settings_navigator_side,
        help_title="Navigator",
        help_entries=(("Left/Right", "choose side"),),
        help_description=(
            "Side of the window for the navigator and inspector.",
            "They stay one column.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_editor_window",
    ),
    RowKind.SETTINGS_HELP_SIDE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="help",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_help_side,
        apply_horizontal=_apply_settings_help_side,
        help_title="Help",
        help_entries=(("Left/Right", "choose side"),),
        help_description=(
            "Side of the window for the help column.",
            "When it shares a side with the navigator, it sits at the window edge.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_editor_window",
    ),
    RowKind.SETTINGS_UI_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="UI",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="UI",
        help_description=(
            "UI scale, notification time, and navigator height for the editor panels.",
        ),
        is_pinned=True,
        parent_group="settings",
    ),
    RowKind.SETTINGS_UI_NOTIFICATION_DISPLAY: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="notification time",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_ui_notification_display,
        apply_horizontal=_apply_settings_ui_notification_display,
        help_title="Notification time",
        help_entries=(
            ("Left/Right", "adjust how long toasts stay visible"),
            ("PgUp/PgDn", "large step"),
            ("0", "until dismissed; Enter clears the toast"),
        ),
        help_description=(
            "How long panel toasts stay visible before they disappear.",
            "Until dismissed keeps them until you press Enter.",
            "Enter dismisses the current toast at any remaining time.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_UI_SCALE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="UI scale",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_ui_scale,
        apply_horizontal=_apply_settings_ui_scale,
        help_title="UI scale",
        help_entries=(
            ("Left/Right", "adjust scale (10%)"),
            ("PgUp/PgDn", "large step (50%)"),
        ),
        help_description=(
            "Size of all editor text and the spacing around it.",
            "Covers the menu, navigator, inspector, help, transport,",
            "notifications, dialogs, and the timeline strip.",
            "Overlay cards in the visualiser keep their own font sizes.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_UI_NAVIGATOR_HEIGHT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="navigator height",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_ui_navigator_height,
        apply_horizontal=_apply_settings_ui_navigator_height,
        help_title="Navigator height",
        help_entries=(
            ("Left/Right", "adjust height (10 px)"),
            ("PgUp/PgDn", "large step (50 px)"),
            ("Drag", "the line between navigator and inspector"),
        ),
        help_description=(
            "How much of the side column the navigator takes.",
            "The inspector fills the rest below it.",
            "Fit to rows sizes the navigator to its tree, up to half the column.",
            "Step Left past the smallest height to return to fit to rows.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_LATENCY_COMPENSATION_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="Latency Compensation",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Latency Compensation",
        help_description=(
            "Use this to correct for bluetooth/wireless latency.",
            "Affects new timeline cue & song marker placements only.",
            "Already saved markers and cues do not move when you change this."
        ),
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
            ("PgUp/PgDn", "large step (50 ms)"),
        ),
        help_description=(
            "Compensates for unmeasurable input/output lag for live monitoring",
            "and timeline cue/song marker placement.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_latency_compensation",
    ),
}
