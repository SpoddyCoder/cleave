"""Track / layer row specs for the live tuning overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.blend_modes import BLEND_MODE_HELP_ENTRIES
from cleave.config_schema.layers import (
    MAX_LAYER_COUNT,
    PRESET_SWITCHING_TRIGGER_HELP_ENTRIES,
    hard_cut_enabled_display,
    preset_start_clean_display,
    preset_switching_trigger_display,
)
from cleave.cue_roles import CUE_ROLE_MARKER_HELP_ENTRIES
from cleave.preset_library import PRESET_FLAG_MARKERS
from cleave.stems import stem_control_label
from cleave.viz.commands import command_by_id
from cleave.viz.material_icons import ADD_GLYPH, ARROW_DOWNWARD_GLYPH, ARROW_UPWARD_GLYPH
from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.song_markers import format_marker_time
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import FitStrategy, RowNavButton, RowPresentStyle, RowSpec
from cleave.viz.row_specs.common import lock_text, noop_horizontal, on_off_text
from cleave.viz.tuning_view_state import TrackBlock, TuningViewState

from cleave.blend_modes import BLEND_MODES
from cleave.config_schema.layers import PRESET_SWITCHING_TRIGGERS
from cleave.viz.row_specs.common import bool_choice, options_choice
from cleave.viz.session import active_stem_sources
if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

def _track_block(state: TuningViewState, desc: RowDescriptor) -> TrackBlock:
    assert desc.slot is not None
    return state.tracks[desc.slot]

def _format_track_stem(state: TuningViewState, desc: RowDescriptor) -> str:
    return stem_control_label(_track_block(state, desc).runtime.stem)

def _format_track_blend(state: TuningViewState, desc: RowDescriptor) -> str:
    return _track_block(state, desc).runtime.blend_mode

def _format_track_opacity(state: TuningViewState, desc: RowDescriptor) -> str:
    return f"{_track_block(state, desc).runtime.opacity_pct}%"

def _format_track_beat(state: TuningViewState, desc: RowDescriptor) -> str:
    return f"{_track_block(state, desc).runtime.beat_sensitivity:.2f}"

def _format_track_preset_switching_trigger(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return preset_switching_trigger_display(
        _track_block(state, desc).runtime.preset_switching_trigger
    )

def _format_track_preset_duration(state: TuningViewState, desc: RowDescriptor) -> str:
    return f"{_track_block(state, desc).runtime.preset_duration:g}s"

def _format_track_soft_cut_duration(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_track_block(state, desc).runtime.soft_cut_duration:g}s"

def _format_track_easter_egg(state: TuningViewState, desc: RowDescriptor) -> str:
    return f"{_track_block(state, desc).runtime.easter_egg:.2f}"

def _format_track_preset_start_clean(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return preset_start_clean_display(
        _track_block(state, desc).runtime.preset_start_clean
    )

def _format_track_hard_cut_enabled(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return hard_cut_enabled_display(
        _track_block(state, desc).runtime.hard_cut_enabled
    )

def _format_track_hard_cut_duration(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_track_block(state, desc).runtime.hard_cut_duration:g}s"

def _format_track_hard_cut_sensitivity(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_track_block(state, desc).runtime.hard_cut_sensitivity:.2f}"

def _apply_track_stem(
    controls: TuningControls, desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.step_stem(desc.slot, delta=1 if forward else -1)

def _apply_track_blend(
    controls: TuningControls, desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.step_blend(desc.slot, delta=1 if forward else -1)

def _apply_track_opacity(
    controls: TuningControls, desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    if desc.slot is None:
        return
    step = 10 if large else 1
    delta = step if forward else -step
    controls.layer_mutations.set_opacity(
        desc.slot, controls.session.layers[desc.slot].opacity_pct + delta
    )

def _apply_track_beat(
    controls: TuningControls, desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    if desc.slot is None:
        return
    step = 0.1 if large else 0.01
    delta = step if forward else -step
    controls.layer_mutations.set_beat(
        desc.slot, controls.session.layers[desc.slot].beat_sensitivity + delta
    )

def _apply_track_preset_switching_trigger(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.step_preset_switching_trigger(desc.slot, delta=1 if forward else -1)

def _apply_track_preset_duration(
    controls: TuningControls, desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.step_preset_duration(desc.slot, forward=forward, large=large)

def _apply_track_soft_cut_duration(
    controls: TuningControls, desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.step_soft_cut_duration(desc.slot, forward=forward, large=large)

def _apply_track_easter_egg(
    controls: TuningControls, desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.step_easter_egg(desc.slot, forward=forward, large=large)

def _apply_track_preset_start_clean(
    controls: TuningControls, desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.step_preset_start_clean(desc.slot, forward=forward)

def _apply_track_hard_cut_enabled(
    controls: TuningControls, desc: RowDescriptor, forward: bool, _large: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.step_hard_cut_enabled(desc.slot, forward=forward)

def _apply_track_hard_cut_duration(
    controls: TuningControls, desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.step_hard_cut_duration(desc.slot, forward=forward, large=large)

def _apply_track_hard_cut_sensitivity(
    controls: TuningControls, desc: RowDescriptor, forward: bool, large: bool,
) -> None:
    if desc.slot is None:
        return
    step = 0.1 if large else 0.01
    delta = step if forward else -step
    controls.layer_mutations.set_hard_cut_sensitivity(
        desc.slot, controls.session.layers[desc.slot].hard_cut_sensitivity + delta
    )

def _toggle_track_enabled(
    controls: TuningControls, desc: RowDescriptor
) -> None:
    slot = desc.slot
    if slot is None:
        return
    layer = controls.session.layers[slot]
    if layer.locked:
        return
    controls.layer_mutations.set_enabled(slot, not layer.enabled)


def _toggle_track_solo(
    controls: TuningControls, desc: RowDescriptor
) -> None:
    slot = desc.slot
    if slot is None:
        return
    if controls.session.solo_slot == slot:
        controls.layer_mutations.exit_solo(slot)
    else:
        controls.layer_mutations.enter_solo(slot)


def _format_track_enabled(state: TuningViewState, desc: RowDescriptor) -> str:
    return on_off_text(_track_block(state, desc).runtime.enabled)


def _format_track_solo(state: TuningViewState, desc: RowDescriptor) -> str:
    return on_off_text(state.solo_slot == desc.slot)


def _format_track_locked(state: TuningViewState, desc: RowDescriptor) -> str:
    return lock_text(_track_block(state, desc).runtime.locked)


def _apply_track_enabled(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    assert desc.slot is not None
    controls.layer_mutations.set_enabled(desc.slot, forward)


def _apply_track_solo(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    assert desc.slot is not None
    if forward:
        controls.layer_mutations.enter_solo(desc.slot)
    else:
        controls.layer_mutations.exit_solo(desc.slot)


def _apply_track_locked(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    assert desc.slot is not None
    if controls.session.layers[desc.slot].locked != forward:
        controls.toggle_layer_locked(desc.slot)


def _format_track_preset_dir(state: TuningViewState, desc: RowDescriptor) -> str:
    return _track_block(state, desc).preset_dir_label

def _format_track_preset(state: TuningViewState, desc: RowDescriptor) -> str:
    return _track_block(state, desc).preset_label

def _format_track_preset_dir_position(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _track_block(state, desc).preset_dir_position

def _preset_dir_can_go_up(state: TuningViewState, desc: RowDescriptor) -> bool:
    return _track_block(state, desc).preset_dir_can_go_up

def _preset_dir_can_go_down(state: TuningViewState, desc: RowDescriptor) -> bool:
    return _track_block(state, desc).preset_dir_can_go_down

def _format_track_preset_position(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _track_block(state, desc).preset_position

_PRESET_MARKER_HELP_TEXT: dict[str, str] = {
    "[F]": "favourite",
    "[B]": "blacklisted",
    "[L]": "in this layer's preset list (not in preset curation)",
}
_PRESET_MARKER_HELP_ENTRIES: tuple[tuple[str, str], ...] = (
    *((token, _PRESET_MARKER_HELP_TEXT[token]) for token, _ in PRESET_FLAG_MARKERS),
    *CUE_ROLE_MARKER_HELP_ENTRIES,
)
_PRESET_LIST_MARKER_HELP_ENTRIES: tuple[tuple[str, str], ...] = tuple(
    entry for entry in _PRESET_MARKER_HELP_ENTRIES if entry[0] != "[L]"
)


def _format_track_preset_markers(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _track_block(state, desc).preset_markers


def _track_preset_tags(state: TuningViewState, desc: RowDescriptor) -> tuple[str, ...]:
    return _track_block(state, desc).preset_tags

def _format_track_preset_list_count(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return str(len(_track_block(state, desc).runtime.preset_list))

def _format_track_preset_list_item(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    assert desc.preset_index is not None
    block = _track_block(state, desc)
    return block.preset_list_labels[desc.preset_index]

def _format_track_preset_list_item_position(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    assert desc.preset_index is not None
    block = _track_block(state, desc)
    starts = block.preset_list_clip_starts
    if desc.preset_index < len(starts):
        # A clip holds this entry: show where it starts.
        return format_marker_time(starts[desc.preset_index])
    if block.runtime.preset_switching_trigger == "timeline":
        return "spare"
    first_times = block.preset_list_first_times
    if desc.preset_index < len(first_times):
        first = first_times[desc.preset_index]
        return "not shown" if first is None else format_marker_time(first)
    return f"{desc.preset_index + 1}/{len(block.preset_list_labels)}"

def _format_track_preset_list_item_markers(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    assert desc.preset_index is not None
    return _track_block(state, desc).preset_list_markers[desc.preset_index]


def _track_preset_list_item_tags(
    state: TuningViewState, desc: RowDescriptor
) -> tuple[str, ...]:
    assert desc.preset_index is not None
    tags = _track_block(state, desc).preset_list_tags
    return tags[desc.preset_index] if desc.preset_index < len(tags) else ()

def _format_track_effect(state: TuningViewState, desc: RowDescriptor) -> str:
    assert desc.effect_id is not None and desc.driver_slug is not None
    pct = _track_block(state, desc).runtime.effects.get(desc.effect_id, {}).get(
        desc.driver_slug, 0
    )
    return f"{pct}%"

def _apply_track_preset_dir(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    slot = desc.slot
    if slot is None:
        return
    controls.layer_mutations.step_directory(slot, forward=forward)

def _apply_track_preset(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    slot = desc.slot
    if slot is None:
        return
    controls.layer_mutations.step_preset(slot, forward=forward, large=large)

def _apply_track_effect(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    slot = desc.slot
    if slot is None:
        return
    effect_id = desc.effect_id
    driver_slug = desc.driver_slug
    if effect_id is None or driver_slug is None:
        return
    step = 10 if large else 1
    delta = step if forward else -step
    current = controls.session.layers[slot].effects.get(effect_id, {}).get(
        driver_slug, 0
    )
    controls.layer_mutations.set_effect(slot, effect_id, driver_slug, current + delta)

def _format_layer_count(state: TuningViewState, _desc: RowDescriptor) -> str:
    return f"{len(state.layer_z_order)} of {MAX_LAYER_COUNT} layers"


def _visibility_track(
    state: TuningViewState, desc: RowDescriptor
) -> tuple[bool, bool]:
    assert desc.slot is not None
    block = state.tracks[desc.slot]
    return (block.visible, state.solo_slot == desc.slot)


def _apply_preset_dir_action(controls: TuningControls, desc: RowDescriptor) -> None:
    slot = desc.slot
    if slot is None:
        return
    controls.layer_mutations.enter_directory(slot)


def _apply_preset_dir_open_action(controls: TuningControls, desc: RowDescriptor) -> None:
    """Enter or a double-click: the first subfolder, or the browser when there is none."""
    slot = desc.slot
    if slot is None:
        return
    if controls.layer_mutations.can_enter_directory(slot):
        controls.layer_mutations.enter_directory(slot)
    else:
        controls.preset_browser.open(slot)


def _track_preset_label(state: TuningViewState, desc: RowDescriptor) -> str:
    """"previewing" while a picked preset holds the layer's switching."""
    if desc.slot is not None and desc.slot in state.tracks:
        runtime = state.tracks[desc.slot].runtime
        if runtime.switching_paused and runtime.preset_switching == "on":
            return "previewing"
    return "preset"


