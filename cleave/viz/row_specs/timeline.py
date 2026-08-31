"""Timeline and song-marker row specs for the live tuning overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.config_schema.timeline import (
    TIMELINE_FADE_DURATION_STEP,
    VISUAL_LIMITER_RATIO_STEP,
    VISUAL_LIMITER_RELEASE_STEP,
    VISUAL_LIMITER_THRESHOLD_STEP,
    clamp_timeline_fade_duration,
    clamp_visual_limiter_ratio,
    clamp_visual_limiter_release,
    clamp_visual_limiter_threshold,
    cycle_timeline_crossfade,
    cycle_timeline_placement_snap,
    timeline_crossfade_display,
)
from cleave.song_markers import (
    DEFAULT_SONG_MARKER_TYPE,
    SongMarker,
    cycle_song_marker_type,
    format_marker_time,
    parse_song_marker_type,
    song_marker_gesture_warning,
)
from cleave.timeline_presets import (
    TIMELINE_PRESET_HELP_ENTRIES,
    TIMELINE_RESET_HELP_ENTRIES,
)
from cleave.timeline_presets.characters import (
    cycle_timeline_preset_kind,
    timeline_preset_kind_display,
)
from cleave.timeline_presets.conductor import (
    cycle_timeline_preset_conductor,
    timeline_preset_conductor_display,
)
from cleave.timeline_presets.cue_snap import (
    cycle_timeline_preset_cue_snap,
    timeline_preset_cue_snap_display,
)
from cleave.timeline_presets.density import (
    cycle_timeline_preset_density,
    timeline_preset_density_display,
)
from cleave.timeline_presets.mode import (
    cycle_timeline_preset_mode,
    timeline_preset_mode_display,
)
from cleave.timeline_presets.repopulate import (
    cycle_timeline_preset_repopulate,
    timeline_preset_repopulate_display,
)
from cleave.timeline_presets.song_marker_snap import (
    cycle_timeline_preset_song_marker_snap,
    timeline_preset_song_marker_snap_display,
)
from cleave.timeline_presets.timeline_cuts import (
    cycle_timeline_preset_timeline_cuts,
    timeline_preset_timeline_cuts_display,
)
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_sections import apply_expand_toggle, apply_panel_anchor_toggle
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.row_specs.common import apply_expand_subheader
from cleave.viz.tuning_view_state import TuningViewState

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

def _format_timeline_bar_phase(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"+{state.render_timeline.bar_phase_offset}"

def _apply_timeline_bar_phase(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls.timeline_phase.nudge(forward=forward)

def _format_timeline_bar_grid(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return "show" if state.render_timeline.show_bar_grid else "hide"

def _apply_timeline_bar_grid(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls.session.timeline.show_bar_grid = forward

def _format_timeline_placement_snap(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.render_timeline.placement_snap

def _apply_timeline_placement_snap(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    tl = controls.session.timeline
    tl.placement_snap = cycle_timeline_placement_snap(
        tl.placement_snap,
        forward=forward,
    )

def _format_timeline_preset_character(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return timeline_preset_kind_display(state.render_timeline.timeline_preset_kind)

def _apply_timeline_preset_character(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    tl = controls.session.timeline
    tl.timeline_preset_kind = cycle_timeline_preset_kind(
        tl.timeline_preset_kind,
        forward=forward,
    )

def _format_timeline_preset_density(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return timeline_preset_density_display(
        state.render_timeline.timeline_preset_density
    )

def _apply_timeline_preset_density(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    tl = controls.session.timeline
    tl.timeline_preset_density = cycle_timeline_preset_density(
        tl.timeline_preset_density,
        forward=forward,
    )

def _format_timeline_preset_cue_snap(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return timeline_preset_cue_snap_display(
        state.render_timeline.timeline_preset_cue_snap
    )

def _apply_timeline_preset_cue_snap(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    tl = controls.session.timeline
    tl.timeline_preset_cue_snap = cycle_timeline_preset_cue_snap(
        tl.timeline_preset_cue_snap,
        forward=forward,
    )

def _format_timeline_preset_song_marker_snap(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return timeline_preset_song_marker_snap_display(
        state.render_timeline.timeline_preset_song_marker_snap
    )

def _apply_timeline_preset_song_marker_snap(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    tl = controls.session.timeline
    tl.timeline_preset_song_marker_snap = cycle_timeline_preset_song_marker_snap(
        tl.timeline_preset_song_marker_snap,
        forward=forward,
    )

def _format_timeline_preset_timeline_cuts(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return timeline_preset_timeline_cuts_display(
        state.render_timeline.timeline_preset_timeline_cuts
    )

def _apply_timeline_preset_timeline_cuts(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    tl = controls.session.timeline
    tl.timeline_preset_timeline_cuts = cycle_timeline_preset_timeline_cuts(
        tl.timeline_preset_timeline_cuts,
        forward=forward,
    )

def _format_timeline_preset_repopulate(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return timeline_preset_repopulate_display(
        state.render_timeline.timeline_preset_repopulate
    )

def _apply_timeline_preset_repopulate(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    tl = controls.session.timeline
    tl.timeline_preset_repopulate = cycle_timeline_preset_repopulate(
        tl.timeline_preset_repopulate,
        forward=forward,
    )

def _format_timeline_preset_conductor(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return timeline_preset_conductor_display(
        state.render_timeline.timeline_preset_conductor
    )

def _apply_timeline_preset_conductor(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    tl = controls.session.timeline
    tl.timeline_preset_conductor = cycle_timeline_preset_conductor(
        tl.timeline_preset_conductor,
        forward=forward,
    )

def _format_timeline_preset_mode(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return timeline_preset_mode_display(state.render_timeline.timeline_preset_mode)

def _apply_timeline_preset_mode(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    tl = controls.session.timeline
    tl.timeline_preset_mode = cycle_timeline_preset_mode(
        tl.timeline_preset_mode,
        forward=forward,
    )

def _format_visual_limiter_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return timeline_crossfade_display(state.render_timeline.limiter.enabled)

def _apply_visual_limiter_enabled(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    del _ctrl, _shift
    controls.set_visual_limiter_enabled(forward)

def _format_visual_limiter_threshold(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{int(round(state.render_timeline.limiter.threshold * 100))}%"

def _apply_visual_limiter_threshold(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    del _ctrl, _shift
    lim = controls.session.timeline.limiter
    delta = VISUAL_LIMITER_THRESHOLD_STEP if forward else -VISUAL_LIMITER_THRESHOLD_STEP
    lim.threshold = clamp_visual_limiter_threshold(
        round(lim.threshold + delta, 2)
    )

def _format_visual_limiter_ratio(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_timeline.limiter.ratio:.1f}:1"

def _apply_visual_limiter_ratio(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    del _ctrl, _shift
    lim = controls.session.timeline.limiter
    delta = VISUAL_LIMITER_RATIO_STEP if forward else -VISUAL_LIMITER_RATIO_STEP
    lim.ratio = clamp_visual_limiter_ratio(round(lim.ratio + delta, 1))

def _format_visual_limiter_release(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_timeline.limiter.release:.1f}s"

def _apply_visual_limiter_release(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    del _ctrl, _shift
    lim = controls.session.timeline.limiter
    delta = VISUAL_LIMITER_RELEASE_STEP if forward else -VISUAL_LIMITER_RELEASE_STEP
    lim.release = clamp_visual_limiter_release(round(lim.release + delta, 1))

def _format_timeline_hard_cut_fades_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return hard_cut_enabled_display(state.render_timeline.hard_cut_fades.enabled)

def _apply_timeline_hard_cut_fades_enabled(
    controls: TuningControls,
    _desc: RowDescriptor,
    _forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    group = controls.session.timeline.hard_cut_fades
    group.enabled = not group.enabled

def _format_timeline_hard_cut_fade_in(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_timeline.hard_cut_fades.fade_in:.1f}s"

def _apply_timeline_hard_cut_fade_in(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    group = controls.session.timeline.hard_cut_fades
    delta = TIMELINE_FADE_DURATION_STEP if forward else -TIMELINE_FADE_DURATION_STEP
    group.fade_in = clamp_timeline_fade_duration(round(group.fade_in + delta, 1))

def _format_timeline_hard_cut_fade_out(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_timeline.hard_cut_fades.fade_out:.1f}s"

def _apply_timeline_hard_cut_fade_out(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    group = controls.session.timeline.hard_cut_fades
    delta = TIMELINE_FADE_DURATION_STEP if forward else -TIMELINE_FADE_DURATION_STEP
    group.fade_out = clamp_timeline_fade_duration(round(group.fade_out + delta, 1))

def _format_timeline_soft_cut_fades_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return hard_cut_enabled_display(state.render_timeline.soft_cut_fades.enabled)

def _apply_timeline_soft_cut_fades_enabled(
    controls: TuningControls,
    _desc: RowDescriptor,
    _forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    group = controls.session.timeline.soft_cut_fades
    group.enabled = not group.enabled

def _format_timeline_soft_cut_fade_in(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_timeline.soft_cut_fades.fade_in:.1f}s"

def _apply_timeline_soft_cut_fade_in(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    group = controls.session.timeline.soft_cut_fades
    delta = TIMELINE_FADE_DURATION_STEP if forward else -TIMELINE_FADE_DURATION_STEP
    group.fade_in = clamp_timeline_fade_duration(round(group.fade_in + delta, 1))

def _format_timeline_soft_cut_fade_out(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_timeline.soft_cut_fades.fade_out:.1f}s"

def _apply_timeline_soft_cut_fade_out(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    group = controls.session.timeline.soft_cut_fades
    delta = TIMELINE_FADE_DURATION_STEP if forward else -TIMELINE_FADE_DURATION_STEP
    group.fade_out = clamp_timeline_fade_duration(round(group.fade_out + delta, 1))

def _format_timeline_hard_cut_crossfade(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return timeline_crossfade_display(state.render_timeline.hard_cut_fades.crossfade)

def _apply_timeline_hard_cut_crossfade(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    group = controls.session.timeline.hard_cut_fades
    group.crossfade = cycle_timeline_crossfade(group.crossfade, forward=forward)

def _format_timeline_soft_cut_crossfade(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return timeline_crossfade_display(state.render_timeline.soft_cut_fades.crossfade)

def _apply_timeline_soft_cut_crossfade(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    group = controls.session.timeline.soft_cut_fades
    group.crossfade = cycle_timeline_crossfade(group.crossfade, forward=forward)

def _apply_render_timeline_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    from cleave.viz.row_spec import row_spec
    if ctrl:
        if (
            controls.session.timeline.locked
            and row_spec(desc.kind).can_enable_disable
        ):
            return
        controls.set_render_timeline_enabled(forward)
        return
    apply_panel_anchor_toggle(controls, desc.kind, forward)

def _format_song_markers_count(state: TuningViewState, _desc: RowDescriptor) -> str:
    return f"({len(state.render_timeline.song_marker_times)})"

def _song_marker_type_display(marker_type: str) -> str:
    if marker_type == DEFAULT_SONG_MARKER_TYPE:
        return "-"
    return marker_type

def _format_song_marker_item(state: TuningViewState, desc: RowDescriptor) -> str:
    assert desc.marker_index is not None
    index = desc.marker_index
    times = state.render_timeline.song_marker_times
    types = state.render_timeline.song_marker_types
    marker_type = (
        types[index]
        if 0 <= index < len(types)
        else DEFAULT_SONG_MARKER_TYPE
    )
    return (
        f"[{format_marker_time(times[index])}] "
        f"{_song_marker_type_display(marker_type)}"
    )

def _apply_song_marker_type(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    assert desc.marker_index is not None
    markers = controls.session.song_markers
    index = desc.marker_index
    if index < 0 or index >= len(markers.markers):
        return
    current = markers.markers[index]
    next_type = cycle_song_marker_type(
        parse_song_marker_type(current.marker_type),
        forward=forward,
    )
    markers.markers[index] = SongMarker(current.time, next_type)
    warning = song_marker_gesture_warning(markers.markers, index)
    if warning is not None:
        controls.show_notification(warning)

def _visibility_timeline(
    state: TuningViewState, _desc: RowDescriptor
) -> tuple[bool, bool]:
    return (state.render_timeline.enabled, False)

SPECS: dict[RowKind, RowSpec] = {
    RowKind.RENDER_TIMELINE_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="TIMELINE",
        present_style=RowPresentStyle.COMPOSITE_HEADER,
        apply_horizontal=_apply_render_timeline_header,
        header_prefix="Render: ",
        header_suffix="TIMELINE",
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_timeline,
        help_title="Timeline",
        help_description=(
            "Layer visibility automation.",
            "When enabled, standard layer visibility is disabled.",
        ),
        quick_nav_target=True,
        can_enable_disable=True,
    ),
    RowKind.TIMELINE_PRESETS_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="timeline preset",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="Timeline preset",
        help_description=(
            "Stage character, density, re-populate, conductor, and mode,",
            "then apply a randomly generated timeline preset. Overwrites the current timeline.",
        ),
        is_sub_header=True,
    ),
    RowKind.TIMELINE_PRESET_CHARACTER: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="character",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_character,
        apply_horizontal=_apply_timeline_preset_character,
        help_title="Character",
        help_entries=(("Left/Right", "cycle character"),),
        help_description=(
            "Procedural timeline character used when applying a preset.",
            "Song markers favour cue placement; crescendo types build crescendos.",
        ),
        help_mode_entries=TIMELINE_PRESET_HELP_ENTRIES,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_PRESET_DENSITY: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="density",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_density,
        apply_horizontal=_apply_timeline_preset_density,
        help_title="Density",
        help_entries=(("Left/Right", "cycle density"),),
        help_description=(
            "How aggressively the generator favors denser layer stacks.",
            "Normal matches the default stack-cost ramp for the layer count.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_PRESET_CUE_SNAP: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="cue snap",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_cue_snap,
        apply_horizontal=_apply_timeline_preset_cue_snap,
        help_title="Cue snap",
        help_entries=(("Left/Right", "cycle cue snap"),),
        help_description=(
            "After build, snap cues to the beat or bar grid.",
            "None leaves cue times from the generator unchanged.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_PRESET_SONG_MARKER_SNAP: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="song marker snap",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_song_marker_snap,
        apply_horizontal=_apply_timeline_preset_song_marker_snap,
        help_title="Song marker snap",
        help_entries=(("Left/Right", "cycle song marker snap proximity"),),
        help_description=(
            "After cue snap, pull nearby cues onto song markers.",
            "Applies each_layer scope across all slots; none skips.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_PRESET_TIMELINE_CUTS: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="timeline cuts",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_timeline_cuts,
        apply_horizontal=_apply_timeline_preset_timeline_cuts,
        help_title="Timeline cuts",
        help_entries=(("Left/Right", "cycle timeline cuts"),),
        help_description=(
            "After snaps, assign hard/soft cut types to cues.",
            "By marker sets soft everywhere then hard on song markers.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_PRESET_REPOPULATE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="re-populate preset lists",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_repopulate,
        apply_horizontal=_apply_timeline_preset_repopulate,
        help_title="Re-populate Preset Lists",
        help_entries=(("Left/Right", "cycle re-populate mode"),),
        help_description=(
            "When Apply runs, optionally rebuild preset lists on layers with",
            "timeline-trigger switching: cue roles, directory random, or",
            "directory sequential. Choose no to leave lists unchanged.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_PRESET_CONDUCTOR: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="conductor",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_conductor,
        apply_horizontal=_apply_timeline_preset_conductor,
        help_title="Conductor",
        help_entries=(("Left/Right", "toggle conductor on/off"),),
        help_description=(
            "When on, stem energy shapes motif casting and cue levels.",
            "Requires project signals; otherwise apply skips the conductor.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_PRESET_MODE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="mode",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_mode,
        apply_horizontal=_apply_timeline_preset_mode,
        help_title="Mode",
        help_entries=(("Left/Right", "cycle layers / pattern mask"),),
        help_description=(
            "Layers uses the stacked timeline. Pattern mask enables",
            "render pattern mask with strips on Apply.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_PRESETS: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="apply timeline preset",
        present_style=RowPresentStyle.FULL_LINE,
        fit_strategy=FitStrategy.NONE,
        shows_enter_icon=True,
        help_title="Apply timeline preset",
        help_entries=(("Enter", "apply timeline preset"),),
        help_description=(
            "Apply the staged character, density, snaps, cuts, re-populate,",
            "conductor, and mode. Crescendo song markers build crescendos.",
            "Overwrites the timeline.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_VISUAL_LIMITER_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="visual limiter",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="Visual limiter",
        help_description=(
            "Duck busy stacked layers using post-composite busyness.",
            "Expand for enabled, threshold, ratio, and release.",
        ),
        is_sub_header=True,
    ),
    RowKind.TIMELINE_VISUAL_LIMITER_ENABLED: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="enabled",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_visual_limiter_enabled,
        apply_horizontal=_apply_visual_limiter_enabled,
        help_title="Visual limiter enabled",
        help_entries=(("Left/Right", "off / on"),),
        help_description=(
            "When off, the limiter is idle and remaining knobs hide.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_VISUAL_LIMITER_THRESHOLD: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="threshold",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_visual_limiter_threshold,
        apply_horizontal=_apply_visual_limiter_threshold,
        help_title="Visual limiter threshold",
        help_entries=(
            ("Left", "decrease threshold"),
            ("Right", "increase threshold"),
        ),
        help_description=(
            "Busyness level above which compression engages.",
        ),
        repeatable=True,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_VISUAL_LIMITER_RATIO: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="ratio",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_visual_limiter_ratio,
        apply_horizontal=_apply_visual_limiter_ratio,
        help_title="Visual limiter ratio",
        help_entries=(
            ("Left", "decrease ratio"),
            ("Right", "increase ratio"),
        ),
        help_description=(
            "Compression aggressiveness above the threshold.",
            "Higher ratios duck hot layers more.",
        ),
        repeatable=True,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_VISUAL_LIMITER_RELEASE: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="release",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_visual_limiter_release,
        apply_horizontal=_apply_visual_limiter_release,
        help_title="Visual limiter release",
        help_entries=(
            ("Left", "decrease release"),
            ("Right", "increase release"),
        ),
        help_description=(
            "Envelope release time constant in seconds.",
            "Controls how quickly ducking eases off.",
        ),
        repeatable=True,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_RESET: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="reset timeline",
        present_style=RowPresentStyle.FULL_LINE,
        fit_strategy=FitStrategy.NONE,
        shows_enter_icon=True,
        help_title="Reset timeline",
        help_entries=(("Enter", "reset timeline"),),
        help_description=(
            "Clear all timeline cues and set every layer",
            "on or off for the whole track.",
        ),
        help_mode_entries=TIMELINE_RESET_HELP_ENTRIES,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_BEAT_BAR_GRID_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="beat / bar grid",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="Beat / bar grid",
        help_description=(
            "AI beat detection powered by Beat This!",
        ),
        is_sub_header=True,
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
        help_title="Placement snap",
        help_entries=(("Left/Right", "cycle off / beat / bar"),),
        help_description=(
            "Applies when placing song markers and timeline cues",
            "Snap to the nearest beat or bar.",
            "Switch off when the beat detection is not accurate.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_SNAP_CUES_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="snap cues",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="Snap cues",
        help_description=(
            "One-shot actions that pull existing timeline cues onto the beat grid or song markers.",
        ),
        is_sub_header=True,
    ),
    RowKind.TIMELINE_SNAP_TO_BEATS: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="snap to beats",
        present_style=RowPresentStyle.FULL_LINE,
        fit_strategy=FitStrategy.NONE,
        shows_enter_icon=True,
        help_title="Snap to beats",
        help_entries=(("Enter", "snap cues to beats"),),
        help_description=(
            "Snap all timeline cues to the nearest beat.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_SNAP_TO_BARS: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="snap to bars",
        present_style=RowPresentStyle.FULL_LINE,
        fit_strategy=FitStrategy.NONE,
        shows_enter_icon=True,
        help_title="Snap to bars",
        help_entries=(("Enter", "snap cues to bars"),),
        help_description=(
            "Snap all timeline cues to the nearest bar.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_SNAP_TO_SONG_MARKERS: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="snap to song markers",
        present_style=RowPresentStyle.FULL_LINE,
        fit_strategy=FitStrategy.NONE,
        shows_enter_icon=True,
        help_title="Snap to song markers",
        help_entries=(("Enter", "snap cues to song markers"),),
        help_description=(
            "Pull closest cues within proximity onto song markers.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_CUTS_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="timeline cuts",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="Timeline cuts",
        help_description=(
            "Opacity fade in and out for timeline cue edges by cut type.",
        ),
        is_sub_header=True,
    ),
    RowKind.TIMELINE_HARD_CUTS: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="hard cuts",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_hard_cut_fades_enabled,
        apply_horizontal=_apply_timeline_hard_cut_fades_enabled,
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
        panel_label="crossfade",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_hard_cut_crossfade,
        apply_horizontal=_apply_timeline_hard_cut_crossfade,
        help_title="Hard cut crossfade",
        help_entries=(("Left/Right", "off / on"),),
        help_description=(
            "Center hard-cut fade ramps on the cue time instead of aligning to an edge.",
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
        panel_label="crossfade",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_soft_cut_crossfade,
        apply_horizontal=_apply_timeline_soft_cut_crossfade,
        help_title="Soft cut crossfade",
        help_entries=(("Left/Right", "off / on"),),
        help_description=(
            "Center soft-cut fade ramps on the cue time instead of aligning to an edge.",
        ),
        repeatable=True,
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_APPLY_SOFT_CUTS: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="apply soft cuts to cues",
        present_style=RowPresentStyle.FULL_LINE,
        fit_strategy=FitStrategy.NONE,
        shows_enter_icon=True,
        help_title="Apply soft cuts to cues",
        help_entries=(("Enter", "apply soft cuts"),),
        help_description=(
            "Set cut type soft on all cues, song-marker cues, or all except markers.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.TIMELINE_APPLY_HARD_CUTS: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="apply hard cuts to cues",
        present_style=RowPresentStyle.FULL_LINE,
        fit_strategy=FitStrategy.NONE,
        shows_enter_icon=True,
        help_title="Apply hard cuts to cues",
        help_entries=(("Enter", "apply hard cuts"),),
        help_description=(
            "Set cut type hard on all cues, song-marker cues, or all except markers.",
        ),
        blocked_by_section_lock=True,
    ),
    RowKind.SONG_MARKERS_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="song markers",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        format_value=_format_song_markers_count,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="Song markers",
        help_description=(
            "Manual song markers for major transitions.",
            "Ctrl+Enter drops a marker at the playhead.",
        ),
        is_sub_header=True,
    ),
    RowKind.SONG_MARKER_ITEM: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="",
        present_style=RowPresentStyle.FULL_LINE,
        format_value=_format_song_marker_item,
        apply_horizontal=_apply_song_marker_type,
        fit_strategy=FitStrategy.NONE,
        shows_enter_icon=True,
        help_title="Song marker",
        help_entries=(
            ("Enter", "seek to marker"),
            ("Left / Right", "cycle marker type"),
            ("Delete", "confirm remove"),
        ),
        help_description=(
            "A song marker time and type (-, crescendo,",
            "diminuendo). Crescendo markers build crescendos on",
            "timeline preset apply. Enter seeks; Left/Right cycles type.",
        ),
        blocked_by_section_lock=True,
    ),
}
