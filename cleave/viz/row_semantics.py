"""Row interaction semantics for the live tuning overlay."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class RowKind(Enum):
    TRACK_HEADER = auto()
    TRACK_PRESET_DIR = auto()
    TRACK_PRESET = auto()
    TRACK_STEM = auto()
    TRACK_BLEND = auto()
    TRACK_OPACITY = auto()
    TRACK_BEAT = auto()
    TRACK_EFFECTS_HEADER = auto()
    TRACK_EFFECT = auto()
    TIMELINE_LAYER_HINT = auto()
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
    CONFIG_HEADER = auto()
    TRANSPORT = auto()
    SAVE_CONFIG = auto()


@dataclass(frozen=True)
class RowDescriptor:
    kind: RowKind
    stem: str | None = None
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
    navigable: bool = True
    is_header: bool = False
    is_sub_header: bool = False
    can_enable_disable: bool = False
    can_solo: bool = False
    can_enter_move_mode: bool = False
    repeatable: bool = False
    parent_group: str | None = None


ROW_BEHAVIORS: dict[RowKind, RowBehavior] = {
    RowKind.TRANSPORT: RowBehavior(
        RowAffordance.SEEK,
        is_header=True,
        repeatable=True,
    ),
    RowKind.CONFIG_HEADER: RowBehavior(
        RowAffordance.DISPLAY,
        is_header=True,
        navigable=False,
    ),
    RowKind.SAVE_CONFIG: RowBehavior(
        RowAffordance.ACTION,
        is_header=True,
    ),
    RowKind.TRACK_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        can_enter_move_mode=True,
        can_solo=True,
        can_enable_disable=True,
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
    RowKind.TIMELINE_LAYER_HINT: RowBehavior(
        RowAffordance.DISPLAY,
        navigable=False,
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
LOCKED_NAVIGABLE_SUB_ROW_KINDS = frozenset(
    k
    for k, b in ROW_BEHAVIORS.items()
    if b.parent_group == "track"
    and b.is_sub_header
    and b.affordance == RowAffordance.EXPAND
) | frozenset({RowKind.TRACK_STEM})


def row_behavior(kind: RowKind) -> RowBehavior:
    behavior = ROW_BEHAVIORS.get(kind)
    assert behavior is not None, f"missing RowBehavior for {kind!r}"
    return behavior


def expandable_row_kinds() -> frozenset[RowKind]:
    return frozenset(
        k for k, b in ROW_BEHAVIORS.items() if b.affordance == RowAffordance.EXPAND
    )
