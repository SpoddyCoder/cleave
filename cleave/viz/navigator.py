"""Navigator tree for the shell.

Nodes are data only. This module does not draw or read keyboard state.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from cleave.stems import stem_overlay_header
from cleave.viz.editor_mode_controls import curation_focus_slot, is_preset_curation_mode

if TYPE_CHECKING:
    from cleave.viz.session import TuningSession


LAYER_ID_PREFIX = "layer:"
SOLO_BADGE = "solo"
HIDDEN_BADGE = "hidden"
_DEFAULT_EXPANDED = frozenset({"layers"})


@dataclass(frozen=True)
class NavNode:
    id: str
    label: str
    depth: int
    has_inspector: bool
    badge: str | None
    parent_id: str | None = None
    expandable: bool = False
    slot: str | None = None
    locked: bool = False


_TOP_LEVEL: tuple[NavNode, ...] = (
    NavNode("settings", "Settings", 0, True, None),
    NavNode("project", "Project", 0, True, None),
    NavNode("render", "Render", 0, False, None),
    NavNode("layers", "Layers", 0, True, None, expandable=True),
    NavNode("song_markers", "Song markers", 0, False, None),
)

TOP_LEVEL_IDS: tuple[str, ...] = tuple(node.id for node in _TOP_LEVEL)

_HIDDEN_IN_CURATION = frozenset({"project", "render", "song_markers"})


def layer_node_id(slot: str) -> str:
    """Navigator id for a layer slot."""
    return f"{LAYER_ID_PREFIX}{slot}"


def visible_top_level_ids(session: TuningSession) -> tuple[str, ...]:
    """Top-level ids ``build_navigator`` may emit, in order."""
    if is_preset_curation_mode(session.settings.editor_mode):
        return tuple(node_id for node_id in TOP_LEVEL_IDS if node_id not in _HIDDEN_IN_CURATION)
    return TOP_LEVEL_IDS


def build_navigator(
    session: TuningSession,
    expanded: Collection[str] | None = None,
) -> tuple[NavNode, ...]:
    """Visible navigator rows for *session*.

    *expanded* defaults to ``{"layers"}`` so layer children are included.
    Preset curation omits Project, Render, and Song markers, and keeps one
    layer child for the curation focus slot. Song markers carries the marker
    count as its badge, including ``"0"``.
    """
    if expanded is None:
        expanded = _DEFAULT_EXPANDED
    visible = frozenset(visible_top_level_ids(session))
    marker_badge = str(len(session.song_markers.times))
    nodes: list[NavNode] = []
    for node in _TOP_LEVEL:
        if node.id not in visible:
            continue
        if node.id == "song_markers":
            node = replace(node, badge=marker_badge)
        nodes.append(node)
        if node.id == "layers" and "layers" in expanded:
            nodes.extend(_layer_children(session))
    return tuple(nodes)


def _layer_children(session: TuningSession) -> tuple[NavNode, ...]:
    return tuple(_layer_node(session, slot) for slot in _child_slots(session))


def _child_slots(session: TuningSession) -> tuple[str, ...]:
    if is_preset_curation_mode(session.settings.editor_mode):
        focus = curation_focus_slot(session)
        if focus is None:
            return ()
        return (focus,)
    return tuple(session.layer_z_order)


def _layer_node(session: TuningSession, slot: str) -> NavNode:
    layer = session.layers[slot]
    index = session.layer_z_order.index(slot)
    return NavNode(
        id=layer_node_id(slot),
        label=f"{index + 1}  {stem_overlay_header(layer.stem)}",
        depth=1,
        has_inspector=True,
        badge=_layer_badge(session, slot),
        parent_id="layers",
        slot=slot,
        locked=layer.locked,
    )


def _layer_badge(session: TuningSession, slot: str) -> str | None:
    if session.solo_slot == slot:
        return SOLO_BADGE
    if not session.layers[slot].enabled:
        return HIDDEN_BADGE
    return None
