"""Keyboard and click editing for the shell inspector."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from cleave.viz.commands import command_by_id, command_context
from cleave.viz.inspector import InspectorRow, build_inspector_rows
from cleave.viz.row_kinds import RowKind
from cleave.viz.row_spec import (
    REPEAT_ROW_KINDS,
    apply_field_action,
    apply_field_horizontal,
    section_lock_blocks_mutation,
)
from cleave.viz.shell_focus import ShellFocusState, ShellRegion

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls
    from cleave.viz.tuning_view_state import TuningViewState


class InspectorControls:
    """Arrows, Enter, and Esc while the inspector region is active."""

    def __init__(self, controls: TuningControls) -> None:
        self._controls = controls

    def handle_keydown(self, event: pygame.event.Event) -> bool:
        key = event.key
        if key in (pygame.K_UP, pygame.K_DOWN):
            delta = -1 if key == pygame.K_UP else 1
            self.move(delta)
            self._controls.arm_key_repeat(
                key,
                event.mod,
                accel=False,
                on_repeat=lambda repeat_key, _mod: self.move(
                    -1 if repeat_key == pygame.K_UP else 1
                ),
            )
            return True
        if key in (pygame.K_LEFT, pygame.K_RIGHT):
            self._horizontal(forward=key == pygame.K_RIGHT, large=False, event=event)
            return True
        if key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            self._horizontal(forward=key == pygame.K_PAGEDOWN, large=True, event=event)
            return True
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            row = self._current_row()
            if row is not None:
                self.activate(row)
            return True
        if key == pygame.K_ESCAPE:
            self._controls.shell_focus.region = ShellRegion.NAVIGATOR
            return True
        return False

    def move(self, delta: int) -> None:
        rows = self._navigable_rows()
        if not rows:
            return
        index = _cursor_index(rows, self._controls.shell_focus)
        if index is None:
            index = 0 if delta > 0 else len(rows) - 1
        else:
            index = (index + delta) % len(rows)
        self.focus_row(rows[index])

    def focus_row(self, row: InspectorRow) -> None:
        focus = self._controls.shell_focus
        focus.region = ShellRegion.INSPECTOR
        if row.command_id is not None:
            focus.inspector_cursor = None
            focus.inspector_command_id = row.command_id
            return
        focus.inspector_cursor = row.descriptor
        focus.inspector_command_id = None

    def toggle_group(self, kind: RowKind) -> None:
        collapsed = self._controls.shell_focus.collapsed
        if kind in collapsed:
            collapsed.discard(kind)
        else:
            collapsed.add(kind)

    def activate(self, row: InspectorRow) -> None:
        if row.command_id is not None:
            run_inspector_command(self._controls, row.command_id)
            return
        if row.descriptor is not None:
            apply_field_action(self._controls, row.descriptor)

    def _horizontal(
        self,
        *,
        forward: bool,
        large: bool,
        event: pygame.event.Event,
    ) -> None:
        row = self._current_row()
        if row is None or row.descriptor is None:
            return
        if row.is_group:
            if not large:
                self.toggle_group(row.descriptor.kind)
            return
        desc = row.descriptor
        if section_lock_blocks_mutation(self._controls.session, desc):
            return
        apply_field_horizontal(self._controls, desc, forward, large)
        if desc.kind not in REPEAT_ROW_KINDS:
            return
        page = event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN)

        def on_repeat(key: int, _mod: int) -> None:
            if section_lock_blocks_mutation(self._controls.session, desc):
                return
            step_forward = key in (pygame.K_RIGHT, pygame.K_PAGEDOWN)
            apply_field_horizontal(self._controls, desc, step_forward, page)

        self._controls.arm_key_repeat(event.key, event.mod, on_repeat=on_repeat)

    def _current_row(self) -> InspectorRow | None:
        rows = self._navigable_rows()
        index = _cursor_index(rows, self._controls.shell_focus)
        if index is None:
            return rows[0] if rows else None
        return rows[index]

    def _navigable_rows(self) -> tuple[InspectorRow, ...]:
        view = self._view()
        focus = self._controls.shell_focus
        rows = build_inspector_rows(view, focus.selected_id, focus.collapsed)
        return tuple(row for row in rows if row.navigable)

    def _view(self) -> TuningViewState:
        return self._controls.build_view_state(
            paused=self._controls.playback.paused
        )


def _cursor_index(rows: tuple[InspectorRow, ...], focus: ShellFocusState) -> int | None:
    for index, row in enumerate(rows):
        if row.command_id is not None:
            if focus.inspector_command_id == row.command_id:
                return index
            continue
        if (
            focus.inspector_command_id is None
            and focus.inspector_cursor == row.descriptor
        ):
            return index
    return None


def inspector_command_enabled(controls: TuningControls, command_id: str) -> bool:
    command = command_by_id(command_id)
    return bool(command.enabled(command_context(controls)))


def run_inspector_command(controls: TuningControls, command_id: str) -> None:
    if not inspector_command_enabled(controls, command_id):
        return
    command_by_id(command_id).run(controls)
