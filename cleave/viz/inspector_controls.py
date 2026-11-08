"""Keyboard and click editing for the shell inspector."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from cleave.viz.commands import command_by_id, command_context
from cleave.viz.inspector import InspectorRow, build_inspector_rows
from cleave.viz.row_hotkeys import handle_row_hotkey, node_control_descriptor
from cleave.choice import ChoiceKind, choice_kind
from cleave.viz.choice_list import ChoiceListState
from cleave.viz.row_spec import (
    REPEAT_ROW_KINDS,
    apply_field_action,
    apply_field_choice,
    apply_field_horizontal,
    row_spec,
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
            self._horizontal(forward=key == pygame.K_PAGEUP, large=True, event=event)
            return True
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            row = self._current_row()
            if row is not None:
                self.activate(row)
            return True
        if key == pygame.K_ESCAPE:
            self._controls.set_shell_region(ShellRegion.NAVIGATOR)
            return True
        return False

    def handle_hotkey(self, event: pygame.event.Event) -> bool:
        """Letter, Delete, and Backspace for the focused inspector row."""
        page_desc = node_control_descriptor(self._controls.shell_focus.selected_id)
        row = self._current_row()
        if row is None or row.descriptor is None:
            if page_desc is None:
                return False
            return handle_row_hotkey(self._controls, page_desc, event)
        return handle_row_hotkey(
            self._controls, row.descriptor, event, page_desc=page_desc
        )

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
        self._controls.set_shell_region(ShellRegion.INSPECTOR)
        if row.command_ids:
            self.focus_command(row, row.command_ids[0])
            return
        focus.inspector_cursor = row.descriptor
        focus.inspector_command_id = None
        if row.descriptor is not None:
            self._controls.song_markers.sync_focus(row.descriptor)

    def focus_command(self, row: InspectorRow, command_id: str) -> None:
        """Focus one button of a button row."""
        focus = self._controls.shell_focus
        self._controls.set_shell_region(ShellRegion.INSPECTOR)
        focus.inspector_cursor = None
        focus.inspector_command_id = command_id

    def activate(self, row: InspectorRow) -> None:
        if row.command_ids:
            focused = self._controls.shell_focus.inspector_command_id
            command_id = focused if focused in row.command_ids else row.command_ids[0]
            run_inspector_command(self._controls, command_id)
            return
        if row.descriptor is None:
            return
        if apply_field_action(self._controls, row.descriptor):
            return
        self.open_choice(row)

    def open_choice(self, row: InspectorRow) -> None:
        """Focus a combo row and open its list. Other rows only take focus."""
        desc = row.descriptor
        if desc is None:
            return
        self.focus_row(row)
        choice = row_spec(desc.kind).choice
        if choice is None or section_lock_blocks_mutation(self._controls.session, desc):
            return
        view = self._view()
        labels = choice.labels()
        if choice_kind(len(labels)) is not ChoiceKind.COMBO:
            return
        start = choice.index(view, desc)
        self._controls.inline_edit.begin_choice(
            ChoiceListState(
                target=desc,
                options=labels,
                start=start,
                on_pick=lambda index: apply_field_choice(
                    self._controls, desc, index - start
                ),
            )
        )

    def _horizontal(
        self,
        *,
        forward: bool,
        large: bool,
        event: pygame.event.Event,
    ) -> None:
        row = self._current_row()
        if row is not None and row.command_ids:
            self._step_button(row, forward=forward)
            return
        if row is None or row.descriptor is None:
            return
        desc = row.descriptor
        if not apply_field_horizontal(self._controls, desc, forward, large):
            return
        if desc.kind not in REPEAT_ROW_KINDS:
            return
        page = event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN)

        def on_repeat(key: int, _mod: int) -> None:
            step_forward = key in (pygame.K_RIGHT, pygame.K_PAGEUP)
            apply_field_horizontal(self._controls, desc, step_forward, page)

        self._controls.arm_key_repeat(event.key, event.mod, on_repeat=on_repeat)

    def _step_button(self, row: InspectorRow, *, forward: bool) -> None:
        """Left and Right move between the buttons of a row, stopping at the ends."""
        ids = row.command_ids
        focused = self._controls.shell_focus.inspector_command_id
        index = ids.index(focused) if focused in ids else 0
        index = max(0, min(len(ids) - 1, index + (1 if forward else -1)))
        self.focus_command(row, ids[index])

    def _current_row(self) -> InspectorRow | None:
        rows = self._navigable_rows()
        index = _cursor_index(rows, self._controls.shell_focus)
        if index is None:
            return rows[0] if rows else None
        return rows[index]

    def _navigable_rows(self) -> tuple[InspectorRow, ...]:
        view = self._view()
        rows = build_inspector_rows(view, self._controls.shell_focus.selected_id)
        return tuple(row for row in rows if row.navigable)

    def _view(self) -> TuningViewState:
        return self._controls.build_view_state(
            paused=self._controls.playback.paused
        )


def _cursor_index(rows: tuple[InspectorRow, ...], focus: ShellFocusState) -> int | None:
    for index, row in enumerate(rows):
        if row.command_ids:
            if focus.inspector_command_id in row.command_ids:
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


def inspector_command_locked(controls: TuningControls, command_id: str) -> bool:
    command = command_by_id(command_id)
    return bool(command.locked(command_context(controls)))


def run_inspector_command(controls: TuningControls, command_id: str) -> None:
    if not inspector_command_enabled(controls, command_id):
        return
    command_by_id(command_id).run(controls)
