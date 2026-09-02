"""Unified panel row spec for the live tuning overlay.

``RowSpec`` is the single registry entry per ``RowKind``: affordance, help,
navigation, labels, present style, and Left/Right mutations. Placement stays
in row_sections.py. Identity types live in row_kinds.py.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from cleave.stems import stem_overlay_header
from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_sections import (
    RENDER_OVERLAY_SECTION_KINDS,
    RENDER_PATTERN_MASK_SECTION_KINDS,
    RENDER_POST_FX_SECTION_KINDS,
    RENDER_TIMELINE_SECTION_KINDS,
    expand_arrow_for_header,
    expand_arrow_glyph,
    row_tree_indent_depth,
    section_header_from_section_tree,
)
from cleave.viz.tuning_view_state import TuningViewState

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls


class RowPresentStyle(Enum):
    LABELED_VALUE = auto()
    ACTION_PARAMETER = auto()
    EXPAND_SUBHEADER = auto()
    COMPOSITE_HEADER = auto()
    PATH_ICON = auto()
    FULL_LINE = auto()
    DYNAMIC = auto()
    TRACK_HEADER = auto()
    NOTIFICATION = auto()
    SPACER = auto()


class FitStrategy(Enum):
    PLAIN = auto()
    COUNTER_LABEL = auto()
    PATH = auto()
    NONE = auto()


FieldMutator = Callable[["TuningControls", RowDescriptor, bool, bool, bool], None]
VisibilityIconFn = Callable[[TuningViewState, RowDescriptor], tuple[bool, bool]]


@dataclass(frozen=True)
class RowSpec:
    affordance: RowAffordance
    panel_label: str
    present_style: RowPresentStyle
    format_value: Callable[[TuningViewState, RowDescriptor], str] | None = None
    apply_horizontal: FieldMutator | None = None
    header_prefix: str | None = None
    header_suffix: str | None = None
    fit_strategy: FitStrategy = FitStrategy.PLAIN
    visibility_icon: VisibilityIconFn | None = None
    shows_enter_icon: bool = False
    help_title: str = ""
    help_entries: tuple[tuple[str, str], ...] | None = None
    help_description: tuple[str, ...] | None = None
    help_mode_entries: tuple[tuple[str, str], ...] | None = None
    navigable: bool = True
    quick_nav_target: bool = False
    quick_nav_always: bool = False
    is_header: bool = False
    is_sub_header: bool = False
    is_pinned: bool = False
    can_enable_disable: bool = False
    can_solo: bool = False
    can_enter_move_mode: bool = False
    repeatable: bool = False
    parent_group: str | None = None
    blocked_by_section_lock: bool | None = None
    navigable_when_section_locked: bool | None = None


# Domain modules import RowSpec from this module, so assembly happens after the
# dataclass is defined.
from cleave.viz.row_specs.pattern_mask import SPECS as _PATTERN_MASK_SPECS
from cleave.viz.row_specs.render_overlays import (
    SPECS as _RENDER_OVERLAY_SPECS,
    overlay_card_panel_label,
)
from cleave.viz.row_specs.render_post_fx import SPECS as _RENDER_POST_FX_SPECS
from cleave.viz.row_specs.settings import (
    SPECS as _SETTINGS_SPECS,
    editor_mode_confirm_pending,
)
from cleave.viz.row_specs.timeline import SPECS as _TIMELINE_SPECS
from cleave.viz.row_specs.track import SPECS as _TRACK_SPECS
from cleave.viz.row_specs.transport import SPECS as _TRANSPORT_SPECS

ROW_SPECS: dict[RowKind, RowSpec] = {
    **_TRANSPORT_SPECS,
    **_SETTINGS_SPECS,
    **_TRACK_SPECS,
    **_RENDER_OVERLAY_SPECS,
    **_RENDER_POST_FX_SPECS,
    **_PATTERN_MASK_SPECS,
    **_TIMELINE_SPECS,
}

_missing = set(RowKind) - set(ROW_SPECS)
_duplicate_overlap = (
    len(_TRANSPORT_SPECS)
    + len(_SETTINGS_SPECS)
    + len(_TRACK_SPECS)
    + len(_RENDER_OVERLAY_SPECS)
    + len(_RENDER_POST_FX_SPECS)
    + len(_PATTERN_MASK_SPECS)
    + len(_TIMELINE_SPECS)
) - len(ROW_SPECS)
assert not _missing and _duplicate_overlap == 0, (
    f"RowSpec registry is incomplete or overlapping: missing={_missing!r} "
    f"overlap={_duplicate_overlap}"
)


def row_spec(kind: RowKind) -> RowSpec:
    spec = ROW_SPECS.get(kind)
    assert spec is not None, f"missing RowSpec for {kind!r}"
    return spec


HEADER_ROW_KINDS = frozenset(k for k, spec in ROW_SPECS.items() if spec.is_header)
REPEAT_ROW_KINDS = frozenset(k for k, spec in ROW_SPECS.items() if spec.repeatable)
ACTION_ROW_KINDS = frozenset(
    k for k, spec in ROW_SPECS.items() if spec.affordance == RowAffordance.ACTION
)
LABELED_SUB_ROW_KINDS = frozenset(
    k
    for k, spec in ROW_SPECS.items()
    if spec.affordance
    in {
        RowAffordance.VALUE_STEP,
        RowAffordance.PATH_DIR,
        RowAffordance.PATH_PRESET,
    }
    and not spec.is_header
)

TRACK_SUB_ROW_KINDS = frozenset(
    k for k, spec in ROW_SPECS.items() if spec.parent_group == "track"
)
TRACK_LOCK_KINDS = TRACK_SUB_ROW_KINDS | frozenset({RowKind.TRACK_HEADER})
TRACK_EFFECT_SUB_ROW_KINDS = frozenset({RowKind.TRACK_EFFECT})
TRACK_PRESET_LIST_SUB_ROW_KINDS = frozenset(
    {
        RowKind.TRACK_PRESET_LIST_ITEM,
        RowKind.TRACK_PRESET_LIST_ADD,
        RowKind.TRACK_PRESET_LIST_POPULATE,
    }
)
SONG_MARKER_SUB_ROW_KINDS = frozenset({RowKind.SONG_MARKER_ITEM})
PRESET_FILE_ROW_KINDS = frozenset({RowKind.TRACK_PRESET, RowKind.TRACK_PRESET_LIST_ITEM})

_SECTION_LOCK_BLOCKING_AFFORDANCES = frozenset(
    {
        RowAffordance.VALUE_STEP,
        RowAffordance.ACTION_PARAMETER,
        RowAffordance.PATH_DIR,
        RowAffordance.PATH_PRESET,
    }
)


def _in_lockable_group(parent_group: str | None) -> bool:
    if parent_group is None:
        return False
    return (
        parent_group == "track"
        or parent_group.startswith("render_overlay")
        or parent_group.startswith("render_post_fx")
        or parent_group.startswith("render_pattern_mask")
    )


def row_is_pinned(kind: RowKind) -> bool:
    spec = row_spec(kind)
    return spec.is_header or spec.is_pinned


def expandable_row_kinds() -> frozenset[RowKind]:
    return frozenset(
        k for k, spec in ROW_SPECS.items() if spec.affordance == RowAffordance.EXPAND
    )


def _derived_blocked_by_section_lock(spec: RowSpec) -> bool:
    if spec.blocked_by_section_lock is not None:
        return spec.blocked_by_section_lock
    return (
        _in_lockable_group(spec.parent_group)
        and spec.affordance in _SECTION_LOCK_BLOCKING_AFFORDANCES
    )


def _derived_navigable_when_section_locked(spec: RowSpec) -> bool:
    if spec.navigable_when_section_locked is not None:
        return spec.navigable_when_section_locked
    # Section and sub-section headers stay navigable so the section can still be
    # expanded and viewed while locked.
    return spec.affordance == RowAffordance.EXPAND


def row_blocked_by_section_lock(kind: RowKind) -> bool:
    return _derived_blocked_by_section_lock(row_spec(kind))


def row_navigable_when_section_locked(kind: RowKind) -> bool:
    return _derived_navigable_when_section_locked(row_spec(kind))


def _state_track_locked(state: object, slot: str) -> bool:
    tracks = getattr(state, "tracks", None)
    if tracks is not None:
        track = tracks[slot]
        runtime = getattr(track, "runtime", None)
        if runtime is not None:
            return bool(runtime.locked)
        return bool(track.locked)
    return bool(state.layers[slot].locked)


def _state_timeline_locked(state: object) -> bool:
    render_timeline = getattr(state, "render_timeline", None)
    if render_timeline is not None:
        return bool(render_timeline.locked)
    return bool(state.timeline.locked)


def _row_lock_section(kind: RowKind) -> str | None:
    if kind in TRACK_LOCK_KINDS:
        return "track"
    if kind in RENDER_OVERLAY_SECTION_KINDS:
        return "render_overlay"
    if kind in RENDER_POST_FX_SECTION_KINDS:
        return "render_post_fx"
    if kind in RENDER_PATTERN_MASK_SECTION_KINDS:
        return "render_pattern_mask"
    if kind in RENDER_TIMELINE_SECTION_KINDS:
        return "timeline"
    return None


def section_locked(state: object, desc: RowDescriptor) -> bool:
    """Whether the section owning *desc* is locked.

    Accepts either a ``TuningViewState`` (tracks/render_timeline attributes)
    or a ``TuningSession`` (layers/timeline attributes).

    Section locks are ignored in preset curation mode so layer browse and
    favourite / blacklist / restore stay available.
    """
    settings = getattr(state, "settings", None)
    if settings is not None and getattr(settings, "editor_mode", None) == (
        "preset_curation"
    ):
        return False
    section = _row_lock_section(desc.kind)
    if section is None:
        return False
    if section == "track":
        slot = desc.slot
        if slot is None:
            return False
        return _state_track_locked(state, slot)
    if section == "render_overlay":
        return bool(state.render_overlays.locked)
    if section == "render_post_fx":
        return bool(state.render_post_fx.locked)
    if section == "render_pattern_mask":
        return bool(state.render_pattern_mask.locked)
    if section == "timeline":
        return _state_timeline_locked(state)
    return False


def section_lock_blocks_mutation(state: object, desc: RowDescriptor) -> bool:
    return section_locked(state, desc) and row_blocked_by_section_lock(desc.kind)


def row_triggers_layer_delete(kind: RowKind) -> bool:
    """True when Delete should prompt to remove the focused track block's layer."""
    if kind == RowKind.TRACK_HEADER:
        return True
    return row_spec(kind).parent_group == "track"


