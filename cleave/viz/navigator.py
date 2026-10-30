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
OVERLAY_CARD_ID_PREFIX = "render.overlays.card:"
SOLO_BADGE = "solo"
HIDDEN_BADGE = "hidden"
OFF_BADGE = "off"
_DEFAULT_EXPANDED = frozenset({"layers", "render", "timeline"})


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
    NavNode("render", "Render", 0, False, None, expandable=True),
    NavNode("layers", "Layers", 0, True, None, expandable=True),
    NavNode("timeline", "Timeline", 0, True, None, expandable=True),
)

TOP_LEVEL_IDS: tuple[str, ...] = tuple(node.id for node in _TOP_LEVEL)

_HIDDEN_IN_CURATION = frozenset({"project", "render", "timeline"})


def layer_node_id(slot: str) -> str:
    """Navigator id for a layer slot."""
    return f"{LAYER_ID_PREFIX}{slot}"


def overlay_card_node_id(card: str) -> str:
    """Inspector page id for an opening or closing overlay card."""
    return f"{OVERLAY_CARD_ID_PREFIX}{card}"


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

    *expanded* defaults to ``{"layers", "render", "timeline"}`` so layer
    children, render children, and Song markers are included. Render children
    are Overlays, Post-FX, and Pattern mask. Timeline's only child is Song
    markers.
    Preset curation omits Project, Render, and Timeline, and keeps one layer
    child for the curation focus slot. Song markers has an inspector and
    carries the marker count as its badge, including ``"0"``.
    """
    if expanded is None:
        expanded = _DEFAULT_EXPANDED
    visible = frozenset(visible_top_level_ids(session))
    nodes: list[NavNode] = []
    for node in _TOP_LEVEL:
        if node.id not in visible:
            continue
        if node.id == "timeline":
            node = replace(node, locked=session.timeline.locked)
        nodes.append(node)
        if node.id == "render" and "render" in expanded:
            nodes.extend(_render_children(session))
        if node.id == "layers" and "layers" in expanded:
            nodes.extend(_layer_children(session))
        if node.id == "timeline" and "timeline" in expanded:
            nodes.append(_song_markers_node(session))
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


def _render_children(session: TuningSession) -> tuple[NavNode, ...]:
    return (
        _overlays_node(session),
        _post_fx_node(session),
        _pattern_mask_node(session),
    )


def _overlays_node(session: TuningSession) -> NavNode:
    overlays = session.render_overlays
    return NavNode(
        id="render.overlays",
        label="Overlays",
        depth=1,
        has_inspector=True,
        badge=_overlays_badge(session),
        parent_id="render",
        locked=overlays.locked,
    )


def _post_fx_node(session: TuningSession) -> NavNode:
    post_fx = session.render_post_fx
    return NavNode(
        id="render.post_fx",
        label="Post-FX",
        depth=1,
        has_inspector=True,
        badge=None if post_fx.enabled else OFF_BADGE,
        parent_id="render",
        locked=post_fx.locked,
    )


def _pattern_mask_node(session: TuningSession) -> NavNode:
    pattern_mask = session.render_pattern_mask
    return NavNode(
        id="render.pattern_mask",
        label="Pattern mask",
        depth=1,
        has_inspector=True,
        badge=None if pattern_mask.enabled else OFF_BADGE,
        parent_id="render",
        locked=pattern_mask.locked,
    )


def _song_markers_node(session: TuningSession) -> NavNode:
    return NavNode(
        id="song_markers",
        label="Song markers",
        depth=1,
        has_inspector=True,
        badge=str(len(session.song_markers.times)),
        parent_id="timeline",
    )


def _overlays_badge(session: TuningSession) -> str | None:
    if session.render_overlay_solo:
        return SOLO_BADGE
    overlays = session.render_overlays
    if not overlays.opening_card.enabled and not overlays.closing_card.enabled:
        return OFF_BADGE
    return None
