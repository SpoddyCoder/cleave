"""Navigator Enter, selection, and reconcile."""

from __future__ import annotations

from cleave.viz.inspector import build_inspector_rows
from cleave.viz.navigator import layer_node_id, layer_page_node_id
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.shell_focus import ShellRegion
from tests.support.viz import (
    make_controls,
    make_controls_with_manager,
)


def test_open_page_shows_a_project_page_without_a_navigator_row() -> None:
    controls = make_controls(("layer_1",))
    focus = controls.shell_focus
    expanded = set(focus.nav_expanded)
    controls.navigator.open_page("project.projectm")
    assert focus.selected_id == "project.projectm"
    assert focus.region is ShellRegion.INSPECTOR
    assert focus.nav_expanded == expanded
    assert focus.inspector_cursor == RowDescriptor(
        RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY
    )


def test_open_page_survives_reconcile_and_quick_step_leaves_it() -> None:
    controls = make_controls(("layer_1",))
    focus = controls.shell_focus
    controls.navigator.open_page("settings.preview")
    controls.navigator.reconcile()
    assert focus.selected_id == "settings.preview"
    assert focus.region is ShellRegion.INSPECTOR

    controls.navigator.quick_step(1)
    assert focus.selected_id == "layers"
    controls.navigator.open_page("settings.ui")
    controls.navigator.quick_step(-1)
    assert focus.selected_id == "timeline"


def test_enter_on_root_page_focuses_its_enabled_row() -> None:
    controls = make_controls(("layer_1",))
    focus = controls.shell_focus
    for node_id, kind in (
        ("overlay", RowKind.OVERLAYS_PREVIEW),
        ("post_fx", RowKind.POST_FX_LOCKED),
        ("pattern_mask", RowKind.PATTERN_MASK_ENABLED),
        ("timeline", RowKind.TIMELINE_ENABLED),
    ):
        controls.navigator.select(node_id)
        controls.navigator.activate()
        assert focus.selected_id == node_id
        assert focus.region is ShellRegion.INSPECTOR
        assert focus.inspector_cursor == RowDescriptor(kind)