# Tooltips name only mouse gestures: whoever reads one is using the mouse.
PRESET_BROWSER_TOOLTIP = "Double-click to open the preset browser"


def preset_row_problem(state: TuningViewState, desc: RowDescriptor) -> str | None:
    """Why the folder on the directory row, or the preset file on a preset row
    or preset list entry, cannot be used."""
    if desc.slot is None or desc.slot not in state.tracks:
        return None
    block = state.tracks[desc.slot]
    if desc.kind is RowKind.TRACK_PRESET_DIR:
        return block.preset_dir_problem
    if desc.kind is RowKind.TRACK_PRESET:
        return block.preset_problem
    if desc.kind is RowKind.TRACK_PRESET_LIST_ITEM and desc.preset_index is not None:
        if desc.preset_index < len(block.preset_list_problems):
            return block.preset_list_problems[desc.preset_index]
    return None


def _preset_row_tooltip(state: TuningViewState, desc: RowDescriptor) -> str:
    problem = preset_row_problem(state, desc)
    if problem is not None:
        return f"{problem}\n{PRESET_BROWSER_TOOLTIP}"
    return PRESET_BROWSER_TOOLTIP


def _stem_row_tooltip(state: TuningViewState, desc: RowDescriptor) -> str:
    block = _track_block(state, desc)
    if not block.stem_silent:
        return ""
    return (
        f"The {stem_control_label(block.runtime.stem)} stem is silent in this "
        "song, so this layer has no audio to react to"
    )


