"""Shell hotkeys follow the navigator or inspector row."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pygame

from cleave.viz.focus_nav import MainFocus
from cleave.viz.input_dispatch import dispatch_keydown
from cleave.viz.inspector import InspectorRow, build_inspector_rows
from cleave.viz.menu_bar import MenuBarState
from cleave.viz.navigator import layer_node_id
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.shell_focus import ShellRegion
from tests.cleave.viz.test_controls import (
    _make_controls,
    _make_controls_with_manager,
)
from tests.support.viz import keydown

_LAYER_DELETE = "Delete this Milkdrop visualisation layer?"


def _runtime(controls):
    return SimpleNamespace(
        controls=controls,
        seed=SimpleNamespace(session=controls.session),
        modal_host=controls.modal_host,
        menu_bar=MenuBarState(),
        timeline_controls=None,
        overlay=MagicMock(),
        overlay_profiler=MagicMock(),
        playback=controls.playback,
    )


def _select_layer(controls, slot: str, *, region: ShellRegion) -> None:
    focus = controls.shell_focus
    focus.region = region
    focus.selected_id = layer_node_id(slot)
    focus.inspector_command_id = None


def test_navigator_layer_lock_and_delete_follow_selected_node() -> None:
    controls, manager = _make_controls_with_manager(("layer_1", "layer_2"))

    def remove_layer(slot: str) -> None:
        controls.session.layer_z_order.remove(slot)
        del controls.session.layers[slot]

    manager.remove_layer.side_effect = remove_layer
    controls.focus_cursor = MainFocus(RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER))
    _select_layer(controls, "layer_2", region=ShellRegion.NAVIGATOR)
    runtime = _runtime(controls)

    assert dispatch_keydown(keydown(pygame.K_l), runtime) is True
    assert controls.session.layers["layer_2"].locked is True
    assert controls.session.layers["layer_1"].locked is False
    assert controls.session.render_overlays.locked is False

    assert dispatch_keydown(keydown(pygame.K_DELETE), runtime) is True
    modal = controls.modal_host.view_state()
    assert modal is not None
    assert modal.message == _LAYER_DELETE
    assert dispatch_keydown(keydown(pygame.K_RETURN), runtime) is True
    manager.remove_layer.assert_called_once_with("layer_2")
    assert "layer_2" not in controls.session.layer_z_order


def test_inspector_preset_item_delete_and_move_stay_on_the_item() -> None:
    controls, manager = _make_controls_with_manager(("layer_1",))
    layer = controls.session.layers["layer_1"]
    layer.preset_switching = "on"
    layer.preset_switching_trigger = "timer"
    layer.preset_list = ["/tmp/presets/a.milk", "/tmp/presets/b.milk"]
    item = RowDescriptor(
        RowKind.TRACK_PRESET_LIST_ITEM, slot="layer_1", preset_index=0
    )
    _select_layer(controls, "layer_1", region=ShellRegion.INSPECTOR)
    controls.shell_focus.inspector_cursor = item
    view = controls.build_view_state(paused=False)
    rows = build_inspector_rows(
        view,
        layer_node_id("layer_1"),
        controls.shell_focus.collapsed,
        controls.shell_focus.opened,
    )
    assert any(row.descriptor == item for row in rows)
    runtime = _runtime(controls)

    assert dispatch_keydown(keydown(pygame.K_DELETE), runtime) is True
    modal = controls.modal_host.view_state()
    assert modal is not None
    assert modal.message is not None
    assert modal.message.startswith("Remove preset:")
    manager.remove_layer.assert_not_called()
    assert "layer_1" in controls.session.layers
    controls.modal_host.dismiss()

    assert dispatch_keydown(keydown(pygame.K_m), runtime) is True
    assert controls.preset_list.move_mode_preset == ("layer_1", 0)
    assert controls.layer_lifecycle.move_mode_slot is None


def test_inspector_value_row_l_locks_the_page_layer() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    opacity = RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")
    controls.focus_cursor = MainFocus(RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER))
    _select_layer(controls, "layer_1", region=ShellRegion.INSPECTOR)
    controls.shell_focus.inspector_cursor = opacity
    runtime = _runtime(controls)

    assert dispatch_keydown(keydown(pygame.K_l), runtime) is True
    assert controls.session.layers["layer_1"].locked is True
    assert controls.session.layers["layer_2"].locked is False
    assert controls.session.render_overlays.locked is False


def test_move_mode_up_reorders_layers_before_navigator_cursor() -> None:
    controls = _make_controls(("layer_1", "layer_2", "layer_3"))
    _select_layer(controls, "layer_2", region=ShellRegion.NAVIGATOR)
    runtime = _runtime(controls)
    selected = layer_node_id("layer_2")

    assert dispatch_keydown(keydown(pygame.K_m), runtime) is True
    assert controls.layer_lifecycle.move_mode_slot == "layer_2"
    assert dispatch_keydown(keydown(pygame.K_UP), runtime) is True
    assert controls.shell_focus.selected_id == selected
    assert controls.session.layer_z_order == ["layer_2", "layer_1", "layer_3"]

    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert controls.layer_lifecycle.move_mode_slot is None
    assert controls.session.layer_z_order == ["layer_1", "layer_2", "layer_3"]
    assert controls.shell_focus.selected_id == selected
    assert controls.consume_hide_overlay() is False

    assert dispatch_keydown(keydown(pygame.K_m), runtime) is True
    assert dispatch_keydown(keydown(pygame.K_UP), runtime) is True
    assert dispatch_keydown(keydown(pygame.K_m), runtime) is True
    assert controls.layer_lifecycle.move_mode_slot is None
    assert controls.session.layer_z_order == ["layer_2", "layer_1", "layer_3"]
    assert controls.shell_focus.selected_id == selected


def test_panel_render_header_l_still_toggles_overlay_lock() -> None:
    controls = _make_controls(("layer_1",))
    controls.focus_cursor = MainFocus(RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER))
    _select_layer(controls, "layer_1", region=ShellRegion.PANEL)
    runtime = _runtime(controls)

    assert dispatch_keydown(keydown(pygame.K_l), runtime) is True
    assert controls.session.render_overlays.locked is True
    assert controls.session.layers["layer_1"].locked is False


def _focus_inspector(controls, slot: str, desc: RowDescriptor) -> None:
    _select_layer(controls, slot, region=ShellRegion.INSPECTOR)
    controls.shell_focus.inspector_cursor = desc


def test_section_lock_inspector_refuses_edits_and_delete_still_prompts() -> None:
    controls, _manager = _make_controls_with_manager(("layer_1", "layer_2"))
    layer = controls.session.layers["layer_1"]
    layer.locked = True
    layer.preset_switching_trigger = "timer"
    layer.preset_list = ["/tmp/presets/a.milk", "/tmp/presets/b.milk"]
    runtime = _runtime(controls)
    opacity = RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")
    _focus_inspector(controls, "layer_1", opacity)

    before = layer.opacity_pct
    assert dispatch_keydown(keydown(pygame.K_RIGHT), runtime) is True
    assert dispatch_keydown(keydown(pygame.K_LEFT), runtime) is True
    assert layer.opacity_pct == before

    add = RowDescriptor(RowKind.TRACK_PRESET_LIST_ADD, slot="layer_1")
    view = controls.build_view_state(paused=False)
    built = build_inspector_rows(
        view,
        layer_node_id("layer_1"),
        controls.shell_focus.collapsed,
        controls.shell_focus.opened,
    )
    assert any(row.descriptor == add and row.navigable for row in built)
    _focus_inspector(controls, "layer_1", add)
    assert dispatch_keydown(keydown(pygame.K_RETURN), runtime) is True
    assert controls.modal_host.view_state() is None

    item = RowDescriptor(
        RowKind.TRACK_PRESET_LIST_ITEM, slot="layer_1", preset_index=0
    )
    _focus_inspector(controls, "layer_1", item)
    controls.preset_list.prompt_delete = MagicMock()
    assert dispatch_keydown(keydown(pygame.K_m), runtime) is True
    assert controls.preset_list.move_mode_preset is None
    assert dispatch_keydown(keydown(pygame.K_DELETE), runtime) is True
    controls.preset_list.prompt_delete.assert_not_called()
    assert controls.modal_host.view_state() is None

    assert dispatch_keydown(keydown(pygame.K_l), runtime) is True
    assert layer.locked is False
    assert dispatch_keydown(keydown(pygame.K_l), runtime) is True
    assert layer.locked is True

    delete = RowDescriptor(RowKind.LAYER_MANAGEMENT_DELETE, slot="layer_1")
    _focus_inspector(controls, "layer_1", opacity)
    visited = []
    for _ in range(32):
        controls.inspector.move(1)
        visited.append(controls.shell_focus.inspector_cursor)
        if controls.shell_focus.inspector_cursor == delete:
            break
    assert delete in visited

    assert dispatch_keydown(keydown(pygame.K_RETURN), runtime) is True
    modal = controls.modal_host.view_state()
    assert modal is not None
    assert modal.message == _LAYER_DELETE


def test_curation_shell_allowlist() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.session.settings.editor_mode = "preset_curation"
    layer = controls.session.layers["layer_1"]
    current = layer.playlist.current
    assert current is not None
    current.parent.mkdir(parents=True, exist_ok=True)
    current.write_text("milk", encoding="utf-8")
    layer.preset_switching = "on"
    controls.layer_lifecycle.prompt_delete = MagicMock()
    controls.layer_lifecycle.prompt_add = MagicMock()
    mock_curation = MagicMock()
    controls._preset_curation = mock_curation
    runtime = _runtime(controls)
    preset = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    _focus_inspector(controls, "layer_1", preset)

    for key in (pygame.K_f, pygame.K_b, pygame.K_c, pygame.K_r):
        assert dispatch_keydown(keydown(key), runtime) is True
    mock_curation.prompt_favourite.assert_called_once_with("layer_1", current)
    mock_curation.prompt_blacklist.assert_called_once()
    mock_curation.prompt_cast.assert_called_once_with("layer_1", current)
    mock_curation.prompt_restore.assert_called_once_with("layer_1", current)

    stem = RowDescriptor(RowKind.TRACK_STEM, slot="layer_1")
    _focus_inspector(controls, "layer_1", stem)
    before_stem = layer.stem
    assert dispatch_keydown(keydown(pygame.K_RIGHT), runtime) is True
    assert layer.stem != before_stem

    was_paused = controls.playback.paused
    assert dispatch_keydown(keydown(pygame.K_SPACE), runtime) is True
    assert controls.playback.paused is not was_paused

    assert layer.locked is False
    assert layer.enabled is True
    assert controls.session.solo_slot is None
    for key in (pygame.K_l, pygame.K_m, pygame.K_s, pygame.K_e, pygame.K_p):
        assert dispatch_keydown(keydown(key), runtime) is True
    assert layer.locked is False
    assert controls.layer_lifecycle.move_mode_slot is None
    assert controls.session.solo_slot is None
    assert layer.enabled is True
    assert controls.modal_host.view_state() is None

    assert dispatch_keydown(keydown(pygame.K_DELETE), runtime) is True
    controls.layer_lifecycle.prompt_delete.assert_not_called()

    _select_layer(controls, "layer_1", region=ShellRegion.NAVIGATOR)
    assert dispatch_keydown(keydown(pygame.K_DELETE), runtime) is True
    controls.layer_lifecycle.prompt_delete.assert_not_called()

    delete = RowDescriptor(RowKind.LAYER_MANAGEMENT_DELETE, slot="layer_1")
    _focus_inspector(controls, "layer_1", delete)
    controls.inspector._navigable_rows = lambda: (
        InspectorRow(descriptor=delete, is_group=False, depth=0, navigable=True),
    )
    assert dispatch_keydown(keydown(pygame.K_RETURN), runtime) is True
    controls.layer_lifecycle.prompt_delete.assert_not_called()
    controls.layer_lifecycle.prompt_add.assert_not_called()

    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert controls.consume_hide_overlay() is True
    assert controls.shell_focus.region is ShellRegion.INSPECTOR

    _select_layer(controls, "layer_1", region=ShellRegion.NAVIGATOR)
    assert dispatch_keydown(keydown(pygame.K_ESCAPE), runtime) is True
    assert controls.consume_hide_overlay() is True
    assert controls.shell_focus.region is ShellRegion.NAVIGATOR

    order = list(controls.session.layer_z_order)
    controls.layer_lifecycle.enter_move_mode("layer_2")
    _select_layer(controls, "layer_2", region=ShellRegion.NAVIGATOR)
    assert dispatch_keydown(keydown(pygame.K_UP), runtime) is True
    assert controls.session.layer_z_order == order
