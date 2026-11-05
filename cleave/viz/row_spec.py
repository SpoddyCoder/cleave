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

from cleave.viz.row_kinds import RowAffordance, RowDescriptor, RowKind
from cleave.viz.row_sections import (
    OVERLAY_SECTION_KINDS,
    PATTERN_MASK_SECTION_KINDS,
    POST_FX_SECTION_KINDS,
    TIMELINE_SECTION_KINDS,
)
from cleave.viz.tuning_view_state import TuningViewState

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls


class RowPresentStyle(Enum):
    LABELED_VALUE = auto()
    HEADING = auto()
    PATH_ICON = auto()
    FULL_LINE = auto()
    DYNAMIC = auto()


class FitStrategy(Enum):
    PLAIN = auto()
    PATH = auto()
    NONE = auto()


FieldMutator = Callable[["TuningControls", RowDescriptor, bool, bool], None]
ActionMutator = Callable[["TuningControls", RowDescriptor], None]
VisibilityIconFn = Callable[[TuningViewState, RowDescriptor], tuple[bool, bool]]


@dataclass(frozen=True)
class RowNavButton:
    """Icon button after a row label. Dims when *available* is false."""

    glyph: str
    available: Callable[[TuningViewState, RowDescriptor], bool]
    action: ActionMutator


@dataclass(frozen=True)
class RowSpec:
    affordance: RowAffordance
    panel_label: str
    present_style: RowPresentStyle
    format_value: Callable[[TuningViewState, RowDescriptor], str] | None = None
    # Set on two-line rows: position sits in the arrows on the label line, with
    # the markers after the label. format_value is the second line.
    format_position: Callable[[TuningViewState, RowDescriptor], str] | None = None
    format_markers: Callable[[TuningViewState, RowDescriptor], str] | None = None
    nav_buttons: tuple[RowNavButton, ...] = ()
    apply_horizontal: FieldMutator | None = None
    apply_action: ActionMutator | None = None
    # A mouse click only focuses the row. Double-click runs apply_action.
    activate_on_double_click: bool = False
    fit_strategy: FitStrategy = FitStrategy.PLAIN
    visibility_icon: VisibilityIconFn | None = None
    header_glyph: str | None = None
    header_glyph_color: tuple[int, int, int] | None = None
    shows_enter_icon: bool = False
    shows_dirty_suffix: bool = False
    help_title: str = ""
    help_entries: tuple[tuple[str, str], ...] | None = None
    help_description: tuple[str, ...] | None = None
    help_mode_entries: tuple[tuple[str, str], ...] | None = None
    navigable: bool = True
    is_header: bool = False
    is_pinned: bool = False
    toggle_enabled: ActionMutator | None = None
    toggle_solo: ActionMutator | None = None
    can_enter_move_mode: bool = False
    repeatable: bool = False
    parent_group: str | None = None
    blocked_by_section_lock: bool | None = None
    navigable_when_section_locked: bool | None = None


# Domain modules import RowSpec from this module, so assembly happens after the
# dataclass is defined.
from cleave.viz.row_specs.pattern_mask import SPECS as _PATTERN_MASK_SPECS
from cleave.viz.row_specs.overlays import (
    SPECS as _OVERLAY_SPECS,
    overlay_card_panel_label,
)
from cleave.viz.row_specs.post_fx import SPECS as _POST_FX_SPECS
from cleave.viz.row_specs.project import SPECS as _PROJECT_SPECS
from cleave.viz.row_specs.settings import SPECS as _SETTINGS_SPECS
from cleave.viz.row_specs.timeline import SPECS as _TIMELINE_SPECS
from cleave.viz.row_specs.track import SPECS as _TRACK_SPECS

ROW_SPECS: dict[RowKind, RowSpec] = {
    **_SETTINGS_SPECS,
    **_PROJECT_SPECS,
    **_TRACK_SPECS,
    **_OVERLAY_SPECS,
    **_POST_FX_SPECS,
    **_PATTERN_MASK_SPECS,
    **_TIMELINE_SPECS,
}

