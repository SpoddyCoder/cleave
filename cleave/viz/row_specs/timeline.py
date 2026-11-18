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
    SongMarkerType,
    step_song_marker_type,
    format_marker_time,
    parse_song_marker_type,
)
from cleave.timeline_presets import (
    TIMELINE_PRESET_HELP_ENTRIES,
    TIMELINE_RESET_HELP_ENTRIES,
)
from cleave.blend_modes import BLEND_MODE_HELP_ENTRIES, BLEND_MODES, BlendMode
from cleave.choice import choice_index
from cleave.cue_roles import CUE_ROLE_HELP_BLURB, CUE_ROLES, CueRole
from cleave.cut_types import CUT_TYPES, CutType
from cleave.timeline import ClipEdge, TimelineClip
from cleave.viz.commands import command_by_id
from cleave.viz.playback import format_mmss
from cleave.viz.timeline_clip_edits import ClipEditor
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
    markers = controls.session.song_markers.markers
    index = desc.marker_index
    if index < 0 or index >= len(markers):
        return
    current = parse_song_marker_type(markers[index].marker_type)
    controls.song_markers.set_type(index, step(current))

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


def _selected_clip(state: TuningViewState, desc: RowDescriptor) -> TimelineClip | None:
    if desc.slot is None:
        return None
    return state.timeline.selected_clips.get(desc.slot)


def _clip_edits_available(state: TuningViewState, _desc: RowDescriptor) -> bool:
    # Clip rows only show for a selected clip; recording pauses clip
    # selection and edits.
    return not state.timeline_recording


def _clip_cut_out_available(state: TuningViewState, desc: RowDescriptor) -> bool:
    """Cut out needs an end cue of the clip's own: a gap after it."""
    clip = _selected_clip(state, desc)
    return (
        clip is not None and clip.has_end_cue and _clip_edits_available(state, desc)
    )


def _format_clip_heading(state: TuningViewState, desc: RowDescriptor) -> str:
    clip = _selected_clip(state, desc)
    if clip is None:
        return "no clip selected"
    return f"clip {format_mmss(clip.start)}-{format_mmss(clip.end)}"


def _format_clip_start(state: TuningViewState, desc: RowDescriptor) -> str:
    clip = _selected_clip(state, desc)
    return "-" if clip is None else format_marker_time(clip.start)


def _format_clip_end(state: TuningViewState, desc: RowDescriptor) -> str:
    clip = _selected_clip(state, desc)
    return "-" if clip is None else format_marker_time(clip.end)


def _clip_trim_row(edge: ClipEdge) -> FieldMutator:
    """Left/Right move one edge by a snap step; the large step is one bar."""

    def horizontal(
        controls: TuningControls, desc: RowDescriptor, forward: bool, large: bool
    ) -> None:
        assert desc.slot is not None
        controls.clip_editor.trim_step(desc.slot, edge, forward=forward, large=large)

    return horizontal


def _format_clip_opacity(state: TuningViewState, desc: RowDescriptor) -> str:
    clip = _selected_clip(state, desc)
    if clip is None:
        return "-"
    return f"{int(round(float(clip.level) * 100.0))}%"


def _apply_clip_opacity(
    controls: TuningControls, desc: RowDescriptor, forward: bool, large: bool
) -> None:
    assert desc.slot is not None
    controls.clip_editor.nudge_level(desc.slot, forward=forward, large=large)


def _cut_value(cut: CutType | None) -> CutType:
    return cut if cut in CUT_TYPES else "none"


_BLEND_OPTIONS: tuple[BlendMode | None, ...] = (None, *BLEND_MODES)
_ROLE_OPTIONS: tuple[CueRole | None, ...] = (None, *CUE_ROLES)


def _blend_display(blend: BlendMode | None) -> str:
    # No clip blend holds the layer's own blend mode.
    return "layer" if blend is None else blend


def _role_display(role: CueRole | None) -> str:
    return "none" if role is None else role


def _clip_cut_in(clip: TimelineClip | None) -> CutType:
    return _cut_value(None if clip is None else clip.cut_in)


def _clip_cut_out(clip: TimelineClip | None) -> CutType:
    return _cut_value(None if clip is None else clip.cut_out)


def _clip_blend(clip: TimelineClip | None) -> BlendMode | None:
    return None if clip is None else clip.blend


def _clip_role(clip: TimelineClip | None) -> CueRole | None:
    return None if clip is None else clip.role


def _clip_field(
    read: Callable[[TimelineClip | None], T],
) -> Callable[[TuningViewState, RowDescriptor], T]:
    def value(state: TuningViewState, desc: RowDescriptor) -> T:
        return read(_selected_clip(state, desc))

    return value


def _clip_field_text(
    read: Callable[[TimelineClip | None], T],
    display: Callable[[T], str] = str,
) -> Callable[[TuningViewState, RowDescriptor], str]:
    def text(state: TuningViewState, desc: RowDescriptor) -> str:
        clip = _selected_clip(state, desc)
        return "-" if clip is None else display(read(clip))

    return text


