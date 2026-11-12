"""Preset row context menu items, through real ``TuningControls``."""

from __future__ import annotations

import tempfile
from pathlib import Path

from cleave.viz.context_menu import ContextMenuItem, ContextSubmenu
from cleave.viz.preset_context_menu import preset_row_menu, preset_row_menu_entries
from cleave.viz.row_kinds import RowDescriptor, RowKind
from tests.cleave.viz.test_controls import _make_controls


def _item_desc(index: int) -> RowDescriptor:
    return RowDescriptor(
        RowKind.TRACK_PRESET_LIST_ITEM, slot="layer_1", preset_index=index
    )


def _entries(controls, desc: RowDescriptor):
    return {
        entry.id: entry
        for entry in preset_row_menu_entries(controls, desc)
        if isinstance(entry, (ContextMenuItem, ContextSubmenu))
    }


def _controls_with_list(tmp: str, names: tuple[str, ...] = ("a", "b", "c")):
    root = Path(tmp)
    paths = []
    for name in names:
        path = root / f"{name}.milk"
        path.write_text("milk", encoding="utf-8")
        paths.append(str(path))
    controls = _make_controls(("layer_1",), project_dir=root / "project")
    layer = controls.session.layers["layer_1"]
    layer.preset_list = list(paths)
    layer.preset_switching = "on"
    return controls, paths


def test_list_item_menu_lists_its_items_in_order() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        items = _entries(controls, _item_desc(1))
        assert list(items) == [
            "preset.audition",
            "preset.move_up",
            "preset.move_down",
            "preset.remove",
            "preset.add_current",
            "preset.populate",
            "preset.curate",
        ]
        assert all(entry.enabled for entry in items.values())
        curate = items["preset.curate"]
        assert [item.shortcut for item in curate.items] == ["F", "B", "C", "R"]
        restore = curate.items[3]
        assert restore.enabled is False
        assert restore.hint == "Not favourited, cast, or blacklisted"


def test_move_items_reorder_and_stop_at_the_ends() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, (a, b, c) = _controls_with_list(tmp)
        first = _entries(controls, _item_desc(0))
        assert first["preset.move_up"].enabled is False
        assert first["preset.move_up"].hint == "Already the first preset"
        last = _entries(controls, _item_desc(2))
        assert last["preset.move_down"].enabled is False
        assert last["preset.move_down"].hint == "Already the last preset"
        first["preset.move_down"].run()
        assert controls.session.layers["layer_1"].preset_list == [b, a, c]
        assert controls.shell_focus.inspector_cursor == _item_desc(1)


def test_lock_disables_edits_but_not_audition() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        controls.session.layers["layer_1"].locked = True
        items = _entries(controls, _item_desc(1))
        assert items["preset.audition"].enabled is True
        for item_id in (
            "preset.move_up",
            "preset.move_down",
            "preset.remove",
            "preset.add_current",
            "preset.populate",
        ):
            assert items[item_id].enabled is False, item_id
            assert items[item_id].hint == "Locked: unlock to change"
        assert not any(item.enabled for item in items["preset.curate"].items)


def test_add_current_needs_switching_on() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        controls.session.layers["layer_1"].preset_switching = "off"
        add = _entries(controls, _item_desc(0))["preset.add_current"]
        assert add.enabled is False
        assert add.hint == "Turn on preset switching first"


def test_remove_prompts_for_confirmation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        _entries(controls, _item_desc(0))["preset.remove"].run()
        assert controls.modal_host.active


def test_current_preset_row_offers_add_and_curate() -> None:
    controls = _make_controls(("layer_1",))
    desc = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    items = _entries(controls, desc)
    assert list(items) == ["preset.add_current", "preset.curate"]
    assert items["preset.add_current"].label == "Add to preset list"


def test_menu_is_empty_once_the_row_is_gone() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        provider = preset_row_menu(controls, _item_desc(2))
        assert provider()
        controls.session.layers["layer_1"].preset_list.pop()
        assert provider() == ()
