"""Right-click menu for the preview (the visualiser rect).

Play or pause, solo a layer, switch Overlay, Post-FX, and Pattern Mask on
or off, pick the preview quality, grab a still, and go fullscreen. The
solo and on/off items read the navigator's own icons, so their checks,
locks, and hints match it; each item calls the same path as its icon or
key.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from cleave.config_schema.editor import EDITOR_PREVIEW_QUALITIES
from cleave.viz.commands import command_by_id, command_menu_item
from cleave.viz.context_menu import (
    ContextMenuEntry,
    ContextMenuItem,
    ContextMenuLeaf,
    ContextMenuProvider,
    ContextSubmenu,
    join_groups,
)
from cleave.viz.navigator import (
    TOGGLE_ENABLED,
    TOGGLE_SOLO,
    NavNode,
    NavToggle,
    build_navigator,
)
from cleave.viz.navigator_context_menu import navigator_toggle_hint
from cleave.viz.row_hotkeys import activate_header_toggle, node_control_descriptor

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls

# Root nodes with an on/off item, in menu order.
_BLOCK_ITEMS: tuple[tuple[str, str], ...] = (
    ("overlay", "Overlays"),
    ("post_fx", "Post-FX"),
    ("pattern_mask", "Pattern Mask"),
)


class PreviewTransport(Protocol):
    @property
    def paused(self) -> bool: ...

    def toggle_transport(self) -> None: ...


def preview_menu(
    controls: TuningControls, transport: PreviewTransport
) -> ContextMenuProvider:
    def entries() -> tuple[ContextMenuEntry, ...]:
        return preview_menu_entries(controls, transport)

    return entries


def preview_menu_entries(
    controls: TuningControls, transport: PreviewTransport
) -> tuple[ContextMenuEntry, ...]:
    # Layers open, so the layer rows (and their solo icons) are listed.
    nodes = build_navigator(controls.session, {"layers"})
    return join_groups(
        [
            (_transport_item(transport),),
            _view_items(controls, nodes),
            (_quality_submenu(controls), _still_item(controls)),
            (command_menu_item(command_by_id("view.fullscreen"), controls),),
        ]
    )


def _transport_item(transport: PreviewTransport) -> ContextMenuItem:
    return ContextMenuItem(
        id="preview.transport",
        label="Play" if transport.paused else "Pause",
        run=transport.toggle_transport,
        shortcut="Space",
    )


def _view_items(
    controls: TuningControls, nodes: tuple[NavNode, ...]
) -> tuple[ContextMenuEntry, ...]:
    items: list[ContextMenuEntry] = []
    solo = _solo_submenu(controls, nodes)
    if solo is not None:
        items.append(solo)
    by_id = {node.id: node for node in nodes}
    for node_id, label in _BLOCK_ITEMS:
        node = by_id.get(node_id)
        toggle = None if node is None else _toggle(node, TOGGLE_ENABLED)
        if node is None or toggle is None:
            continue
        hint = navigator_toggle_hint(toggle)
        items.append(
            ContextMenuItem(
                id=f"preview.enabled.{node_id}",
                label=label,
                run=_toggle_run(controls, node, TOGGLE_ENABLED),
                enabled=hint is None,
                checked=toggle.active,
                hint=hint,
            )
        )
    return tuple(items)


def _solo_submenu(
    controls: TuningControls, nodes: tuple[NavNode, ...]
) -> ContextSubmenu | None:
    layers = [
        (node, toggle)
        for node in nodes
        if node.parent_id == "layers"
        and (toggle := _toggle(node, TOGGLE_SOLO)) is not None
    ]
    if not layers:
        return None
    session = controls.session
    current = session.solo_slot

    def clear() -> None:
        if current is not None:
            controls.layer_mutations.exit_solo(current)

    children: list[ContextMenuLeaf] = [
        ContextMenuItem(
            id="preview.solo.none",
            label="None",
            run=clear,
            checked=current is None,
        )
    ]
    children.extend(
        ContextMenuItem(
            id=f"preview.solo.{node.slot}",
            label=node.label,
            run=_toggle_run(controls, node, TOGGLE_SOLO),
            checked=toggle.active,
        )
        for node, toggle in layers
    )
    return ContextSubmenu(id="preview.solo", label="Solo layer", items=tuple(children))


def _quality_submenu(controls: TuningControls) -> ContextSubmenu:
    current = controls.cfg.editor.preview_quality
    return ContextSubmenu(
        id="preview.quality",
        label="Preview quality",
        items=tuple(
            ContextMenuItem(
                id=f"preview.quality.{mode}",
                label=mode,
                run=lambda mode=mode: controls.settings.set_preview_quality(mode),
                checked=mode == current,
            )
            for mode in EDITOR_PREVIEW_QUALITIES
        ),
    )


def _still_item(controls: TuningControls) -> ContextMenuItem:
    capture = controls.still_capture
    hint: str | None = None
    if not capture.available:
        hint = "No project folder to save into"
    elif capture.busy:
        hint = "Capturing a still"
    elif controls.project_render.busy:
        hint = "Render in progress"
    return ContextMenuItem(
        id="preview.grab_still",
        label="Grab still",
        run=capture.request,
        enabled=hint is None,
        hint=hint,
    )


def _toggle(node: NavNode, toggle_id: str) -> NavToggle | None:
    return next((toggle for toggle in node.toggles if toggle.id == toggle_id), None)


def _toggle_run(
    controls: TuningControls, node: NavNode, toggle_id: str
) -> Callable[[], None]:
    descriptor = node_control_descriptor(node.id)

    def run() -> None:
        if descriptor is not None:
            activate_header_toggle(controls, toggle_id, descriptor)

    return run
