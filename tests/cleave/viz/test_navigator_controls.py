"""Navigator Enter, selection, and reconcile."""

from __future__ import annotations

from cleave.viz.inspector import build_inspector_rows
from cleave.viz.navigator import layer_node_id, layer_page_node_id
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.shell_focus import ShellRegion
from tests.cleave.viz.test_controls import _make_controls, _make_controls_with_manager


def test_enter_on_project_opens_first_child() -> None:
    controls = _make_controls(("layer_1",))
    focus = controls.shell_focus
    controls.navigator.select("project")
    controls.navigator.activate()
    assert focus.selected_id == "project.projectm"
    assert focus.region is ShellRegion.INSPECTOR
    assert "project" in focus.nav_expanded
    assert focus.inspector_cursor == RowDescriptor(
        RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY
    )


def test_enter_on_settings_opens_first_child() -> None:
    controls = _make_controls(("layer_1",))
    focus = controls.shell_focus
    controls.navigator.select("settings")
    controls.navigator.activate()
    assert focus.selected_id == "settings.editor_window"
    assert focus.region is ShellRegion.INSPECTOR


def test_enter_on_chips_only_page_stays_on_navigator() -> None:
    controls = _make_controls(("layer_1",))
    focus = controls.shell_focus
    for node_id in ("overlay", "post_fx", "timeline"):
        controls.navigator.select(node_id)
        controls.navigator.activate()
        assert focus.selected_id == node_id
        assert focus.region is ShellRegion.NAVIGATOR


def test_enter_on_pages_focuses_first_navigable_row() -> None:
    controls = _make_controls(("layer_1",))
    focus = controls.shell_focus
    view = controls.build_view_state(paused=controls.playback.paused)
    for node_id in (
        "overlay.opening_card",
        "post_fx.fade",
        "pattern_mask",
        "timeline.song_markers",
        layer_page_node_id("layer_1", "compositing"),
    ):
        controls.navigator.select(node_id)
        controls.navigator.activate()
        assert focus.region is ShellRegion.INSPECTOR
        assert focus.selected_id == node_id
        assert focus.inspector_cursor == next(
            row.descriptor
            for row in build_inspector_rows(view, node_id)
            if row.navigable and row.descriptor is not None
        )


def test_enter_on_layers_opens_inspector() -> None:
    controls = _make_controls(("layer_1",))
    controls.navigator.select("layers")
    before = controls.focus_descriptor
    controls.navigator.activate()
    assert controls.shell_focus.region is ShellRegion.INSPECTOR
    assert controls.focus_descriptor == before
    view = controls.build_view_state(paused=controls.playback.paused)
    focus = controls.shell_focus
    rows = build_inspector_rows(
        view, "layers"
    )
    assert [row.descriptor.kind for row in rows if row.descriptor is not None] == [
        RowKind.LAYER_MANAGEMENT_COUNT,
    ]
    assert focus.inspector_command_id == "layers.add"
    assert focus.inspector_cursor is None

    controls.navigator.select(layer_node_id("layer_1"))
    controls.navigator.activate()
    assert controls.shell_focus.region is ShellRegion.INSPECTOR
    assert controls.focus_descriptor == before
    layer_rows = build_inspector_rows(
        view, layer_node_id("layer_1")
    )
    layer_kinds = [
        row.descriptor.kind
        for row in layer_rows
        if row.descriptor is not None
    ]
    assert RowKind.TRACK_HEADER not in layer_kinds
    assert RowKind.TRACK_PRESET in layer_kinds
    assert focus.inspector_cursor == next(
        row.descriptor
        for row in layer_rows
        if row.navigable and row.descriptor is not None
    )


def test_selecting_nodes_does_not_move_the_leftover_cursor() -> None:
    controls = _make_controls(("layer_1",))
    before = controls.focus_descriptor
    for node_id in ("overlay", "layers", layer_node_id("layer_1")):
        controls.navigator.select(node_id)
        assert controls.shell_focus.region is ShellRegion.NAVIGATOR
        assert controls.focus_descriptor == before


def test_quick_step_stays_on_top_level_ids() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    focus = controls.shell_focus
    controls.navigator.select("timeline")
    controls.navigator.quick_step(1)
    assert focus.selected_id == "layers"
    controls.navigator.quick_step(1)
    assert focus.selected_id == "settings"
    controls.navigator.quick_step(-1)
    assert focus.selected_id == "layers"


def test_quick_step_from_a_child_moves_from_its_root() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    focus = controls.shell_focus
    controls.navigator.select("post_fx.limiter")
    controls.navigator.quick_step(1)
    assert focus.selected_id == "pattern_mask"

    controls.navigator.select(layer_page_node_id("layer_2", "effects"))
    controls.navigator.quick_step(-1)
    assert focus.selected_id == "timeline"


def test_delete_reconciles_to_nearest_layer_sibling() -> None:
    controls, manager = _make_controls_with_manager(("layer_1", "layer_2", "layer_3"))
    controls.navigator.select(layer_node_id("layer_2"))

    def remove(slot: str) -> None:
        controls.session.layer_z_order.remove(slot)
        del controls.session.layers[slot]

    manager.remove_layer.side_effect = remove
    controls.layer_lifecycle.confirm_delete("layer_2")
    assert controls.shell_focus.selected_id == layer_node_id("layer_3")
    assert controls.layer_lifecycle.removed_layer_index is None

    controls.layer_lifecycle.confirm_delete("layer_3")
    assert controls.shell_focus.selected_id == layer_node_id("layer_1")


def test_delete_from_a_layer_page_lands_on_a_sibling_layer() -> None:
    controls, manager = _make_controls_with_manager(("layer_1", "layer_2"))
    controls.navigator.select(layer_page_node_id("layer_2", "compositing"))

    def remove(slot: str) -> None:
        controls.session.layer_z_order.remove(slot)
        del controls.session.layers[slot]

    manager.remove_layer.side_effect = remove
    controls.layer_lifecycle.confirm_delete("layer_2")
    assert controls.shell_focus.selected_id == layer_node_id("layer_1")


def test_reconcile_opens_the_branch_it_lands_on() -> None:
    controls = _make_controls(("layer_1",))
    focus = controls.shell_focus
    controls.navigator.select("project.render")
    controls.session.settings.editor_mode = "preset_curation"
    controls.navigator.reconcile()
    assert focus.selected_id == "layers"
    assert "layers" in focus.nav_expanded