def test_enter_on_pages_focuses_first_navigable_row() -> None:
    controls = make_controls(("layer_1",))
    focus = controls.shell_focus
    view = controls.build_view_state(paused=controls.playback.paused)
    for node_id in (
        "overlay.opening_card",
        "post_fx.fade",
        "pattern_mask",
        "timeline.grid",
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
    controls = make_controls(("layer_1",))
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
    assert RowKind.TRACK_STEM in layer_kinds
    assert RowKind.TRACK_PRESET not in layer_kinds
    assert focus.inspector_cursor == next(
        row.descriptor
        for row in layer_rows
        if row.navigable and row.descriptor is not None
    )


def test_selecting_nodes_does_not_move_the_leftover_cursor() -> None:
    controls = make_controls(("layer_1",))
    before = controls.focus_descriptor
    for node_id in ("overlay", "layers", layer_node_id("layer_1")):
        controls.navigator.select(node_id)
        assert controls.shell_focus.region is ShellRegion.NAVIGATOR
        assert controls.focus_descriptor == before


def test_quick_step_stays_on_top_level_ids() -> None:
    controls = make_controls(("layer_1", "layer_2"))
    focus = controls.shell_focus
    controls.navigator.select("timeline")
    controls.navigator.quick_step(1)
    assert focus.selected_id == "layers"
    controls.navigator.quick_step(1)
    assert focus.selected_id == "overlay"
    controls.navigator.quick_step(-1)
    assert focus.selected_id == "layers"


def test_quick_step_from_a_child_moves_from_its_root() -> None:
    controls = make_controls(("layer_1", "layer_2"))
    focus = controls.shell_focus
    controls.navigator.select("post_fx.limiter")
    controls.navigator.quick_step(1)
    assert focus.selected_id == "pattern_mask"

    controls.navigator.select(layer_page_node_id("layer_2", "effects"))
    controls.navigator.quick_step(-1)
    assert focus.selected_id == "timeline"


def test_delete_reconciles_to_nearest_layer_sibling() -> None:
    controls, manager = make_controls_with_manager(("layer_1", "layer_2", "layer_3"))
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
    controls, manager = make_controls_with_manager(("layer_1", "layer_2"))
    controls.navigator.select(layer_page_node_id("layer_2", "compositing"))

    def remove(slot: str) -> None:
        controls.session.layer_z_order.remove(slot)
        del controls.session.layers[slot]

    manager.remove_layer.side_effect = remove
    controls.layer_lifecycle.confirm_delete("layer_2")
    assert controls.shell_focus.selected_id == layer_node_id("layer_1")


def test_reconcile_opens_the_branch_it_lands_on() -> None:
    controls = make_controls(("layer_1",))
    focus = controls.shell_focus
    controls.navigator.open_page("project.resolution")
    controls.session.settings.editor_mode = "preset_curation"
    controls.navigator.reconcile()
    assert focus.selected_id == "layers"
    assert "layers" in focus.nav_expanded


def test_switching_off_moves_selection_off_the_preset_list_page() -> None:
    controls = make_controls(("layer_1",))
    focus = controls.shell_focus
    layer = controls.session.layers["layer_1"]
    layer.preset_switching_trigger = "timer"
    page = layer_page_node_id("layer_1", "preset_list")
    controls.navigator.select(page)
    controls.navigator.reconcile()
    assert focus.selected_id == page

    layer.preset_switching_trigger = "off"
    controls.navigator.reconcile()
    assert focus.selected_id == layer_node_id("layer_1")


def _visit(controls, page_id: str) -> None:
    controls.shell_focus.selected_id = page_id
    controls.page_history.observe(page_id, 0.0)
    controls.page_history.observe(page_id, 5.0)


def test_back_selects_the_previous_page_and_opens_its_ancestors() -> None:
    controls = make_controls(("layer_1",))
    focus = controls.shell_focus
    page = layer_page_node_id("layer_1", "compositing")
    _visit(controls, "layers")
    _visit(controls, page)
    _visit(controls, "post_fx")
    focus.nav_expanded = set()
    assert controls.navigator.history_targets() == (page, None)
    controls.navigator.go_back()
    assert focus.selected_id == page
    assert {"layers", layer_node_id("layer_1")} <= focus.nav_expanded
    assert focus.region is ShellRegion.NAVIGATOR
    assert controls.navigator.history_targets()[1] == "post_fx"
    controls.navigator.go_forward()
    assert focus.selected_id == "post_fx"


def test_back_in_the_inspector_keeps_focus_and_moves_the_cursor() -> None:
    controls = make_controls(("layer_1",))
    focus = controls.shell_focus
    _visit(controls, "overlay")
    controls.navigator.open_page("project.projectm")
    _visit(controls, "project.projectm")
    assert focus.region is ShellRegion.INSPECTOR
    controls.navigator.go_back()
    assert focus.selected_id == "overlay"
    assert focus.region is ShellRegion.INSPECTOR
    assert focus.inspector_cursor == RowDescriptor(RowKind.OVERLAYS_PREVIEW)


def test_back_skips_a_page_whose_layer_was_removed() -> None:
    controls = make_controls(("layer_1", "layer_2"))
    _visit(controls, "overlay")
    _visit(controls, layer_node_id("layer_2"))
    _visit(controls, "post_fx")
    controls.session.layer_z_order.remove("layer_2")
    del controls.session.layers["layer_2"]
    controls.navigator.go_back()
    assert controls.shell_focus.selected_id == "overlay"


def test_back_from_the_strip_to_a_navigator_page_leaves_the_strip() -> None:
    controls = make_controls(("layer_1", "layer_2"))
    controls.open_timeline_panel()
    _visit(controls, "overlay")
    controls.set_shell_region(ShellRegion.TIMELINE)
    controls.set_timeline_focus_row(1)
    _visit(controls, controls.shell_focus.selected_id)
    assert controls.shell_focus.selected_id == "timeline.row:layer_2"
    controls.navigator.go_back()
    assert controls.shell_focus.selected_id == "overlay"
    assert controls.shell_focus.region is ShellRegion.NAVIGATOR
    controls.navigator.go_forward()
    assert controls.shell_focus.selected_id == "timeline.row:layer_2"
    assert controls.session.timeline.focus_row == 1
