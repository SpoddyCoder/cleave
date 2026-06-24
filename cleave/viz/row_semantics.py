"""Row interaction semantics for the live tuning overlay."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class RowKind(Enum):
    TRACK_HEADER = auto()
    TRACK_PRESET_DIR = auto()
    TRACK_PRESET = auto()
    TRACK_PRESET_SWITCHING = auto()
    TRACK_PRESET_SWITCHING_SCOPE = auto()
    TRACK_STEM = auto()
    TRACK_BLEND = auto()
    TRACK_OPACITY = auto()
    TRACK_BEAT = auto()
    TRACK_EFFECTS_HEADER = auto()
    TRACK_EFFECT = auto()
    LAYER_MANAGEMENT_ADD = auto()
    LAYER_MANAGEMENT_DELETE = auto()
    PANEL_NOTIFICATION = auto()
    RENDER_SECTION_GAP = auto()
    RENDER_OVERLAY_HEADER = auto()
    RENDER_OVERLAY_POSITION = auto()
    RENDER_OVERLAY_TITLE_HEADER = auto()
    RENDER_OVERLAY_TITLE_FONT_SIZE = auto()
    RENDER_OVERLAY_TITLE_FONT = auto()
    RENDER_OVERLAY_TITLE_MARGIN_BOTTOM = auto()
    RENDER_OVERLAY_BODY_HEADER = auto()
    RENDER_OVERLAY_BODY_FONT_SIZE = auto()
    RENDER_OVERLAY_BODY_FONT = auto()
    RENDER_OVERLAY_OPACITY = auto()
    RENDER_OVERLAY_BORDER_WIDTH = auto()
    RENDER_OVERLAY_START_DELAY = auto()
    RENDER_OVERLAY_DISPLAY_TIME = auto()
    RENDER_POST_FX_HEADER = auto()
    RENDER_POST_FX_FADE_IN = auto()
    RENDER_POST_FX_FADE_OUT = auto()
    RENDER_TIMELINE_HEADER = auto()
    SETTINGS_HEADER = auto()
    SETTINGS_RENDER_MODE = auto()
    CONFIG_HEADER = auto()
    TRANSPORT = auto()


@dataclass(frozen=True)
class RowDescriptor:
    kind: RowKind
    slot: str | None = None
    effect_id: str | None = None
    driver_slug: str | None = None


class RowAffordance(Enum):
    EXPAND = auto()
    VALUE_STEP = auto()
    PATH_DIR = auto()
    PATH_PRESET = auto()
    SEEK = auto()
    ACTION = auto()
    DISPLAY = auto()


@dataclass(frozen=True)
class RowBehavior:
    affordance: RowAffordance
    help_title: str = ""
    help_entries: tuple[tuple[str, str], ...] | None = None
    navigable: bool = True
    quick_nav_target: bool = False
    is_header: bool = False
    is_sub_header: bool = False
    is_pinned: bool = False
    can_enable_disable: bool = False
    can_solo: bool = False
    can_enter_move_mode: bool = False
    repeatable: bool = False
    parent_group: str | None = None
    blocked_by_layer_lock: bool | None = None
    navigable_when_layer_locked: bool | None = None


ROW_BEHAVIORS: dict[RowKind, RowBehavior] = {
    RowKind.TRANSPORT: RowBehavior(
        RowAffordance.SEEK,
        is_header=True,
        repeatable=True,
        quick_nav_target=True,
    ),
    RowKind.CONFIG_HEADER: RowBehavior(
        RowAffordance.ACTION,
        is_header=True,
        help_title="Save",
    ),
    RowKind.TRACK_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        can_enter_move_mode=True,
        can_solo=True,
        can_enable_disable=True,
        quick_nav_target=True,
    ),
    RowKind.TRACK_PRESET_DIR: RowBehavior(
        RowAffordance.PATH_DIR,
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET: RowBehavior(
        RowAffordance.PATH_PRESET,
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_SWITCHING: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Preset switching",
        help_entries=(("Left/Right", "cycle mode"),),
    ),
    RowKind.TRACK_PRESET_SWITCHING_SCOPE: RowBehavior(
        RowAffordance.VALUE_STEP,
        parent_group="track",
        help_title="Preset switching scope",
        help_entries=(("Left/Right", "directory only in v1"),),
    ),
    RowKind.TRACK_STEM: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        help_title="Stem",
        parent_group="track",
    ),
    RowKind.TRACK_BLEND: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_OPACITY: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_BEAT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_EFFECTS_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        help_title="Cleave Effects",
        parent_group="track",
    ),
    RowKind.TRACK_EFFECT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        help_title="Cleave Effects",
        parent_group="track",
    ),
    RowKind.LAYER_MANAGEMENT_ADD: RowBehavior(
        RowAffordance.ACTION,
        help_title="Add Layer",
        navigable=True,
    ),
    RowKind.LAYER_MANAGEMENT_DELETE: RowBehavior(
        RowAffordance.ACTION,
        help_title="Delete layer",
        navigable=True,
        parent_group="track",
        blocked_by_layer_lock=False,
        navigable_when_layer_locked=True,
    ),
    RowKind.PANEL_NOTIFICATION: RowBehavior(
        RowAffordance.DISPLAY,
        navigable=False,
        is_pinned=True,
    ),
    RowKind.RENDER_SECTION_GAP: RowBehavior(
        RowAffordance.DISPLAY,
        navigable=False,
    ),
    RowKind.RENDER_OVERLAY_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        can_enable_disable=True,
        can_solo=True,
        help_title="Render",
        quick_nav_target=True,
    ),
    RowKind.RENDER_OVERLAY_POSITION: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay",
    ),
    RowKind.RENDER_OVERLAY_TITLE_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        help_title="Edit",
        parent_group="render_overlay",
    ),
    RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_title",
    ),
    RowKind.RENDER_OVERLAY_TITLE_FONT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_title",
    ),
    RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_title",
    ),
    RowKind.RENDER_OVERLAY_BODY_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        help_title="Edit",
        parent_group="render_overlay",
    ),
    RowKind.RENDER_OVERLAY_BODY_FONT_SIZE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_body",
    ),
    RowKind.RENDER_OVERLAY_BODY_FONT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_body",
    ),
    RowKind.RENDER_OVERLAY_OPACITY: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay",
    ),
    RowKind.RENDER_OVERLAY_BORDER_WIDTH: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay",
    ),
    RowKind.RENDER_OVERLAY_START_DELAY: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay",
    ),
    RowKind.RENDER_OVERLAY_DISPLAY_TIME: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay",
    ),
    RowKind.RENDER_POST_FX_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        can_enable_disable=True,
        can_solo=True,
        help_title="Render",
        quick_nav_target=True,
    ),
    RowKind.RENDER_POST_FX_FADE_IN: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_post_fx",
    ),
    RowKind.RENDER_POST_FX_FADE_OUT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_post_fx",
    ),
    RowKind.RENDER_TIMELINE_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        can_enable_disable=True,
        can_solo=False,
        help_title="Render",
        quick_nav_target=True,
    ),
    RowKind.SETTINGS_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_header=True,
        help_title="Settings",
        quick_nav_target=True,
    ),
    RowKind.SETTINGS_RENDER_MODE: RowBehavior(
        RowAffordance.VALUE_STEP,
        is_pinned=True,
        repeatable=True,
        parent_group="settings",
        help_title="Render mode",
        help_entries=(
            ("Left/Right", "cycle mode"),
            ("", "live preview only; layers scale by z-order"),
        ),
    ),
}

HEADER_ROW_KINDS = frozenset(k for k, b in ROW_BEHAVIORS.items() if b.is_header)
REPEAT_ROW_KINDS = frozenset(k for k, b in ROW_BEHAVIORS.items() if b.repeatable)
LABELED_SUB_ROW_KINDS = frozenset(
    k
    for k, b in ROW_BEHAVIORS.items()
    if b.affordance
    in {
        RowAffordance.VALUE_STEP,
        RowAffordance.PATH_DIR,
        RowAffordance.PATH_PRESET,
    }
    and not b.is_header
)

TRACK_SUB_ROW_KINDS = frozenset(
    k for k, b in ROW_BEHAVIORS.items() if b.parent_group == "track"
)
TRACK_EFFECT_SUB_ROW_KINDS = frozenset({RowKind.TRACK_EFFECT})
RENDER_OVERLAY_SUB_ROW_KINDS = frozenset(
    k for k, b in ROW_BEHAVIORS.items() if b.parent_group == "render_overlay"
)
RENDER_OVERLAY_TITLE_NESTED_KINDS = frozenset(
    k for k, b in ROW_BEHAVIORS.items() if b.parent_group == "render_overlay_title"
)
RENDER_OVERLAY_BODY_NESTED_KINDS = frozenset(
    k for k, b in ROW_BEHAVIORS.items() if b.parent_group == "render_overlay_body"
)
RENDER_OVERLAY_ALL_SUB_ROW_KINDS = (
    RENDER_OVERLAY_SUB_ROW_KINDS
    | RENDER_OVERLAY_TITLE_NESTED_KINDS
    | RENDER_OVERLAY_BODY_NESTED_KINDS
)
RENDER_POST_FX_SUB_ROW_KINDS = frozenset(
    k for k, b in ROW_BEHAVIORS.items() if b.parent_group == "render_post_fx"
)
SETTINGS_SUB_ROW_KINDS = frozenset(
    k for k, b in ROW_BEHAVIORS.items() if b.parent_group == "settings"
)

_LAYER_LOCK_BLOCKING_AFFORDANCES = frozenset(
    {
        RowAffordance.VALUE_STEP,
        RowAffordance.PATH_DIR,
        RowAffordance.PATH_PRESET,
    }
)


def row_behavior(kind: RowKind) -> RowBehavior:
    behavior = ROW_BEHAVIORS.get(kind)
    assert behavior is not None, f"missing RowBehavior for {kind!r}"
    return behavior


def row_is_pinned(kind: RowKind) -> bool:
    behavior = row_behavior(kind)
    return behavior.is_header or behavior.is_pinned


def expandable_row_kinds() -> frozenset[RowKind]:
    return frozenset(
        k for k, b in ROW_BEHAVIORS.items() if b.affordance == RowAffordance.EXPAND
    )


def _derived_blocked_by_layer_lock(behavior: RowBehavior) -> bool:
    if behavior.blocked_by_layer_lock is not None:
        return behavior.blocked_by_layer_lock
    return (
        behavior.parent_group == "track"
        and behavior.affordance in _LAYER_LOCK_BLOCKING_AFFORDANCES
    )


def _derived_navigable_when_layer_locked(behavior: RowBehavior) -> bool:
    if behavior.navigable_when_layer_locked is not None:
        return behavior.navigable_when_layer_locked
    return (
        behavior.parent_group == "track"
        and behavior.is_sub_header
        and behavior.affordance == RowAffordance.EXPAND
    )


def row_blocked_by_layer_lock(kind: RowKind) -> bool:
    return _derived_blocked_by_layer_lock(row_behavior(kind))


def row_navigable_when_layer_locked(kind: RowKind) -> bool:
    return _derived_navigable_when_layer_locked(row_behavior(kind))


def layer_lock_blocks_mutation(kind: RowKind, *, locked: bool) -> bool:
    return locked and row_blocked_by_layer_lock(kind)


def row_triggers_layer_delete(kind: RowKind) -> bool:
    """True when Delete should prompt to remove the focused track block's layer."""
    if kind == RowKind.TRACK_HEADER:
        return True
    return row_behavior(kind).parent_group == "track"


def section_header_descriptor(desc: RowDescriptor) -> RowDescriptor:
    """Map a sub-row descriptor to its section header for focus fallback."""
    kind = desc.kind
    if kind == RowKind.SETTINGS_RENDER_MODE:
        return RowDescriptor(RowKind.SETTINGS_HEADER)
    if kind in RENDER_OVERLAY_TITLE_NESTED_KINDS:
        return RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_HEADER)
    if kind in RENDER_OVERLAY_BODY_NESTED_KINDS:
        return RowDescriptor(RowKind.RENDER_OVERLAY_BODY_HEADER)
    if kind in RENDER_OVERLAY_ALL_SUB_ROW_KINDS:
        return RowDescriptor(RowKind.RENDER_OVERLAY_HEADER)
    if kind in RENDER_POST_FX_SUB_ROW_KINDS:
        return RowDescriptor(RowKind.RENDER_POST_FX_HEADER)
    behavior = row_behavior(kind)
    if behavior.parent_group == "track":
        if kind in TRACK_EFFECT_SUB_ROW_KINDS:
            return RowDescriptor(RowKind.TRACK_EFFECTS_HEADER, slot=desc.slot)
        return RowDescriptor(RowKind.TRACK_HEADER, slot=desc.slot)
    return desc
