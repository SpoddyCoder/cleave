"""Tests for preset favourites and blacklist modal orchestration."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pygame

from cleave.preset_curation import BLACKLIST_DIR, FAVOURITES_DIR, PresetCurationIndex
from cleave.preset_playlist import PresetPlaylist
from cleave.viz.modal import ModalHost
from cleave.viz.preset_curation_controls import PresetCurationController
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.viz import keydown, noop_layer_bindings


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_controller(
    *,
    preset_root: Path,
    modal: ModalHost | None = None,
    layer_bindings=noop_layer_bindings,
) -> tuple[PresetCurationController, TuningSession, ModalHost]:
    modal_host = modal if modal is not None else ModalHost()
    playlist = PresetPlaylist(
        current_dir=preset_root / "pack",
        paths=(preset_root / "pack" / "demo.milk",),
        index=0,
    )
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=playlist,
                browse_floor=preset_root,
                stem="drums",
                opacity_pct=50,
                user_presets=[str(preset_root / "pack" / "demo.milk")],
            ),
        },
    )
    controller = PresetCurationController(
        session,
        preset_root,
        modal_host,
        layer_bindings(),
        PresetCurationIndex.build(preset_root),
    )
    return controller, session, modal_host


def test_prompt_favourite_no_subdirs_uses_yes_no() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "pack" / "demo.milk"
        _write(src, "milk")
        controller, _session, modal = _make_controller(preset_root=root)

        controller.prompt_favourite("layer_1", src)

        view = modal.view_state()
        assert view is not None
        assert view.message == "Favourite preset: demo.milk?"
        assert view.options == ("Yes", "No")


def test_prompt_favourite_with_subdirs_uses_choice_modal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "pack" / "demo.milk"
        _write(src, "milk")
        (root / FAVOURITES_DIR / "keepers").mkdir(parents=True)
        controller, _session, modal = _make_controller(preset_root=root)

        controller.prompt_favourite("layer_1", src)

        view = modal.view_state()
        assert view is not None
        assert view.options == ("(root)", "keepers", "Cancel")


def test_confirm_favourite_copies_without_session_mutation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "pack" / "demo.milk"
        _write(src, "milk")
        locked: list[str] = []
        unlocked: list[str] = []
        controller, session, modal = _make_controller(
            preset_root=root,
            layer_bindings=lambda: noop_layer_bindings(
                lock_preset_for_modal=lambda slot: locked.append(slot),
                unlock_preset_after_modal=lambda slot: unlocked.append(slot),
            ),
        )
        user_presets_before = list(session.layers["layer_1"].user_presets)

        controller.prompt_favourite("layer_1", src)
        modal.handle_keydown(keydown(pygame.K_RETURN))

        assert locked == ["layer_1"]
        assert unlocked == ["layer_1"]
        assert (root / FAVOURITES_DIR / "demo.milk").exists()
        assert session.layers["layer_1"].user_presets == user_presets_before
        assert "demo.milk" in controller._index.favourites
        assert controller._index.marker("demo.milk") == " [F]"


def test_confirm_blacklist_moves_and_updates_playlist_and_user_presets() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "pack" / "demo.milk"
        _write(src, "milk")
        preset_changes: list[tuple[str, int]] = []
        switching_changes: list[str] = []
        locked: list[str] = []
        unlocked: list[str] = []
        controller, session, modal = _make_controller(
            preset_root=root,
            layer_bindings=lambda: noop_layer_bindings(
                on_preset_change=lambda slot, playlist: preset_changes.append(
                    (slot, playlist.index)
                ),
                on_preset_switching_change=lambda slot: switching_changes.append(slot),
                lock_preset_for_modal=lambda slot: locked.append(slot),
                unlock_preset_after_modal=lambda slot: unlocked.append(slot),
            ),
        )

        controller.prompt_blacklist(
            "layer_1",
            src,
            from_user_preset=False,
            user_preset_index=None,
        )
        modal.handle_keydown(keydown(pygame.K_RETURN))

        assert locked == ["layer_1"]
        assert unlocked == ["layer_1"]
        assert not src.exists()
        assert (root / BLACKLIST_DIR / "demo.milk").exists()
        assert (root / BLACKLIST_DIR / "demo.milk.origin").read_text(
            encoding="utf-8"
        ) == "pack/demo.milk"
        assert session.layers["layer_1"].playlist.paths == ()
        assert preset_changes == [("layer_1", 0)]
        assert switching_changes == ["layer_1"]
        assert session.layers["layer_1"].user_presets == []
        assert "demo.milk" in controller._index.blacklist
        assert controller._index.marker("demo.milk") == " [B]"


def test_prompt_favourite_already_in_favourites_uses_move_wording() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "pack" / "demo.milk"
        _write(src, "milk")
        _write(root / FAVOURITES_DIR / "demo.milk", "milk")
        (root / FAVOURITES_DIR / "keepers").mkdir(parents=True)
        locked: list[str] = []
        controller, _session, modal = _make_controller(
            preset_root=root,
            layer_bindings=lambda: noop_layer_bindings(
                lock_preset_for_modal=lambda slot: locked.append(slot),
            ),
        )

        controller.prompt_favourite("layer_1", src)

        view = modal.view_state()
        assert view is not None
        assert view.message == "Move favourite preset: demo.milk?"
        assert view.options == ("(root)", "keepers", "Cancel")
        assert locked == ["layer_1"]


def test_confirm_favourite_relocates_existing_favourite() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "pack" / "demo.milk"
        _write(src, "milk")
        existing = root / FAVOURITES_DIR / "demo.milk"
        _write(existing, "fav-content")
        keepers = root / FAVOURITES_DIR / "keepers"
        keepers.mkdir(parents=True)
        controller, _session, modal = _make_controller(preset_root=root)

        controller.prompt_favourite("layer_1", src)
        modal.handle_keydown(keydown(pygame.K_RIGHT))  # keepers
        modal.handle_keydown(keydown(pygame.K_RETURN))

        assert not existing.exists()
        assert (keepers / "demo.milk").read_text(encoding="utf-8") == "fav-content"
        assert src.exists()


def test_prompt_blacklist_already_in_blacklist_uses_move_wording() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "pack" / "demo.milk"
        _write(src, "milk")
        _write(root / BLACKLIST_DIR / "demo.milk", "milk")
        (root / BLACKLIST_DIR / "reject").mkdir(parents=True)
        locked: list[str] = []
        controller, _session, modal = _make_controller(
            preset_root=root,
            layer_bindings=lambda: noop_layer_bindings(
                lock_preset_for_modal=lambda slot: locked.append(slot),
            ),
        )

        controller.prompt_blacklist(
            "layer_1",
            src,
            from_user_preset=False,
            user_preset_index=None,
        )

        view = modal.view_state()
        assert view is not None
        assert view.message == "Move blacklist preset: demo.milk?"
        assert view.options == ("(root)", "reject", "Cancel")
        assert locked == ["layer_1"]


def test_confirm_blacklist_relocates_existing_blacklist() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "pack" / "demo.milk"
        _write(src, "milk")
        existing = root / BLACKLIST_DIR / "demo.milk"
        _write(existing, "bl-content")
        reject = root / BLACKLIST_DIR / "reject"
        reject.mkdir(parents=True)
        controller, _session, modal = _make_controller(preset_root=root)

        controller.prompt_blacklist(
            "layer_1",
            src,
            from_user_preset=False,
            user_preset_index=None,
        )
        modal.handle_keydown(keydown(pygame.K_RIGHT))  # reject
        modal.handle_keydown(keydown(pygame.K_RETURN))

        assert not existing.exists()
        assert (reject / "demo.milk").read_text(encoding="utf-8") == "bl-content"
        assert src.exists()


def test_prompt_favourite_allows_when_only_blacklisted() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "pack" / "demo.milk"
        _write(src, "milk")
        _write(root / BLACKLIST_DIR / "demo.milk", "other")
        controller, _session, modal = _make_controller(preset_root=root)

        controller.prompt_favourite("layer_1", src)

        view = modal.view_state()
        assert view is not None
        assert view.message == "Favourite preset: demo.milk?"


def test_blacklist_from_user_preset_skips_playlist_when_not_current() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pack_dir = root / "pack"
        current = pack_dir / "current.milk"
        user_only = pack_dir / "user-only.milk"
        _write(current, "current")
        _write(user_only, "user-only")
        preset_changes: list[str] = []
        controller, session, modal = _make_controller(
            preset_root=root,
            layer_bindings=lambda: noop_layer_bindings(
                on_preset_change=lambda slot, _playlist: preset_changes.append(slot),
            ),
        )
        session.layers["layer_1"].playlist = PresetPlaylist(
            current_dir=pack_dir,
            paths=(current, user_only),
            index=0,
        )
        session.layers["layer_1"].user_presets = [str(user_only)]

        controller.prompt_blacklist(
            "layer_1",
            user_only,
            from_user_preset=True,
            user_preset_index=0,
        )
        modal.handle_keydown(keydown(pygame.K_RETURN))

        assert preset_changes == []
        assert session.layers["layer_1"].playlist.paths == (current, user_only)
        assert session.layers["layer_1"].playlist.current == current
        assert session.layers["layer_1"].user_presets == []
        assert not user_only.exists()


def test_prompt_restore_favourite_uses_remove_modal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "pack" / "demo.milk"
        _write(src, "milk")
        _write(root / FAVOURITES_DIR / "demo.milk", "fav")
        locked: list[str] = []
        controller, _session, modal = _make_controller(
            preset_root=root,
            layer_bindings=lambda: noop_layer_bindings(
                lock_preset_for_modal=lambda slot: locked.append(slot),
            ),
        )

        controller.prompt_restore("layer_1", src)

        view = modal.view_state()
        assert view is not None
        assert view.message == "Remove favourite: demo.milk?"
        assert view.options == ("Yes", "No")
        assert locked == ["layer_1"]


def test_confirm_restore_removes_favourite() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "pack" / "demo.milk"
        _write(src, "milk")
        fav = root / FAVOURITES_DIR / "demo.milk"
        _write(fav, "fav")
        unlocked: list[str] = []
        controller, session, modal = _make_controller(
            preset_root=root,
            layer_bindings=lambda: noop_layer_bindings(
                unlock_preset_after_modal=lambda slot: unlocked.append(slot),
            ),
        )
        user_presets_before = list(session.layers["layer_1"].user_presets)

        controller.prompt_restore("layer_1", src)
        modal.handle_keydown(keydown(pygame.K_RETURN))

        assert not fav.exists()
        assert src.exists()
        assert "demo.milk" not in controller._index.favourites
        assert unlocked == ["layer_1"]
        assert session.layers["layer_1"].user_presets == user_presets_before


def test_confirm_remove_favourite_scrubs_playlist_and_user_presets() -> None:
    """Removing a favourite while browsing favourites drops it from playlists."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fav_dir = root / FAVOURITES_DIR
        keep = fav_dir / "keep.milk"
        remove = fav_dir / "remove.milk"
        _write(keep, "keep")
        _write(remove, "remove")
        preset_changes: list[tuple[str, int]] = []
        switching_changes: list[str] = []
        unlocked: list[str] = []
        controller, session, modal = _make_controller(
            preset_root=root,
            layer_bindings=lambda: noop_layer_bindings(
                on_preset_change=lambda slot, playlist: preset_changes.append(
                    (slot, playlist.index)
                ),
                on_preset_switching_change=lambda slot: switching_changes.append(slot),
                unlock_preset_after_modal=lambda slot: unlocked.append(slot),
            ),
        )
        session.layers["layer_1"].playlist = PresetPlaylist(
            current_dir=fav_dir,
            paths=(keep, remove),
            index=1,
        )
        session.layers["layer_1"].user_presets = [str(remove)]

        controller.prompt_restore("layer_1", remove)
        modal.handle_keydown(keydown(pygame.K_RETURN))

        assert not remove.exists()
        assert keep.exists()
        assert "remove.milk" not in controller._index.favourites
        assert session.layers["layer_1"].playlist.paths == (keep,)
        assert session.layers["layer_1"].playlist.current == keep
        assert session.layers["layer_1"].user_presets == []
        assert preset_changes == [("layer_1", 0)]
        assert switching_changes == ["layer_1"]
        assert unlocked == ["layer_1"]