def _clip_option_rows(
    options: Sequence[T],
    read: Callable[[TimelineClip | None], T],
    write: Callable[[ClipEditor, str, T], None],
) -> tuple[FieldMutator, ChoiceJump]:
    """Left/Right and a list pick for one clip field, clamped at the ends."""

    def move(controls: TuningControls, desc: RowDescriptor, delta: int) -> None:
        assert desc.slot is not None
        clip = controls.clip_editor.selected(desc.slot)
        if clip is None:
            return
        index = choice_index(options, read(clip)) + delta
        write(
            controls.clip_editor,
            desc.slot,
            options[max(0, min(len(options) - 1, index))],
        )

    def horizontal(
        controls: TuningControls, desc: RowDescriptor, forward: bool, _large: bool
    ) -> None:
        move(controls, desc, 1 if forward else -1)

    return horizontal, move


# Lambdas keep the editor calls on its public methods.
_apply_clip_cut_in, _jump_clip_cut_in = _clip_option_rows(
    CUT_TYPES, _clip_cut_in, lambda editor, slot, cut: editor.set_cut_in(slot, cut)
)
_apply_clip_cut_out, _jump_clip_cut_out = _clip_option_rows(
    CUT_TYPES, _clip_cut_out, lambda editor, slot, cut: editor.set_cut_out(slot, cut)
)
_apply_clip_blend, _jump_clip_blend = _clip_option_rows(
    _BLEND_OPTIONS,
    _clip_blend,
    lambda editor, slot, blend: editor.set_blend(slot, blend),
)
_apply_clip_role, _jump_clip_role = _clip_option_rows(
    _ROLE_OPTIONS, _clip_role, lambda editor, slot, role: editor.set_role(slot, role)
)


