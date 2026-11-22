"""Preset row context menu items, through real ``TuningControls``."""

from __future__ import annotations

import tempfile
from pathlib import Path

from cleave.preset_library import UNFILTERED_CATALOG
from cleave.viz.context_menu import ContextMenuItem, ContextSubmenu
from cleave.viz.preset_context_menu import (
    preset_list_page_menu,
    preset_row_menu,
    preset_row_menu_entries,
)
from cleave.viz.row_kinds import RowDescriptor, RowKind
from tests.support.viz import make_controls
from tests.support.preset_list import entries


def _item_desc(index: int) -> RowDescriptor:
    return RowDescriptor(
        RowKind.TRACK_PRESET_LIST_ITEM, slot="layer_1", preset_index=index
    )


def _flatten(entries):
    """Each row by id, with a submenu's child rows after it."""
    rows = {}
    for entry in entries:
        if isinstance(entry, (ContextMenuItem, ContextSubmenu)):
            rows[entry.id] = entry
        if isinstance(entry, ContextSubmenu):
            rows.update(_flatten(entry.items))
    return rows


def _entries(controls, desc: RowDescriptor):
    return _flatten(preset_row_menu_entries(controls, desc))


def _controls_with_list(
    tmp: str,
    names: tuple[str, ...] = ("a", "b", "c"),
    slots: tuple[str, ...] = ("layer_1",),
):
    root = Path(tmp)
    paths = []
    for name in names:
        path = root / f"{name}.milk"
        path.write_text(f"milk {name}", encoding="utf-8")
        paths.append(str(path))
    controls = make_controls(slots, project_dir=root / "project")
    for slot in slots:
        controls.session.layers[slot].preset_switching = "on"
    controls.session.layers["layer_1"].preset_list = entries(*paths)
    return controls, paths


def _names(controls, slot: str = "layer_1") -> list[str]:
    return [entry.display_name for entry in controls.session.layers[slot].preset_list]


def test_list_item_menu_lists_its_items_in_order() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        entries = preset_row_menu_entries(controls, _item_desc(1))
        assert [getattr(entry, "id", None) for entry in entries] == [
            "preset.audition",
            None,
            "preset.cut",
            "preset.copy",
            "preset.paste",
            "preset.duplicate",
            None,
            "preset.replace_browse",
            "preset.current",
            None,
            "preset.populate",
            "preset.clear",
            None,
            "preset.move_up",
            "preset.move_down",
            "preset.remove",
            None,
            "preset.favourite",
            "preset.blacklist",
            "preset.role",
        ]
        items = _entries(controls, _item_desc(1))
        assert [(item.id, item.label) for item in items["preset.paste"].items] == [
            ("preset.paste_over", "Over this entry"),
            ("preset.paste_before", "Before this entry"),
            ("preset.paste_after", "After this entry"),
        ]
        assert [(item.id, item.label) for item in items["preset.current"].items] == [
            ("preset.replace_current", "Replace this entry"),
            ("preset.insert_current", "Insert after this entry"),
            ("preset.add_current", "Add to end of list"),
        ]
        paste_ids = {
            "preset.paste",
            "preset.paste_over",
            "preset.paste_before",
            "preset.paste_after",
        }
        assert all(
            entry.enabled
            for item_id, entry in items.items()
            if item_id not in paste_ids and not item_id.startswith("preset.role.")
        )
        for item_id in paste_ids:
            assert items[item_id].enabled is False
            assert items[item_id].hint == "Nothing copied"
        assert items["preset.remove"].label == "Remove from list"
        assert [
            items[i].shortcut
            for i in ("preset.cut", "preset.copy", "preset.duplicate")
        ] == ["Ctrl+X", "Ctrl+C", "Ctrl+D"]
        assert items["preset.paste_over"].shortcut == "Ctrl+V"
        assert items["preset.paste_after"].shortcut == "Ctrl+Shift+V"
        assert [items[i].shortcut for i in ("preset.favourite", "preset.blacklist", "preset.role")] == ["F", "B", "C"]
        assert items["preset.favourite"].label == "Favourite"
        assert items["preset.blacklist"].label == "Blacklist…"
        role = items["preset.role"]
        assert [item.label for item in role.items] == [
            "Bed", "Pulse", "Lead", "Accent", "None",
        ]
        assert [item.checked for item in role.items] == [
            False, False, False, False, True,
        ]


