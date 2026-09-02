"""Track / layer row specs for the live tuning overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.blend_modes import BLEND_MODE_HELP_ENTRIES
from cleave.config_schema.layers import (
    PRESET_SWITCHING_MODE_HELP_ENTRIES,
    PRESET_SWITCHING_TRIGGER_HELP_ENTRIES,
    hard_cut_enabled_display,
    preset_start_clean_display,
    preset_switching_display,
    preset_switching_trigger_display,
)
from cleave.cue_roles import CUE_ROLE_MARKER_HELP_ENTRIES
from cleave.stems import stem_control_label
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_sections import apply_expand_toggle
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.row_specs.common import apply_expand_subheader, noop_horizontal
from cleave.viz.tuning_view_state import TrackBlock, TuningViewState

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

def _format_track_preset_switching_mode(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return preset_switching_display(_track_block(state, desc).runtime.preset_switching)

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
    controls: TuningControls, desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.cycle_stem(desc.slot, forward=forward)

def _apply_track_blend(
    controls: TuningControls, desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.cycle_blend(desc.slot, forward=forward)

def _apply_track_opacity(
    controls: TuningControls, desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    step = 10 if ctrl else 1
    delta = step if forward else -step
    controls.layer_mutations.set_opacity(
        desc.slot, controls.session.layers[desc.slot].opacity_pct + delta
    )

def _apply_track_beat(
    controls: TuningControls, desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    step = 0.1 if ctrl else 0.01
    delta = step if forward else -step
    controls.layer_mutations.set_beat(
        desc.slot, controls.session.layers[desc.slot].beat_sensitivity + delta
    )

def _apply_track_preset_switching_mode(
    controls: TuningControls, desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.cycle_preset_switching(desc.slot, forward=forward)

def _apply_track_preset_switching_trigger(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.cycle_preset_switching_trigger(desc.slot, forward=forward)

def _apply_track_preset_duration(
    controls: TuningControls, desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.step_preset_duration(desc.slot, forward=forward, ctrl=ctrl)

def _apply_track_soft_cut_duration(
    controls: TuningControls, desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.step_soft_cut_duration(desc.slot, forward=forward, ctrl=ctrl)

def _apply_track_easter_egg(
    controls: TuningControls, desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.step_easter_egg(desc.slot, forward=forward, ctrl=ctrl)

def _apply_track_preset_start_clean(
    controls: TuningControls, desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.cycle_preset_start_clean(desc.slot, forward=forward)

def _apply_track_hard_cut_enabled(
    controls: TuningControls, desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.cycle_hard_cut_enabled(desc.slot, forward=forward)

def _apply_track_hard_cut_duration(
    controls: TuningControls, desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls.layer_mutations.step_hard_cut_duration(desc.slot, forward=forward, ctrl=ctrl)

def _apply_track_hard_cut_sensitivity(
    controls: TuningControls, desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    step = 0.1 if ctrl else 0.01
    delta = step if forward else -step
    controls.layer_mutations.set_hard_cut_sensitivity(
        desc.slot, controls.session.layers[desc.slot].hard_cut_sensitivity + delta
    )

def _apply_track_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    shift: bool,
) -> None:
    from cleave.viz.row_spec import row_spec
    slot = desc.slot
    if slot is None:
        return
    if shift:
        if forward:
            controls.layer_mutations.enter_solo(slot)
        else:
            controls.layer_mutations.exit_solo(slot)
        return
    if ctrl:
        if (
            controls.session.layers[slot].locked
            and row_spec(desc.kind).can_enable_disable
        ):
            return
        controls.layer_mutations.set_enabled(slot, forward)
        return
    apply_expand_toggle(controls, desc.kind, slot, forward, card=desc.card)

def _format_track_preset_dir(state: TuningViewState, desc: RowDescriptor) -> str:
    return _track_block(state, desc).preset_dir_label

def _format_track_preset(state: TuningViewState, desc: RowDescriptor) -> str:
    return _track_block(state, desc).preset_label

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
    ctrl: bool,
    _shift: bool,
) -> None:
    slot = desc.slot
    if slot is None:
        return
    if ctrl:
        if forward:
            controls.layer_mutations.enter_directory(slot)
        else:
            controls.layer_mutations.parent_directory(slot)
        return
    controls.layer_mutations.step_directory(slot, forward=forward)

def _apply_track_preset(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    slot = desc.slot
    if slot is None:
        return
    controls.layer_mutations.step_preset(slot, forward=forward, ctrl=ctrl)

def _apply_track_effect(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    slot = desc.slot
    if slot is None:
        return
    effect_id = desc.effect_id
    driver_slug = desc.driver_slug
    if effect_id is None or driver_slug is None:
        return
    step = 10 if ctrl else 1
    delta = step if forward else -step
    current = controls.session.layers[slot].effects.get(effect_id, {}).get(
        driver_slug, 0
    )
    controls.layer_mutations.set_effect(slot, effect_id, driver_slug, current + delta)

def _visibility_track(
    state: TuningViewState, desc: RowDescriptor
) -> tuple[bool, bool]:
    assert desc.slot is not None
    block = state.tracks[desc.slot]
    return (block.visible, state.solo_slot == desc.slot)

SPECS: dict[RowKind, RowSpec] = {
    RowKind.TRACK_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="Layer",
        present_style=RowPresentStyle.TRACK_HEADER,
        apply_horizontal=_apply_track_header,
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_track,
        help_title="Layer",
        help_description=(
            "projectM visualiser layer.",
        ),
        quick_nav_target=True,
        can_enable_disable=True,
        can_solo=True,
        can_enter_move_mode=True,
    ),
    RowKind.TRACK_PRESET_DIR: RowSpec(
        affordance=RowAffordance.PATH_DIR,
        panel_label="preset directory",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_track_preset_dir,
        apply_horizontal=_apply_track_preset_dir,
        fit_strategy=FitStrategy.COUNTER_LABEL,
        help_title="Preset Directory",
        help_description=(
            "Directory from which presets are browsed for this layer.",
            "[▲▼] marks when a parent and/or child directory is available.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET: RowSpec(
        affordance=RowAffordance.PATH_PRESET,
        panel_label="preset",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_track_preset,
        apply_horizontal=_apply_track_preset,
        fit_strategy=FitStrategy.COUNTER_LABEL,
        help_title="Milkdrop Preset File",
        help_description=(
            "Currently active Milkdrop preset for this layer.",
            "[F/B/U] indicates favourited/blacklisted/user-defined.",
            "[R:X] indicates the chosen role.",
        ),
        help_mode_entries=CUE_ROLE_MARKER_HELP_ENTRIES,
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_SWITCHING: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="preset switching",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        format_value=_format_track_preset_switching_mode,
        apply_horizontal=_apply_track_preset_switching_mode,
        fit_strategy=FitStrategy.NONE,
        help_title="Preset switching",
        help_entries=(("Left/Right", "off / on"),),
        help_description=(
            "When on, advances through this layer's ordered preset list.",
            "The trigger chooses timer, projectM, or timeline on-transitions.",
        ),
        help_mode_entries=PRESET_SWITCHING_MODE_HELP_ENTRIES,
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_SWITCHING_TRIGGER: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="trigger",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_preset_switching_trigger,
        apply_horizontal=_apply_track_preset_switching_trigger,
        help_title="Trigger",
        help_entries=(("Left/Right", "cycle trigger"),),
        help_description=(
            "How the ordered preset list advances while switching is on.",
            "Timeline trigger needs Render: TIMELINE enabled.",
        ),
        help_mode_entries=PRESET_SWITCHING_TRIGGER_HELP_ENTRIES,
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_LIST: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="preset list",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        format_value=_format_track_preset_list_count,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="preset list",
        help_description=(
            "Ordered presets used for automatic switching on this layer.",
            "Expand to reorder, delete, or add the current browse preset.",
        ),
        is_sub_header=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_LIST_ITEM: RowSpec(
        affordance=RowAffordance.PATH_PRESET,
        panel_label="preset",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_track_preset_list_item,
        apply_horizontal=noop_horizontal,
        fit_strategy=FitStrategy.COUNTER_LABEL,
        help_title="preset list entry",
        help_description=(
            "Preset in this layer's switching list.",
            "[F/B] indicates favourited/blacklisted.",
            "[R:X] indicates the chosen role.",
        ),
        help_mode_entries=CUE_ROLE_MARKER_HELP_ENTRIES,
        can_enter_move_mode=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_LIST_ADD: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="add current preset",
        present_style=RowPresentStyle.FULL_LINE,
        apply_horizontal=noop_horizontal,
        fit_strategy=FitStrategy.NONE,
        shows_enter_icon=True,
        help_title="Add Current Preset",
        help_description=(
            "Add the layer's current browse preset to the end of the list.",
            "Copies the preset file into the project presets folder.",
            "U on any row in the layer is the same action.",
        ),
        parent_group="track",
        blocked_by_section_lock=True,
    ),
    RowKind.TRACK_PRESET_LIST_POPULATE: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="populate presets",
        present_style=RowPresentStyle.FULL_LINE,
        apply_horizontal=noop_horizontal,
        fit_strategy=FitStrategy.NONE,
        shows_enter_icon=True,
        help_title="Populate Presets",
        help_description=(
            "Replace the entire preset list from the current directory "
            "(random or sequential) or random cue marker role pools.",
            "Enter opens a choice modal.",
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
        help_title="Preset duration",
        help_entries=(("Left/Right", "step value"),),
        help_description=(
            "Seconds between timer advances, and projectM preset duration.",
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
        help_title="Soft cut",
        help_entries=(("Left/Right", "step value"),),
        help_description=(
            "Duration of the crossfade when projectM blends between presets.",
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
        help_title="Easter egg",
        help_entries=(
            ("Left/Right", "step value"),
            ("Ctrl + Left/Right", "large step"),
        ),
        help_description=(
            "How much projectM randomizes preset duration (Milkdrop legacy gaussian).",
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
        help_title="Start clean",
        help_entries=(("Left/Right", "yes / no"),),
        help_description=(
            "When enabled, each new preset starts with a blank canvas",
            "instead of inheriting the previous frame.",
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
        help_title="Hard cut",
        help_entries=(("Left/Right", "enabled / disabled"),),
        help_description=(
            "Whether projectM can switch presets instantly on strong beats",
            "(bypassing soft cut).",
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
        help_title="Hard cut min",
        help_entries=(("Left/Right", "step value"),),
        help_description=(
            "Time window after a hard cut before another can fire.",
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
        help_title="Hard cut sens",
        help_entries=(("Left/Right", "step value"),),
        help_description=(
            "Beat energy threshold required to trigger a hard cut.",
            "Higher = less frequent.",
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
        help_title="Stem",
        help_entries=(("Left/Right", "cycle stem source"),),
        help_description=(
            "Audio stem fed to libprojectM for this layer's beat detection",
            "and waveform display.",
            "Effects reset when the stem changes.",
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
        help_title="Blend mode",
        help_description=(
            "How this layer is composited onto the layers below it.",
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
        help_description=("Opacity of this layer.",),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_BEAT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="beat sensitivity",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_beat,
        apply_horizontal=_apply_track_beat,
        help_title="Beat sensitivity",
        help_description=(
            "Beat sensitivity multiplier for this layer.",
            "Higher values make the visuals more reactive.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_EFFECTS_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="cleave effects",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="Cleave Effects",
        help_description=(
            "Cleave audio-driven effects applied to this layer's output.",
        ),
        is_sub_header=True,
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
            "Depth of this effect.",
            "0 disables it.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.LAYER_MANAGEMENT_ADD: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="Add Layer",
        present_style=RowPresentStyle.FULL_LINE,
        fit_strategy=FitStrategy.NONE,
        shows_enter_icon=True,
        help_title="Add Layer",
        help_description=(
            "Add a new layer at the top of the z-order.",
            "Maximum eight layers.",
        ),
    ),
    RowKind.LAYER_MANAGEMENT_DELETE: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="Delete Layer",
        present_style=RowPresentStyle.FULL_LINE,
        fit_strategy=FitStrategy.NONE,
        shows_enter_icon=True,
        help_title="Delete layer",
        help_description=(
            "Remove this layer permanently.",
            "At least one layer must remain.",
        ),
        parent_group="track",
        blocked_by_section_lock=False,
        navigable_when_section_locked=True,
    ),
}
