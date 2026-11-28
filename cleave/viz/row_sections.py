"""Section composition for inspector pages."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from cleave.effects.registry import effect_roster
from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.row_kinds import RowDescriptor, RowKind

if TYPE_CHECKING:
    from cleave.viz.tuning_view_state import TuningViewState


AppendDynamicChildrenFn = Callable[[list[RowDescriptor], "TuningViewState", str | None], None]
PredicateFn = Callable[["TuningViewState", RowDescriptor], bool]


@dataclass(frozen=True)
class ConditionalRowsDef:
    """Value-gated rows.

    By default children share the parent's depth (siblings of the gating
    control). Set ``child_indent_offset`` to nest them visually under that
    control (e.g. seed under shuffle).
    """

    name: str
    predicate: PredicateFn
    children: tuple["SectionNode", ...]
    child_indent_offset: int = 0


@dataclass(frozen=True)
class SectionNode:
    """Tree node: leaf row, headed subsection, conditional group, buttons, or divider.

    ``commands`` is one row of buttons, as ids in the command registry.
    ``status`` is a line of text at the start of that row.
    ``divider`` is a thin rule between rows.
    ``with_commands`` moves a leaf row down to the page's buttons, under the
    divider, for a setting that belongs with the command beside it.
    """

    leaf_kind: RowKind | None = None
    subsection: SectionDef | None = None
    conditional: ConditionalRowsDef | None = None
    commands: tuple[str, ...] | None = None
    status: str | None = None
    divider: bool = False
    with_commands: bool = False

    def __post_init__(self) -> None:
        set_count = self.divider + sum(
            x is not None
            for x in (self.leaf_kind, self.subsection, self.conditional, self.commands)
        )
        if set_count != 1:
            raise ValueError("SectionNode requires exactly one child type")
        if self.with_commands and self.leaf_kind is None:
            raise ValueError("with_commands applies only to a leaf row")


@dataclass(frozen=True)
class SectionDef:
    """Rows of one inspector page, or of a headed block inside a page.

    A navigator node names the section for its page. A section nested through
    ``SectionNode.subsection`` draws its header as a static heading.
    """

    header_kind: RowKind | None
    context: Literal["global", "per_slot"]
    children: tuple[SectionNode, ...] = ()
    append_dynamic_children: AppendDynamicChildrenFn | None = None
    card: str | None = None
    # A command drawn as a button on the left of the page title's icon line,
    # shown while *title_command_when* (if set) holds for the page's slot.
    title_command: str | None = None
    title_command_when: PredicateFn | None = None
    # False: the page's buttons join its last group of rows instead of
    # sitting under a divider of their own.
    commands_divider: bool = True


def _append_track_effect_rows(
    row_list: list[RowDescriptor],
    state: TuningViewState,
    slot: str | None,
) -> None:
    if slot is None:
        return
    block = state.tracks[slot]
    for effect_def in effect_roster(block.runtime.stem):
        row_list.append(
            RowDescriptor(
                RowKind.TRACK_EFFECT,
                slot=slot,
                effect_id=effect_def.effect_id,
                driver_slug=effect_def.driver_slug,
            )
        )


def _append_preset_list_rows(
    row_list: list[RowDescriptor],
    state: TuningViewState,
    slot: str | None,
) -> None:
    if slot is None:
        return
    block = state.tracks[slot]
    for index, _path in enumerate(block.runtime.preset_list):
        row_list.append(
            RowDescriptor(
                RowKind.TRACK_PRESET_LIST_ITEM,
                slot=slot,
                preset_index=index,
            )
        )


def _append_song_marker_rows(
    row_list: list[RowDescriptor],
    state: TuningViewState,
    _slot: str | None,
) -> None:
    for index in range(len(state.timeline.song_marker_times)):
        row_list.append(
            RowDescriptor(RowKind.SONG_MARKER_ITEM, marker_index=index)
        )


SETTINGS_PREVIEW_SECTION = SectionDef(
    header_kind=RowKind.SETTINGS_PREVIEW_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.SETTINGS_PREVIEW_QUALITY),
    ),
)

SETTINGS_LATENCY_SECTION = SectionDef(
    header_kind=RowKind.SETTINGS_LATENCY_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.SETTINGS_AUDIO_LATENCY_MS),
        SectionNode(leaf_kind=RowKind.SETTINGS_TAP_LATENCY_MS),
        SectionNode(
            commands=("settings.measure_latency", "settings.calibrate_tap_timing")
        ),
    ),
)

SETTINGS_UI_SECTION = SectionDef(
    header_kind=RowKind.SETTINGS_UI_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.SETTINGS_UI_SCALE),
        SectionNode(divider=True),
        SectionNode(leaf_kind=RowKind.SETTINGS_UI_NOTIFICATION_DISPLAY),
        SectionNode(leaf_kind=RowKind.SETTINGS_UI_HIGHLIGHT_NEW_PAGE),
        SectionNode(leaf_kind=RowKind.SETTINGS_UI_SHOW_TOOLTIPS),
        SectionNode(divider=True),
        SectionNode(leaf_kind=RowKind.SETTINGS_NAVIGATOR_SIDE),
        SectionNode(leaf_kind=RowKind.SETTINGS_NAVIGATOR_EXPAND_CLICK),
        SectionNode(divider=True),
        SectionNode(leaf_kind=RowKind.SETTINGS_HELP_SIDE),
        SectionNode(divider=True),
        SectionNode(leaf_kind=RowKind.SETTINGS_UI_THEME),
        SectionNode(
            commands=("settings.open_themes_folder", "settings.reload_themes")
        ),
    ),
    commands_divider=False,
)

SETTINGS_DEV_TOOLS_SECTION = SectionDef(
    header_kind=RowKind.SETTINGS_DEV_TOOLS_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.SETTINGS_DEV_TOOLS_CRASH_LOG),
        SectionNode(commands=("settings.open_crash_log_folder",)),
    ),
)

PROJECT_MILKDROP_SECTION = SectionDef(
    header_kind=RowKind.PROJECT_MILKDROP_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.PROJECT_MILKDROP_BEAT_SENSITIVITY),
    ),
)

PROJECT_COMPOSITOR_SECTION = SectionDef(
    header_kind=RowKind.PROJECT_COMPOSITOR_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.PROJECT_COMPOSITOR_HDR),
    ),
)

PROJECT_RESOLUTION_SECTION = SectionDef(
    header_kind=RowKind.PROJECT_RESOLUTION_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.PROJECT_RESOLUTION_WIDTH),
        SectionNode(leaf_kind=RowKind.PROJECT_RESOLUTION_HEIGHT),
    ),
)


def _layers_show_add(state: TuningViewState, _desc: RowDescriptor) -> bool:
    return not is_preset_curation_mode(state.settings.editor_mode)


LAYERS_SHOW_ADD = ConditionalRowsDef(
    name="layers_show_add",
    predicate=_layers_show_add,
    children=(SectionNode(commands=("layers.add",)),),
)

LAYERS_SECTION = SectionDef(
    header_kind=None,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.LAYER_MANAGEMENT_COUNT),
        SectionNode(conditional=LAYERS_SHOW_ADD),
    ),
)

CURATION_LAYER_SECTION = SectionDef(
    header_kind=RowKind.TRACK_HEADER,
    context="per_slot",
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_STEM),
        SectionNode(leaf_kind=RowKind.TRACK_BEAT),
        SectionNode(leaf_kind=RowKind.TRACK_PRESET_DIR),
        SectionNode(leaf_kind=RowKind.TRACK_PRESET),
    ),
)

def _build_overlay_card_section(card: str) -> SectionDef:
    title_section = SectionDef(
        header_kind=RowKind.OVERLAY_CARD_TITLE_HEADER,
        context="global",
        card=card,
        children=(
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_TITLE_TEXT),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_TITLE_COLOUR),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_TITLE_BACKGROUND_COLOUR),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_TITLE_FONT),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_TITLE_FONT_SIZE),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_TITLE_MARGIN_BOTTOM),
        ),
    )
    body_section = SectionDef(
        header_kind=RowKind.OVERLAY_CARD_BODY_HEADER,
        context="global",
        card=card,
        children=(
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_BODY_TEXT),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_BODY_COLOUR),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_BODY_BACKGROUND_COLOUR),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_BODY_FONT),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_BODY_FONT_SIZE),
        ),
    )
    slide_conditional = ConditionalRowsDef(
        name=f"overlay_{card}_animation_slide_direction",
        predicate=(
            lambda state, _desc, card=card: getattr(
                state.overlays, card
            ).runtime.animation.type
            != "fade"
        ),
        children=(
            SectionNode(
                leaf_kind=RowKind.OVERLAY_CARD_ANIMATION_SLIDE_DIRECTION
            ),
        ),
    )
    animation_section = SectionDef(
        header_kind=RowKind.OVERLAY_CARD_ANIMATION_HEADER,
        context="global",
        card=card,
        children=(
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_ANIMATION_TYPE),
            SectionNode(conditional=slide_conditional),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_TIME),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_DISPLAY_TIME),
        ),
    )
    return SectionDef(
        header_kind=RowKind.OVERLAY_CARD_HEADER,
        context="global",
        card=card,
        children=(
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_ENABLED),
            SectionNode(subsection=animation_section),
            SectionNode(divider=True),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_POSITION),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_OPACITY),
            SectionNode(divider=True),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_BACKGROUND_COLOUR),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_BACKGROUND_MARGIN),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_BACKGROUND_PADDING),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_BORDER_WIDTH),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_BORDER_COLOUR),
            SectionNode(divider=True),
            SectionNode(subsection=title_section),
            SectionNode(subsection=body_section),
        ),
    )


OVERLAY_OPENING_CARD_SECTION = _build_overlay_card_section(
    "opening_card"
)
OVERLAY_CLOSING_CARD_SECTION = _build_overlay_card_section(
    "closing_card"
)

OVERLAY_PAGE_SECTION = SectionDef(
    header_kind=None,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.OVERLAYS_PREVIEW),
        SectionNode(leaf_kind=RowKind.OVERLAYS_LOCKED),
    ),
)

OVERLAYS_SECTION = SectionDef(
    header_kind=RowKind.OVERLAYS_HEADER,
    context="global",
    children=(
        SectionNode(subsection=OVERLAY_OPENING_CARD_SECTION),
        SectionNode(subsection=OVERLAY_CLOSING_CARD_SECTION),
    ),
)

POST_FX_HIGHLIGHT_ROLLOFF_ACTIVE = ConditionalRowsDef(
    name="highlight_rolloff_active",
    predicate=lambda state, _desc: state.post_fx.highlight_rolloff.enabled,
    children=(
        SectionNode(leaf_kind=RowKind.POST_FX_HIGHLIGHT_ROLLOFF_MODE),
        SectionNode(leaf_kind=RowKind.POST_FX_HIGHLIGHT_ROLLOFF_CURVE),
        SectionNode(leaf_kind=RowKind.POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD),
        SectionNode(leaf_kind=RowKind.POST_FX_HIGHLIGHT_ROLLOFF_CEILING),
        SectionNode(leaf_kind=RowKind.POST_FX_HIGHLIGHT_ROLLOFF_STRENGTH),
        SectionNode(leaf_kind=RowKind.POST_FX_HIGHLIGHT_ROLLOFF_SOFTNESS),
        SectionNode(leaf_kind=RowKind.POST_FX_HIGHLIGHT_ROLLOFF_DESATURATION),
    ),
)

POST_FX_HIGHLIGHT_ROLLOFF_SECTION = SectionDef(
    header_kind=RowKind.POST_FX_HIGHLIGHT_ROLLOFF_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.POST_FX_HIGHLIGHT_ROLLOFF_ENABLED),
        SectionNode(conditional=POST_FX_HIGHLIGHT_ROLLOFF_ACTIVE),
    ),
)

POST_FX_CHROMA_BOOST_ACTIVE = ConditionalRowsDef(
    name="chroma_boost_active",
    predicate=lambda state, _desc: state.post_fx.chroma_boost.enabled,
    children=(
        SectionNode(leaf_kind=RowKind.POST_FX_CHROMA_BOOST_MODE),
        SectionNode(leaf_kind=RowKind.POST_FX_CHROMA_BOOST_VARIANT),
        SectionNode(leaf_kind=RowKind.POST_FX_CHROMA_BOOST_AMOUNT),
    ),
)

def _post_fx_limiter_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> bool:
    return state.post_fx.limiter.enabled


POST_FX_LIMITER_ACTIVE = ConditionalRowsDef(
    name="visual_limiter_enabled",
    predicate=_post_fx_limiter_enabled,
    children=(
        SectionNode(leaf_kind=RowKind.POST_FX_LIMITER_THRESHOLD),
        SectionNode(leaf_kind=RowKind.POST_FX_LIMITER_RATIO),
        SectionNode(leaf_kind=RowKind.POST_FX_LIMITER_RELEASE),
    ),
)

POST_FX_LIMITER_SECTION = SectionDef(
    header_kind=RowKind.POST_FX_LIMITER_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.POST_FX_LIMITER_ENABLED),
        SectionNode(conditional=POST_FX_LIMITER_ACTIVE),
    ),
)

POST_FX_CHROMA_BOOST_SECTION = SectionDef(
    header_kind=RowKind.POST_FX_CHROMA_BOOST_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.POST_FX_CHROMA_BOOST_ENABLED),
        SectionNode(conditional=POST_FX_CHROMA_BOOST_ACTIVE),
    ),
)

POST_FX_FADE_IN_SECTION = SectionDef(
    header_kind=RowKind.POST_FX_FADE_IN_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.POST_FX_FADE_IN_START),
        SectionNode(leaf_kind=RowKind.POST_FX_FADE_IN_END),
        SectionNode(leaf_kind=RowKind.POST_FX_FADE_IN_TYPE),
    ),
)

POST_FX_FADE_OUT_SECTION = SectionDef(
    header_kind=RowKind.POST_FX_FADE_OUT_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.POST_FX_FADE_OUT_START),
        SectionNode(leaf_kind=RowKind.POST_FX_FADE_OUT_END),
        SectionNode(leaf_kind=RowKind.POST_FX_FADE_OUT_TYPE),
    ),
)

POST_FX_FADE_SECTION = SectionDef(
    header_kind=RowKind.POST_FX_FADE_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.POST_FX_FADE_ENABLED),
        SectionNode(subsection=POST_FX_FADE_IN_SECTION),
        SectionNode(subsection=POST_FX_FADE_OUT_SECTION),
    ),
)

POST_FX_PAGE_SECTION = SectionDef(
    header_kind=None,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.POST_FX_LOCKED),
    ),
)

POST_FX_SECTION = SectionDef(
    header_kind=RowKind.POST_FX_HEADER,
    context="global",
    children=(
        SectionNode(subsection=POST_FX_FADE_SECTION),
        SectionNode(subsection=POST_FX_HIGHLIGHT_ROLLOFF_SECTION),
        SectionNode(subsection=POST_FX_CHROMA_BOOST_SECTION),
        SectionNode(subsection=POST_FX_LIMITER_SECTION),
    ),
)

PATTERN_MASK_PLASMA_SEED = ConditionalRowsDef(
    name="pattern_mask_plasma_seed",
    predicate=lambda state, _desc: state.pattern_mask.type == "plasma",
    children=(
        SectionNode(leaf_kind=RowKind.PATTERN_MASK_SEED),
    ),
)

PATTERN_MASK_PATTERN_SECTION = SectionDef(
    header_kind=RowKind.PATTERN_MASK_PATTERN_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.PATTERN_MASK_TYPE),
        SectionNode(leaf_kind=RowKind.PATTERN_MASK_DENSITY),
        SectionNode(leaf_kind=RowKind.PATTERN_MASK_INVERT),
        SectionNode(conditional=PATTERN_MASK_PLASMA_SEED),
    ),
)

PATTERN_MASK_EDGES_SECTION = SectionDef(
    header_kind=RowKind.PATTERN_MASK_EDGES_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.PATTERN_MASK_FEATHER),
        SectionNode(leaf_kind=RowKind.PATTERN_MASK_TRANSITION_UNIT),
        SectionNode(leaf_kind=RowKind.PATTERN_MASK_TRANSITION),
    ),
)

PATTERN_MASK_PAGE_SECTION = SectionDef(
    header_kind=None,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.PATTERN_MASK_ENABLED),
        SectionNode(leaf_kind=RowKind.PATTERN_MASK_LOCKED),
    ),
)

PATTERN_MASK_SECTION = SectionDef(
    header_kind=RowKind.PATTERN_MASK_HEADER,
    context="global",
    children=(
        SectionNode(subsection=PATTERN_MASK_PATTERN_SECTION),
        SectionNode(subsection=PATTERN_MASK_EDGES_SECTION),
    ),
)

def _preset_switching_paused(
    state: TuningViewState, desc: RowDescriptor
) -> bool:
    if desc.slot is None:
        return False
    return state.tracks[desc.slot].runtime.switching_paused


def _preset_switching_active(
    state: TuningViewState, desc: RowDescriptor
) -> bool:
    if desc.slot is None:
        return False
    return state.tracks[desc.slot].runtime.preset_switching_trigger != "off"


def _preset_switching_projectm_trigger(
    state: TuningViewState, desc: RowDescriptor
) -> bool:
    if desc.slot is None:
        return False
    return state.tracks[desc.slot].runtime.preset_switching_trigger == "projectm"


def _preset_switching_uses_duration(
    state: TuningViewState, desc: RowDescriptor
) -> bool:
    if desc.slot is None:
        return False
    return state.tracks[desc.slot].runtime.preset_switching_trigger not in (
        "off",
        "timeline",
    )


def _hard_cut_enabled(state: TuningViewState, desc: RowDescriptor) -> bool:
    if desc.slot is None:
        return False
    return state.tracks[desc.slot].runtime.hard_cut_enabled


HARD_CUT_ENABLED = ConditionalRowsDef(
    name="hard_cut_enabled",
    predicate=_hard_cut_enabled,
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_HARD_CUT_DURATION),
        SectionNode(leaf_kind=RowKind.TRACK_HARD_CUT_SENSITIVITY),
    ),
)

TRACK_PRESET_LIST_SECTION = SectionDef(
    header_kind=RowKind.TRACK_PRESET_LIST,
    context="per_slot",
    # The layer's preset directory, as on the Milkdrop Preset page: the
    # folder Populate list fills the list from.
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_PRESET_DIR),
        SectionNode(divider=True),
    ),
    append_dynamic_children=_append_preset_list_rows,
    title_command="layers.populate_presets",
)

PRESET_SWITCHING_USES_DURATION = ConditionalRowsDef(
    name="preset_switching_uses_duration",
    predicate=_preset_switching_uses_duration,
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_PRESET_DURATION),
    ),
)

PRESET_SWITCHING_PROJECTM_TRIGGER = ConditionalRowsDef(
    name="preset_switching_projectm_trigger",
    predicate=_preset_switching_projectm_trigger,
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_EASTER_EGG),
        SectionNode(leaf_kind=RowKind.TRACK_SOFT_CUT_DURATION),
        SectionNode(divider=True),
        SectionNode(leaf_kind=RowKind.TRACK_HARD_CUT_ENABLED),
        SectionNode(conditional=HARD_CUT_ENABLED),
    ),
)

PRESET_SWITCHING_PAUSED = ConditionalRowsDef(
    name="preset_switching_paused",
    predicate=_preset_switching_paused,
    children=(
        SectionNode(
            commands=("layers.resume_switching",),
            status="Previewing presets",
        ),
    ),
)

PRESET_SWITCHING_ACTIVE = ConditionalRowsDef(
    name="preset_switching_active",
    predicate=_preset_switching_active,
    children=(
        SectionNode(conditional=PRESET_SWITCHING_USES_DURATION),
        SectionNode(conditional=PRESET_SWITCHING_PROJECTM_TRIGGER),
        SectionNode(divider=True),
        SectionNode(leaf_kind=RowKind.TRACK_PRESET_START_CLEAN),
    ),
)

TRACK_MILKDROP_PRESET_SECTION = SectionDef(
    header_kind=RowKind.TRACK_MILKDROP_PRESET_HEADER,
    context="per_slot",
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_PRESET_DIR),
        SectionNode(leaf_kind=RowKind.TRACK_PRESET),
        SectionNode(divider=True),
        SectionNode(leaf_kind=RowKind.TRACK_BEAT),
        SectionNode(conditional=PRESET_SWITCHING_PAUSED),
    ),
    title_command="layers.go_to_preset_list",
    title_command_when=_preset_switching_active,
)

TRACK_PRESET_SWITCHING_SECTION = SectionDef(
    header_kind=RowKind.TRACK_PRESET_SWITCHING,
    context="per_slot",
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_PRESET_SWITCHING_TRIGGER),
        SectionNode(conditional=PRESET_SWITCHING_ACTIVE),
    ),
    title_command="layers.go_to_preset_list",
    title_command_when=_preset_switching_active,
)

TRACK_EFFECTS_SECTION = SectionDef(
    header_kind=RowKind.TRACK_EFFECTS_HEADER,
    context="per_slot",
    children=(),
    append_dynamic_children=_append_track_effect_rows,
)

TRACK_COMPOSITING_SECTION = SectionDef(
    header_kind=RowKind.TRACK_COMPOSITING_HEADER,
    context="per_slot",
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_BLEND),
        SectionNode(leaf_kind=RowKind.TRACK_OPACITY),
    ),
)

TRACK_SECTION = SectionDef(
    header_kind=RowKind.TRACK_HEADER,
    context="per_slot",
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_ENABLED),
        SectionNode(leaf_kind=RowKind.TRACK_SOLO),
        SectionNode(leaf_kind=RowKind.TRACK_LOCKED),
        SectionNode(leaf_kind=RowKind.TRACK_STEM),
        SectionNode(commands=("layers.delete",)),
    ),
)

def _timeline_clip_selected(state: TuningViewState, desc: RowDescriptor) -> bool:
    return desc.slot is not None and desc.slot in state.timeline.selected_clips


def _timeline_clip_holds_preset(state: TuningViewState, desc: RowDescriptor) -> bool:
    return desc.slot is not None and desc.slot in state.timeline.selected_clip_presets


# Rows for the selected clip's preset, on a layer whose presets change on
# each clip. Starts stays listed and draws disabled on a clip after a gap.
TIMELINE_CLIP_PRESET_ROWS = ConditionalRowsDef(
    name="timeline_clip_holds_preset",
    predicate=_timeline_clip_holds_preset,
    children=(
        SectionNode(leaf_kind=RowKind.TIMELINE_CLIP_PRESET),
        SectionNode(leaf_kind=RowKind.TIMELINE_CLIP_STARTS),
    ),
)

TIMELINE_CLIP_SELECTED = ConditionalRowsDef(
    name="timeline_clip_selected",
    predicate=_timeline_clip_selected,
    children=(
        SectionNode(conditional=TIMELINE_CLIP_PRESET_ROWS),
        SectionNode(leaf_kind=RowKind.TIMELINE_CLIP_START),
        SectionNode(leaf_kind=RowKind.TIMELINE_CLIP_END),
        SectionNode(leaf_kind=RowKind.TIMELINE_CLIP_OPACITY),
        SectionNode(leaf_kind=RowKind.TIMELINE_CLIP_BLEND),
        SectionNode(leaf_kind=RowKind.TIMELINE_CLIP_ROLE),
        SectionNode(leaf_kind=RowKind.TIMELINE_CLIP_CUT_IN),
        SectionNode(leaf_kind=RowKind.TIMELINE_CLIP_CUT_OUT),
    ),
)

# The heading names the selected clip's span, or says none is selected. Cut
# out stays listed and draws disabled on a clip with no end cue of its own.
TIMELINE_CLIP_SECTION = SectionDef(
    header_kind=RowKind.TIMELINE_CLIP_HEADER,
    context="per_slot",
    children=(SectionNode(conditional=TIMELINE_CLIP_SELECTED),),
)

# Page of one timeline strip row, shown while that row is selected.
TIMELINE_ROW_SECTION = SectionDef(
    header_kind=None,
    context="per_slot",
    children=(SectionNode(subsection=TIMELINE_CLIP_SECTION),),
)

SONG_MARKERS_SECTION = SectionDef(
    header_kind=RowKind.SONG_MARKERS_HEADER,
    context="global",
    children=(),
    append_dynamic_children=_append_song_marker_rows,
    title_command="timeline.snap_to_markers",
)

BEAT_BAR_GRID_SECTION = SectionDef(
    header_kind=RowKind.TIMELINE_BEAT_BAR_GRID_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.TIMELINE_PLACEMENT_SNAP),
        SectionNode(leaf_kind=RowKind.TIMELINE_BAR_GRID),
        SectionNode(leaf_kind=RowKind.TIMELINE_BAR_PHASE),
        SectionNode(commands=("timeline.snap_cues", "timeline.snap_song_markers")),
    ),
)


def _timeline_hard_cut_fades_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> bool:
    return state.timeline.hard_cut_fades.enabled


def _timeline_soft_cut_fades_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> bool:
    return state.timeline.soft_cut_fades.enabled


TIMELINE_HARD_CUTS_ACTIVE = ConditionalRowsDef(
    name="timeline_hard_cut_fades_enabled",
    predicate=_timeline_hard_cut_fades_enabled,
    children=(
        SectionNode(leaf_kind=RowKind.TIMELINE_HARD_CUT_FADE_IN),
        SectionNode(leaf_kind=RowKind.TIMELINE_HARD_CUT_FADE_OUT),
        SectionNode(leaf_kind=RowKind.TIMELINE_HARD_CUT_CROSSFADE),
    ),
)

TIMELINE_SOFT_CUTS_ACTIVE = ConditionalRowsDef(
    name="timeline_soft_cut_fades_enabled",
    predicate=_timeline_soft_cut_fades_enabled,
    children=(
        SectionNode(leaf_kind=RowKind.TIMELINE_SOFT_CUT_FADE_IN),
        SectionNode(leaf_kind=RowKind.TIMELINE_SOFT_CUT_FADE_OUT),
        SectionNode(leaf_kind=RowKind.TIMELINE_SOFT_CUT_CROSSFADE),
    ),
)

TIMELINE_CUTS_SECTION = SectionDef(
    header_kind=RowKind.TIMELINE_CUTS_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.TIMELINE_HARD_CUTS),
        SectionNode(conditional=TIMELINE_HARD_CUTS_ACTIVE),
        SectionNode(divider=True),
        SectionNode(leaf_kind=RowKind.TIMELINE_SOFT_CUTS),
        SectionNode(conditional=TIMELINE_SOFT_CUTS_ACTIVE),
        SectionNode(divider=True),
        SectionNode(leaf_kind=RowKind.TIMELINE_GLIDE),
        SectionNode(commands=("timeline.set_cut_type",)),
    ),
)

def leaf_kinds_in_section(section: SectionDef) -> frozenset[RowKind]:
    kinds: set[RowKind] = set()
    for child in section.children:
        if child.leaf_kind is not None:
            kinds.add(child.leaf_kind)
        if child.subsection is not None:
            kinds |= leaf_kinds_in_section(child.subsection)
        if child.conditional is not None:
            kinds |= _leaf_kinds_in_nodes(child.conditional.children)
    return frozenset(kinds)


def _leaf_kinds_in_nodes(nodes: tuple[SectionNode, ...]) -> frozenset[RowKind]:
    kinds: set[RowKind] = set()
    for child in nodes:
        if child.leaf_kind is not None:
            kinds.add(child.leaf_kind)
        if child.subsection is not None:
            kinds |= leaf_kinds_in_section(child.subsection)
        if child.conditional is not None:
            kinds |= _leaf_kinds_in_nodes(child.conditional.children)
    return frozenset(kinds)


def kinds_in_section(section: SectionDef) -> frozenset[RowKind]:
    kinds: set[RowKind] = set()
    if section.header_kind is not None:
        kinds.add(section.header_kind)
    for child in section.children:
        if child.leaf_kind is not None:
            kinds.add(child.leaf_kind)
        if child.subsection is not None:
            kinds |= kinds_in_section(child.subsection)
        if child.conditional is not None:
            kinds |= _leaf_kinds_in_nodes(child.conditional.children)
    return frozenset(kinds)


TIMELINE_PAGE_SECTION = SectionDef(
    header_kind=None,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.TIMELINE_ENABLED),
        SectionNode(leaf_kind=RowKind.TIMELINE_LOCKED),
        SectionNode(leaf_kind=RowKind.TIMELINE_PRESET_NAMES),
        SectionNode(commands=("timeline.generate", "timeline.reset")),
    ),
)

OVERLAY_SECTION_KINDS = kinds_in_section(OVERLAYS_SECTION) | kinds_in_section(
    OVERLAY_PAGE_SECTION
)
POST_FX_SECTION_KINDS = kinds_in_section(POST_FX_SECTION) | kinds_in_section(
    POST_FX_PAGE_SECTION
)
POST_FX_FADE_KINDS = kinds_in_section(POST_FX_FADE_SECTION)
PATTERN_MASK_SECTION_KINDS = kinds_in_section(
    PATTERN_MASK_SECTION
) | kinds_in_section(PATTERN_MASK_PAGE_SECTION)
TRACK_COMPOSITING_SECTION_KINDS = kinds_in_section(TRACK_COMPOSITING_SECTION)
TIMELINE_SECTION_KINDS = frozenset(
    {
        RowKind.TIMELINE_HEADER,
        RowKind.TIMELINE_ENABLED,
        RowKind.TIMELINE_LOCKED,
        RowKind.TIMELINE_PRESET_NAMES,
        RowKind.SONG_MARKERS_HEADER,
        RowKind.SONG_MARKER_ITEM,
        RowKind.TIMELINE_GENERATE,
        RowKind.TIMELINE_RESET,
        RowKind.TIMELINE_BEAT_BAR_GRID_HEADER,
        RowKind.TIMELINE_PLACEMENT_SNAP,
        RowKind.TIMELINE_BAR_GRID,
        RowKind.TIMELINE_BAR_PHASE,
        RowKind.TIMELINE_SNAP_CUES,
        RowKind.TIMELINE_SNAP_SONG_MARKERS,
        RowKind.TIMELINE_CUTS_HEADER,
        RowKind.TIMELINE_HARD_CUTS,
        RowKind.TIMELINE_HARD_CUT_FADE_IN,
        RowKind.TIMELINE_HARD_CUT_FADE_OUT,
        RowKind.TIMELINE_HARD_CUT_CROSSFADE,
        RowKind.TIMELINE_SOFT_CUTS,
        RowKind.TIMELINE_SOFT_CUT_FADE_IN,
        RowKind.TIMELINE_SOFT_CUT_FADE_OUT,
        RowKind.TIMELINE_SOFT_CUT_CROSSFADE,
        RowKind.TIMELINE_GLIDE,
        RowKind.TIMELINE_SET_CUT_TYPE,
        RowKind.TIMELINE_CLIP_HEADER,
        RowKind.TIMELINE_CLIP_START,
        RowKind.TIMELINE_CLIP_END,
        RowKind.TIMELINE_CLIP_OPACITY,
        RowKind.TIMELINE_CLIP_BLEND,
        RowKind.TIMELINE_CLIP_ROLE,
        RowKind.TIMELINE_CLIP_CUT_IN,
        RowKind.TIMELINE_CLIP_CUT_OUT,
        RowKind.TIMELINE_CLIP_PRESET,
        RowKind.TIMELINE_CLIP_STARTS,
    }
)

# On/off, solo, and lock rows of a root or layer page, and each card's on/off
# row. They stay readable while their block is off, since they turn it back on.
SECTION_SWITCH_KINDS = frozenset(
    {
        RowKind.TRACK_ENABLED,
        RowKind.TRACK_SOLO,
        RowKind.TRACK_LOCKED,
        RowKind.OVERLAYS_PREVIEW,
        RowKind.OVERLAYS_LOCKED,
        RowKind.OVERLAY_CARD_ENABLED,
        RowKind.POST_FX_LOCKED,
        RowKind.PATTERN_MASK_ENABLED,
        RowKind.PATTERN_MASK_LOCKED,
        RowKind.TIMELINE_ENABLED,
        RowKind.TIMELINE_LOCKED,
    }
)
