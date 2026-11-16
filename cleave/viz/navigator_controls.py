"""Keyboard and click selection for the shell navigator."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pygame

from cleave.viz.config_pages import available_config_page_ids
from cleave.viz.inspector import InspectorRow, build_inspector_rows
from cleave.viz.navigator import (
    NavNode,
    all_navigator_ids,
    ancestor_ids,
    build_navigator,
    root_id,
    timeline_row_node_id,
    timeline_row_slot_of,
    visible_top_level_ids,
)
from cleave.viz.row_hotkeys import handle_row_hotkey, node_control_descriptor
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
        return False

    def handle_hotkey(self, event: pygame.event.Event) -> bool:
        """Letter, Delete, and Backspace for the selected navigator page."""
        header = node_control_descriptor(self._controls.shell_focus.selected_id)
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
        repaired = reconcile_nav_id(
            self._visible_ids(),
            focus.selected_id,
            self._controls.session.layer_z_order,
            prior_index=prior,
            pages=self._pages(),
        )
        if repaired != focus.selected_id:
            focus.nav_expanded |= ancestor_ids(repaired)
            focus.selected_id = repaired

    def quick_step(self, delta: int) -> None:
        """Select the next visible top-level id and stay on the navigator."""
        self.reconcile()
        focus = self._controls.shell_focus
        ids = visible_top_level_ids(self._controls.session)
        self.select(quick_nav_id(ids, root_id(focus.selected_id), delta))

    def select(self, node_id: str) -> None:
        """Select *node_id*, open its ancestors, and stay on the navigator."""
        focus = self._controls.shell_focus
        focus.nav_expanded |= ancestor_ids(node_id)
        node_id = reconcile_nav_id(
            self._visible_ids(),
            node_id,
            self._controls.session.layer_z_order,
        )
        focus.nav_expanded |= ancestor_ids(node_id)
        self._controls.set_shell_region(ShellRegion.NAVIGATOR)
        focus.selected_id = node_id

    def activate(self) -> None:
        """Open the selected node's inspector.

        A page with no rows keeps focus on the navigator.
        """
        node = self._node(self._controls.shell_focus.selected_id)
        if node is None:
            return
        self._enter_inspector(node.id)

    def open_page(self, page_id: str) -> None:
        """Show a Settings or Project page in the inspector.

        The page has no navigator row, so no row is selected and no node
        opens. Focus moves into the inspector when the page has rows.
        """
        focus = self._controls.shell_focus
        focus.selected_id = page_id
        self._controls.set_shell_region(ShellRegion.NAVIGATOR)
        self._enter_inspector(page_id)

    def page_filter(self) -> Callable[[str], bool]:
        """Test for a page id that history may still show.

        Config pages follow the editor mode, a strip row page needs its layer
        and the open strip, and a navigator page needs its node to exist once
        its ancestors open.
        """
        shown = set(self._pages()) | all_navigator_ids(self._controls.session)
        return shown.__contains__

    def can_go_back(self) -> bool:
        return self._controls.page_history.peek_back(self.page_filter()) is not None

    def can_go_forward(self) -> bool:
        history = self._controls.page_history
        return history.peek_forward(self.page_filter()) is not None

    def go_back(self) -> None:
        """Show the previous page in the history."""
        page_id = self._controls.page_history.back(self.page_filter())
        if page_id is not None:
            self._show_history_page(page_id)

    def go_forward(self) -> None:
        """Show the next page in the history."""
        page_id = self._controls.page_history.forward(self.page_filter())
        if page_id is not None:
            self._show_history_page(page_id)

    def _show_history_page(self, page_id: str) -> None:
        """Select *page_id* and keep the focus region where it is.

        The inspector cursor moves to the page's first row, or focus returns
        to the navigator when the page has none. A strip row page moves the
        strip lane with it; any other page takes focus off the strip.
        """
        controls = self._controls
        focus = controls.shell_focus
        focus.nav_expanded |= ancestor_ids(page_id)
        slot = timeline_row_slot_of(page_id)
        if slot is not None:
            focus.selected_id = page_id
            controls.set_timeline_focus_row(
                controls.session.layer_z_order.index(slot)
            )
        else:
            if focus.region is ShellRegion.TIMELINE:
                controls.set_shell_region(ShellRegion.NAVIGATOR)
            focus.selected_id = page_id
        if focus.region is not ShellRegion.INSPECTOR:
            return
        rows = build_inspector_rows(self._view(), page_id)
        first = next((row for row in rows if row.navigable), None)
        if first is None:
            controls.set_shell_region(ShellRegion.NAVIGATOR)
            return
        _set_inspector_cursor(focus, first)

    def _enter_inspector(self, node_id: str) -> None:
        focus = self._controls.shell_focus
        view = self._view()
        rows = build_inspector_rows(view, node_id)
        first = next((row for row in rows if row.navigable), None)
        if first is None:
            return
        self._controls.set_shell_region(ShellRegion.INSPECTOR)
        _set_inspector_cursor(focus, first)

    def _tree_step(self, delta: int) -> None:
        focus = self._controls.shell_focus
        if timeline_row_slot_of(focus.selected_id) is not None:
            # A strip row has no navigator row; arrows start from Timeline.
            self.select("timeline")
            return
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

    def _pages(self) -> tuple[str, ...]:
        """Inspector pages with no navigator row: config pages and strip rows."""
        session = self._controls.session
        pages = available_config_page_ids(session.settings.editor_mode)
        if not session.timeline.panel_open:
            return pages
        return pages + tuple(
            timeline_row_node_id(slot) for slot in session.layer_z_order
        )

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


def _set_inspector_cursor(focus, row: InspectorRow) -> None:
    if row.command_ids:
        focus.inspector_cursor = None
        focus.inspector_command_id = row.command_ids[0]
        return
    focus.inspector_cursor = row.descriptor
    focus.inspector_command_id = None
