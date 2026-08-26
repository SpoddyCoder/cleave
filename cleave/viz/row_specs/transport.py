"""Transport, notification, and spacer row specs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.tuning_view_state import TuningViewState

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

def _format_transport(_state: TuningViewState, _desc: RowDescriptor) -> str:
    return ""

def _format_panel_notification(state: TuningViewState, desc: RowDescriptor) -> str:
    if desc.marker_index == 0:
        return state.persistent_notification_message or ""
    return state.notification_message or ""

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

SPECS: dict[RowKind, RowSpec] = {
    RowKind.TRANSPORT: RowSpec(
        affordance=RowAffordance.SEEK,
        panel_label="",
        present_style=RowPresentStyle.FULL_LINE,
        format_value=_format_transport,
        apply_horizontal=_apply_transport,
        help_title="Transport",
        help_description=("Scrubber and play/pause for the project audio.",),
        quick_nav_target=True,
        quick_nav_always=True,
        is_header=True,
        repeatable=True,
    ),
    RowKind.PANEL_NOTIFICATION: RowSpec(
        affordance=RowAffordance.DISPLAY,
        panel_label="",
        present_style=RowPresentStyle.NOTIFICATION,
        format_value=_format_panel_notification,
        navigable=False,
        is_pinned=True,
    ),
    RowKind.RENDER_SECTION_GAP: RowSpec(
        affordance=RowAffordance.DISPLAY,
        panel_label="",
        present_style=RowPresentStyle.SPACER,
        fit_strategy=FitStrategy.NONE,
        navigable=False,
    ),
}