_missing = set(RowKind) - set(ROW_SPECS)
_duplicate_overlap = (
    len(_SETTINGS_SPECS)
    + len(_PROJECT_SPECS)
    + len(_TRACK_SPECS)
    + len(_OVERLAY_SPECS)
    + len(_POST_FX_SPECS)
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
TRACK_SUB_ROW_KINDS = frozenset(
    k for k, spec in ROW_SPECS.items() if spec.parent_group == "track"
)
TRACK_LOCK_KINDS = TRACK_SUB_ROW_KINDS | frozenset({RowKind.TRACK_HEADER})
PRESET_FILE_ROW_KINDS = frozenset({RowKind.TRACK_PRESET, RowKind.TRACK_PRESET_LIST_ITEM})

_SECTION_LOCK_BLOCKING_AFFORDANCES = frozenset(
    {
        RowAffordance.VALUE_STEP,
        RowAffordance.PATH_DIR,
        RowAffordance.PATH_PRESET,
    }
)


def _in_lockable_group(parent_group: str | None) -> bool:
    if parent_group is None:
        return False
    return (
        parent_group == "track"
        or parent_group.startswith("overlay")
        or parent_group.startswith("post_fx")
        or parent_group.startswith("pattern_mask")
    )


def row_is_pinned(kind: RowKind) -> bool:
    spec = row_spec(kind)
    return spec.is_header or spec.is_pinned


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
    return spec.affordance == RowAffordance.HEADING


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


def row_lock_section(kind: RowKind) -> str | None:
    if kind in TRACK_LOCK_KINDS:
        return "track"
    if kind in OVERLAY_SECTION_KINDS:
        return "overlay"
    if kind in POST_FX_SECTION_KINDS:
        return "post_fx"
    if kind in PATTERN_MASK_SECTION_KINDS:
        return "pattern_mask"
    if kind in TIMELINE_SECTION_KINDS:
        return "timeline"
    return None


def section_locked(state: object, desc: RowDescriptor) -> bool:
    """Whether the section owning *desc* is locked.

    Accepts either a ``TuningViewState`` or a ``TuningSession``.

    Section locks are ignored in preset curation mode so layer browse and
    favourite / blacklist / restore stay available.
    """
    settings = getattr(state, "settings", None)
    if settings is not None and getattr(settings, "editor_mode", None) == (
        "preset_curation"
    ):
        return False
    section = row_lock_section(desc.kind)
    if section is None:
        return False
    if section == "track":
        slot = desc.slot
        if slot is None:
            return False
        return _state_track_locked(state, slot)
    if section == "overlay":
        return bool(state.overlays.locked)
    if section == "post_fx":
        return bool(state.post_fx.locked)
    if section == "pattern_mask":
        return bool(state.pattern_mask.locked)
    if section == "timeline":
        return bool(state.timeline.locked)
    return False


def section_lock_blocks_mutation(state: object, desc: RowDescriptor) -> bool:
    return section_locked(state, desc) and row_blocked_by_section_lock(desc.kind)


def row_triggers_layer_delete(kind: RowKind) -> bool:
    """True when Delete should prompt to remove the focused track block's layer."""
    if kind == RowKind.TRACK_HEADER:
        return True
    return row_spec(kind).parent_group == "track"


def row_panel_label(kind: RowKind, desc: RowDescriptor | None = None) -> str:
    if desc is not None:
        if kind == RowKind.TRACK_EFFECT:
            return row_dynamic_panel_label(desc)
        overlay_label = overlay_card_panel_label(kind, desc.card)
        if overlay_label is not None:
            return overlay_label
    return row_spec(kind).panel_label


def format_row_value(state: TuningViewState, desc: RowDescriptor) -> str:
    spec = row_spec(desc.kind)
    assert spec.format_value is not None, f"no format_value for {desc.kind!r}"
    return spec.format_value(state, desc)


def row_is_two_line(kind: RowKind) -> bool:
    return row_spec(kind).format_position is not None


def format_row_position(state: TuningViewState, desc: RowDescriptor) -> str:
    spec = row_spec(desc.kind)
    assert spec.format_position is not None, f"no format_position for {desc.kind!r}"
    return spec.format_position(state, desc)


def format_row_markers(state: TuningViewState, desc: RowDescriptor) -> str:
    spec = row_spec(desc.kind)
    if spec.format_markers is None:
        return ""
    return spec.format_markers(state, desc)


def row_dynamic_panel_label(desc: RowDescriptor) -> str:
    assert desc.kind == RowKind.TRACK_EFFECT
    assert desc.effect_id is not None and desc.driver_slug is not None
    return f"{desc.effect_id} ({desc.driver_slug})"


def apply_field_horizontal(
    controls: TuningControls,
    desc: RowDescriptor,
    forward: bool,
    large: bool,
) -> bool:
    spec = ROW_SPECS.get(desc.kind)
    if spec is None or spec.apply_horizontal is None:
        return False
    if section_lock_blocks_mutation(controls.session, desc):
        return False
    spec.apply_horizontal(controls, desc, forward, large)
    return True


def apply_field_action(
    controls: TuningControls,
    desc: RowDescriptor,
) -> bool:
    spec = ROW_SPECS.get(desc.kind)
    if spec is None or spec.apply_action is None:
        return False
    if section_lock_blocks_mutation(controls.session, desc):
        return True
    spec.apply_action(controls, desc)
    return True


def apply_field_nav_button(
    controls: TuningControls,
    desc: RowDescriptor,
    index: int,
) -> bool:
    """Run the icon button at *index*. False when the section lock blocks it."""
    if section_lock_blocks_mutation(controls.session, desc):
        return False
    button = row_spec(desc.kind).nav_buttons[index]
    button.action(controls, desc)
    return True


def apply_field_toggle_enabled(
    controls: TuningControls,
    desc: RowDescriptor,
) -> bool:
    spec = ROW_SPECS.get(desc.kind)
    if spec is None or spec.toggle_enabled is None:
        return False
    spec.toggle_enabled(controls, desc)
    return True


def apply_field_toggle_solo(
    controls: TuningControls,
    desc: RowDescriptor,
) -> bool:
    spec = ROW_SPECS.get(desc.kind)
    if spec is None or spec.toggle_solo is None:
        return False
    spec.toggle_solo(controls, desc)
    return True
