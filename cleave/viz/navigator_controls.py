"""Keyboard and click selection for the shell navigator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.focus_nav import MainFocus
from cleave.viz.inspector import InspectorRow, build_inspector_rows
from cleave.viz.navigator import NavNode, build_navigator, visible_top_level_ids
from cleave.viz.row_hotkeys import handle_row_hotkey, node_header_descriptor
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_layout import first_leftover_descriptor, row_navigable
from cleave.viz.shell_focus import (
    ShellRegion,
    escape_region,
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
            if is_preset_curation_mode(self._controls.session.settings.editor_mode):
                self._controls.request_hide_overlay()
                return True
            self.escape()
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
        """Select *node_id* and stay on the navigator.

        A node with no inspector that cannot expand scrolls the leftover
        panel to its header.
        """
        focus = self._controls.shell_focus
        node_id = reconcile_nav_id(
            self._visible_ids(),
            node_id,
            self._controls.session.layer_z_order,
        )
        focus.region = ShellRegion.NAVIGATOR
        focus.selected_id = node_id
        node = self._node(node_id)
        if node is not None and not node.has_inspector and not node.expandable:
            self._focus_leftover_header(node_id)

    def activate(self) -> None:
        """Open an inspector, or hand a leaf without one to the leftover panel.

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
        if node.expandable:
            focus.nav_expanded.add(node.id)
            child = self._first_child(node.id)
            if child is not None:
                focus.selected_id = child.id
                self._enter_inspector(child.id)
                return
        focus.region = ShellRegion.PANEL
        self._focus_leftover_header(node.id)

    def escape(self) -> None:
        """Leave the navigator for the panel when leftover rows are navigable."""
        focus = self._controls.shell_focus
        view = self._view()
        target = escape_region(
            focus.region,
            leftover_rows=self._has_navigable_leftover(view),
        )
        if target is not ShellRegion.PANEL:
            return
        focus.region = ShellRegion.PANEL
        header = self._header_for(view, focus.selected_id)
        if header is None:
            header = first_leftover_descriptor(view)
        self._controls.focus_cursor = MainFocus(header)

    def _enter_inspector(self, node_id: str) -> None:
        focus = self._controls.shell_focus
        view = self._view()
        rows = build_inspector_rows(
            view, node_id, focus.collapsed, focus.opened
        )
        focus.region = ShellRegion.INSPECTOR
        first = next((row for row in rows if row.navigable), None)
        _set_inspector_cursor(focus, first)

    def _focus_leftover_header(self, node_id: str) -> None:
        view = self._view()
        header = self._header_for(view, node_id)
        if header is None:
            header = first_leftover_descriptor(view)
        self._controls.focus_cursor = MainFocus(header)

    def _header_for(
        self, view: TuningViewState, node_id: str
    ) -> RowDescriptor | None:
        if node_id != "song_markers":
            return None
        layout = view.layout
        desc = RowDescriptor(RowKind.SONG_MARKERS_HEADER)
        if not layout.contains_descriptor(desc):
            desc = RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
        if layout.contains_descriptor(desc):
            return desc
        return None

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

    @staticmethod
    def _has_navigable_leftover(view: TuningViewState) -> bool:
        return any(row_navigable(view, desc) for desc in view.layout.rows)


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
