"""Right-click menu for a navigator row.

Expand or collapse the row, and flip its on/off, solo, and lock icons.
The right-click has already selected the row, so its page shows in the
inspector. A layer row adds a page jump, move up and
down, and add and delete layer. Each item calls the same path as its icon
or key, and a disabled item says why in its hint.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from cleave.viz.commands import command_by_id, command_context
from cleave.viz.context_menu import (
    CONTEXT_SEPARATOR,
    ContextMenuEntry,
    ContextMenuItem,
    ContextMenuProvider,
    ContextSubmenu,
)
from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.navigator import (
    TOGGLE_ADD,
    TOGGLE_ENABLED,
    TOGGLE_LOCK,
    TOGGLE_SOLO,
    NavNode,
    NavToggle,
    build_navigator,
    layer_page_nodes,
)
from cleave.viz.row_hotkeys import activate_header_toggle, node_control_descriptor

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

_TOGGLE_ITEMS: dict[str, tuple[str, str]] = {
    TOGGLE_ENABLED: ("Enabled", "E"),
    TOGGLE_SOLO: ("Solo", "S"),
    TOGGLE_LOCK: ("Locked", "L"),
}


def navigator_node_menu(
    controls: TuningControls,
    node_id: str,
    toggle_expanded: Callable[[str], None],
) -> ContextMenuProvider:
    """Provider for *node_id*'s menu; empty once the row is gone.

    *toggle_expanded* opens or closes a row as its twisty does.
    """

    def entries() -> tuple[ContextMenuEntry, ...]:
        return navigator_node_menu_entries(controls, node_id, toggle_expanded)

    return entries


def navigator_node_menu_entries(
    controls: TuningControls,
    node_id: str,
    toggle_expanded: Callable[[str], None],
) -> tuple[ContextMenuEntry, ...]:
    focus = controls.shell_focus
    node = next(
        (
            candidate
            for candidate in build_navigator(controls.session, focus.nav_expanded)
            if candidate.id == node_id
        ),
        None,
    )
    if node is None:
        return ()
    groups: list[tuple[ContextMenuEntry, ...]] = [
        _tree_items(controls, node, toggle_expanded),
        _toggle_items(controls, node),
    ]
    if _is_layer_row(controls, node):
        groups.append(_layer_items(controls, node))
    return _join(groups)


def _tree_items(
    controls: TuningControls,
    node: NavNode,
    toggle_expanded: Callable[[str], None],
) -> tuple[ContextMenuEntry, ...]:
    items: list[ContextMenuEntry] = []
    if node.expandable:
        expanded = node.id in controls.shell_focus.nav_expanded
        items.append(
            ContextMenuItem(
                id="navigator.expand",
                label="Collapse" if expanded else "Expand",
                run=lambda: toggle_expanded(node.id),
                shortcut="Left" if expanded else "Right",
            )
        )
    if node.slot is not None and _is_layer_row(controls, node):
        pages = layer_page_nodes(controls.session, node.slot)
        items.append(
            ContextSubmenu(
                id="navigator.go_to",
                label="Go to page",
                items=tuple(_go_to_item(controls, page) for page in pages),
            )
        )
    return tuple(items)


def _go_to_item(controls: TuningControls, page: NavNode) -> ContextMenuItem:
    def run() -> None:
        controls.navigator.select(page.id)
        controls.navigator.activate()

    return ContextMenuItem(id=f"navigator.go_to.{page.id}", label=page.label, run=run)


def _toggle_items(
    controls: TuningControls, node: NavNode
) -> tuple[ContextMenuEntry, ...]:
    descriptor = node_control_descriptor(node.id)
    items: list[ContextMenuEntry] = []
    for toggle in node.toggles:
        if toggle.id == TOGGLE_ADD:
            items.append(_add_item(controls, blocked=toggle.blocked))
            continue
        label_key = _TOGGLE_ITEMS.get(toggle.id)
        if label_key is None or descriptor is None:
            continue
        label, key = label_key
        hint = _toggle_hint(toggle)
        items.append(
            ContextMenuItem(
                id=f"navigator.toggle.{toggle.id}",
                label=label,
                run=lambda toggle_id=toggle.id: activate_header_toggle(
                    controls, toggle_id, descriptor
                ),
                enabled=hint is None,
                checked=toggle.active,
                shortcut=key,
                hint=hint,
            )
        )
    return tuple(items)


def _toggle_hint(toggle: NavToggle) -> str | None:
    if toggle.blocked:
        return "Locked: unlock to change"
    if toggle.inert:
        return "Timeline controls layer visibility"
    return None


def _add_item(controls: TuningControls, *, blocked: bool) -> ContextMenuItem:
    command = command_by_id("layers.add")
    enabled = not blocked and bool(command.enabled(command_context(controls)))
    return ContextMenuItem(
        id="navigator.layer.add",
        label="Add layer",
        run=lambda: command.run(controls),
        enabled=enabled,
        shortcut=command.shortcut,
        hint=None if enabled else "Layer limit reached",
    )


def _is_layer_row(controls: TuningControls, node: NavNode) -> bool:
    return (
        node.parent_id == "layers"
        and node.slot is not None
        and not is_preset_curation_mode(controls.session.settings.editor_mode)
    )


def _layer_items(
    controls: TuningControls, node: NavNode
) -> tuple[ContextMenuEntry, ...]:
    slot = node.slot
    assert slot is not None
    session = controls.session
    lifecycle = controls.layer_lifecycle
    order = session.layer_z_order
    index = order.index(slot)
    locked = session.layers[slot].locked
    lock_hint = "Locked: unlock to move" if locked else None

    def move(delta: int) -> None:
        lifecycle.move_slot_to(slot, order.index(slot) + delta)

    can_remove = lifecycle.can_remove()
    return (
        ContextMenuItem(
            id="navigator.layer.move_up",
            label="Move up",
            run=lambda: move(-1),
            enabled=not locked and index > 0,
            hint=lock_hint or (None if index > 0 else "Already the first layer"),
        ),
        ContextMenuItem(
            id="navigator.layer.move_down",
            label="Move down",
            run=lambda: move(1),
            enabled=not locked and index < len(order) - 1,
            hint=lock_hint
            or (None if index < len(order) - 1 else "Already the last layer"),
        ),
        CONTEXT_SEPARATOR,
        _add_item(controls, blocked=False),
        ContextMenuItem(
            id="navigator.layer.delete",
            label="Delete layer...",
            run=lambda: lifecycle.prompt_delete(slot),
            enabled=can_remove,
            shortcut="Delete",
            hint=None if can_remove else "Must have at least 1 layer",
        ),
    )


def _join(groups: list[tuple[ContextMenuEntry, ...]]) -> tuple[ContextMenuEntry, ...]:
    entries: list[ContextMenuEntry] = []
    for group in groups:
        if not group:
            continue
        if entries:
            entries.append(CONTEXT_SEPARATOR)
        entries.extend(group)
    return tuple(entries)
