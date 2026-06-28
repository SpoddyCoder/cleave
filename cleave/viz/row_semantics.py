"""Row interaction semantics for the live tuning overlay."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from cleave.blend_modes import BLEND_MODE_HELP_ENTRIES
from cleave.config_schema import (
    PRESET_SWITCHING_MODE_HELP_ENTRIES,
    VISUALIZER_RENDER_MODE_HELP_ENTRIES,
)


class RowKind(Enum):
    TRACK_HEADER = auto()
    TRACK_PRESET_DIR = auto()
    TRACK_PRESET = auto()
    TRACK_PRESET_SWITCHING = auto()
    TRACK_PRESET_SWITCHING_MODE = auto()
    TRACK_USER_PRESETS = auto()
    TRACK_USER_PRESET_ITEM = auto()
    TRACK_USER_PRESET_ADD = auto()
    TRACK_PRESET_SWITCHING_SCOPE = auto()
    TRACK_PRESET_DURATION = auto()
    TRACK_SOFT_CUT_DURATION = auto()
    TRACK_EASTER_EGG = auto()
    TRACK_PRESET_START_CLEAN = auto()
    TRACK_HARD_CUT_ENABLED = auto()
    TRACK_HARD_CUT_DURATION = auto()
    TRACK_HARD_CUT_SENSITIVITY = auto()
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
    SETTINGS_UI_HEADER = auto()
    SETTINGS_UI_WIDTH_MODE = auto()
    SETTINGS_UI_WIDTH = auto()
    SETTINGS_UI_FADE = auto()
    CONFIG_HEADER = auto()
    TRANSPORT = auto()


@dataclass(frozen=True)
class RowDescriptor:
    kind: RowKind
    slot: str | None = None
    effect_id: str | None = None
    driver_slug: str | None = None
    preset_index: int | None = None


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
    help_description: tuple[str, ...] | None = None
    help_mode_entries: tuple[tuple[str, str], ...] | None = None
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
        help_title="Transport",
        help_description=("Scrubber and play/pause for the project audio.",),
        is_header=True,
        repeatable=True,
        quick_nav_target=True,
    ),
    RowKind.CONFIG_HEADER: RowBehavior(
        RowAffordance.ACTION,
        help_title="Save",
        help_description=(
            "Active config file.",
            "Enter or Ctrl+S saves the current session settings.",
        ),
        is_header=True,
    ),
    RowKind.TRACK_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        help_title="Layer",
        help_description=(
            "Layer header.",
            "Contains blend mode, opacity, stem, and preset controls.",
        ),
        can_enter_move_mode=True,
        can_solo=True,
        can_enable_disable=True,
        quick_nav_target=True,
    ),
    RowKind.TRACK_PRESET_DIR: RowBehavior(
        RowAffordance.PATH_DIR,
        help_title="Preset Directory",
        help_description=(
            "Directory from which presets are browsed for this layer.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET: RowBehavior(
        RowAffordance.PATH_PRESET,
        help_title="Milkdrop Preset File",
        help_description=(
            "Currently active Milkdrop preset for this layer.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_SWITCHING: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        parent_group="track",
        help_title="Preset switching",
        help_description=(
            "Controls how and when presets change during playback.",
        ),
    ),
    RowKind.TRACK_PRESET_SWITCHING_MODE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Switching mode",
        help_entries=(("Left/Right", "cycle mode"),),
        help_description=(),
        help_mode_entries=PRESET_SWITCHING_MODE_HELP_ENTRIES,
    ),
    RowKind.TRACK_USER_PRESETS: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        parent_group="track",
        help_title="user presets",
        help_description=(
            "Presets in the rotation set for user-defined switching.",
            "Expand to list entries and add from the current browse position.",
        ),
    ),
    RowKind.TRACK_USER_PRESET_ITEM: RowBehavior(
        RowAffordance.PATH_PRESET,
        parent_group="track",
        help_title="user preset entry",
        help_description=(
            "Preset in the user-defined rotation set for this layer.",
        ),
    ),
    RowKind.TRACK_USER_PRESET_ADD: RowBehavior(
        RowAffordance.ACTION,
        parent_group="track",
        blocked_by_layer_lock=True,
        help_title="Add Current Preset",
        help_description=(
            "Add the layer's current preset to the user-defined rotation set.",
            "Copies the preset file into the project presets folder.",
            "+ on the preset dir or preset file row is the same action.",
        ),
    ),
    RowKind.TRACK_PRESET_SWITCHING_SCOPE: RowBehavior(
        RowAffordance.VALUE_STEP,
        parent_group="track",
        help_title="Preset switching scope",
        help_entries=(("Left/Right", "directory only in v1"),),
        help_description=(
            "Which preset files are eligible when projectM switches.",
        ),
    ),
    RowKind.TRACK_PRESET_DURATION: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Preset duration",
        help_entries=(("Left/Right", "step value"),),
        help_description=(
            "How long a preset plays before projectM transitions to the next.",
        ),
    ),
    RowKind.TRACK_SOFT_CUT_DURATION: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Soft cut",
        help_entries=(("Left/Right", "step value"),),
        help_description=(
            "Duration of the crossfade when projectM blends between presets.",
        ),
    ),
    RowKind.TRACK_EASTER_EGG: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Easter egg",
        help_entries=(
            ("Left/Right", "step value"),
            ("Ctrl + Left/Right", "large step"),
        ),
        help_description=(
            "Probability that projectM picks a random preset instead of the next in sequence.",
        ),
    ),
    RowKind.TRACK_PRESET_START_CLEAN: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Start clean",
        help_entries=(("Left/Right", "yes / no"),),
        help_description=(
            "When enabled, each new preset starts with a blank canvas",
            "instead of inheriting the previous frame.",
        ),
    ),
    RowKind.TRACK_HARD_CUT_ENABLED: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Hard cut",
        help_entries=(("Left/Right", "enabled / disabled"),),
        help_description=(
            "Whether projectM can switch presets instantly on strong beats",
            "(bypassing soft cut).",
        ),
    ),
    RowKind.TRACK_HARD_CUT_DURATION: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Hard cut min",
        help_entries=(("Left/Right", "step value"),),
        help_description=(
            "Time window after a hard cut before another can fire.",
        ),
    ),
    RowKind.TRACK_HARD_CUT_SENSITIVITY: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Hard cut sens",
        help_entries=(("Left/Right", "step value"),),
        help_description=(
            "Beat energy threshold required to trigger a hard cut.",
            "Higher = less frequent.",
        ),
    ),
    RowKind.TRACK_STEM: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        help_title="Stem",
        help_entries=(("Left/Right", "cycle stem source"),),
        help_description=(
            "Audio stem fed to libprojectM for this layer's beat detection",
            "and waveform display.",
            "Effects reset when the stem changes.",
        ),
        parent_group="track",
    ),
    RowKind.TRACK_BLEND: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Blend mode",
        help_description=(
            "How this layer is composited onto the layers below it.",
        ),
        help_mode_entries=BLEND_MODE_HELP_ENTRIES,
    ),
    RowKind.TRACK_OPACITY: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Opacity",
        help_description=("Opacity of this layer.",),
    ),
    RowKind.TRACK_BEAT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Beat sensitivity",
        help_description=(
            "Beat sensitivity multiplier for this layer.",
            "Higher values make the visuals more reactive.",
        ),
    ),
    RowKind.TRACK_EFFECTS_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        help_title="Cleave Effects",
        help_description=(
            "Cleave audio-driven effects applied to this layer's output.",
        ),
        parent_group="track",
    ),
    RowKind.TRACK_EFFECT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        help_title="Cleave Effects",
        help_description=(
            "Depth of this effect.",
            "0 disables it.",
        ),
        parent_group="track",
    ),
    RowKind.LAYER_MANAGEMENT_ADD: RowBehavior(
        RowAffordance.ACTION,
        help_title="Add Layer",
        help_description=(
            "Add a new layer at the top of the z-order.",
            "Maximum eight layers.",
        ),
        navigable=True,
    ),
    RowKind.LAYER_MANAGEMENT_DELETE: RowBehavior(
        RowAffordance.ACTION,
        help_title="Delete layer",
        help_description=(
            "Remove this layer permanently.",
            "At least one layer must remain.",
        ),
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
        help_title="Credits overlay",
        help_description=(
            "Credits overlay burned into the offline render output.",
            "Previewed live during playback.",
        ),
        quick_nav_target=True,
    ),
    RowKind.RENDER_OVERLAY_POSITION: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay",
        help_title="Position",
        help_description=(
            "Screen corner where the credits overlay appears.",
        ),
    ),
    RowKind.RENDER_OVERLAY_TITLE_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        help_title="Overlay title",
        help_description=("Title line of the credits overlay.",),
        parent_group="render_overlay",
    ),
    RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_title",
        help_title="Title font size",
        help_description=("Font size of the overlay title.",),
    ),
    RowKind.RENDER_OVERLAY_TITLE_FONT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_title",
        help_title="Title font",
        help_description=("Font used for the overlay title.",),
    ),
    RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_title",
        help_title="Title margin bottom",
        help_description=(
            "Gap between the title and body in the overlay box.",
        ),
    ),
    RowKind.RENDER_OVERLAY_BODY_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        help_title="Overlay body",
        help_description=("Body block of the credits overlay (secondary text).",),
        parent_group="render_overlay",
    ),
    RowKind.RENDER_OVERLAY_BODY_FONT_SIZE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_body",
        help_title="Body font size",
        help_description=("Font size of the overlay body.",),
    ),
    RowKind.RENDER_OVERLAY_BODY_FONT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_body",
        help_title="Body font",
        help_description=("Font used for the overlay body.",),
    ),
    RowKind.RENDER_OVERLAY_OPACITY: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay",
        help_title="Background opacity",
        help_description=("Background opacity of the credits overlay box.",),
    ),
    RowKind.RENDER_OVERLAY_BORDER_WIDTH: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay",
        help_title="Border width",
        help_description=(
            "Width of the border drawn around the credits overlay box.",
        ),
    ),
    RowKind.RENDER_OVERLAY_START_DELAY: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay",
        help_title="Start delay",
        help_description=(
            "Seconds after the render starts before the overlay fades in.",
        ),
    ),
    RowKind.RENDER_OVERLAY_DISPLAY_TIME: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay",
        help_title="Display time",
        help_description=(
            "Duration the overlay stays fully visible before fading out.",
            "0 = stays on.",
        ),
    ),
    RowKind.RENDER_POST_FX_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        can_enable_disable=True,
        can_solo=True,
        help_title="Post FX",
        help_description=(
            "Post-processing effects applied to the composited output:",
            "fade in and fade out.",
        ),
        quick_nav_target=True,
    ),
    RowKind.RENDER_POST_FX_FADE_IN: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_post_fx",
        help_title="Fade in",
        help_description=(
            "Duration of the fade-in at the start of the render.",
        ),
    ),
    RowKind.RENDER_POST_FX_FADE_OUT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_post_fx",
        help_title="Fade out",
        help_description=(
            "Duration of the fade-out at the end of the render.",
        ),
    ),
    RowKind.RENDER_TIMELINE_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        can_enable_disable=True,
        can_solo=False,
        help_title="Timeline",
        help_description=(
            "Timeline automation for layer visibility.",
            "Cues are burned into the offline render.",
            "When enabled, standard layer visibility is disabled;",
            "visibility is controlled by the timeline instead.",
        ),
        quick_nav_target=True,
    ),
    RowKind.SETTINGS_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_header=True,
        help_title="Editor Settings",
        help_description=("Global visualizer settings (not per-layer).",),
        quick_nav_target=True,
    ),
    RowKind.SETTINGS_RENDER_MODE: RowBehavior(
        RowAffordance.VALUE_STEP,
        is_pinned=True,
        repeatable=True,
        parent_group="settings",
        help_title="Render mode",
        help_entries=(("Left/Right", "cycle mode"),),
        help_description=(
            "Trade-off between visual quality and CPU/GPU load.",
            "Affects layer resolution scaling in the live view only.",
        ),
        help_mode_entries=VISUALIZER_RENDER_MODE_HELP_ENTRIES,
    ),
    RowKind.SETTINGS_UI_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        is_pinned=True,
        parent_group="settings",
        help_title="UI",
        help_description=("Panel width and auto-fade for the main tuning overlay.",),
    ),
    RowKind.SETTINGS_UI_FADE: RowBehavior(
        RowAffordance.VALUE_STEP,
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
        help_title="Auto-fade",
        help_entries=(
            ("Left/Right", "adjust delay before UI fades"),
            ("Ctrl + Left/Right", "large step"),
            ("0", "disabled; UI stays until Esc"),
        ),
        help_description=(
            "Delay before the overlay panel fades out.",
            "0 keeps it always visible.",
        ),
    ),
    RowKind.SETTINGS_UI_WIDTH_MODE: RowBehavior(
        RowAffordance.VALUE_STEP,
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
        help_title="Width mode",
        help_entries=(("Left/Right", "cycle mode"),),
        help_description=(
            "Flexible shrinks the panel to fit content up to the max width.",
            "Fixed keeps the panel at the max width always.",
        ),
    ),
    RowKind.SETTINGS_UI_WIDTH: RowBehavior(
        RowAffordance.VALUE_STEP,
        is_pinned=True,
        repeatable=True,
        parent_group="settings_ui",
        help_title="Max width",
        help_entries=(
            ("Left/Right", "adjust max panel width"),
            ("Ctrl + Left/Right", "large step"),
        ),
        help_description=(
            "Maximum width of the main tuning panel.",
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
TRACK_USER_PRESET_SUB_ROW_KINDS = frozenset(
    {RowKind.TRACK_USER_PRESET_ITEM, RowKind.TRACK_USER_PRESET_ADD}
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


from cleave.viz.row_sections import section_header_from_section_tree


def section_header_descriptor(desc: RowDescriptor) -> RowDescriptor:
    """Map a sub-row descriptor to its section header for focus fallback."""
    from_tree = section_header_from_section_tree(desc)
    if from_tree is not None:
        return from_tree
    kind = desc.kind
    if kind in TRACK_EFFECT_SUB_ROW_KINDS:
        return RowDescriptor(RowKind.TRACK_EFFECTS_HEADER, slot=desc.slot)
    if kind in TRACK_USER_PRESET_SUB_ROW_KINDS:
        return RowDescriptor(RowKind.TRACK_USER_PRESETS, slot=desc.slot)
    return desc
