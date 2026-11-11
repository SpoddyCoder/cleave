"""Project header, ProjectM, compositor, resolution, and render row specs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.config_schema.project_render import (
    PROJECT_RENDER_QUALITY_HELP_ENTRIES,
    RENDER_FPS_STEP,
    RENDER_FPS_STEP_LARGE,
)
from cleave.config_schema.project_resolution import (
    RESOLUTION_STEP,
    RESOLUTION_STEP_LARGE,
)
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.tuning_view_state import TuningViewState

from cleave.config_schema.project_render import PROJECT_RENDER_QUALITIES
from cleave.viz.row_specs.common import bool_choice, options_choice
if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls


def _format_project_render_output(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return state.project.output_label


def _format_project_resolution_width(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return str(state.project.width)


def _format_project_resolution_height(
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


def _format_project_milkdrop_beat(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return f"{state.project.milkdrop_beat_sensitivity:.2f}"


def _format_project_compositor_hdr(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return "on" if state.project.compositor_hdr else "off"


def _apply_project_resolution_width(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    controls.project.adjust_width(forward=forward, large=large)


def _apply_project_resolution_height(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    controls.project.adjust_height(forward=forward, large=large)


def _apply_project_render_fps(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    controls.project.adjust_fps(forward=forward, large=large)


def _apply_project_render_quality(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    controls.project.step_quality(forward=forward)


def _apply_project_render_start(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    controls.project.adjust_start(forward=forward, large=large)


def _apply_project_render_end(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    controls.project.adjust_end(forward=forward, large=large)


def _apply_project_milkdrop_beat(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> None:
    controls.project.adjust_milkdrop_beat_sensitivity(forward=forward, large=large)


def _apply_project_compositor_hdr(
    controls: TuningControls,
    _desc: RowDescriptor,
    forward: bool,
    _large: bool,
) -> None:
    controls.project.set_compositor_hdr(forward)


SPECS: dict[RowKind, RowSpec] = {
    RowKind.PROJECT_MILKDROP_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="ProjectM",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="ProjectM",
        help_description=(
            "The default beat sensitivity for the project.",
        ),
        is_pinned=True,
        parent_group="project",
    ),
    RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="default beat sensitivity",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_project_milkdrop_beat,
        apply_horizontal=_apply_project_milkdrop_beat,
        help_title="Default Beat Sensitivity",
        help_entries=(
            ("Left/Right", "adjust (0.1)"),
            ("PgUp/PgDn", "large step (0.5)"),
        ),
        help_description=(
            "Layers with no beat sensitivity of their own use this value.",
            "New layers start at this value.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="project_milkdrop",
    ),
    RowKind.PROJECT_COMPOSITOR_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="Compositor",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Compositor",
        help_description=(
            "The colour depth that Cleave uses to combine the layers.",
            "Preset curation always uses 8-bit.",
        ),
        is_pinned=True,
        parent_group="project",
    ),
    RowKind.PROJECT_COMPOSITOR_HDR: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="hdr compositing",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_project_compositor_hdr,
        apply_horizontal=_apply_project_compositor_hdr,
        choice=bool_choice(lambda s, _d: s.project.compositor_hdr),
        help_title="HDR Compositing",
        help_entries=(("Left/Right", "off / on"),),
        help_description=(
            "When on, Cleave combines the layers in 16-bit colour.",
            "When off, it uses 8-bit.",
            "This applies to the live view and to the render.",
            "The video file is 8-bit in both cases.",
            "When on, a light highlight rolloff also runs.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="project_compositor",
    ),
    RowKind.PROJECT_RESOLUTION_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="Resolution",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Resolution",
        help_description=(
            "The width and height of the video, in pixels.",
            "The render uses this size.",
            "The live preview uses its shape.",
        ),
        is_pinned=True,
        parent_group="project",
    ),
    RowKind.PROJECT_RESOLUTION_WIDTH: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="width",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_project_resolution_width,
        apply_horizontal=_apply_project_resolution_width,
        help_title="Resolution Width",
        help_entries=(
            ("Left/Right", f"adjust width ({RESOLUTION_STEP} px)"),
            ("PgUp/PgDn", f"large step ({RESOLUTION_STEP_LARGE} px)"),
        ),
        help_description=(
            "Width of the video, in pixels.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="project_resolution",
    ),
    RowKind.PROJECT_RESOLUTION_HEIGHT: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="height",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_project_resolution_height,
        apply_horizontal=_apply_project_resolution_height,
        help_title="Resolution Height",
        help_entries=(
            ("Left/Right", f"adjust height ({RESOLUTION_STEP} px)"),
            ("PgUp/PgDn", f"large step ({RESOLUTION_STEP_LARGE} px)"),
        ),
        help_description=(
            "Height of the video, in pixels.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="project_resolution",
    ),
    RowKind.PROJECT_RENDER_HEADER: RowSpec(
        affordance=RowAffordance.HEADING,
        panel_label="Render",
        present_style=RowPresentStyle.HEADING,
        fit_strategy=FitStrategy.NONE,
        help_title="Render",
        help_description=(
            "Renders the project to an MP4 video file.",
        ),
        is_pinned=True,
        parent_group="project",
    ),
    RowKind.PROJECT_RENDER_OUTPUT: RowSpec(
        affordance=RowAffordance.DISPLAY,
        panel_label="",
        present_style=RowPresentStyle.PATH_ICON,
        format_value=_format_project_render_output,
        fit_strategy=FitStrategy.PATH,
        help_title="Render Output",
        help_entries=(("Left/Right", "not editable"),),
        help_description=(
            "The MP4 file that the render makes, in the renders directory of the project.",
        ),
        is_pinned=True,
        parent_group="project_render",
    ),
    RowKind.PROJECT_RENDER_FPS: RowSpec(
        affordance=RowAffordance.VALUE_STEP,
        panel_label="fps",
        present_style=RowPresentStyle.LABELED_VALUE,
        format_value=_format_project_render_fps,
        apply_horizontal=_apply_project_render_fps,
        help_title="Render FPS",
        help_entries=(
            ("Left/Right", f"adjust fps ({RENDER_FPS_STEP})"),
            ("PgUp/PgDn", f"large step ({RENDER_FPS_STEP_LARGE})"),
        ),
        help_description=("Frames per second of the rendered video.",),
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
        choice=options_choice(PROJECT_RENDER_QUALITIES, lambda s, _d: s.project.quality),
        help_title="Render Quality",
        help_entries=(("Left/Right", "choose mode"),),
        help_description=("Speed or quality for the render.",),
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
        help_title="Render Start",
        help_entries=(
            ("Left/Right", "adjust start (1s)"),
            ("PgUp/PgDn", "large step (10s)"),
        ),
        help_description=("Time in the song where the render starts, in seconds.",),
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
        help_title="Render End",
        help_entries=(
            ("Left/Right", "adjust end (1s)"),
            ("PgUp/PgDn", "large step (10s)"),
        ),
        help_description=("Time in the song where the render ends, in seconds.",),
        is_pinned=True,
        repeatable=True,
        parent_group="project_render",
    ),
}
