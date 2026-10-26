"""Spacer row specs."""

from __future__ import annotations

from cleave.viz.row_kinds import RowAffordance, RowKind
from cleave.viz.row_spec import FitStrategy, RowPresentStyle, RowSpec

SPECS: dict[RowKind, RowSpec] = {
    RowKind.RENDER_SECTION_GAP: RowSpec(
        affordance=RowAffordance.DISPLAY,
        panel_label="",
        present_style=RowPresentStyle.SPACER,
        fit_strategy=FitStrategy.NONE,
        navigable=False,
    ),
}
