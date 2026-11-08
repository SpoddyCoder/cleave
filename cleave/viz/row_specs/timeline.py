"""Timeline and song-marker row specs for the live tuning overlay."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

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
from cleave.viz.commands import command_by_id
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.material_icons import DELETE_GLYPH
from cleave.viz.row_spec import FitStrategy, RowNavButton, RowPresentStyle, RowSpec
from cleave.viz.row_specs.common import lock_text, on_off_text
from cleave.viz.tuning_view_state import TuningViewState

from cleave.config_schema.timeline import TIMELINE_PLACEMENT_SNAP_OPTIONS
from cleave.viz.row_specs.common import bool_choice, options_choice
if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

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


SPECS: dict[RowKind, RowSpec] = {
    RowKind.TIMELINE_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="Timeline",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_timeline,
        help_title="Timeline",
        help_description=(
            "Layer visibility automation.",
            "When enabled, standard layer visibility is disabled.",
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
        help_title="Timeline enabled",
        help_description=(
            "When on, the timeline drives layer visibility and its strip opens.",
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
        help_title="Timeline lock",
        help_description=("Locked timeline settings cannot be edited.",),
        blocked_by_section_lock=False,
    ),
    RowKind.TIMELINE_GENERATE: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Generate timeline...",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_timeline_generate,
        fit_strategy=FitStrategy.NONE,
        help_title="Generate timeline",
        help_entries=(("Enter", "open generate dialog"),),
        help_description=(
            "Build a new timeline from character, density, snaps, cuts,",
            "re-populate, conductor, and mode. Replaces the current cues.",
            "Crescendo song markers build crescendos.",
            "The dialog remembers its values in the project.",
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
        help_title="Set cut type",
        help_entries=(("Enter", "open set cut type dialog"),),
        help_description=(
            "Set hard, soft, or no cut on all cues, on song marker cues,",
            "or on all cues except song markers.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_RESET: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Reset timeline...",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_timeline_reset,
        fit_strategy=FitStrategy.NONE,
        help_title="Reset timeline",
        help_entries=(("Enter", "open reset dialog"),),
        help_description=(
            "Clear all timeline cues and set every layer",
            "on or off for the whole track.",
        ),
        help_mode_entries=TIMELINE_RESET_HELP_ENTRIES,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_BEAT_BAR_GRID_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="beat / bar grid",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Beat / bar grid",
        help_description=(
            "AI beat detection powered by Beat This!",
        ),
    ),
    RowKind.TIMELINE_BAR_PHASE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="bar phase",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_bar_phase,
        apply_horizontal=_apply_timeline_bar_phase,
        help_title="Bar phase",
        help_entries=(
            ("Left", "shift cues -1 beat"),
            ("Right", "shift cues +1 beat"),
        ),
        help_description=(
            "Nudge all timeline cues by one beat.",
            "Tip: re-apply snap to song markers after adjusting this."
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
        help_title="Bar grid",
        help_entries=(
            ("Left", "hide detected bar lines"),
            ("Right", "show detected bar lines"),
        ),
        help_description=(
            "Show Beat This! bar detection points on the timeline strip.",
            "Gaps mean missing detection (no rhythm/drums).",
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
        help_title="Placement snap",
        help_entries=(("Left/Right", "choose off / beat / bar"),),
        help_description=(
            "Applies when placing song markers and timeline cues",
            "Snap to the nearest beat or bar.",
            "Switch off when the beat detection is not accurate.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_SNAP_CUES: RowSpec(
        affordance=RowAffordance.COMMAND,
        panel_label="Snap cues...",
        present_style=RowPresentStyle.FULL_LINE,
        apply_action=_apply_timeline_snap_cues,
        fit_strategy=FitStrategy.NONE,
        help_title="Snap cues",
        help_entries=(("Enter", "open snap dialog"),),
        help_description=(
            "Snap timeline cues to the nearest beat or bar,",
            "or pull cues within proximity onto song markers.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_CUTS_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="cue fades",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Cue fades",
        help_description=(
            "Opacity fade in and out for timeline cue edges by cut type.",
        ),
    ),
    RowKind.TIMELINE_HARD_CUTS: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="hard cuts",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_hard_cut_fades_enabled,
        apply_horizontal=_apply_timeline_hard_cut_fades_enabled,
        choice=bool_choice(lambda s, _d: s.timeline.hard_cut_fades.enabled, hard_cut_enabled_display),
        help_title="Hard cuts",
        help_entries=(("Left/Right", "enabled / disabled"),),
        help_description=(
            "Fade edges on cues with cut set to hard.",
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
        help_title="Hard cut fade in",
        help_entries=(
            ("Left", "decrease fade in"),
            ("Right", "increase fade in"),
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
        help_title="Hard cut fade out",
        help_entries=(
            ("Left", "decrease fade out"),
            ("Right", "increase fade out"),
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
        help_title="Hard cut shift for crossfade",
        help_entries=(("Left/Right", "off / on"),),
        help_description=(
            "Center hard-cut fade ramps on the cue time instead of aligning to an edge.",
            "Produces a crossfade effect between layers.",
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
        help_title="Soft cuts",
        help_entries=(("Left/Right", "enabled / disabled"),),
        help_description=(
            "Fade edges on cues with cut set to soft.",
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
        help_title="Soft cut fade in",
        help_entries=(
            ("Left", "decrease fade in"),
            ("Right", "increase fade in"),
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
        help_title="Soft cut fade out",
        help_entries=(
            ("Left", "decrease fade out"),
            ("Right", "increase fade out"),
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
        help_title="Soft cut shift for crossfade",
        help_entries=(("Left/Right", "off / on"),),
        help_description=(
            "Center soft-cut fade ramps on the cue time instead of aligning to an edge.",
            "Produces a crossfade effect between layers.",
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
        help_title="Song markers",
        help_description=(
            "Manual song markers for major transitions.",
            "Ctrl+Enter drops a marker at the playhead.",
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
        help_title="Song marker",
        help_entries=(
            ("Enter", "seek to marker"),
            ("Left / Right", "choose marker type"),
            ("Delete", "confirm remove"),
        ),
        help_description=(
            "A song marker time and type. Crescendo markers build",
            "crescendos on timeline preset apply. Enter or a click seeks;",
            "Left/Right or the list chooses type; the bin deletes.",
        ),
        blocked_by_section_lock=True,
    ),
}
