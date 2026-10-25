"""Keyboard and click selection for the shell navigator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from cleave.viz.inspector import InspectorRow, build_inspector_rows
from cleave.viz.navigator import NavNode, build_navigator, visible_top_level_ids
from cleave.viz.row_hotkeys import handle_row_hotkey, node_header_descriptor
from cleave.viz.shell_focus import (
    ShellRegion,
    quick_nav_id,
    reconcile_nav_id,
    tree_nav_id,
)

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls
    from cleave.viz.tuning_view_state import TuningViewState


class NavigatorControls:
    """Tree keys, Enter, and Esc while the navigator region is active."""

    def __init__(self, controls: TuningControls) -> None:
        self._controls = controls

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Consume navigator keys. Unowned keys return False."""
        key = event.key
        if key in (pygame.K_UP, pygame.K_DOWN):
            self.reconcile()
            delta = -1 if key == pygame.K_UP else 1
            self._tree_step(delta)
            self._controls.arm_key_repeat(
                key,
                event.mod,
                accel=False,
                on_repeat=lambda repeat_key, _mod: self._tree_step(
                    -1 if repeat_key == pygame.K_UP else 1
                ),
            )
            return True
        if key in (pygame.K_LEFT, pygame.K_RIGHT):
            self.reconcile()
            self._horizontal(key)
            return True
        if key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            self.reconcile()
            return True
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.reconcile()
            self.activate()
            return True
        if key == pygame.K_ESCAPE:
            self.reconcile()
            self._controls.request_hide_overlay()
            return True
        return False

    def handle_hotkey(self, event: pygame.event.Event) -> bool:
        """Letter, Delete, and Backspace for a selected layer or render node."""
        header = node_header_descriptor(self._controls.shell_focus.selected_id)
        if header is None:
            return False
        return handle_row_hotkey(
            self._controls, header, event, page_desc=header
        )

    def reconcile(self) -> None:
        """Repair a selected id that is no longer a visible navigator row."""
        focus = self._controls.shell_focus
        lifecycle = self._controls.layer_lifecycle
        prior = lifecycle.removed_layer_index
        lifecycle.removed_layer_index = None
        focus.selected_id = reconcile_nav_id(
            self._visible_ids(),
            focus.selected_id,
            self._controls.session.layer_z_order,
            prior_index=prior,
        )

    def quick_step(self, delta: int) -> None:
        """Select the next visible top-level id and stay on the navigator."""
        self.reconcile()
        focus = self._controls.shell_focus
        ids = visible_top_level_ids(self._controls.session)
        self.select(quick_nav_id(ids, focus.selected_id, delta))

    def select(self, node_id: str) -> None:
        """Select *node_id* and stay on the navigator."""
        focus = self._controls.shell_focus
        node_id = reconcile_nav_id(
            self._visible_ids(),
            node_id,
            self._controls.session.layer_z_order,
        )
        self._controls.set_shell_region(ShellRegion.NAVIGATOR)
        focus.selected_id = node_id

    def activate(self) -> None:
        """Open an inspector.

        An expandable node with no inspector expands and opens its first
        child's inspector.
        """
        focus = self._controls.shell_focus
        node = self._node(focus.selected_id)
        if node is None:
            return
        if node.has_inspector:
            self._enter_inspector(node.id)
            return
        if not node.expandable:
            return
        focus.nav_expanded.add(node.id)
        child = self._first_child(node.id)
        if child is None:
            return
        focus.selected_id = child.id
        self._enter_inspector(child.id)

    def _enter_inspector(self, node_id: str) -> None:
        focus = self._controls.shell_focus
        view = self._view()
        rows = build_inspector_rows(
            view, node_id, focus.collapsed, focus.opened
        )
        self._controls.set_shell_region(ShellRegion.INSPECTOR)
        first = next((row for row in rows if row.navigable), None)
        _set_inspector_cursor(focus, first)

    def _tree_step(self, delta: int) -> None:
        focus = self._controls.shell_focus
        self.select(tree_nav_id(self._visible_ids(), focus.selected_id, delta))

    def _horizontal(self, key: int) -> None:
        node = self._node(self._controls.shell_focus.selected_id)
        if node is None:
            return
        if key == pygame.K_RIGHT:
            self._expand_or_enter(node)
            return
        self._collapse_or_parent(node)

    def _expand_or_enter(self, node: NavNode) -> None:
        if not node.expandable:
            return
        focus = self._controls.shell_focus
        if node.id not in focus.nav_expanded:
            focus.nav_expanded.add(node.id)
            return
        child = self._first_child(node.id)
        if child is not None:
            self.select(child.id)

    def _collapse_or_parent(self, node: NavNode) -> None:
        focus = self._controls.shell_focus
        if node.expandable and node.id in focus.nav_expanded:
            focus.nav_expanded.discard(node.id)
            return
        if node.parent_id is not None:
            self.select(node.parent_id)

    def _first_child(self, parent_id: str) -> NavNode | None:
        for node in self._nodes():
            if node.parent_id == parent_id:
                return node
        return None

    def _visible_ids(self) -> tuple[str, ...]:
        return tuple(node.id for node in self._nodes())

    def _nodes(self) -> tuple[NavNode, ...]:
        return build_navigator(
            self._controls.session,
            self._controls.shell_focus.nav_expanded,
        )

    def _node(self, node_id: str) -> NavNode | None:
        for node in self._nodes():
            if node.id == node_id:
                return node
        return None

    def _view(self) -> TuningViewState:
        playback = self._controls.playback
        return self._controls.build_view_state(paused=playback.paused)


def _set_inspector_cursor(focus, row: InspectorRow | None) -> None:
    if row is None:
        focus.inspector_cursor = None
        focus.inspector_command_id = None
        return
    if row.command_id is not None:
        focus.inspector_cursor = None
        focus.inspector_command_id = row.command_id
        return
    focus.inspector_cursor = row.descriptor
    focus.inspector_command_id = None
