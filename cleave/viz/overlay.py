"""Live tuning tree overlay for the Cleave visualizer.

Row typography: LABEL prefixes, VALUE defaults, DISABLED/LOCKED state overrides.
See cleave/viz/theme.py and .cursor/rules/live-tuning-ui.mdc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pygame

from cleave.config import RenderOverlayPosition
from cleave.config_schema import (
    default_render_overlay_runtime_values,
    default_render_post_fx_runtime_values,
)
from cleave.effects.registry import effect_roster
from cleave.extract import StemSource, stem_control_label, stem_overlay_header
from cleave.viz.row_semantics import (
    HEADER_ROW_KINDS,
    LABELED_SUB_ROW_KINDS,
    RENDER_OVERLAY_ALL_SUB_ROW_KINDS,
    RENDER_OVERLAY_BODY_NESTED_KINDS,
    RENDER_OVERLAY_SUB_ROW_KINDS,
    RENDER_OVERLAY_TITLE_NESTED_KINDS,
    RENDER_POST_FX_SUB_ROW_KINDS,
    RowDescriptor,
    RowKind,
    TRACK_EFFECT_SUB_ROW_KINDS,
    TRACK_SUB_ROW_KINDS,
    row_blocked_by_layer_lock,
    row_navigable_when_layer_locked,
)
from cleave.viz.fonts import render_overlay_font_display
from cleave.viz.text_fit import (
    fit_counter_label_to_width,
    fit_path_label_to_width,
    fit_text_to_width,
)
from cleave.viz.playback import format_mmss
from cleave.viz.material_icons import (
    FILE_GLYPH,
    FOLDER_GLYPH,
    LOCK_GLYPH,
    VISIBILITY_GLYPH,
    VISIBILITY_OFF_GLYPH,
    VISIBILITY_ICON_PAD_X,
    render_glyph,
    render_transport_icons,
    row_icon_prefix_width,
    track_header_lock_suffix_width,
    visibility_icon_slot_width,
)
from cleave.viz.theme import (
    BACKGROUND,
    BACKGROUND_ALPHA,
    BORDER_COLOR,
    BORDER_WIDTH,
    DISABLED,
    FADE_DURATION_SEC,
    FOCUS_ROW_BG_ALPHA,
    HIGHLIGHT,
    HIGHLIGHT_MUTED,
    HOLD_IDLE_SEC,
    LABEL,
    LOCKED,
    LOCK_ICON,
    MOVE_MODE,
    PANEL_CONTENT_MAX_WIDTH,
    PRESET_FILE_ICON,
    PRESET_ICON,
    OVERRIDE_BG,
    OVERRIDE_GLYPH,
    OVERRIDE_GLYPH_OFF,
    CONFIG_DIRTY,
    SCROLLBAR_CONTENT_GAP,
    SCROLLBAR_THUMB,
    SCROLLBAR_TRACK,
    SCROLLBAR_WIDTH,
    SOLO_BG,
    VALUE,
    tuning_ui_metrics,
)
from cleave.viz.ui_tint import blit_tint

Anchor = Literal["topleft", "bottomleft"]

HEADER_ROWS = 2
_tuning_ui = tuning_ui_metrics()
TREE_INDENT = _tuning_ui.tree_indent
TIMELINE_LAYER_HINT_TEXT = "Timeline is enabled and controlling layer visibility"
ROW_ICON_SUFFIX_GAP = _tuning_ui.row_icon_suffix_gap


@dataclass
class TrackBlock:
    stem: StemSource
    preset_dir_label: str
    preset_label: str
    blend_mode: str
    opacity_pct: int
    beat_sensitivity: float
    effects: dict[str, dict[str, int]]
    effects_expanded: bool = False
    enabled: bool = True
    visible: bool = True
    expanded: bool = False
    locked: bool = False
    preset_empty: bool = False


_RO_OVERLAY_DEFAULTS = default_render_overlay_runtime_values()
_RO_POST_FX_DEFAULTS = default_render_post_fx_runtime_values()


@dataclass
class RenderOverlayBlock:
    enabled: bool = _RO_OVERLAY_DEFAULTS["enabled"]
    expanded: bool = _RO_OVERLAY_DEFAULTS["expanded"]
    position: RenderOverlayPosition = _RO_OVERLAY_DEFAULTS["position"]
    title_expanded: bool = _RO_OVERLAY_DEFAULTS["title_expanded"]
    body_expanded: bool = _RO_OVERLAY_DEFAULTS["body_expanded"]
    title_font_size: int = _RO_OVERLAY_DEFAULTS["title_font_size"]
    title_font: str = _RO_OVERLAY_DEFAULTS["title_font"]
    title_margin_bottom: int = _RO_OVERLAY_DEFAULTS["title_margin_bottom"]
    body_font_size: int = _RO_OVERLAY_DEFAULTS["body_font_size"]
    body_font: str = _RO_OVERLAY_DEFAULTS["body_font"]
    opacity_pct: int = _RO_OVERLAY_DEFAULTS["opacity_pct"]
    border_width: int = _RO_OVERLAY_DEFAULTS["border_width"]
    start_delay: float = _RO_OVERLAY_DEFAULTS["start_delay"]
    display_time: float = _RO_OVERLAY_DEFAULTS["display_time"]
    solo: bool = False


@dataclass
class RenderPostFxBlock:
    enabled: bool = _RO_POST_FX_DEFAULTS["enabled"]
    expanded: bool = _RO_POST_FX_DEFAULTS["expanded"]
    fade_in: float = _RO_POST_FX_DEFAULTS["fade_in"]
    fade_out: float = _RO_POST_FX_DEFAULTS["fade_out"]
    solo: bool = False


@dataclass
class RenderTimelineBlock:
    enabled: bool = False
    expanded: bool = False


@dataclass
class TuningViewState:
    layer_z_order: tuple[str, ...]
    tracks: dict[str, TrackBlock]
    paused: bool
    position_sec: float
    focus_index: int
    move_mode_slot: str | None
    toast_message: str | None
    toast_remaining_sec: float
    allow_overwrite: bool = True
    active_config_label: str = "cleave-viz.yaml"
    config_dirty: bool = False
    solo_slot: str | None = None
    solo_active: bool = False
    render_overlay: RenderOverlayBlock = field(default_factory=RenderOverlayBlock)
    render_post_fx: RenderPostFxBlock = field(
        default_factory=RenderPostFxBlock
    )
    render_timeline: RenderTimelineBlock = field(
        default_factory=RenderTimelineBlock
    )
    timeline_submenu_focused: bool = False
    timeline_recording: bool = False
    timeline_override_active: bool = False
    help_visible: bool = False


def header_row_count(state: TuningViewState) -> int:
    return HEADER_ROWS


def build_row_layout(state: TuningViewState) -> list[RowDescriptor]:
    rows: list[RowDescriptor] = [
        RowDescriptor(RowKind.TRANSPORT),
        RowDescriptor(RowKind.CONFIG_HEADER),
    ]
    for slot in state.layer_z_order:
        rows.append(RowDescriptor(RowKind.TRACK_HEADER, slot=slot))
        rows.append(RowDescriptor(RowKind.TRACK_PRESET_DIR, slot=slot))
        rows.append(RowDescriptor(RowKind.TRACK_PRESET, slot=slot))
        rows.append(RowDescriptor(RowKind.TRACK_STEM, slot=slot))
        rows.append(RowDescriptor(RowKind.TRACK_BLEND, slot=slot))
        rows.append(RowDescriptor(RowKind.TRACK_OPACITY, slot=slot))
        rows.append(RowDescriptor(RowKind.TRACK_BEAT, slot=slot))
        rows.append(RowDescriptor(RowKind.TRACK_EFFECTS_HEADER, slot=slot))
        block = state.tracks[slot]
        if block.effects_expanded:
            for effect_def in effect_roster(block.stem):
                rows.append(
                    RowDescriptor(
                        RowKind.TRACK_EFFECT,
                        slot=slot,
                        effect_id=effect_def.effect_id,
                        driver_slug=effect_def.driver_slug,
                    )
                )
        if block.expanded:
            rows.append(
                RowDescriptor(RowKind.LAYER_MANAGEMENT_DELETE, slot=slot)
            )
    rows.append(RowDescriptor(RowKind.LAYER_MANAGEMENT_ADD))
    if state.render_timeline.enabled:
        rows.append(RowDescriptor(RowKind.TIMELINE_LAYER_HINT))
    rows.append(RowDescriptor(RowKind.RENDER_SECTION_GAP))
    rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_HEADER))
    if state.render_overlay.expanded:
        rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_POSITION))
        rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_OPACITY))
        rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_BORDER_WIDTH))
        rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_START_DELAY))
        rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_DISPLAY_TIME))
        rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_HEADER))
        if state.render_overlay.title_expanded:
            rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_FONT))
            rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE))
            rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM))
        rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_BODY_HEADER))
        if state.render_overlay.body_expanded:
            rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_BODY_FONT))
            rows.append(RowDescriptor(RowKind.RENDER_OVERLAY_BODY_FONT_SIZE))
    rows.append(RowDescriptor(RowKind.RENDER_POST_FX_HEADER))
    if state.render_post_fx.expanded:
        rows.append(RowDescriptor(RowKind.RENDER_POST_FX_FADE_IN))
        rows.append(RowDescriptor(RowKind.RENDER_POST_FX_FADE_OUT))
    rows.append(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER))
    return rows


def track_row_count(state: TuningViewState) -> int:
    """Count of scrollable content rows (all rows except pinned header rows)."""
    return sum(
        1
        for row in build_row_layout(state)
        if row.kind not in HEADER_ROW_KINDS
    )


def row_descriptor(state: TuningViewState, index: int) -> RowDescriptor:
    layout = build_row_layout(state)
    if index < 0 or index >= len(layout):
        raise IndexError(index)
    return layout[index]


def find_row(
    state: TuningViewState,
    slot: str,
    kind: RowKind,
    *,
    effect_id: str | None = None,
    driver_slug: str | None = None,
) -> int:
    for index, desc in enumerate(build_row_layout(state)):
        if desc.kind != kind or desc.slot != slot:
            continue
        if kind == RowKind.TRACK_EFFECT:
            if desc.effect_id != effect_id or desc.driver_slug != driver_slug:
                continue
        return index
    raise ValueError(f"no row for slot={slot!r} kind={kind!r}")


def find_row_by_kind(state: TuningViewState, kind: RowKind) -> int:
    for index, desc in enumerate(build_row_layout(state)):
        if desc.kind == kind:
            return index
    raise ValueError(f"no row for kind={kind!r}")


def row_count(state: TuningViewState) -> int:
    return len(build_row_layout(state))


def track_sub_rows_visible(state: TuningViewState, slot: str) -> bool:
    return state.tracks[slot].expanded


def _sub_row_visible(state: TuningViewState, index: int) -> bool:
    desc = row_descriptor(state, index)
    if desc.kind in {RowKind.RENDER_SECTION_GAP, RowKind.TIMELINE_LAYER_HINT}:
        return True
    if desc.kind in RENDER_OVERLAY_SUB_ROW_KINDS:
        return state.render_overlay.expanded
    if desc.kind in RENDER_OVERLAY_TITLE_NESTED_KINDS:
        return state.render_overlay.expanded and state.render_overlay.title_expanded
    if desc.kind in RENDER_OVERLAY_BODY_NESTED_KINDS:
        return state.render_overlay.expanded and state.render_overlay.body_expanded
    if desc.kind in RENDER_POST_FX_SUB_ROW_KINDS:
        return state.render_post_fx.expanded
    slot = desc.slot
    if slot is None or desc.kind not in TRACK_SUB_ROW_KINDS:
        return True
    block = state.tracks[slot]
    if not block.expanded:
        return False
    if desc.kind in TRACK_EFFECT_SUB_ROW_KINDS:
        return block.effects_expanded
    return True


def row_visible(state: TuningViewState, index: int) -> bool:
    return _sub_row_visible(state, index)


def visible_row_indices(state: TuningViewState) -> list[int]:
    """Row indices drawn in the panel (sub-rows hidden when collapsed)."""
    return [index for index in range(row_count(state)) if row_visible(state, index)]


def navigable_row_indices(state: TuningViewState) -> list[int]:
    """Row indices reachable via Up/Down (sub-rows skipped when collapsed)."""
    indices: list[int] = []
    for index in range(row_count(state)):
        desc = row_descriptor(state, index)
        if desc.kind in {
            RowKind.RENDER_SECTION_GAP,
            RowKind.TIMELINE_LAYER_HINT,
        }:
            continue
        if desc.kind in RENDER_OVERLAY_SUB_ROW_KINDS:
            if not state.render_overlay.expanded:
                continue
        elif desc.kind in RENDER_OVERLAY_TITLE_NESTED_KINDS:
            if not state.render_overlay.expanded or not state.render_overlay.title_expanded:
                continue
        elif desc.kind in RENDER_OVERLAY_BODY_NESTED_KINDS:
            if not state.render_overlay.expanded or not state.render_overlay.body_expanded:
                continue
        elif desc.kind in RENDER_POST_FX_SUB_ROW_KINDS:
            if not state.render_post_fx.expanded:
                continue
        elif desc.kind in TRACK_SUB_ROW_KINDS:
            slot = desc.slot
            assert slot is not None
            block = state.tracks[slot]
            if not block.expanded:
                continue
            if block.locked and not row_navigable_when_layer_locked(desc.kind):
                continue
            if desc.kind in TRACK_EFFECT_SUB_ROW_KINDS and not block.effects_expanded:
                continue
        indices.append(index)
    return indices


def quick_nav_row_indices(state: TuningViewState) -> list[int]:
    """Row indices for Ctrl+Up/Down: layer headers and transport only."""
    indices: list[int] = []
    for index in range(row_count(state)):
        kind = row_kind(state, index)
        if kind in (
            RowKind.TRACK_HEADER,
            RowKind.RENDER_OVERLAY_HEADER,
            RowKind.RENDER_POST_FX_HEADER,
            RowKind.RENDER_TIMELINE_HEADER,
            RowKind.TRANSPORT,
        ):
            indices.append(index)
    return indices


def row_slot(state: TuningViewState, index: int) -> str | None:
    return row_descriptor(state, index).slot


def row_kind(state: TuningViewState, index: int) -> RowKind:
    return row_descriptor(state, index).kind


def row_effect(
    state: TuningViewState, index: int
) -> tuple[str, str] | None:
    desc = row_descriptor(state, index)
    if desc.kind != RowKind.TRACK_EFFECT:
        return None
    assert desc.effect_id is not None and desc.driver_slug is not None
    return desc.effect_id, desc.driver_slug


def _effect_pct(block: TrackBlock, effect_id: str, driver_slug: str) -> int:
    return block.effects.get(effect_id, {}).get(driver_slug, 0)


def _row_text(state: TuningViewState, index: int) -> str:
    kind = row_kind(state, index)
    if kind == RowKind.CONFIG_HEADER:
        return state.active_config_label
    if kind == RowKind.TRANSPORT:
        return ""
    if kind == RowKind.RENDER_SECTION_GAP:
        return ""

    if kind == RowKind.TIMELINE_LAYER_HINT:
        return TIMELINE_LAYER_HINT_TEXT

    if kind == RowKind.LAYER_MANAGEMENT_ADD:
        return "ADD NEW LAYER"
    if kind == RowKind.LAYER_MANAGEMENT_DELETE:
        return "Delete Layer"

    if kind == RowKind.RENDER_OVERLAY_HEADER:
        arrow = "▼" if state.render_overlay.expanded else "▶"
        return f"Render: OVERLAY {arrow}"

    if kind == RowKind.RENDER_POST_FX_HEADER:
        arrow = "▼" if state.render_post_fx.expanded else "▶"
        return f"Render: POST FX {arrow}"

    if kind == RowKind.RENDER_TIMELINE_HEADER:
        arrow = "▼" if state.render_timeline.expanded else "▶"
        return f"Render: TIMELINE {arrow}"

    block_ro = state.render_overlay
    if kind == RowKind.RENDER_OVERLAY_POSITION:
        return f"└─ position: {block_ro.position}"
    if kind == RowKind.RENDER_OVERLAY_TITLE_HEADER:
        arrow = "▼" if block_ro.title_expanded else "▶"
        return f"└─ title {arrow}"
    if kind == RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE:
        return f"└─ font size: {block_ro.title_font_size}px"
    if kind == RowKind.RENDER_OVERLAY_TITLE_FONT:
        return f"└─ font: {render_overlay_font_display(block_ro.title_font)}"
    if kind == RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM:
        return f"└─ margin bottom: {block_ro.title_margin_bottom}px"
    if kind == RowKind.RENDER_OVERLAY_BODY_HEADER:
        arrow = "▼" if block_ro.body_expanded else "▶"
        return f"└─ body {arrow}"
    if kind == RowKind.RENDER_OVERLAY_BODY_FONT_SIZE:
        return f"└─ font size: {block_ro.body_font_size}px"
    if kind == RowKind.RENDER_OVERLAY_BODY_FONT:
        return f"└─ font: {render_overlay_font_display(block_ro.body_font)}"
    if kind == RowKind.RENDER_OVERLAY_OPACITY:
        return f"└─ background opacity: {block_ro.opacity_pct}%"
    if kind == RowKind.RENDER_OVERLAY_BORDER_WIDTH:
        return f"└─ border width: {block_ro.border_width}px"
    if kind == RowKind.RENDER_OVERLAY_START_DELAY:
        return f"└─ start delay: {block_ro.start_delay:.1f}s"
    if kind == RowKind.RENDER_OVERLAY_DISPLAY_TIME:
        return f"└─ display time: {block_ro.display_time:.1f}s"

    block_pp = state.render_post_fx
    if kind == RowKind.RENDER_POST_FX_FADE_IN:
        return f"└─ fade in: {block_pp.fade_in:.1f}s"
    if kind == RowKind.RENDER_POST_FX_FADE_OUT:
        return f"└─ fade out: {block_pp.fade_out:.1f}s"

    stem = row_slot(state, index)
    assert stem is not None
    block = state.tracks[stem]
    if kind == RowKind.TRACK_HEADER:
        layer_num = state.layer_z_order.index(stem) + 1
        arrow = "▼" if block.expanded else "▶"
        return f"Layer {layer_num}: {stem_overlay_header(block.stem)} {arrow}"
    if kind == RowKind.TRACK_PRESET_DIR:
        return block.preset_dir_label
    if kind == RowKind.TRACK_PRESET:
        return block.preset_label
    if kind == RowKind.TRACK_STEM:
        return f"└─ driving stem: {stem_control_label(block.stem)}"
    if kind == RowKind.TRACK_BLEND:
        return f"└─ blend mode: {block.blend_mode}"
    if kind == RowKind.TRACK_OPACITY:
        return f"└─ opacity: {block.opacity_pct}%"
    if kind == RowKind.TRACK_BEAT:
        return f"└─ beat sensitivity: {block.beat_sensitivity:.2f}"
    if kind == RowKind.TRACK_EFFECTS_HEADER:
        arrow = "▼" if block.effects_expanded else "▶"
        return f"└─ cleave effects {arrow}"
    assert kind == RowKind.TRACK_EFFECT
    effect = row_effect(state, index)
    assert effect is not None
    effect_id, driver_slug = effect
    pct = _effect_pct(block, effect_id, driver_slug)
    return f"└─ {effect_id} ({driver_slug}): {pct}%"


def _labeled_sub_row_prefix(state: TuningViewState, index: int) -> str:
    kind = row_kind(state, index)
    if kind == RowKind.TRACK_BLEND:
        return "└─ blend mode: "
    if kind == RowKind.TRACK_STEM:
        return "└─ driving stem: "
    if kind == RowKind.TRACK_OPACITY:
        return "└─ opacity: "
    if kind == RowKind.TRACK_BEAT:
        return "└─ beat sensitivity: "
    if kind == RowKind.RENDER_OVERLAY_POSITION:
        return "└─ position: "
    if kind == RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE:
        return "└─ font size: "
    if kind == RowKind.RENDER_OVERLAY_TITLE_FONT:
        return "└─ font: "
    if kind == RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM:
        return "└─ margin bottom: "
    if kind == RowKind.RENDER_OVERLAY_BODY_FONT_SIZE:
        return "└─ font size: "
    if kind == RowKind.RENDER_OVERLAY_BODY_FONT:
        return "└─ font: "
    if kind == RowKind.RENDER_OVERLAY_OPACITY:
        return "└─ background opacity: "
    if kind == RowKind.RENDER_OVERLAY_BORDER_WIDTH:
        return "└─ border width: "
    if kind == RowKind.RENDER_OVERLAY_START_DELAY:
        return "└─ start delay: "
    if kind == RowKind.RENDER_OVERLAY_DISPLAY_TIME:
        return "└─ display time: "
    if kind == RowKind.RENDER_POST_FX_FADE_IN:
        return "└─ fade in: "
    if kind == RowKind.RENDER_POST_FX_FADE_OUT:
        return "└─ fade out: "
    assert kind == RowKind.TRACK_EFFECT
    effect = row_effect(state, index)
    assert effect is not None
    effect_id, driver_slug = effect
    return f"└─ {effect_id} ({driver_slug}): "


def _labeled_sub_row_value(state: TuningViewState, index: int) -> str:
    kind = row_kind(state, index)
    block_ro = state.render_overlay
    if kind == RowKind.RENDER_OVERLAY_POSITION:
        return block_ro.position
    if kind == RowKind.RENDER_OVERLAY_TITLE_FONT_SIZE:
        return f"{block_ro.title_font_size}px"
    if kind == RowKind.RENDER_OVERLAY_TITLE_FONT:
        return render_overlay_font_display(block_ro.title_font)
    if kind == RowKind.RENDER_OVERLAY_TITLE_MARGIN_BOTTOM:
        return f"{block_ro.title_margin_bottom}px"
    if kind == RowKind.RENDER_OVERLAY_BODY_FONT_SIZE:
        return f"{block_ro.body_font_size}px"
    if kind == RowKind.RENDER_OVERLAY_BODY_FONT:
        return render_overlay_font_display(block_ro.body_font)
    if kind == RowKind.RENDER_OVERLAY_OPACITY:
        return f"{block_ro.opacity_pct}%"
    if kind == RowKind.RENDER_OVERLAY_BORDER_WIDTH:
        return f"{block_ro.border_width}px"
    if kind == RowKind.RENDER_OVERLAY_START_DELAY:
        return f"{block_ro.start_delay:.1f}s"
    if kind == RowKind.RENDER_OVERLAY_DISPLAY_TIME:
        return f"{block_ro.display_time:.1f}s"
    block_pp = state.render_post_fx
    if kind == RowKind.RENDER_POST_FX_FADE_IN:
        return f"{block_pp.fade_in:.1f}s"
    if kind == RowKind.RENDER_POST_FX_FADE_OUT:
        return f"{block_pp.fade_out:.1f}s"
    stem = row_slot(state, index)
    assert stem is not None
    block = state.tracks[stem]
    if kind == RowKind.TRACK_BLEND:
        return block.blend_mode
    if kind == RowKind.TRACK_STEM:
        return stem_control_label(block.stem)
    if kind == RowKind.TRACK_OPACITY:
        return f"{block.opacity_pct}%"
    if kind == RowKind.TRACK_BEAT:
        return f"{block.beat_sensitivity:.2f}"
    assert kind == RowKind.TRACK_EFFECT
    effect = row_effect(state, index)
    assert effect is not None
    effect_id, driver_slug = effect
    return f"{_effect_pct(block, effect_id, driver_slug)}%"


def _fit_labeled_sub_row_value(
    font: pygame.font.Font,
    state: TuningViewState,
    index: int,
    *,
    max_content_width: int = PANEL_CONTENT_MAX_WIDTH,
) -> str:
    kind = row_kind(state, index)
    budget = max_content_width - _row_indent(state, index)
    budget -= font.size(_labeled_sub_row_prefix(state, index))[0]
    value = _labeled_sub_row_value(state, index)
    if kind in {
        RowKind.RENDER_OVERLAY_TITLE_FONT,
        RowKind.RENDER_OVERLAY_BODY_FONT,
    }:
        return fit_counter_label_to_width(font, value, budget)
    return fit_text_to_width(font, value, budget)


def _render_label_value_row(
    font: pygame.font.Font,
    *,
    prefix: str,
    value: str,
    value_color: tuple[int, int, int],
    line_height: int,
    prefix_color: tuple[int, int, int] | None = None,
    suffix_surf: pygame.Surface | None = None,
    suffix_gap: int = 0,
) -> pygame.Surface:
    prefix_surf = font.render(prefix, True, prefix_color if prefix_color is not None else LABEL)
    value_surf = font.render(value, True, value_color)
    label_w = prefix_surf.get_width() + value_surf.get_width()
    if suffix_surf is not None:
        label_w += suffix_gap + suffix_surf.get_width()

    label_surf = pygame.Surface((label_w, line_height), pygame.SRCALPHA)
    x = 0
    label_surf.blit(prefix_surf, (x, 0))
    x += prefix_surf.get_width()
    label_surf.blit(value_surf, (x, 0))
    if suffix_surf is not None:
        x += value_surf.get_width() + suffix_gap
        label_surf.blit(suffix_surf, (x, 0))
    return label_surf


def _track_header_layer_prefix(state: TuningViewState, index: int) -> str:
    stem = row_slot(state, index)
    assert stem is not None
    layer_num = state.layer_z_order.index(stem) + 1
    return f"Layer {layer_num}: "


def _track_header_expand_suffix(expanded: bool) -> str:
    arrow = "▼" if expanded else "▶"
    return f" {arrow}"


def _render_overlay_header_prefix() -> str:
    return "Render: "


def _render_post_fx_header_prefix() -> str:
    return "Render: "


def _render_timeline_header_prefix() -> str:
    return "Render: "


def render_visibility_icon(
    *,
    enabled: bool,
    solo: bool = False,
    override: bool = False,
    line_height: int,
) -> pygame.Surface:
    glyph = VISIBILITY_GLYPH if enabled else VISIBILITY_OFF_GLYPH
    if override:
        color = OVERRIDE_GLYPH if enabled else OVERRIDE_GLYPH_OFF
    elif enabled or solo:
        color = VALUE
    else:
        color = DISABLED
    glyph_surf = render_glyph(glyph, color=color, line_height=line_height)
    slot_w = visibility_icon_slot_width(line_height)
    surf = pygame.Surface((slot_w, line_height), pygame.SRCALPHA)
    if solo:
        pygame.draw.rect(surf, SOLO_BG, (0, 0, slot_w, line_height))
    elif override:
        pygame.draw.rect(surf, OVERRIDE_BG, (0, 0, slot_w, line_height))
    surf.blit(glyph_surf, (VISIBILITY_ICON_PAD_X, 0))
    return surf


def track_header_prefix_width(font: pygame.font.Font) -> int:
    line_h = font.get_linesize()
    icon_w = render_visibility_icon(
        enabled=True, solo=False, line_height=line_h
    ).get_width()
    return icon_w + ROW_ICON_SUFFIX_GAP


def _effects_header_prefix() -> str:
    return "└─ cleave effects "


def _effects_header_expand_value(expanded: bool) -> str:
    return "▼" if expanded else "▶"


def _render_overlay_text_header_prefix(label: str) -> str:
    return f"└─ {label} "


def _render_overlay_text_header_expand_value(expanded: bool) -> str:
    return _effects_header_expand_value(expanded)


def _fit_track_header_stem(
    font: pygame.font.Font,
    state: TuningViewState,
    index: int,
    *,
    max_content_width: int = PANEL_CONTENT_MAX_WIDTH,
) -> str:
    stem = row_slot(state, index)
    assert stem is not None
    block = state.tracks[stem]
    locked = block.locked
    budget = max_content_width - _row_indent(state, index)
    budget -= track_header_prefix_width(font)
    budget -= font.size(_track_header_layer_prefix(state, index))[0]
    budget -= font.size(_track_header_expand_suffix(block.expanded))[0]
    if locked:
        budget -= track_header_lock_suffix_width(font.get_linesize())
    return fit_text_to_width(font, stem_overlay_header(block.stem), budget)


def _render_track_header_label(
    font: pygame.font.Font,
    *,
    layer_prefix: str,
    stem_text: str,
    value_color: tuple[int, int, int],
    expanded: bool,
    locked: bool,
    line_height: int,
) -> pygame.Surface:
    arrow = _track_header_expand_suffix(expanded)
    prefix_surf = font.render(layer_prefix, True, LABEL)
    stem_surf = font.render(stem_text, True, value_color)
    arrow_surf = font.render(arrow, True, value_color)
    lock_surf = (
        render_glyph(LOCK_GLYPH, color=LOCK_ICON, line_height=line_height)
        if locked
        else None
    )

    label_w = prefix_surf.get_width() + stem_surf.get_width() + arrow_surf.get_width()
    if lock_surf is not None:
        label_w += ROW_ICON_SUFFIX_GAP + lock_surf.get_width()

    label_surf = pygame.Surface((label_w, line_height), pygame.SRCALPHA)
    x = 0
    label_surf.blit(prefix_surf, (x, 0))
    x += prefix_surf.get_width()
    label_surf.blit(stem_surf, (x, 0))
    x += stem_surf.get_width()
    label_surf.blit(arrow_surf, (x, 0))
    if lock_surf is not None:
        x += arrow_surf.get_width() + ROW_ICON_SUFFIX_GAP
        label_surf.blit(lock_surf, (x, 0))
    return label_surf


def fit_row_text(
    font: pygame.font.Font,
    state: TuningViewState,
    index: int,
    *,
    max_content_width: int = PANEL_CONTENT_MAX_WIDTH,
) -> str:
    """Fit row label to the shared panel content width (pixels)."""
    kind = row_kind(state, index)
    indent = _row_indent(state, index)
    budget = max_content_width - indent
    text = _row_text(state, index)

    if kind in {RowKind.CONFIG_HEADER, RowKind.TRACK_PRESET_DIR, RowKind.TRACK_PRESET}:
        icon_w = row_icon_prefix_width(font.get_linesize())
        if kind == RowKind.CONFIG_HEADER:
            suffix_w = font.size("*")[0] if state.config_dirty else 0
            return fit_path_label_to_width(font, text, budget - icon_w - suffix_w)
        return fit_counter_label_to_width(font, text, budget - icon_w)
    if kind == RowKind.TRACK_HEADER:
        stem = row_slot(state, index)
        assert stem is not None
        expanded = state.tracks[stem].expanded
        return (
            _track_header_layer_prefix(state, index)
            + _fit_track_header_stem(
                font, state, index, max_content_width=max_content_width
            )
            + _track_header_expand_suffix(expanded)
        )
    if kind == RowKind.RENDER_SECTION_GAP:
        return ""
    if kind == RowKind.TIMELINE_LAYER_HINT:
        return TIMELINE_LAYER_HINT_TEXT
    if kind in {RowKind.LAYER_MANAGEMENT_ADD, RowKind.LAYER_MANAGEMENT_DELETE}:
        return _row_text(state, index)
    if kind == RowKind.RENDER_OVERLAY_HEADER:
        expanded = state.render_overlay.expanded
        return (
            _render_overlay_header_prefix()
            + "OVERLAY"
            + _track_header_expand_suffix(expanded)
        )
    if kind == RowKind.RENDER_POST_FX_HEADER:
        expanded = state.render_post_fx.expanded
        return (
            _render_post_fx_header_prefix()
            + "POST FX"
            + _track_header_expand_suffix(expanded)
        )
    if kind == RowKind.RENDER_TIMELINE_HEADER:
        expanded = state.render_timeline.expanded
        return (
            _render_timeline_header_prefix()
            + "TIMELINE"
            + _track_header_expand_suffix(expanded)
        )
    if kind in LABELED_SUB_ROW_KINDS:
        return _labeled_sub_row_prefix(state, index) + _fit_labeled_sub_row_value(
            font, state, index, max_content_width=max_content_width
        )
    return fit_text_to_width(font, text, budget)


def _row_indent(state: TuningViewState, index: int) -> int:
    kind = row_kind(state, index)
    if kind in {
        RowKind.TRACK_HEADER,
        RowKind.RENDER_OVERLAY_HEADER,
        RowKind.RENDER_POST_FX_HEADER,
        RowKind.RENDER_TIMELINE_HEADER,
    }:
        return 0
    if kind == RowKind.RENDER_SECTION_GAP:
        return 0
    if kind == RowKind.TIMELINE_LAYER_HINT:
        return 0
    if kind == RowKind.LAYER_MANAGEMENT_ADD:
        return 0
    if kind == RowKind.LAYER_MANAGEMENT_DELETE:
        return TREE_INDENT
    if kind == RowKind.TRACK_EFFECT:
        return TREE_INDENT * 2
    if kind in RENDER_OVERLAY_TITLE_NESTED_KINDS | RENDER_OVERLAY_BODY_NESTED_KINDS:
        return TREE_INDENT * 2
    if kind in {
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_STEM,
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
        RowKind.TRACK_BEAT,
        RowKind.TRACK_EFFECTS_HEADER,
    } | RENDER_OVERLAY_SUB_ROW_KINDS | RENDER_POST_FX_SUB_ROW_KINDS:
        return TREE_INDENT
    return 0


def _track_disabled(state: TuningViewState, slot: str) -> bool:
    return not state.tracks[slot].visible


def _row_highlight_color(state: TuningViewState, index: int) -> tuple[int, int, int]:
    stem = row_slot(state, index)
    if stem is not None and _track_disabled(state, stem):
        return HIGHLIGHT_MUTED
    return HIGHLIGHT


def _row_has_tree_focus(state: TuningViewState, index: int) -> bool:
    if state.timeline_submenu_focused:
        return False
    return index == state.focus_index


def _row_value_color(state: TuningViewState, index: int) -> tuple[int, int, int]:
    """Return the VALUE-role color for a row (before label/value split rendering)."""
    kind = row_kind(state, index)
    if kind == RowKind.TIMELINE_LAYER_HINT:
        return DISABLED

    if kind == RowKind.LAYER_MANAGEMENT_ADD:
        return LABEL
    if kind == RowKind.LAYER_MANAGEMENT_DELETE:
        if len(state.layer_z_order) == 1:
            return DISABLED
        return LABEL

    stem = row_slot(state, index)
    if kind == RowKind.CONFIG_HEADER:
        if state.solo_active:
            return DISABLED
        return LABEL

    if kind in {RowKind.RENDER_OVERLAY_HEADER, *RENDER_OVERLAY_ALL_SUB_ROW_KINDS}:
        if not state.render_overlay.enabled:
            return DISABLED

    if kind in {
        RowKind.RENDER_POST_FX_HEADER,
        *RENDER_POST_FX_SUB_ROW_KINDS,
    }:
        if not state.render_post_fx.enabled:
            return DISABLED

    if kind == RowKind.RENDER_TIMELINE_HEADER:
        if not state.render_timeline.enabled:
            return DISABLED

    if (
        kind == RowKind.TRACK_PRESET
        and stem is not None
        and state.tracks[stem].preset_empty
    ):
        return DISABLED

    if stem is not None and state.move_mode_slot == stem:
        return MOVE_MODE

    if _row_has_tree_focus(state, index):
        return _row_highlight_color(state, index)

    if stem is not None and _track_disabled(state, stem):
        return DISABLED

    if (
        stem is not None
        and state.tracks[stem].locked
        and row_blocked_by_layer_lock(kind)
    ):
        return LOCKED

    return VALUE


def _row_bg_color(state: TuningViewState, index: int) -> tuple[int, int, int] | None:
    stem = row_slot(state, index)
    if stem is not None and state.move_mode_slot == stem:
        return MOVE_MODE
    if _row_has_tree_focus(state, index):
        return _row_highlight_color(state, index)
    return None


@dataclass(frozen=True)
class PanelScrollMetrics:
    scrollable_indices: list[int]
    header_indices: list[int]
    row_stride: int
    scroll_content_h: int
    header_block_h: int
    footer_block_h: int
    max_panel_h: int
    natural_h: int
    panel_h: int
    scroll_viewport_h: int
    needs_scroll: bool
    show_scrollbar: bool


@dataclass(frozen=True)
class PanelToastLayout:
    toast_y: int | None


def panel_toast_layout(
    *,
    panel_h: int,
    padding: int,
    line_h: int,
    toast_active: bool,
) -> PanelToastLayout:
    """Place toast on the panel bottom."""
    toast_y = panel_h - padding - line_h if toast_active else None
    return PanelToastLayout(toast_y=toast_y)


@dataclass(frozen=True)
class PanelHelpHintLayout:
    x: int
    y: int


def panel_help_hint_layout(
    *,
    panel_w: int,
    panel_h: int,
    padding: int,
    line_h: int,
    hint_width: int,
    show_scrollbar: bool,
) -> PanelHelpHintLayout:
    """Bottom-right help CTA; shifts left when the scrollbar column is visible."""
    right_reserve = (
        SCROLLBAR_WIDTH + SCROLLBAR_CONTENT_GAP if show_scrollbar else 0
    )
    return PanelHelpHintLayout(
        x=panel_w - padding - right_reserve - hint_width,
        y=panel_h - padding - line_h,
    )


def scroll_metrics(
    *,
    visible_indices: list[int],
    first_scrollable_visible: int | None,
    line_h: int,
    line_gap: int,
    padding: int,
    header_gap: int,
    toast_active: bool,
    max_panel_h: int,
) -> PanelScrollMetrics:
    if first_scrollable_visible is not None:
        split_pos = visible_indices.index(first_scrollable_visible)
        header_indices = visible_indices[:split_pos]
        scrollable_indices = visible_indices[split_pos:]
    else:
        header_indices = list(visible_indices)
        scrollable_indices = []

    row_stride = line_h + line_gap
    n_scroll = len(scrollable_indices)
    scroll_content_h = (
        n_scroll * line_h + max(0, n_scroll - 1) * line_gap if n_scroll else 0
    )

    n_header = len(header_indices)
    header_rows_h = (
        n_header * line_h + max(0, n_header - 1) * line_gap if n_header else 0
    )
    header_block_h = header_rows_h
    if scrollable_indices:
        header_block_h += header_gap

    footer_block_h = line_gap + line_h if toast_active else 0

    visible_count = len(visible_indices)
    natural_h = (
        visible_count * line_h
        + max(0, visible_count - 1) * line_gap
        + (header_gap if first_scrollable_visible is not None else 0)
        + padding * 2
    )
    if toast_active:
        natural_h += line_gap + line_h

    needs_scroll = natural_h > max_panel_h
    if needs_scroll:
        scroll_viewport_h = max(
            0, max_panel_h - padding * 2 - header_block_h - footer_block_h
        )
        panel_h = min(natural_h, max_panel_h)
        show_scrollbar = scroll_content_h > scroll_viewport_h
    else:
        scroll_viewport_h = scroll_content_h
        panel_h = natural_h
        show_scrollbar = False

    return PanelScrollMetrics(
        scrollable_indices=scrollable_indices,
        header_indices=header_indices,
        row_stride=row_stride,
        scroll_content_h=scroll_content_h,
        header_block_h=header_block_h,
        footer_block_h=footer_block_h,
        max_panel_h=max_panel_h,
        natural_h=natural_h,
        panel_h=panel_h,
        scroll_viewport_h=scroll_viewport_h,
        needs_scroll=needs_scroll,
        show_scrollbar=show_scrollbar,
    )


def panel_content_max_width(
    *,
    index: int,
    scrollable_indices: frozenset[int],
    show_scrollbar: bool,
) -> int:
    """Content width budget for a row; scrollable rows reserve the scrollbar column."""
    if show_scrollbar and index in scrollable_indices:
        return PANEL_CONTENT_MAX_WIDTH - SCROLLBAR_WIDTH
    return PANEL_CONTENT_MAX_WIDTH


def clip_rect_to_surface(
    rect: tuple[int, int, int, int],
    surface: pygame.Surface,
) -> tuple[int, int, int, int] | None:
    """Intersection of rect with surface bounds (for subsurface-safe panel_rect)."""
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return None
    sw, sh = surface.get_width(), surface.get_height()
    left = max(x, 0)
    top = max(y, 0)
    right = min(x + w, sw)
    bottom = min(y + h, sh)
    clip_w = right - left
    clip_h = bottom - top
    if clip_w <= 0 or clip_h <= 0:
        return None
    return (left, top, clip_w, clip_h)


class TuningOverlay:
    """Tree-style live tuning panel; holds visible after input, then fades out."""

    def __init__(
        self,
        *,
        anchor: Anchor = "topleft",
        margin: tuple[int, int] | None = None,
        font_size: int | None = None,
        padding: int | None = None,
        line_gap: int | None = None,
    ) -> None:
        metrics = tuning_ui_metrics()
        if margin is None:
            margin = (metrics.margin, metrics.margin)
        if font_size is None:
            font_size = metrics.font_size
        if padding is None:
            padding = metrics.padding
        if line_gap is None:
            line_gap = metrics.line_gap
        self._anchor = anchor
        self._margin = margin
        self._font_size = font_size
        self._padding = padding
        self._line_gap = line_gap
        self._hold_idle_sec = HOLD_IDLE_SEC
        self._fade_duration_sec = FADE_DURATION_SEC
        self._idle_sec = self._hold_idle_sec + self._fade_duration_sec + 1.0
        self._visibility = 0.0
        self._font: pygame.font.Font | None = None
        self._panel_rect: tuple[int, int, int, int] | None = None
        self._scroll_y = 0

    def _clamp_scroll(self, scroll_content_h: int, viewport_h: int) -> None:
        max_scroll = max(0, scroll_content_h - viewport_h)
        if self._scroll_y < 0:
            self._scroll_y = 0
        elif self._scroll_y > max_scroll:
            self._scroll_y = max_scroll

    def _ensure_focus_visible(
        self,
        state: TuningViewState,
        scrollable_indices: list[int],
        row_stride: int,
        viewport_h: int,
        line_h: int,
    ) -> None:
        try:
            row_index = scrollable_indices.index(state.focus_index)
        except ValueError:
            return
        row_y = row_index * row_stride
        if row_y < self._scroll_y:
            self._scroll_y = row_y
        elif row_y + line_h > self._scroll_y + viewport_h:
            self._scroll_y = row_y + line_h - viewport_h
        n = len(scrollable_indices)
        scroll_content_h = n * row_stride - self._line_gap if n > 0 else 0
        self._clamp_scroll(scroll_content_h, viewport_h)

    def notify_input(self) -> None:
        self._idle_sec = 0.0
        self._visibility = 1.0

    def hide_immediately(self) -> None:
        self._idle_sec = self._hold_idle_sec + self._fade_duration_sec + 1.0
        self._visibility = 0.0
        self._scroll_y = 0

    def is_visible(self) -> bool:
        return self._visibility > 0.01

    @property
    def visibility(self) -> float:
        return self._visibility

    def update(self, dt_sec: float) -> None:
        self._idle_sec += dt_sec
        hold_idle_sec = self._hold_idle_sec
        if self._idle_sec <= hold_idle_sec:
            self._visibility = 1.0
        elif self._fade_duration_sec <= 0:
            self._visibility = 0.0
        elif self._idle_sec <= hold_idle_sec + self._fade_duration_sec:
            fade_t = (self._idle_sec - hold_idle_sec) / self._fade_duration_sec
            self._visibility = 1.0 - fade_t
        else:
            self._visibility = 0.0

    def _font_get(self) -> pygame.font.Font:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", self._font_size)
        return self._font

    @property
    def panel_rect(self) -> tuple[int, int, int, int] | None:
        """Top-left x, y, width, height of the last drawn panel, if any."""
        return self._panel_rect

    def _blit_row(
        self,
        panel: pygame.Surface,
        *,
        state: TuningViewState,
        index: int,
        draw_index: int,
        row_surfaces: list[pygame.Surface],
        row_time_surfaces: list[pygame.Surface | None],
        y: int,
        text_alpha: int,
        panel_w: int,
        line_h: int,
    ) -> None:
        surf = row_surfaces[draw_index]
        bg = _row_bg_color(state, index)
        if bg is not None:
            bg_alpha = int(FOCUS_ROW_BG_ALPHA * self._visibility)
            blit_tint(
                panel,
                (self._padding, y, panel_w - self._padding * 2, line_h),
                bg,
                alpha=bg_alpha,
            )

        indent = self._padding + _row_indent(state, index)
        if text_alpha >= 2:
            surf.set_alpha(text_alpha)
            panel.blit(surf, (indent, y))
            time_surf = row_time_surfaces[draw_index]
            if time_surf is not None:
                time_surf.set_alpha(text_alpha)
                panel.blit(time_surf, (indent + surf.get_width(), y))

    def _draw_scrollbar(
        self,
        panel: pygame.Surface,
        *,
        panel_w: int,
        scroll_top: int,
        scroll_viewport_h: int,
        scroll_content_h: int,
        border_alpha: int,
    ) -> None:
        if border_alpha < 2:
            return
        track_x = panel_w - SCROLLBAR_WIDTH
        track_y = scroll_top
        track_bottom = track_y + scroll_viewport_h
        track_color = (*SCROLLBAR_TRACK, border_alpha)
        pygame.draw.line(panel, track_color, (track_x, track_y), (track_x, track_bottom))
        pygame.draw.line(
            panel,
            track_color,
            (track_x + SCROLLBAR_WIDTH - 1, track_y),
            (track_x + SCROLLBAR_WIDTH - 1, track_bottom),
        )
        max_scroll = scroll_content_h - scroll_viewport_h
        if max_scroll <= 0:
            return
        thumb_h = max(8, int(scroll_viewport_h * scroll_viewport_h / scroll_content_h))
        thumb_travel = scroll_viewport_h - thumb_h
        thumb_y = track_y + int(self._scroll_y * thumb_travel / max_scroll)
        pygame.draw.rect(
            panel,
            (*SCROLLBAR_THUMB, border_alpha),
            (track_x, thumb_y, SCROLLBAR_WIDTH, thumb_h),
        )

    def draw(
        self,
        surface: pygame.Surface,
        state: TuningViewState,
        *,
        timeline_panel_open: bool = False,
    ) -> None:
        self._panel_rect = None
        if self._visibility <= 0.01 or row_count(state) == 0:
            return

        font = self._font_get()
        line_h = font.get_linesize()
        visible_indices = visible_row_indices(state)
        visible_count = len(visible_indices)
        first_scrollable_visible = next(
            (
                index
                for index in visible_indices
                if row_kind(state, index) not in HEADER_ROW_KINDS
            ),
            None,
        )
        toast_active = bool(state.toast_message and state.toast_remaining_sec > 0)

        header_gap = line_h + self._line_gap
        _, margin_y = self._margin
        max_panel_h = surface.get_height() - margin_y * 2
        if timeline_panel_open:
            from cleave.viz.timeline_overlay import timeline_viewport_reserve_px

            max_panel_h -= timeline_viewport_reserve_px(len(state.layer_z_order))
        metrics = scroll_metrics(
            visible_indices=visible_indices,
            first_scrollable_visible=first_scrollable_visible,
            line_h=line_h,
            line_gap=self._line_gap,
            padding=self._padding,
            header_gap=header_gap,
            toast_active=toast_active,
            max_panel_h=max_panel_h,
        )
        scrollable_indices = frozenset(metrics.scrollable_indices)

        row_surfaces: list[pygame.Surface] = []
        row_time_surfaces: list[pygame.Surface | None] = []
        row_widths: list[int] = []
        for index in visible_indices:
            max_content_width = panel_content_max_width(
                index=index,
                scrollable_indices=scrollable_indices,
                show_scrollbar=metrics.show_scrollbar,
            )
            kind = row_kind(state, index)
            indent = self._padding + _row_indent(state, index)
            color = _row_value_color(state, index)

            if kind == RowKind.TRANSPORT:
                icons_surf = render_transport_icons(
                    color=color,
                    line_height=line_h,
                    paused=state.paused,
                )
                time_text = f" [{format_mmss(state.position_sec)}]"
                time_surf = font.render(time_text, True, color)
                row_surfaces.append(icons_surf)
                row_time_surfaces.append(time_surf)
                row_widths.append(
                    indent + icons_surf.get_width() + time_surf.get_width()
                )
            elif kind == RowKind.TRACK_HEADER:
                stem = row_slot(state, index)
                block = state.tracks[stem] if stem is not None else None
                enabled = block.visible if block is not None else True
                solo = stem is not None and state.solo_slot == stem
                locked = block.locked if block is not None else False
                prefix_surf = render_visibility_icon(
                    enabled=enabled, solo=solo, line_height=line_h
                )
                layer_prefix = _track_header_layer_prefix(state, index)
                stem_text = _fit_track_header_stem(
                    font, state, index, max_content_width=max_content_width
                )
                expanded = block.expanded if block is not None else False
                label_surf = _render_track_header_label(
                    font,
                    layer_prefix=layer_prefix,
                    stem_text=stem_text,
                    value_color=color,
                    expanded=expanded,
                    locked=locked,
                    line_height=line_h,
                )
                row_surfaces.append(prefix_surf)
                row_time_surfaces.append(label_surf)
                row_widths.append(
                    indent + prefix_surf.get_width() + label_surf.get_width()
                )
            elif kind == RowKind.RENDER_OVERLAY_HEADER:
                block_ro = state.render_overlay
                prefix_surf = render_visibility_icon(
                    enabled=block_ro.enabled,
                    solo=block_ro.solo,
                    line_height=line_h,
                )
                label_surf = _render_track_header_label(
                    font,
                    layer_prefix=_render_overlay_header_prefix(),
                    stem_text="OVERLAY",
                    value_color=color,
                    expanded=block_ro.expanded,
                    locked=False,
                    line_height=line_h,
                )
                row_surfaces.append(prefix_surf)
                row_time_surfaces.append(label_surf)
                row_widths.append(
                    indent + prefix_surf.get_width() + label_surf.get_width()
                )
            elif kind == RowKind.RENDER_POST_FX_HEADER:
                block_pp = state.render_post_fx
                prefix_surf = render_visibility_icon(
                    enabled=block_pp.enabled,
                    solo=block_pp.solo,
                    line_height=line_h,
                )
                label_surf = _render_track_header_label(
                    font,
                    layer_prefix=_render_post_fx_header_prefix(),
                    stem_text="POST FX",
                    value_color=color,
                    expanded=block_pp.expanded,
                    locked=False,
                    line_height=line_h,
                )
                row_surfaces.append(prefix_surf)
                row_time_surfaces.append(label_surf)
                row_widths.append(
                    indent + prefix_surf.get_width() + label_surf.get_width()
                )
            elif kind == RowKind.RENDER_TIMELINE_HEADER:
                block_tl = state.render_timeline
                prefix_surf = render_visibility_icon(
                    enabled=block_tl.enabled,
                    solo=False,
                    line_height=line_h,
                )
                label_surf = _render_track_header_label(
                    font,
                    layer_prefix=_render_timeline_header_prefix(),
                    stem_text="TIMELINE",
                    value_color=color,
                    expanded=block_tl.expanded,
                    locked=False,
                    line_height=line_h,
                )
                row_surfaces.append(prefix_surf)
                row_time_surfaces.append(label_surf)
                row_widths.append(
                    indent + prefix_surf.get_width() + label_surf.get_width()
                )
            elif kind == RowKind.RENDER_SECTION_GAP:
                gap_surf = pygame.Surface((1, line_h), pygame.SRCALPHA)
                row_surfaces.append(gap_surf)
                row_time_surfaces.append(None)
                row_widths.append(indent + gap_surf.get_width())
            elif kind in {
                RowKind.CONFIG_HEADER,
                RowKind.TRACK_PRESET_DIR,
                RowKind.TRACK_PRESET,
            }:
                if kind == RowKind.TRACK_PRESET_DIR:
                    glyph = FOLDER_GLYPH
                    icon_color = PRESET_ICON
                else:
                    glyph = FILE_GLYPH
                    icon_color = PRESET_FILE_ICON
                icon_surf = render_glyph(glyph, color=icon_color, line_height=line_h)
                if kind == RowKind.CONFIG_HEADER:
                    path = fit_row_text(
                        font, state, index, max_content_width=max_content_width
                    )
                    label_surf = _render_label_value_row(
                        font,
                        prefix=path,
                        value="*" if state.config_dirty else "",
                        value_color=CONFIG_DIRTY,
                        line_height=line_h,
                    )
                else:
                    label = fit_row_text(
                        font, state, index, max_content_width=max_content_width
                    )
                    label_surf = font.render(label, True, color)
                row_surfaces.append(icon_surf)
                row_time_surfaces.append(label_surf)
                row_widths.append(
                    indent + icon_surf.get_width() + label_surf.get_width()
                )
            elif kind == RowKind.TRACK_EFFECTS_HEADER:
                stem = row_slot(state, index)
                assert stem is not None
                block = state.tracks[stem]
                surf = _render_label_value_row(
                    font,
                    prefix=_effects_header_prefix(),
                    value=_effects_header_expand_value(block.effects_expanded),
                    value_color=color,
                    line_height=line_h,
                )
                row_surfaces.append(surf)
                row_time_surfaces.append(None)
                row_widths.append(indent + surf.get_width())
            elif kind in {
                RowKind.RENDER_OVERLAY_TITLE_HEADER,
                RowKind.RENDER_OVERLAY_BODY_HEADER,
            }:
                block_ro = state.render_overlay
                if kind == RowKind.RENDER_OVERLAY_TITLE_HEADER:
                    prefix = _render_overlay_text_header_prefix("title")
                    expanded = block_ro.title_expanded
                else:
                    prefix = _render_overlay_text_header_prefix("body")
                    expanded = block_ro.body_expanded
                surf = _render_label_value_row(
                    font,
                    prefix=prefix,
                    value=_render_overlay_text_header_expand_value(expanded),
                    value_color=color,
                    line_height=line_h,
                )
                row_surfaces.append(surf)
                row_time_surfaces.append(None)
                row_widths.append(indent + surf.get_width())
            elif kind in LABELED_SUB_ROW_KINDS:
                prefix = _labeled_sub_row_prefix(state, index)
                value = _fit_labeled_sub_row_value(
                    font, state, index, max_content_width=max_content_width
                )
                surf = _render_label_value_row(
                    font,
                    prefix=prefix,
                    value=value,
                    value_color=color,
                    line_height=line_h,
                )
                row_surfaces.append(surf)
                row_time_surfaces.append(None)
                row_widths.append(indent + surf.get_width())
            elif kind in {
                RowKind.LAYER_MANAGEMENT_ADD,
                RowKind.LAYER_MANAGEMENT_DELETE,
            }:
                label = _row_text(state, index)
                label_color = _row_value_color(state, index)
                surf = _render_label_value_row(
                    font,
                    prefix=label,
                    value="",
                    value_color=label_color,
                    prefix_color=label_color,
                    line_height=line_h,
                )
                row_surfaces.append(surf)
                row_time_surfaces.append(None)
                row_widths.append(indent + surf.get_width())
            else:
                text = fit_row_text(
                    font, state, index, max_content_width=max_content_width
                )
                surf = font.render(text, True, color)
                row_surfaces.append(surf)
                row_time_surfaces.append(None)
                row_widths.append(indent + surf.get_width())

        toast_surf: pygame.Surface | None = None
        if toast_active:
            assert state.toast_message is not None
            toast_text = fit_text_to_width(
                font, state.toast_message, PANEL_CONTENT_MAX_WIDTH
            )
            toast_surf = font.render(toast_text, True, DISABLED)

        content_w = max(row_widths) if row_widths else 0
        if toast_surf is not None:
            content_w = max(content_w, toast_surf.get_width())
        content_w = min(content_w, PANEL_CONTENT_MAX_WIDTH)
        panel_w = content_w + self._padding * 2
        panel_h = metrics.panel_h

        alpha = int(BACKGROUND_ALPHA * self._visibility)
        if alpha < 2:
            return

        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((*BACKGROUND, alpha))

        text_alpha = int(255 * self._visibility)
        index_to_draw = {index: draw_index for draw_index, index in enumerate(visible_indices)}

        if metrics.needs_scroll:
            self._ensure_focus_visible(
                state,
                metrics.scrollable_indices,
                metrics.row_stride,
                metrics.scroll_viewport_h,
                line_h,
            )
            header_y = self._padding
            for row_index, index in enumerate(metrics.header_indices):
                y = header_y + row_index * metrics.row_stride
                self._blit_row(
                    panel,
                    state=state,
                    index=index,
                    draw_index=index_to_draw[index],
                    row_surfaces=row_surfaces,
                    row_time_surfaces=row_time_surfaces,
                    y=y,
                    text_alpha=text_alpha,
                    panel_w=panel_w,
                    line_h=line_h,
                )

            scroll_top = self._padding + metrics.header_block_h
            scroll_bottom = scroll_top + metrics.scroll_viewport_h
            old_clip = panel.get_clip()
            clip_right_reserve = (
                SCROLLBAR_WIDTH + SCROLLBAR_CONTENT_GAP
                if metrics.show_scrollbar
                else self._padding
            )
            clip_w = panel_w - self._padding - clip_right_reserve
            panel.set_clip(
                pygame.Rect(self._padding, scroll_top, clip_w, metrics.scroll_viewport_h)
            )
            for row_index, index in enumerate(metrics.scrollable_indices):
                local_y = row_index * metrics.row_stride
                y = scroll_top + local_y - self._scroll_y
                if y + line_h <= scroll_top or y >= scroll_bottom:
                    continue
                self._blit_row(
                    panel,
                    state=state,
                    index=index,
                    draw_index=index_to_draw[index],
                    row_surfaces=row_surfaces,
                    row_time_surfaces=row_time_surfaces,
                    y=y,
                    text_alpha=text_alpha,
                    panel_w=panel_w,
                    line_h=line_h,
                )
            panel.set_clip(old_clip)

            if metrics.show_scrollbar:
                self._draw_scrollbar(
                    panel,
                    panel_w=panel_w,
                    scroll_top=scroll_top,
                    scroll_viewport_h=metrics.scroll_viewport_h,
                    scroll_content_h=metrics.scroll_content_h,
                    border_alpha=int(255 * self._visibility),
                )
        else:
            row_y = self._padding
            for draw_index, index in enumerate(visible_indices):
                if index == first_scrollable_visible:
                    row_y += header_gap
                self._blit_row(
                    panel,
                    state=state,
                    index=index,
                    draw_index=draw_index,
                    row_surfaces=row_surfaces,
                    row_time_surfaces=row_time_surfaces,
                    y=row_y,
                    text_alpha=text_alpha,
                    panel_w=panel_w,
                    line_h=line_h,
                )
                row_y += line_h + self._line_gap

        toast_layout = panel_toast_layout(
            panel_h=panel_h,
            padding=self._padding,
            line_h=line_h,
            toast_active=toast_active,
        )

        if toast_surf is not None and text_alpha >= 2 and toast_layout.toast_y is not None:
            toast_surf.set_alpha(text_alpha)
            panel.blit(toast_surf, (self._padding, toast_layout.toast_y))

        if text_alpha >= 2:
            help_hint = font.render("h - help", True, LABEL)
            help_hint.set_alpha(text_alpha)
            hint_layout = panel_help_hint_layout(
                panel_w=panel_w,
                panel_h=panel_h,
                padding=self._padding,
                line_h=line_h,
                hint_width=help_hint.get_width(),
                show_scrollbar=metrics.show_scrollbar,
            )
            panel.blit(help_hint, (hint_layout.x, hint_layout.y))

        border_alpha = int(255 * self._visibility)
        if border_alpha >= 2 and BORDER_WIDTH > 0:
            pygame.draw.rect(
                panel,
                (*BORDER_COLOR, border_alpha),
                panel.get_rect(),
                width=BORDER_WIDTH,
            )

        mx, my = self._margin
        if self._anchor == "topleft":
            pos = (mx, my)
        else:
            pos = (mx, surface.get_height() - panel_h - my)

        surface.blit(panel, pos)
        self._panel_rect = clip_rect_to_surface(
            (pos[0], pos[1], panel_w, panel_h),
            surface,
        )
