"""Panel field manifest for the live tuning overlay.

Single source for panel labels, value formatting, tree branch chrome, and
Left/Right mutations. Structure (nesting, expand/collapse) stays in
row_sections.py; affordance and help stay in row_semantics.py.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

from cleave.config_schema.editor import ui_fade_display
from cleave.config_schema.layers import (
    hard_cut_enabled_display,
    preset_start_clean_display,
    preset_switching_display,
    preset_switching_trigger_display,
)
from cleave.config_schema.render import (
    PATTERN_MASK_DENSITY_STEP,
    PATTERN_MASK_DENSITY_STEP_LARGE,
    PATTERN_MASK_FEATHER_PCT_STEP,
    PATTERN_MASK_FEATHER_PCT_STEP_LARGE,
    PATTERN_MASK_TRANSITION_STEP,
    PATTERN_MASK_TRANSITION_STEP_LARGE,
)
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
from cleave.extract import stem_control_label, stem_overlay_header
from cleave.pattern_mask import (
    pattern_mask_invert_display,
)
from cleave.song_markers import (
    DEFAULT_SONG_MARKER_TYPE,
    SongMarker,
    cycle_song_marker_type,
    format_marker_time,
    parse_song_marker_type,
    song_marker_gesture_warning,
)
from cleave.timeline_presets.characters import (
    cycle_timeline_preset_kind,
    timeline_preset_kind_display,
)
from cleave.timeline_presets.conductor import (
    cycle_timeline_preset_conductor,
    timeline_preset_conductor_display,
)
from cleave.timeline_presets.mode import (
    cycle_timeline_preset_mode,
    timeline_preset_mode_display,
)
from cleave.timeline_presets.repopulate import (
    cycle_timeline_preset_repopulate,
    timeline_preset_repopulate_display,
)
from cleave.timeline_presets.cue_snap import (
    cycle_timeline_preset_cue_snap,
    timeline_preset_cue_snap_display,
)
from cleave.timeline_presets.density import (
    cycle_timeline_preset_density,
    timeline_preset_density_display,
)
from cleave.timeline_presets.song_marker_snap import (
    cycle_timeline_preset_song_marker_snap,
    timeline_preset_song_marker_snap_display,
)
from cleave.timeline_presets.timeline_cuts import (
    cycle_timeline_preset_timeline_cuts,
    timeline_preset_timeline_cuts_display,
)
from cleave.viz.fonts import render_overlay_font_display
from cleave.viz.row_semantics import (
    ACTION_ROW_KINDS,
    RowAffordance,
    RowDescriptor,
    RowKind,
    row_behavior,
)
from cleave.viz.row_sections import (
    apply_expand_toggle,
    apply_panel_anchor_toggle,
    expand_arrow_for_header,
    expand_arrow_glyph,
    row_tree_indent_depth,
)
from cleave.viz.tuning_view_state import TrackBlock, TuningViewState
if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls


class RowPresentStyle(Enum):
    LABELED_VALUE = auto()
    ACTION_PARAMETER = auto()
    EXPAND_SUBHEADER = auto()
    COMPOSITE_HEADER = auto()
    PATH_ICON = auto()
    FULL_LINE = auto()
    DYNAMIC = auto()
    TRACK_HEADER = auto()
    NOTIFICATION = auto()
    SPACER = auto()


class FitStrategy(Enum):
    PLAIN = auto()
    COUNTER_LABEL = auto()
    PATH = auto()
    NONE = auto()


FieldMutator = Callable[["TuningControls", RowDescriptor, bool, bool, bool], None]
VisibilityIconFn = Callable[[TuningViewState, RowDescriptor], tuple[bool, bool]]


@dataclass(frozen=True)
class RowFieldDef:
    panel_label: str
    present_style: RowPresentStyle
    format_value: Callable[[TuningViewState, RowDescriptor], str] | None = None
    apply_horizontal: FieldMutator | None = None
    header_prefix: str | None = None
    header_suffix: str | None = None
    fit_strategy: FitStrategy = FitStrategy.PLAIN
    visibility_icon: VisibilityIconFn | None = None
    shows_enter_icon: bool = False


def tree_branch_leading_spaces(depth: int) -> str:
    """Leading spaces before a branch glyph for nested tree depth."""
    if depth <= 1:
        return ""
    return " " * (2 * (depth - 1))


def tree_branch_prefix(depth: int) -> str:
    """Branch glyph for tree depth; pixel indent comes from row_tree_indent_depth."""
    if depth <= 0:
        return ""
    return tree_branch_leading_spaces(depth) + "└─ "


def _format_settings_preview_quality(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.settings.preview_quality


def _format_settings_editor_mode(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    from cleave.viz.session import EDITOR_MODE_PANEL_LABELS

    return EDITOR_MODE_PANEL_LABELS[state.settings.editor_mode_selection]  # type: ignore[index]


def editor_mode_confirm_pending(state: TuningViewState) -> bool:
    """True when Left/Right staged a mode that still needs Enter."""
    return state.settings.editor_mode_selection != state.settings.editor_mode


def _format_settings_ui_width_mode(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.settings.ui_width_mode


def _format_settings_ui_width(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return str(state.settings.ui_width)


def _format_settings_ui_fade(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return ui_fade_display(state.settings.ui_fade)


def _format_settings_residual_latency_ms(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.settings.residual_latency_ms} ms"


def _format_settings_measure_latency(
    _state: TuningViewState, _desc: RowDescriptor
) -> str:
    return "measure latency"


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


def _apply_settings_editor_mode(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls.editor_mode.cycle_editor_mode_selection(forward=forward)


def _apply_settings_preview_quality(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls.settings.cycle_preview_quality(forward=forward)
    controls.apply_preview_resolutions()


def _apply_settings_ui_width_mode(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls.settings.cycle_ui_width_mode(forward=forward)


def _apply_settings_ui_width(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    controls.settings.adjust_ui_width(forward=forward, ctrl=ctrl)


def _apply_settings_ui_fade(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    controls.settings.adjust_ui_fade(forward=forward, ctrl=ctrl)


def _apply_settings_residual_latency_ms(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    controls.settings.adjust_residual_latency_ms(forward=forward, ctrl=ctrl)
    controls.on_residual_latency_changed()


def _track_block(state: TuningViewState, desc: RowDescriptor) -> TrackBlock:
    assert desc.slot is not None
    return state.tracks[desc.slot]


def _overlay_card_block(state: TuningViewState, desc: RowDescriptor):
    assert desc.card is not None
    return getattr(state.render_overlays, desc.card)


def _overlay_card_controls(controls: TuningControls, desc: RowDescriptor):
    assert desc.card is not None
    return controls.render_overlays.card(desc.card)


def _overlay_card_block_session(controls: TuningControls, desc: RowDescriptor):
    assert desc.card is not None
    return getattr(controls.session.render_overlays, desc.card)


def overlay_card_panel_label(kind: RowKind, card: str | None) -> str | None:
    if card is None:
        return None
    if kind == RowKind.RENDER_OVERLAY_CARD_HEADER:
        return "opening card" if card == "opening_card" else "closing card"
    if kind == RowKind.RENDER_OVERLAY_CARD_TIME:
        return "appear at" if card == "opening_card" else "disappear at"
    return None


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


def _format_overlay_card_position(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _overlay_card_block(state, desc).runtime.position


def _format_overlay_card_title_font_size(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.title_font_size}px"


def _format_overlay_card_title_font(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return render_overlay_font_display(_overlay_card_block(state, desc).runtime.title_font)


def _format_overlay_card_title_margin_bottom(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.title_margin_bottom}px"


def _format_overlay_card_body_font_size(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.body_font_size}px"


def _format_overlay_card_body_font(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return render_overlay_font_display(_overlay_card_block(state, desc).runtime.body_font)


def _format_overlay_card_opacity(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.opacity_pct}%"


def _format_overlay_card_border_width(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.border_width}px"


def _format_overlay_card_time(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    anim = _overlay_card_block(state, desc).runtime.animation
    if desc.card == "opening_card":
        return f"{getattr(anim, 'appear_at', 0.0):.1f}s"
    return f"{getattr(anim, 'disappear_at', 0.0):.1f}s"


def _format_overlay_card_display_time(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_overlay_card_block(state, desc).runtime.animation.display_time:.1f}s"


def _format_overlay_card_animation_type(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _overlay_card_block(state, desc).runtime.animation.type


def _format_overlay_card_slide_direction(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _overlay_card_block(state, desc).runtime.animation.slide_direction


def _format_render_post_fx_fade_in(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.fade_in:.1f}s"


def _format_render_post_fx_fade_out(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.fade_out:.1f}s"


def _format_render_post_fx_highlight_rolloff_mode(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.render_post_fx.highlight_rolloff.mode


def _format_render_post_fx_highlight_rolloff_curve(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.render_post_fx.highlight_rolloff.curve


def _format_render_post_fx_highlight_rolloff_threshold(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.highlight_rolloff.threshold_pct}%"


def _format_render_post_fx_highlight_rolloff_ceiling(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.highlight_rolloff.ceiling_pct}%"


def _format_render_post_fx_highlight_rolloff_strength(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.highlight_rolloff.strength_pct}%"


def _format_render_post_fx_highlight_rolloff_softness(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.highlight_rolloff.softness_pct}%"


def _format_render_post_fx_highlight_rolloff_desaturation(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.highlight_rolloff.desaturation_pct}%"


def _format_render_post_fx_chroma_boost_mode(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.render_post_fx.chroma_boost.mode


def _format_render_post_fx_chroma_boost_variant(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.render_post_fx.chroma_boost.variant


def _format_render_post_fx_chroma_boost_amount(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_post_fx.chroma_boost.amount_pct}%"


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


def _apply_overlay_card_position(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    _overlay_card_controls(controls, desc).cycle_position(forward=forward)


def _apply_overlay_card_title_font_size(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_title_font_size(
        card.title_font_size + delta
    )


def _apply_overlay_card_title_font(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    _overlay_card_controls(controls, desc).cycle_title_font(forward=forward)


def _apply_overlay_card_title_margin_bottom(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_title_margin_bottom(
        card.title_margin_bottom + delta
    )


def _apply_overlay_card_body_font_size(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_body_font_size(
        card.body_font_size + delta
    )


def _apply_overlay_card_body_font(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    _overlay_card_controls(controls, desc).cycle_body_font(forward=forward)


def _apply_overlay_card_opacity(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_opacity(card.opacity_pct + delta)


def _apply_overlay_card_border_width(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_border_width(card.border_width + delta)


def _apply_overlay_card_time(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = 30.0 if ctrl else 1.0
    delta = step if forward else -step
    card_controls = _overlay_card_controls(controls, desc)
    anim = _overlay_card_block_session(controls, desc).animation
    if desc.card == "opening_card":
        card_controls.set_appear_at(getattr(anim, "appear_at", 0.0) + delta)
        return
    card_controls.set_disappear_at(getattr(anim, "disappear_at", 0.0) + delta)


def _apply_overlay_card_display_time(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = 30.0 if ctrl else 1.0
    delta = step if forward else -step
    card = _overlay_card_block_session(controls, desc)
    _overlay_card_controls(controls, desc).set_display_time(
        card.animation.display_time + delta
    )


def _apply_overlay_card_animation_type(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    _overlay_card_controls(controls, desc).cycle_animation_type(forward=forward)


def _apply_overlay_card_slide_direction(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    _overlay_card_controls(controls, desc).cycle_slide_direction(forward=forward)


def _apply_render_post_fx_fade_in(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10.0 if ctrl else 1.0
    delta = step if forward else -step
    controls.render_post_fx.set_fade_in(
        controls.session.render_post_fx.fade_in + delta
    )


def _apply_render_post_fx_fade_out(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10.0 if ctrl else 1.0
    delta = step if forward else -step
    controls.render_post_fx.set_fade_out(
        controls.session.render_post_fx.fade_out + delta
    )


def _apply_render_post_fx_highlight_rolloff_mode(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls.render_post_fx.cycle_highlight_rolloff_mode(forward=forward)


def _apply_render_post_fx_highlight_rolloff_curve(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls.render_post_fx.cycle_highlight_rolloff_curve(forward=forward)


def _apply_render_post_fx_highlight_rolloff_threshold(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    hr = controls.session.render_post_fx.highlight_rolloff
    controls.render_post_fx.set_highlight_rolloff_threshold_pct(
        hr.threshold_pct + delta
    )


def _apply_render_post_fx_highlight_rolloff_ceiling(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    hr = controls.session.render_post_fx.highlight_rolloff
    controls.render_post_fx.set_highlight_rolloff_ceiling_pct(
        hr.ceiling_pct + delta
    )


def _apply_render_post_fx_highlight_rolloff_strength(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    hr = controls.session.render_post_fx.highlight_rolloff
    controls.render_post_fx.set_highlight_rolloff_strength_pct(
        hr.strength_pct + delta
    )


def _apply_render_post_fx_highlight_rolloff_softness(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    hr = controls.session.render_post_fx.highlight_rolloff
    controls.render_post_fx.set_highlight_rolloff_softness_pct(
        hr.softness_pct + delta
    )


def _apply_render_post_fx_highlight_rolloff_desaturation(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    hr = controls.session.render_post_fx.highlight_rolloff
    controls.render_post_fx.set_highlight_rolloff_desaturation_pct(
        hr.desaturation_pct + delta
    )


def _apply_render_post_fx_chroma_boost_mode(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls.render_post_fx.cycle_chroma_boost_mode(forward=forward)


def _apply_render_post_fx_chroma_boost_variant(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls.render_post_fx.cycle_chroma_boost_variant(forward=forward)


def _apply_render_post_fx_chroma_boost_amount(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    cb = controls.session.render_post_fx.chroma_boost
    controls.render_post_fx.set_chroma_boost_amount_pct(cb.amount_pct + delta)


def _apply_expand_subheader(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    apply_expand_toggle(
        controls, desc.kind, desc.slot, forward, card=desc.card
    )


def _apply_settings_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    apply_expand_toggle(
        controls, desc.kind, desc.slot, forward, card=desc.card
    )


def _apply_track_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    shift: bool,
) -> None:
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
            and row_behavior(desc.kind).can_enable_disable
        ):
            return
        controls.layer_mutations.set_enabled(slot, forward)
        return
    apply_expand_toggle(controls, desc.kind, slot, forward, card=desc.card)


def _apply_render_overlays_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    shift: bool,
) -> None:
    if shift:
        if forward:
            controls.render_overlays.enter_solo()
        else:
            controls.render_overlays.exit_solo()
        return
    if ctrl:
        if (
            controls.session.render_overlays.locked
            and row_behavior(desc.kind).can_enable_disable
        ):
            return
        controls.render_overlays.set_enabled(forward)
        return
    apply_expand_toggle(
        controls, desc.kind, desc.slot, forward, card=desc.card
    )


def _apply_overlay_card_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    if ctrl:
        if (
            controls.session.render_overlays.locked
            and row_behavior(desc.kind).can_enable_disable
        ):
            return
        _overlay_card_controls(controls, desc).set_enabled(forward)
        return
    apply_expand_toggle(
        controls, desc.kind, desc.slot, forward, card=desc.card
    )


def _apply_render_post_fx_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    if ctrl:
        if (
            controls.session.render_post_fx.locked
            and row_behavior(desc.kind).can_enable_disable
        ):
            return
        controls.render_post_fx.set_enabled(forward)
        return
    apply_expand_toggle(
        controls, desc.kind, desc.slot, forward, card=desc.card
    )


def _format_render_pattern_mask_type(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.render_pattern_mask.type


def _format_render_pattern_mask_feather(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_pattern_mask.feather_pct}%"


def _format_render_pattern_mask_density(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_pattern_mask.density:.1f}x"


def _format_render_pattern_mask_invert(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return pattern_mask_invert_display(state.render_pattern_mask.invert)


def _format_render_pattern_mask_transition(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_pattern_mask.transition:.1f}s"


def _format_render_pattern_mask_seed(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return str(state.render_pattern_mask.seed)


def _apply_render_pattern_mask_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    if ctrl:
        if (
            controls.session.render_pattern_mask.locked
            and row_behavior(desc.kind).can_enable_disable
        ):
            return
        controls.render_pattern_mask.set_enabled(forward)
        return
    apply_expand_toggle(
        controls, desc.kind, desc.slot, forward, card=desc.card
    )


def _apply_render_pattern_mask_type(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls.render_pattern_mask.cycle_type(forward=forward)


def _apply_render_pattern_mask_feather(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = (
        PATTERN_MASK_FEATHER_PCT_STEP_LARGE if ctrl else PATTERN_MASK_FEATHER_PCT_STEP
    )
    delta = step if forward else -step
    controls.render_pattern_mask.set_feather_pct(
        controls.session.render_pattern_mask.feather_pct + delta
    )


def _apply_render_pattern_mask_density(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = PATTERN_MASK_DENSITY_STEP_LARGE if ctrl else PATTERN_MASK_DENSITY_STEP
    delta = step if forward else -step
    controls.render_pattern_mask.set_density(
        controls.session.render_pattern_mask.density + delta
    )


def _apply_render_pattern_mask_invert(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls.render_pattern_mask.cycle_invert(forward=forward)


def _apply_render_pattern_mask_transition(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    step = (
        PATTERN_MASK_TRANSITION_STEP_LARGE if ctrl else PATTERN_MASK_TRANSITION_STEP
    )
    delta = step if forward else -step
    controls.render_pattern_mask.set_transition(
        controls.session.render_pattern_mask.transition + delta
    )


def _apply_render_pattern_mask_seed(
    controls: TuningControls,
    _desc: RowDescriptor,
    _forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls.render_pattern_mask.respin_seed()


def _apply_render_timeline_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    if ctrl:
        if (
            controls.session.timeline.locked
            and row_behavior(desc.kind).can_enable_disable
        ):
            return
        controls.set_render_timeline_enabled(forward)
        return
    apply_panel_anchor_toggle(controls, desc.kind, forward)


def _format_config_header(state: TuningViewState, _desc: RowDescriptor) -> str:
    return state.active_config_label


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


def _format_transport(_state: TuningViewState, _desc: RowDescriptor) -> str:
    return ""


def _format_panel_notification(state: TuningViewState, desc: RowDescriptor) -> str:
    if desc.marker_index == 0:
        return state.persistent_notification_message or ""
    return state.notification_message or ""


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


def _noop_horizontal(
    _controls: TuningControls,
    _desc: RowDescriptor,
    _forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    return


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


def _apply_transport(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    shift: bool,
) -> None:
    from cleave.viz.controls import SEEK_LONG, SEEK_SHORT, SEEK_TINY

    if ctrl:
        delta_sec = SEEK_LONG
    elif shift:
        delta_sec = SEEK_TINY
    else:
        delta_sec = SEEK_SHORT
    if not forward:
        delta_sec = -delta_sec
    controls.do_seek(delta_sec)


def _visibility_track(
    state: TuningViewState, desc: RowDescriptor
) -> tuple[bool, bool]:
    assert desc.slot is not None
    block = state.tracks[desc.slot]
    return (block.visible, state.solo_slot == desc.slot)


def _visibility_overlays(
    state: TuningViewState, _desc: RowDescriptor
) -> tuple[bool, bool]:
    block = state.render_overlays
    any_enabled = (
        block.opening_card.runtime.enabled or block.closing_card.runtime.enabled
    )
    return (any_enabled, block.solo)


def _visibility_post_fx(
    state: TuningViewState, _desc: RowDescriptor
) -> tuple[bool, bool]:
    block = state.render_post_fx
    return (block.enabled, block.solo)


def _visibility_pattern_mask(
    state: TuningViewState, _desc: RowDescriptor
) -> tuple[bool, bool]:
    return (state.render_pattern_mask.enabled, False)


def _visibility_timeline(
    state: TuningViewState, _desc: RowDescriptor
) -> tuple[bool, bool]:
    return (state.render_timeline.enabled, False)


ROW_FIELDS: dict[RowKind, RowFieldDef] = {
    RowKind.SETTINGS_HEADER: RowFieldDef(
        panel_label="Editor Settings",
        present_style=RowPresentStyle.COMPOSITE_HEADER,
        apply_horizontal=_apply_settings_header,
    ),
    RowKind.SETTINGS_EDITOR_MODE: RowFieldDef(
        panel_label="editor mode",
        present_style=RowPresentStyle.ACTION_PARAMETER,
        format_value=_format_settings_editor_mode,
        apply_horizontal=_apply_settings_editor_mode,
    ),
    RowKind.SETTINGS_PREVIEW_QUALITY: RowFieldDef(
        panel_label="preview quality",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_preview_quality,
        apply_horizontal=_apply_settings_preview_quality,
    ),
    RowKind.SETTINGS_UI_HEADER: RowFieldDef(
        panel_label="UI",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.SETTINGS_UI_WIDTH_MODE: RowFieldDef(
        panel_label="width mode",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_ui_width_mode,
        apply_horizontal=_apply_settings_ui_width_mode,
    ),
    RowKind.SETTINGS_UI_WIDTH: RowFieldDef(
        panel_label="max width",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_ui_width,
        apply_horizontal=_apply_settings_ui_width,
    ),
    RowKind.SETTINGS_UI_FADE: RowFieldDef(
        panel_label="auto-fade",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_ui_fade,
        apply_horizontal=_apply_settings_ui_fade,
    ),
    RowKind.SETTINGS_LATENCY_COMPENSATION_HEADER: RowFieldDef(
        panel_label="Latency Compensation",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.SETTINGS_RESIDUAL_LATENCY_MS: RowFieldDef(
        panel_label="residual latency",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_settings_residual_latency_ms,
        apply_horizontal=_apply_settings_residual_latency_ms,
    ),
    RowKind.SETTINGS_MEASURE_LATENCY: RowFieldDef(
        panel_label="measure latency",
        present_style=RowPresentStyle.FULL_LINE,
        format_value=_format_settings_measure_latency,
    ),
    RowKind.TRACK_HEADER: RowFieldDef(
        panel_label="Layer",
        present_style=RowPresentStyle.TRACK_HEADER,
        apply_horizontal=_apply_track_header,
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_track,
    ),
    RowKind.TRACK_PRESET_SWITCHING: RowFieldDef(
        panel_label="preset switching",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        format_value=_format_track_preset_switching_mode,
        apply_horizontal=_apply_track_preset_switching_mode,
    ),
    RowKind.TRACK_EFFECTS_HEADER: RowFieldDef(
        panel_label="cleave effects",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.TRACK_STEM: RowFieldDef(
        panel_label="driving stem",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_stem,
        apply_horizontal=_apply_track_stem,
    ),
    RowKind.TRACK_BLEND: RowFieldDef(
        panel_label="blend mode",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_blend,
        apply_horizontal=_apply_track_blend,
    ),
    RowKind.TRACK_OPACITY: RowFieldDef(
        panel_label="opacity",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_opacity,
        apply_horizontal=_apply_track_opacity,
    ),
    RowKind.TRACK_BEAT: RowFieldDef(
        panel_label="beat sensitivity",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_beat,
        apply_horizontal=_apply_track_beat,
    ),
    RowKind.TRACK_PRESET_SWITCHING_TRIGGER: RowFieldDef(
        panel_label="trigger",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_preset_switching_trigger,
        apply_horizontal=_apply_track_preset_switching_trigger,
    ),
    RowKind.TRACK_PRESET_LIST: RowFieldDef(
        panel_label="preset list",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        format_value=_format_track_preset_list_count,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.TRACK_PRESET_LIST_ITEM: RowFieldDef(
        panel_label="preset",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_track_preset_list_item,
        apply_horizontal=_noop_horizontal,
    ),
    RowKind.TRACK_PRESET_LIST_ADD: RowFieldDef(
        panel_label="add current preset",
        present_style=RowPresentStyle.FULL_LINE,
        apply_horizontal=_noop_horizontal,
    ),
    RowKind.TRACK_PRESET_LIST_POPULATE: RowFieldDef(
        panel_label="populate presets",
        present_style=RowPresentStyle.FULL_LINE,
        apply_horizontal=_noop_horizontal,
    ),
    RowKind.TRACK_PRESET_DURATION: RowFieldDef(
        panel_label="duration",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_preset_duration,
        apply_horizontal=_apply_track_preset_duration,
    ),
    RowKind.TRACK_SOFT_CUT_DURATION: RowFieldDef(
        panel_label="soft cut",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_soft_cut_duration,
        apply_horizontal=_apply_track_soft_cut_duration,
    ),
    RowKind.TRACK_EASTER_EGG: RowFieldDef(
        panel_label="easter egg",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_easter_egg,
        apply_horizontal=_apply_track_easter_egg,
    ),
    RowKind.TRACK_PRESET_START_CLEAN: RowFieldDef(
        panel_label="start clean",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_preset_start_clean,
        apply_horizontal=_apply_track_preset_start_clean,
    ),
    RowKind.TRACK_HARD_CUT_ENABLED: RowFieldDef(
        panel_label="hard cut",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_hard_cut_enabled,
        apply_horizontal=_apply_track_hard_cut_enabled,
    ),
    RowKind.TRACK_HARD_CUT_DURATION: RowFieldDef(
        panel_label="hard cut min",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_hard_cut_duration,
        apply_horizontal=_apply_track_hard_cut_duration,
    ),
    RowKind.TRACK_HARD_CUT_SENSITIVITY: RowFieldDef(
        panel_label="hard cut sens",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_hard_cut_sensitivity,
        apply_horizontal=_apply_track_hard_cut_sensitivity,
    ),
    RowKind.RENDER_OVERLAYS_HEADER: RowFieldDef(
        panel_label="OVERLAYS",
        present_style=RowPresentStyle.COMPOSITE_HEADER,
        header_prefix="Render: ",
        header_suffix="OVERLAYS",
        apply_horizontal=_apply_render_overlays_header,
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_overlays,
    ),
    RowKind.RENDER_OVERLAY_CARD_HEADER: RowFieldDef(
        panel_label="card",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_overlay_card_header,
    ),
    RowKind.RENDER_OVERLAY_CARD_POSITION: RowFieldDef(
        panel_label="position",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_position,
        apply_horizontal=_apply_overlay_card_position,
    ),
    RowKind.RENDER_OVERLAY_CARD_TITLE_HEADER: RowFieldDef(
        panel_label="title",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.RENDER_OVERLAY_CARD_TITLE_FONT_SIZE: RowFieldDef(
        panel_label="font size",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_title_font_size,
        apply_horizontal=_apply_overlay_card_title_font_size,
    ),
    RowKind.RENDER_OVERLAY_CARD_TITLE_FONT: RowFieldDef(
        panel_label="font",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_title_font,
        apply_horizontal=_apply_overlay_card_title_font,
    ),
    RowKind.RENDER_OVERLAY_CARD_TITLE_MARGIN_BOTTOM: RowFieldDef(
        panel_label="margin bottom",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_title_margin_bottom,
        apply_horizontal=_apply_overlay_card_title_margin_bottom,
    ),
    RowKind.RENDER_OVERLAY_CARD_BODY_FONT_SIZE: RowFieldDef(
        panel_label="font size",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_body_font_size,
        apply_horizontal=_apply_overlay_card_body_font_size,
    ),
    RowKind.RENDER_OVERLAY_CARD_BODY_FONT: RowFieldDef(
        panel_label="font",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_body_font,
        apply_horizontal=_apply_overlay_card_body_font,
    ),
    RowKind.RENDER_OVERLAY_CARD_BODY_HEADER: RowFieldDef(
        panel_label="body",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.RENDER_OVERLAY_CARD_OPACITY: RowFieldDef(
        panel_label="background opacity",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_opacity,
        apply_horizontal=_apply_overlay_card_opacity,
    ),
    RowKind.RENDER_OVERLAY_CARD_BORDER_WIDTH: RowFieldDef(
        panel_label="border width",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_border_width,
        apply_horizontal=_apply_overlay_card_border_width,
    ),
    RowKind.RENDER_OVERLAY_CARD_ANIMATION_HEADER: RowFieldDef(
        panel_label="animation",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.RENDER_OVERLAY_CARD_ANIMATION_TYPE: RowFieldDef(
        panel_label="type",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_animation_type,
        apply_horizontal=_apply_overlay_card_animation_type,
    ),
    RowKind.RENDER_OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION: RowFieldDef(
        panel_label="slide-direction",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_slide_direction,
        apply_horizontal=_apply_overlay_card_slide_direction,
    ),
    RowKind.RENDER_OVERLAY_CARD_TIME: RowFieldDef(
        panel_label="card time",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_time,
        apply_horizontal=_apply_overlay_card_time,
    ),
    RowKind.RENDER_OVERLAY_CARD_DISPLAY_TIME: RowFieldDef(
        panel_label="display time",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_overlay_card_display_time,
        apply_horizontal=_apply_overlay_card_display_time,
    ),
    RowKind.RENDER_POST_FX_FADE_IN: RowFieldDef(
        panel_label="fade in",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_fade_in,
        apply_horizontal=_apply_render_post_fx_fade_in,
    ),
    RowKind.RENDER_POST_FX_HEADER: RowFieldDef(
        panel_label="POST FX",
        present_style=RowPresentStyle.COMPOSITE_HEADER,
        header_prefix="Render: ",
        header_suffix="POST FX",
        apply_horizontal=_apply_render_post_fx_header,
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_post_fx,
    ),
    RowKind.RENDER_POST_FX_FADE_OUT: RowFieldDef(
        panel_label="fade out",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_fade_out,
        apply_horizontal=_apply_render_post_fx_fade_out,
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_HEADER: RowFieldDef(
        panel_label="highlight rolloff",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_MODE: RowFieldDef(
        panel_label="mode",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_highlight_rolloff_mode,
        apply_horizontal=_apply_render_post_fx_highlight_rolloff_mode,
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CURVE: RowFieldDef(
        panel_label="curve",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_highlight_rolloff_curve,
        apply_horizontal=_apply_render_post_fx_highlight_rolloff_curve,
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD: RowFieldDef(
        panel_label="threshold",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_highlight_rolloff_threshold,
        apply_horizontal=_apply_render_post_fx_highlight_rolloff_threshold,
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CEILING: RowFieldDef(
        panel_label="ceiling",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_highlight_rolloff_ceiling,
        apply_horizontal=_apply_render_post_fx_highlight_rolloff_ceiling,
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_STRENGTH: RowFieldDef(
        panel_label="strength",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_highlight_rolloff_strength,
        apply_horizontal=_apply_render_post_fx_highlight_rolloff_strength,
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_SOFTNESS: RowFieldDef(
        panel_label="softness",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_highlight_rolloff_softness,
        apply_horizontal=_apply_render_post_fx_highlight_rolloff_softness,
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_DESATURATION: RowFieldDef(
        panel_label="desaturation",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_highlight_rolloff_desaturation,
        apply_horizontal=_apply_render_post_fx_highlight_rolloff_desaturation,
    ),
    RowKind.RENDER_POST_FX_CHROMA_BOOST_HEADER: RowFieldDef(
        panel_label="chroma boost",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.RENDER_POST_FX_CHROMA_BOOST_MODE: RowFieldDef(
        panel_label="mode",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_chroma_boost_mode,
        apply_horizontal=_apply_render_post_fx_chroma_boost_mode,
    ),
    RowKind.RENDER_POST_FX_CHROMA_BOOST_VARIANT: RowFieldDef(
        panel_label="variant",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_chroma_boost_variant,
        apply_horizontal=_apply_render_post_fx_chroma_boost_variant,
    ),
    RowKind.RENDER_POST_FX_CHROMA_BOOST_AMOUNT: RowFieldDef(
        panel_label="amount",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_post_fx_chroma_boost_amount,
        apply_horizontal=_apply_render_post_fx_chroma_boost_amount,
    ),
    RowKind.RENDER_PATTERN_MASK_HEADER: RowFieldDef(
        panel_label="PATTERN MASK",
        present_style=RowPresentStyle.COMPOSITE_HEADER,
        header_prefix="Render: ",
        header_suffix="PATTERN MASK",
        apply_horizontal=_apply_render_pattern_mask_header,
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_pattern_mask,
    ),
    RowKind.RENDER_PATTERN_MASK_TYPE: RowFieldDef(
        panel_label="type",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_pattern_mask_type,
        apply_horizontal=_apply_render_pattern_mask_type,
    ),
    RowKind.RENDER_PATTERN_MASK_DENSITY: RowFieldDef(
        panel_label="density",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_pattern_mask_density,
        apply_horizontal=_apply_render_pattern_mask_density,
    ),
    RowKind.RENDER_PATTERN_MASK_FEATHER: RowFieldDef(
        panel_label="feather",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_pattern_mask_feather,
        apply_horizontal=_apply_render_pattern_mask_feather,
    ),
    RowKind.RENDER_PATTERN_MASK_INVERT: RowFieldDef(
        panel_label="invert",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_pattern_mask_invert,
        apply_horizontal=_apply_render_pattern_mask_invert,
    ),
    RowKind.RENDER_PATTERN_MASK_TRANSITION: RowFieldDef(
        panel_label="transition",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_pattern_mask_transition,
        apply_horizontal=_apply_render_pattern_mask_transition,
    ),
    RowKind.RENDER_PATTERN_MASK_SEED: RowFieldDef(
        panel_label="seed",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_pattern_mask_seed,
        apply_horizontal=_apply_render_pattern_mask_seed,
    ),
    RowKind.RENDER_TIMELINE_HEADER: RowFieldDef(
        panel_label="TIMELINE",
        present_style=RowPresentStyle.COMPOSITE_HEADER,
        header_prefix="Render: ",
        header_suffix="TIMELINE",
        apply_horizontal=_apply_render_timeline_header,
        fit_strategy=FitStrategy.NONE,
        visibility_icon=_visibility_timeline,
    ),
    RowKind.CONFIG_HEADER: RowFieldDef(
        panel_label="",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_config_header,
        fit_strategy=FitStrategy.PATH,
        shows_enter_icon=True,
    ),
    RowKind.TRACK_PRESET_DIR: RowFieldDef(
        panel_label="preset directory",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_track_preset_dir,
        apply_horizontal=_apply_track_preset_dir,
    ),
    RowKind.TRACK_PRESET: RowFieldDef(
        panel_label="preset",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_track_preset,
        apply_horizontal=_apply_track_preset,
    ),
    RowKind.TRANSPORT: RowFieldDef(
        panel_label="",
        present_style=RowPresentStyle.FULL_LINE,
        format_value=_format_transport,
        apply_horizontal=_apply_transport,
    ),
    RowKind.LAYER_MANAGEMENT_ADD: RowFieldDef(
        panel_label="Add Layer",
        present_style=RowPresentStyle.FULL_LINE,
    ),
    RowKind.LAYER_MANAGEMENT_DELETE: RowFieldDef(
        panel_label="Delete Layer",
        present_style=RowPresentStyle.FULL_LINE,
    ),
    RowKind.TIMELINE_PRESETS_HEADER: RowFieldDef(
        panel_label="timeline preset",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.TIMELINE_PRESET_CHARACTER: RowFieldDef(
        panel_label="character",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_character,
        apply_horizontal=_apply_timeline_preset_character,
    ),
    RowKind.TIMELINE_PRESET_DENSITY: RowFieldDef(
        panel_label="density",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_density,
        apply_horizontal=_apply_timeline_preset_density,
    ),
    RowKind.TIMELINE_PRESET_CUE_SNAP: RowFieldDef(
        panel_label="cue snap",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_cue_snap,
        apply_horizontal=_apply_timeline_preset_cue_snap,
    ),
    RowKind.TIMELINE_PRESET_SONG_MARKER_SNAP: RowFieldDef(
        panel_label="song marker snap",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_song_marker_snap,
        apply_horizontal=_apply_timeline_preset_song_marker_snap,
    ),
    RowKind.TIMELINE_PRESET_TIMELINE_CUTS: RowFieldDef(
        panel_label="timeline cuts",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_timeline_cuts,
        apply_horizontal=_apply_timeline_preset_timeline_cuts,
    ),
    RowKind.TIMELINE_PRESET_REPOPULATE: RowFieldDef(
        panel_label="re-populate preset lists",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_repopulate,
        apply_horizontal=_apply_timeline_preset_repopulate,
    ),
    RowKind.TIMELINE_PRESET_CONDUCTOR: RowFieldDef(
        panel_label="conductor",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_conductor,
        apply_horizontal=_apply_timeline_preset_conductor,
    ),
    RowKind.TIMELINE_PRESET_MODE: RowFieldDef(
        panel_label="mode",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_preset_mode,
        apply_horizontal=_apply_timeline_preset_mode,
    ),
    RowKind.TIMELINE_PRESETS: RowFieldDef(
        panel_label="apply timeline preset",
        present_style=RowPresentStyle.FULL_LINE,
    ),
    RowKind.TIMELINE_VISUAL_LIMITER_HEADER: RowFieldDef(
        panel_label="visual limiter",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.TIMELINE_VISUAL_LIMITER_ENABLED: RowFieldDef(
        panel_label="enabled",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_visual_limiter_enabled,
        apply_horizontal=_apply_visual_limiter_enabled,
    ),
    RowKind.TIMELINE_VISUAL_LIMITER_THRESHOLD: RowFieldDef(
        panel_label="threshold",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_visual_limiter_threshold,
        apply_horizontal=_apply_visual_limiter_threshold,
    ),
    RowKind.TIMELINE_VISUAL_LIMITER_RATIO: RowFieldDef(
        panel_label="ratio",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_visual_limiter_ratio,
        apply_horizontal=_apply_visual_limiter_ratio,
    ),
    RowKind.TIMELINE_VISUAL_LIMITER_RELEASE: RowFieldDef(
        panel_label="release",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_visual_limiter_release,
        apply_horizontal=_apply_visual_limiter_release,
    ),
    RowKind.TIMELINE_RESET: RowFieldDef(
        panel_label="reset timeline",
        present_style=RowPresentStyle.FULL_LINE,
    ),
    RowKind.TIMELINE_BEAT_BAR_GRID_HEADER: RowFieldDef(
        panel_label="beat / bar grid",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.TIMELINE_BAR_PHASE: RowFieldDef(
        panel_label="bar phase",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_bar_phase,
        apply_horizontal=_apply_timeline_bar_phase,
    ),
    RowKind.TIMELINE_BAR_GRID: RowFieldDef(
        panel_label="bar grid",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_bar_grid,
        apply_horizontal=_apply_timeline_bar_grid,
    ),
    RowKind.TIMELINE_PLACEMENT_SNAP: RowFieldDef(
        panel_label="placement snap",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_placement_snap,
        apply_horizontal=_apply_timeline_placement_snap,
    ),
    RowKind.TIMELINE_SNAP_CUES_HEADER: RowFieldDef(
        panel_label="snap cues",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.TIMELINE_SNAP_TO_BEATS: RowFieldDef(
        panel_label="snap to beats",
        present_style=RowPresentStyle.FULL_LINE,
    ),
    RowKind.TIMELINE_SNAP_TO_BARS: RowFieldDef(
        panel_label="snap to bars",
        present_style=RowPresentStyle.FULL_LINE,
    ),
    RowKind.TIMELINE_SNAP_TO_SONG_MARKERS: RowFieldDef(
        panel_label="snap to song markers",
        present_style=RowPresentStyle.FULL_LINE,
    ),
    RowKind.TIMELINE_CUTS_HEADER: RowFieldDef(
        panel_label="timeline cuts",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.TIMELINE_HARD_CUTS: RowFieldDef(
        panel_label="hard cuts",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_hard_cut_fades_enabled,
        apply_horizontal=_apply_timeline_hard_cut_fades_enabled,
    ),
    RowKind.TIMELINE_HARD_CUT_FADE_IN: RowFieldDef(
        panel_label="fade in duration",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_hard_cut_fade_in,
        apply_horizontal=_apply_timeline_hard_cut_fade_in,
    ),
    RowKind.TIMELINE_HARD_CUT_FADE_OUT: RowFieldDef(
        panel_label="fade out duration",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_hard_cut_fade_out,
        apply_horizontal=_apply_timeline_hard_cut_fade_out,
    ),
    RowKind.TIMELINE_HARD_CUT_CROSSFADE: RowFieldDef(
        panel_label="crossfade",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_hard_cut_crossfade,
        apply_horizontal=_apply_timeline_hard_cut_crossfade,
    ),
    RowKind.TIMELINE_SOFT_CUTS: RowFieldDef(
        panel_label="soft cuts",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_soft_cut_fades_enabled,
        apply_horizontal=_apply_timeline_soft_cut_fades_enabled,
    ),
    RowKind.TIMELINE_SOFT_CUT_FADE_IN: RowFieldDef(
        panel_label="fade in duration",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_soft_cut_fade_in,
        apply_horizontal=_apply_timeline_soft_cut_fade_in,
    ),
    RowKind.TIMELINE_SOFT_CUT_FADE_OUT: RowFieldDef(
        panel_label="fade out duration",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_soft_cut_fade_out,
        apply_horizontal=_apply_timeline_soft_cut_fade_out,
    ),
    RowKind.TIMELINE_SOFT_CUT_CROSSFADE: RowFieldDef(
        panel_label="crossfade",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_soft_cut_crossfade,
        apply_horizontal=_apply_timeline_soft_cut_crossfade,
    ),
    RowKind.TIMELINE_APPLY_SOFT_CUTS: RowFieldDef(
        panel_label="apply soft cuts to cues",
        present_style=RowPresentStyle.FULL_LINE,
    ),
    RowKind.TIMELINE_APPLY_HARD_CUTS: RowFieldDef(
        panel_label="apply hard cuts to cues",
        present_style=RowPresentStyle.FULL_LINE,
    ),
    RowKind.SONG_MARKERS_HEADER: RowFieldDef(
        panel_label="song markers",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        format_value=_format_song_markers_count,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.SONG_MARKER_ITEM: RowFieldDef(
        panel_label="",
        present_style=RowPresentStyle.FULL_LINE,
        format_value=_format_song_marker_item,
        apply_horizontal=_apply_song_marker_type,
    ),
    RowKind.PANEL_NOTIFICATION: RowFieldDef(
        panel_label="",
        present_style=RowPresentStyle.NOTIFICATION,
        format_value=_format_panel_notification,
    ),
    RowKind.RENDER_SECTION_GAP: RowFieldDef(
        panel_label="",
        present_style=RowPresentStyle.SPACER,
        fit_strategy=FitStrategy.NONE,
    ),
    RowKind.TRACK_EFFECT: RowFieldDef(
        panel_label="",
        present_style=RowPresentStyle.DYNAMIC,
        format_value=_format_track_effect,
        apply_horizontal=_apply_track_effect,
    ),
}

_COUNTER_LABEL_KINDS = frozenset(
    {
        RowKind.RENDER_OVERLAY_CARD_TITLE_FONT,
        RowKind.RENDER_OVERLAY_CARD_BODY_FONT,
    }
)
_NONE_FIT_STYLES = frozenset(
    {
        RowPresentStyle.COMPOSITE_HEADER,
        RowPresentStyle.EXPAND_SUBHEADER,
        RowPresentStyle.TRACK_HEADER,
        RowPresentStyle.SPACER,
    }
)


def _finalize_row_fields(
    fields: dict[RowKind, RowFieldDef],
) -> dict[RowKind, RowFieldDef]:
    finalized: dict[RowKind, RowFieldDef] = {}
    for kind, field in fields.items():
        updates: dict[str, object] = {}
        if kind in ACTION_ROW_KINDS or kind == RowKind.SETTINGS_EDITOR_MODE:
            updates["shows_enter_icon"] = True
        if field.fit_strategy == FitStrategy.PLAIN:
            if field.present_style in _NONE_FIT_STYLES:
                updates["fit_strategy"] = FitStrategy.NONE
            elif field.present_style == RowPresentStyle.PATH_ICON:
                updates["fit_strategy"] = FitStrategy.COUNTER_LABEL
            elif kind in _COUNTER_LABEL_KINDS:
                updates["fit_strategy"] = FitStrategy.COUNTER_LABEL
            elif (
                field.present_style == RowPresentStyle.FULL_LINE
                and row_behavior(kind).affordance == RowAffordance.ACTION
            ):
                updates["fit_strategy"] = FitStrategy.NONE
        if updates:
            field = replace(field, **updates)
        finalized[kind] = field
    return finalized


ROW_FIELDS = _finalize_row_fields(ROW_FIELDS)


def row_field_def(kind: RowKind) -> RowFieldDef:
    field = ROW_FIELDS.get(kind)
    assert field is not None, f"no RowFieldDef for {kind!r}"
    return field


def row_panel_label(kind: RowKind, desc: RowDescriptor | None = None) -> str:
    if desc is not None:
        overlay_label = overlay_card_panel_label(kind, desc.card)
        if overlay_label is not None:
            return overlay_label
    return row_field_def(kind).panel_label


def format_row_value(state: TuningViewState, desc: RowDescriptor) -> str:
    field = row_field_def(desc.kind)
    assert field.format_value is not None, f"no format_value for {desc.kind!r}"
    return field.format_value(state, desc)


def labeled_row_prefix(kind: RowKind, desc: RowDescriptor | None = None) -> str:
    depth = row_tree_indent_depth(kind)
    return tree_branch_prefix(depth) + row_panel_label(kind, desc) + ": "


def row_labeled_display_text(state: TuningViewState, desc: RowDescriptor) -> str:
    return labeled_row_prefix(desc.kind, desc) + format_row_value(state, desc)


def row_action_parameter_display_text(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return labeled_row_prefix(desc.kind, desc) + format_row_value(state, desc)


def expand_subheader_prefix(
    kind: RowKind, desc: RowDescriptor | None = None
) -> str:
    depth = row_tree_indent_depth(kind)
    field = row_field_def(kind)
    label = tree_branch_prefix(depth) + row_panel_label(kind, desc)
    if field.format_value is not None:
        # Status/value before the expand arrow uses labeled "label: value" form.
        # Parenthetical suffixes (e.g. song markers "(N)") keep a space.
        return label
    return label + " "


def format_expand_subheader_value(state: TuningViewState, desc: RowDescriptor) -> str:
    arrow = expand_arrow_for_header(state, desc.kind, desc.slot, card=desc.card)
    field = row_field_def(desc.kind)
    if field.format_value is not None:
        suffix = field.format_value(state, desc)
        if suffix:
            if suffix.startswith("("):
                return f" {suffix} {arrow}"
            return f": {suffix} {arrow}"
    return arrow


def row_expand_subheader_display_text(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return expand_subheader_prefix(desc.kind, desc) + format_expand_subheader_value(
        state, desc
    )


def _track_header_layer_prefix(state: TuningViewState, slot: str) -> str:
    layer_num = state.layer_z_order.index(slot) + 1
    return f"Layer {layer_num}: "


def composite_header_prefix_part(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    field = row_field_def(desc.kind)
    if field.present_style == RowPresentStyle.TRACK_HEADER:
        assert desc.slot is not None
        return _track_header_layer_prefix(state, desc.slot)
    if desc.kind == RowKind.SETTINGS_HEADER:
        return f"{field.panel_label} "
    if field.header_prefix is not None:
        return field.header_prefix
    return f"{field.panel_label} "


def composite_header_suffix_part(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    field = row_field_def(desc.kind)
    if desc.kind == RowKind.SETTINGS_HEADER:
        return ""
    if field.present_style == RowPresentStyle.TRACK_HEADER:
        assert desc.slot is not None
        return stem_overlay_header(state.tracks[desc.slot].runtime.stem)
    assert field.header_suffix is not None
    return field.header_suffix


def format_composite_header_expand_value(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    if desc.kind == RowKind.RENDER_TIMELINE_HEADER:
        return expand_arrow_glyph(state.render_timeline.expanded)
    return expand_arrow_for_header(state, desc.kind, desc.slot, card=desc.card)


def row_composite_header_display_text(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    body = (composite_header_prefix_part(state, desc) + composite_header_suffix_part(
        state, desc
    )).rstrip()
    arrow = format_composite_header_expand_value(state, desc)
    return f"{body} {arrow}"


def row_kinds_requiring_fields() -> frozenset[RowKind]:
    return frozenset(RowKind)


def row_dynamic_panel_label(desc: RowDescriptor) -> str:
    assert desc.kind == RowKind.TRACK_EFFECT
    assert desc.effect_id is not None and desc.driver_slug is not None
    return f"{desc.effect_id} ({desc.driver_slug})"


def _full_line_branch_depth(kind: RowKind) -> int:
    if kind == RowKind.LAYER_MANAGEMENT_DELETE:
        return 1
    return row_tree_indent_depth(kind)


def full_line_prefix(kind: RowKind) -> str:
    return tree_branch_prefix(_full_line_branch_depth(kind)) + row_panel_label(kind)


def row_full_line_display_text(state: TuningViewState, desc: RowDescriptor) -> str:
    field = row_field_def(desc.kind)
    if field.present_style == RowPresentStyle.NOTIFICATION:
        assert field.format_value is not None
        return field.format_value(state, desc)
    if desc.kind == RowKind.TRANSPORT:
        return ""
    if field.format_value is not None:
        return (
            tree_branch_prefix(_full_line_branch_depth(desc.kind))
            + field.format_value(state, desc)
        )
    return full_line_prefix(desc.kind)


def row_dynamic_labeled_prefix(desc: RowDescriptor) -> str:
    depth = row_tree_indent_depth(desc.kind)
    return tree_branch_prefix(depth) + row_dynamic_panel_label(desc) + ": "


def row_dynamic_labeled_display_text(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return row_dynamic_labeled_prefix(desc) + format_row_value(state, desc)


def apply_field_horizontal(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    shift: bool = False,
) -> bool:
    field = ROW_FIELDS.get(desc.kind)
    if field is None or field.apply_horizontal is None:
        return False
    field.apply_horizontal(controls, desc, forward, ctrl, shift)
    return True
