"""Keyboard and click selection for the shell navigator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from cleave.viz.focus_nav import MainFocus
from cleave.viz.inspector import InspectorRow, build_inspector_rows
from cleave.viz.navigator import NavNode, build_navigator, visible_top_level_ids
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.row_layout import first_leftover_descriptor, row_navigable
from cleave.viz.shell_focus import ShellRegion, escape_region, quick_nav_id

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls
    from cleave.viz.tuning_view_state import TuningViewState


class NavigatorControls:
    """Up/Down, Enter, and Esc while the navigator region is active."""

    def __init__(self, controls: TuningControls) -> None:
        self._controls = controls

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        """Consume navigator keys. Unowned keys return False."""
        key = event.key
        if key in (pygame.K_UP, pygame.K_DOWN):
            delta = -1 if key == pygame.K_UP else 1
            self.quick_step(delta)
            self._controls.arm_key_repeat(
                key,
                event.mod,
                accel=False,
                on_repeat=lambda repeat_key, _mod: self.quick_step(
                    -1 if repeat_key == pygame.K_UP else 1
                ),
            )
            return True
        if key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            return True
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.activate()
            return True
        if key == pygame.K_ESCAPE:
            self.escape()
            return True
        return False

    def quick_step(self, delta: int) -> None:
        """Select the next visible top-level id and stay on the navigator."""
        focus = self._controls.shell_focus
        ids = visible_top_level_ids(self._controls.session)
        self.select(quick_nav_id(ids, focus.selected_id, delta))

    def select(self, node_id: str) -> None:
        """Select *node_id*, stay on the navigator, and scroll unmigrated sections."""
        focus = self._controls.shell_focus
        focus.region = ShellRegion.NAVIGATOR
        focus.selected_id = node_id
        node = self._node(node_id)
        if node is not None and not node.has_inspector:
            self._focus_leftover_header(node_id)

    def activate(self) -> None:
        """Enter: inspector for migrated nodes, leftover header for the rest."""
        focus = self._controls.shell_focus
        node = self._node(focus.selected_id)
        if node is None:
            return
        if node.has_inspector:
            self._enter_inspector(node.id)
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
        rows = build_inspector_rows(view, node_id, focus.collapsed)
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
        layout = view.layout
        if node_id == "render":
            desc = RowDescriptor(RowKind.RENDER_OVERLAYS_HEADER)
        elif node_id == "layers":
            if not view.layer_z_order:
                return None
            desc = RowDescriptor(RowKind.TRACK_HEADER, slot=view.layer_z_order[0])
        elif node_id == "song_markers":
            desc = RowDescriptor(RowKind.SONG_MARKERS_HEADER)
            if not layout.contains_descriptor(desc):
                desc = RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)
        else:
            return None
        if layout.contains_descriptor(desc):
            return desc
        return None

    def _node(self, node_id: str) -> NavNode | None:
        for node in build_navigator(self._controls.session):
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
