"""What the shell's region modules share: the frame's inputs and its derived state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cleave.viz.commands import CommandContext
    from cleave.viz.controls import TuningControls
    from cleave.viz.menu_bar import MenuBarState
    from cleave.viz.navigator import NavNode
    from cleave.viz.shell_layout import ShellLayout
    from cleave.viz.top_layer import TopLayer
    from cleave.viz.tuning_view_state import TuningViewState


@dataclass
class ShellContext:
    """The controller and window state every shell region draws against.

    ``layout`` is the frame's shell rects, None before the first layout.
    ``command_ctx`` is the context the caller built for this frame.
    """

    controls: TuningControls
    menu_state: MenuBarState
    top_layer: TopLayer
    layout: ShellLayout | None = None
    command_ctx: CommandContext | None = None

    def modal_has_pointer(self) -> bool:
        """True while a modal owns the pointer, drawn yet or not."""
        return bool(self.top_layer.modal_active) or bool(
            self.controls.modal_host.active
        )

    def choice_list_open(self) -> bool:
        return self.controls.inline_edit.choice_view is not None

    def input_blocked(self) -> bool:
        """True while a modal, an open combo list, or a context menu takes the pointer."""
        return (
            self.modal_has_pointer()
            or self.choice_list_open()
            or self.controls.context_menu.is_open
        )


@dataclass(frozen=True)
class ShellFrame:
    """What one shell frame draws from, built once so every panel agrees.

    ``nav_nodes`` are the navigator's visible rows. ``command_ctx`` carries
    the unsaved-changes flag and the page history targets.
    """

    view_state: TuningViewState
    nav_nodes: tuple[NavNode, ...]
    command_ctx: CommandContext
