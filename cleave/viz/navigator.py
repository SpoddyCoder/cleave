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
OFF_BADGE = "off"
DEFAULT_SELECTED_ID = "settings"
# The ImGui atlas must include these; the default Latin range draws them as "?".
TWISTY_EXPANDED = "▾"
TWISTY_COLLAPSED = "▸"

LAYER_PAGE_PRESET_SWITCHING = "preset_switching"
LAYER_PAGE_COMPOSITING = "compositing"
LAYER_PAGE_EFFECTS = "effects"

_LAYER_PAGES: tuple[tuple[str, str], ...] = (
    (LAYER_PAGE_PRESET_SWITCHING, "Preset Switching"),
    (LAYER_PAGE_COMPOSITING, "Compositing"),
    (LAYER_PAGE_EFFECTS, "Cleave Effects"),
)


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
    NavNode("settings", "Settings", 0, False, None, expandable=True),
    NavNode("project", "Project", 0, False, None, expandable=True),
    NavNode("overlay", "Overlay", 0, True, None, expandable=True),
    NavNode("post_fx", "Post-FX", 0, True, None, expandable=True),
    NavNode("pattern_mask", "Pattern Mask", 0, True, None),
    NavNode("timeline", "Timeline", 0, True, None, expandable=True),
    NavNode("layers", "Layers", 0, True, None, expandable=True),
)

_STATIC_CHILDREN: dict[str, tuple[tuple[str, str], ...]] = {
    "settings": (
        ("settings.editor_window", "Editor Window"),
        ("settings.ui", "UI"),
        ("settings.latency", "Latency Compensation"),
    ),
    "project": (
        ("project.projectm", "ProjectM"),
        ("project.compositor", "Compositor"),
        ("project.render", "Render Project"),
    ),
    "overlay": (
        ("overlay.opening_card", "Opening Card"),
        ("overlay.closing_card", "Closing Card"),
    ),
    "post_fx": (
        ("post_fx.fade", "Fade"),
        ("post_fx.highlight_rolloff", "Highlight Rolloff"),
        ("post_fx.chroma_boost", "Chroma Boost"),
        ("post_fx.limiter", "Visual Limiter"),
    ),
    "timeline": (
        ("timeline.grid", "Beat / Bar Grid"),
        ("timeline.cue_fades", "Cue Fades"),
        ("timeline.song_markers", "Song Markers"),
        ("timeline.preset", "Timeline Preset"),
    ),
}

TOP_LEVEL_IDS: tuple[str, ...] = tuple(node.id for node in _TOP_LEVEL)

_HIDDEN_IN_CURATION = frozenset(
    {"project", "overlay", "post_fx", "pattern_mask", "timeline"}
)


def layer_node_id(slot: str) -> str:
    """Navigator id for a layer slot."""
    return f"{LAYER_ID_PREFIX}{slot}"


def layer_page_node_id(slot: str, page: str) -> str:
    """Navigator id for one page nested under a layer."""
    return f"{layer_node_id(slot)}:{page}"


def layer_slot_of(node_id: str) -> str | None:
    """Slot that owns *node_id*, for a layer or a page nested under one."""
    if not node_id.startswith(LAYER_ID_PREFIX):
        return None
    return node_id[len(LAYER_ID_PREFIX) :].partition(":")[0]


def layer_page_of(node_id: str) -> str | None:
    """Layer page name in *node_id*, or None for a layer itself or any other id."""
    if not node_id.startswith(LAYER_ID_PREFIX):
        return None
    return node_id[len(LAYER_ID_PREFIX) :].partition(":")[2] or None


def parent_id_of(node_id: str) -> str | None:
    """Parent navigator id, or None for a root."""
    slot = layer_slot_of(node_id)
    if slot is not None:
        return "layers" if layer_page_of(node_id) is None else layer_node_id(slot)
    root, separator, _child = node_id.partition(".")
    return root if separator else None


def root_id(node_id: str) -> str:
    """Top-level id that contains *node_id*."""
    parent = parent_id_of(node_id)
    while parent is not None:
        node_id = parent
        parent = parent_id_of(node_id)
    return node_id


