"""Panel field manifest for the live tuning overlay.

Single source for panel labels, value formatting, tree branch chrome, and
Left/Right mutations. Structure (nesting, expand/collapse) stays in
row_sections.py; affordance and help stay in row_semantics.py.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

from cleave.config_schema import (
    TIMELINE_FADE_DURATION_STEP,
    clamp_timeline_fade_duration,
    cycle_timeline_fades_apply_to,
    hard_cut_enabled_display,
    preset_start_clean_display,
    preset_switching_display,
    preset_switching_shuffle_display,
    timeline_fades_apply_to_label,
    ui_fade_display,
)
from cleave.extract import stem_control_label, stem_overlay_header
from cleave.song_markers import format_marker_time
from cleave.viz.fonts import render_overlay_font_display
from cleave.viz.row_sections import (
    apply_expand_toggle,
    apply_panel_anchor_toggle,
    expand_arrow_for_header,
    expand_arrow_glyph,
    row_tree_indent_depth,
)
from cleave.viz.row_semantics import RowDescriptor, RowKind, row_behavior
from cleave.viz.tuning_view_state import TrackBlock, TuningViewState
from cleave.viz.timeline_snap_controls import (
    cycle_song_marker_snap_scope,
    song_marker_snap_scope_label,
)

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls


class RowPresentStyle(Enum):
    LABELED_VALUE = auto()
    ACTION_PARAMETER = auto()
    EXPAND_SUBHEADER = auto()
    ACTION_EXPAND_SUBHEADER = auto()
    COMPOSITE_HEADER = auto()
    PATH_ICON = auto()
    FULL_LINE = auto()
    DYNAMIC = auto()


FieldMutator = Callable[["TuningControls", RowDescriptor, bool, bool, bool], None]


@dataclass(frozen=True)
class RowFieldDef:
    panel_label: str
    present_style: RowPresentStyle
    format_value: Callable[[TuningViewState, RowDescriptor], str] | None = None
    apply_horizontal: FieldMutator | None = None
    header_prefix: str | None = None
    header_suffix: str | None = None


def tree_branch_prefix(depth: int) -> str:
    """Branch glyph for tree depth; pixel indent comes from row_tree_indent_depth."""
    if depth <= 0:
        return ""
    return " " * (2 * (depth - 1)) + "└─ "


def _format_settings_preview_quality(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.settings.preview_quality


def _format_settings_editor_mode(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    from cleave.viz.session import EDITOR_MODE_PANEL_LABELS

    label = EDITOR_MODE_PANEL_LABELS[state.settings.editor_mode_selection]  # type: ignore[index]
    if state.settings.editor_mode_selection != state.settings.editor_mode:
        return f"{label} [Enter to confirm]"
    return label


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
    controls._timeline_phase.nudge(forward=forward)


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


_SONG_MARKER_SNAP_PROXIMITY_MIN = 0.5
_SONG_MARKER_SNAP_PROXIMITY_MAX = 30.0
_SONG_MARKER_SNAP_PROXIMITY_STEP = 0.5


def _format_timeline_snap_marker_proximity(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_timeline.song_marker_snap_proximity:.1f}s"


def _apply_timeline_snap_marker_proximity(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    tl = controls.session.timeline
    delta = _SONG_MARKER_SNAP_PROXIMITY_STEP if forward else -_SONG_MARKER_SNAP_PROXIMITY_STEP
    tl.song_marker_snap_proximity = max(
        _SONG_MARKER_SNAP_PROXIMITY_MIN,
        min(
            _SONG_MARKER_SNAP_PROXIMITY_MAX,
            round(tl.song_marker_snap_proximity + delta, 1),
        ),
    )


def _format_timeline_snap_marker_scope(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return song_marker_snap_scope_label(
        state.render_timeline.song_marker_snap_scope,
        state.layer_z_order,
    )


def _apply_timeline_snap_marker_scope(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    tl = controls.session.timeline
    tl.song_marker_snap_scope = cycle_song_marker_snap_scope(
        tl.song_marker_snap_scope,
        controls.session.layer_z_order,
        forward=forward,
    )


def _format_timeline_fades_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return hard_cut_enabled_display(state.render_timeline.fades_enabled)


def _apply_timeline_fades_enabled(
    controls: TuningControls,
    _desc: RowDescriptor,
    _forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    tl = controls.session.timeline
    tl.fades_enabled = not tl.fades_enabled


def _format_timeline_fade_in(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_timeline.fade_in:.1f}s"


def _apply_timeline_fade_in(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    tl = controls.session.timeline
    delta = TIMELINE_FADE_DURATION_STEP if forward else -TIMELINE_FADE_DURATION_STEP
    tl.fade_in = clamp_timeline_fade_duration(round(tl.fade_in + delta, 1))


def _format_timeline_fade_out(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_timeline.fade_out:.1f}s"


def _apply_timeline_fade_out(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    tl = controls.session.timeline
    delta = TIMELINE_FADE_DURATION_STEP if forward else -TIMELINE_FADE_DURATION_STEP
    tl.fade_out = clamp_timeline_fade_duration(round(tl.fade_out + delta, 1))


def _format_timeline_fades_apply_to(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return timeline_fades_apply_to_label(state.render_timeline.fades_apply_to)


def _apply_timeline_fades_apply_to(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    tl = controls.session.timeline
    tl.fades_apply_to = cycle_timeline_fades_apply_to(
        tl.fades_apply_to,
        forward=forward,
    )


def _apply_settings_editor_mode(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls._editor_mode.cycle_editor_mode_selection(forward=forward)


def _apply_settings_preview_quality(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls._settings.cycle_preview_quality(forward=forward)
    controls._apply_preview_resolutions()


def _apply_settings_ui_width_mode(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls._settings.cycle_ui_width_mode(forward=forward)


def _apply_settings_ui_width(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    controls._settings.adjust_ui_width(forward=forward, ctrl=ctrl)


def _apply_settings_ui_fade(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    controls._settings.adjust_ui_fade(forward=forward, ctrl=ctrl)


def _track_block(state: TuningViewState, desc: RowDescriptor) -> TrackBlock:
    assert desc.slot is not None
    return state.tracks[desc.slot]


def _format_track_stem(state: TuningViewState, desc: RowDescriptor) -> str:
    return stem_control_label(_track_block(state, desc).stem)


def _format_track_blend(state: TuningViewState, desc: RowDescriptor) -> str:
    return _track_block(state, desc).blend_mode


def _format_track_opacity(state: TuningViewState, desc: RowDescriptor) -> str:
    return f"{_track_block(state, desc).opacity_pct}%"


def _format_track_beat(state: TuningViewState, desc: RowDescriptor) -> str:
    return f"{_track_block(state, desc).beat_sensitivity:.2f}"


def _format_track_preset_switching_mode(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return preset_switching_display(_track_block(state, desc).preset_switching)


def _format_track_preset_switching_scope(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return _track_block(state, desc).preset_switching_scope


def _format_track_preset_duration(state: TuningViewState, desc: RowDescriptor) -> str:
    return f"{_track_block(state, desc).preset_duration:g}s"


def _format_track_soft_cut_duration(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_track_block(state, desc).soft_cut_duration:g}s"


def _format_track_easter_egg(state: TuningViewState, desc: RowDescriptor) -> str:
    return f"{_track_block(state, desc).easter_egg:.2f}"


def _format_track_preset_start_clean(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return preset_start_clean_display(_track_block(state, desc).preset_start_clean)


def _format_track_preset_switching_shuffle(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return preset_switching_shuffle_display(
        _track_block(state, desc).preset_switching_shuffle
    )


def _format_track_hard_cut_enabled(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return hard_cut_enabled_display(_track_block(state, desc).hard_cut_enabled)


def _format_track_hard_cut_duration(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_track_block(state, desc).hard_cut_duration:g}s"


def _format_track_hard_cut_sensitivity(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return f"{_track_block(state, desc).hard_cut_sensitivity:.2f}"


def _format_render_overlay_position(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.render_overlay.position


def _format_render_overlay_title_font_size(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_overlay.title_font_size}px"


def _format_render_overlay_title_font(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return render_overlay_font_display(state.render_overlay.title_font)


def _format_render_overlay_title_margin_bottom(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_overlay.title_margin_bottom}px"


def _format_render_overlay_body_font_size(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_overlay.body_font_size}px"


def _format_render_overlay_body_font(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return render_overlay_font_display(state.render_overlay.body_font)


def _format_render_overlay_opacity(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_overlay.opacity_pct}%"


def _format_render_overlay_border_width(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_overlay.border_width}px"


def _format_render_overlay_start_delay(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_overlay.start_delay:.1f}s"


def _format_render_overlay_display_time(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.render_overlay.display_time:.1f}s"


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
    controls._cycle_stem(desc.slot, forward=forward)


def _apply_track_blend(
    controls: TuningControls, desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls._cycle_blend(desc.slot, forward=forward)


def _apply_track_opacity(
    controls: TuningControls, desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    step = 10 if ctrl else 1
    delta = step if forward else -step
    controls._set_opacity(
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
    controls._set_beat(
        desc.slot, controls.session.layers[desc.slot].beat_sensitivity + delta
    )


def _apply_track_preset_switching_mode(
    controls: TuningControls, desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls._cycle_preset_switching(desc.slot, forward=forward)


def _apply_track_preset_switching_scope(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls._cycle_preset_switching_scope(desc.slot, forward=forward)


def _apply_track_preset_duration(
    controls: TuningControls, desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls._step_preset_duration(desc.slot, forward=forward, ctrl=ctrl)


def _apply_track_soft_cut_duration(
    controls: TuningControls, desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls._step_soft_cut_duration(desc.slot, forward=forward, ctrl=ctrl)


def _apply_track_easter_egg(
    controls: TuningControls, desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls._step_easter_egg(desc.slot, forward=forward, ctrl=ctrl)


def _apply_track_preset_start_clean(
    controls: TuningControls, desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls._cycle_preset_start_clean(desc.slot, forward=forward)


def _apply_track_preset_switching_shuffle(
    controls: TuningControls, desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls._cycle_preset_switching_shuffle(desc.slot, forward=forward)


def _apply_track_hard_cut_enabled(
    controls: TuningControls, desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls._cycle_hard_cut_enabled(desc.slot, forward=forward)


def _apply_track_hard_cut_duration(
    controls: TuningControls, desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    controls._step_hard_cut_duration(desc.slot, forward=forward, ctrl=ctrl)


def _apply_track_hard_cut_sensitivity(
    controls: TuningControls, desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    if desc.slot is None:
        return
    step = 0.1 if ctrl else 0.01
    delta = step if forward else -step
    controls._set_hard_cut_sensitivity(
        desc.slot, controls.session.layers[desc.slot].hard_cut_sensitivity + delta
    )


def _apply_render_overlay_position(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls._render_overlay.cycle_position(forward=forward)


def _apply_render_overlay_title_font_size(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    controls._render_overlay.set_title_font_size(
        controls.session.render_overlay.title_font_size + delta
    )


def _apply_render_overlay_title_font(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls._render_overlay.cycle_title_font(forward=forward)


def _apply_render_overlay_title_margin_bottom(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    controls._render_overlay.set_title_margin_bottom(
        controls.session.render_overlay.title_margin_bottom + delta
    )


def _apply_render_overlay_body_font_size(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    controls._render_overlay.set_body_font_size(
        controls.session.render_overlay.body_font_size + delta
    )


def _apply_render_overlay_body_font(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls._render_overlay.cycle_body_font(forward=forward)


def _apply_render_overlay_opacity(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    controls._render_overlay.set_opacity(
        controls.session.render_overlay.opacity_pct + delta
    )


def _apply_render_overlay_border_width(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    controls._render_overlay.set_border_width(
        controls.session.render_overlay.border_width + delta
    )


def _apply_render_overlay_start_delay(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 30.0 if ctrl else 1.0
    delta = step if forward else -step
    controls._render_overlay.set_start_delay(
        controls.session.render_overlay.start_delay + delta
    )


def _apply_render_overlay_display_time(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 30.0 if ctrl else 1.0
    delta = step if forward else -step
    controls._render_overlay.set_display_time(
        controls.session.render_overlay.display_time + delta
    )


def _apply_render_post_fx_fade_in(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10.0 if ctrl else 1.0
    delta = step if forward else -step
    controls._render_post_fx.set_fade_in(
        controls.session.render_post_fx.fade_in + delta
    )


def _apply_render_post_fx_fade_out(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10.0 if ctrl else 1.0
    delta = step if forward else -step
    controls._render_post_fx.set_fade_out(
        controls.session.render_post_fx.fade_out + delta
    )


def _apply_render_post_fx_highlight_rolloff_mode(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls._render_post_fx.cycle_highlight_rolloff_mode(forward=forward)


def _apply_render_post_fx_highlight_rolloff_curve(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls._render_post_fx.cycle_highlight_rolloff_curve(forward=forward)


def _apply_render_post_fx_highlight_rolloff_threshold(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    hr = controls.session.render_post_fx.highlight_rolloff
    controls._render_post_fx.set_highlight_rolloff_threshold_pct(
        hr.threshold_pct + delta
    )


def _apply_render_post_fx_highlight_rolloff_ceiling(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    hr = controls.session.render_post_fx.highlight_rolloff
    controls._render_post_fx.set_highlight_rolloff_ceiling_pct(
        hr.ceiling_pct + delta
    )


def _apply_render_post_fx_highlight_rolloff_strength(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    hr = controls.session.render_post_fx.highlight_rolloff
    controls._render_post_fx.set_highlight_rolloff_strength_pct(
        hr.strength_pct + delta
    )


def _apply_render_post_fx_highlight_rolloff_softness(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    hr = controls.session.render_post_fx.highlight_rolloff
    controls._render_post_fx.set_highlight_rolloff_softness_pct(
        hr.softness_pct + delta
    )


def _apply_render_post_fx_highlight_rolloff_desaturation(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    hr = controls.session.render_post_fx.highlight_rolloff
    controls._render_post_fx.set_highlight_rolloff_desaturation_pct(
        hr.desaturation_pct + delta
    )


def _apply_render_post_fx_chroma_boost_mode(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls._render_post_fx.cycle_chroma_boost_mode(forward=forward)


def _apply_render_post_fx_chroma_boost_variant(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, _ctrl: bool,
    _shift: bool,
) -> None:
    controls._render_post_fx.cycle_chroma_boost_variant(forward=forward)


def _apply_render_post_fx_chroma_boost_amount(
    controls: TuningControls, _desc: RowDescriptor, forward: bool, ctrl: bool,
    _shift: bool,
) -> None:
    step = 10 if ctrl else 1
    delta = step if forward else -step
    cb = controls.session.render_post_fx.chroma_boost
    controls._render_post_fx.set_chroma_boost_amount_pct(cb.amount_pct + delta)


def _apply_expand_subheader(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    apply_expand_toggle(controls, desc.kind, desc.slot, forward)


def _apply_settings_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    apply_expand_toggle(controls, desc.kind, desc.slot, forward)


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
            controls._enter_solo(slot)
        else:
            controls._exit_solo(slot)
        return
    if ctrl:
        if (
            controls.session.layers[slot].locked
            and row_behavior(desc.kind).can_enable_disable
        ):
            return
        controls._set_enabled(slot, forward)
        return
    apply_expand_toggle(controls, desc.kind, slot, forward)


def _apply_render_overlay_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    shift: bool,
) -> None:
    if shift:
        if forward:
            controls._render_overlay.enter_solo()
        else:
            controls._render_overlay.exit_solo()
        return
    if ctrl:
        if (
            controls.session.render_overlay.locked
            and row_behavior(desc.kind).can_enable_disable
        ):
            return
        controls._render_overlay.set_enabled(forward)
        return
    apply_expand_toggle(controls, desc.kind, desc.slot, forward)


def _apply_render_post_fx_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    shift: bool,
) -> None:
    if shift:
        if forward:
            controls._render_post_fx.enter_solo()
        else:
            controls._render_post_fx.exit_solo()
        return
    if ctrl:
        if (
            controls.session.render_post_fx.locked
            and row_behavior(desc.kind).can_enable_disable
        ):
            return
        controls._render_post_fx.set_enabled(forward)
        return
    apply_expand_toggle(controls, desc.kind, desc.slot, forward)


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
        controls._set_render_timeline_enabled(forward)
        return
    apply_panel_anchor_toggle(controls, desc.kind, forward)


def _format_config_header(state: TuningViewState, _desc: RowDescriptor) -> str:
    return state.active_config_label


def _format_track_preset_dir(state: TuningViewState, desc: RowDescriptor) -> str:
    return _track_block(state, desc).preset_dir_label


def _format_track_preset(state: TuningViewState, desc: RowDescriptor) -> str:
    return _track_block(state, desc).preset_label


def _format_track_user_preset_item(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    assert desc.preset_index is not None
    block = _track_block(state, desc)
    return block.user_preset_labels[desc.preset_index]


def _format_song_markers_count(state: TuningViewState, _desc: RowDescriptor) -> str:
    return f"({len(state.render_timeline.song_marker_times)})"


def _format_song_marker_item(state: TuningViewState, desc: RowDescriptor) -> str:
    assert desc.marker_index is not None
    times = state.render_timeline.song_marker_times
    return f"[{format_marker_time(times[desc.marker_index])}]"


def _format_transport(_state: TuningViewState, _desc: RowDescriptor) -> str:
    return ""


def _format_panel_notification(state: TuningViewState, _desc: RowDescriptor) -> str:
    return state.notification_message or ""


def _format_track_effect(state: TuningViewState, desc: RowDescriptor) -> str:
    assert desc.effect_id is not None and desc.driver_slug is not None
    pct = _track_block(state, desc).effects.get(desc.effect_id, {}).get(
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
            controls._enter_directory(slot)
        else:
            controls._parent_directory(slot)
        return
    controls._step_directory(slot, forward=forward)


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
    controls._step_preset(slot, forward=forward, ctrl=ctrl)


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
    controls._set_effect(slot, effect_id, driver_slug, current + delta)


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
    controls._do_seek(delta_sec)


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
    RowKind.TRACK_HEADER: RowFieldDef(
        panel_label="Layer",
        present_style=RowPresentStyle.COMPOSITE_HEADER,
        apply_horizontal=_apply_track_header,
    ),
    RowKind.TRACK_PRESET_SWITCHING: RowFieldDef(
        panel_label="preset switching",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
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
    RowKind.TRACK_PRESET_SWITCHING_MODE: RowFieldDef(
        panel_label="switching mode",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_preset_switching_mode,
        apply_horizontal=_apply_track_preset_switching_mode,
    ),
    RowKind.TRACK_USER_PRESETS: RowFieldDef(
        panel_label="user presets",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.TRACK_USER_PRESET_ITEM: RowFieldDef(
        panel_label="preset",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_track_user_preset_item,
        apply_horizontal=_noop_horizontal,
    ),
    RowKind.TRACK_USER_PRESET_ADD: RowFieldDef(
        panel_label="Add Current Preset",
        present_style=RowPresentStyle.FULL_LINE,
        apply_horizontal=_noop_horizontal,
    ),
    RowKind.TRACK_PRESET_SWITCHING_SCOPE: RowFieldDef(
        panel_label="scope",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_preset_switching_scope,
        apply_horizontal=_apply_track_preset_switching_scope,
    ),
    RowKind.TRACK_PRESET_SWITCHING_SHUFFLE: RowFieldDef(
        panel_label="shuffle",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_track_preset_switching_shuffle,
        apply_horizontal=_apply_track_preset_switching_shuffle,
    ),
    RowKind.TRACK_PRESET_DURATION: RowFieldDef(
        panel_label="preset duration",
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
    RowKind.RENDER_OVERLAY_POSITION: RowFieldDef(
        panel_label="position",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_overlay_position,
        apply_horizontal=_apply_render_overlay_position,
    ),
    RowKind.RENDER_OVERLAY_HEADER: RowFieldDef(
        panel_label="OVERLAY",
        present_style=RowPresentStyle.COMPOSITE_HEADER,
        header_prefix="Render: ",
        header_suffix="OVERLAY",
        apply_horizontal=_apply_render_overlay_header,
    ),
    RowKind.RENDER_OVERLAY_TITLE_HEADER: RowFieldDef(
        panel_label="title",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE: RowFieldDef(
        panel_label="font size",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_overlay_title_font_size,
        apply_horizontal=_apply_render_overlay_title_font_size,
    ),
    RowKind.RENDER_OVERLAY_TITLE_FONT: RowFieldDef(
        panel_label="font",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_overlay_title_font,
        apply_horizontal=_apply_render_overlay_title_font,
    ),
    RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM: RowFieldDef(
        panel_label="margin bottom",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_overlay_title_margin_bottom,
        apply_horizontal=_apply_render_overlay_title_margin_bottom,
    ),
    RowKind.RENDER_OVERLAY_BODY_FONT_SIZE: RowFieldDef(
        panel_label="font size",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_overlay_body_font_size,
        apply_horizontal=_apply_render_overlay_body_font_size,
    ),
    RowKind.RENDER_OVERLAY_BODY_FONT: RowFieldDef(
        panel_label="font",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_overlay_body_font,
        apply_horizontal=_apply_render_overlay_body_font,
    ),
    RowKind.RENDER_OVERLAY_BODY_HEADER: RowFieldDef(
        panel_label="body",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.RENDER_OVERLAY_OPACITY: RowFieldDef(
        panel_label="background opacity",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_overlay_opacity,
        apply_horizontal=_apply_render_overlay_opacity,
    ),
    RowKind.RENDER_OVERLAY_BORDER_WIDTH: RowFieldDef(
        panel_label="border width",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_overlay_border_width,
        apply_horizontal=_apply_render_overlay_border_width,
    ),
    RowKind.RENDER_OVERLAY_START_DELAY: RowFieldDef(
        panel_label="start delay",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_overlay_start_delay,
        apply_horizontal=_apply_render_overlay_start_delay,
    ),
    RowKind.RENDER_OVERLAY_DISPLAY_TIME: RowFieldDef(
        panel_label="display time",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_render_overlay_display_time,
        apply_horizontal=_apply_render_overlay_display_time,
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
    RowKind.RENDER_TIMELINE_HEADER: RowFieldDef(
        panel_label="TIMELINE",
        present_style=RowPresentStyle.COMPOSITE_HEADER,
        header_prefix="Render: ",
        header_suffix="TIMELINE",
        apply_horizontal=_apply_render_timeline_header,
    ),
    RowKind.CONFIG_HEADER: RowFieldDef(
        panel_label="",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_config_header,
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
    RowKind.TIMELINE_PRESETS: RowFieldDef(
        panel_label="apply a timeline preset",
        present_style=RowPresentStyle.FULL_LINE,
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
    RowKind.TIMELINE_SNAP_TO_BEATS: RowFieldDef(
        panel_label="snap to beats",
        present_style=RowPresentStyle.FULL_LINE,
    ),
    RowKind.TIMELINE_SNAP_TO_BARS: RowFieldDef(
        panel_label="snap to bars",
        present_style=RowPresentStyle.FULL_LINE,
    ),
    RowKind.TIMELINE_SNAP_MARKER_PROXIMITY: RowFieldDef(
        panel_label="proximity",
        present_style=RowPresentStyle.ACTION_PARAMETER,
        format_value=_format_timeline_snap_marker_proximity,
        apply_horizontal=_apply_timeline_snap_marker_proximity,
    ),
    RowKind.TIMELINE_SNAP_MARKER_SCOPE: RowFieldDef(
        panel_label="layer scope",
        present_style=RowPresentStyle.ACTION_PARAMETER,
        format_value=_format_timeline_snap_marker_scope,
        apply_horizontal=_apply_timeline_snap_marker_scope,
    ),
    RowKind.TIMELINE_SNAP_TO_SONG_MARKERS: RowFieldDef(
        panel_label="snap to song markers",
        present_style=RowPresentStyle.ACTION_EXPAND_SUBHEADER,
        apply_horizontal=_apply_expand_subheader,
    ),
    RowKind.TIMELINE_FADES: RowFieldDef(
        panel_label="timeline fades",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_fades_enabled,
        apply_horizontal=_apply_timeline_fades_enabled,
    ),
    RowKind.TIMELINE_FADE_IN: RowFieldDef(
        panel_label="fade in duration",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_fade_in,
        apply_horizontal=_apply_timeline_fade_in,
    ),
    RowKind.TIMELINE_FADE_OUT: RowFieldDef(
        panel_label="fade out duration",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_fade_out,
        apply_horizontal=_apply_timeline_fade_out,
    ),
    RowKind.TIMELINE_FADES_APPLY_TO: RowFieldDef(
        panel_label="apply to cues",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_timeline_fades_apply_to,
        apply_horizontal=_apply_timeline_fades_apply_to,
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
    ),
    RowKind.PANEL_NOTIFICATION: RowFieldDef(
        panel_label="",
        present_style=RowPresentStyle.FULL_LINE,
        format_value=_format_panel_notification,
    ),
    RowKind.TRACK_EFFECT: RowFieldDef(
        panel_label="",
        present_style=RowPresentStyle.DYNAMIC,
        format_value=_format_track_effect,
        apply_horizontal=_apply_track_effect,
    ),
}


def row_field_def(kind: RowKind) -> RowFieldDef:
    field = ROW_FIELDS.get(kind)
    assert field is not None, f"no RowFieldDef for {kind!r}"
    return field


def row_panel_label(kind: RowKind) -> str:
    return row_field_def(kind).panel_label


def format_row_value(state: TuningViewState, desc: RowDescriptor) -> str:
    field = row_field_def(desc.kind)
    assert field.format_value is not None, f"no format_value for {desc.kind!r}"
    return field.format_value(state, desc)


def labeled_row_prefix(kind: RowKind) -> str:
    depth = row_tree_indent_depth(kind)
    return tree_branch_prefix(depth) + row_panel_label(kind) + ": "


def row_labeled_display_text(state: TuningViewState, desc: RowDescriptor) -> str:
    return labeled_row_prefix(desc.kind) + format_row_value(state, desc)


def row_action_parameter_display_text(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return labeled_row_prefix(desc.kind) + format_row_value(state, desc)


def expand_subheader_prefix(kind: RowKind) -> str:
    depth = row_tree_indent_depth(kind)
    field = row_field_def(kind)
    label = tree_branch_prefix(depth) + row_panel_label(kind)
    if field.format_value is not None:
        # Status/value before the expand arrow uses labeled "label: value" form.
        # Parenthetical suffixes (e.g. song markers "(N)") keep a space.
        return label
    return label + " "


def format_expand_subheader_value(state: TuningViewState, desc: RowDescriptor) -> str:
    arrow = expand_arrow_for_header(state, desc.kind, desc.slot)
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
    return expand_subheader_prefix(desc.kind) + format_expand_subheader_value(
        state, desc
    )


def _track_header_layer_prefix(state: TuningViewState, slot: str) -> str:
    layer_num = state.layer_z_order.index(slot) + 1
    return f"Layer {layer_num}: "


def composite_header_prefix_part(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    field = row_field_def(desc.kind)
    if desc.kind == RowKind.TRACK_HEADER:
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
    if desc.kind == RowKind.TRACK_HEADER:
        assert desc.slot is not None
        return stem_overlay_header(state.tracks[desc.slot].stem)
    assert field.header_suffix is not None
    return field.header_suffix


def format_composite_header_expand_value(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    if desc.kind == RowKind.RENDER_TIMELINE_HEADER:
        return expand_arrow_glyph(state.render_timeline.expanded)
    return expand_arrow_for_header(state, desc.kind, desc.slot)


def row_composite_header_display_text(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    body = (composite_header_prefix_part(state, desc) + composite_header_suffix_part(
        state, desc
    )).rstrip()
    arrow = format_composite_header_expand_value(state, desc)
    return f"{body} {arrow}"


def row_kinds_requiring_fields() -> frozenset[RowKind]:
    return frozenset(k for k in RowKind if k != RowKind.RENDER_SECTION_GAP)


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
    if desc.kind == RowKind.PANEL_NOTIFICATION:
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