def _preset_list_item_tooltip(state: TuningViewState, desc: RowDescriptor) -> str:
    return preset_row_problem(state, desc) or ""


def _preset_dir_row_tooltip(state: TuningViewState, desc: RowDescriptor) -> str:
    if _preset_dir_can_go_down(state, desc):
        click = "Double-click to open the first subfolder"
    else:
        click = PRESET_BROWSER_TOOLTIP
    problem = preset_row_problem(state, desc)
    return click if problem is None else f"{problem}\n{click}"


def _preset_dir_up_tooltip(state: TuningViewState, desc: RowDescriptor) -> str:
    if _preset_dir_can_go_up(state, desc):
        return "Up to the parent folder"
    return "Already at the top of this pack"


def _preset_dir_down_tooltip(state: TuningViewState, desc: RowDescriptor) -> str:
    if _preset_dir_can_go_down(state, desc):
        return "Open the first subfolder"
    return "No subfolders here"


def _apply_preset_browse_action(controls: TuningControls, desc: RowDescriptor) -> None:
    slot = desc.slot
    if slot is None:
        return
    controls.preset_browser.open(slot)


def _apply_preset_dir_parent_action(
    controls: TuningControls, desc: RowDescriptor
) -> None:
    slot = desc.slot
    if slot is None:
        return
    controls.layer_mutations.parent_directory(slot)