def test_curation_items_undo_themselves() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, (a, _b, _c) = _controls_with_list(tmp)
        library = controls.library
        desc = _item_desc(0)

        _entries(controls, desc)["preset.favourite"].run()
        assert library.is_favourite(Path(a))
        items = _entries(controls, desc)
        assert items["preset.favourite"].label == "Unfavourite"
        items["preset.favourite"].run()
        assert not library.is_favourite(Path(a))

        library.set_blacklisted(Path(a), True)
        items = _entries(controls, desc)
        assert items["preset.blacklist"].label == "Unblacklist"
        items["preset.blacklist"].run()
        assert not library.is_blacklisted(Path(a))
        assert not controls.modal_host.active

        role = _entries(controls, desc)["preset.role"]
        role.items[2].run()
        assert library.role_of(Path(a)) == "lead"
        role = _entries(controls, desc)["preset.role"]
        assert [item.checked for item in role.items] == [
            False, False, True, False, False,
        ]
        role.items[4].run()
        assert library.role_of(Path(a)) is None


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
        assert controls.session.layers["layer_1"].preset_list == entries(b, a, c)
        assert controls.shell_focus.inspector_cursor == _item_desc(1)


def test_lock_disables_edits_but_not_audition() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        controls.session.layers["layer_1"].locked = True
        controls.preset_clipboard.copy_entry("layer_1", 0)
        items = _entries(controls, _item_desc(1))
        assert items["preset.audition"].enabled is True
        assert items["preset.copy"].enabled is True
        for item_id in (
            "preset.move_up",
            "preset.move_down",
            "preset.remove",
            "preset.cut",
            "preset.duplicate",
            "preset.paste",
            "preset.paste_over",
            "preset.paste_before",
            "preset.paste_after",
            "preset.replace_browse",
            "preset.current",
            "preset.replace_current",
            "preset.insert_current",
            "preset.add_current",
            "preset.populate",
            "preset.clear",
        ):
            assert items[item_id].enabled is False, item_id
            assert items[item_id].hint == "Locked: unlock to change"
        for item_id in ("preset.favourite", "preset.blacklist", "preset.role"):
            assert items[item_id].enabled is False, item_id
            assert items[item_id].hint == "Locked: unlock to change"


def test_add_current_needs_switching_on() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        controls.session.layers["layer_1"].preset_switching = "off"
        add = _entries(controls, _item_desc(0))["preset.add_current"]
        assert add.enabled is False
        assert add.hint == "Turn on preset switching first"


def test_remove_runs_at_once_and_undo_restores_it() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        _entries(controls, _item_desc(0))["preset.remove"].run()
        assert not controls.modal_host.active
        assert _names(controls) == ["b.milk", "c.milk"]
        controls.undo()
        assert _names(controls) == ["a.milk", "b.milk", "c.milk"]
        controls.redo()
        assert _names(controls) == ["b.milk", "c.milk"]


def test_clear_asks_first_and_undo_restores_the_list() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        clear = _entries(controls, _item_desc(1))["preset.clear"]
        assert clear.label == "Clear list…"
        clear.run()
        modal = controls.modal_host
        assert modal.active
        view = modal.view_state()
        assert view is not None
        assert view.message == "Clear preset list?"
        modal.cancel()
        assert _names(controls) == ["a.milk", "b.milk", "c.milk"]
        preset_list_page_menu(controls, "layer_1")()[-1].run()
        modal.activate_option(0)
        assert not modal.active
        assert _names(controls) == []
        controls.undo()
        assert _names(controls) == ["a.milk", "b.milk", "c.milk"]


def test_copy_then_paste_over_before_and_after() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        _entries(controls, _item_desc(0))["preset.copy"].run()
        _entries(controls, _item_desc(2))["preset.paste_over"].run()
        assert _names(controls) == ["a.milk", "b.milk", "a.milk"]
        _entries(controls, _item_desc(1))["preset.paste_before"].run()
        assert _names(controls) == ["a.milk", "a.milk", "b.milk", "a.milk"]
        _entries(controls, _item_desc(3))["preset.paste_after"].run()
        assert _names(controls) == ["a.milk", "a.milk", "b.milk", "a.milk", "a.milk"]
        assert controls.shell_focus.inspector_cursor == _item_desc(4)
        project_presets = Path(tmp) / "project" / "presets"
        for entry in controls.session.layers["layer_1"].preset_list[1:]:
            if entry.display_name == "a.milk":
                assert entry.file.parent == project_presets
        for _ in range(3):
            controls.undo()
        assert _names(controls) == ["a.milk", "b.milk", "c.milk"]


def test_cut_moves_an_entry_to_another_layer() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp, slots=("layer_1", "layer_2"))
        _entries(controls, _item_desc(1))["preset.cut"].run()
        assert _names(controls) == ["a.milk", "c.milk"]
        controls.preset_clipboard.paste_before("layer_2", 0)
        assert _names(controls, "layer_2") == ["b.milk"]
        controls.undo()
        assert _names(controls, "layer_2") == []
        controls.undo()
        assert _names(controls) == ["a.milk", "b.milk", "c.milk"]


