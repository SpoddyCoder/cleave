"""Navigator row context menu items, through real ``TuningControls``."""

from __future__ import annotations

from cleave.viz.context_menu import ContextMenuItem, ContextSubmenu
from cleave.viz.navigator_context_menu import (
    navigator_node_menu,
    navigator_node_menu_entries,
)
from tests.cleave.viz.test_controls import _make_controls, _make_controls_with_manager


def _entries(controls, node_id: str, toggled: list[str] | None = None):
    sink = toggled if toggled is not None else []
    return {
        entry.id: entry
        for entry in navigator_node_menu_entries(controls, node_id, sink.append)
        if isinstance(entry, (ContextMenuItem, ContextSubmenu))
    }


def test_root_row_offers_expand_and_its_icons() -> None:
    controls = _make_controls(("layer_1",))
    toggled: list[str] = []
    items = _entries(controls, "post_fx", toggled)
    assert list(items) == [
        "navigator.expand",
        "navigator.toggle.enabled",
        "navigator.toggle.lock",
    ]
    assert items["navigator.expand"].label == "Expand"
    items["navigator.expand"].run()
    assert toggled == ["post_fx"]
    enabled = items["navigator.toggle.enabled"]
    assert enabled.shortcut == "E"
    was = controls.session.post_fx.enabled
    enabled.run()
    assert controls.session.post_fx.enabled is not was
    assert _entries(controls, "post_fx")["navigator.toggle.enabled"].checked is not was


def test_lock_greys_out_the_enabled_item() -> None:
    controls = _make_controls(("layer_1",))
    _entries(controls, "post_fx")["navigator.toggle.lock"].run()
    enabled = _entries(controls, "post_fx")["navigator.toggle.enabled"]
    assert enabled.enabled is False
    assert enabled.hint == "Locked: unlock to change"


def test_layer_row_has_pages_solo_move_and_delete() -> None:
    controls, _manager = _make_controls_with_manager(("layer_1", "layer_2"))
    items = _entries(controls, "layer:layer_1")
    go_to = items["navigator.go_to"]
    assert [item.label for item in go_to.items] == [
        "Milkdrop Preset",
        "Preset Switching",
        "Compositing",
        "Cleave Effects",
    ]
    assert items["navigator.toggle.solo"].shortcut == "S"
    assert items["navigator.layer.move_up"].enabled is False
    assert items["navigator.layer.move_up"].hint == "Already the first layer"
    assert items["navigator.layer.delete"].shortcut == "Delete"

    items["navigator.layer.move_down"].run()
    assert controls.session.layer_z_order == ["layer_2", "layer_1"]

    go_to.items[0].run()
    assert controls.shell_focus.selected_id == "layer:layer_1:milkdrop_preset"


def test_locked_layer_cannot_move() -> None:
    controls, _manager = _make_controls_with_manager(("layer_1", "layer_2"))
    controls.toggle_layer_locked("layer_1")
    move = _entries(controls, "layer:layer_1")["navigator.layer.move_down"]
    assert move.enabled is False
    assert move.hint == "Locked: unlock to move"


def test_layers_root_offers_add_and_a_gone_row_has_no_menu() -> None:
    controls = _make_controls(("layer_1",))
    assert "navigator.layer.add" in _entries(controls, "layers")
    assert navigator_node_menu(controls, "layer:gone", lambda _id: None)() == ()