def _apply_preset_add_to_list_action(
    controls: TuningControls, desc: RowDescriptor
) -> None:
    slot = desc.slot
    if slot is None:
        return
    controls.preset_list.add_current(slot)


def _preset_can_add_to_list(state: TuningViewState, desc: RowDescriptor) -> bool:
    return (
        not is_preset_curation_mode(state.settings.editor_mode)
        and _track_block(state, desc).runtime.preset_switching_trigger != "off"
    )


def _preset_add_to_list_tooltip(state: TuningViewState, desc: RowDescriptor) -> str:
    if _preset_can_add_to_list(state, desc):
        return "Add to preset list (P)"
    return "Turn on preset switching to keep a preset list"


def _apply_preset_list_item_action(
    controls: TuningControls, desc: RowDescriptor
) -> None:
    slot = desc.slot
    index = desc.preset_index
    if slot is None or index is None:
        return
    controls.preset_list.audition(slot, index)


def _open_preset_list_item_replace(
    controls: TuningControls, desc: RowDescriptor
) -> None:
    """Double-click: open the preset browser to replace this entry."""
    slot = desc.slot
    index = desc.preset_index
    if slot is None or index is None:
        return
    if controls.preset_list.project_dir is None:
        return
    controls.preset_browser.open(slot, replace_index=index)