def test_list_page_menu_pastes_into_an_empty_list() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp, slots=("layer_1", "layer_2"))
        page = _flatten(preset_list_page_menu(controls, "layer_2")())
        assert page["preset.paste_end"].enabled is False
        assert page["preset.paste_end"].hint == "Nothing copied"
        controls.preset_clipboard.copy_entry("layer_1", 2)
        page = _flatten(preset_list_page_menu(controls, "layer_2")())
        assert set(page) == {
            "preset.paste_end",
            "preset.add_current",
            "preset.populate",
            "preset.clear",
        }
        assert page["preset.clear"].enabled is False
        assert page["preset.clear"].hint == "The list is already empty"
        page["preset.paste_end"].run()
        page["preset.paste_end"].run()
        assert _names(controls, "layer_2") == ["c.milk", "c.milk"]
        controls.undo()
        assert _names(controls, "layer_2") == ["c.milk"]


def test_list_page_menu_is_disabled_when_locked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        controls.preset_clipboard.copy_entry("layer_1", 0)
        controls.session.layers["layer_1"].locked = True
        page = _flatten(preset_list_page_menu(controls, "layer_1")())
        for item in page.values():
            assert item.enabled is False, item.id
            assert item.hint == "Locked: unlock to change"


def test_duplicate_inserts_a_second_copy_after() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        _entries(controls, _item_desc(1))["preset.duplicate"].run()
        assert _names(controls) == ["a.milk", "b.milk", "b.milk", "c.milk"]


def test_paste_is_disabled_once_the_copied_file_is_gone() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, (a, _b, _c) = _controls_with_list(tmp)
        controls.preset_clipboard.copy_path(Path(a))
        Path(a).unlink()
        paste = _entries(controls, _item_desc(1))["preset.paste_over"]
        assert paste.enabled is False
        assert paste.hint == "Copied preset file is missing"


def test_insert_on_a_timeline_layer_warns_that_later_presets_shift() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        controls.session.layers["layer_1"].preset_switching_trigger = "timeline"
        controls.preset_clipboard.copy_entry("layer_1", 0)
        items = _entries(controls, _item_desc(1))
        assert items["preset.paste_over"].hint is None
        assert items["preset.paste_after"].hint == "Later presets move to the next clip"
        assert items["preset.insert_current"].hint == "Later presets move to the next clip"


def test_current_preset_row_offers_add_and_curate() -> None:
    controls = make_controls(("layer_1",))
    desc = RowDescriptor(RowKind.TRACK_PRESET, slot="layer_1")
    items = _entries(controls, desc)
    assert [item_id for item_id in items if not item_id.startswith("preset.role.")] == [
        "preset.browse",
        "preset.copy",
        "preset.paste_preview",
        "preset.add_current",
        "preset.favourite",
        "preset.blacklist",
        "preset.role",
    ]
    assert items["preset.add_current"].label == "Add to preset list"


def test_menu_is_empty_once_the_row_is_gone() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        provider = preset_row_menu(controls, _item_desc(2))
        assert provider()
        controls.session.layers["layer_1"].preset_list.pop()
        assert provider() == ()


def _dir_desc() -> RowDescriptor:
    return RowDescriptor(RowKind.TRACK_PRESET_DIR, slot="layer_1")


def _controls_with_library(tmp: str):
    controls, paths = _controls_with_list(tmp)
    controls.session.layers["layer_1"].playlist.catalog = controls.library
    return controls, paths


def test_directory_row_has_only_browse_without_collections() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_list(tmp)
        controls.session.layers["layer_1"].playlist.catalog = UNFILTERED_CATALOG
        entries = preset_row_menu_entries(controls, _dir_desc())
        assert [entry.id for entry in entries] == ["preset.browse"]


def test_directory_row_jumps_to_a_collection() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_library(tmp)
        items = _entries(controls, _dir_desc())
        assert [
            getattr(entry, "id", None)
            for entry in preset_row_menu_entries(controls, _dir_desc())
        ] == ["preset.browse", None, "preset.jump"]
        assert items["preset.browse"].label == "Browse presets…"
        jump = items["preset.jump"]
        assert jump.label == "Jump to directory"
        assert [item.label for item in jump.items] == [
            "Favourites",
            "Role: bed",
            "Role: pulse",
            "Role: lead",
            "Role: accent",
            "Blacklisted",
        ]
        assert not any(item.checked for item in jump.items)

        jump.items[0].run()
        playlist = controls.session.layers["layer_1"].playlist
        assert playlist.collection == "favourites"
        jump = _entries(controls, _dir_desc())["preset.jump"]
        assert [item.checked for item in jump.items] == [
            True, False, False, False, False, False,
        ]

        jump.items[-1].run()
        assert playlist.collection == "blacklisted"


def test_directory_jump_is_disabled_when_locked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        controls, _paths = _controls_with_library(tmp)
        controls.session.layers["layer_1"].locked = True
        jump = _entries(controls, _dir_desc())["preset.jump"]
        assert not jump.enabled
        assert jump.hint == "Locked: unlock to change"
