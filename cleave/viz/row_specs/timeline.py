"""Timeline and song-marker row specs for the live tuning overlay."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, TypeVar

from cleave.choice import step_choice
from cleave.config_schema.layers import hard_cut_enabled_display
from cleave.config_schema.timeline import (
    TIMELINE_FADE_DURATION_STEP,
    clamp_timeline_fade_duration,
    step_timeline_placement_snap,
    timeline_crossfade_display,
)
from cleave.song_markers import (
    DEFAULT_SONG_MARKER_TYPE,
    SONG_MARKER_TYPES,
    SongMarker,
    SongMarkerType,
    step_song_marker_type,
    format_marker_time,
    parse_song_marker_type,
    song_marker_gesture_warning,
)
from cleave.timeline_presets import (
    TIMELINE_PRESET_HELP_ENTRIES,
    TIMELINE_RESET_HELP_ENTRIES,
)
from cleave.blend_modes import BLEND_MODES, BlendMode
from cleave.choice import choice_index
from cleave.cue_roles import CUE_ROLES, CueRole
from cleave.cut_types import CUT_TYPES, CutType
from cleave.timeline import SlotCue, cue_editable_for_blend_role
from cleave.viz.commands import command_by_id
from cleave.viz.playback import current_sec, format_mmss
from cleave.viz.timeline_cue_edits import (
    cue_selection_allowed,
    nudge_cue_level,
    selected_cue,
    set_cue_blend,
    set_cue_cut,
    set_cue_role,
    step_cue_selection,
)
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.material_icons import DELETE_GLYPH
from cleave.viz.row_spec import (
    ChoiceJump,
    FieldMutator,
    FitStrategy,
    RowChoice,
    RowNavButton,
    RowPresentStyle,
    RowSpec,
)
from cleave.viz.row_specs.common import lock_text, on_off_text
from cleave.viz.tuning_view_state import TuningViewState

from cleave.config_schema.timeline import TIMELINE_PLACEMENT_SNAP_OPTIONS
from cleave.viz.row_specs.common import bool_choice, options_choice
if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls
    from cleave.viz.session import TuningSession

T = TypeVar("T")

def _format_timeline_bar_phase(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"+{state.timeline.bar_phase_offset}"

def _apply_timeline_bar_phase(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    controls.timeline_phase.nudge(forward=forward)

def _format_timeline_bar_grid(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return _bar_grid_display(state.timeline.show_bar_grid)

def _bar_grid_display(show: bool) -> str:
    return "show" if show else "hide"

def _apply_timeline_bar_grid(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    controls.session.timeline.show_bar_grid = forward

def _format_timeline_placement_snap(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.timeline.placement_snap

def _apply_timeline_placement_snap(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    tl = controls.session.timeline
    tl.placement_snap = step_timeline_placement_snap(
        tl.placement_snap,
        forward=forward,
    )

def _format_timeline_hard_cut_fades_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return hard_cut_enabled_display(state.timeline.hard_cut_fades.enabled)

def _apply_timeline_hard_cut_fades_enabled(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    controls.session.timeline.hard_cut_fades.enabled = forward

def _format_timeline_hard_cut_fade_in(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.timeline.hard_cut_fades.fade_in:.1f}s"

def _apply_timeline_hard_cut_fade_in(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    group = controls.session.timeline.hard_cut_fades
    delta = TIMELINE_FADE_DURATION_STEP if forward else -TIMELINE_FADE_DURATION_STEP
    group.fade_in = clamp_timeline_fade_duration(round(group.fade_in + delta, 1))

def _format_timeline_hard_cut_fade_out(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.timeline.hard_cut_fades.fade_out:.1f}s"

def _apply_timeline_hard_cut_fade_out(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    group = controls.session.timeline.hard_cut_fades
    delta = TIMELINE_FADE_DURATION_STEP if forward else -TIMELINE_FADE_DURATION_STEP
    group.fade_out = clamp_timeline_fade_duration(round(group.fade_out + delta, 1))

def _format_timeline_soft_cut_fades_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return hard_cut_enabled_display(state.timeline.soft_cut_fades.enabled)

def _apply_timeline_soft_cut_fades_enabled(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    controls.session.timeline.soft_cut_fades.enabled = forward

def _format_timeline_soft_cut_fade_in(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.timeline.soft_cut_fades.fade_in:.1f}s"

def _apply_timeline_soft_cut_fade_in(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    group = controls.session.timeline.soft_cut_fades
    delta = TIMELINE_FADE_DURATION_STEP if forward else -TIMELINE_FADE_DURATION_STEP
    group.fade_in = clamp_timeline_fade_duration(round(group.fade_in + delta, 1))

def _format_timeline_soft_cut_fade_out(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.timeline.soft_cut_fades.fade_out:.1f}s"

def _apply_timeline_soft_cut_fade_out(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    group = controls.session.timeline.soft_cut_fades
    delta = TIMELINE_FADE_DURATION_STEP if forward else -TIMELINE_FADE_DURATION_STEP
    group.fade_out = clamp_timeline_fade_duration(round(group.fade_out + delta, 1))

def _format_timeline_hard_cut_crossfade(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return timeline_crossfade_display(state.timeline.hard_cut_fades.crossfade)

def _apply_timeline_hard_cut_crossfade(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    group = controls.session.timeline.hard_cut_fades
    group.crossfade = forward

def _format_timeline_soft_cut_crossfade(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return timeline_crossfade_display(state.timeline.soft_cut_fades.crossfade)

def _apply_timeline_soft_cut_crossfade(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    group = controls.session.timeline.soft_cut_fades
    group.crossfade = forward

def _toggle_timeline_enabled(
    controls: TuningControls, _desc: RowDescriptor
) -> None:
    if controls.session.timeline.locked:
        return
    enabled = controls.session.timeline.enabled
    controls.set_timeline_enabled(not enabled)


def _format_song_markers_count(state: TuningViewState, _desc: RowDescriptor) -> str:
    return f"({len(state.timeline.song_marker_times)})"

def _song_marker_type_display(marker_type: str) -> str:
    if marker_type == DEFAULT_SONG_MARKER_TYPE:
        return "-"
    return marker_type

def _song_marker_type(state: TuningViewState, desc: RowDescriptor) -> str:
    assert desc.marker_index is not None
    types = state.timeline.song_marker_types
    index = desc.marker_index
    return types[index] if 0 <= index < len(types) else DEFAULT_SONG_MARKER_TYPE

def _format_song_marker_time(state: TuningViewState, desc: RowDescriptor) -> str:
    assert desc.marker_index is not None
    return format_marker_time(state.timeline.song_marker_times[desc.marker_index])

def _format_song_marker_type(state: TuningViewState, desc: RowDescriptor) -> str:
    return _song_marker_type_display(_song_marker_type(state, desc))

def _set_song_marker_type(
    controls: TuningControls,
    desc: RowDescriptor,
    step: Callable[[SongMarkerType], SongMarkerType],
) -> None:
    assert desc.marker_index is not None
    markers = controls.session.song_markers
    index = desc.marker_index
    if index < 0 or index >= len(markers.markers):
        return
    current = markers.markers[index]
    next_type = step(parse_song_marker_type(current.marker_type))
    if next_type == current.marker_type:
        return
    markers.markers[index] = SongMarker(current.time, next_type)
    warning = song_marker_gesture_warning(markers.markers, index)
    if warning is not None:
        controls.show_notification(warning)

def _apply_song_marker_type(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    _set_song_marker_type(
        controls,
        desc,
        lambda current: step_song_marker_type(current, forward=forward),
    )

def _jump_song_marker_type(
    controls: TuningControls, desc: RowDescriptor, delta: int
) -> None:
    _set_song_marker_type(
        controls,
        desc,
        lambda current: step_choice(SONG_MARKER_TYPES, current, delta),
    )

def _visibility_timeline(
    state: TuningViewState, _desc: RowDescriptor
) -> tuple[bool, bool]:
    return (state.timeline.enabled, False)


def _section_lock_blocks(controls: TuningControls, desc: RowDescriptor) -> bool:
    from cleave.viz.row_spec import section_lock_blocks_mutation

    return section_lock_blocks_mutation(controls.session, desc)


def _apply_timeline_generate(controls: TuningControls, _desc: RowDescriptor) -> None:
    command_by_id("timeline.generate").run(controls)


def _apply_timeline_set_cut_type(
    controls: TuningControls, _desc: RowDescriptor
) -> None:
    command_by_id("timeline.set_cut_type").run(controls)


def _apply_timeline_reset(controls: TuningControls, _desc: RowDescriptor) -> None:
    command_by_id("timeline.reset").run(controls)


def _apply_timeline_snap_cues(controls: TuningControls, _desc: RowDescriptor) -> None:
    command_by_id("timeline.snap_cues").run(controls)


def _always_available(_state: TuningViewState, _desc: RowDescriptor) -> bool:
    return True


def _delete_song_marker(controls: TuningControls, desc: RowDescriptor) -> None:
    if desc.marker_index is not None:
        controls.song_markers.prompt_delete(desc.marker_index)


def _apply_song_marker_item(controls: TuningControls, desc: RowDescriptor) -> None:
    if _section_lock_blocks(controls, desc):
        return
    controls.seek_song_marker(desc)


def _format_timeline_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return on_off_text(state.timeline.enabled)


def _format_timeline_locked(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return lock_text(state.timeline.locked)


def _apply_timeline_enabled(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    controls.set_timeline_enabled(forward)


def _apply_timeline_locked(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    if controls.session.timeline.locked != forward:
        controls.toggle_timeline_locked()


def _selected_cue(state: TuningViewState, desc: RowDescriptor) -> SlotCue | None:
    if desc.slot is None:
        return None
    return state.timeline.selected_cues.get(desc.slot)


def _selected_on_cue(state: TuningViewState, desc: RowDescriptor) -> SlotCue | None:
    cue = _selected_cue(state, desc)
    if cue is None or not cue_editable_for_blend_role(cue):
        return None
    return cue


def _cue_edits_available(state: TuningViewState, _desc: RowDescriptor) -> bool:
    # Cue rows only show for a selected cue that has the field; recording
    # pauses cue selection and edits.
    return not state.timeline_recording


def _format_cue_heading(state: TuningViewState, desc: RowDescriptor) -> str:
    """Start cues turn the layer on and carry its look; end cues turn it off."""
    cue = _selected_cue(state, desc)
    if cue is None:
        return "no cue selected"
    return "start cue" if cue_editable_for_blend_role(cue) else "end cue"


def _format_cue_time(state: TuningViewState, desc: RowDescriptor) -> str:
    cue = _selected_cue(state, desc)
    return "none" if cue is None else format_mmss(cue.t)


def _apply_cue_time(
    controls: TuningControls, desc: RowDescriptor, forward: bool, _large: bool
) -> None:
    """Left/Right select the previous or next cue on the row."""
    assert desc.slot is not None
    step_cue_selection(
        controls.session,
        desc.slot,
        forward=forward,
        playhead_sec=current_sec(controls.playback, controls.duration_sec),
    )


def _seek_to_cue(controls: TuningControls, desc: RowDescriptor) -> None:
    assert desc.slot is not None
    cue = selected_cue(controls.session, desc.slot)
    if cue is not None and cue_selection_allowed(controls.session):
        controls.seek_to(cue.t)


def _format_cue_opacity(state: TuningViewState, desc: RowDescriptor) -> str:
    cue = _selected_on_cue(state, desc)
    if cue is None:
        return "-"
    return f"{int(round(float(cue.level) * 100.0))}%"


def _apply_cue_opacity(
    controls: TuningControls, desc: RowDescriptor, forward: bool, large: bool
) -> None:
    assert desc.slot is not None
    nudge_cue_level(controls.session, desc.slot, forward=forward, large=large)


def _cut_value(cue: SlotCue | None) -> CutType:
    return cue.cut if cue is not None and cue.cut in CUT_TYPES else "none"


_BLEND_OPTIONS: tuple[BlendMode | None, ...] = (None, *BLEND_MODES)
_ROLE_OPTIONS: tuple[CueRole | None, ...] = (None, *CUE_ROLES)


def _blend_display(blend: BlendMode | None) -> str:
    # No cue blend holds the layer's own blend mode.
    return "layer" if blend is None else blend


def _role_display(role: CueRole | None) -> str:
    return "none" if role is None else role


def _cue_cut_value(state: TuningViewState, desc: RowDescriptor) -> CutType:
    return _cut_value(_selected_cue(state, desc))


def _cue_blend_value(state: TuningViewState, desc: RowDescriptor) -> BlendMode | None:
    cue = _selected_on_cue(state, desc)
    return None if cue is None else cue.blend


def _cue_role_value(state: TuningViewState, desc: RowDescriptor) -> CueRole | None:
    cue = _selected_on_cue(state, desc)
    return None if cue is None else cue.role


def _format_cue_cut(state: TuningViewState, desc: RowDescriptor) -> str:
    return "-" if _selected_cue(state, desc) is None else _cue_cut_value(state, desc)


def _format_cue_blend(state: TuningViewState, desc: RowDescriptor) -> str:
    if _selected_on_cue(state, desc) is None:
        return "-"
    return _blend_display(_cue_blend_value(state, desc))


def _format_cue_role(state: TuningViewState, desc: RowDescriptor) -> str:
    if _selected_on_cue(state, desc) is None:
        return "-"
    return _role_display(_cue_role_value(state, desc))


def _cue_option_rows(
    options: Sequence[T],
    value: Callable[[SlotCue | None], T],
    write: Callable[[TuningSession, str, T], None],
) -> tuple[FieldMutator, ChoiceJump]:
    """Left/Right and a list pick for one cue field, clamped at the ends."""

    def move(controls: TuningControls, desc: RowDescriptor, delta: int) -> None:
        assert desc.slot is not None
        cue = selected_cue(controls.session, desc.slot)
        if cue is None:
            return
        index = choice_index(options, value(cue)) + delta
        write(
            controls.session,
            desc.slot,
            options[max(0, min(len(options) - 1, index))],
        )

    def horizontal(
        controls: TuningControls, desc: RowDescriptor, forward: bool, _large: bool
    ) -> None:
        move(controls, desc, 1 if forward else -1)

    return horizontal, move


_apply_cue_cut, _jump_cue_cut = _cue_option_rows(CUT_TYPES, _cut_value, set_cue_cut)
_apply_cue_blend, _jump_cue_blend = _cue_option_rows(
    _BLEND_OPTIONS,
    lambda cue: None if cue is None else cue.blend,
    set_cue_blend,
)
_apply_cue_role, _jump_cue_role = _cue_option_rows(
    _ROLE_OPTIONS,
    lambda cue: None if cue is None else cue.role,
    set_cue_role,
)


def _cue_spec(
    label: str,
    format_value: Callable[[TuningViewState, RowDescriptor], str],
    apply_horizontal: FieldMutator,
    available: Callable[[TuningViewState, RowDescriptor], bool],
    *,
    help_title: str,
    help_entries: tuple[tuple[str, str], ...],
    help_description: tuple[str, ...],
    choice: RowChoice | None = None,
    apply_action: Callable[[TuningControls, RowDescriptor], None] | None = None,
    repeatable: bool = False,
    blocked_by_section_lock: bool = True,
) -> RowSpec:
    """One field of the selected strip cue. Edits match the strip's cue keys."""
    return RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label=label,
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=format_value,
        apply_horizontal=apply_horizontal,
        apply_action=apply_action,
        choice=choice,
        available=available,
        repeatable=repeatable,
        help_title=help_title,
        help_entries=help_entries,
        help_description=help_description,
        blocked_by_section_lock=blocked_by_section_lock,
    )


