"""Row interaction semantics for the live tuning overlay."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from cleave.blend_modes import BLEND_MODE_HELP_ENTRIES
from cleave.config_schema import (
    CAST_ROLES_DEFAULT_ROLE_HELP_ENTRIES,
    CAST_ROLES_TIMELINE_BEHAVIOUR_HELP_ENTRIES,
    CHROMA_BOOST_APPLY_MODE_HELP_ENTRIES,
    CHROMA_BOOST_VARIANT_HELP_ENTRIES,
    HIGHLIGHT_ROLLOFF_APPLY_MODE_HELP_ENTRIES,
    HIGHLIGHT_ROLLOFF_CURVE_HELP_ENTRIES,
    PRESET_SWITCHING_MODE_HELP_ENTRIES,
    PRESET_SWITCHING_ROTATION_SET_HELP_ENTRIES,
    EDITOR_PREVIEW_QUALITY_HELP_ENTRIES,
    RENDER_OVERLAY_ANIMATION_TYPE_HELP_ENTRIES,
    RENDER_OVERLAY_SLIDE_DIRECTION_HELP_ENTRIES,
)
from cleave.cue_roles import CUE_ROLE_MARKER_HELP_ENTRIES
from cleave.timeline_presets import (
    TIMELINE_PRESET_HELP_ENTRIES,
    TIMELINE_RESET_HELP_ENTRIES,
)


class RowKind(Enum):
    TRACK_HEADER = auto()
    TRACK_PRESET_DIR = auto()
    TRACK_PRESET = auto()
    TRACK_PRESET_SWITCHING = auto()
    TRACK_USER_PRESETS = auto()
    TRACK_USER_PRESET_ITEM = auto()
    TRACK_USER_PRESET_ADD = auto()
    TRACK_PRESET_SWITCHING_ROTATION_SET = auto()
    TRACK_CAST_ROLES_TIMELINE_BEHAVIOUR = auto()
    TRACK_CAST_ROLES_DEFAULT_ROLE = auto()
    TRACK_PRESET_SWITCHING_SHUFFLE = auto()
    TRACK_PRESET_SWITCHING_SEED = auto()
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
    RENDER_OVERLAYS_HEADER = auto()
    RENDER_OVERLAY_OPENING_CARD_HEADER = auto()
    RENDER_OVERLAY_CLOSING_CARD_HEADER = auto()
    RENDER_OVERLAY_OPENING_ANIMATION_HEADER = auto()
    RENDER_OVERLAY_CLOSING_ANIMATION_HEADER = auto()
    RENDER_OVERLAY_OPENING_ANIMATION_TYPE = auto()
    RENDER_OVERLAY_CLOSING_ANIMATION_TYPE = auto()
    RENDER_OVERLAY_OPENING_ANIMATION_SLIDE_DIRECTION = auto()
    RENDER_OVERLAY_CLOSING_ANIMATION_SLIDE_DIRECTION = auto()
    RENDER_OVERLAY_OPENING_POSITION = auto()
    RENDER_OVERLAY_CLOSING_POSITION = auto()
    RENDER_OVERLAY_OPENING_TITLE_HEADER = auto()
    RENDER_OVERLAY_CLOSING_TITLE_HEADER = auto()
    RENDER_OVERLAY_OPENING_TITLE_FONT_SIZE = auto()
    RENDER_OVERLAY_CLOSING_TITLE_FONT_SIZE = auto()
    RENDER_OVERLAY_OPENING_TITLE_FONT = auto()
    RENDER_OVERLAY_CLOSING_TITLE_FONT = auto()
    RENDER_OVERLAY_OPENING_TITLE_MARGIN_BOTTOM = auto()
    RENDER_OVERLAY_CLOSING_TITLE_MARGIN_BOTTOM = auto()
    RENDER_OVERLAY_OPENING_BODY_HEADER = auto()
    RENDER_OVERLAY_CLOSING_BODY_HEADER = auto()
    RENDER_OVERLAY_OPENING_BODY_FONT_SIZE = auto()
    RENDER_OVERLAY_CLOSING_BODY_FONT_SIZE = auto()
    RENDER_OVERLAY_OPENING_BODY_FONT = auto()
    RENDER_OVERLAY_CLOSING_BODY_FONT = auto()
    RENDER_OVERLAY_OPENING_OPACITY = auto()
    RENDER_OVERLAY_CLOSING_OPACITY = auto()
    RENDER_OVERLAY_OPENING_BORDER_WIDTH = auto()
    RENDER_OVERLAY_CLOSING_BORDER_WIDTH = auto()
    RENDER_OVERLAY_OPENING_APPEAR_AT = auto()
    RENDER_OVERLAY_CLOSING_DISAPPEAR_AT = auto()
    RENDER_OVERLAY_OPENING_DISPLAY_TIME = auto()
    RENDER_OVERLAY_CLOSING_DISPLAY_TIME = auto()
    RENDER_POST_FX_HEADER = auto()
    RENDER_POST_FX_FADE_IN = auto()
    RENDER_POST_FX_FADE_OUT = auto()
    RENDER_POST_FX_HIGHLIGHT_ROLLOFF_HEADER = auto()
    RENDER_POST_FX_HIGHLIGHT_ROLLOFF_MODE = auto()
    RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CURVE = auto()
    RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD = auto()
    RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CEILING = auto()
    RENDER_POST_FX_HIGHLIGHT_ROLLOFF_STRENGTH = auto()
    RENDER_POST_FX_HIGHLIGHT_ROLLOFF_SOFTNESS = auto()
    RENDER_POST_FX_HIGHLIGHT_ROLLOFF_DESATURATION = auto()
    RENDER_POST_FX_CHROMA_BOOST_HEADER = auto()
    RENDER_POST_FX_CHROMA_BOOST_MODE = auto()
    RENDER_POST_FX_CHROMA_BOOST_VARIANT = auto()
    RENDER_POST_FX_CHROMA_BOOST_AMOUNT = auto()
    RENDER_TIMELINE_HEADER = auto()
    TIMELINE_PRESETS_HEADER = auto()
    TIMELINE_PRESET_CHARACTER = auto()
    TIMELINE_PRESET_CRESCENDO = auto()
    TIMELINE_PRESET_DENSITY = auto()
    TIMELINE_PRESET_CUE_SNAP = auto()
    TIMELINE_PRESET_SONG_MARKER_SNAP = auto()
    TIMELINE_PRESET_TIMELINE_CUTS = auto()
    TIMELINE_PRESET_CONDUCTOR = auto()
    TIMELINE_PRESETS = auto()
    TIMELINE_VISUAL_LIMITER_HEADER = auto()
    TIMELINE_VISUAL_LIMITER_THRESHOLD = auto()
    TIMELINE_VISUAL_LIMITER_RELEASE = auto()
    TIMELINE_RESET = auto()
    TIMELINE_BEAT_BAR_GRID_HEADER = auto()
    TIMELINE_BAR_PHASE = auto()
    TIMELINE_BAR_GRID = auto()
    TIMELINE_PLACEMENT_SNAP = auto()
    TIMELINE_SNAP_CUES_HEADER = auto()
    TIMELINE_SNAP_TO_BEATS = auto()
    TIMELINE_SNAP_TO_BARS = auto()
    TIMELINE_SNAP_TO_SONG_MARKERS = auto()
    TIMELINE_CUTS_HEADER = auto()
    TIMELINE_HARD_CUTS = auto()
    TIMELINE_HARD_CUT_FADE_IN = auto()
    TIMELINE_HARD_CUT_FADE_OUT = auto()
    TIMELINE_SOFT_CUTS = auto()
    TIMELINE_SOFT_CUT_FADE_IN = auto()
    TIMELINE_SOFT_CUT_FADE_OUT = auto()
    TIMELINE_APPLY_SOFT_CUTS = auto()
    TIMELINE_APPLY_HARD_CUTS = auto()
    SONG_MARKERS_HEADER = auto()
    SONG_MARKER_ITEM = auto()
    SETTINGS_HEADER = auto()
    SETTINGS_EDITOR_MODE = auto()
    SETTINGS_PREVIEW_QUALITY = auto()
    SETTINGS_UI_HEADER = auto()
    SETTINGS_UI_WIDTH_MODE = auto()
    SETTINGS_UI_WIDTH = auto()
    SETTINGS_UI_FADE = auto()
    SETTINGS_LATENCY_COMPENSATION_HEADER = auto()
    SETTINGS_RESIDUAL_LATENCY_MS = auto()
    SETTINGS_MEASURE_LATENCY = auto()
    CONFIG_HEADER = auto()
    TRANSPORT = auto()


@dataclass(frozen=True)
class RowDescriptor:
    kind: RowKind
    slot: str | None = None
    effect_id: str | None = None
    driver_slug: str | None = None
    preset_index: int | None = None
    marker_index: int | None = None


class RowAffordance(Enum):
    EXPAND = auto()
    VALUE_STEP = auto()
    ACTION_PARAMETER = auto()
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
    # When True with quick_nav_target, Ctrl+Up/Down always lands here even if collapsed.
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


ROW_BEHAVIORS: dict[RowKind, RowBehavior] = {
    RowKind.TRANSPORT: RowBehavior(
        RowAffordance.SEEK,
        help_title="Transport",
        help_description=("Scrubber and play/pause for the project audio.",),
        is_header=True,
        repeatable=True,
        quick_nav_target=True,
        quick_nav_always=True,
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
            "projectM visualiser layer.",
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
            "[▲▼] marks when a parent and/or child directory is available.",
        ),
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET: RowBehavior(
        RowAffordance.PATH_PRESET,
        help_title="Milkdrop Preset File",
        help_description=(
            "Currently active Milkdrop preset for this layer.",
            "[F/B/U] indicates favourited/blacklisted/user-defined.",
            "[R:X] indicates the chosen role.",
        ),
        help_mode_entries=CUE_ROLE_MARKER_HELP_ENTRIES,
        repeatable=True,
        parent_group="track",
    ),
    RowKind.TRACK_PRESET_SWITCHING: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Preset switching",
        help_entries=(("Left/Right", "cycle mode"),),
        help_description=(
            "Controls how and when presets change during playback.",
        ),
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
            "[F/B] indicates favourited/blacklisted.",
            "[R:X] indicates the chosen role.",
        ),
        help_mode_entries=CUE_ROLE_MARKER_HELP_ENTRIES,
    ),
    RowKind.TRACK_USER_PRESET_ADD: RowBehavior(
        RowAffordance.ACTION,
        parent_group="track",
        blocked_by_section_lock=True,
        help_title="Add Current Preset",
        help_description=(
            "Add the layer's current preset to the user-defined rotation set.",
            "Copies the preset file into the project presets folder.",
            "U on the preset dir or preset file row is the same action.",
        ),
    ),
    RowKind.TRACK_PRESET_SWITCHING_ROTATION_SET: RowBehavior(
        RowAffordance.VALUE_STEP,
        parent_group="track",
        help_title="Rotation set",
        help_entries=(("Left/Right", "cycle rotation set"),),
        help_description=(),
        help_mode_entries=PRESET_SWITCHING_ROTATION_SET_HELP_ENTRIES,
    ),
    RowKind.TRACK_CAST_ROLES_TIMELINE_BEHAVIOUR: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Timeline behaviour",
        help_entries=(("Left/Right", "cycle behaviour"),),
        help_description=(),
        help_mode_entries=CAST_ROLES_TIMELINE_BEHAVIOUR_HELP_ENTRIES,
    ),
    RowKind.TRACK_CAST_ROLES_DEFAULT_ROLE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Default role",
        help_entries=(("Left/Right", "cycle role"),),
        help_description=(),
        help_mode_entries=CAST_ROLES_DEFAULT_ROLE_HELP_ENTRIES,
    ),
    RowKind.TRACK_PRESET_SWITCHING_SHUFFLE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Shuffle",
        help_entries=(("Left/Right", "off / on"),),
        help_description=(
            "When on, auto switching uses a fixed shuffled order",
            "(same in live preview and offline render).",
            "Use the seed row to roll a new order.",
        ),
    ),
    RowKind.TRACK_PRESET_SWITCHING_SEED: RowBehavior(
        RowAffordance.ACTION,
        parent_group="track",
        blocked_by_section_lock=True,
        help_title="Seed",
        help_entries=(("Enter", "generate a new seed"),),
        help_description=(
            "Current shuffle seed for this layer.",
            "Enter rolls a new seed and rebuilds the shuffled preset order.",
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
            "How much projectM randomizes preset duration (Milkdrop legacy gaussian).",
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
        blocked_by_section_lock=False,
        navigable_when_section_locked=True,
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
    RowKind.RENDER_OVERLAYS_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        can_enable_disable=True,
        can_solo=True,
        help_title="Credits overlays",
        help_description=(
            "Opening and closing credits cards.",
        ),
        quick_nav_target=True,
        quick_nav_always=True,
    ),
    RowKind.RENDER_OVERLAY_OPENING_CARD_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        can_enable_disable=True,
        is_sub_header=True,
        parent_group="render_overlay",
        help_title="Opening card",
        help_description=("Credits card at the start of the song.",),
    ),
    RowKind.RENDER_OVERLAY_CLOSING_CARD_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        can_enable_disable=True,
        is_sub_header=True,
        parent_group="render_overlay",
        help_title="Closing card",
        help_description=("Credits card near the end of the song.",),
    ),
    RowKind.RENDER_OVERLAY_OPENING_ANIMATION_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        parent_group="render_overlay_opening",
        help_title="Opening card animation",
        help_description=(
            "Entrance and exit motion for the opening credits card.",
        ),
    ),
    RowKind.RENDER_OVERLAY_CLOSING_ANIMATION_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        parent_group="render_overlay_closing",
        help_title="Closing card animation",
        help_description=(
            "Entrance and exit motion for the closing credits card.",
        ),
    ),
    RowKind.RENDER_OVERLAY_OPENING_ANIMATION_TYPE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_opening_animation",
        help_title="Animation type",
        help_entries=(("Left/Right", "cycle type"),),
        help_description=("How the opening card enters and leaves the screen.",),
        help_mode_entries=RENDER_OVERLAY_ANIMATION_TYPE_HELP_ENTRIES,
    ),
    RowKind.RENDER_OVERLAY_CLOSING_ANIMATION_TYPE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_closing_animation",
        help_title="Animation type",
        help_entries=(("Left/Right", "cycle type"),),
        help_description=("How the closing card enters and leaves the screen.",),
        help_mode_entries=RENDER_OVERLAY_ANIMATION_TYPE_HELP_ENTRIES,
    ),
    RowKind.RENDER_OVERLAY_OPENING_ANIMATION_SLIDE_DIRECTION: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_opening_animation",
        help_title="Slide direction",
        help_entries=(("Left/Right", "cycle direction"),),
        help_description=(
            "Edge the opening card travels from on entrance (reverse on exit).",
        ),
        help_mode_entries=RENDER_OVERLAY_SLIDE_DIRECTION_HELP_ENTRIES,
    ),
    RowKind.RENDER_OVERLAY_CLOSING_ANIMATION_SLIDE_DIRECTION: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_closing_animation",
        help_title="Slide direction",
        help_entries=(("Left/Right", "cycle direction"),),
        help_description=(
            "Edge the closing card travels from on entrance (reverse on exit).",
        ),
        help_mode_entries=RENDER_OVERLAY_SLIDE_DIRECTION_HELP_ENTRIES,
    ),
    RowKind.RENDER_OVERLAY_OPENING_POSITION: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_opening",
        help_title="Position",
        help_description=(
            "Screen corner where the opening credits card appears.",
        ),
    ),
    RowKind.RENDER_OVERLAY_CLOSING_POSITION: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_closing",
        help_title="Position",
        help_description=(
            "Screen corner where the closing credits card appears.",
        ),
    ),
    RowKind.RENDER_OVERLAY_OPENING_TITLE_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        help_title="Opening card title",
        help_description=("Title line of the opening credits card.",),
        parent_group="render_overlay_opening",
    ),
    RowKind.RENDER_OVERLAY_CLOSING_TITLE_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        help_title="Closing card title",
        help_description=("Title line of the closing credits card.",),
        parent_group="render_overlay_closing",
    ),
    RowKind.RENDER_OVERLAY_OPENING_TITLE_FONT_SIZE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_opening_title",
        help_title="Title font size",
        help_description=("Font size of the opening card title.",),
    ),
    RowKind.RENDER_OVERLAY_CLOSING_TITLE_FONT_SIZE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_closing_title",
        help_title="Title font size",
        help_description=("Font size of the closing card title.",),
    ),
    RowKind.RENDER_OVERLAY_OPENING_TITLE_FONT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_opening_title",
        help_title="Title font",
        help_description=("Font used for the opening card title.",),
    ),
    RowKind.RENDER_OVERLAY_CLOSING_TITLE_FONT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_closing_title",
        help_title="Title font",
        help_description=("Font used for the closing card title.",),
    ),
    RowKind.RENDER_OVERLAY_OPENING_TITLE_MARGIN_BOTTOM: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_opening_title",
        help_title="Title margin bottom",
        help_description=(
            "Gap between the title and body in the opening card box.",
        ),
    ),
    RowKind.RENDER_OVERLAY_CLOSING_TITLE_MARGIN_BOTTOM: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_closing_title",
        help_title="Title margin bottom",
        help_description=(
            "Gap between the title and body in the closing card box.",
        ),
    ),
    RowKind.RENDER_OVERLAY_OPENING_BODY_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        help_title="Opening card body",
        help_description=("Body block of the opening credits card.",),
        parent_group="render_overlay_opening",
    ),
    RowKind.RENDER_OVERLAY_CLOSING_BODY_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        help_title="Closing card body",
        help_description=("Body block of the closing credits card.",),
        parent_group="render_overlay_closing",
    ),
    RowKind.RENDER_OVERLAY_OPENING_BODY_FONT_SIZE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_opening_body",
        help_title="Body font size",
        help_description=("Font size of the opening card body.",),
    ),
    RowKind.RENDER_OVERLAY_CLOSING_BODY_FONT_SIZE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_closing_body",
        help_title="Body font size",
        help_description=("Font size of the closing card body.",),
    ),
    RowKind.RENDER_OVERLAY_OPENING_BODY_FONT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_opening_body",
        help_title="Body font",
        help_description=("Font used for the opening card body.",),
    ),
    RowKind.RENDER_OVERLAY_CLOSING_BODY_FONT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_closing_body",
        help_title="Body font",
        help_description=("Font used for the closing card body.",),
    ),
    RowKind.RENDER_OVERLAY_OPENING_OPACITY: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_opening",
        help_title="Background opacity",
        help_description=("Background opacity of the opening credits card box.",),
    ),
    RowKind.RENDER_OVERLAY_CLOSING_OPACITY: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_closing",
        help_title="Background opacity",
        help_description=("Background opacity of the closing credits card box.",),
    ),
    RowKind.RENDER_OVERLAY_OPENING_BORDER_WIDTH: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_opening",
        help_title="Border width",
        help_description=(
            "Width of the border drawn around the opening credits card box.",
        ),
    ),
    RowKind.RENDER_OVERLAY_CLOSING_BORDER_WIDTH: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_closing",
        help_title="Border width",
        help_description=(
            "Width of the border drawn around the closing credits card box.",
        ),
    ),
    RowKind.RENDER_OVERLAY_OPENING_APPEAR_AT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_opening_animation",
        help_title="Appear at",
        help_description=(
            "The opening card appears this many seconds after the song starts.",
        ),
    ),
    RowKind.RENDER_OVERLAY_CLOSING_DISAPPEAR_AT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_closing_animation",
        help_title="Disappear at",
        help_description=(
            "The closing card disappears this many seconds before the song ends.",
        ),
    ),
    RowKind.RENDER_OVERLAY_OPENING_DISPLAY_TIME: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_opening_animation",
        help_title="Display time",
        help_description=(
            "Duration the opening card stays on screen including entrance and exit.",
            "0 = stays on.",
        ),
    ),
    RowKind.RENDER_OVERLAY_CLOSING_DISPLAY_TIME: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_overlay_closing_animation",
        help_title="Display time",
        help_description=(
            "Duration the closing card stays on screen including entrance and exit.",
            "0 = stays on.",
        ),
    ),
    RowKind.RENDER_POST_FX_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        can_enable_disable=True,
        can_solo=True,
        help_title="Post FX",
        help_description=(
            "Post-processing effects applied during final compositing.",
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
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        parent_group="render_post_fx",
        help_title="Highlight rolloff",
        help_description=(
            "Compresses bright hotspots during layer compositing.",
            "Prevents stacked black-key layers from washing out to white.",
            "Preserves hue by scaling RGB to the compressed luminance.",
            "With render.hdr_compositing enabled, a baseline display shoulder",
            "runs automatically; composite rolloff here is extra control.",
            "Per-layer rolloff is optional and can stay light.",
        ),
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_MODE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_post_fx_highlight_rolloff",
        help_title="Mode",
        help_entries=(("Left/Right", "cycle mode"),),
        help_description=("Where highlight rolloff is applied.",),
        help_mode_entries=HIGHLIGHT_ROLLOFF_APPLY_MODE_HELP_ENTRIES,
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CURVE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_post_fx_highlight_rolloff",
        help_title="Curve",
        help_entries=(("Left/Right", "cycle curve"),),
        help_description=("Shoulder curve used above the soft knee.",),
        help_mode_entries=HIGHLIGHT_ROLLOFF_CURVE_HELP_ENTRIES,
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_post_fx_highlight_rolloff",
        help_title="Threshold",
        help_description=(
            "Rec.709 luminance level where compression begins.",
            "Lower = compression starts earlier, more of the image affected.",
            "Higher = only the brightest peaks are compressed.",
        ),
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CEILING: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_post_fx_highlight_rolloff",
        help_title="Ceiling",
        help_description=(
            "Luminance target for fully compressed highlights.",
            "At full strength, saturated whites are pulled down to this level.",
            "Must be at or below threshold (e.g. threshold 78%, ceiling 65%).",
        ),
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_STRENGTH: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_post_fx_highlight_rolloff",
        help_title="Strength",
        help_description=(
            "How strongly highlights above the threshold are compressed.",
            "100% = full compression toward the ceiling.",
            "Above 100% (up to 200%) = extra aggressive pull toward the ceiling.",
            "Lower = gentler rolloff with more retained brightness.",
        ),
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_SOFTNESS: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_post_fx_highlight_rolloff",
        help_title="Softness",
        help_description=(
            "Width of the soft knee above the threshold.",
            "Higher = wider, more gradual transition into compression.",
            "Lower = tighter transition right at the threshold.",
        ),
    ),
    RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_DESATURATION: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_post_fx_highlight_rolloff",
        help_title="Desaturation",
        help_description=(
            "How much compressed highlights lose color purity.",
            "Higher = less pure white, more tinted or muted highlights.",
            "Hue is preserved during luminance scaling, then pulled toward gray.",
        ),
    ),
    RowKind.RENDER_POST_FX_CHROMA_BOOST_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        parent_group="render_post_fx",
        help_title="Chroma boost",
        help_description=(
            "Boosts saturation or vibrance around Rec.709 luma.",
            "Useful after highlight compression to restore perceived color.",
            "Vibrance spares already-saturated pixels to avoid clipping primaries.",
        ),
    ),
    RowKind.RENDER_POST_FX_CHROMA_BOOST_MODE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_post_fx_chroma_boost",
        help_title="Mode",
        help_entries=(("Left/Right", "cycle mode"),),
        help_description=("Where chroma boost is applied.",),
        help_mode_entries=CHROMA_BOOST_APPLY_MODE_HELP_ENTRIES,
    ),
    RowKind.RENDER_POST_FX_CHROMA_BOOST_VARIANT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_post_fx_chroma_boost",
        help_title="Variant",
        help_entries=(("Left/Right", "cycle variant"),),
        help_description=("Saturation vs vibrance weighting.",),
        help_mode_entries=CHROMA_BOOST_VARIANT_HELP_ENTRIES,
    ),
    RowKind.RENDER_POST_FX_CHROMA_BOOST_AMOUNT: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="render_post_fx_chroma_boost",
        help_title="Amount",
        help_description=(
            "Chroma boost strength as a percentage.",
            "0% disables the pass even when mode is not off.",
        ),
    ),
    RowKind.RENDER_TIMELINE_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        can_enable_disable=True,
        can_solo=False,
        help_title="Timeline",
        help_description=(
            "Layer visibility automation.",
            "When enabled, standard layer visibility is disabled.",
        ),
        quick_nav_target=True,
    ),
    RowKind.TIMELINE_PRESETS_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        help_title="Timeline preset",
        help_description=(
            "Stage character, crescendo, density, and conductor, then apply a",
            "randomly generated timeline preset. This overwrites the current timeline.",
        ),
    ),
    RowKind.TIMELINE_PRESET_CHARACTER: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Character",
        help_entries=(("Left/Right", "cycle character"),),
        help_description=(
            "Procedural timeline character used when applying a preset.",
            "If song markers are present, they are favoured for cue placement.",
        ),
        help_mode_entries=TIMELINE_PRESET_HELP_ENTRIES,
    ),
    RowKind.TIMELINE_PRESET_CRESCENDO: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Crescendo",
        help_entries=(("Left/Right", "cycle crescendo target"),),
        help_description=(
            "Optional build to a crescendo at a song marker.",
            "Requires three or more song markers; otherwise apply skips crescendo.",
        ),
    ),
    RowKind.TIMELINE_PRESET_DENSITY: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Density",
        help_entries=(("Left/Right", "cycle density"),),
        help_description=(
            "How aggressively the generator favors denser layer stacks.",
            "Normal matches the default stack-cost ramp for the layer count.",
        ),
    ),
    RowKind.TIMELINE_PRESET_CUE_SNAP: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Cue snap",
        help_entries=(("Left/Right", "cycle cue snap"),),
        help_description=(
            "After build, snap cues to the beat or bar grid.",
            "None leaves cue times from the generator unchanged.",
        ),
    ),
    RowKind.TIMELINE_PRESET_SONG_MARKER_SNAP: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Song marker snap",
        help_entries=(("Left/Right", "cycle song marker snap proximity"),),
        help_description=(
            "After cue snap, pull nearby cues onto song markers.",
            "Applies each_layer scope across all slots; none skips.",
        ),
    ),
    RowKind.TIMELINE_PRESET_TIMELINE_CUTS: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Timeline cuts",
        help_entries=(("Left/Right", "cycle timeline cuts"),),
        help_description=(
            "After snaps, assign hard/soft cut types to cues.",
            "By marker sets soft everywhere then hard on song markers.",
        ),
    ),
    RowKind.TIMELINE_PRESET_CONDUCTOR: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Conductor",
        help_entries=(("Left/Right", "toggle conductor on/off"),),
        help_description=(
            "When on, stem energy shapes motif casting and cue levels.",
            "Requires project signals; otherwise apply skips the conductor.",
        ),
    ),
    RowKind.TIMELINE_PRESETS: RowBehavior(
        RowAffordance.ACTION,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Apply timeline preset",
        help_entries=(("Enter", "apply timeline preset"),),
        help_description=(
            "Apply the staged character, crescendo, density, snaps, cuts, and conductor.",
            "This overwrites the current timeline.",
        ),
    ),
    RowKind.TIMELINE_VISUAL_LIMITER_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        can_enable_disable=True,
        help_title="Visual limiter",
        help_entries=(("Left/Right", "disable / enable"),),
        help_description=(
            "Duck busy stacked layers using post-composite busyness.",
            "When enabled, threshold and release rows appear below.",
        ),
    ),
    RowKind.TIMELINE_VISUAL_LIMITER_THRESHOLD: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        repeatable=True,
        blocked_by_section_lock=True,
        help_title="Visual limiter threshold",
        help_entries=(
            ("Left", "decrease threshold"),
            ("Right", "increase threshold"),
        ),
        help_description=(
            "Busyness level that starts ducking hot layers.",
            "Off-threshold stays a fixed gap below this value.",
        ),
    ),
    RowKind.TIMELINE_VISUAL_LIMITER_RELEASE: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        repeatable=True,
        blocked_by_section_lock=True,
        help_title="Visual limiter release",
        help_entries=(
            ("Left", "decrease release ramp"),
            ("Right", "increase release ramp"),
        ),
        help_description=(
            "Playhead seconds to ramp ducked layers back to full opacity.",
            "Release hold before the ramp scales with this value.",
        ),
    ),
    RowKind.TIMELINE_RESET: RowBehavior(
        RowAffordance.ACTION,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Reset timeline",
        help_entries=(("Enter", "reset timeline"),),
        help_description=(
            "Clear all timeline cues and set every layer",
            "on or off for the whole track.",
        ),
        help_mode_entries=TIMELINE_RESET_HELP_ENTRIES,
    ),
    RowKind.TIMELINE_BEAT_BAR_GRID_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        help_title="Beat / bar grid",
        help_description=(
            "AI beat detection powered by Beat This!",
        ),
    ),
    RowKind.TIMELINE_BAR_PHASE: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        repeatable=True,
        blocked_by_section_lock=True,
        help_title="Bar phase",
        help_entries=(
            ("Left", "shift cues -1 beat"),
            ("Right", "shift cues +1 beat"),
        ),
        help_description=(
            "Nudge all timeline cues by one beat.",
            "Tip: re-apply snap to song markers after adjusting this."
        ),
    ),
    RowKind.TIMELINE_BAR_GRID: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Bar grid",
        help_entries=(
            ("Left", "hide detected bar lines"),
            ("Right", "show detected bar lines"),
        ),
        help_description=(
            "Show Beat This! bar detection points on the timeline strip.",
            "Gaps mean missing detection (no rhythm/drums).",
        ),
    ),
    RowKind.TIMELINE_PLACEMENT_SNAP: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Placement snap",
        help_entries=(("Left/Right", "cycle off / beat / bar"),),
        help_description=(
            "Applies when placing song markers and timeline cues",
            "Snap to the nearest beat or bar.",
            "Switch off when the beat detection is not accurate.",
        ),
    ),
    RowKind.TIMELINE_SNAP_CUES_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        help_title="Snap cues",
        help_description=(
            "One-shot actions that pull existing timeline cues onto the beat grid or song markers.",
        ),
    ),
    RowKind.TIMELINE_SNAP_TO_BEATS: RowBehavior(
        RowAffordance.ACTION,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Snap to beats",
        help_entries=(("Enter", "snap cues to beats"),),
        help_description=(
            "Snap all timeline cues to the nearest beat.",
        ),
    ),
    RowKind.TIMELINE_SNAP_TO_BARS: RowBehavior(
        RowAffordance.ACTION,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Snap to bars",
        help_entries=(("Enter", "snap cues to bars"),),
        help_description=(
            "Snap all timeline cues to the nearest bar.",
        ),
    ),
    RowKind.TIMELINE_SNAP_TO_SONG_MARKERS: RowBehavior(
        RowAffordance.ACTION,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Snap to song markers",
        help_entries=(("Enter", "snap cues to song markers"),),
        help_description=(
            "Pull closest cues within proximity onto song markers.",
        ),
    ),
    RowKind.TIMELINE_CUTS_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        help_title="Timeline cuts",
        help_description=(
            "Opacity fade in and out for timeline cue edges by cut type.",
        ),
    ),
    RowKind.TIMELINE_HARD_CUTS: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        repeatable=True,
        blocked_by_section_lock=True,
        help_title="Hard cuts",
        help_entries=(("Left/Right", "enabled / disabled"),),
        help_description=(
            "Fade edges on cues with cut set to hard.",
        ),
    ),
    RowKind.TIMELINE_HARD_CUT_FADE_IN: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        repeatable=True,
        blocked_by_section_lock=True,
        help_title="Hard cut fade in",
        help_entries=(
            ("Left", "decrease fade in"),
            ("Right", "increase fade in"),
        ),
        help_description=(
            "The fade-in starts this many seconds before a hard-cut cue.",
        ),
    ),
    RowKind.TIMELINE_HARD_CUT_FADE_OUT: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        repeatable=True,
        blocked_by_section_lock=True,
        help_title="Hard cut fade out",
        help_entries=(
            ("Left", "decrease fade out"),
            ("Right", "increase fade out"),
        ),
        help_description=(
            "The fade-out starts this many seconds after a hard-cut cue.",
        ),
    ),
    RowKind.TIMELINE_SOFT_CUTS: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        repeatable=True,
        blocked_by_section_lock=True,
        help_title="Soft cuts",
        help_entries=(("Left/Right", "enabled / disabled"),),
        help_description=(
            "Fade edges on cues with cut set to soft.",
        ),
    ),
    RowKind.TIMELINE_SOFT_CUT_FADE_IN: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        repeatable=True,
        blocked_by_section_lock=True,
        help_title="Soft cut fade in",
        help_entries=(
            ("Left", "decrease fade in"),
            ("Right", "increase fade in"),
        ),
        help_description=(
            "The fade-in starts this many seconds before a soft-cut cue.",
        ),
    ),
    RowKind.TIMELINE_SOFT_CUT_FADE_OUT: RowBehavior(
        RowAffordance.VALUE_STEP,
        navigable=True,
        repeatable=True,
        blocked_by_section_lock=True,
        help_title="Soft cut fade out",
        help_entries=(
            ("Left", "decrease fade out"),
            ("Right", "increase fade out"),
        ),
        help_description=(
            "The fade-out starts this many seconds after a soft-cut cue.",
        ),
    ),
    RowKind.TIMELINE_APPLY_SOFT_CUTS: RowBehavior(
        RowAffordance.ACTION,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Apply soft cuts to cues",
        help_entries=(("Enter", "apply soft cuts"),),
        help_description=(
            "Set cut type soft on all cues, song-marker cues, or all except markers.",
        ),
    ),
    RowKind.TIMELINE_APPLY_HARD_CUTS: RowBehavior(
        RowAffordance.ACTION,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Apply hard cuts to cues",
        help_entries=(("Enter", "apply hard cuts"),),
        help_description=(
            "Set cut type hard on all cues, song-marker cues, or all except markers.",
        ),
    ),
    RowKind.SONG_MARKERS_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        help_title="Song markers",
        help_description=(
            "Manual song markers for major transitions.",
            "Ctrl+Enter drops a marker at the playhead.",
        ),
    ),
    RowKind.SONG_MARKER_ITEM: RowBehavior(
        RowAffordance.ACTION,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Song marker",
        help_entries=(
            ("Enter", "seek to marker"),
            ("Delete", "confirm remove"),
        ),
        help_description=(
            "A song marker time. Enter seeks the playhead;",
            "Delete asks to remove the marker.",
        ),
    ),
    RowKind.SETTINGS_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_header=True,
        help_title="Editor Settings",
        help_description=("Global editor settings (applies to all projects)",),
        quick_nav_target=True,
        quick_nav_always=True,
    ),
    RowKind.SETTINGS_EDITOR_MODE: RowBehavior(
        RowAffordance.ACTION_PARAMETER,
        is_pinned=True,
        repeatable=True,
        parent_group="settings",
        help_title="Editor mode",
        help_entries=(
            ("Left/Right", "cycle mode"),
            ("Enter", "confirm switch"),
        ),
        help_description=(
            "Visualizer mode exposes the full tuning panel.",
            "Preset curation mode limits the panel to preset favourites and blacklist.",
            "Left/Right stages a mode; Enter confirms the switch.",
        ),
    ),
    RowKind.SETTINGS_PREVIEW_QUALITY: RowBehavior(
        RowAffordance.VALUE_STEP,
        is_pinned=True,
        repeatable=True,
        parent_group="settings",
        help_title="Preview quality",
        help_entries=(("Left/Right", "cycle mode"),),
        help_description=(
            "Trade-off between visual quality and CPU/GPU load.",
            "Affects layer resolution scaling in the live view only.",
        ),
        help_mode_entries=EDITOR_PREVIEW_QUALITY_HELP_ENTRIES,
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
    RowKind.SETTINGS_LATENCY_COMPENSATION_HEADER: RowBehavior(
        RowAffordance.EXPAND,
        is_sub_header=True,
        is_pinned=True,
        parent_group="settings",
        help_title="Latency Compensation",
        help_description=(
            "Use this to correct for bluetooth/wireless latency.",
            "Affects new timeline cue & song marker placements only.",
            "Already saved markers and cues do not move when you change this."
        ),
    ),
    RowKind.SETTINGS_RESIDUAL_LATENCY_MS: RowBehavior(
        RowAffordance.VALUE_STEP,
        is_pinned=True,
        repeatable=True,
        parent_group="settings_latency_compensation",
        help_title="Residual latency",
        help_entries=(
            ("Left/Right", "adjust latency (10 ms)"),
            ("Ctrl + Left/Right", "large step (50 ms)"),
        ),
        help_description=(
            "Compensates for unmeasurable input/output lag for live monitoring",
            "and timeline cue/song marker placement.",
        ),
    ),
    RowKind.SETTINGS_MEASURE_LATENCY: RowBehavior(
        RowAffordance.ACTION,
        is_pinned=True,
        parent_group="settings_latency_compensation",
        help_title="Measure latency",
        help_entries=(
            ("Enter", "start calibration"),
            ("Space", "tap on each bar beat"),
            ("Esc", "cancel"),
        ),
        help_description=(
            "Plays a 140 BPM click track.",
            "Measurement is confirmed when four consistent taps are detected.",
        ),
    ),
}

HEADER_ROW_KINDS = frozenset(k for k, b in ROW_BEHAVIORS.items() if b.is_header)
REPEAT_ROW_KINDS = frozenset(k for k, b in ROW_BEHAVIORS.items() if b.repeatable)
ACTION_ROW_KINDS = frozenset(
    k for k, b in ROW_BEHAVIORS.items() if b.affordance == RowAffordance.ACTION
)
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
TRACK_LOCK_KINDS = TRACK_SUB_ROW_KINDS | frozenset({RowKind.TRACK_HEADER})
TRACK_EFFECT_SUB_ROW_KINDS = frozenset({RowKind.TRACK_EFFECT})
TRACK_USER_PRESET_SUB_ROW_KINDS = frozenset(
    {RowKind.TRACK_USER_PRESET_ITEM, RowKind.TRACK_USER_PRESET_ADD}
)
SONG_MARKER_SUB_ROW_KINDS = frozenset({RowKind.SONG_MARKER_ITEM})
PRESET_FILE_ROW_KINDS = frozenset({RowKind.TRACK_PRESET, RowKind.TRACK_USER_PRESET_ITEM})

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


def _derived_blocked_by_section_lock(behavior: RowBehavior) -> bool:
    if behavior.blocked_by_section_lock is not None:
        return behavior.blocked_by_section_lock
    return (
        _in_lockable_group(behavior.parent_group)
        and behavior.affordance in _SECTION_LOCK_BLOCKING_AFFORDANCES
    )


def _derived_navigable_when_section_locked(behavior: RowBehavior) -> bool:
    if behavior.navigable_when_section_locked is not None:
        return behavior.navigable_when_section_locked
    # Section and sub-section headers stay navigable so the section can still be
    # expanded and viewed while locked.
    return behavior.affordance == RowAffordance.EXPAND


def row_blocked_by_section_lock(kind: RowKind) -> bool:
    return _derived_blocked_by_section_lock(row_behavior(kind))


def row_navigable_when_section_locked(kind: RowKind) -> bool:
    return _derived_navigable_when_section_locked(row_behavior(kind))


def _state_track_locked(state: object, slot: str) -> bool:
    tracks = getattr(state, "tracks", None)
    if tracks is not None:
        return bool(tracks[slot].locked)
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
    if section == "timeline":
        return _state_timeline_locked(state)
    return False


def section_lock_blocks_mutation(state: object, desc: RowDescriptor) -> bool:
    return section_locked(state, desc) and row_blocked_by_section_lock(desc.kind)


def row_triggers_layer_delete(kind: RowKind) -> bool:
    """True when Delete should prompt to remove the focused track block's layer."""
    if kind == RowKind.TRACK_HEADER:
        return True
    return row_behavior(kind).parent_group == "track"


from cleave.viz.row_sections import (
    RENDER_OVERLAY_SECTION_KINDS,
    RENDER_POST_FX_SECTION_KINDS,
    RENDER_TIMELINE_SECTION_KINDS,
    section_header_from_section_tree,
)


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
    if kind in SONG_MARKER_SUB_ROW_KINDS:
        return RowDescriptor(RowKind.SONG_MARKERS_HEADER)
    return desc
