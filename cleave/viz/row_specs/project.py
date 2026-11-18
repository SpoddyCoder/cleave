"""Project header, ProjectM, compositor, and resolution row specs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.config_schema.project_resolution import (
    RESOLUTION_STEP,
    RESOLUTION_STEP_LARGE,
)
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.row_specs.common import bool_choice
from cleave.viz.tuning_view_state import TuningViewState

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls


def _format_project_resolution_width(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return str(state.project.width)


def _format_project_resolution_height(
    state: TuningViewState, _desc: RowDescriptor
) -> str:
    return str(state.project.height)










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
            "Project-wide projectM defaults.",
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
            "The beat sensitivity for any layer that does not set its own, and the starting value for new layers.",
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
            "The bit depth used when combining layers. Preset curation always uses 8-bit.",
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
            "Composites layers at 16 bits per channel instead of 8, in both the live view and the render, which avoids banding and clipping when many bright layers stack. The output video is 8-bit either way. Also enables a gentle highlight rolloff.",
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
            "The output video's frame size. Renders use it exactly; the live preview matches its aspect ratio.",
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
            "Output width, in pixels.",
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
            "Output height, in pixels.",
        ),
        is_pinned=True,
        repeatable=True,
        parent_group="project_resolution",
    ),
}
