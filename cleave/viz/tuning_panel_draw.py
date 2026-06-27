"""Pygame draw path for the live tuning tree panel.

Row typography: LABEL prefixes, VALUE defaults, DISABLED/LOCKED state overrides.
See cleave/viz/theme.py and .cursor/rules/live-tuning-ui.mdc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pygame

from cleave.config_schema import (
    hard_cut_enabled_display,
    preset_start_clean_display,
    preset_switching_display,
    ui_fade_display,
    DEFAULT_UI_FADE_SEC,
)
from cleave.extract import stem_control_label, stem_overlay_header
from cleave.viz.row_semantics import (
    LABELED_SUB_ROW_KINDS,
    PRESET_SWITCHING_SUBMENU_KINDS,
    PRESET_SWITCHING_HARD_CUT_SUBMENU_KINDS,
    RENDER_OVERLAY_ALL_SUB_ROW_KINDS,
    RENDER_OVERLAY_BODY_NESTED_KINDS,
    RENDER_OVERLAY_SUB_ROW_KINDS,
    RENDER_OVERLAY_TITLE_NESTED_KINDS,
    RENDER_POST_FX_SUB_ROW_KINDS,
    RowKind,
    row_blocked_by_layer_lock,
    row_is_pinned,
)
from cleave.viz.fonts import render_overlay_font_display
from cleave.viz.text_fit import (
    fit_counter_label_to_width,
    fit_path_label_to_width,
    fit_text_to_width,
)
from cleave.viz.frame_rate import format_fps_display
from cleave.viz.playback import format_mmss
from cleave.viz.material_icons import (
    FILE_GLYPH,
    FOLDER_GLYPH,
    LOCK_GLYPH,
    SETTINGS_GLYPH,
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
    ACTION,
    BACKGROUND,
    BACKGROUND_ALPHA,
    BORDER_COLOR,
    BORDER_WIDTH,
    DISABLED,
    FADE_DURATION_SEC,
    FOCUS_ROW_BG_ALPHA,
    HIGHLIGHT,
    HIGHLIGHT_MUTED,
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
from cleave.viz.tuning_view_state import TrackBlock, TuningViewState
from cleave.viz.ui_tint import blit_tint

Anchor = Literal["topleft", "bottomleft"]

_tuning_ui = tuning_ui_metrics()
TREE_INDENT = _tuning_ui.tree_indent
TREE_BRANCH = "└"
ROW_ICON_SUFFIX_GAP = _tuning_ui.row_icon_suffix_gap


def track_sub_rows_visible(state: TuningViewState, slot: str) -> bool:
    return state.tracks[slot].expanded


def row_effect(
    state: TuningViewState, index: int
) -> tuple[str, str] | None:
    desc = state.layout.descriptor(index)
    if desc.kind != RowKind.TRACK_EFFECT:
        return None
    assert desc.effect_id is not None and desc.driver_slug is not None
    return desc.effect_id, desc.driver_slug


def _effect_pct(block: TrackBlock, effect_id: str, driver_slug: str) -> int:
    return block.effects.get(effect_id, {}).get(driver_slug, 0)


def _row_text(state: TuningViewState, index: int) -> str:
    kind = state.layout.kind(index)
    if kind == RowKind.CONFIG_HEADER:
        return state.active_config_label
    if kind == RowKind.TRANSPORT:
        return ""
    if kind == RowKind.RENDER_SECTION_GAP:
        return ""

    if kind == RowKind.PANEL_NOTIFICATION:
        return state.notification_message or ""

    if kind == RowKind.LAYER_MANAGEMENT_ADD:
        return "Add Layer"
    if kind == RowKind.LAYER_MANAGEMENT_DELETE:
        return f"{_layer_management_delete_prefix()}Delete Layer"

    if kind == RowKind.SETTINGS_HEADER:
        arrow = "▼" if state.settings.expanded else "▶"
        return f"Settings {arrow}"

    if kind == RowKind.SETTINGS_RENDER_MODE:
        return f"└─ render mode: {state.settings.render_mode}"

    if kind == RowKind.SETTINGS_UI_FADE:
        return f"└─ UI fade: {ui_fade_display(state.settings.ui_fade)}"

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

    stem = state.layout.slot(index)
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
    if kind == RowKind.TRACK_PRESET_SWITCHING:
        return f"└─ preset switching: {preset_switching_display(block.preset_switching)}"
    if kind == RowKind.TRACK_PRESET_SWITCHING_SCOPE:
        return (
            f"{_preset_switching_submenu_prefix()}scope: {block.preset_switching_scope}"
        )
    if kind == RowKind.TRACK_PRESET_DURATION:
        return (
            f"{_preset_switching_submenu_prefix()}preset duration: {block.preset_duration:g}s"
        )
    if kind == RowKind.TRACK_SOFT_CUT_DURATION:
        return (
            f"{_preset_switching_submenu_prefix()}soft cut: {block.soft_cut_duration:g}s"
        )
    if kind == RowKind.TRACK_EASTER_EGG:
        return (
            f"{_preset_switching_submenu_prefix()}easter egg: {block.easter_egg:.2f}"
        )
    if kind == RowKind.TRACK_PRESET_START_CLEAN:
        return (
            f"{_preset_switching_submenu_prefix()}start clean: "
            f"{preset_start_clean_display(block.preset_start_clean)}"
        )
    if kind == RowKind.TRACK_HARD_CUT_ENABLED:
        return (
            f"{_preset_switching_submenu_prefix()}hard cut: "
            f"{hard_cut_enabled_display(block.hard_cut_enabled)}"
        )
    if kind == RowKind.TRACK_HARD_CUT_DURATION:
        return (
            f"{_preset_switching_hard_cut_submenu_prefix()}hard cut min: "
            f"{block.hard_cut_duration:g}s"
        )
    if kind == RowKind.TRACK_HARD_CUT_SENSITIVITY:
        return (
            f"{_preset_switching_hard_cut_submenu_prefix()}hard cut sens: "
            f"{block.hard_cut_sensitivity:.2f}"
        )
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
    return f"{_effects_submenu_prefix()}{effect_id} ({driver_slug}): {pct}%"


def _labeled_sub_row_prefix(state: TuningViewState, index: int) -> str:
    kind = state.layout.kind(index)
    if kind == RowKind.TRACK_BLEND:
        return "└─ blend mode: "
    if kind == RowKind.TRACK_STEM:
        return "└─ driving stem: "
    if kind == RowKind.TRACK_OPACITY:
        return "└─ opacity: "
    if kind == RowKind.TRACK_BEAT:
        return "└─ beat sensitivity: "
    if kind == RowKind.TRACK_PRESET_SWITCHING:
        return "└─ preset switching: "
    if kind == RowKind.TRACK_PRESET_SWITCHING_SCOPE:
        return "  └─ scope: "
    if kind == RowKind.TRACK_PRESET_DURATION:
        return "  └─ preset duration: "
    if kind == RowKind.TRACK_SOFT_CUT_DURATION:
        return "  └─ soft cut: "
    if kind == RowKind.TRACK_EASTER_EGG:
        return "  └─ easter egg: "
    if kind == RowKind.TRACK_PRESET_START_CLEAN:
        return "  └─ start clean: "
    if kind == RowKind.TRACK_HARD_CUT_ENABLED:
        return "  └─ hard cut: "
    if kind == RowKind.TRACK_HARD_CUT_DURATION:
        return "    └─ hard cut min: "
    if kind == RowKind.TRACK_HARD_CUT_SENSITIVITY:
        return "    └─ hard cut sens: "
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
    if kind == RowKind.SETTINGS_RENDER_MODE:
        return "└─ render mode: "
    if kind == RowKind.SETTINGS_UI_FADE:
        return "└─ UI fade: "
    if kind == RowKind.RENDER_POST_FX_FADE_IN:
        return "└─ fade in: "
    if kind == RowKind.RENDER_POST_FX_FADE_OUT:
        return "└─ fade out: "
    assert kind == RowKind.TRACK_EFFECT
    effect = row_effect(state, index)
    assert effect is not None
    effect_id, driver_slug = effect
    return f"{_effects_submenu_prefix()}{effect_id} ({driver_slug}): "


def _labeled_sub_row_value(state: TuningViewState, index: int) -> str:
    kind = state.layout.kind(index)
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
    if kind == RowKind.SETTINGS_RENDER_MODE:
        return state.settings.render_mode
    if kind == RowKind.SETTINGS_UI_FADE:
        return ui_fade_display(state.settings.ui_fade)
    block_pp = state.render_post_fx
    if kind == RowKind.RENDER_POST_FX_FADE_IN:
        return f"{block_pp.fade_in:.1f}s"
    if kind == RowKind.RENDER_POST_FX_FADE_OUT:
        return f"{block_pp.fade_out:.1f}s"
    stem = state.layout.slot(index)
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
    if kind == RowKind.TRACK_PRESET_SWITCHING:
        return preset_switching_display(block.preset_switching)
    if kind == RowKind.TRACK_PRESET_SWITCHING_SCOPE:
        return block.preset_switching_scope
    if kind == RowKind.TRACK_PRESET_DURATION:
        return f"{block.preset_duration:g}s"
    if kind == RowKind.TRACK_SOFT_CUT_DURATION:
        return f"{block.soft_cut_duration:g}s"
    if kind == RowKind.TRACK_EASTER_EGG:
        return f"{block.easter_egg:.2f}"
    if kind == RowKind.TRACK_PRESET_START_CLEAN:
        return preset_start_clean_display(block.preset_start_clean)
    if kind == RowKind.TRACK_HARD_CUT_ENABLED:
        return hard_cut_enabled_display(block.hard_cut_enabled)
    if kind == RowKind.TRACK_HARD_CUT_DURATION:
        return f"{block.hard_cut_duration:g}s"
    if kind == RowKind.TRACK_HARD_CUT_SENSITIVITY:
        return f"{block.hard_cut_sensitivity:.2f}"
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
    kind = state.layout.kind(index)
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
    stem = state.layout.slot(index)
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


def tree_branch_prefix_width(font: pygame.font.Font) -> int:
    return font.size(TREE_BRANCH)[0]


def preset_row_prefix_width(font: pygame.font.Font, line_height: int) -> int:
    return tree_branch_prefix_width(font) + row_icon_prefix_width(line_height)


def _render_preset_row_prefix(
    font: pygame.font.Font,
    *,
    glyph: str,
    icon_color: tuple[int, int, int],
    line_height: int,
) -> pygame.Surface:
    tree_surf = font.render(TREE_BRANCH, True, LABEL)
    icon_surf = render_glyph(glyph, color=icon_color, line_height=line_height)
    total_w = tree_surf.get_width() + icon_surf.get_width()
    surf = pygame.Surface((total_w, line_height), pygame.SRCALPHA)
    surf.blit(tree_surf, (0, 0))
    surf.blit(icon_surf, (tree_surf.get_width(), 0))
    return surf


def _layer_management_delete_prefix() -> str:
    return "└─ "


def _preset_switching_submenu_prefix() -> str:
    return "  └─ "


def _preset_switching_hard_cut_submenu_prefix() -> str:
    return "    └─ "


def _effects_submenu_prefix() -> str:
    return "  └─ "


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
    stem = state.layout.slot(index)
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
    kind = state.layout.kind(index)
    indent = _row_indent(state, index)
    budget = max_content_width - indent
    text = _row_text(state, index)

    if kind in {RowKind.CONFIG_HEADER, RowKind.TRACK_PRESET_DIR, RowKind.TRACK_PRESET}:
        line_h = font.get_linesize()
        if kind == RowKind.CONFIG_HEADER:
            icon_w = row_icon_prefix_width(line_h)
            suffix_w = font.size("*")[0] if state.config_dirty else 0
            return fit_path_label_to_width(font, text, budget - icon_w - suffix_w)
        prefix_w = preset_row_prefix_width(font, line_h)
        return fit_counter_label_to_width(font, text, budget - prefix_w)
    if kind == RowKind.TRACK_HEADER:
        stem = state.layout.slot(index)
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
    if kind == RowKind.PANEL_NOTIFICATION:
        return fit_text_to_width(
            font, state.notification_message or "", budget
        )
    if kind in {RowKind.LAYER_MANAGEMENT_ADD, RowKind.LAYER_MANAGEMENT_DELETE}:
        return _row_text(state, index)
    if kind == RowKind.SETTINGS_HEADER:
        expanded = state.settings.expanded
        return "Settings " + _track_header_expand_suffix(expanded)
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
    kind = state.layout.kind(index)
    if kind in {
        RowKind.TRACK_HEADER,
        RowKind.RENDER_OVERLAY_HEADER,
        RowKind.RENDER_POST_FX_HEADER,
        RowKind.RENDER_TIMELINE_HEADER,
    }:
        return 0
    if kind == RowKind.RENDER_SECTION_GAP:
        return 0
    if kind == RowKind.PANEL_NOTIFICATION:
        return 0
    if kind == RowKind.LAYER_MANAGEMENT_ADD:
        return 0
    if kind == RowKind.LAYER_MANAGEMENT_DELETE:
        return TREE_INDENT
    if kind == RowKind.TRACK_EFFECT:
        return TREE_INDENT * 2
    if kind in PRESET_SWITCHING_HARD_CUT_SUBMENU_KINDS:
        return TREE_INDENT * 3
    if kind in PRESET_SWITCHING_SUBMENU_KINDS:
        return TREE_INDENT * 2
    if kind in RENDER_OVERLAY_TITLE_NESTED_KINDS | RENDER_OVERLAY_BODY_NESTED_KINDS:
        return TREE_INDENT * 2
    if kind in {
        RowKind.TRACK_PRESET_DIR,
        RowKind.TRACK_PRESET,
        RowKind.TRACK_PRESET_SWITCHING,
        RowKind.TRACK_STEM,
        RowKind.TRACK_BLEND,
        RowKind.TRACK_OPACITY,
        RowKind.TRACK_BEAT,
        RowKind.TRACK_EFFECTS_HEADER,
    } | RENDER_OVERLAY_SUB_ROW_KINDS | RENDER_POST_FX_SUB_ROW_KINDS | {
        RowKind.SETTINGS_RENDER_MODE,
        RowKind.SETTINGS_UI_FADE,
    }:
        return TREE_INDENT
    return 0


def _track_disabled(state: TuningViewState, slot: str) -> bool:
    return not state.tracks[slot].visible


def _row_highlight_color(state: TuningViewState, index: int) -> tuple[int, int, int]:
    stem = state.layout.slot(index)
    if stem is not None and _track_disabled(state, stem):
        return HIGHLIGHT_MUTED
    return HIGHLIGHT


def _row_has_tree_focus(state: TuningViewState, index: int) -> bool:
    if state.timeline_submenu_focused:
        return False
    return index == state.focus_index


def _row_value_color(state: TuningViewState, index: int) -> tuple[int, int, int]:
    """Return the VALUE-role color for a row (before label/value split rendering)."""
    kind = state.layout.kind(index)
    if kind == RowKind.PANEL_NOTIFICATION:
        return HIGHLIGHT

    if kind in {
        RowKind.CONFIG_HEADER,
        RowKind.LAYER_MANAGEMENT_ADD,
        RowKind.LAYER_MANAGEMENT_DELETE,
    }:
        if kind == RowKind.CONFIG_HEADER and state.solo_active:
            return DISABLED
        if kind == RowKind.LAYER_MANAGEMENT_DELETE and len(state.layer_z_order) == 1:
            return DISABLED
        return ACTION

    stem = state.layout.slot(index)

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

    if (
        stem is not None
        and kind in {RowKind.TRACK_PRESET_DIR, RowKind.TRACK_PRESET}
        and state.tracks[stem].preset_switching != "none"
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
    stem = state.layout.slot(index)
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
    max_panel_h: int
    natural_h: int
    panel_h: int
    scroll_viewport_h: int
    needs_scroll: bool
    show_scrollbar: bool


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


@dataclass(frozen=True)
class PanelFpsLayout:
    x: int
    y: int


def panel_fps_layout(
    *,
    panel_w: int,
    padding: int,
    text_width: int,
    show_scrollbar: bool,
) -> PanelFpsLayout:
    """Top-right FPS readout in the header region; shifts left for the scrollbar."""
    right_reserve = (
        SCROLLBAR_WIDTH + SCROLLBAR_CONTENT_GAP if show_scrollbar else 0
    )
    return PanelFpsLayout(
        x=panel_w - padding - right_reserve - text_width,
        y=padding,
    )


def scroll_metrics(
    *,
    visible_indices: list[int],
    first_scrollable_visible: int | None,
    line_h: int,
    line_gap: int,
    padding: int,
    header_gap: int,
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

    visible_count = len(visible_indices)
    natural_h = (
        visible_count * line_h
        + max(0, visible_count - 1) * line_gap
        + (header_gap if first_scrollable_visible is not None else 0)
        + padding * 2
    )

    needs_scroll = natural_h > max_panel_h
    if needs_scroll:
        scroll_viewport_h = max(
            0, max_panel_h - padding * 2 - header_block_h
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
        hold_idle_sec: float | None = None,
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
        self._hold_idle_sec = (
            DEFAULT_UI_FADE_SEC if hold_idle_sec is None else max(0.0, hold_idle_sec)
        )
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

    def set_hold_idle_sec(self, sec: float) -> None:
        if not isinstance(sec, (int, float)):
            return
        sec = max(0.0, sec)
        was_disabled = self._hold_idle_sec <= 0
        self._hold_idle_sec = sec
        if sec <= 0:
            if self._visibility > 0:
                self._visibility = 1.0
                self._idle_sec = 0.0
        elif was_disabled and self._visibility > 0:
            self._idle_sec = 0.0

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
        hold_idle_sec = self._hold_idle_sec
        if hold_idle_sec <= 0:
            return
        self._idle_sec += dt_sec
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
        if self._visibility <= 0.01 or len(state.layout) == 0:
            return

        font = self._font_get()
        line_h = font.get_linesize()
        visible_indices = state.layout.visible_indices(state)
        visible_count = len(visible_indices)
        first_scrollable_visible = next(
            (
                index
                for index in visible_indices
                if not row_is_pinned(state.layout.kind(index))
            ),
            None,
        )
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
            kind = state.layout.kind(index)
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
                stem = state.layout.slot(index)
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
            elif kind == RowKind.SETTINGS_HEADER:
                block = state.settings
                icon_surf = render_glyph(
                    SETTINGS_GLYPH, color=VALUE, line_height=line_h
                )
                label_surf = _render_label_value_row(
                    font,
                    prefix="Settings ",
                    value=_effects_header_expand_value(block.expanded),
                    value_color=color,
                    prefix_color=LABEL,
                    line_height=line_h,
                )
                row_surfaces.append(icon_surf)
                row_time_surfaces.append(label_surf)
                row_widths.append(
                    indent + icon_surf.get_width() + label_surf.get_width()
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
                    icon_surf = _render_preset_row_prefix(
                        font,
                        glyph=glyph,
                        icon_color=icon_color,
                        line_height=line_h,
                    )
                elif kind == RowKind.TRACK_PRESET:
                    glyph = FILE_GLYPH
                    icon_color = PRESET_FILE_ICON
                    icon_surf = _render_preset_row_prefix(
                        font,
                        glyph=glyph,
                        icon_color=icon_color,
                        line_height=line_h,
                    )
                else:
                    icon_surf = render_glyph(
                        FILE_GLYPH, color=PRESET_FILE_ICON, line_height=line_h
                    )
                if kind == RowKind.CONFIG_HEADER:
                    path = fit_row_text(
                        font, state, index, max_content_width=max_content_width
                    )
                    label_surf = _render_label_value_row(
                        font,
                        prefix=path,
                        value="*" if state.config_dirty else "",
                        value_color=CONFIG_DIRTY,
                        prefix_color=color,
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
                stem = state.layout.slot(index)
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
            elif kind == RowKind.LAYER_MANAGEMENT_DELETE:
                label_color = _row_value_color(state, index)
                surf = _render_label_value_row(
                    font,
                    prefix=_layer_management_delete_prefix(),
                    value="Delete Layer",
                    value_color=label_color,
                    line_height=line_h,
                )
                row_surfaces.append(surf)
                row_time_surfaces.append(None)
                row_widths.append(indent + surf.get_width())
            elif kind == RowKind.LAYER_MANAGEMENT_ADD:
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

        content_w = max(row_widths) if row_widths else 0
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

        if state.fps is not None and text_alpha >= 2:
            fps_surf = font.render(format_fps_display(state.fps), True, VALUE)
            fps_surf.set_alpha(text_alpha)
            fps_layout = panel_fps_layout(
                panel_w=panel_w,
                padding=self._padding,
                text_width=fps_surf.get_width(),
                show_scrollbar=metrics.show_scrollbar,
            )
            panel.blit(fps_surf, (fps_layout.x, fps_layout.y))

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