def test_confirm_restore_blacklist_scrubs_playlist_and_user_presets() -> None:
    """Restoring while browsing blacklist drops the old path from playlists."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pack = root / "pack"
        pack.mkdir()
        bl_dir = root / BLACKLIST_DIR
        keep = bl_dir / "keep.milk"
        restore = bl_dir / "restore.milk"
        _write(keep, "keep")
        _write(restore, "restore")
        (bl_dir / "restore.milk.origin").write_text(
            "pack/restore.milk", encoding="utf-8"
        )
        preset_changes: list[tuple[str, int]] = []
        switching_changes: list[str] = []
        unlocked: list[str] = []
        controller, session, modal = _make_controller(
            preset_root=root,
            layer_bindings=lambda: noop_layer_bindings(
                on_preset_change=lambda slot, playlist: preset_changes.append(
                    (slot, playlist.index)
                ),
                on_preset_switching_change=lambda slot: switching_changes.append(slot),
                unlock_preset_after_modal=lambda slot: unlocked.append(slot),
            ),
        )
        session.layers["layer_1"].playlist = PresetPlaylist(
            current_dir=bl_dir,
            paths=(keep, restore),
            index=1,
        )
        session.layers["layer_1"].user_presets = [str(restore)]

        controller.prompt_restore("layer_1", restore)
        modal.handle_keydown(keydown(pygame.K_RETURN))

        restored = pack / "restore.milk"
        assert restored.read_text(encoding="utf-8") == "restore"
        assert not restore.exists()
        assert keep.exists()
        assert "restore.milk" not in controller._index.blacklist
        assert session.layers["layer_1"].playlist.paths == (keep,)
        assert session.layers["layer_1"].playlist.current == keep
        assert session.layers["layer_1"].user_presets == []
        assert preset_changes == [("layer_1", 0)]
        assert switching_changes == ["layer_1"]
        assert unlocked == ["layer_1"]


def test_prompt_restore_blacklist_with_origin_uses_yes_no() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / BLACKLIST_DIR / "demo.milk"
        _write(src, "milk")
        (root / BLACKLIST_DIR / "demo.milk.origin").write_text(
            "pack/demo.milk", encoding="utf-8"
        )
        controller, _session, modal = _make_controller(preset_root=root)

        controller.prompt_restore("layer_1", src)

        view = modal.view_state()
        assert view is not None
        assert view.message == "Restore blacklisted preset: demo.milk?"
        assert view.options == ("Yes", "No")


def test_confirm_restore_blacklist_moves_to_origin() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        pack = root / "pack"
        pack.mkdir()
        src = root / BLACKLIST_DIR / "demo.milk"
        _write(src, "bl-content")
        (root / BLACKLIST_DIR / "demo.milk.origin").write_text(
            "pack/demo.milk", encoding="utf-8"
        )
        unlocked: list[str] = []
        controller, session, modal = _make_controller(
            preset_root=root,
            layer_bindings=lambda: noop_layer_bindings(
                unlock_preset_after_modal=lambda slot: unlocked.append(slot),
            ),
        )
        playlist_before = session.layers["layer_1"].playlist.paths
        user_presets_before = list(session.layers["layer_1"].user_presets)

        controller.prompt_restore("layer_1", src)
        modal.handle_keydown(keydown(pygame.K_RETURN))

        restored = pack / "demo.milk"
        assert restored.read_text(encoding="utf-8") == "bl-content"
        assert not src.exists()
        assert not (root / BLACKLIST_DIR / "demo.milk.origin").exists()
        assert "demo.milk" not in controller._index.blacklist
        assert unlocked == ["layer_1"]
        assert session.layers["layer_1"].playlist.paths == playlist_before
        assert session.layers["layer_1"].user_presets == user_presets_before


def test_confirm_restore_blacklist_without_origin_uses_choice_modal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / BLACKLIST_DIR / "demo.milk"
        _write(src, "milk")
        (root / "pack").mkdir()
        (root / "other").mkdir()
        (root / FAVOURITES_DIR).mkdir()
        unlocked: list[str] = []
        controller, _session, modal = _make_controller(
            preset_root=root,
            layer_bindings=lambda: noop_layer_bindings(
                unlock_preset_after_modal=lambda slot: unlocked.append(slot),
            ),
        )

        controller.prompt_restore("layer_1", src)
        modal.handle_keydown(keydown(pygame.K_RETURN))

        view = modal.view_state()
        assert view is not None
        assert view.message == "Restore blacklisted preset: demo.milk?"
        assert view.options == ("(root)", "other", "pack", "Cancel")
        assert unlocked == []

        modal.handle_keydown(keydown(pygame.K_RIGHT))  # other
        modal.handle_keydown(keydown(pygame.K_RETURN))

        assert (root / "other" / "demo.milk").exists()
        assert not src.exists()
        assert "demo.milk" not in controller._index.blacklist
        assert unlocked == ["layer_1"]


def test_prompt_restore_both_markers_prefers_favourite() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "pack" / "demo.milk"
        _write(src, "milk")
        _write(root / FAVOURITES_DIR / "demo.milk", "fav")
        _write(root / BLACKLIST_DIR / "demo.milk", "bl")
        controller, _session, modal = _make_controller(preset_root=root)

        controller.prompt_restore("layer_1", src)

        view = modal.view_state()
        assert view is not None
        assert view.message == "Remove favourite: demo.milk?"


def test_prompt_restore_path_under_blacklist_wins_over_favourite_marker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / BLACKLIST_DIR / "demo.milk"
        _write(src, "bl")
        _write(root / FAVOURITES_DIR / "demo.milk", "fav")
        controller, _session, modal = _make_controller(preset_root=root)

        controller.prompt_restore("layer_1", src)

        view = modal.view_state()
        assert view is not None
        assert view.message == "Restore blacklisted preset: demo.milk?"


def test_prompt_restore_neither_marker_is_noop() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "pack" / "demo.milk"
        _write(src, "milk")
        locked: list[str] = []
        controller, _session, modal = _make_controller(
            preset_root=root,
            layer_bindings=lambda: noop_layer_bindings(
                lock_preset_for_modal=lambda slot: locked.append(slot),
            ),
        )

        controller.prompt_restore("layer_1", src)

        assert modal.view_state() is None
        assert locked == []
