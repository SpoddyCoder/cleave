"""Tests for preset favourites and blacklist modal orchestration."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pygame

from cleave.preset_curation import BLACKLIST_DIR, FAVOURITES_DIR
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
        assert session.layers["layer_1"].playlist.paths == ()
        assert preset_changes == [("layer_1", 0)]
        assert switching_changes == ["layer_1"]
        assert session.layers["layer_1"].user_presets == []


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