def section_header_descriptor(desc: RowDescriptor) -> RowDescriptor:
    """Map a sub-row descriptor to its section header for focus fallback."""
    from_tree = section_header_from_section_tree(desc)
    if from_tree is not None:
        return from_tree
    kind = desc.kind
    if kind in TRACK_EFFECT_SUB_ROW_KINDS:
        return RowDescriptor(RowKind.TRACK_EFFECTS_HEADER, slot=desc.slot)
    if kind in TRACK_PRESET_LIST_SUB_ROW_KINDS:
        return RowDescriptor(RowKind.TRACK_PRESET_LIST, slot=desc.slot)
    if kind in SONG_MARKER_SUB_ROW_KINDS:
        return RowDescriptor(RowKind.SONG_MARKERS_HEADER)
    return desc


def tree_branch_leading_spaces(depth: int) -> str:
    """Leading spaces before a branch glyph for nested tree depth."""
    if depth <= 1:
        return ""
    return " " * (2 * (depth - 1))


def tree_branch_prefix(depth: int) -> str:
    """Branch glyph for tree depth; pixel indent comes from row_tree_indent_depth."""
    if depth <= 0:
        return ""
    return tree_branch_leading_spaces(depth) + "└─ "


def row_panel_label(kind: RowKind, desc: RowDescriptor | None = None) -> str:
    if desc is not None:
        overlay_label = overlay_card_panel_label(kind, desc.card)
        if overlay_label is not None:
            return overlay_label
    return row_spec(kind).panel_label


