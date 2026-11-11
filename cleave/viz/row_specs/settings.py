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

from cleave.config_schema.editor import COLUMN_SIDES, EDITOR_PREVIEW_QUALITIES
from cleave.viz.row_specs.common import options_choice
if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

def _format_settings_preview_quality(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.settings.preview_quality

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
    controls.settings.step_preview_quality(delta=1 if forward else -1)
    controls.layer_lifecycle.apply_preview_resolutions()

def _apply_settings_navigator_side(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.settings.step_navigator_side(forward=forward)

def _apply_settings_help_side(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.settings.step_help_side(forward=forward)

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

def _jump_settings_preview_quality(
    controls: TuningControls, _desc: RowDescriptor, delta: int
) -> None:
    controls.settings.step_preview_quality(delta=delta)
    controls.layer_lifecycle.apply_preview_resolutions()

SPECS: dict[RowKind, RowSpec] = {
    RowKind.SETTINGS_PREVIEW_QUALITY: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="preview quality",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_preview_quality,
        apply_horizontal=_apply_settings_preview_quality,
        choice=options_choice(EDITOR_PREVIEW_QUALITIES, lambda s, _d: s.settings.preview_quality, jump=_jump_settings_preview_quality),
        help_title="Preview Quality",
        help_entries=(("Left/Right", "choose mode"),),
        help_description=(
            "Lower quality makes the live view faster.",
            "It does not change the render.",
            "Below Output, presets and grain can look a little different.",
            "Use Output to check.",
        ),
        help_mode_entries=EDITOR_PREVIEW_QUALITY_HELP_ENTRIES,
        is_pinned=True,
        repeatable=True,
        parent_group="settings_preview",
    ),
    RowKind.SETTINGS_PREVIEW_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="Preview",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Preview",
        help_description=(
            "Preview quality and audio delay correction.",
            "The preview gets its shape from Project > Resolution.",
            "The window sets its size.",
            "Resize the window, or press F11 for full screen.",
        ),
        is_pinned=True,
        parent_group="settings",
    ),
    RowKind.SETTINGS_NAVIGATOR_SIDE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="navigator side",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_navigator_side,
        apply_horizontal=_apply_settings_navigator_side,
        choice=options_choice(COLUMN_SIDES, lambda s, _d: s.settings.navigator_side),
        help_title="Navigator Side",
        help_entries=(("Left/Right", "choose side"),),
        help_description=(
            "Side of the window for the navigator and inspector.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_HELP_SIDE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="help side",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_help_side,
        apply_horizontal=_apply_settings_help_side,
        choice=options_choice(COLUMN_SIDES, lambda s, _d: s.settings.help_side),
        help_title="Help Side",
        help_entries=(("Left/Right", "choose side"),),
        help_description=(
            "Side of the window for the help column.",
            "If help and the navigator are on the same side, help is at the window edge.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_UI_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="UI",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="UI",
        help_description=(
            "Size and layout of the editor panels.",
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
        help_title="Notification Time",
        help_entries=(
            ("Left/Right", "adjust time"),
            ("PgUp/PgDn", "large step"),
        ),
        help_description=(
            "How long notifications stay on screen.",
            "Until dismissed keeps each one until you close it.",
            "Press Enter, or click the notification, to close it.",
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
        help_title="UI Scale",
        help_entries=(
            ("Left/Right", "adjust scale (10%)"),
            ("PgUp/PgDn", "large step (50%)"),
        ),
        help_description=(
            "Size of all editor text and the spacing around it.",
            "It does not change the credits cards.",
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
        help_title="Navigator Height",
        help_entries=(
            ("Left/Right", "adjust height (10 px)"),
            ("PgUp/PgDn", "large step (50 px)"),
            ("Drag", "move the line between navigator and inspector"),
        ),
        help_description=(
            "Height of the navigator.",
            "The inspector fills the space below it.",
            "Fit to rows makes the navigator as tall as its tree, up to half the column.",
            "Press Left at the smallest height to go back to Fit to rows.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_RESIDUAL_LATENCY_MS: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="residual latency",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_residual_latency_ms,
        apply_horizontal=_apply_settings_residual_latency_ms,
        help_title="Residual Latency",
        help_entries=(
            ("Left/Right", "adjust latency (10 ms)"),
            ("PgUp/PgDn", "large step (50 ms)"),
        ),
        help_description=(
            "Corrects for audio delay that Cleave cannot measure.",
            "Use it for Bluetooth or other wireless headphones.",
            "It changes the live view and where new cues and song markers go.",
            "Cues and markers that you already placed do not move.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_preview",
    ),
}