def _apply_preset_switching_resume_action(
    controls: TuningControls, desc: RowDescriptor
) -> None:
    slot = desc.slot
    if slot is None:
        return
    controls.preset_list.resume(slot)


def _apply_layer_add_action(controls: TuningControls, _desc: RowDescriptor) -> None:
    if is_preset_curation_mode(controls.session.settings.editor_mode):
        return
    command_by_id("layers.add").run(controls)


def _apply_layer_delete_action(controls: TuningControls, _desc: RowDescriptor) -> None:
    if is_preset_curation_mode(controls.session.settings.editor_mode):
        return
    command_by_id("layers.delete").run(controls)


def _jump_track_preset_switching_trigger(
    controls: TuningControls, desc: RowDescriptor, delta: int
) -> None:
    if desc.slot is not None:
        controls.layer_mutations.step_preset_switching_trigger(desc.slot, delta=delta)

def _jump_track_stem(controls: TuningControls, desc: RowDescriptor, delta: int) -> None:
    if desc.slot is not None:
        controls.layer_mutations.step_stem(desc.slot, delta=delta)

def _jump_track_blend(controls: TuningControls, desc: RowDescriptor, delta: int) -> None:
    if desc.slot is not None:
        controls.layer_mutations.step_blend(desc.slot, delta=delta)