def _clip_spec(
    label: str,
    format_value: Callable[[TuningViewState, RowDescriptor], str],
    apply_horizontal: FieldMutator,
    available: Callable[[TuningViewState, RowDescriptor], bool],
    *,
    help_title: str,
    help_entries: tuple[tuple[str, str], ...],
    help_description: tuple[str, ...],
    help_mode_entries: tuple[tuple[str, str], ...] | None = None,
    choice: RowChoice | None = None,
    apply_action: Callable[[TuningControls, RowDescriptor], None] | None = None,
    repeatable: bool = False,
    blocked_by_section_lock: bool = True,
) -> RowSpec:
    """One field of the selected strip clip. Edits match the strip's clip keys."""
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
        help_mode_entries=help_mode_entries,
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
            "Sequences the layers across the song with cues, so each one comes in and drops out at set times. While it is on, the layers' own on/off switches are ignored.",
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
            "Hands layer visibility to the timeline's cues and opens the timeline strip.",
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
        help_description=(
            "Protects the timeline from accidental edits.",
        ),
        blocked_by_section_lock=False,
    ),
    RowKind.TIMELINE_GENERATE: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Generate timeline…",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_timeline_generate,
        fit_strategy=FitStrategy.NONE,
        help_title="Generate Timeline",
        help_entries=(("Enter", "open generate dialog"),),
        help_description=(
            "Builds a complete timeline from the arrangement style you pick in a dialog, replacing the current cues. Crescendo song markers each get a crescendo, and the project remembers your choices for next time.",
        ),
        help_mode_entries=TIMELINE_PRESET_HELP_ENTRIES,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_SET_CUT_TYPE: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Set cut type on cues…",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_timeline_set_cut_type,
        fit_strategy=FitStrategy.NONE,
        help_title="Set Cut Type On Cues",
        help_entries=(("Enter", "open set cut type dialog"),),
        help_description=(
            "Sets the cut type on many cues in one go.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_RESET: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Reset timeline…",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_timeline_reset,
        fit_strategy=FitStrategy.NONE,
        help_title="Reset Timeline",
        help_entries=(("Enter", "open reset dialog"),),
        help_description=(
            "Clears every cue, leaving each layer either on or off for the whole song.",
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
            "The beat and bar grid detected by Beat This!, used to snap cues and song markers.",
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
            "Shifts the bar grid, and every cue with it, by one beat, to fix a downbeat detected in the wrong place. Re-snap cues to song markers afterwards.",
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
            "Draws the detected bars on the timeline strip. Gaps are stretches where no beat was found, such as a beatless intro.",
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
            "Snaps new song markers and cues to the nearest beat or bar. Turn it off if beat detection has gone wrong for this song.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_SNAP_CUES: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Snap cues…",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_timeline_snap_cues,
        fit_strategy=FitStrategy.NONE,
        help_title="Snap Cues",
        help_entries=(("Enter", "open snap dialog"),),
        help_description=(
            "Quantises existing cues to the beat or bar grid, or pulls them onto nearby song markers.",
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
            "Fade lengths at cues, set separately for hard and soft cuts.",
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
            "Applies a fade at hard-cut cues. Off makes them instant.",
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
            "How many seconds before a hard-cut cue the fade-in starts.",
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
            "How many seconds after a hard-cut cue the fade-out starts.",
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
            "Centres each fade on the cue rather than starting or ending it there, so outgoing and incoming layers crossfade.",
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
            "Applies a fade at soft-cut cues. Off makes them instant.",
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
            "How many seconds before a soft-cut cue the fade-in starts.",
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
            "How many seconds after a soft-cut cue the fade-out starts.",
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
            "Centres each fade on the cue rather than starting or ending it there, so outgoing and incoming layers crossfade.",
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
            "Markers for the song's structure, such as drops, breakdowns, and builds. Ctrl+Enter drops one at the playhead.",
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
            "A marker's time and type. Generate Timeline builds a crescendo at each crescendo marker.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_CLIP_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="selected clip",
        present_style=RowPresentStyle.HEADING,
        format_label=_format_clip_heading,
        fit_strategy=FitStrategy.NONE,
        navigable=False,
    ),
    RowKind.TIMELINE_CLIP_START: _clip_spec(
        "start",
        _format_clip_start,
        _clip_trim_row("start"),
        _clip_edits_available,
        repeatable=True,
        help_title="Clip Start",
        help_entries=(
            ("Left/Right", "trim by one snap step"),
            ("PgUp/PgDn", "trim by one bar"),
        ),
        help_description=(
            "Where the clip begins. It cannot pass the previous clip; where the two touch, moving it rolls the shared edit point. Steps follow Placement Snap.",
        ),
    ),
    RowKind.TIMELINE_CLIP_END: _clip_spec(
        "end",
        _format_clip_end,
        _clip_trim_row("end"),
        _clip_edits_available,
        repeatable=True,
        help_title="Clip End",
        help_entries=(
            ("Left/Right", "trim by one snap step"),
            ("PgUp/PgDn", "trim by one bar"),
        ),
        help_description=(
            "Where the clip ends. It cannot pass the next clip; where the two touch, moving it rolls the shared edit point. Steps follow Placement Snap.",
        ),
    ),
    RowKind.TIMELINE_CLIP_OPACITY: _clip_spec(
        "opacity",
        _format_clip_opacity,
        _apply_clip_opacity,
        _clip_edits_available,
        repeatable=True,
        help_title="Clip Opacity",
        help_entries=(
            ("Left/Right", "1% step"),
            ("PgUp/PgDn", "10% step"),
        ),
        help_description=(
            "Opacity for this clip, multiplied with the layer's own opacity. Pattern Mask overrides this while it is on.",
        ),
    ),
    RowKind.TIMELINE_CLIP_BLEND: _clip_spec(
        "blend",
        _clip_field_text(_clip_blend, _blend_display),
        _apply_clip_blend,
        _clip_edits_available,
        choice=options_choice(
            _BLEND_OPTIONS,
            _clip_field(_clip_blend),
            _blend_display,
            jump=_jump_clip_blend,
        ),
        help_title="Clip Blend",
        help_entries=(("Left/Right", "choose blend mode"),),
        help_description=(
            "Blend mode for this clip. Layer uses the layer's own blend mode. Pattern Mask overrides this while it is on.",
        ),
        help_mode_entries=(
            ("layer", "uses the blend mode of the layer."),
            *BLEND_MODE_HELP_ENTRIES,
        ),
    ),
    RowKind.TIMELINE_CLIP_ROLE: _clip_spec(
        "role",
        _clip_field_text(_clip_role, _role_display),
        _apply_clip_role,
        _clip_edits_available,
        choice=options_choice(
            _ROLE_OPTIONS,
            _clip_field(_clip_role),
            _role_display,
            jump=_jump_clip_role,
        ),
        help_title="Clip Role",
        help_entries=(("Left/Right", "choose role"),),
        help_description=(
            "The part this layer plays during the clip. The visual limiter uses it to decide which layers give way when the picture gets busy.",
        ),
        help_mode_entries=(
            ("none", "no role."),
            *((role, f"{CUE_ROLE_HELP_BLURB[role]}.") for role in CUE_ROLES),
        ),
    ),
    RowKind.TIMELINE_CLIP_CUT_IN: _clip_spec(
        "cut in",
        _clip_field_text(_clip_cut_in),
        _apply_clip_cut_in,
        _clip_edits_available,
        choice=options_choice(
            CUT_TYPES,
            _clip_field(_clip_cut_in),
            jump=_jump_clip_cut_in,
        ),
        help_title="Clip Cut In",
        help_entries=(("Left/Right", "choose none / hard / soft"),),
        help_description=(
            "The transition into this clip. Fade lengths are set in Timeline > Cue Fades.",
        ),
    ),
    RowKind.TIMELINE_CLIP_CUT_OUT: _clip_spec(
        "cut out",
        _clip_field_text(_clip_cut_out),
        _apply_clip_cut_out,
        _clip_cut_out_available,
        choice=options_choice(
            CUT_TYPES,
            _clip_field(_clip_cut_out),
            jump=_jump_clip_cut_out,
        ),
        help_title="Clip Cut Out",
        help_entries=(("Left/Right", "choose none / hard / soft"),),
        help_description=(
            "The transition out of this clip. Not available when the clip runs straight into the next one (use that clip's Cut in) or to the end of the song. Fade lengths are set in Timeline > Cue Fades.",
        ),
    ),
}
