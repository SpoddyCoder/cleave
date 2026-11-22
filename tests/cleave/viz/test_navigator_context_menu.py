"""Navigator row context menu items, through real ``TuningControls``."""

from __future__ import annotations

from cleave.viz.context_menu import ContextMenuItem, ContextSubmenu
from cleave.viz.navigator_context_menu import (
    navigator_node_menu,
    navigator_node_menu_entries,
)
from tests.support.viz import (
    make_controls,
    make_controls_with_manager,
)


def _entries(controls, node_id: str, toggled: list[str] | None = None):
    sink = toggled if toggled is not None else []
    return {
        entry.id: entry
        for entry in navigator_node_menu_entries(controls, node_id, sink.append)
        if isinstance(entry, (ContextMenuItem, ContextSubmenu))
    }


def test_root_row_offers_expand_and_its_icons() -> None:
    controls = make_controls(("layer_1",))
    toggled: list[str] = []
    items = _entries(controls, "pattern_mask", toggled)
    assert list(items) == [
        "navigator.expand",
        "navigator.toggle.enabled",
        "navigator.toggle.lock",
    ]
    assert items["navigator.expand"].label == "Expand"
    items["navigator.expand"].run()
    assert toggled == ["pattern_mask"]
    enabled = items["navigator.toggle.enabled"]
    assert enabled.shortcut == "E"
    was = controls.session.pattern_mask.enabled
    enabled.run()
    assert controls.session.pattern_mask.enabled is not was
    assert (
        _entries(controls, "pattern_mask")["navigator.toggle.enabled"].checked
        is not was
    )
    assert list(_entries(controls, "post_fx")) == [
        "navigator.expand",
        "navigator.toggle.lock",
    ]


def test_lock_greys_out_the_enabled_item() -> None:
    controls = make_controls(("layer_1",))
    _entries(controls, "pattern_mask")["navigator.toggle.lock"].run()
    enabled = _entries(controls, "pattern_mask")["navigator.toggle.enabled"]
    assert enabled.enabled is False
    assert enabled.hint == "Locked: unlock to change"


def test_layer_row_has_pages_solo_move_and_delete() -> None:
    controls, _manager = make_controls_with_manager(("layer_1", "layer_2"))
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
    controls, _manager = make_controls_with_manager(("layer_1", "layer_2"))
    controls.toggle_layer_locked("layer_1")
    move = _entries(controls, "layer:layer_1")["navigator.layer.move_down"]
    assert move.enabled is False
    assert move.hint == "Locked: unlock to move"


def test_layers_root_offers_add_and_a_gone_row_has_no_menu() -> None:
    controls = make_controls(("layer_1",))
    assert "navigator.layer.add" in _entries(controls, "layers")
    assert navigator_node_menu(controls, "layer:gone", lambda _id: None)() == ()


def _open(controls, *node_ids: str) -> None:
    controls.shell_focus.nav_expanded.update(node_ids)


def _labels(controls, node_id: str) -> list[str]:
    return [item.label for item in _entries(controls, node_id).values()]


def test_layer_page_lists_its_layers_switches() -> None:
    controls = make_controls(("layer_1",))
    _open(controls, "layer:layer_1")
    items = _entries(controls, "layer:layer_1:compositing")
    assert list(items) == [
        "navigator.toggle.enabled",
        "navigator.toggle.solo",
        "navigator.toggle.lock",
    ]
    solo = items["navigator.toggle.solo"]
    assert solo.label.startswith("Solo (1 ")
    assert solo.shortcut == "S"
    solo.run()
    assert controls.session.solo_slot == "layer_1"
    assert _entries(controls, "layer:layer_1:compositing")[
        "navigator.toggle.solo"
    ].checked


def test_post_fx_effect_owns_its_switch_and_names_the_parent_lock() -> None:
    controls = make_controls(("layer_1",))
    _open(controls, "post_fx")
    assert _labels(controls, "post_fx.fade") == ["Enabled", "Locked (Post-FX)"]
    was = controls.session.post_fx.fade.enabled
    _entries(controls, "post_fx.fade")["navigator.toggle.enabled"].run()
    assert controls.session.post_fx.fade.enabled is not was


def test_timeline_pages_offer_their_buttons() -> None:
    controls = make_controls(("layer_1",))
    _open(controls, "timeline")
    assert _labels(controls, "timeline.grid")[-1] == "Snap clips…"
    markers = _entries(controls, "timeline.song_markers")
    assert "navigator.drop_marker" in markers
    assert markers["navigator.drop_marker"].shortcut == "Ctrl+Enter"
    assert "navigator.page.timeline.snap_to_markers" in markers


def test_go_to_preset_list_follows_the_switching_trigger() -> None:
    controls = make_controls(("layer_1",))
    _open(controls, "layer:layer_1")
    layer = controls.session.layers["layer_1"]
    page = "layer:layer_1:milkdrop_preset"
    layer.preset_switching_trigger = "off"
    assert "navigator.page.layers.go_to_preset_list" not in _entries(controls, page)
    layer.preset_switching_trigger = "timeline"
    assert "navigator.page.layers.go_to_preset_list" in _entries(controls, page)


def test_preset_list_row_takes_the_page_menu() -> None:
    controls = make_controls(("layer_1",))
    _open(controls, "layer:layer_1")
    controls.session.layers["layer_1"].preset_switching_trigger = "timeline"
    labels = _labels(controls, "layer:layer_1:preset_list")
    assert "Paste" in labels
    assert "Clear list…" in labels
    assert labels.count("Populate list…") == 1


def test_card_row_preview_and_lock_act_on_overlay() -> None:
    controls = make_controls(("layer_1",))
    _open(controls, "overlay")
    page = "overlay.opening_card"
    items = _entries(controls, page)
    assert items["navigator.toggle.preview"].label == "Preview (Overlay)"
    was = controls.session.overlay_preview
    items["navigator.toggle.preview"].run()
    assert controls.session.overlay_preview is not was
    assert _entries(controls, page)["navigator.toggle.preview"].checked is not was
    items["navigator.toggle.lock"].run()
    assert controls.session.overlays.locked is True
