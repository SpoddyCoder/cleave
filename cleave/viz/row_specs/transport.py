"""Notification and spacer row specs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec
from cleave.viz.tuning_view_state import TuningViewState

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

def _format_panel_notification(state: TuningViewState, desc: RowDescriptor) -> str:
    if desc.marker_index == 0:
        return state.persistent_notification_message or ""
    return state.notification_message or ""


def _apply_panel_notification_action(
    controls: TuningControls, desc: RowDescriptor
) -> None:
    if desc.marker_index != 1:
        return
    controls.dismiss_notification()

SPECS: dict[RowKind, RowSpec] = {
    RowKind.PANEL_NOTIFICATION: RowSpec(
        affordance=RowAffordance.DISPLAY,
        panel_label="",
        present_style=RowPresentStyle.NOTIFICATION,
        format_value=_format_panel_notification,
        apply_action=_apply_panel_notification_action,
        help_title="Notification",
        help_description=("Status toast.",),
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
