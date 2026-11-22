"""Right-click menu for a navigator row.

A root or layer row: expand or collapse it, and flip its on/off, solo, and
lock icons. A layer row with more than one problem or notice leads with View
all problems, then adds a page jump, move up and down, and add and delete
layer. A sub-row (a card, an effect, a layer page) lists the switches that
act for its page, naming the row that owns each when it is a parent, then
the page's own buttons; Preset List takes its page menu, and Song Markers
adds dropping a marker at the playhead. The right-click has already selected
the row, so its page shows in the inspector. Each item calls the same path
as its icon, button, or key, and a disabled item says why in its hint.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from cleave.viz.commands import command_by_id, command_menu_item
from cleave.viz.context_menu import (
    CONTEXT_SEPARATOR,
    ContextMenuEntry,
    ContextMenuItem,
    ContextMenuProvider,
    ContextSubmenu,
    MenuIcon,
    join_groups,
)
from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.inspector import page_command_ids
from cleave.viz.layer_problems import is_problem, issue_menu_label, layer_issues
from cleave.viz.navigator import (
    LAYER_PAGE_PRESET_LIST,
    TOGGLE_ADD,
    TOGGLE_ENABLED,
    TOGGLE_LOCK,
    TOGGLE_PREVIEW,
    TOGGLE_SOLO,
    NavNode,
    NavToggle,
    build_navigator,
    layer_page_nodes,
    layer_page_of,
    page_toggles,
)
from cleave.viz.preset_context_menu import preset_list_page_menu
from cleave.viz.row_hotkeys import activate_header_toggle, node_control_descriptor

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

_TOGGLE_ITEMS: dict[str, tuple[str, str]] = {
    TOGGLE_ENABLED: ("Enabled", "E"),
    TOGGLE_SOLO: ("Solo", "S"),
    TOGGLE_PREVIEW: ("Preview", "V"),
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
    nodes = build_navigator(controls.session, focus.nav_expanded)
    node = next((candidate for candidate in nodes if candidate.id == node_id), None)
    if node is None:
        return ()
    if _is_sub_row(node):
        return join_groups(
            [
                _owner_switch_items(controls, node, nodes),
                _page_action_items(controls, node),
            ]
        )
    layer_row = _is_layer_row(controls, node)
    groups: list[tuple[ContextMenuEntry, ...]] = [
        _issue_items(controls, node) if layer_row else (),
        _tree_items(controls, node, toggle_expanded),
        _toggle_items(controls, node),
    ]
    if layer_row:
        groups.append(_layer_items(controls, node))
    return join_groups(groups)


def _is_sub_row(node: NavNode) -> bool:
    """A card, a Post-FX effect, a root's child page, or a layer page."""
    return node.parent_id is not None and node.parent_id != "layers"


def _owner_switch_items(
    controls: TuningControls, node: NavNode, nodes: tuple[NavNode, ...]
) -> tuple[ContextMenuEntry, ...]:
    """On/off, solo, preview, and lock for the page, as its title line shows them.

    A switch a parent owns names that parent, as Locked (Post-FX), and acts
    through that parent's header, as the title line's button does.
    """
    items: list[ContextMenuEntry] = []
    for owned in page_toggles(controls.session, node.id, nodes):
        toggle = owned.toggle
        label_key = _TOGGLE_ITEMS.get(toggle.id)
        descriptor = node_control_descriptor(owned.owner_id)
        if label_key is None or descriptor is None:
            continue
        label, key = label_key
        if owned.owner_id != node.id:
            label = f"{label} ({owned.owner_label})"
        hint = navigator_toggle_hint(toggle)
        items.append(
            ContextMenuItem(
                id=f"navigator.toggle.{toggle.id}",
                label=label,
                run=lambda toggle_id=toggle.id, desc=descriptor: activate_header_toggle(
                    controls, toggle_id, desc
                ),
                enabled=hint is None,
                checked=toggle.active,
                shortcut=key,
                hint=hint,
            )
        )
    return tuple(items)


def _page_action_items(
    controls: TuningControls, node: NavNode
) -> tuple[ContextMenuEntry, ...]:
    """The page's buttons; Preset List takes its own page menu."""
    if node.slot is not None and layer_page_of(node.id) == LAYER_PAGE_PRESET_LIST:
        return preset_list_page_menu(controls, node.slot)()
    items: list[ContextMenuEntry] = []
    if node.id == "timeline.song_markers":
        items.append(_drop_marker_item(controls))
    view = controls.build_view_state(paused=controls.playback.paused)
    items.extend(
        command_menu_item(
            command_by_id(command_id), controls, item_id=f"navigator.page.{command_id}"
        )
        for command_id in page_command_ids(view, node.id)
    )
    return tuple(items)


def _drop_marker_item(controls: TuningControls) -> ContextMenuItem:
    recording = bool(controls.session.timeline.recording)
    return ContextMenuItem(
        id="navigator.drop_marker",
        label="Drop song marker at playhead",
        run=controls.song_markers.drop,
        enabled=not recording,
        shortcut="Ctrl+Enter",
        hint="Stop recording to drop markers" if recording else None,
    )


def _issue_items(
    controls: TuningControls, node: NavNode
) -> tuple[ContextMenuEntry, ...]:
    """View all problems, while the layer has more than one problem or notice."""
    slot = node.slot
    assert slot is not None
    issues = layer_issues(controls.session, slot)
    if issues.count < 2:
        return ()
    return (
        ContextSubmenu(
            id="navigator.issues",
            label="View all problems",
            items=tuple(
                ContextMenuItem(
                    id=f"navigator.issue.{index}",
                    label=issue_menu_label(issue),
                    run=lambda index=index: controls.show_issue(slot, index),
                    icon=MenuIcon.PROBLEM if is_problem(issue) else MenuIcon.NOTICE,
                )
                for index, issue in enumerate(issues.items())
            ),
        ),
    )


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
        hint = navigator_toggle_hint(toggle)
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


def navigator_toggle_hint(toggle: NavToggle) -> str | None:
    if toggle.blocked:
        return "Locked: unlock to change"
    if toggle.inert:
        return "Timeline controls layer visibility"
    return None


def _add_item(controls: TuningControls, *, blocked: bool) -> ContextMenuItem:
    return command_menu_item(
        command_by_id("layers.add"),
        controls,
        item_id="navigator.layer.add",
        label="Add layer",
        enabled=not blocked,
        disabled_hint="Layer limit reached",
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
            label="Delete layer…",
            run=lambda: lifecycle.prompt_delete(slot),
            enabled=can_remove,
            shortcut="Delete",
            hint=None if can_remove else "Must have at least 1 layer",
        ),
    )