SPECS: dict[RowKind, RowSpec] = {
    RowKind.TIMELINE_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="Timeline",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_timeline,
        help_title="Timeline",
        help_description=(
            "Shows and hides the layers at set times in the song.",
            "When it is on, the layer on/off switches do not apply.",
        ),
        toggle_enabled=_toggle_timeline_enabled,
    ),
    RowKind.TIMELINE_ENABLED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="enabled",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_enabled,
        apply_horizontal=_apply_timeline_enabled,
        choice=bool_choice(lambda s, _d: s.timeline.enabled),
        help_title="Timeline Enabled",
        help_description=(
            "When on, the timeline shows and hides the layers, and the timeline strip opens.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_LOCKED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="lock",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_locked,
        apply_horizontal=_apply_timeline_locked,
        choice=bool_choice(lambda s, _d: s.timeline.locked, lock_text),
        help_title="Timeline Lock",
        help_description=("When locked, you cannot change the timeline settings.",),
        blocked_by_section_lock=False,
    ),
    RowKind.TIMELINE_GENERATE: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Generate timeline...",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_timeline_generate,
        fit_strategy=FitStrategy.NONE,
        help_title="Generate Timeline",
        help_entries=(("Enter", "open generate dialog"),),
        help_description=(
            "Makes a new timeline from the settings in a dialog.",
            "This replaces the current cues.",
            "Each crescendo song marker gets a crescendo.",
            "The project keeps the dialog settings.",
        ),
        help_mode_entries=TIMELINE_PRESET_HELP_ENTRIES,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_SET_CUT_TYPE: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Set cut type...",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_timeline_set_cut_type,
        fit_strategy=FitStrategy.NONE,
        help_title="Set Cut Type",
        help_entries=(("Enter", "open set cut type dialog"),),
        help_description=(
            "Sets the cut type of many cues at once.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_RESET: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Reset timeline...",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_timeline_reset,
        fit_strategy=FitStrategy.NONE,
        help_title="Reset Timeline",
        help_entries=(("Enter", "open reset dialog"),),
        help_description=(
            "Removes all cues.",
            "Every layer then stays on, or stays off, for the whole song.",
        ),
        help_mode_entries=TIMELINE_RESET_HELP_ENTRIES,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_BEAT_BAR_GRID_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="beat / bar grid",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Beat / Bar Grid",
        help_description=(
            "Beats and bars that Beat This! finds in the song.",
        ),
    ),
    RowKind.TIMELINE_BAR_PHASE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="bar phase",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_bar_phase,
        apply_horizontal=_apply_timeline_bar_phase,
        help_title="Bar Phase",
        help_entries=(
            ("Left/Right", "move grid and cues -1 / +1 beat"),
        ),
        help_description=(
            "Moves the bar grid and all cues by one beat.",
            "After you change it, snap the cues to the song markers again."
        ),
        repeatable=True,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_BAR_GRID: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="bar grid",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_bar_grid,
        apply_horizontal=_apply_timeline_bar_grid,
        choice=bool_choice(lambda s, _d: s.timeline.show_bar_grid, _bar_grid_display),
        help_title="Bar Grid",
        help_entries=(
            ("Left/Right", "hide / show"),
        ),
        help_description=(
            "Shows the detected bars on the timeline strip.",
            "A gap means that no beat was found there, for example with no drums.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_PLACEMENT_SNAP: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="placement snap",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_placement_snap,
        apply_horizontal=_apply_timeline_placement_snap,
        choice=options_choice(TIMELINE_PLACEMENT_SNAP_OPTIONS, lambda s, _d: s.timeline.placement_snap),
        help_title="Placement Snap",
        help_entries=(("Left/Right", "choose off / beat / bar"),),
        help_description=(
            "Moves new song markers and cues to the nearest beat or bar.",
            "Set it to off if the beat detection is wrong.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_SNAP_CUES: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Snap cues...",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_timeline_snap_cues,
        fit_strategy=FitStrategy.NONE,
        help_title="Snap Cues",
        help_entries=(("Enter", "open snap dialog"),),
        help_description=(
            "Moves cues to the nearest beat or bar, or onto nearby song markers.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_CUTS_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="cue fades",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Cue Fades",
        help_description=(
            "Fade times at the cues, for each cut type.",
        ),
    ),
    RowKind.TIMELINE_HARD_CUTS: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="hard cuts",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_hard_cut_fades_enabled,
        apply_horizontal=_apply_timeline_hard_cut_fades_enabled,
        choice=bool_choice(lambda s, _d: s.timeline.hard_cut_fades.enabled, hard_cut_enabled_display),
        help_title="Hard Cuts",
        help_entries=(("Left/Right", "enabled / disabled"),),
        help_description=(
            "When on, the layer fades at cues with a hard cut.",
        ),
        repeatable=True,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_HARD_CUT_FADE_IN: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="fade in duration",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_hard_cut_fade_in,
        apply_horizontal=_apply_timeline_hard_cut_fade_in,
        help_title="Hard Cut Fade In",
        help_entries=(
            ("Left/Right", "decrease / increase"),
        ),
        help_description=(
            "The fade-in starts this many seconds before a hard-cut cue.",
        ),
        repeatable=True,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_HARD_CUT_FADE_OUT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="fade out duration",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_hard_cut_fade_out,
        apply_horizontal=_apply_timeline_hard_cut_fade_out,
        help_title="Hard Cut Fade Out",
        help_entries=(
            ("Left/Right", "decrease / increase"),
        ),
        help_description=(
            "The fade-out starts this many seconds after a hard-cut cue.",
        ),
        repeatable=True,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_HARD_CUT_CROSSFADE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="shift for crossfade",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_hard_cut_crossfade,
        apply_horizontal=_apply_timeline_hard_cut_crossfade,
        choice=bool_choice(lambda s, _d: s.timeline.hard_cut_fades.crossfade, timeline_crossfade_display),
        help_title="Hard Cut Shift For Crossfade",
        help_entries=(("Left/Right", "off / on"),),
        help_description=(
            "Puts the middle of each fade on the cue, not its start or end.",
            "This gives a crossfade between the layers.",
        ),
        repeatable=True,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_SOFT_CUTS: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="soft cuts",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_soft_cut_fades_enabled,
        apply_horizontal=_apply_timeline_soft_cut_fades_enabled,
        choice=bool_choice(lambda s, _d: s.timeline.soft_cut_fades.enabled, hard_cut_enabled_display),
        help_title="Soft Cuts",
        help_entries=(("Left/Right", "enabled / disabled"),),
        help_description=(
            "When on, the layer fades at cues with a soft cut.",
        ),
        repeatable=True,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_SOFT_CUT_FADE_IN: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="fade in duration",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_soft_cut_fade_in,
        apply_horizontal=_apply_timeline_soft_cut_fade_in,
        help_title="Soft Cut Fade In",
        help_entries=(
            ("Left/Right", "decrease / increase"),
        ),
        help_description=(
            "The fade-in starts this many seconds before a soft-cut cue.",
        ),
        repeatable=True,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_SOFT_CUT_FADE_OUT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="fade out duration",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_soft_cut_fade_out,
        apply_horizontal=_apply_timeline_soft_cut_fade_out,
        help_title="Soft Cut Fade Out",
        help_entries=(
            ("Left/Right", "decrease / increase"),
        ),
        help_description=(
            "The fade-out starts this many seconds after a soft-cut cue.",
        ),
        repeatable=True,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_SOFT_CUT_CROSSFADE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="shift for crossfade",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_soft_cut_crossfade,
        apply_horizontal=_apply_timeline_soft_cut_crossfade,
        choice=bool_choice(lambda s, _d: s.timeline.soft_cut_fades.crossfade, timeline_crossfade_display),
        help_title="Soft Cut Shift For Crossfade",
        help_entries=(("Left/Right", "off / on"),),
        help_description=(
            "Puts the middle of each fade on the cue, not its start or end.",
            "This gives a crossfade between the layers.",
        ),
        repeatable=True,
        blocked_by_section_lock=True,
    ),
    RowKind.SONG_MARKERS_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="song markers",
        present_style=RowPresentStyle.HEADING,
        format_value=_format_song_markers_count,
        fit_strategy=FitStrategy.NONE,
        help_title="Song Markers",
        help_description=(
            "Markers that you put at the main changes in the song.",
            "Press Ctrl+Enter to add a marker at the playhead.",
        ),
    ),
    RowKind.SONG_MARKER_ITEM: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="",
        present_style=RowPresentStyle.LIST_ITEM,
        format_label=_format_song_marker_time,
        format_value=_format_song_marker_type,
        nav_buttons=(
            RowNavButton(DELETE_GLYPH, _always_available, _delete_song_marker),
        ),
        apply_horizontal=_apply_song_marker_type,
        apply_action=_apply_song_marker_item,
        choice=options_choice(
            SONG_MARKER_TYPES,
            _song_marker_type,
            _song_marker_type_display,
            jump=_jump_song_marker_type,
        ),
        fit_strategy=FitStrategy.NONE,
        help_title="Song Marker",
        help_entries=(
            ("Enter", "seek to marker"),
            ("Left/Right", "choose marker type"),
            ("Delete", "remove marker"),
        ),
        help_description=(
            "The time and type of a song marker.",
            "Generate Timeline makes a crescendo at each crescendo marker.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_CUE_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="selected cue",
        present_style=RowPresentStyle.HEADING,
        format_label=_format_cue_heading,
        fit_strategy=FitStrategy.NONE,
        navigable=False,
    ),
    RowKind.TIMELINE_CUE_TIME: _cue_spec(
        "time",
        _format_cue_time,
        _apply_cue_time,
        _cue_edits_available,
        apply_action=_seek_to_cue,
        # Selecting and seeking stay open on a locked timeline, as on the strip.
        blocked_by_section_lock=False,
        help_title="Selected Cue",
        help_entries=(
            ("Left/Right", "select previous / next cue"),
            ("Enter", "seek to cue"),
        ),
        help_description=(
            "Time of the selected cue on this row.",
            "A start cue turns the layer on.",
            "An end cue turns it off.",
        ),
    ),
    RowKind.TIMELINE_CUE_OPACITY: _cue_spec(
        "opacity",
        _format_cue_opacity,
        _apply_cue_opacity,
        _cue_edits_available,
        repeatable=True,
        help_title="Cue Opacity",
        help_entries=(
            ("Left/Right", "1% step"),
            ("PgUp/PgDn", "10% step"),
        ),
        help_description=(
            "Layer opacity from this cue on.",
            "It multiplies the opacity of the layer.",
            "Start cues only.",
        ),
    ),
    RowKind.TIMELINE_CUE_CUT: _cue_spec(
        "cut",
        _format_cue_cut,
        _apply_cue_cut,
        _cue_edits_available,
        choice=options_choice(
            CUT_TYPES,
            _cue_cut_value,
            jump=_jump_cue_cut,
        ),
        help_title="Cue Cut",
        help_entries=(("Left/Right", "choose none / hard / soft"),),
        help_description=(
            "How the layer fades at this cue.",
            "Set the fade times in Timeline > Cue Fades.",
        ),
    ),
    RowKind.TIMELINE_CUE_BLEND: _cue_spec(
        "blend",
        _format_cue_blend,
        _apply_cue_blend,
        _cue_edits_available,
        choice=options_choice(
            _BLEND_OPTIONS,
            _cue_blend_value,
            _blend_display,
            jump=_jump_cue_blend,
        ),
        help_title="Cue Blend",
        help_entries=(("Left/Right", "choose blend mode"),),
        help_description=(
            "Blend mode from this cue on.",
            "The Layer option uses the blend mode of the layer.",
            "Start cues only.",
        ),
    ),
    RowKind.TIMELINE_CUE_ROLE: _cue_spec(
        "role",
        _format_cue_role,
        _apply_cue_role,
        _cue_edits_available,
        choice=options_choice(
            _ROLE_OPTIONS,
            _cue_role_value,
            _role_display,
            jump=_jump_cue_role,
        ),
        help_title="Cue Role",
        help_entries=(("Left/Right", "choose role"),),
        help_description=(
            "The role of the layer from this cue on.",
            "The visual limiter uses the role.",
            "Start cues only.",
        ),
    ),
}
