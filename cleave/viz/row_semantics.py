"""Row interaction semantics for the live tuning overlay."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from cleave.blend_modes import BLEND_MODE_HELP_ENTRIES
from cleave.config_schema import (
    CHROMA_BOOST_APPLY_MODE_HELP_ENTRIES,
    CHROMA_BOOST_VARIANT_HELP_ENTRIES,
    HIGHLIGHT_ROLLOFF_APPLY_MODE_HELP_ENTRIES,
    HIGHLIGHT_ROLLOFF_CURVE_HELP_ENTRIES,
    PRESET_SWITCHING_MODE_HELP_ENTRIES,
    EDITOR_PREVIEW_QUALITY_HELP_ENTRIES,
)
from cleave.timeline_presets import (
    TIMELINE_PRESET_HELP_ENTRIES,
    TIMELINE_RESET_HELP_ENTRIES,
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
    TRACK_PRESET_SWITCHING_SHUFFLE = auto()
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
    TIMELINE_PRESETS = auto()
    TIMELINE_RESET = auto()
    TIMELINE_BEAT_BAR_GRID_HEADER = auto()
    TIMELINE_BAR_PHASE = auto()
    TIMELINE_BAR_GRID = auto()
    TIMELINE_SNAP_TO_BEATS = auto()
    TIMELINE_SNAP_TO_BARS = auto()
    TIMELINE_SNAP_MARKER_PROXIMITY = auto()
    TIMELINE_SNAP_MARKER_SCOPE = auto()
    TIMELINE_SNAP_TO_SONG_MARKERS = auto()
    SONG_MARKERS_HEADER = auto()
    SONG_MARKER_ITEM = auto()
    SETTINGS_HEADER = auto()
    SETTINGS_PREVIEW_QUALITY = auto()
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
        blocked_by_section_lock=True,
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
    RowKind.TRACK_PRESET_SWITCHING_SHUFFLE: RowBehavior(
        RowAffordance.VALUE_STEP,
        repeatable=True,
        parent_group="track",
        help_title="Shuffle",
        help_entries=(("Left/Right", "off / on"),),
        help_description=(
            "When on, each auto switch picks a random preset from the rotation set",
            "instead of the next in order. Preset position (N/X) may jump.",
            "Manual Left/Right on the preset file row is unchanged.",
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
            "Post-processing effects applied during final compositing:",
            "fade in, fade out, highlight rolloff, and chroma boost.",
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
            "Timeline automation for layer visibility.",
            "Cues are burned into the offline render.",
            "When enabled, standard layer visibility is disabled;",
            "visibility is controlled by the timeline instead.",
        ),
        quick_nav_target=True,
    ),
    RowKind.TIMELINE_PRESETS: RowBehavior(
        RowAffordance.ACTION,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Timeline presets",
        help_entries=(("Enter", "apply a timeline preset"),),
        help_description=(
            "Apply a randomly generated timeline preset",
            "(this will overwrite the current timeline).",
        ),
        help_mode_entries=TIMELINE_PRESET_HELP_ENTRIES,
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
            "Bar phase, bar grid display, and snap cues to beats or bars.",
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
            "Nudge all committed timeline cues by one beat;",
            "sticky session offset +0..+3 (mod 4).",
            "Presets regenerate on this phase-shifted bar grid.",
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
            "Gaps mean missing detection (no drums)",
        ),
    ),
    RowKind.TIMELINE_SNAP_TO_BEATS: RowBehavior(
        RowAffordance.ACTION,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Snap to beats",
        help_entries=(("Enter", "snap cues to beats"),),
        help_description=(
            "Snap all committed timeline cues to the nearest beat",
            "(irreversible).",
        ),
    ),
    RowKind.TIMELINE_SNAP_TO_BARS: RowBehavior(
        RowAffordance.ACTION,
        navigable=True,
        blocked_by_section_lock=True,
        help_title="Snap to bars",
        help_entries=(("Enter", "snap cues to bars"),),
        help_description=(
            "Snap all committed timeline cues to the nearest bar",
            "(irreversible).",
        ),
    ),
    RowKind.TIMELINE_SNAP_MARKER_PROXIMITY: RowBehavior(
        RowAffordance.ACTION_PARAMETER,
        navigable=True,
        repeatable=True,
        blocked_by_section_lock=True,
        help_title="Snap proximity",
        help_entries=(
            ("Left", "decrease proximity"),
            ("Right", "increase proximity"),
        ),
        help_description=(
            "Maximum distance for snap to song markers.",
        ),
    ),
    RowKind.TIMELINE_SNAP_MARKER_SCOPE: RowBehavior(
        RowAffordance.ACTION_PARAMETER,
        navigable=True,
        repeatable=True,
        blocked_by_section_lock=True,
        help_title="Snap layer scope",
        help_entries=(("Left/Right", "cycle layer scope"),),
        help_description=(
            "Which tracks snap to song markers.",
            "Per-layer, closest wins, or all layers independently.",
        ),
    ),
    RowKind.TIMELINE_SNAP_TO_SONG_MARKERS: RowBehavior(
        RowAffordance.ACTION,
        navigable=True,
        navigable_when_section_locked=True,
        blocked_by_section_lock=True,
        help_title="Snap to song markers",
        help_entries=(
            ("Enter", "snap cues to song markers"),
            ("Left", "collapse"),
            ("Right", "expand"),
        ),
        help_description=(
            "Pull closest cues within proximity onto song markers",
            "(irreversible; confirm uses proximity and layer scope).",
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
        help_description=("Global editor settings (not per-layer).",),
        quick_nav_target=True,
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
}

HEADER_ROW_KINDS = frozenset(k for k, b in ROW_BEHAVIORS.items() if b.is_header)
REPEAT_ROW_KINDS = frozenset(k for k, b in ROW_BEHAVIORS.items() if b.repeatable)
ACTION_PARAMETER_SUB_ROW_KINDS = frozenset(
    k
    for k, b in ROW_BEHAVIORS.items()
    if b.affordance == RowAffordance.ACTION_PARAMETER and not b.is_header
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
    """
    section = _row_lock_section(desc.kind)
    if section is None:
        return False
    if section == "track":
        slot = desc.slot
        if slot is None:
            return False
        return _state_track_locked(state, slot)
    if section == "render_overlay":
        return bool(state.render_overlay.locked)
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
