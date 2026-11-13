"""Tests for favourite / blacklist / cast curation through the preset library."""

from __future__ import annotations

from pathlib import Path

import pygame

from cleave.preset_library import PresetLibrary
from cleave.preset_playlist import playlist_at_collection, playlist_at_dir
from cleave.viz.modal import ModalHost
from cleave.viz.preset_curation_controls import PresetCurationController
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.viz import keydown, noop_layer_bindings


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _make_controller(
    root: Path,
    *,
    layer_bindings=noop_layer_bindings,
    notifications: list[str] | None = None,
) -> tuple[PresetCurationController, TuningSession, ModalHost, PresetLibrary]:
    library = PresetLibrary.in_memory()
    library.index(root)
    modal_host = ModalHost()
    playlist = playlist_at_dir(root / "pack", catalog=library)
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=playlist,
                browse_floor=root,
                stem="drums",
                opacity_pct=50,
                preset_list=[str(root / "pack" / "demo.milk")],
            ),
        },
    )
    controller = PresetCurationController(
        session,
        modal_host,
        layer_bindings(),
        library,
        on_notification=(
            notifications.append if notifications is not None else None
        ),
    )
    return controller, session, modal_host, library


def test_toggle_favourite_flips_flag_without_touching_files(tmp_path: Path) -> None:
    src = tmp_path / "pack" / "demo.milk"
    _write(src, "milk")
    notes: list[str] = []
    controller, _session, modal, library = _make_controller(
        tmp_path, notifications=notes
    )
    before = _tree_snapshot(tmp_path)

    controller.toggle_favourite(src)
    assert library.is_favourite(src)
    assert modal.view_state() is None
    controller.toggle_favourite(src)
    assert not library.is_favourite(src)

    assert notes == ["Favourited", "Removed from favourites"]
    assert _tree_snapshot(tmp_path) == before


def test_confirm_blacklist_hides_from_folder_but_keeps_preset_list(
    tmp_path: Path,
) -> None:
    src = tmp_path / "pack" / "demo.milk"
    _write(src, "milk")
    _write(tmp_path / "pack" / "other.milk", "other")
    preset_changes: list[str] = []
    locked: list[str] = []
    unlocked: list[str] = []
    controller, session, modal, library = _make_controller(
        tmp_path,
        layer_bindings=lambda: noop_layer_bindings(
            on_preset_change=lambda slot, playlist: preset_changes.append(slot),
            lock_preset_for_modal=lambda slot: locked.append(slot),
            unlock_preset_after_modal=lambda slot: unlocked.append(slot),
        ),
    )
    before = _tree_snapshot(tmp_path)

    controller.prompt_blacklist("layer_1", src)
    view = modal.view_state()
    assert view is not None
    assert view.message == "Blacklist preset: demo.milk?"
    modal.handle_keydown(keydown(pygame.K_RETURN))

    assert library.is_blacklisted(src)
    assert locked == ["layer_1"] and unlocked == ["layer_1"]
    layer = session.layers["layer_1"]
    assert [p.name for p in layer.playlist.paths] == ["other.milk"]
    assert preset_changes == ["layer_1"]
    assert layer.preset_list == [str(src)]
    assert _tree_snapshot(tmp_path) == before


def test_cast_sets_role_and_none_clears_it(tmp_path: Path) -> None:
    src = tmp_path / "pack" / "demo.milk"
    _write(src, "milk")
    controller, _session, modal, library = _make_controller(tmp_path)

    controller.prompt_cast("layer_1", src)
    view = modal.view_state()
    assert view is not None
    assert view.options == ("bed", "pulse", "lead", "accent", "Cancel")
    modal.handle_keydown(keydown(pygame.K_RETURN))
    assert library.role_of(src) == "bed"

    controller.prompt_cast("layer_1", src)
    view = modal.view_state()
    assert view is not None
    assert view.options == (
        "bed (current)",
        "pulse",
        "lead",
        "accent",
        "None",
        "Cancel",
    )
    for _ in range(4):
        modal.handle_keydown(keydown(pygame.K_DOWN))
    modal.handle_keydown(keydown(pygame.K_RETURN))
    assert library.role_of(src) is None


def test_toggle_blacklist_confirms_on_and_clears_at_once(tmp_path: Path) -> None:
    src = tmp_path / "pack" / "demo.milk"
    _write(src, "milk")
    notes: list[str] = []
    controller, _session, modal, library = _make_controller(
        tmp_path, notifications=notes
    )

    controller.toggle_blacklist("layer_1", src)
    assert modal.view_state() is not None
    modal.handle_keydown(keydown(pygame.K_RETURN))
    assert library.is_blacklisted(src)

    controller.toggle_blacklist("layer_1", src)
    assert modal.view_state() is None
    assert not library.is_blacklisted(src)
    assert notes == ["Removed from blacklist"]


def test_unfavourite_refreshes_layer_browsing_favourites(tmp_path: Path) -> None:
    a = tmp_path / "pack" / "a.milk"
    b = tmp_path / "pack" / "b.milk"
    _write(a, "a")
    _write(b, "b")
    preset_changes: list[str] = []
    controller, session, _modal, library = _make_controller(
        tmp_path,
        layer_bindings=lambda: noop_layer_bindings(
            on_preset_change=lambda slot, playlist: preset_changes.append(slot),
        ),
    )
    library.set_favourite(a, True)
    library.set_favourite(b, True)
    layer = session.layers["layer_1"]
    layer.playlist = playlist_at_collection(
        "favourites", current_dir=tmp_path / "pack", catalog=library
    )
    assert layer.playlist.current == a.resolve()

    controller.toggle_favourite(a)

    assert layer.playlist.paths == (b.resolve(),)
    assert layer.playlist.current == b.resolve()
    assert preset_changes == ["layer_1"]