def format_row_value(state: TuningViewState, desc: RowDescriptor) -> str:
    spec = row_spec(desc.kind)
    assert spec.format_value is not None, f"no format_value for {desc.kind!r}"
    return spec.format_value(state, desc)


def labeled_row_prefix(kind: RowKind, desc: RowDescriptor | None = None) -> str:
    depth = row_tree_indent_depth(kind)
    return tree_branch_prefix(depth) + row_panel_label(kind, desc) + ": "


def row_labeled_display_text(state: TuningViewState, desc: RowDescriptor) -> str:
    return labeled_row_prefix(desc.kind, desc) + format_row_value(state, desc)


def row_action_parameter_display_text(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return labeled_row_prefix(desc.kind, desc) + format_row_value(state, desc)


def expand_subheader_prefix(
    kind: RowKind, desc: RowDescriptor | None = None
) -> str:
    depth = row_tree_indent_depth(kind)
    spec = row_spec(kind)
    label = tree_branch_prefix(depth) + row_panel_label(kind, desc)
    if spec.format_value is not None:
        # Status/value before the expand arrow uses labeled "label: value" form.
        # Parenthetical suffixes (e.g. song markers "(N)") keep a space.
        return label
    return label + " "


def format_expand_subheader_value(state: TuningViewState, desc: RowDescriptor) -> str:
    arrow = expand_arrow_for_header(state, desc.kind, desc.slot, card=desc.card)
    spec = row_spec(desc.kind)
    if spec.format_value is not None:
        suffix = spec.format_value(state, desc)
        if suffix:
            if suffix.startswith("("):
                return f" {suffix} {arrow}"
            return f": {suffix} {arrow}"
    return arrow


def row_expand_subheader_display_text(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return expand_subheader_prefix(desc.kind, desc) + format_expand_subheader_value(
        state, desc
    )


def _track_header_layer_prefix(state: TuningViewState, slot: str) -> str:
    layer_num = state.layer_z_order.index(slot) + 1
    return f"Layer {layer_num}: "


def composite_header_prefix_part(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    spec = row_spec(desc.kind)
    if spec.present_style == RowPresentStyle.TRACK_HEADER:
        assert desc.slot is not None
        return _track_header_layer_prefix(state, desc.slot)
    if desc.kind == RowKind.SETTINGS_HEADER:
        return f"{spec.panel_label} "
    if spec.header_prefix is not None:
        return spec.header_prefix
    return f"{spec.panel_label} "


def composite_header_suffix_part(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    spec = row_spec(desc.kind)
    if desc.kind == RowKind.SETTINGS_HEADER:
        return ""
    if spec.present_style == RowPresentStyle.TRACK_HEADER:
        assert desc.slot is not None
        return stem_overlay_header(state.tracks[desc.slot].runtime.stem)
    assert spec.header_suffix is not None
    return spec.header_suffix


def format_composite_header_expand_value(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    if desc.kind == RowKind.RENDER_TIMELINE_HEADER:
        return expand_arrow_glyph(state.render_timeline.expanded)
    return expand_arrow_for_header(state, desc.kind, desc.slot, card=desc.card)


def row_composite_header_display_text(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    body = (composite_header_prefix_part(state, desc) + composite_header_suffix_part(
        state, desc
    )).rstrip()
    arrow = format_composite_header_expand_value(state, desc)
    return f"{body} {arrow}"


def row_dynamic_panel_label(desc: RowDescriptor) -> str:
    assert desc.kind == RowKind.TRACK_EFFECT
    assert desc.effect_id is not None and desc.driver_slug is not None
    return f"{desc.effect_id} ({desc.driver_slug})"


def _full_line_branch_depth(kind: RowKind) -> int:
    if kind == RowKind.LAYER_MANAGEMENT_DELETE:
        return 1
    return row_tree_indent_depth(kind)


def full_line_prefix(kind: RowKind) -> str:
    return tree_branch_prefix(_full_line_branch_depth(kind)) + row_panel_label(kind)


def row_full_line_display_text(state: TuningViewState, desc: RowDescriptor) -> str:
    spec = row_spec(desc.kind)
    if spec.present_style == RowPresentStyle.NOTIFICATION:
        assert spec.format_value is not None
        return spec.format_value(state, desc)
    if desc.kind == RowKind.TRANSPORT:
        return ""
    if spec.format_value is not None:
        return (
            tree_branch_prefix(_full_line_branch_depth(desc.kind))
            + spec.format_value(state, desc)
        )
    return full_line_prefix(desc.kind)


def row_dynamic_labeled_prefix(desc: RowDescriptor) -> str:
    depth = row_tree_indent_depth(desc.kind)
    return tree_branch_prefix(depth) + row_dynamic_panel_label(desc) + ": "


def row_dynamic_labeled_display_text(
    state: TuningViewState, desc: RowDescriptor
) -> str:
    return row_dynamic_labeled_prefix(desc) + format_row_value(state, desc)


def apply_field_horizontal(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    ctrl: bool,
    shift: bool = False,
) -> bool:
    spec = ROW_SPECS.get(desc.kind)
    if spec is None or spec.apply_horizontal is None:
        return False
    spec.apply_horizontal(controls, desc, forward, ctrl, shift)
    return True