SPECS: dict[RowKind, RowSpec] = {
    RowKind.TRACK_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="Layer",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_track,
        help_title="Layer",
        help_description=(
            "One projectM visualiser, driven by a single audio stem and stacked with the other layers to build the final picture.",
        ),
        toggle_enabled=_toggle_track_enabled,
        toggle_solo=_toggle_track_solo,
        can_enter_move_mode=True,
    ),
    RowKind.TRACK_ENABLED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="enabled",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_enabled,
        apply_horizontal=_apply_track_enabled,
        choice=bool_choice(lambda s, d: _track_block(s, d).runtime.enabled),
        inert=lambda state, _desc: state.timeline.enabled,
        help_title="Layer Enabled",
        help_description=(
            "Shows or hides the layer. While the timeline is on, its clips control visibility and this switch is ignored.",
        ),
        parent_group="track",
        blocked_by_section_lock=True,
    ),
    RowKind.TRACK_SOLO: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="solo",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_solo,
        apply_horizontal=_apply_track_solo,
        choice=bool_choice(lambda s, d: s.solo_slot == d.slot),
        help_title="Layer Solo",
        help_description=(
            "Isolates this layer so you can judge it on its own, without touching the other layers' settings.",
        ),
        parent_group="track",
        blocked_by_section_lock=False,
    ),
    RowKind.TRACK_LOCKED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="lock",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_locked,
        apply_horizontal=_apply_track_locked,
        choice=bool_choice(lambda s, d: _track_block(s, d).runtime.locked, lock_text),
        help_title="Layer Lock",
        help_description=(
            "Protects the layer's settings from accidental edits while you work elsewhere.",
        ),
        parent_group="track",
        blocked_by_section_lock=False,
    ),
    RowKind.TRACK_MILKDROP_PRESET_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="milkdrop preset",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Milkdrop Preset",
        help_description=(
            "The Milkdrop preset this layer renders, and how hard it responds to the beat.",
        ),
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_DIR: RowSpec(
        affordance=RowAffordance.PATH_DIR,
        panel_label="preset directory",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_track_preset_dir,
        format_position=_format_track_preset_dir_position,
        nav_buttons=(
            RowNavButton(
                ARROW_UPWARD_GLYPH,
                _preset_dir_can_go_up,
                _apply_preset_dir_parent_action,
                tooltip=_preset_dir_up_tooltip,
            ),
            RowNavButton(
                ARROW_DOWNWARD_GLYPH,
                _preset_dir_can_go_down,
                _apply_preset_dir_action,
                tooltip=_preset_dir_down_tooltip,
            ),
        ),
        tooltip=_preset_dir_row_tooltip,
        apply_horizontal=_apply_track_preset_dir,
        apply_action=_apply_preset_dir_open_action,
        activate_on_double_click=True,
        fit_strategy=FitStrategy.NONE,
        help_title="Preset Directory",
        help_description=(
            "The folder this layer browses for presets. Click a folder in the path to go back to it. The up arrow moves to the parent folder; the down arrow, Enter, or a double-click opens the first subfolder, and with no subfolders Enter or a double-click opens the preset browser.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET: RowSpec(
        affordance=RowAffordance.PATH_PRESET,
        panel_label="preset",
        format_label=_track_preset_label,
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_track_preset,
        format_position=_format_track_preset_position,
        format_markers=_format_track_preset_markers,
        marker_tags=_track_preset_tags,
        nav_buttons=(
            RowNavButton(
                ADD_GLYPH,
                _preset_can_add_to_list,
                _apply_preset_add_to_list_action,
                tooltip=_preset_add_to_list_tooltip,
            ),
        ),
        nav_buttons_before_value=True,
        tooltip=_preset_row_tooltip,
        apply_horizontal=_apply_track_preset,
        apply_action=_apply_preset_browse_action,
        activate_on_double_click=True,
        fit_strategy=FitStrategy.NONE,
        help_title="Milkdrop Preset File",
        help_description=(
            "The Milkdrop preset this layer is rendering. Enter or a double-click opens the preset browser, to see every folder and preset and filter them by name. While preset switching is on, the + button left of the arrows adds this preset to the layer's preset list (P does the same from any row of the layer); while previewing, that is the one you are previewing, and the file is copied into the project so it travels with it. Markers after the name show its curation status and role; hover over one for a reminder (a favourite's lists its tags):",
        ),
        help_mode_entries=_PRESET_MARKER_HELP_ENTRIES,
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_SWITCHING: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="preset switching",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Preset Switching",
        help_description=(
            "Moves the layer through a list of presets automatically, on a timer, on projectM's own schedule, or on timeline clips.",
        ),
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_SWITCHING_RESUME: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Resume switching",
        present_style=RowPresentStyle.FULL_LINE,
        apply_horizontal=noop_horizontal,
        apply_action=_apply_preset_switching_resume_action,
        fit_strategy=FitStrategy.NONE,
        help_title="Resume Switching",
        help_description=(
            "Picking a preset yourself, in the preset browser or the preset list, previews it and holds switching. This ends the preview: the layer jumps to the list entry scheduled for this point in the song (highlighted in the list), as if you had never previewed.",
        ),
        parent_group="track",
        blocked_by_section_lock=True,
    ),
    RowKind.TRACK_PRESET_SWITCHING_TRIGGER: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="change presets",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_preset_switching_trigger,
        apply_horizontal=_apply_track_preset_switching_trigger,
        choice=options_choice(PRESET_SWITCHING_TRIGGERS, lambda s, d: _track_block(s, d).runtime.preset_switching_trigger, preset_switching_trigger_display, jump=_jump_track_preset_switching_trigger),
        help_title="Change Presets",
        help_entries=(("Left/Right", "choose when presets change"),),
        help_description=(
            "When the layer moves on to another preset. The timeline decides when a layer is on screen; this decides which preset it shows.",
        ),
        help_mode_entries=PRESET_SWITCHING_TRIGGER_HELP_ENTRIES,
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_LIST: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="preset list",
        present_style=RowPresentStyle.HEADING,
        format_value=_format_track_preset_list_count,
        fit_strategy=FitStrategy.NONE,
        help_title="Preset List",
        help_description=(
            "The presets this layer cycles through, in playback order.",
        ),
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_LIST_ITEM: RowSpec(
        affordance=RowAffordance.PATH_PRESET,
        panel_label="preset",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_track_preset_list_item,
        format_position=_format_track_preset_list_item_position,
        format_markers=_format_track_preset_list_item_markers,
        marker_tags=_track_preset_list_item_tags,
        tooltip=_preset_list_item_tooltip,
        apply_action=_apply_preset_list_item_action,
        double_click_action=_open_preset_list_item_replace,
        fit_strategy=FitStrategy.NONE,
        help_title="Preset List Entry",
        help_description=(
            "A preset in this layer's switching list. The highlighted entry is the one scheduled for this point in the song.",
            "On a timer, the time is when the entry first plays. On each clip, it is when its clip starts; a spare is on no clip.",
            "Right-click for more ways to edit the list.",
            "Markers after the name show its curation status and role; hover over one for a reminder (a favourite's lists its tags):",
        ),
        help_mode_entries=_PRESET_LIST_MARKER_HELP_ENTRIES,
        can_enter_move_mode=True,
        drag_reorder=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_DURATION: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="duration",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_preset_duration,
        apply_horizontal=_apply_track_preset_duration,
        help_title="Preset Duration",
        help_entries=(("Left/Right", "adjust value"),),
        help_description=(
            "How long each preset plays, in seconds, before the next one takes over.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_SOFT_CUT_DURATION: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="soft cut",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_soft_cut_duration,
        apply_horizontal=_apply_track_soft_cut_duration,
        help_title="Soft Cut",
        help_entries=(("Left/Right", "adjust value"),),
        help_description=(
            "Length of projectM's blend between consecutive presets, in seconds. Longer values give slower, smoother morphs.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_EASTER_EGG: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="easter egg",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_easter_egg,
        apply_horizontal=_apply_track_easter_egg,
        help_title="Easter Egg",
        help_entries=(
            ("Left/Right", "adjust value"),
            ("PgUp/PgDn", "large step"),
        ),
        help_description=(
            "Randomises each preset's duration around the set value, so changes feel less mechanical.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_START_CLEAN: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="start clean",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_preset_start_clean,
        apply_horizontal=_apply_track_preset_start_clean,
        choice=bool_choice(lambda s, d: _track_block(s, d).runtime.preset_start_clean, preset_start_clean_display),
        help_title="Start Clean",
        help_entries=(("Left/Right", "yes / no"),),
        help_description=(
            "Starts each new preset from a black frame instead of letting it build on the previous preset's last image. Off gives more continuity between presets.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_HARD_CUT_ENABLED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="hard cut",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_hard_cut_enabled,
        apply_horizontal=_apply_track_hard_cut_enabled,
        choice=bool_choice(lambda s, d: _track_block(s, d).runtime.hard_cut_enabled, hard_cut_enabled_display),
        help_title="Hard Cut",
        help_entries=(("Left/Right", "enabled / disabled"),),
        help_description=(
            "Lets projectM jump straight to the next preset on a strong beat, skipping the blend. Good for punchy, rhythmic material.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_HARD_CUT_DURATION: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="hard cut min",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_hard_cut_duration,
        apply_horizontal=_apply_track_hard_cut_duration,
        help_title="Hard Cut Min",
        help_entries=(("Left/Right", "adjust value"),),
        help_description=(
            "Minimum gap between hard cuts, in seconds, so busy passages do not trigger a cut on every hit.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_HARD_CUT_SENSITIVITY: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="hard cut sens",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_hard_cut_sensitivity,
        apply_horizontal=_apply_track_hard_cut_sensitivity,
        help_title="Hard Cut Sens",
        help_entries=(("Left/Right", "adjust value"),),
        help_description=(
            "How strong a beat must be to trigger a hard cut. Raise it if cuts are too frequent.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_STEM: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="driving stem",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_stem,
        tooltip=_stem_row_tooltip,
        apply_horizontal=_apply_track_stem,
        choice=options_choice(active_stem_sources, lambda s, d: _track_block(s, d).runtime.stem, stem_control_label, jump=_jump_track_stem),
        help_title="Stem",
        help_entries=(("Left/Right", "choose stem source"),),
        help_description=(
            "The audio stem this layer reacts to. Changing it resets the layer's Cleave Effects, since their drivers depend on the stem.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_BLEND: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="blend mode",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_blend,
        apply_horizontal=_apply_track_blend,
        choice=options_choice(BLEND_MODES, lambda s, d: _track_block(s, d).runtime.blend_mode, jump=_jump_track_blend),
        help_title="Blend Mode",
        help_description=(
            "How this layer combines with everything beneath it. Pattern Mask overrides this while it is on.",
        ),
        help_mode_entries=BLEND_MODE_HELP_ENTRIES,
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_OPACITY: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="opacity",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_opacity,
        apply_horizontal=_apply_track_opacity,
        help_title="Opacity",
        help_description=(
            "The layer's overall opacity. Pattern Mask overrides this while it is on.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_BEAT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="beat sensitivity",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_beat,
        apply_horizontal=_apply_track_beat,
        help_title="Beat Sensitivity",
        help_description=(
            "How hard the preset responds to the beat. Higher values give more movement; lower values suit calmer, ambient layers.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_COMPOSITING_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="compositing",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Compositing",
        help_description=(
            "Blend mode and opacity: how this layer combines with the layers beneath it. Pattern Mask overrides both while it is on.",
        ),
        parent_group="track",
    ),
    RowKind.TRACK_EFFECTS_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="cleave effects",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Cleave Effects",
        help_description=(
            "Audio-reactive effects Cleave adds on top of the preset, each driven by this layer's stem.",
        ),
        parent_group="track",
    ),
    RowKind.TRACK_EFFECT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="",
        present_style=RowPresentStyle.DYNAMIC,
        format_value=_format_track_effect,
        apply_horizontal=_apply_track_effect,
        help_title="Cleave Effects",
        help_description=(
            "Effect depth. 0 bypasses it.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.LAYER_MANAGEMENT_COUNT: RowSpec(
        affordance=RowAffordance.DISPLAY,
        panel_label="",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_layer_count,
        navigable=False,
    ),
    RowKind.LAYER_MANAGEMENT_ADD: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Add layer",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_layer_add_action,
        fit_strategy=FitStrategy.NONE,
        help_title="Add Layer",
        help_description=(
            "Adds a layer at the top of the stack. A project can hold up to eight.",
        ),
    ),
    RowKind.LAYER_MANAGEMENT_DELETE: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Delete layer…",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_layer_delete_action,
        fit_strategy=FitStrategy.NONE,
        help_title="Delete Layer",
        help_description=(
            "Removes this layer and all its settings. A project needs at least one layer, so the last one cannot be deleted.",
        ),
        parent_group="track",
        blocked_by_section_lock=False,
        navigable_when_section_locked=True,
    ),
}
