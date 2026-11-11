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
from cleave.stems import stem_control_label
from cleave.viz.commands import command_by_id
from cleave.viz.material_icons import ARROW_DOWNWARD_GLYPH, ARROW_UPWARD_GLYPH
from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import FitStrategy, RowNavButton, RowPresentStyle, RowSpec
from cleave.viz.row_specs.common import lock_text, noop_horizontal, on_off_text
from cleave.viz.tuning_view_state import TrackBlock, TuningViewState

from cleave.blend_modes import BLEND_MODES
from cleave.config_schema.layers import PRESET_SWITCHING_TRIGGERS
from cleave.stems import STEM_SOURCES
from cleave.viz.row_specs.common import bool_choice, options_choice
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

def _format_track_preset_markers(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _track_block(state, desc).preset_markers

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
    total = len(_track_block(state, desc).preset_list_labels)
    return f"{desc.preset_index + 1}/{total}"

def _format_track_preset_list_item_markers(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    assert desc.preset_index is not None
    return _track_block(state, desc).preset_list_markers[desc.preset_index]

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


def _apply_preset_dir_parent_action(
    controls: TuningControls, desc: RowDescriptor
) -> None:
    slot = desc.slot
    if slot is None:
        return
    controls.layer_mutations.parent_directory(slot)


def _apply_preset_list_add_action(
    controls: TuningControls, desc: RowDescriptor
) -> None:
    slot = desc.slot
    if slot is None:
        return
    controls.preset_list.add_current(slot)


def _apply_preset_list_item_action(
    controls: TuningControls, desc: RowDescriptor
) -> None:
    slot = desc.slot
    index = desc.preset_index
    if slot is None or index is None:
        return
    controls.preset_list.audition(slot, index)


def _apply_preset_switching_resume_action(
    controls: TuningControls, desc: RowDescriptor
) -> None:
    slot = desc.slot
    if slot is None:
        return
    controls.preset_list.resume(slot)


def _apply_preset_list_populate_action(
    controls: TuningControls, desc: RowDescriptor
) -> None:
    slot = desc.slot
    if slot is None:
        return
    controls.preset_list.prompt_populate(slot)


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
            "A projectM visualiser layer.",
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
            "Shows or hides this layer.",
            "When the timeline is on, the timeline shows and hides the layer instead.",
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
        help_description=("Shows only this layer.",),
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
        help_description=("When locked, you cannot change the layer settings.",),
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
            "The Milkdrop preset of this layer, and how strongly it reacts to the beat.",
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
            ),
            RowNavButton(
                ARROW_DOWNWARD_GLYPH,
                _preset_dir_can_go_down,
                _apply_preset_dir_action,
            ),
        ),
        apply_horizontal=_apply_track_preset_dir,
        apply_action=_apply_preset_dir_action,
        activate_on_double_click=True,
        fit_strategy=FitStrategy.NONE,
        help_title="Preset Directory",
        help_description=(
            "The directory that contains the presets for this layer.",
            "Click the up arrow to open the parent directory.",
            "Click the down arrow, or double-click, to open the first subdirectory.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET: RowSpec(
        affordance=RowAffordance.PATH_PRESET,
        panel_label="preset",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_track_preset,
        format_position=_format_track_preset_position,
        format_markers=_format_track_preset_markers,
        apply_horizontal=_apply_track_preset,
        fit_strategy=FitStrategy.NONE,
        help_title="Milkdrop Preset File",
        help_description=(
            "The Milkdrop preset that this layer shows.",
            "[F], [B], and [U] mark a favourite, blacklisted, or user preset.",
            "[R:X] shows the preset role:",
        ),
        help_mode_entries=CUE_ROLE_MARKER_HELP_ENTRIES,
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
            "Changes the preset of this layer automatically, from a list.",
        ),
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_SWITCHING_RESUME: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Resume",
        present_style=RowPresentStyle.FULL_LINE,
        apply_horizontal=noop_horizontal,
        apply_action=_apply_preset_switching_resume_action,
        fit_strategy=FitStrategy.NONE,
        help_title="Resume Switching",
        help_description=(
            "Stops manual browsing and starts automatic switching again.",
        ),
        parent_group="track",
        blocked_by_section_lock=True,
    ),
    RowKind.TRACK_PRESET_SWITCHING_TRIGGER: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="trigger",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_preset_switching_trigger,
        apply_horizontal=_apply_track_preset_switching_trigger,
        choice=options_choice(PRESET_SWITCHING_TRIGGERS, lambda s, d: _track_block(s, d).runtime.preset_switching_trigger, preset_switching_trigger_display, jump=_jump_track_preset_switching_trigger),
        help_title="Trigger",
        help_entries=(("Left/Right", "choose trigger"),),
        help_description=(
            "What moves the layer to the next preset in the list.",
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
            "The presets that this layer switches through, in order.",
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
        apply_action=_apply_preset_list_item_action,
        fit_strategy=FitStrategy.NONE,
        help_title="Preset List Entry",
        help_description=(
            "A preset in the switching list of this layer.",
            "[F] and [B] mark a favourite or blacklisted preset.",
            "[R:X] shows the preset role:",
        ),
        help_mode_entries=CUE_ROLE_MARKER_HELP_ENTRIES,
        can_enter_move_mode=True,
        drag_reorder=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_LIST_ADD: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Add To Preset List",
        present_style=RowPresentStyle.FULL_LINE,
        apply_horizontal=noop_horizontal,
        apply_action=_apply_preset_list_add_action,
        fit_strategy=FitStrategy.NONE,
        help_title="Add To Preset List",
        help_description=(
            "Adds the current preset to the end of the list.",
            "When switching is paused, this is the preset that you browsed to.",
            "Cleave copies the preset file into the project.",
            "Press P on any row of the layer to do the same.",
        ),
        parent_group="track",
        blocked_by_section_lock=True,
    ),
    RowKind.TRACK_PRESET_LIST_POPULATE: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Populate...",
        present_style=RowPresentStyle.FULL_LINE,
        apply_horizontal=noop_horizontal,
        apply_action=_apply_preset_list_populate_action,
        fit_strategy=FitStrategy.NONE,
        help_title="Populate Presets",
        help_entries=(("Enter", "choose a directory"),),
        help_description=(
            "Replaces the full list with the presets from a directory.",
        ),
        parent_group="track",
        blocked_by_section_lock=True,
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
            "Seconds that each preset plays before the next one starts.",
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
            "Seconds that projectM takes to blend from one preset to the next.",
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
            "How much projectM changes each preset duration at random.",
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
            "When on, each new preset starts from a blank frame, not from the last frame.",
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
            "When on, projectM can change the preset immediately on a strong beat, with no blend.",
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
            "Minimum seconds between two hard cuts.",
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
            "How strong a beat must be to cause a hard cut.",
            "A higher value gives fewer hard cuts.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_STEM: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="driving stem",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_stem,
        apply_horizontal=_apply_track_stem,
        choice=options_choice(STEM_SOURCES, lambda s, d: _track_block(s, d).runtime.stem, stem_control_label, jump=_jump_track_stem),
        help_title="Stem",
        help_entries=(("Left/Right", "choose stem source"),),
        help_description=(
            "The audio stem that this layer reacts to.",
            "When you change the stem, the Cleave Effects of the layer reset.",
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
            "How this layer mixes with the layers below it.",
            "Pattern Mask replaces this when it is on.",
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
            "How visible this layer is.",
            "0% hides it.",
            "Pattern Mask replaces this when it is on.",
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
            "How strongly this layer reacts to the beat.",
            "A higher value makes the visuals move more.",
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
            "How this layer mixes with the layers below it.",
            "Pattern Mask replaces these settings when it is on.",
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
            "Effects on this layer that follow the audio.",
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
            "The strength of this effect.",
            "0 turns it off.",
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
            "Adds a new layer on top of the others.",
            "You can have up to eight layers.",
        ),
    ),
    RowKind.LAYER_MANAGEMENT_DELETE: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Delete layer...",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_layer_delete_action,
        fit_strategy=FitStrategy.NONE,
        help_title="Delete Layer",
        help_description=(
            "Removes this layer permanently.",
            "You cannot delete the last layer.",
        ),
        parent_group="track",
        blocked_by_section_lock=False,
        navigable_when_section_locked=True,
    ),
}
