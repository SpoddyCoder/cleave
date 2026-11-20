"""Navigator tree for the shell.

Nodes are data only. This module does not draw or read keyboard state.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from cleave.stems import stem_overlay_header
from cleave.config_schema.layers import MAX_LAYER_COUNT
from cleave.viz.editor_mode_controls import curation_focus_slot, is_preset_curation_mode
from cleave.viz.layer_problems import ProblemPage, layer_problems, layer_problems_tooltip
from cleave.viz.theme import palette

if TYPE_CHECKING:
    from cleave.viz.session import TuningSession


LAYER_ID_PREFIX = "layer:"
# Inspector page of one timeline strip row. It has no navigator row.
TIMELINE_ROW_ID_PREFIX = "timeline.row:"
SOLO_BADGE = "solo"
HIDDEN_BADGE = "hidden"
DEFAULT_SELECTED_ID = "layers"
DEFAULT_EXPANDED_IDS = frozenset({"layers"})
# The ImGui atlas must include these; the default Latin range draws them as "?".
TWISTY_EXPANDED = "▾"
TWISTY_COLLAPSED = "▸"

TOGGLE_ENABLED = "enabled"
TOGGLE_SOLO = "solo"
TOGGLE_PREVIEW = "preview"
TOGGLE_LOCK = "lock"
TOGGLE_ADD = "add"
TOGGLE_HOLD = "hold"
TOGGLE_WARN = "warn"

LAYER_PAGE_MILKDROP_PRESET = "milkdrop_preset"
LAYER_PAGE_PRESET_SWITCHING = "preset_switching"
LAYER_PAGE_PRESET_LIST = "preset_list"
LAYER_PAGE_COMPOSITING = "compositing"
LAYER_PAGE_EFFECTS = "effects"

# Layer pages nested under another layer page, keyed by child page.
_LAYER_SUBPAGE_PARENTS: dict[str, str] = {
    LAYER_PAGE_PRESET_LIST: LAYER_PAGE_PRESET_SWITCHING,
}

_LAYER_PAGES: tuple[tuple[str, str], ...] = (
    (LAYER_PAGE_MILKDROP_PRESET, "Milkdrop Preset"),
    (LAYER_PAGE_PRESET_SWITCHING, "Preset Switching"),
    (LAYER_PAGE_PRESET_LIST, "Preset List"),
    (LAYER_PAGE_COMPOSITING, "Compositing"),
    (LAYER_PAGE_EFFECTS, "Cleave Effects"),
)


@dataclass(frozen=True)
class NavToggle:
    """One clickable icon on a navigator row.

    ``id`` is ``TOGGLE_ENABLED``, ``TOGGLE_SOLO``, ``TOGGLE_PREVIEW``,
    ``TOGGLE_LOCK``, ``TOGGLE_ADD``, ``TOGGLE_HOLD``, or ``TOGGLE_WARN``.
    ``active`` is on, soloed, previewing, or locked. A hold toggle is present
    only while the layer's preset switching is held, and a warn toggle only
    while the layer has a problem; both are always active, and a warn
    toggle's ``detail`` is its tooltip, naming every problem. ``blocked`` is true
    while the section lock refuses the toggle, or Add has no room. ``inert``
    is true while a press is refused for another reason (the timeline owns
    layer visibility): the icon draws as usual and the pointer stays an arrow.
    """

    id: str
    active: bool
    blocked: bool = False
    inert: bool = False
    detail: str = ""


@dataclass(frozen=True)
class NavNode:
    id: str
    label: str
    depth: int
    badge: str | None
    parent_id: str | None = None
    expandable: bool = False
    slot: str | None = None
    locked: bool = False
    toggles: tuple[NavToggle, ...] = ()
    # Leading drag handle that reorders the row; blocked draws it inert.
    draggable: bool = False
    drag_blocked: bool = False
    # Start of the label that belongs to the drag handle: it washes and
    # takes the press with the handle (a layer's number).
    handle_text: str = ""


_TOP_LEVEL: tuple[NavNode, ...] = (
    NavNode("overlay", "Overlay", 0, None, expandable=True),
    NavNode("post_fx", "Post-FX", 0, None, expandable=True),
    NavNode("pattern_mask", "Pattern Mask", 0, None, expandable=True),
    NavNode("timeline", "Timeline", 0, None, expandable=True),
    NavNode("layers", "Layers", 0, None, expandable=True),
)

_STATIC_CHILDREN: dict[str, tuple[tuple[str, str], ...]] = {
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
    "pattern_mask": (
        ("pattern_mask.pattern", "Pattern"),
        ("pattern_mask.edges", "Edges & Motion"),
    ),
    "timeline": (
        ("timeline.grid", "Beat / Bar Grid"),
        ("timeline.cue_fades", "Cue Fades"),
        ("timeline.song_markers", "Song Markers"),
    ),
}

TOP_LEVEL_IDS: tuple[str, ...] = tuple(node.id for node in _TOP_LEVEL)

_HIDDEN_IN_CURATION = frozenset({"overlay", "post_fx", "pattern_mask", "timeline"})


def layer_node_id(slot: str) -> str:
    """Navigator id for a layer slot."""
    return f"{LAYER_ID_PREFIX}{slot}"


def layer_page_node_id(slot: str, page: str) -> str:
    """Navigator id for one page nested under a layer."""
    return f"{layer_node_id(slot)}:{page}"


def timeline_row_node_id(slot: str) -> str:
    """Inspector page id for the timeline strip row of *slot*."""
    return f"{TIMELINE_ROW_ID_PREFIX}{slot}"


def timeline_row_slot_of(node_id: str) -> str | None:
    """Slot of a timeline row page, or None for any other id."""
    if not node_id.startswith(TIMELINE_ROW_ID_PREFIX):
        return None
    return node_id[len(TIMELINE_ROW_ID_PREFIX) :] or None


def timeline_row_title(session: TuningSession, slot: str) -> str:
    """Breadcrumb for a timeline row page, such as ``Timeline > 1  Drums``."""
    if slot not in session.layers:
        return "Timeline"
    index = session.layer_z_order.index(slot)
    header = stem_overlay_header(session.layers[slot].stem)
    return f"Timeline > {index + 1}  {header}"


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
        page = layer_page_of(node_id)
        if page is None:
            return "layers"
        parent_page = _LAYER_SUBPAGE_PARENTS.get(page)
        if parent_page is None:
            return layer_node_id(slot)
        return layer_page_node_id(slot, parent_page)
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
    root except Layers, and keeps one childless layer for the
    curation focus slot.
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


def initial_expanded_ids(session: TuningSession) -> frozenset[str]:
    """Navigator ids open when a project opens.

    Layers is always open. Another root starts open when its own on/off
    switch is on or any of its child rows' switches is on. Layer rows start
    closed.
    """
    expanded = set(DEFAULT_EXPANDED_IDS)
    for node in build_navigator(session, TOP_LEVEL_IDS):
        if node.id == "layers" or node.parent_id == "layers":
            continue
        if any(
            toggle.id == TOGGLE_ENABLED and toggle.active for toggle in node.toggles
        ):
            expanded.add(node.id if node.parent_id is None else node.parent_id)
    return frozenset(expanded)


class _EveryId(Collection[str]):
    """An expanded set that holds every id, so one build opens every node."""

    def __contains__(self, item: object) -> bool:
        return True

    def __iter__(self) -> Iterator[str]:
        return iter(())

    def __len__(self) -> int:
        return 0


_EVERY_ID = _EveryId()


def all_navigator_ids(session: TuningSession) -> frozenset[str]:
    """Every navigator id that would show with all of its ancestors open."""
    return frozenset(node.id for node in build_navigator(session, _EVERY_ID))


@dataclass(frozen=True)
class PageStatus:
    """Why an inspector page has no effect or refuses edits.

    ``off_by`` and ``locked_by`` name the nearest page, the page itself or a
    parent that owns it, whose on/off switch is off or that is locked.
    """

    off_by: str | None = None
    locked_by: str | None = None


def _page_chain(
    session: TuningSession,
    node_id: str,
    nodes: Sequence[NavNode] | None,
) -> list[NavNode]:
    """The page's navigator node, then each parent's, nearest first.

    A timeline row page has no node and follows Timeline. *nodes* is a
    navigator already built this frame; it is used when it holds the page,
    which means it holds the page's parents too.
    """
    if timeline_row_slot_of(node_id) is not None:
        node_id = "timeline"
    chain = [node_id]
    parent = parent_id_of(node_id)
    while parent is not None:
        chain.append(parent)
        parent = parent_id_of(parent)
    by_id = {} if nodes is None else {node.id: node for node in nodes}
    if node_id not in by_id:
        by_id = {node.id: node for node in build_navigator(session, set(chain))}
    return [by_id[chain_id] for chain_id in chain if chain_id in by_id]


def page_status(
    session: TuningSession,
    node_id: str,
    nodes: Sequence[NavNode] | None = None,
) -> PageStatus:
    """Off and locked owners for the inspector page *node_id*.

    A timeline row page follows Timeline. An inert switch (layer visibility
    while the timeline owns it) does not count, and config pages have none.
    """
    off_by: str | None = None
    locked_by: str | None = None
    for node in _page_chain(session, node_id, nodes):
        name = " ".join(node.label.split())
        toggles = {toggle.id: toggle for toggle in node.toggles}
        switch = toggles.get(TOGGLE_ENABLED)
        if (
            off_by is None
            and switch is not None
            and not switch.active
            and not switch.inert
        ):
            off_by = name
        lock = toggles.get(TOGGLE_LOCK)
        if locked_by is None and (node.locked or (lock is not None and lock.active)):
            locked_by = name
    return PageStatus(off_by=off_by, locked_by=locked_by)


# Title-line icons, in the navigator's column order.
_PAGE_TOGGLE_ORDER = (
    TOGGLE_WARN,
    TOGGLE_HOLD,
    TOGGLE_ENABLED,
    TOGGLE_SOLO,
    TOGGLE_PREVIEW,
    TOGGLE_LOCK,
)


@dataclass(frozen=True)
class PageToggle:
    """A navigator on/off, solo, preview, or lock icon that acts for an inspector page.

    ``owner_id`` is the nearest node, the page itself or a parent, that
    carries the icon, and ``owner_label`` its name.
    """

    toggle: NavToggle
    owner_id: str
    owner_label: str


def page_toggles(
    session: TuningSession,
    node_id: str,
    nodes: Sequence[NavNode] | None = None,
) -> tuple[PageToggle, ...]:
    """The warning, held-switching, on/off, solo or preview, then lock icons that act
    for the inspector page *node_id*, in the navigator's column order.

    Each comes from the nearest node in the page's chain that has it, so a
    Post-FX child page acts on Post-FX, a layer page solos its layer, and a
    card's on/off acts on the card while its preview and lock are Overlay's.
    Config pages and preset curation have none.
    """
    found: dict[str, PageToggle] = {}
    for node in _page_chain(session, node_id, nodes):
        for toggle in node.toggles:
            if toggle.id in _PAGE_TOGGLE_ORDER and toggle.id not in found:
                found[toggle.id] = PageToggle(
                    toggle, node.id, " ".join(node.label.split())
                )
    return tuple(found[key] for key in _PAGE_TOGGLE_ORDER if key in found)


def navigator_row_bright(node: NavNode) -> bool:
    """True for rows drawn in the value colour: roots and the layer rows."""
    return node.depth == 0 or node.parent_id == "layers"


def navigator_row_text_color(
    node: NavNode, *, selected: bool, moving: bool
) -> tuple[int, int, int]:
    """Label colour for a navigator row.

    A layer in move mode wins. The selected row, roots, and layer rows are
    ``value``; the selected row's band sets it apart.
    """
    if moving:
        return palette().move_mode
    return palette().value if selected or navigator_row_bright(node) else palette().label


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
        return replace(
            node,
            toggles=(
                NavToggle(TOGGLE_PREVIEW, session.overlay_preview),
                NavToggle(TOGGLE_LOCK, overlays.locked),
            ),
        )
    if node.id == "post_fx":
        return replace(
            node, toggles=(NavToggle(TOGGLE_LOCK, session.post_fx.locked),)
        )
    if node.id == "pattern_mask":
        return replace(node, toggles=_block_toggles(session.pattern_mask))
    if node.id == "timeline":
        return replace(node, toggles=_block_toggles(session.timeline))
    if node.id == "layers" and not is_preset_curation_mode(
        session.settings.editor_mode
    ):
        full = len(session.layer_z_order) >= MAX_LAYER_COUNT
        return replace(node, toggles=(NavToggle(TOGGLE_ADD, True, full),))
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
            badge=None,
            parent_id=parent_id,
            toggles=_static_child_toggles(session, node_id),
        )
        for node_id, label in _STATIC_CHILDREN.get(parent_id, ())
    )


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
    post_fx = session.post_fx
    if node_id == "post_fx.fade":
        return (NavToggle(TOGGLE_ENABLED, post_fx.fade.enabled, post_fx.locked),)
    if node_id == "post_fx.highlight_rolloff":
        return (
            NavToggle(
                TOGGLE_ENABLED, post_fx.highlight_rolloff.enabled, post_fx.locked
            ),
        )
    if node_id == "post_fx.chroma_boost":
        return (
            NavToggle(TOGGLE_ENABLED, post_fx.chroma_boost.enabled, post_fx.locked),
        )
    if node_id == "post_fx.limiter":
        # The limiter ignores the Post-FX lock and switch.
        return (NavToggle(TOGGLE_ENABLED, post_fx.limiter.enabled),)
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
            nodes.extend(layer_page_nodes(session, slot))
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
    number = str(index + 1)
    return NavNode(
        id=layer_node_id(slot),
        label=f"{number}  {stem_overlay_header(layer.stem)}",
        depth=1,
        badge=_layer_badge(session, slot) if curation else None,
        parent_id="layers",
        expandable=expandable,
        slot=slot,
        locked=curation and layer.locked,
        toggles=() if curation else _layer_toggles(session, slot),
        draggable=not curation,
        drag_blocked=layer.locked,
        handle_text="" if curation else number,
    )


def _layer_toggles(session: TuningSession, slot: str) -> tuple[NavToggle, ...]:
    layer = session.layers[slot]
    lead: list[NavToggle] = []
    problems = layer_problems(session, slot)
    if problems:
        lead.append(
            NavToggle(TOGGLE_WARN, True, detail=layer_problems_tooltip(problems))
        )
    if switching_held(session, slot):
        lead.append(NavToggle(TOGGLE_HOLD, True, layer.locked))
    return tuple(lead) + (
        NavToggle(
            TOGGLE_ENABLED,
            layer.enabled,
            layer.locked,
            inert=session.timeline.enabled,
        ),
        NavToggle(TOGGLE_SOLO, session.solo_slot == slot),
        NavToggle(TOGGLE_LOCK, layer.locked),
    )


_PROBLEM_PAGES = {
    ProblemPage.MILKDROP_PRESET: LAYER_PAGE_MILKDROP_PRESET,
    ProblemPage.PRESET_SWITCHING: LAYER_PAGE_PRESET_SWITCHING,
    ProblemPage.PRESET_LIST: LAYER_PAGE_PRESET_LIST,
    ProblemPage.COMPOSITING: LAYER_PAGE_COMPOSITING,
}


def first_problem_page_id(session: TuningSession, slot: str) -> str | None:
    """Navigator id of the page that fixes the layer's first problem, if any."""
    problems = layer_problems(session, slot)
    if not problems:
        return None
    page = _PROBLEM_PAGES[problems[0].page]
    if not _layer_page_visible(session, slot, page):
        page = LAYER_PAGE_PRESET_SWITCHING
    return layer_page_node_id(slot, page)


def switching_held(session: TuningSession, slot: str) -> bool:
    """True while browsing has paused the layer's preset switching."""
    layer = session.layers[slot]
    return layer.switching_paused and layer.preset_switching == "on"


def _layer_page_visible(session: TuningSession, slot: str, page: str) -> bool:
    if page == LAYER_PAGE_PRESET_LIST:
        return session.layers[slot].preset_switching_trigger != "off"
    return True


def layer_page_nodes(session: TuningSession, slot: str) -> tuple[NavNode, ...]:
    """Page rows under *slot*, as the navigator shows them while it is open."""
    return tuple(
        NavNode(
            id=layer_page_node_id(slot, page),
            label=label,
            depth=3 if page in _LAYER_SUBPAGE_PARENTS else 2,
            badge=None,
            parent_id=parent_id_of(layer_page_node_id(slot, page)),
            slot=slot,
        )
        for page, label in _LAYER_PAGES
        if _layer_page_visible(session, slot, page)
    )


def _layer_badge(session: TuningSession, slot: str) -> str | None:
    if session.solo_slot == slot:
        return SOLO_BADGE
    if not session.layers[slot].enabled:
        return HIDDEN_BADGE
    return None