def expansion_path(node_id: str) -> set[str]:
    """Ids left open when *node_id* is selected: it and its ancestors."""
    path = {node_id}
    parent = parent_id_of(node_id)
    while parent is not None:
        path.add(parent)
        parent = parent_id_of(parent)
    return path


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

    *expanded* defaults to the path of the default selection. A node's children
    are included only while its id is in *expanded*. Preset curation omits every
    root except Settings and Layers, and keeps one childless layer for the
    curation focus slot. Song Markers carries the marker count as its badge,
    including ``"0"``.
    """
    if expanded is None:
        expanded = expansion_path(DEFAULT_SELECTED_ID)
    visible = frozenset(visible_top_level_ids(session))
    nodes: list[NavNode] = []
    for node in _TOP_LEVEL:
        if node.id not in visible:
            continue
        nodes.append(_root_node(session, node))
        if node.id not in expanded:
            continue
        if node.id == "layers":
            nodes.extend(_layer_children(session, expanded))
        else:
            nodes.extend(_static_children(session, node.id))
    return tuple(nodes)


def _root_node(session: TuningSession, node: NavNode) -> NavNode:
    if node.id == "overlay":
        return replace(
            node,
            badge=_overlay_badge(session),
            locked=session.overlays.locked,
        )
    if node.id == "post_fx":
        post_fx = session.post_fx
        return replace(
            node,
            badge=None if post_fx.enabled else OFF_BADGE,
            locked=post_fx.locked,
        )
    if node.id == "pattern_mask":
        pattern_mask = session.pattern_mask
        return replace(
            node,
            badge=None if pattern_mask.enabled else OFF_BADGE,
            locked=pattern_mask.locked,
        )
    if node.id == "timeline":
        return replace(node, locked=session.timeline.locked)
    return node


def _static_children(session: TuningSession, parent_id: str) -> tuple[NavNode, ...]:
    return tuple(
        NavNode(
            id=node_id,
            label=label,
            depth=1,
            has_inspector=True,
            badge=_static_child_badge(session, node_id),
            parent_id=parent_id,
        )
        for node_id, label in _STATIC_CHILDREN.get(parent_id, ())
    )


def _static_child_badge(session: TuningSession, node_id: str) -> str | None:
    if node_id == "timeline.song_markers":
        return str(len(session.song_markers.times))
    if node_id == "overlay.opening_card":
        return None if session.overlays.opening_card.enabled else OFF_BADGE
    if node_id == "overlay.closing_card":
        return None if session.overlays.closing_card.enabled else OFF_BADGE
    return None


def _layer_children(
    session: TuningSession, expanded: Collection[str]
) -> tuple[NavNode, ...]:
    curation = is_preset_curation_mode(session.settings.editor_mode)
    nodes: list[NavNode] = []
    for slot in _child_slots(session):
        node = _layer_node(session, slot, expandable=not curation)
        nodes.append(node)
        if not curation and node.id in expanded:
            nodes.extend(_layer_page_nodes(slot))
    return tuple(nodes)


def _child_slots(session: TuningSession) -> tuple[str, ...]:
    if is_preset_curation_mode(session.settings.editor_mode):
        focus = curation_focus_slot(session)
        if focus is None:
            return ()
        return (focus,)
    return tuple(session.layer_z_order)


def _layer_node(session: TuningSession, slot: str, *, expandable: bool) -> NavNode:
    layer = session.layers[slot]
    index = session.layer_z_order.index(slot)
    return NavNode(
        id=layer_node_id(slot),
        label=f"{index + 1}  {stem_overlay_header(layer.stem)}",
        depth=1,
        has_inspector=True,
        badge=_layer_badge(session, slot),
        parent_id="layers",
        expandable=expandable,
        slot=slot,
        locked=layer.locked,
    )


def _layer_page_nodes(slot: str) -> tuple[NavNode, ...]:
    return tuple(
        NavNode(
            id=layer_page_node_id(slot, page),
            label=label,
            depth=2,
            has_inspector=True,
            badge=None,
            parent_id=layer_node_id(slot),
            slot=slot,
        )
        for page, label in _LAYER_PAGES
    )


def _layer_badge(session: TuningSession, slot: str) -> str | None:
    if session.solo_slot == slot:
        return SOLO_BADGE
    if not session.layers[slot].enabled:
        return HIDDEN_BADGE
    return None


def _overlay_badge(session: TuningSession) -> str | None:
    if session.overlay_solo:
        return SOLO_BADGE
    overlays = session.overlays
    if not overlays.opening_card.enabled and not overlays.closing_card.enabled:
        return OFF_BADGE
    return None
