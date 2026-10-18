"""Navigator Enter: inspector groups and leftover headers."""

from __future__ import annotations

from cleave.viz.inspector import build_inspector_rows
from cleave.viz.row_kinds import RowKind
from cleave.viz.shell_focus import ShellRegion
from tests.cleave.viz.test_controls import _make_controls


def test_enter_on_project_builds_inspector_groups() -> None:
    controls = _make_controls(("layer_1",))
    controls.shell_focus.selected_id = "project"
    controls.shell_focus.region = ShellRegion.NAVIGATOR
    controls.navigator.activate()
    assert controls.shell_focus.region is ShellRegion.INSPECTOR
    view = controls.build_view_state(paused=controls.playback.paused)
    rows = build_inspector_rows(view, "project", controls.shell_focus.collapsed)
    groups = tuple(
        row.descriptor.kind for row in rows if row.is_group and row.descriptor is not None
    )
    assert groups == (
        RowKind.PROJECT_MILKDROP_HEADER,
        RowKind.PROJECT_COMPOSITOR_HEADER,
        RowKind.PROJECT_RENDER_HEADER,
    )
    assert controls.shell_focus.inspector_cursor == next(
        row.descriptor for row in rows if row.navigable and row.descriptor is not None
    )


def test_enter_on_render_moves_to_overlays_header() -> None:
    controls = _make_controls(("layer_1",))
    controls.shell_focus.selected_id = "render"
    controls.shell_focus.region = ShellRegion.NAVIGATOR
    controls.navigator.activate()
    assert controls.shell_focus.region is ShellRegion.PANEL
    assert controls.focus_descriptor.kind is RowKind.RENDER_OVERLAYS_HEADER
