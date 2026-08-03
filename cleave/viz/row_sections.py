"""Expandable section composition for the live tuning panel."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from cleave.effects.registry import effect_roster
from cleave.viz.row_semantics import RowDescriptor, RowKind

if TYPE_CHECKING:
    from cleave.viz.controls import TuningControls
    from cleave.viz.tuning_view_state import TuningViewState


def expand_arrow_glyph(expanded: bool) -> str:
    return "▼" if expanded else "▶"


ExpandToggleFn = Callable[["TuningControls", str | None, bool], None]
AppendDynamicChildrenFn = Callable[[list[RowDescriptor], "TuningViewState", str | None], None]
PanelAnchorToggleFn = Callable[["TuningControls", bool], None]


def _toggle_settings(controls: TuningControls, _slot: str | None, forward: bool) -> None:
    controls._settings.set_expanded(forward)


def _toggle_settings_ui(controls: TuningControls, _slot: str | None, forward: bool) -> None:
    controls._settings.set_ui_expanded(forward)


def _toggle_settings_latency_compensation(
    controls: TuningControls, _slot: str | None, forward: bool
) -> None:
    controls._settings.set_latency_compensation_expanded(forward)


def _toggle_render_overlays(
    controls: TuningControls, _slot: str | None, forward: bool
) -> None:
    controls._render_overlays.set_expanded(forward)


def _toggle_render_overlay_opening_card(
    controls: TuningControls, _slot: str | None, forward: bool
) -> None:
    controls._render_overlays.opening_card.set_expanded(forward)


def _toggle_render_overlay_closing_card(
    controls: TuningControls, _slot: str | None, forward: bool
) -> None:
    controls._render_overlays.closing_card.set_expanded(forward)


def _toggle_render_overlay_opening_title(
    controls: TuningControls, _slot: str | None, forward: bool
) -> None:
    controls._render_overlays.opening_card.set_title_expanded(forward)


def _toggle_render_overlay_closing_title(
    controls: TuningControls, _slot: str | None, forward: bool
) -> None:
    controls._render_overlays.closing_card.set_title_expanded(forward)


def _toggle_render_overlay_opening_body(
    controls: TuningControls, _slot: str | None, forward: bool
) -> None:
    controls._render_overlays.opening_card.set_body_expanded(forward)


def _toggle_render_overlay_closing_body(
    controls: TuningControls, _slot: str | None, forward: bool
) -> None:
    controls._render_overlays.closing_card.set_body_expanded(forward)


def _toggle_render_overlay_opening_animation(
    controls: TuningControls, _slot: str | None, forward: bool
) -> None:
    controls._render_overlays.opening_card.set_animation_expanded(forward)


def _toggle_render_overlay_closing_animation(
    controls: TuningControls, _slot: str | None, forward: bool
) -> None:
    controls._render_overlays.closing_card.set_animation_expanded(forward)


def _toggle_render_post_fx(controls: TuningControls, _slot: str | None, forward: bool) -> None:
    controls._render_post_fx.set_expanded(forward)


def _toggle_render_post_fx_highlight_rolloff(
    controls: TuningControls, _slot: str | None, forward: bool
) -> None:
    controls._render_post_fx.set_highlight_rolloff_expanded(forward)


def _toggle_render_post_fx_chroma_boost(
    controls: TuningControls, _slot: str | None, forward: bool
) -> None:
    controls._render_post_fx.set_chroma_boost_expanded(forward)


def _toggle_track_header(controls: TuningControls, slot: str | None, forward: bool) -> None:
    if slot is None:
        return
    controls._set_expanded(slot, forward)


def _toggle_preset_switching(controls: TuningControls, slot: str | None, forward: bool) -> None:
    if slot is None:
        return
    controls._cycle_preset_switching(slot, forward=forward)


def _toggle_effects_header(controls: TuningControls, slot: str | None, forward: bool) -> None:
    if slot is None:
        return
    controls._set_effects_expanded(slot, forward)


def _toggle_preset_list(controls: TuningControls, slot: str | None, forward: bool) -> None:
    if slot is None:
        return
    controls._set_preset_list_expanded(slot, forward)


def _toggle_song_markers(controls: TuningControls, _slot: str | None, forward: bool) -> None:
    controls._set_song_markers_expanded(forward)


def _toggle_beat_bar_grid(controls: TuningControls, _slot: str | None, forward: bool) -> None:
    controls._set_beat_bar_grid_expanded(forward)


def _beat_bar_grid_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.render_timeline.beat_bar_grid_expanded


def _toggle_snap_cues(controls: TuningControls, _slot: str | None, forward: bool) -> None:
    controls._set_snap_cues_expanded(forward)


def _snap_cues_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.render_timeline.snap_cues_expanded


def _toggle_timeline_cuts(controls: TuningControls, _slot: str | None, forward: bool) -> None:
    controls._set_timeline_cuts_expanded(forward)


def _timeline_cuts_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.render_timeline.cuts_expanded


def _toggle_timeline_presets(controls: TuningControls, _slot: str | None, forward: bool) -> None:
    controls._set_timeline_presets_expanded(forward)


def _timeline_presets_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.render_timeline.timeline_presets_expanded


def _toggle_visual_limiter(
    controls: TuningControls, _slot: str | None, forward: bool
) -> None:
    controls._set_visual_limiter_enabled(forward)


def _visual_limiter_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.render_timeline.limiter.enabled


def _open_timeline_panel(controls: TuningControls, forward: bool) -> None:
    if forward:
        controls._open_timeline_panel()
    else:
        controls.close_timeline_panel()


def apply_panel_anchor_toggle(
    controls: TuningControls,
    header_kind: RowKind,
    forward: bool,
) -> bool:
    handler = PANEL_ANCHOR_TOGGLE_BY_HEADER.get(header_kind)
    if handler is None:
        return False
    handler(controls, forward)
    return True


PredicateFn = Callable[["TuningViewState", RowDescriptor], bool]


@dataclass(frozen=True)
class ConditionalRowsDef:
    """Value-gated rows (no expand arrow or expanded flag).

    By default children share the parent's tree depth (siblings of the gating
    control). Set ``child_indent_offset`` to nest them visually under that
    control (e.g. seed under shuffle).
    """

    name: str
    predicate: PredicateFn
    children: tuple["SectionNode", ...]
    child_indent_offset: int = 0


@dataclass(frozen=True)
class PanelAnchorDef:
    """Header row whose content lives in a separate panel host."""

    header_kind: RowKind
    content_host: Literal["timeline_strip"]
    toggle: PanelAnchorToggleFn


@dataclass(frozen=True)
class SectionNode:
    """Tree node: leaf row, expandable section, conditional group, or panel anchor."""

    leaf_kind: RowKind | None = None
    expand: ExpandSectionDef | None = None
    conditional: ConditionalRowsDef | None = None
    panel_anchor: PanelAnchorDef | None = None

    def __post_init__(self) -> None:
        set_count = sum(
            x is not None
            for x in (self.leaf_kind, self.expand, self.conditional, self.panel_anchor)
        )
        if set_count != 1:
            raise ValueError("SectionNode requires exactly one child type")


@dataclass(frozen=True)
class ExpandSectionDef:
    header_kind: RowKind
    context: Literal["global", "per_slot"]
    read_expanded: Callable[["TuningViewState", str | None], bool]
    toggle: ExpandToggleFn
    children: tuple[SectionNode, ...] = ()
    append_dynamic_children: AppendDynamicChildrenFn | None = None


TIMELINE_PANEL_ANCHOR = PanelAnchorDef(
    header_kind=RowKind.RENDER_TIMELINE_HEADER,
    content_host="timeline_strip",
    toggle=_open_timeline_panel,
)

PANEL_ANCHORS: tuple[PanelAnchorDef, ...] = (TIMELINE_PANEL_ANCHOR,)

PANEL_ANCHOR_BY_HEADER: dict[RowKind, PanelAnchorDef] = {
    anchor.header_kind: anchor for anchor in PANEL_ANCHORS
}

PANEL_ANCHOR_TOGGLE_BY_HEADER: dict[RowKind, PanelAnchorToggleFn] = {
    anchor.header_kind: anchor.toggle for anchor in PANEL_ANCHORS
}

PANEL_ANCHOR_HEADER_KINDS = frozenset(PANEL_ANCHOR_BY_HEADER)


def _settings_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.settings.expanded


def _settings_ui_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.settings.ui_expanded


def _settings_latency_compensation_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.settings.latency_compensation_expanded


def _render_overlays_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.render_overlays.expanded


def _render_overlay_opening_card_expanded(
    state: TuningViewState, _slot: str | None
) -> bool:
    return state.render_overlays.opening_card.expanded


def _render_overlay_closing_card_expanded(
    state: TuningViewState, _slot: str | None
) -> bool:
    return state.render_overlays.closing_card.expanded


def _render_overlay_opening_title_expanded(
    state: TuningViewState, _slot: str | None
) -> bool:
    return state.render_overlays.opening_card.title_expanded


def _render_overlay_closing_title_expanded(
    state: TuningViewState, _slot: str | None
) -> bool:
    return state.render_overlays.closing_card.title_expanded


def _render_overlay_opening_body_expanded(
    state: TuningViewState, _slot: str | None
) -> bool:
    return state.render_overlays.opening_card.body_expanded


def _render_overlay_closing_body_expanded(
    state: TuningViewState, _slot: str | None
) -> bool:
    return state.render_overlays.closing_card.body_expanded


def _render_overlay_opening_animation_expanded(
    state: TuningViewState, _slot: str | None
) -> bool:
    return state.render_overlays.opening_card.animation.expanded


def _render_overlay_closing_animation_expanded(
    state: TuningViewState, _slot: str | None
) -> bool:
    return state.render_overlays.closing_card.animation.expanded


def _render_post_fx_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.render_post_fx.expanded


def _render_post_fx_highlight_rolloff_expanded(
    state: TuningViewState, _slot: str | None
) -> bool:
    return state.render_post_fx.highlight_rolloff.expanded


def _render_post_fx_chroma_boost_expanded(
    state: TuningViewState, _slot: str | None
) -> bool:
    return state.render_post_fx.chroma_boost.expanded


def _track_header_expanded(state: TuningViewState, slot: str | None) -> bool:
    if slot is None:
        return True
    return state.tracks[slot].expanded


def _track_preset_switching_expanded(state: TuningViewState, slot: str | None) -> bool:
    if slot is None:
        return True
    return state.tracks[slot].preset_switching == "on"


def _track_effects_expanded(state: TuningViewState, slot: str | None) -> bool:
    if slot is None:
        return True
    return state.tracks[slot].effects_expanded


def _preset_list_expanded(state: TuningViewState, slot: str | None) -> bool:
    if slot is None:
        return True
    return state.tracks[slot].preset_list_expanded


def _song_markers_expanded(state: TuningViewState, _slot: str | None) -> bool:
    return state.render_timeline.song_markers_expanded


def _append_track_effect_rows(
    row_list: list[RowDescriptor],
    state: TuningViewState,
    slot: str | None,
) -> None:
    if slot is None:
        return
    block = state.tracks[slot]
    for effect_def in effect_roster(block.stem):
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
    for index, _path in enumerate(block.preset_list):
        row_list.append(
            RowDescriptor(
                RowKind.TRACK_PRESET_LIST_ITEM,
                slot=slot,
                preset_index=index,
            )
        )
    row_list.append(RowDescriptor(RowKind.TRACK_PRESET_LIST_ADD, slot=slot))
    row_list.append(RowDescriptor(RowKind.TRACK_PRESET_LIST_POPULATE, slot=slot))


def _append_song_marker_rows(
    row_list: list[RowDescriptor],
    state: TuningViewState,
    _slot: str | None,
) -> None:
    for index in range(len(state.render_timeline.song_marker_times)):
        row_list.append(
            RowDescriptor(RowKind.SONG_MARKER_ITEM, marker_index=index)
        )


SETTINGS_UI_SECTION = ExpandSectionDef(
    header_kind=RowKind.SETTINGS_UI_HEADER,
    context="global",
    read_expanded=_settings_ui_expanded,
    toggle=_toggle_settings_ui,
    children=(
        SectionNode(leaf_kind=RowKind.SETTINGS_UI_WIDTH_MODE),
        SectionNode(leaf_kind=RowKind.SETTINGS_UI_WIDTH),
        SectionNode(leaf_kind=RowKind.SETTINGS_UI_FADE),
    ),
)

SETTINGS_LATENCY_COMPENSATION_SECTION = ExpandSectionDef(
    header_kind=RowKind.SETTINGS_LATENCY_COMPENSATION_HEADER,
    context="global",
    read_expanded=_settings_latency_compensation_expanded,
    toggle=_toggle_settings_latency_compensation,
    children=(
        SectionNode(leaf_kind=RowKind.SETTINGS_RESIDUAL_LATENCY_MS),
        SectionNode(leaf_kind=RowKind.SETTINGS_MEASURE_LATENCY),
    ),
)

SETTINGS_SECTION = ExpandSectionDef(
    header_kind=RowKind.SETTINGS_HEADER,
    context="global",
    read_expanded=_settings_expanded,
    toggle=_toggle_settings,
    children=(
        SectionNode(leaf_kind=RowKind.SETTINGS_EDITOR_MODE),
        SectionNode(leaf_kind=RowKind.SETTINGS_PREVIEW_QUALITY),
        SectionNode(expand=SETTINGS_UI_SECTION),
        SectionNode(expand=SETTINGS_LATENCY_COMPENSATION_SECTION),
    ),
)

CURATION_LAYER_SECTION = ExpandSectionDef(
    header_kind=RowKind.TRACK_HEADER,
    context="per_slot",
    read_expanded=_track_header_expanded,
    toggle=_toggle_track_header,
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_STEM),
        SectionNode(leaf_kind=RowKind.TRACK_BEAT),
        SectionNode(leaf_kind=RowKind.TRACK_PRESET_DIR),
        SectionNode(leaf_kind=RowKind.TRACK_PRESET),
    ),
)

def _build_render_overlay_card_section(
    *,
    card_attr: Literal["opening_card", "closing_card"],
    card_header: RowKind,
    animation_header: RowKind,
    animation_type: RowKind,
    slide_direction: RowKind,
    timing_kind: RowKind,
    display_time: RowKind,
    position: RowKind,
    opacity: RowKind,
    border_width: RowKind,
    title_header: RowKind,
    title_font: RowKind,
    title_font_size: RowKind,
    title_margin_bottom: RowKind,
    body_header: RowKind,
    body_font: RowKind,
    body_font_size: RowKind,
    read_card_expanded: Callable[["TuningViewState", str | None], bool],
    toggle_card: ExpandToggleFn,
    read_title_expanded: Callable[["TuningViewState", str | None], bool],
    toggle_title: ExpandToggleFn,
    read_body_expanded: Callable[["TuningViewState", str | None], bool],
    toggle_body: ExpandToggleFn,
    read_animation_expanded: Callable[["TuningViewState", str | None], bool],
    toggle_animation: ExpandToggleFn,
) -> ExpandSectionDef:
    title_section = ExpandSectionDef(
        header_kind=title_header,
        context="global",
        read_expanded=read_title_expanded,
        toggle=toggle_title,
        children=(
            SectionNode(leaf_kind=title_font),
            SectionNode(leaf_kind=title_font_size),
            SectionNode(leaf_kind=title_margin_bottom),
        ),
    )
    body_section = ExpandSectionDef(
        header_kind=body_header,
        context="global",
        read_expanded=read_body_expanded,
        toggle=toggle_body,
        children=(
            SectionNode(leaf_kind=body_font),
            SectionNode(leaf_kind=body_font_size),
        ),
    )
    slide_conditional = ConditionalRowsDef(
        name=f"overlay_{card_attr}_animation_slide_direction",
        predicate=(
            lambda state, _desc, attr=card_attr: getattr(
                state.render_overlays, attr
            ).animation.type
            != "fade"
        ),
        children=(SectionNode(leaf_kind=slide_direction),),
    )
    animation_section = ExpandSectionDef(
        header_kind=animation_header,
        context="global",
        read_expanded=read_animation_expanded,
        toggle=toggle_animation,
        children=(
            SectionNode(leaf_kind=animation_type),
            SectionNode(conditional=slide_conditional),
            SectionNode(leaf_kind=timing_kind),
            SectionNode(leaf_kind=display_time),
        ),
    )
    return ExpandSectionDef(
        header_kind=card_header,
        context="global",
        read_expanded=read_card_expanded,
        toggle=toggle_card,
        children=(
            SectionNode(expand=animation_section),
            SectionNode(leaf_kind=position),
            SectionNode(leaf_kind=opacity),
            SectionNode(leaf_kind=border_width),
            SectionNode(expand=title_section),
            SectionNode(expand=body_section),
        ),
    )


RENDER_OVERLAY_OPENING_CARD_SECTION = _build_render_overlay_card_section(
    card_attr="opening_card",
    card_header=RowKind.RENDER_OVERLAY_OPENING_CARD_HEADER,
    animation_header=RowKind.RENDER_OVERLAY_OPENING_ANIMATION_HEADER,
    animation_type=RowKind.RENDER_OVERLAY_OPENING_ANIMATION_TYPE,
    slide_direction=RowKind.RENDER_OVERLAY_OPENING_ANIMATION_SLIDE_DIRECTION,
    timing_kind=RowKind.RENDER_OVERLAY_OPENING_APPEAR_AT,
    display_time=RowKind.RENDER_OVERLAY_OPENING_DISPLAY_TIME,
    position=RowKind.RENDER_OVERLAY_OPENING_POSITION,
    opacity=RowKind.RENDER_OVERLAY_OPENING_OPACITY,
    border_width=RowKind.RENDER_OVERLAY_OPENING_BORDER_WIDTH,
    title_header=RowKind.RENDER_OVERLAY_OPENING_TITLE_HEADER,
    title_font=RowKind.RENDER_OVERLAY_OPENING_TITLE_FONT,
    title_font_size=RowKind.RENDER_OVERLAY_OPENING_TITLE_FONT_SIZE,
    title_margin_bottom=RowKind.RENDER_OVERLAY_OPENING_TITLE_MARGIN_BOTTOM,
    body_header=RowKind.RENDER_OVERLAY_OPENING_BODY_HEADER,
    body_font=RowKind.RENDER_OVERLAY_OPENING_BODY_FONT,
    body_font_size=RowKind.RENDER_OVERLAY_OPENING_BODY_FONT_SIZE,
    read_card_expanded=_render_overlay_opening_card_expanded,
    toggle_card=_toggle_render_overlay_opening_card,
    read_title_expanded=_render_overlay_opening_title_expanded,
    toggle_title=_toggle_render_overlay_opening_title,
    read_body_expanded=_render_overlay_opening_body_expanded,
    toggle_body=_toggle_render_overlay_opening_body,
    read_animation_expanded=_render_overlay_opening_animation_expanded,
    toggle_animation=_toggle_render_overlay_opening_animation,
)

RENDER_OVERLAY_CLOSING_CARD_SECTION = _build_render_overlay_card_section(
    card_attr="closing_card",
    card_header=RowKind.RENDER_OVERLAY_CLOSING_CARD_HEADER,
    animation_header=RowKind.RENDER_OVERLAY_CLOSING_ANIMATION_HEADER,
    animation_type=RowKind.RENDER_OVERLAY_CLOSING_ANIMATION_TYPE,
    slide_direction=RowKind.RENDER_OVERLAY_CLOSING_ANIMATION_SLIDE_DIRECTION,
    timing_kind=RowKind.RENDER_OVERLAY_CLOSING_DISAPPEAR_AT,
    display_time=RowKind.RENDER_OVERLAY_CLOSING_DISPLAY_TIME,
    position=RowKind.RENDER_OVERLAY_CLOSING_POSITION,
    opacity=RowKind.RENDER_OVERLAY_CLOSING_OPACITY,
    border_width=RowKind.RENDER_OVERLAY_CLOSING_BORDER_WIDTH,
    title_header=RowKind.RENDER_OVERLAY_CLOSING_TITLE_HEADER,
    title_font=RowKind.RENDER_OVERLAY_CLOSING_TITLE_FONT,
    title_font_size=RowKind.RENDER_OVERLAY_CLOSING_TITLE_FONT_SIZE,
    title_margin_bottom=RowKind.RENDER_OVERLAY_CLOSING_TITLE_MARGIN_BOTTOM,
    body_header=RowKind.RENDER_OVERLAY_CLOSING_BODY_HEADER,
    body_font=RowKind.RENDER_OVERLAY_CLOSING_BODY_FONT,
    body_font_size=RowKind.RENDER_OVERLAY_CLOSING_BODY_FONT_SIZE,
    read_card_expanded=_render_overlay_closing_card_expanded,
    toggle_card=_toggle_render_overlay_closing_card,
    read_title_expanded=_render_overlay_closing_title_expanded,
    toggle_title=_toggle_render_overlay_closing_title,
    read_body_expanded=_render_overlay_closing_body_expanded,
    toggle_body=_toggle_render_overlay_closing_body,
    read_animation_expanded=_render_overlay_closing_animation_expanded,
    toggle_animation=_toggle_render_overlay_closing_animation,
)

RENDER_OVERLAYS_SECTION = ExpandSectionDef(
    header_kind=RowKind.RENDER_OVERLAYS_HEADER,
    context="global",
    read_expanded=_render_overlays_expanded,
    toggle=_toggle_render_overlays,
    children=(
        SectionNode(expand=RENDER_OVERLAY_OPENING_CARD_SECTION),
        SectionNode(expand=RENDER_OVERLAY_CLOSING_CARD_SECTION),
    ),
)

RENDER_POST_FX_HIGHLIGHT_ROLLOFF_ACTIVE = ConditionalRowsDef(
    name="highlight_rolloff_active",
    predicate=lambda state, _desc: state.render_post_fx.highlight_rolloff.mode != "off",
    children=(
        SectionNode(leaf_kind=RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CURVE),
        SectionNode(leaf_kind=RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD),
        SectionNode(leaf_kind=RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CEILING),
        SectionNode(leaf_kind=RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_STRENGTH),
        SectionNode(leaf_kind=RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_SOFTNESS),
        SectionNode(leaf_kind=RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_DESATURATION),
    ),
)

RENDER_POST_FX_HIGHLIGHT_ROLLOFF_SECTION = ExpandSectionDef(
    header_kind=RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_HEADER,
    context="global",
    read_expanded=_render_post_fx_highlight_rolloff_expanded,
    toggle=_toggle_render_post_fx_highlight_rolloff,
    children=(
        SectionNode(leaf_kind=RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_MODE),
        SectionNode(conditional=RENDER_POST_FX_HIGHLIGHT_ROLLOFF_ACTIVE),
    ),
)

RENDER_POST_FX_CHROMA_BOOST_ACTIVE = ConditionalRowsDef(
    name="chroma_boost_active",
    predicate=lambda state, _desc: state.render_post_fx.chroma_boost.mode != "off",
    children=(
        SectionNode(leaf_kind=RowKind.RENDER_POST_FX_CHROMA_BOOST_VARIANT),
        SectionNode(leaf_kind=RowKind.RENDER_POST_FX_CHROMA_BOOST_AMOUNT),
    ),
)

RENDER_POST_FX_CHROMA_BOOST_SECTION = ExpandSectionDef(
    header_kind=RowKind.RENDER_POST_FX_CHROMA_BOOST_HEADER,
    context="global",
    read_expanded=_render_post_fx_chroma_boost_expanded,
    toggle=_toggle_render_post_fx_chroma_boost,
    children=(
        SectionNode(leaf_kind=RowKind.RENDER_POST_FX_CHROMA_BOOST_MODE),
        SectionNode(conditional=RENDER_POST_FX_CHROMA_BOOST_ACTIVE),
    ),
)

RENDER_POST_FX_SECTION = ExpandSectionDef(
    header_kind=RowKind.RENDER_POST_FX_HEADER,
    context="global",
    read_expanded=_render_post_fx_expanded,
    toggle=_toggle_render_post_fx,
    children=(
        SectionNode(leaf_kind=RowKind.RENDER_POST_FX_FADE_IN),
        SectionNode(leaf_kind=RowKind.RENDER_POST_FX_FADE_OUT),
        SectionNode(expand=RENDER_POST_FX_HIGHLIGHT_ROLLOFF_SECTION),
        SectionNode(expand=RENDER_POST_FX_CHROMA_BOOST_SECTION),
    ),
)

def _preset_switching_projectm_trigger(
    state: TuningViewState, desc: RowDescriptor
) -> bool:
    if desc.slot is None:
        return False
    return state.tracks[desc.slot].preset_switching_trigger == "projectm"


def _preset_switching_uses_duration(
    state: TuningViewState, desc: RowDescriptor
) -> bool:
    if desc.slot is None:
        return False
    return state.tracks[desc.slot].preset_switching_trigger != "timeline"


def _hard_cut_enabled(state: TuningViewState, desc: RowDescriptor) -> bool:
    if desc.slot is None:
        return False
    return state.tracks[desc.slot].hard_cut_enabled


HARD_CUT_ENABLED = ConditionalRowsDef(
    name="hard_cut_enabled",
    predicate=_hard_cut_enabled,
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_HARD_CUT_DURATION),
        SectionNode(leaf_kind=RowKind.TRACK_HARD_CUT_SENSITIVITY),
    ),
)

PRESET_LIST_SECTION = ExpandSectionDef(
    header_kind=RowKind.TRACK_PRESET_LIST,
    context="per_slot",
    read_expanded=_preset_list_expanded,
    toggle=_toggle_preset_list,
    children=(),
    append_dynamic_children=_append_preset_list_rows,
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

TRACK_PRESET_SWITCHING_SECTION = ExpandSectionDef(
    header_kind=RowKind.TRACK_PRESET_SWITCHING,
    context="per_slot",
    read_expanded=_track_preset_switching_expanded,
    toggle=_toggle_preset_switching,
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_PRESET_SWITCHING_TRIGGER),
        SectionNode(conditional=PRESET_SWITCHING_USES_DURATION),
        SectionNode(conditional=PRESET_SWITCHING_PROJECTM_TRIGGER),
        SectionNode(leaf_kind=RowKind.TRACK_PRESET_START_CLEAN),
        SectionNode(expand=PRESET_LIST_SECTION),
    ),
)

TRACK_EFFECTS_SECTION = ExpandSectionDef(
    header_kind=RowKind.TRACK_EFFECTS_HEADER,
    context="per_slot",
    read_expanded=_track_effects_expanded,
    toggle=_toggle_effects_header,
    children=(),
    append_dynamic_children=_append_track_effect_rows,
)

TRACK_SECTION = ExpandSectionDef(
    header_kind=RowKind.TRACK_HEADER,
    context="per_slot",
    read_expanded=_track_header_expanded,
    toggle=_toggle_track_header,
    children=(
        SectionNode(leaf_kind=RowKind.TRACK_STEM),
        SectionNode(leaf_kind=RowKind.TRACK_BEAT),
        SectionNode(leaf_kind=RowKind.TRACK_PRESET_DIR),
        SectionNode(leaf_kind=RowKind.TRACK_PRESET),
        SectionNode(expand=TRACK_PRESET_SWITCHING_SECTION),
        SectionNode(leaf_kind=RowKind.TRACK_BLEND),
        SectionNode(leaf_kind=RowKind.TRACK_OPACITY),
        SectionNode(expand=TRACK_EFFECTS_SECTION),
        SectionNode(leaf_kind=RowKind.LAYER_MANAGEMENT_DELETE),
    ),
)

ROOT_SECTION_NODES: tuple[SectionNode, ...] = (SectionNode(expand=SETTINGS_SECTION),)

RENDER_SECTION_NODES: tuple[SectionNode, ...] = (
    SectionNode(expand=RENDER_OVERLAYS_SECTION),
    SectionNode(expand=RENDER_POST_FX_SECTION),
    SectionNode(panel_anchor=TIMELINE_PANEL_ANCHOR),
)

SONG_MARKERS_SECTION = ExpandSectionDef(
    header_kind=RowKind.SONG_MARKERS_HEADER,
    context="global",
    read_expanded=_song_markers_expanded,
    toggle=_toggle_song_markers,
    children=(),
    append_dynamic_children=_append_song_marker_rows,
)

BEAT_BAR_GRID_SECTION = ExpandSectionDef(
    header_kind=RowKind.TIMELINE_BEAT_BAR_GRID_HEADER,
    context="global",
    read_expanded=_beat_bar_grid_expanded,
    toggle=_toggle_beat_bar_grid,
    children=(
        SectionNode(leaf_kind=RowKind.TIMELINE_PLACEMENT_SNAP),
        SectionNode(leaf_kind=RowKind.TIMELINE_BAR_GRID),
        SectionNode(leaf_kind=RowKind.TIMELINE_BAR_PHASE),
    ),
)

SNAP_CUES_SECTION = ExpandSectionDef(
    header_kind=RowKind.TIMELINE_SNAP_CUES_HEADER,
    context="global",
    read_expanded=_snap_cues_expanded,
    toggle=_toggle_snap_cues,
    children=(
        SectionNode(leaf_kind=RowKind.TIMELINE_SNAP_TO_BEATS),
        SectionNode(leaf_kind=RowKind.TIMELINE_SNAP_TO_BARS),
        SectionNode(leaf_kind=RowKind.TIMELINE_SNAP_TO_SONG_MARKERS),
    ),
)


def _timeline_hard_cut_fades_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> bool:
    return state.render_timeline.hard_cut_fades.enabled


def _timeline_soft_cut_fades_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> bool:
    return state.render_timeline.soft_cut_fades.enabled


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

TIMELINE_CUTS_SECTION = ExpandSectionDef(
    header_kind=RowKind.TIMELINE_CUTS_HEADER,
    context="global",
    read_expanded=_timeline_cuts_expanded,
    toggle=_toggle_timeline_cuts,
    children=(
        SectionNode(leaf_kind=RowKind.TIMELINE_HARD_CUTS),
        SectionNode(conditional=TIMELINE_HARD_CUTS_ACTIVE),
        SectionNode(leaf_kind=RowKind.TIMELINE_SOFT_CUTS),
        SectionNode(conditional=TIMELINE_SOFT_CUTS_ACTIVE),
        SectionNode(leaf_kind=RowKind.TIMELINE_APPLY_SOFT_CUTS),
        SectionNode(leaf_kind=RowKind.TIMELINE_APPLY_HARD_CUTS),
    ),
)

TIMELINE_PRESETS_SECTION = ExpandSectionDef(
    header_kind=RowKind.TIMELINE_PRESETS_HEADER,
    context="global",
    read_expanded=_timeline_presets_expanded,
    toggle=_toggle_timeline_presets,
    children=(
        SectionNode(leaf_kind=RowKind.TIMELINE_PRESET_CHARACTER),
        SectionNode(leaf_kind=RowKind.TIMELINE_PRESET_CRESCENDO),
        SectionNode(leaf_kind=RowKind.TIMELINE_PRESET_DENSITY),
        SectionNode(leaf_kind=RowKind.TIMELINE_PRESET_CUE_SNAP),
        SectionNode(leaf_kind=RowKind.TIMELINE_PRESET_SONG_MARKER_SNAP),
        SectionNode(leaf_kind=RowKind.TIMELINE_PRESET_TIMELINE_CUTS),
        SectionNode(leaf_kind=RowKind.TIMELINE_PRESET_REPOPULATE),
        SectionNode(leaf_kind=RowKind.TIMELINE_PRESET_CONDUCTOR),
        SectionNode(leaf_kind=RowKind.TIMELINE_PRESETS),
    ),
)


def _visual_limiter_enabled(
    state: TuningViewState, _desc: RowDescriptor
) -> bool:
    return state.render_timeline.limiter.enabled


TIMELINE_VISUAL_LIMITER_ACTIVE = ConditionalRowsDef(
    name="visual_limiter_enabled",
    predicate=_visual_limiter_enabled,
    children=(
        SectionNode(leaf_kind=RowKind.TIMELINE_VISUAL_LIMITER_THRESHOLD),
        SectionNode(leaf_kind=RowKind.TIMELINE_VISUAL_LIMITER_RELEASE),
    ),
)

TIMELINE_VISUAL_LIMITER_SECTION = ExpandSectionDef(
    header_kind=RowKind.TIMELINE_VISUAL_LIMITER_HEADER,
    context="global",
    read_expanded=_visual_limiter_expanded,
    toggle=_toggle_visual_limiter,
    children=(
        SectionNode(conditional=TIMELINE_VISUAL_LIMITER_ACTIVE),
    ),
)


def _collect_expand_sections(
    *roots: ExpandSectionDef,
    extra_nodes: tuple[SectionNode, ...] = (),
) -> tuple[ExpandSectionDef, ...]:
    seen: dict[RowKind, ExpandSectionDef] = {}
    order: list[ExpandSectionDef] = []

    def walk_section(section: ExpandSectionDef) -> None:
        if section.header_kind in seen:
            return
        seen[section.header_kind] = section
        order.append(section)
        walk_nodes(section.children)

    def walk_nodes(nodes: tuple[SectionNode, ...]) -> None:
        for child in nodes:
            if child.expand is not None:
                walk_section(child.expand)
            elif child.conditional is not None:
                walk_nodes(child.conditional.children)

    for root in roots:
        walk_section(root)
    walk_nodes(extra_nodes)
    return tuple(order)


_ALL_EXPAND_SECTIONS = _collect_expand_sections(
    SETTINGS_SECTION,
    TRACK_SECTION,
    SONG_MARKERS_SECTION,
    BEAT_BAR_GRID_SECTION,
    SNAP_CUES_SECTION,
    TIMELINE_CUTS_SECTION,
    TIMELINE_PRESETS_SECTION,
    TIMELINE_VISUAL_LIMITER_SECTION,
    extra_nodes=RENDER_SECTION_NODES,
)

EXPAND_SECTION_BY_HEADER: dict[RowKind, ExpandSectionDef] = {
    section.header_kind: section for section in _ALL_EXPAND_SECTIONS
}

EXPAND_TOGGLE_BY_HEADER: dict[RowKind, ExpandToggleFn] = {
    section.header_kind: section.toggle for section in _ALL_EXPAND_SECTIONS
}

EXPAND_HEADER_KINDS = frozenset(EXPAND_SECTION_BY_HEADER)


def apply_expand_toggle(
    controls: TuningControls,
    header_kind: RowKind,
    slot: str | None,
    forward: bool,
) -> bool:
    section = EXPAND_SECTION_BY_HEADER.get(header_kind)
    if section is None:
        return False
    section.toggle(controls, slot, forward)
    return True


def _root_expand_sections(nodes: tuple[SectionNode, ...]) -> tuple[ExpandSectionDef, ...]:
    return tuple(node.expand for node in nodes if node.expand is not None)


_GLOBAL_ROOT_EXPAND_SECTIONS = _root_expand_sections(ROOT_SECTION_NODES + RENDER_SECTION_NODES)


def expand_section_expanded(
    state: TuningViewState,
    section: ExpandSectionDef,
    slot: str | None,
) -> bool:
    return section.read_expanded(state, slot)


def expand_arrow_for_header(
    state: TuningViewState,
    kind: RowKind,
    slot: str | None = None,
) -> str:
    section = EXPAND_SECTION_BY_HEADER[kind]
    section_slot = slot if section.context == "per_slot" else None
    return expand_arrow_glyph(expand_section_expanded(state, section, section_slot))


def leaf_kinds_in_expand_section(section: ExpandSectionDef) -> frozenset[RowKind]:
    kinds: set[RowKind] = set()
    for child in section.children:
        if child.leaf_kind is not None:
            kinds.add(child.leaf_kind)
        if child.expand is not None:
            kinds |= leaf_kinds_in_expand_section(child.expand)
        if child.conditional is not None:
            kinds |= _leaf_kinds_in_nodes(child.conditional.children)
    return frozenset(kinds)


def _leaf_kinds_in_nodes(nodes: tuple[SectionNode, ...]) -> frozenset[RowKind]:
    kinds: set[RowKind] = set()
    for child in nodes:
        if child.leaf_kind is not None:
            kinds.add(child.leaf_kind)
        if child.expand is not None:
            kinds |= leaf_kinds_in_expand_section(child.expand)
        if child.conditional is not None:
            kinds |= _leaf_kinds_in_nodes(child.conditional.children)
    return frozenset(kinds)


def kinds_in_expand_section(section: ExpandSectionDef) -> frozenset[RowKind]:
    kinds: set[RowKind] = {section.header_kind}
    for child in section.children:
        if child.leaf_kind is not None:
            kinds.add(child.leaf_kind)
        if child.expand is not None:
            kinds |= kinds_in_expand_section(child.expand)
        if child.conditional is not None:
            kinds |= _leaf_kinds_in_nodes(child.conditional.children)
    return frozenset(kinds)


RENDER_OVERLAY_SECTION_KINDS = kinds_in_expand_section(RENDER_OVERLAYS_SECTION)
RENDER_POST_FX_SECTION_KINDS = kinds_in_expand_section(RENDER_POST_FX_SECTION)
PRESET_SWITCHING_CHILD_KINDS = frozenset(
    kinds_in_expand_section(TRACK_PRESET_SWITCHING_SECTION)
    - {RowKind.TRACK_PRESET_SWITCHING}
    | {
        RowKind.TRACK_PRESET_LIST_ITEM,
        RowKind.TRACK_PRESET_LIST_ADD,
        RowKind.TRACK_PRESET_LIST_POPULATE,
    }
)
RENDER_TIMELINE_SECTION_KINDS = frozenset(
    {
        RowKind.RENDER_TIMELINE_HEADER,
        RowKind.SONG_MARKERS_HEADER,
        RowKind.SONG_MARKER_ITEM,
        RowKind.TIMELINE_PRESETS_HEADER,
        RowKind.TIMELINE_PRESET_CHARACTER,
        RowKind.TIMELINE_PRESET_CRESCENDO,
        RowKind.TIMELINE_PRESET_DENSITY,
        RowKind.TIMELINE_PRESET_CUE_SNAP,
        RowKind.TIMELINE_PRESET_SONG_MARKER_SNAP,
        RowKind.TIMELINE_PRESET_TIMELINE_CUTS,
        RowKind.TIMELINE_PRESET_REPOPULATE,
        RowKind.TIMELINE_PRESET_CONDUCTOR,
        RowKind.TIMELINE_PRESETS,
        RowKind.TIMELINE_VISUAL_LIMITER_HEADER,
        RowKind.TIMELINE_VISUAL_LIMITER_THRESHOLD,
        RowKind.TIMELINE_VISUAL_LIMITER_RELEASE,
        RowKind.TIMELINE_RESET,
        RowKind.TIMELINE_BEAT_BAR_GRID_HEADER,
        RowKind.TIMELINE_PLACEMENT_SNAP,
        RowKind.TIMELINE_BAR_GRID,
        RowKind.TIMELINE_BAR_PHASE,
        RowKind.TIMELINE_SNAP_CUES_HEADER,
        RowKind.TIMELINE_SNAP_TO_BEATS,
        RowKind.TIMELINE_SNAP_TO_BARS,
        RowKind.TIMELINE_SNAP_TO_SONG_MARKERS,
        RowKind.TIMELINE_CUTS_HEADER,
        RowKind.TIMELINE_HARD_CUTS,
        RowKind.TIMELINE_HARD_CUT_FADE_IN,
        RowKind.TIMELINE_HARD_CUT_FADE_OUT,
        RowKind.TIMELINE_HARD_CUT_CROSSFADE,
        RowKind.TIMELINE_SOFT_CUTS,
        RowKind.TIMELINE_SOFT_CUT_FADE_IN,
        RowKind.TIMELINE_SOFT_CUT_FADE_OUT,
        RowKind.TIMELINE_SOFT_CUT_CROSSFADE,
        RowKind.TIMELINE_APPLY_SOFT_CUTS,
        RowKind.TIMELINE_APPLY_HARD_CUTS,
    }
)


def _assign_indent_depth(
    depths: dict[RowKind, int],
    nodes: tuple[SectionNode, ...],
    depth: int,
) -> None:
    for child in nodes:
        if child.leaf_kind is not None:
            depths[child.leaf_kind] = depth
        elif child.expand is not None:
            _assign_expand_indent_depth(depths, child.expand, depth)
        elif child.conditional is not None:
            _assign_indent_depth(
                depths,
                child.conditional.children,
                depth + child.conditional.child_indent_offset,
            )


def _assign_expand_indent_depth(
    depths: dict[RowKind, int],
    section: ExpandSectionDef,
    depth: int,
) -> None:
    depths[section.header_kind] = depth
    _assign_indent_depth(depths, section.children, depth + 1)


def _build_row_tree_indent_depth() -> dict[RowKind, int]:
    depths: dict[RowKind, int] = {}
    _assign_expand_indent_depth(depths, SETTINGS_SECTION, 0)
    _assign_expand_indent_depth(depths, TRACK_SECTION, 0)
    for node in RENDER_SECTION_NODES:
        if node.expand is not None:
            _assign_expand_indent_depth(depths, node.expand, 0)
    depths[RowKind.TRACK_EFFECT] = 2
    # Dynamic preset list rows nest under the preset list header.
    preset_list_depth = depths[RowKind.TRACK_PRESET_LIST]
    preset_list_item_depth = preset_list_depth + 1
    depths[RowKind.TRACK_PRESET_LIST_ITEM] = preset_list_item_depth
    depths[RowKind.TRACK_PRESET_LIST_ADD] = preset_list_item_depth
    depths[RowKind.TRACK_PRESET_LIST_POPULATE] = preset_list_item_depth
    depths[RowKind.SONG_MARKERS_HEADER] = 1
    depths[RowKind.SONG_MARKER_ITEM] = 2
    depths[RowKind.TIMELINE_RESET] = 1
    _assign_expand_indent_depth(depths, BEAT_BAR_GRID_SECTION, 1)
    _assign_expand_indent_depth(depths, SNAP_CUES_SECTION, 1)
    _assign_expand_indent_depth(depths, TIMELINE_CUTS_SECTION, 1)
    _assign_expand_indent_depth(depths, TIMELINE_PRESETS_SECTION, 1)
    _assign_expand_indent_depth(depths, TIMELINE_VISUAL_LIMITER_SECTION, 1)
    depths[RowKind.TIMELINE_HARD_CUT_FADE_IN] = 3
    depths[RowKind.TIMELINE_HARD_CUT_FADE_OUT] = 3
    depths[RowKind.TIMELINE_HARD_CUT_CROSSFADE] = 3
    depths[RowKind.TIMELINE_SOFT_CUT_FADE_IN] = 3
    depths[RowKind.TIMELINE_SOFT_CUT_FADE_OUT] = 3
    depths[RowKind.TIMELINE_SOFT_CUT_CROSSFADE] = 3
    depths[RowKind.TIMELINE_VISUAL_LIMITER_THRESHOLD] = 2
    depths[RowKind.TIMELINE_VISUAL_LIMITER_RELEASE] = 2
    return depths


ROW_TREE_INDENT_DEPTH = _build_row_tree_indent_depth()


def row_tree_indent_depth(kind: RowKind) -> int:
    """Tree depth for draw indent (0 = no branch prefix, 1 = └─, 2 = nested)."""
    return ROW_TREE_INDENT_DEPTH.get(kind, 0)


def _expand_path_to_kind(
    section: ExpandSectionDef,
    kind: RowKind,
) -> list[ExpandSectionDef] | None:
    """Expand sections from *section* (inclusive) down to the owner of *kind*."""
    if kind == section.header_kind:
        return [section]
    for child in section.children:
        if child.leaf_kind == kind:
            return [section]
        if child.conditional is not None and kind in _leaf_kinds_in_nodes(
            child.conditional.children
        ):
            return [section]
        if child.expand is not None:
            if child.expand.header_kind == kind:
                return [section]
            nested = _expand_path_to_kind(child.expand, kind)
            if nested is not None:
                return [section, *nested]
    return None


def expand_section_sub_row_visible(
    state: TuningViewState,
    desc: RowDescriptor,
    section: ExpandSectionDef,
) -> bool | None:
    kind = desc.kind
    if kind == section.header_kind:
        return True
    slot = desc.slot if section.context == "per_slot" else None
    if kind not in leaf_kinds_in_expand_section(section):
        return None
    path = _expand_path_to_kind(section, kind)
    if path is None:
        return None
    for ancestor in path:
        if not expand_section_expanded(state, ancestor, slot):
            return False
    return True


def sub_row_expand_visible(state: TuningViewState, desc: RowDescriptor) -> bool:
    for section in _GLOBAL_ROOT_EXPAND_SECTIONS:
        visible = expand_section_sub_row_visible(state, desc, section)
        if visible is not None:
            return visible
    if desc.slot is not None:
        visible = expand_section_sub_row_visible(state, desc, TRACK_SECTION)
        if visible is not None:
            return visible
    return True


def _append_section_nodes(
    row_list: list[RowDescriptor],
    nodes: tuple[SectionNode, ...],
    state: TuningViewState,
    slot: str | None,
    section_slot: str | None,
) -> None:
    probe = RowDescriptor(RowKind.TRACK_HEADER, slot=section_slot)
    for child in nodes:
        if child.leaf_kind is not None:
            row_list.append(RowDescriptor(child.leaf_kind, slot=section_slot))
        elif child.expand is not None:
            append_expand_section_rows(row_list, child.expand, state, slot)
        elif child.conditional is not None:
            if child.conditional.predicate(state, probe):
                _append_section_nodes(
                    row_list, child.conditional.children, state, slot, section_slot
                )
        elif child.panel_anchor is not None:
            row_list.append(RowDescriptor(child.panel_anchor.header_kind))


def append_expand_section_rows(
    row_list: list[RowDescriptor],
    section: ExpandSectionDef,
    state: TuningViewState,
    slot: str | None = None,
) -> None:
    section_slot = slot if section.context == "per_slot" else None
    row_list.append(RowDescriptor(section.header_kind, slot=section_slot))
    if not expand_section_expanded(state, section, slot):
        return
    _append_section_nodes(row_list, section.children, state, slot, section_slot)
    if section.append_dynamic_children is not None:
        section.append_dynamic_children(row_list, state, slot)


def append_render_section_rows(
    row_list: list[RowDescriptor],
    state: TuningViewState,
) -> None:
    for node in RENDER_SECTION_NODES:
        if node.expand is not None:
            append_expand_section_rows(row_list, node.expand, state)
        elif node.panel_anchor is not None:
            row_list.append(RowDescriptor(node.panel_anchor.header_kind))
            if (
                node.panel_anchor.header_kind == RowKind.RENDER_TIMELINE_HEADER
                and state.render_timeline.expanded
            ):
                append_expand_section_rows(row_list, SONG_MARKERS_SECTION, state)
                append_expand_section_rows(row_list, BEAT_BAR_GRID_SECTION, state)
                append_expand_section_rows(row_list, SNAP_CUES_SECTION, state)
                append_expand_section_rows(row_list, TIMELINE_CUTS_SECTION, state)
                append_expand_section_rows(row_list, TIMELINE_PRESETS_SECTION, state)
                append_expand_section_rows(
                    row_list, TIMELINE_VISUAL_LIMITER_SECTION, state
                )
                row_list.append(RowDescriptor(RowKind.TIMELINE_RESET))


def append_track_section_rows(
    row_list: list[RowDescriptor],
    state: TuningViewState,
    slot: str,
) -> None:
    append_expand_section_rows(row_list, TRACK_SECTION, state, slot)


_PER_SLOT_SECTION_HEADERS = frozenset(
    {
        RowKind.TRACK_HEADER,
        RowKind.TRACK_PRESET_SWITCHING,
        RowKind.TRACK_EFFECTS_HEADER,
    }
)


def _register_section_header_parent(
    out: dict[RowKind, RowKind],
    parent_header: RowKind,
    nodes: tuple[SectionNode, ...],
) -> None:
    for child in nodes:
        if child.leaf_kind is not None:
            out[child.leaf_kind] = parent_header
        elif child.expand is not None:
            out[child.expand.header_kind] = parent_header
            _walk_expand_section_for_headers(child.expand, out)
        elif child.conditional is not None:
            _register_section_header_parent(out, parent_header, child.conditional.children)


def _walk_expand_section_for_headers(
    section: ExpandSectionDef,
    out: dict[RowKind, RowKind],
) -> None:
    header = section.header_kind
    _register_section_header_parent(out, header, section.children)


def _build_section_header_parent_map() -> dict[RowKind, RowKind]:
    out: dict[RowKind, RowKind] = {}
    for section in _GLOBAL_ROOT_EXPAND_SECTIONS:
        _walk_expand_section_for_headers(section, out)
    _walk_expand_section_for_headers(TRACK_SECTION, out)
    _walk_expand_section_for_headers(SONG_MARKERS_SECTION, out)
    _walk_expand_section_for_headers(BEAT_BAR_GRID_SECTION, out)
    _walk_expand_section_for_headers(SNAP_CUES_SECTION, out)
    _walk_expand_section_for_headers(TIMELINE_CUTS_SECTION, out)
    _walk_expand_section_for_headers(TIMELINE_PRESETS_SECTION, out)
    _walk_expand_section_for_headers(TIMELINE_VISUAL_LIMITER_SECTION, out)
    out[RowKind.TIMELINE_SNAP_CUES_HEADER] = RowKind.RENDER_TIMELINE_HEADER
    out[RowKind.TIMELINE_CUTS_HEADER] = RowKind.RENDER_TIMELINE_HEADER
    out[RowKind.TIMELINE_PRESETS_HEADER] = RowKind.RENDER_TIMELINE_HEADER
    out[RowKind.TIMELINE_VISUAL_LIMITER_HEADER] = RowKind.RENDER_TIMELINE_HEADER
    return out


_SECTION_HEADER_PARENTS = _build_section_header_parent_map()


def section_header_from_section_tree(desc: RowDescriptor) -> RowDescriptor | None:
    """Map a sub-row to its section header using the composition tree."""
    parent_kind = _SECTION_HEADER_PARENTS.get(desc.kind)
    if parent_kind is None:
        return None
    if parent_kind in _PER_SLOT_SECTION_HEADERS:
        return RowDescriptor(parent_kind, slot=desc.slot)
    return RowDescriptor(parent_kind)
