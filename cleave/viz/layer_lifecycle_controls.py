"""Layer add/delete, z-order move mode, and preview resolution for live tuning."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.modal import ModalHost
from cleave.viz.session import TuningSession

if TYPE_CHECKING:
    from cleave.viz.wiring import LayerManager


class LayerLifecycleController:
    """Mutations for adding, removing, and reordering layers."""

    def __init__(
        self,
        session: TuningSession,
        layer_manager: LayerManager | None,
        modal_host: ModalHost,
        layer_bindings: LiveLayerBindings | None,
        *,
        on_rebuild_view: Callable[[], None] | None = None,
        on_notification: Callable[[str], None] | None = None,
        on_focus_after_add: Callable[[], None] | None = None,
        on_capture_delete_nav: Callable[[], int] | None = None,
        on_restore_delete_focus: Callable[[int], None] | None = None,
    ) -> None:
        self.session = session
        self._layer_manager = layer_manager
        self._modal = modal_host
        self._layer_bindings = layer_bindings
        self._on_rebuild_view = on_rebuild_view
        self._on_notification = on_notification
        self._on_focus_after_add = on_focus_after_add
        self._on_capture_delete_nav = on_capture_delete_nav
        self._on_restore_delete_focus = on_restore_delete_focus
        self.move_mode_slot: str | None = None
        self._move_mode_original_z_order: list[str] | None = None

    def apply_preview_resolutions(self) -> None:
        if self._layer_manager is not None:
            self._layer_manager.apply_preview_resolutions()

    def signature_payload(self) -> dict[str, list[str]] | None:
        if (
            self.move_mode_slot is not None
            and self._move_mode_original_z_order is not None
        ):
            return {"layer_z_order": list(self._move_mode_original_z_order)}
        return None

    def enter_move_mode(self, slot: str) -> None:
        self._move_mode_original_z_order = list(self.session.layer_z_order)
        self.move_mode_slot = slot

    def swap_stem_in_z_order(self, stem: str, direction: int) -> None:
        order = self.session.layer_z_order
        try:
            index = order.index(stem)
        except ValueError:
            return
        target = index + direction
        if target < 0 or target >= len(order):
            return
        order[index], order[target] = order[target], order[index]
        self.apply_preview_resolutions()

    def confirm_move_mode(self) -> None:
        self.move_mode_slot = None
        self._move_mode_original_z_order = None

    def cancel_move_mode(self) -> None:
        if self._move_mode_original_z_order is not None:
            self.session.layer_z_order[:] = self._move_mode_original_z_order
            self.apply_preview_resolutions()
        self.move_mode_slot = None
        self._move_mode_original_z_order = None

    def prompt_add(self) -> None:
        if self._layer_manager is None:
            return
        if not self._layer_manager.can_add():
            return
        self._modal.prompt_yes_no(
            "Add new Milkdrop visualisation layer?",
            on_confirm=self.confirm_add,
        )

    def confirm_add(self) -> None:
        if self._layer_manager is None:
            return
        self._layer_manager.add_layer()
        if self._on_rebuild_view is not None:
            self._on_rebuild_view()
        if self._on_focus_after_add is not None:
            self._on_focus_after_add()

    def prompt_delete(self, slot: str) -> None:
        if self._layer_manager is None:
            return
        if not self._layer_manager.can_remove():
            if self._on_notification is not None:
                self._on_notification("Must have at least 1 layer")
            return
        self._modal.prompt_yes_no(
            "Delete this Milkdrop visualisation layer?",
            on_confirm=lambda: self.confirm_delete(slot),
        )

    def confirm_delete(self, slot: str) -> None:
        if self._layer_manager is None:
            return
        nav_pos = (
            self._on_capture_delete_nav()
            if self._on_capture_delete_nav is not None
            else 0
        )
        self._layer_manager.remove_layer(slot)
        if self._on_rebuild_view is not None:
            self._on_rebuild_view()
        if self._on_restore_delete_focus is not None:
            self._on_restore_delete_focus(nav_pos)
