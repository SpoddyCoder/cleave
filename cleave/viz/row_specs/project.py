"""Project header, config path, Compositor, and Render Project row specs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.config_schema.project_render import (
    PROJECT_RENDER_QUALITY_HELP_ENTRIES,
    RENDER_FPS_STEP,
    RENDER_FPS_STEP_LARGE,
    RENDER_SIZE_STEP,
    RENDER_SIZE_STEP_LARGE,
)
from cleave.viz.material_icons import FOLDER_GLYPH
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_sections import apply_expand_toggle
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.row_specs.common import apply_expand_subheader
from cleave.viz.theme import PRESET_ICON
from cleave.viz.tuning_view_state import TuningViewState

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls


def _format_config_header(state: TuningViewState, _desc: RowDescriptor) -> str:
    return state.active_config_label


def _format_project_render_output(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.project.output_label


def _format_project_render_width(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return str(state.project.width)


def _format_project_render_height(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return str(state.project.height)


def _format_project_render_fps(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return str(state.project.fps)


def _format_project_render_quality(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.project.quality


def _format_project_render_start(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.project.start_sec}s"


def _format_project_render_end(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.project.end_sec}s"


def _format_project_render_action(
    _state: TuningViewState, _desc: RowDescriptor
) -> str:
    return "render the project"


def _format_project_milkdrop_beat(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.project.milkdrop_beat_sensitivity:.2f}"


def _format_project_compositor_hdr(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return "on" if state.project.compositor_hdr else "off"


def _apply_project_header(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    apply_expand_toggle(
        controls, desc.kind, desc.slot, forward, card=desc.card
    )


def _apply_project_render_width(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    controls.project.adjust_width(forward=forward, ctrl=ctrl)


def _apply_project_render_height(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    controls.project.adjust_height(forward=forward, ctrl=ctrl)


def _apply_project_render_fps(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    controls.project.adjust_fps(forward=forward, ctrl=ctrl)


def _apply_project_render_quality(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls.project.cycle_quality(forward=forward)


def _apply_project_render_start(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    controls.project.adjust_start(forward=forward, ctrl=ctrl)


def _apply_project_render_end(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    controls.project.adjust_end(forward=forward, ctrl=ctrl)


def _apply_project_milkdrop_beat(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    _shift: bool,
) -> None:
    controls.project.adjust_milkdrop_beat_sensitivity(forward=forward, ctrl=ctrl)


def _apply_project_compositor_hdr(
    controls: TuningControls,
    _desc: RowDescriptor,
    _forward: bool,
    _ctrl: bool,
    _shift: bool,
) -> None:
    controls.project.toggle_compositor_hdr()


SPECS: dict[RowKind, RowSpec] = {
    RowKind.PROJECT_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="Project",
        present_style=RowPresentStyle.COMPOSITE_HEADER,
        apply_horizontal=_apply_project_header,
        header_suffix="",
        fit_strategy=FitStrategy.NONE,
        help_title="Project",
        help_description=("Save the session and render this project to video.",),
        header_glyph=FOLDER_GLYPH,
        header_glyph_color=PRESET_ICON,
        quick_nav_target=True,
        quick_nav_always=True,
        is_header=True,
    ),
    RowKind.CONFIG_HEADER: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_config_header,
        fit_strategy=FitStrategy.PATH,
        shows_enter_icon=True,
        shows_dirty_suffix=True,
        help_title="Save",
        help_description=(
            "Active config file.",
            "Enter or Ctrl+S saves the current session settings.",
        ),
        is_pinned=True,
        parent_group="project",
    ),
    RowKind.PROJECT_MILKDROP_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="ProjectM",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="ProjectM",
        help_description=(
            "Project default for ProjectM beat detection.",
            "Layers without their own beat sensitivity use this value.",
        ),
        is_sub_header=True,
        is_pinned=True,
        parent_group="project",
    ),
    RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="default beat sensitivity",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_project_milkdrop_beat,
        apply_horizontal=_apply_project_milkdrop_beat,
        help_title="Default beat sensitivity",
        help_entries=(
            ("Left/Right", "adjust (0.1)"),
            ("Ctrl + Left/Right", "large step (0.5)"),
        ),
        help_description=(
            "Fallback beat sensitivity for layers that do not set their own.",
            "New layers start at this value.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="project_milkdrop",
    ),
    RowKind.PROJECT_COMPOSITOR_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="Compositor",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="Compositor",
        help_description=(
            "Layer composite format for live play and offline render.",
            "hdr on uses 16-bit float FBOs; off uses 8-bit.",
            "Preset curation always composites in 8-bit.",
        ),
        is_sub_header=True,
        is_pinned=True,
        parent_group="project",
    ),
    RowKind.PROJECT_COMPOSITOR_HDR: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="hdr",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_project_compositor_hdr,
        apply_horizontal=_apply_project_compositor_hdr,
        help_title="hdr",
        help_entries=(("Left/Right", "toggle on/off"),),
        help_description=(
            "16-bit float compositing when on; 8-bit when off.",
            "The HDR display shoulder in frame finish follows this flag.",
            "Changing it resizes compositor attachments immediately.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="project_compositor",
    ),
    RowKind.PROJECT_RENDER_HEADER: RowSpec(
        affordance=RowAffordance.EXPAND,
        panel_label="Render Project",
        present_style=RowPresentStyle.EXPAND_SUBHEADER,
        apply_horizontal=apply_expand_subheader,
        fit_strategy=FitStrategy.NONE,
        help_title="Render Project",
        help_description=(
            "Choose output size, frame rate, quality, and a time range,",
            "then render this project to MP4.",
        ),
        is_sub_header=True,
        is_pinned=True,
        parent_group="project",
    ),
    RowKind.PROJECT_RENDER_OUTPUT: RowSpec(
        affordance=RowAffordance.DISPLAY,
        panel_label="",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_project_render_output,
        fit_strategy=FitStrategy.PATH,
        help_title="Render output",
        help_entries=(("Left/Right", "not editable"),),
        help_description=(
            "Default MP4 path in this project's renders directory.",
            "Not editable.",
        ),
        is_pinned=True,
        parent_group="project_render",
    ),
    RowKind.PROJECT_RENDER_WIDTH: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="width",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_project_render_width,
        apply_horizontal=_apply_project_render_width,
        help_title="Render width",
        help_entries=(
            ("Left/Right", f"adjust width ({RENDER_SIZE_STEP} px)"),
            ("Ctrl + Left/Right", f"large step ({RENDER_SIZE_STEP_LARGE} px)"),
        ),
        help_description=("Offline render output width in pixels.",),
        is_pinned=True,
        repeatable=True,
        parent_group="project_render",
    ),
    RowKind.PROJECT_RENDER_HEIGHT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="height",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_project_render_height,
        apply_horizontal=_apply_project_render_height,
        help_title="Render height",
        help_entries=(
            ("Left/Right", f"adjust height ({RENDER_SIZE_STEP} px)"),
            ("Ctrl + Left/Right", f"large step ({RENDER_SIZE_STEP_LARGE} px)"),
        ),
        help_description=("Offline render output height in pixels.",),
        is_pinned=True,
        repeatable=True,
        parent_group="project_render",
    ),
    RowKind.PROJECT_RENDER_FPS: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="fps",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_project_render_fps,
        apply_horizontal=_apply_project_render_fps,
        help_title="Render fps",
        help_entries=(
            ("Left/Right", f"adjust fps ({RENDER_FPS_STEP})"),
            ("Ctrl + Left/Right", f"large step ({RENDER_FPS_STEP_LARGE})"),
        ),
        help_description=("Offline render output frame rate.",),
        is_pinned=True,
        repeatable=True,
        parent_group="project_render",
    ),
    RowKind.PROJECT_RENDER_QUALITY: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="quality",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_project_render_quality,
        apply_horizontal=_apply_project_render_quality,
        help_title="Render quality",
        help_entries=(("Left/Right", "cycle mode"),),
        help_description=("Encode and layer-resolution trade-off for this render.",),
        help_mode_entries=PROJECT_RENDER_QUALITY_HELP_ENTRIES,
        is_pinned=True,
        repeatable=True,
        parent_group="project_render",
    ),
    RowKind.PROJECT_RENDER_START: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="start",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_project_render_start,
        apply_horizontal=_apply_project_render_start,
        help_title="Render start",
        help_entries=(
            ("Left/Right", "adjust start (1s)"),
            ("Ctrl + Left/Right", "large step (10s)"),
        ),
        help_description=("Segment start in whole seconds.",),
        is_pinned=True,
        repeatable=True,
        parent_group="project_render",
    ),
    RowKind.PROJECT_RENDER_END: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="end",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_project_render_end,
        apply_horizontal=_apply_project_render_end,
        help_title="Render end",
        help_entries=(
            ("Left/Right", "adjust end (1s)"),
            ("Ctrl + Left/Right", "large step (10s)"),
        ),
        help_description=("Segment end in whole seconds.",),
        is_pinned=True,
        repeatable=True,
        parent_group="project_render",
    ),
    RowKind.PROJECT_RENDER_ACTION: RowSpec(
        affordance=RowAffordance.ACTION,
        panel_label="render the project",
        present_style=RowPresentStyle.FULL_LINE,
        format_value=_format_project_render_action,
        shows_enter_icon=True,
        help_title="Render the project",
        help_entries=(("Enter", "confirm render"),),
        help_description=("Write an MP4 using the path, size, fps, quality, and range above.",),
        is_pinned=True,
        parent_group="project_render",
    ),
}
