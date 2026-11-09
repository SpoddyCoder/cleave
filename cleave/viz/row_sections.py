"""Section composition for inspector pages."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from cleave.effects.registry import effect_roster
from cleave.timeline import cue_editable_for_blend_role
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
    """Tree node: leaf row, headed subsection, conditional group, or buttons.

    ``commands`` is one row of buttons, as ids in the command registry.
    ``status`` is a line of text at the start of that row.
    """

    leaf_kind: RowKind | None = None
    subsection: SectionDef | None = None
    conditional: ConditionalRowsDef | None = None
    commands: tuple[str, ...] | None = None
    status: str | None = None

    def __post_init__(self) -> None:
        set_count = sum(
            x is not None
            for x in (self.leaf_kind, self.subsection, self.conditional, self.commands)
        )
        if set_count != 1:
            raise ValueError("SectionNode requires exactly one child type")


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
    trailing_commands: tuple[str, ...] = ()


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
        SectionNode(leaf_kind=RowKind.SETTINGS_RESIDUAL_LATENCY_MS),
        SectionNode(commands=("settings.measure_latency",)),
    ),
)

SETTINGS_UI_SECTION = SectionDef(
    header_kind=RowKind.SETTINGS_UI_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.SETTINGS_UI_SCALE),
        SectionNode(leaf_kind=RowKind.SETTINGS_UI_NOTIFICATION_DISPLAY),
        SectionNode(leaf_kind=RowKind.SETTINGS_UI_NAVIGATOR_HEIGHT),
        SectionNode(leaf_kind=RowKind.SETTINGS_NAVIGATOR_SIDE),
        SectionNode(leaf_kind=RowKind.SETTINGS_HELP_SIDE),
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

PROJECT_RENDER_SECTION = SectionDef(
    header_kind=RowKind.PROJECT_RENDER_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.PROJECT_RENDER_OUTPUT),
        SectionNode(leaf_kind=RowKind.PROJECT_RENDER_FPS),
        SectionNode(leaf_kind=RowKind.PROJECT_RENDER_QUALITY),
        SectionNode(leaf_kind=RowKind.PROJECT_RENDER_START),
        SectionNode(leaf_kind=RowKind.PROJECT_RENDER_END),
        SectionNode(commands=("project.render",)),
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
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_POSITION),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_OPACITY),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_BACKGROUND_COLOUR),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_BACKGROUND_MARGIN),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_BACKGROUND_PADDING),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_BORDER_WIDTH),
            SectionNode(leaf_kind=RowKind.OVERLAY_CARD_BORDER_COLOUR),
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
        SectionNode(leaf_kind=RowKind.OVERLAYS_ENABLED),
        SectionNode(leaf_kind=RowKind.OVERLAYS_SOLO),
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
    predicate=lambda state, _desc: state.post_fx.highlight_rolloff.mode != "off",
    children=(
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
        SectionNode(leaf_kind=RowKind.POST_FX_HIGHLIGHT_ROLLOFF_MODE),
        SectionNode(conditional=POST_FX_HIGHLIGHT_ROLLOFF_ACTIVE),
    ),
)

POST_FX_CHROMA_BOOST_ACTIVE = ConditionalRowsDef(
    name="chroma_boost_active",
    predicate=lambda state, _desc: state.post_fx.chroma_boost.mode != "off",
    children=(
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
        SectionNode(leaf_kind=RowKind.POST_FX_CHROMA_BOOST_MODE),
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
        SectionNode(subsection=POST_FX_FADE_IN_SECTION),
        SectionNode(subsection=POST_FX_FADE_OUT_SECTION),
    ),
)

POST_FX_PAGE_SECTION = SectionDef(
    header_kind=None,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.POST_FX_ENABLED),
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
    children=(),
    append_dynamic_children=_append_preset_list_rows,
    trailing_commands=("layers.populate_presets",),
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
            status="Switching paused",
        ),
    ),
)

PRESET_SWITCHING_ACTIVE = ConditionalRowsDef(
    name="preset_switching_active",
    predicate=_preset_switching_active,
    children=(
        SectionNode(conditional=PRESET_SWITCHING_USES_DURATION),
        SectionNode(conditional=PRESET_SWITCHING_PROJECTM_TRIGGER),
        SectionNode(leaf_kind=RowKind.TRACK_PRESET_START_CLEAN),
    ),
)

PRESET_SWITCHING_ADD_TO_LIST = ConditionalRowsDef(
    name="preset_switching_add_to_list",
    predicate=_preset_switching_active,
    children=(
        SectionNode(commands=("layers.add_current_preset",)),
    ),
)

TRACK_MILKDROP_PRESET_SECTION = SectionDef(
    header_kind=RowKind.TRACK_MILKDROP_PRESET_HEADER,
    context="per_slot",
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_PRESET_DIR),
        SectionNode(leaf_kind=RowKind.TRACK_PRESET),
        SectionNode(leaf_kind=RowKind.TRACK_BEAT),
        SectionNode(conditional=PRESET_SWITCHING_ADD_TO_LIST),
        SectionNode(conditional=PRESET_SWITCHING_PAUSED),
    ),
)

TRACK_PRESET_SWITCHING_SECTION = SectionDef(
    header_kind=RowKind.TRACK_PRESET_SWITCHING,
    context="per_slot",
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_PRESET_SWITCHING_TRIGGER),
        SectionNode(conditional=PRESET_SWITCHING_ACTIVE),
    ),
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

def _timeline_cue_selected(state: TuningViewState, desc: RowDescriptor) -> bool:
    return desc.slot is not None and desc.slot in state.timeline.selected_cues


def _timeline_start_cue_selected(
    state: TuningViewState, desc: RowDescriptor
) -> bool:
    if desc.slot is None:
        return False
    cue = state.timeline.selected_cues.get(desc.slot)
    return cue is not None and cue_editable_for_blend_role(cue)


TIMELINE_CUE_SELECTED = ConditionalRowsDef(
    name="timeline_cue_selected",
    predicate=_timeline_cue_selected,
    children=(SectionNode(leaf_kind=RowKind.TIMELINE_CUE_TIME),),
)

TIMELINE_START_CUE_LEVEL = ConditionalRowsDef(
    name="timeline_start_cue_selected",
    predicate=_timeline_start_cue_selected,
    children=(SectionNode(leaf_kind=RowKind.TIMELINE_CUE_OPACITY),),
)

TIMELINE_CUE_CUT = ConditionalRowsDef(
    name="timeline_cue_selected",
    predicate=_timeline_cue_selected,
    children=(SectionNode(leaf_kind=RowKind.TIMELINE_CUE_CUT),),
)

TIMELINE_START_CUE_LOOK = ConditionalRowsDef(
    name="timeline_start_cue_selected",
    predicate=_timeline_start_cue_selected,
    children=(
        SectionNode(leaf_kind=RowKind.TIMELINE_CUE_BLEND),
        SectionNode(leaf_kind=RowKind.TIMELINE_CUE_ROLE),
    ),
)

# The heading names the cue (start, end, or none selected). An end cue only
# turns the layer off, so it has no opacity, blend, or role.
TIMELINE_CUE_SECTION = SectionDef(
    header_kind=RowKind.TIMELINE_CUE_HEADER,
    context="per_slot",
    children=(
        SectionNode(conditional=TIMELINE_CUE_SELECTED),
        SectionNode(conditional=TIMELINE_START_CUE_LEVEL),
        SectionNode(conditional=TIMELINE_CUE_CUT),
        SectionNode(conditional=TIMELINE_START_CUE_LOOK),
    ),
)

# Page of one timeline strip row, shown while that row is selected.
TIMELINE_ROW_SECTION = SectionDef(
    header_kind=None,
    context="per_slot",
    children=(SectionNode(subsection=TIMELINE_CUE_SECTION),),
)

SONG_MARKERS_SECTION = SectionDef(
    header_kind=RowKind.SONG_MARKERS_HEADER,
    context="global",
    children=(
        SectionNode(commands=("timeline.snap_to_markers",)),
    ),
    append_dynamic_children=_append_song_marker_rows,
)

BEAT_BAR_GRID_SECTION = SectionDef(
    header_kind=RowKind.TIMELINE_BEAT_BAR_GRID_HEADER,
    context="global",
    children=(
        SectionNode(leaf_kind=RowKind.TIMELINE_PLACEMENT_SNAP),
        SectionNode(leaf_kind=RowKind.TIMELINE_BAR_GRID),
        SectionNode(leaf_kind=RowKind.TIMELINE_BAR_PHASE),
        SectionNode(commands=("timeline.snap_cues",)),
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
        SectionNode(leaf_kind=RowKind.TIMELINE_SOFT_CUTS),
        SectionNode(conditional=TIMELINE_SOFT_CUTS_ACTIVE),
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
        SectionNode(commands=("timeline.generate", "timeline.reset")),
    ),
)

OVERLAY_SECTION_KINDS = kinds_in_section(OVERLAYS_SECTION) | kinds_in_section(
    OVERLAY_PAGE_SECTION
)
POST_FX_SECTION_KINDS = kinds_in_section(POST_FX_SECTION) | kinds_in_section(
    POST_FX_PAGE_SECTION
)
POST_FX_LIMITER_KINDS = kinds_in_section(POST_FX_LIMITER_SECTION)
PATTERN_MASK_SECTION_KINDS = kinds_in_section(
    PATTERN_MASK_SECTION
) | kinds_in_section(PATTERN_MASK_PAGE_SECTION)
TRACK_COMPOSITING_SECTION_KINDS = kinds_in_section(TRACK_COMPOSITING_SECTION)
TIMELINE_SECTION_KINDS = frozenset(
    {
        RowKind.TIMELINE_HEADER,
        RowKind.TIMELINE_ENABLED,
        RowKind.TIMELINE_LOCKED,
        RowKind.SONG_MARKERS_HEADER,
        RowKind.SONG_MARKER_ITEM,
        RowKind.TIMELINE_GENERATE,
        RowKind.TIMELINE_RESET,
        RowKind.TIMELINE_BEAT_BAR_GRID_HEADER,
        RowKind.TIMELINE_PLACEMENT_SNAP,
        RowKind.TIMELINE_BAR_GRID,
        RowKind.TIMELINE_BAR_PHASE,
        RowKind.TIMELINE_SNAP_CUES,
        RowKind.TIMELINE_CUTS_HEADER,
        RowKind.TIMELINE_HARD_CUTS,
        RowKind.TIMELINE_HARD_CUT_FADE_IN,
        RowKind.TIMELINE_HARD_CUT_FADE_OUT,
        RowKind.TIMELINE_HARD_CUT_CROSSFADE,
        RowKind.TIMELINE_SOFT_CUTS,
        RowKind.TIMELINE_SOFT_CUT_FADE_IN,
        RowKind.TIMELINE_SOFT_CUT_FADE_OUT,
        RowKind.TIMELINE_SOFT_CUT_CROSSFADE,
        RowKind.TIMELINE_SET_CUT_TYPE,
        RowKind.TIMELINE_CUE_HEADER,
        RowKind.TIMELINE_CUE_TIME,
        RowKind.TIMELINE_CUE_OPACITY,
        RowKind.TIMELINE_CUE_CUT,
        RowKind.TIMELINE_CUE_BLEND,
        RowKind.TIMELINE_CUE_ROLE,
    }
)

# On/off, solo, and lock rows of a root or layer page, and each card's on/off
# row. They stay readable while their block is off, since they turn it back on.
SECTION_SWITCH_KINDS = frozenset(
    {
        RowKind.TRACK_ENABLED,
        RowKind.TRACK_SOLO,
        RowKind.TRACK_LOCKED,
        RowKind.OVERLAYS_ENABLED,
        RowKind.OVERLAYS_SOLO,
        RowKind.OVERLAYS_LOCKED,
        RowKind.OVERLAY_CARD_ENABLED,
        RowKind.POST_FX_ENABLED,
        RowKind.POST_FX_LOCKED,
        RowKind.PATTERN_MASK_ENABLED,
        RowKind.PATTERN_MASK_LOCKED,
        RowKind.TIMELINE_ENABLED,
        RowKind.TIMELINE_LOCKED,
    }
)
