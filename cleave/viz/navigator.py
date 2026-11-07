"""Navigator tree for the shell.

Nodes are data only. This module does not draw or read keyboard state.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from cleave.stems import stem_overlay_header
from cleave.viz.editor_mode_controls import curation_focus_slot, is_preset_curation_mode

if TYPE_CHECKING:
    from cleave.viz.session import TuningSession


LAYER_ID_PREFIX = "layer:"
SOLO_BADGE = "solo"
HIDDEN_BADGE = "hidden"
DEFAULT_SELECTED_ID = "settings"
DEFAULT_EXPANDED_IDS = frozenset({"layers"})
# The ImGui atlas must include these; the default Latin range draws them as "?".
TWISTY_EXPANDED = "▾"
TWISTY_COLLAPSED = "▸"

TOGGLE_ENABLED = "enabled"
TOGGLE_SOLO = "solo"
TOGGLE_LOCK = "lock"

LAYER_PAGE_PRESET_SWITCHING = "preset_switching"
LAYER_PAGE_COMPOSITING = "compositing"
LAYER_PAGE_EFFECTS = "effects"

_LAYER_PAGES: tuple[tuple[str, str], ...] = (
    (LAYER_PAGE_PRESET_SWITCHING, "Preset Switching"),
    (LAYER_PAGE_COMPOSITING, "Compositing"),
    (LAYER_PAGE_EFFECTS, "Cleave Effects"),
)


@dataclass(frozen=True)
class NavToggle:
    """One clickable icon on a navigator row.

    ``id`` is ``TOGGLE_ENABLED``, ``TOGGLE_SOLO``, or ``TOGGLE_LOCK``. ``active``
    is on, soloed, or locked. ``blocked`` is true while the section lock refuses
    the toggle.
    """

    id: str
    active: bool
    blocked: bool = False


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
    toggles: tuple[NavToggle, ...] = ()


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


def ancestor_ids(node_id: str) -> set[str]:
    """Ids that must be open for *node_id* to be visible."""
    ancestors: set[str] = set()
    parent = parent_id_of(node_id)
    while parent is not None:
        ancestors.add(parent)
        parent = parent_id_of(parent)
    return ancestors


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

    *expanded* defaults to ``DEFAULT_EXPANDED_IDS``. A node's children are
    included only while its id is in *expanded*. Preset curation omits every
    root except Settings and Layers, and keeps one childless layer for the
    curation focus slot. Song Markers carries the marker count as its badge,
    including ``"0"``.
    """
    if expanded is None:
        expanded = DEFAULT_EXPANDED_IDS
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


def navigator_row_bright(node: NavNode) -> bool:
    """True for rows drawn in the value colour: roots and the layer rows."""
    return node.depth == 0 or node.parent_id == "layers"


def navigator_tree_rails(nodes: Sequence[NavNode]) -> tuple[tuple[bool, ...], ...]:
    """Tree rails for each row of *nodes*, in the same order.

    A row has one entry per depth level, so a root has none. Entry ``k`` is true
    while the branch at depth ``k + 1`` continues below this row. The last entry
    is the row's own branch: true for a tee, false for a closing elbow.
    """
    continues: set[int] = set()
    rails: list[tuple[bool, ...]] = []
    for node in reversed(nodes):
        continues = {depth for depth in continues if depth <= node.depth}
        rails.append(
            tuple(depth in continues for depth in range(1, node.depth + 1))
        )
        continues.add(node.depth)
    return tuple(reversed(rails))


def _root_node(session: TuningSession, node: NavNode) -> NavNode:
    if node.id == "overlay":
        overlays = session.overlays
        enabled = overlays.opening_card.enabled or overlays.closing_card.enabled
        return replace(
            node,
            toggles=(
                NavToggle(TOGGLE_ENABLED, enabled, overlays.locked),
                NavToggle(TOGGLE_SOLO, session.overlay_solo),
                NavToggle(TOGGLE_LOCK, overlays.locked),
            ),
        )
    if node.id == "post_fx":
        return replace(node, toggles=_block_toggles(session.post_fx))
    if node.id == "pattern_mask":
        return replace(node, toggles=_block_toggles(session.pattern_mask))
    if node.id == "timeline":
        return replace(node, toggles=_block_toggles(session.timeline))
    return node


def _block_toggles(block: object) -> tuple[NavToggle, ...]:
    return (
        NavToggle(TOGGLE_ENABLED, block.enabled, block.locked),
        NavToggle(TOGGLE_LOCK, block.locked),
    )


def _static_children(session: TuningSession, parent_id: str) -> tuple[NavNode, ...]:
    return tuple(
        NavNode(
            id=node_id,
            label=label,
            depth=1,
            has_inspector=True,
            badge=_static_child_badge(session, node_id),
            parent_id=parent_id,
            toggles=_static_child_toggles(session, node_id),
        )
        for node_id, label in _STATIC_CHILDREN.get(parent_id, ())
    )


def _static_child_badge(session: TuningSession, node_id: str) -> str | None:
    if node_id == "timeline.song_markers":
        return str(len(session.song_markers.times))
    return None


def _static_child_toggles(
    session: TuningSession, node_id: str
) -> tuple[NavToggle, ...]:
    overlays = session.overlays
    if node_id == "overlay.opening_card":
        return (
            NavToggle(TOGGLE_ENABLED, overlays.opening_card.enabled, overlays.locked),
        )
    if node_id == "overlay.closing_card":
        return (
            NavToggle(TOGGLE_ENABLED, overlays.closing_card.enabled, overlays.locked),
        )
    return ()


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
    curation = is_preset_curation_mode(session.settings.editor_mode)
    return NavNode(
        id=layer_node_id(slot),
        label=f"{index + 1}  {stem_overlay_header(layer.stem)}",
        depth=1,
        has_inspector=True,
        badge=_layer_badge(session, slot) if curation else None,
        parent_id="layers",
        expandable=expandable,
        slot=slot,
        locked=curation and layer.locked,
        toggles=() if curation else _layer_toggles(session, slot),
    )


def _layer_toggles(session: TuningSession, slot: str) -> tuple[NavToggle, ...]:
    layer = session.layers[slot]
    return (
        NavToggle(TOGGLE_ENABLED, layer.enabled, layer.locked),
        NavToggle(TOGGLE_SOLO, session.solo_slot == slot),
        NavToggle(TOGGLE_LOCK, layer.locked),
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

