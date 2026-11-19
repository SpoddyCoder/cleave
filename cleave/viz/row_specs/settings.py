"""Editor settings row specs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.config_schema.editor import (
    EDITOR_PREVIEW_QUALITY_HELP_ENTRIES,
    NAVIGATOR_EXPAND_CLICKS,
    navigator_expand_click_label,
    ui_scale_label,
    notification_display_label,
)
from cleave.crash_log import crash_log_active
from cleave.viz.commands import command_by_id
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.theme import theme_ids, theme_label
from cleave.viz.tuning_view_state import TuningViewState

from cleave.config_schema.editor import COLUMN_SIDES, EDITOR_PREVIEW_QUALITIES
from cleave.viz.row_specs.common import bool_choice, on_off_text, options_choice
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

def _format_settings_navigator_expand_click(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return navigator_expand_click_label(state.settings.navigator_expand_click)

def _format_settings_help_side(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.settings.help_side

def _format_settings_ui_notification_display(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return notification_display_label(state.settings.notification_display_sec)

def _format_settings_ui_theme(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return theme_label(state.settings.theme)

def _format_settings_ui_scale(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return ui_scale_label(state.settings.ui_scale)

def _format_settings_audio_latency_ms(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.settings.audio_latency_ms} ms"

def _format_settings_tap_latency_ms(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.settings.tap_latency_ms:+d} ms"

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

def _apply_settings_navigator_expand_click(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.settings.step_navigator_expand_click(forward=forward)

def _apply_settings_help_side(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.settings.step_help_side(forward=forward)

def _apply_settings_ui_notification_display(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    controls.settings.adjust_notification_display_sec(forward=forward, large=large)

def _format_settings_ui_highlight_new_page(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return on_off_text(state.settings.highlight_new_page)

def _apply_settings_ui_highlight_new_page(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.settings.set_highlight_new_page(forward)

def _format_settings_ui_show_tooltips(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return on_off_text(state.settings.show_tooltips)

def _apply_settings_ui_show_tooltips(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.settings.set_show_tooltips(forward)

def _format_settings_dev_tools_crash_log(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    text = on_off_text(state.settings.crash_log)
    if state.settings.crash_log != crash_log_active():
        return f"{text} (next start)"
    return text

def _apply_settings_dev_tools_crash_log(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.settings.set_crash_log(forward)

def _apply_settings_dev_tools_open_crash_log_folder(
    controls: TuningControls, _desc: RowDescriptor
) -> None:
    command_by_id("settings.open_crash_log_folder").run(controls)

def _apply_settings_ui_open_themes_folder(
    controls: TuningControls, _desc: RowDescriptor
) -> None:
    command_by_id("settings.open_themes_folder").run(controls)

def _apply_settings_ui_reload_themes(
    controls: TuningControls, _desc: RowDescriptor
) -> None:
    command_by_id("settings.reload_themes").run(controls)

def _apply_settings_measure_audio_latency(
    controls: TuningControls, _desc: RowDescriptor
) -> None:
    command_by_id("settings.measure_latency").run(controls)

def _apply_settings_calibrate_tap_timing(
    controls: TuningControls, _desc: RowDescriptor
) -> None:
    command_by_id("settings.calibrate_tap_timing").run(controls)

def _apply_settings_ui_theme(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    controls.settings.step_theme(forward=forward)

def _apply_settings_ui_scale(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    controls.settings.adjust_ui_scale(forward=forward, large=large)

def _apply_settings_audio_latency_ms(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    controls.settings.adjust_audio_latency_ms(forward=forward, large=large)
    controls.on_audio_latency_changed()

def _apply_settings_tap_latency_ms(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    controls.settings.adjust_tap_latency_ms(forward=forward, large=large)
    controls.on_tap_latency_changed()

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
            "Trades live preview fidelity for frame rate; renders are unaffected. Below Output, presets and grain can look slightly different, so switch to Output when you need to judge the final image.",
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
            "Preview quality. The preview takes its aspect ratio from Project > Resolution and its size from the window: resize the window, or press F11 for Full screen editor. Ctrl+F plays the show full screen; Esc returns.",
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
            "Which side of the window holds the navigator and inspector.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_NAVIGATOR_EXPAND_CLICK: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="navigator expand",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_navigator_expand_click,
        apply_horizontal=_apply_settings_navigator_expand_click,
        choice=options_choice(
            NAVIGATOR_EXPAND_CLICKS,
            lambda s, _d: s.settings.navigator_expand_click,
            navigator_expand_click_label,
            combo=True,
        ),
        help_title="Navigator Expand",
        help_entries=(("Left/Right", "choose how rows open"),),
        help_description=(
            "What clicking a navigator row with pages under it does:",
            "Dbl-click: a click selects; a double-click opens or closes.",
            "Click / dbl-click: a click opens; a double-click closes.",
            "Click: each click opens or closes.",
            "Arrow only: a click selects; only the arrow opens or closes.",
            "The arrow always toggles the row with a single click.",
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
            "Which side of the window holds the help column. When it shares a side with the navigator, help goes on the outside edge.",
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
            "Editor appearance and layout.",
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
            "How long notifications stay up. Until dismissed keeps each one until you press Enter or click it.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_UI_HIGHLIGHT_NEW_PAGE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="highlight new page",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_ui_highlight_new_page,
        apply_horizontal=_apply_settings_ui_highlight_new_page,
        choice=bool_choice(lambda s, _d: s.settings.highlight_new_page),
        help_title="Highlight New Page",
        help_entries=(("Left/Right", "off / on"),),
        help_description=(
            "Flashes the inspector title when a new page opens, and scrolls titles too long for the column. Off keeps the title still.",
        ),
        is_pinned=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_UI_SHOW_TOOLTIPS: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="tooltips",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_ui_show_tooltips,
        apply_horizontal=_apply_settings_ui_show_tooltips,
        choice=bool_choice(lambda s, _d: s.settings.show_tooltips),
        help_title="Tooltips",
        help_entries=(("Left/Right", "off / on"),),
        help_description=(
            "Shows short tips when hovering over icons and strip labels, and explains why a greyed-out menu item is unavailable.",
        ),
        is_pinned=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_LATENCY_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="Latency",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Latency",
        help_description=(
            "Timing corrections for the preview and the markers and clips you tap.",
        ),
        is_pinned=True,
        parent_group="settings",
    ),
    RowKind.SETTINGS_DEV_TOOLS_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="Dev Tools",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Dev Tools",
        help_description=(
            "Diagnostics for tracking down problems in Cleave itself.",
        ),
        is_pinned=True,
        parent_group="settings",
    ),
    RowKind.SETTINGS_DEV_TOOLS_CRASH_LOG: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="crash log",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_dev_tools_crash_log,
        apply_horizontal=_apply_settings_dev_tools_crash_log,
        choice=bool_choice(lambda s, _d: s.settings.crash_log),
        help_title="Crash Log",
        help_entries=(("Left/Right", "off / on"),),
        help_description=(
            "Records what Cleave was doing when it crashed, in crash.log next to config.yaml:",
            "Windows: %APPDATA%\\Cleave.",
            "Linux: ~/.config/cleave.",
            "Takes effect the next time Cleave starts.",
        ),
        is_pinned=True,
        parent_group="settings_dev_tools",
    ),
    RowKind.SETTINGS_DEV_TOOLS_OPEN_CRASH_LOG_FOLDER: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Open crash log folder",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_settings_dev_tools_open_crash_log_folder,
        fit_strategy=FitStrategy.NONE,
        help_title="Open Crash Log Folder",
        help_entries=(("Enter", "open the folder"),),
        help_description=(
            "Opens the folder holding crash.log and config.yaml. Once crash.log passes 1 MB, Cleave trims it to the newest entries on the next start.",
        ),
        is_pinned=True,
    ),
    RowKind.SETTINGS_UI_THEME: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="theme",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_ui_theme,
        apply_horizontal=_apply_settings_ui_theme,
        choice=options_choice(
            theme_ids,
            lambda s, _d: s.settings.theme,
            theme_label,
            combo=True,
        ),
        help_title="Theme",
        help_entries=(("Left/Right", "choose theme"),),
        help_description=(
            "The editor's colour scheme. It does not affect the visuals or credits cards. Add your own with theme files in the themes folder, then use Reload themes.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_UI_OPEN_THEMES_FOLDER: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Open themes folder",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_settings_ui_open_themes_folder,
        fit_strategy=FitStrategy.NONE,
        help_title="Open Themes Folder",
        help_entries=(("Enter", "open the folder"),),
        help_description=(
            "Opens the folder for custom themes. Each .yaml file there starts from a built-in theme and overrides only the colours it lists; the user guide lists the colour names.",
        ),
        is_pinned=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_UI_RELOAD_THEMES: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Reload themes",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_settings_ui_reload_themes,
        fit_strategy=FitStrategy.NONE,
        help_title="Reload Themes",
        help_entries=(("Enter", "read the theme files again"),),
        help_description=(
            "Rereads the themes folder so edits to a theme file apply immediately. Any errors in the files are reported in a message.",
        ),
        is_pinned=True,
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
            "Scales all editor text and spacing, for high-DPI screens or viewing from a distance. Credits cards are unaffected.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
    ),
    RowKind.SETTINGS_AUDIO_LATENCY_MS: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="audio latency",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_audio_latency_ms,
        apply_horizontal=_apply_settings_audio_latency_ms,
        help_title="Audio Latency",
        help_entries=(
            ("Left/Right", "adjust audio latency (10 ms)"),
            ("PgUp/PgDn", "large step (50 ms)"),
        ),
        help_description=(
            "Delays the preview to match late sound, such as from wireless headphones. Preview only; renders are unaffected.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_latency",
    ),
    RowKind.SETTINGS_MEASURE_AUDIO_LATENCY: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Measure audio latency",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_settings_measure_audio_latency,
        fit_strategy=FitStrategy.NONE,
        help_title="Measure Audio Latency",
        help_entries=(("Enter", "start the test"),),
        help_description=(
            "Flashes the preview on a beep each bar. Adjust until they land together.",
        ),
        is_pinned=True,
        parent_group="settings_latency",
    ),
    RowKind.SETTINGS_CALIBRATE_TAP_TIMING: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Calibrate tap timing",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_settings_calibrate_tap_timing,
        fit_strategy=FitStrategy.NONE,
        help_title="Calibrate Tap Timing",
        help_entries=(("Enter", "start the test"),),
        help_description=(
            "Plays a click track. Press Enter on each long low tone until your timing settles.",
        ),
        is_pinned=True,
        parent_group="settings_latency",
    ),
    RowKind.SETTINGS_TAP_LATENCY_MS: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="tap latency",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_tap_latency_ms,
        apply_horizontal=_apply_settings_tap_latency_ms,
        help_title="Tap Latency",
        help_entries=(
            ("Left/Right", "adjust tap latency (10 ms)"),
            ("PgUp/PgDn", "large step (50 ms)"),
        ),
        help_description=(
            "Moves song markers and recorded clips you tap during playback back by this much, so they land on the beat. Below zero if you tap early.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="settings_latency",
    ),
}
