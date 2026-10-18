"""Top-level navigator model for the shell.

Nodes are data only. Phases 3 and 4 add children. This module does not draw
or read keyboard state.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from cleave.viz.editor_mode_controls import is_preset_curation_mode

if TYPE_CHECKING:
    from cleave.viz.session import TuningSession


@dataclass(frozen=True)
class NavNode:
    id: str
    label: str
    depth: int
    has_inspector: bool
    badge: str | None


_TOP_LEVEL: tuple[NavNode, ...] = (
    NavNode("settings", "Settings", 0, True, None),
    NavNode("project", "Project", 0, True, None),
    NavNode("render", "Render", 0, False, None),
    NavNode("layers", "Layers", 0, False, None),
    NavNode("song_markers", "Song markers", 0, False, None),
)

TOP_LEVEL_IDS: tuple[str, ...] = tuple(node.id for node in _TOP_LEVEL)

_HIDDEN_IN_CURATION = frozenset({"project", "render", "song_markers"})


def visible_top_level_ids(session: TuningSession) -> tuple[str, ...]:
    """Ids ``build_navigator`` emits, in order."""
    if is_preset_curation_mode(session.settings.editor_mode):
        return tuple(node_id for node_id in TOP_LEVEL_IDS if node_id not in _HIDDEN_IN_CURATION)
    return TOP_LEVEL_IDS


def build_navigator(session: TuningSession) -> tuple[NavNode, ...]:
    """Top-level navigator rows for *session*.

    Preset curation omits Project, Render, and Song markers. Song markers
    carries the marker count as its badge, including ``"0"``.
    """
    visible = frozenset(visible_top_level_ids(session))
    marker_badge = str(len(session.song_markers.times))
    nodes: list[NavNode] = []
    for node in _TOP_LEVEL:
        if node.id not in visible:
            continue
        if node.id == "song_markers":
            node = replace(node, badge=marker_badge)
        nodes.append(node)
    return tuple(nodes)
