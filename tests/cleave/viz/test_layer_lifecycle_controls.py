"""Tests for layer add/delete and z-order move-mode controller."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from cleave.preset_playlist import PresetPlaylist
from cleave.viz.layer_lifecycle_controls import LayerLifecycleController
from cleave.viz.modal import ModalHost
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.viz import keydown, noop_layer_bindings

import pygame


def _make_controller(
    slots: tuple[str, ...] = ("layer_1", "layer_2"),
    *,
    can_add: bool = True,
    can_remove: bool = True,
    on_rebuild_view=None,
    on_notification=None,
    on_focus_after_add=None,
    on_capture_delete_nav=None,
    on_restore_delete_focus=None,
) -> tuple[LayerLifecycleController, TuningSession, ModalHost, MagicMock]:
    session = TuningSession(
        layer_z_order=list(slots),
        layers={
            slot: LayerRuntime(
                playlist=PresetPlaylist(
                    current_dir=Path(f"/tmp/presets/{slot}"),
                    paths=(Path(f"/tmp/presets/{slot}/preset-0.milk"),),
                    index=0,
                ),
                browse_floor=Path(f"/tmp/presets/{slot}"),
                stem="drums",
                opacity_pct=50,
            )
            for slot in slots
        },
    )
    modal = ModalHost()
    manager = MagicMock()
    manager.can_add.return_value = can_add
    manager.can_remove.return_value = can_remove
    controller = LayerLifecycleController(
        session,
        manager,
        modal,
        noop_layer_bindings(),
        on_rebuild_view=on_rebuild_view,
        on_notification=on_notification,
        on_focus_after_add=on_focus_after_add,
        on_capture_delete_nav=on_capture_delete_nav,
        on_restore_delete_focus=on_restore_delete_focus,
    )
    return controller, session, modal, manager


def test_prompt_add_opens_confirm_and_confirm_calls_manager() -> None:
    rebuilt: list[str] = []
    focused: list[str] = []
    controller, _session, modal, manager = _make_controller(
        on_rebuild_view=lambda: rebuilt.append("rebuild"),
        on_focus_after_add=lambda: focused.append("focus"),
    )
    controller.prompt_add()
    view = modal.view_state()
    assert view is not None
    assert view.message == "Add new Milkdrop visualisation layer?"
    modal.handle_keydown(keydown(pygame.K_RETURN))
    manager.add_layer.assert_called_once()
    assert rebuilt == ["rebuild"]
    assert focused == ["focus"]


def test_prompt_add_skipped_when_cannot_add() -> None:
    controller, _session, modal, manager = _make_controller(can_add=False)
    controller.prompt_add()
    assert modal.view_state() is None
    manager.add_layer.assert_not_called()


def test_prompt_delete_toasts_at_min() -> None:
    notes: list[str] = []
    controller, _session, modal, manager = _make_controller(
        ("layer_1",),
        can_remove=False,
        on_notification=notes.append,
    )
    controller.prompt_delete("layer_1")
    assert modal.view_state() is None
    manager.remove_layer.assert_not_called()
    assert notes == ["Must have at least 1 layer"]


def test_confirm_delete_rebuilds_and_restores_focus() -> None:
    restored: list[int] = []
    rebuilt: list[str] = []
    controller, _session, modal, manager = _make_controller(
        on_rebuild_view=lambda: rebuilt.append("rebuild"),
        on_capture_delete_nav=lambda: 3,
        on_restore_delete_focus=lambda pos: restored.append(pos),
    )
    controller.prompt_delete("layer_2")
    modal.handle_keydown(keydown(pygame.K_RETURN))
    manager.remove_layer.assert_called_once_with("layer_2")
    assert rebuilt == ["rebuild"]
    assert restored == [3]


def test_enter_and_swap_move_mode() -> None:
    controller, session, _modal, manager = _make_controller(
        ("layer_1", "layer_2", "layer_3")
    )
    controller.enter_move_mode("layer_2")
    assert controller.move_mode_slot == "layer_2"
    assert controller.signature_payload() == {
        "layer_z_order": ["layer_1", "layer_2", "layer_3"]
    }
    controller.swap_stem_in_z_order("layer_2", -1)
    assert session.layer_z_order == ["layer_2", "layer_1", "layer_3"]
    manager.apply_preview_resolutions.assert_called_once()


def test_cancel_move_mode_restores_z_order() -> None:
    controller, session, _modal, manager = _make_controller(
        ("layer_1", "layer_2", "layer_3")
    )
    controller.enter_move_mode("layer_2")
    controller.swap_stem_in_z_order("layer_2", -1)
    manager.apply_preview_resolutions.reset_mock()
    controller.cancel_move_mode()
    assert session.layer_z_order == ["layer_1", "layer_2", "layer_3"]
    assert controller.move_mode_slot is None
    assert controller.signature_payload() is None
    manager.apply_preview_resolutions.assert_called_once()


def test_confirm_move_mode_keeps_z_order() -> None:
    controller, session, _modal, _manager = _make_controller(
        ("layer_1", "layer_2", "layer_3")
    )
    controller.enter_move_mode("layer_2")
    controller.swap_stem_in_z_order("layer_2", -1)
    controller.confirm_move_mode()
    assert session.layer_z_order == ["layer_2", "layer_1", "layer_3"]
    assert controller.move_mode_slot is None
    assert controller.signature_payload() is None


def test_apply_preview_resolutions_noops_without_manager() -> None:
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={
            "layer_1": LayerRuntime(
                playlist=PresetPlaylist(
                    current_dir=Path("/tmp/presets/layer_1"),
                    paths=(Path("/tmp/presets/layer_1/preset-0.milk"),),
                    index=0,
                ),
                browse_floor=Path("/tmp/presets/layer_1"),
                stem="drums",
            )
        },
    )
    controller = LayerLifecycleController(
        session, None, ModalHost(), None
    )
    controller.apply_preview_resolutions()
