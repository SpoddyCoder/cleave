"""Pygame draw path for the live tuning tree panel.

Row typography: LABEL prefixes, VALUE defaults, DISABLED/LOCKED state overrides.
See cleave/viz/theme.py and .cursor/rules/live-tuning-ui.mdc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import pygame

from cleave.config_schema import DEFAULT_UI_FADE_SEC
from cleave.viz.row_fields import (
    ROW_FIELDS,
    RowPresentStyle,
    composite_header_prefix_part,
    composite_header_suffix_part,
    expand_subheader_prefix,
    format_composite_header_expand_value,
    format_expand_subheader_value,
    format_row_value,
    labeled_row_prefix,
    row_composite_header_display_text,
    row_dynamic_labeled_display_text,
    row_dynamic_labeled_prefix,
    row_expand_subheader_display_text,
    row_full_line_display_text,
    row_labeled_display_text,
)
from cleave.extract import stem_overlay_header
from cleave.viz.row_sections import (
    RENDER_OVERLAY_SECTION_KINDS,
    RENDER_POST_FX_SECTION_KINDS,
    expand_arrow_glyph,
    row_tree_indent_depth,
)
from cleave.viz.row_semantics import (
    LABELED_SUB_ROW_KINDS,
    RowDescriptor,
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
    material_font,
    render_glyph,
    render_transport_icons,
    row_icon_prefix_width,
    track_header_lock_suffix_width,
    visibility_icon_slot_width,
)
from cleave.viz.ui_tint import draw_opaque_row_background
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
    panel_content_max_width_px,
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
from cleave.viz.overlay_profiler import OverlayDrawCounters
from cleave.viz.overlay_upload import (
    OverlayGpuState,
    UploadPlan,
    UploadSignature,
    clip_dirty_rects,
    upload_plan_for_signature,
)
from cleave.viz.tuning_panel_cache import (
    PanelSignature,
    RowRenderEntry,
    TuningPanelCache,
    ensure_row_surface,
    live_upload_signature,
    panel_signature,
    static_row_keys,
    tuning_upload_signature,
)
from cleave.viz.tuning_view_state import TuningViewState

Anchor = Literal["topleft", "bottomleft"]


def _render_text(
    font: pygame.font.Font,
    text: str,
    antialias: bool,
    color: tuple[int, int, int],
    *,
    counters: OverlayDrawCounters | None = None,
) -> pygame.Surface:
    if counters is not None:
        counters.font_renders += 1
    return font.render(text, antialias, color)


def _compose_surface(
    size: tuple[int, int],
    *,
    counters: OverlayDrawCounters | None = None,
    flags: int = pygame.SRCALPHA,
) -> pygame.Surface:
    if counters is not None:
        counters.surface_builds += 1
    return pygame.Surface(size, flags)


_tuning_ui = tuning_ui_metrics()
TREE_INDENT = _tuning_ui.tree_indent
TREE_BRANCH = "└"
ROW_ICON_SUFFIX_GAP = _tuning_ui.row_icon_suffix_gap


def track_sub_rows_visible(state: TuningViewState, slot: str) -> bool:
    return state.tracks[slot].expanded


def _row_text(state: TuningViewState, index: int) -> str:
    kind = state.layout.kind(index)
    if kind == RowKind.RENDER_SECTION_GAP:
        return ""

    desc = state.layout.descriptor(index)
    field = ROW_FIELDS.get(kind)
    if field is not None:
        if field.present_style == RowPresentStyle.LABELED_VALUE:
            return row_labeled_display_text(state, desc)
        if field.present_style == RowPresentStyle.EXPAND_SUBHEADER:
            return row_expand_subheader_display_text(state, desc)
        if field.present_style == RowPresentStyle.COMPOSITE_HEADER:
            return row_composite_header_display_text(state, desc)
        if field.present_style == RowPresentStyle.PATH_ICON:
            return format_row_value(state, desc)
        if field.present_style == RowPresentStyle.FULL_LINE:
            return row_full_line_display_text(state, desc)
        if field.present_style == RowPresentStyle.DYNAMIC:
            return row_dynamic_labeled_display_text(state, desc)
    return ""


def _labeled_sub_row_prefix(state: TuningViewState, index: int) -> str:
    kind = state.layout.kind(index)
    field = ROW_FIELDS.get(kind)
    if field is not None:
        if field.present_style == RowPresentStyle.LABELED_VALUE:
            return labeled_row_prefix(kind)
        if field.present_style == RowPresentStyle.DYNAMIC:
            return row_dynamic_labeled_prefix(state.layout.descriptor(index))
    return ""


def _labeled_sub_row_value(state: TuningViewState, index: int) -> str:
    kind = state.layout.kind(index)
    field = ROW_FIELDS.get(kind)
    if field is not None:
        if field.present_style == RowPresentStyle.LABELED_VALUE:
            return format_row_value(state, state.layout.descriptor(index))
        if field.present_style == RowPresentStyle.DYNAMIC:
            return format_row_value(state, state.layout.descriptor(index))
    return ""


def _fit_labeled_sub_row_value(
    font: pygame.font.Font,
    state: TuningViewState,
    index: int,
    *,
    max_content_width: int = PANEL_CONTENT_MAX_WIDTH,
    cache: TuningPanelCache | None = None,
) -> str:
    kind = state.layout.kind(index)
    budget = max_content_width - _row_indent(state, index)
    budget -= font.size(_labeled_sub_row_prefix(state, index))[0]
    value = _labeled_sub_row_value(state, index)
    if kind in {
        RowKind.RENDER_OVERLAY_TITLE_FONT,
        RowKind.RENDER_OVERLAY_BODY_FONT,
    }:
        if cache is None:
            return fit_counter_label_to_width(font, value, budget)
        return cache.fit_text_cached(
            "counter", fit_counter_label_to_width, font, value, budget
        )
    if cache is None:
        return fit_text_to_width(font, value, budget)
    return cache.fit_text_cached("text", fit_text_to_width, font, value, budget)


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
    counters: OverlayDrawCounters | None = None,
) -> pygame.Surface:
    prefix_surf = _render_text(
        font, prefix, True, prefix_color if prefix_color is not None else LABEL, counters=counters
    )
    value_surf = _render_text(font, value, True, value_color, counters=counters)
    label_w = prefix_surf.get_width() + value_surf.get_width()
    if suffix_surf is not None:
        label_w += suffix_gap + suffix_surf.get_width()

    label_surf = _compose_surface((label_w, line_height), counters=counters)
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


def _track_header_expand_suffix(state: TuningViewState, desc: RowDescriptor) -> str:
    return f" {format_composite_header_expand_value(state, desc)}"


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
    counters: OverlayDrawCounters | None = None,
) -> pygame.Surface:
    tree_surf = _render_text(font, TREE_BRANCH, True, LABEL, counters=counters)
    icon_surf = render_glyph(glyph, color=icon_color, line_height=line_height)
    total_w = tree_surf.get_width() + icon_surf.get_width()
    surf = _compose_surface((total_w, line_height), counters=counters)
    surf.blit(tree_surf, (0, 0))
    surf.blit(icon_surf, (tree_surf.get_width(), 0))
    return surf


def _fit_track_header_stem(
    font: pygame.font.Font,
    state: TuningViewState,
    index: int,
    *,
    max_content_width: int = PANEL_CONTENT_MAX_WIDTH,
    cache: TuningPanelCache | None = None,
) -> str:
    stem = state.layout.slot(index)
    assert stem is not None
    block = state.tracks[stem]
    locked = block.locked
    desc = RowDescriptor(RowKind.TRACK_HEADER, slot=stem)
    budget = max_content_width - _row_indent(state, index)
    budget -= track_header_prefix_width(font)
    budget -= font.size(_track_header_layer_prefix(state, index))[0]
    budget -= font.size(_track_header_expand_suffix(state, desc))[0]
    if locked:
        budget -= track_header_lock_suffix_width(font.get_linesize())
    stem_text = stem_overlay_header(block.stem)
    if cache is None:
        return fit_text_to_width(font, stem_text, budget)
    return cache.fit_text_cached("text", fit_text_to_width, font, stem_text, budget)


def _render_track_header_label(
    font: pygame.font.Font,
    *,
    layer_prefix: str,
    stem_text: str,
    value_color: tuple[int, int, int],
    expand_arrow: str,
    locked: bool,
    line_height: int,
    counters: OverlayDrawCounters | None = None,
) -> pygame.Surface:
    arrow = f" {expand_arrow}"
    prefix_surf = _render_text(font, layer_prefix, True, LABEL, counters=counters)
    stem_surf = _render_text(font, stem_text, True, value_color, counters=counters)
    arrow_surf = _render_text(font, arrow, True, value_color, counters=counters)
    lock_surf = (
        render_glyph(LOCK_GLYPH, color=LOCK_ICON, line_height=line_height)
        if locked
        else None
    )

    label_w = prefix_surf.get_width() + stem_surf.get_width() + arrow_surf.get_width()
    if lock_surf is not None:
        label_w += ROW_ICON_SUFFIX_GAP + lock_surf.get_width()

    label_surf = _compose_surface((label_w, line_height), counters=counters)
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
    cache: TuningPanelCache | None = None,
) -> str:
    """Fit row label to the shared panel content width (pixels)."""

    def _fit(
        fitter: str,
        fit_fn: Callable[[pygame.font.Font, str, int], str],
        text: str,
        budget: int,
    ) -> str:
        if cache is None:
            return fit_fn(font, text, budget)
        return cache.fit_text_cached(fitter, fit_fn, font, text, budget)

    kind = state.layout.kind(index)
    indent = _row_indent(state, index)
    budget = max_content_width - indent
    text = _row_text(state, index)

    field = ROW_FIELDS.get(kind)
    if field is not None and field.present_style == RowPresentStyle.PATH_ICON:
        line_h = font.get_linesize()
        if kind == RowKind.CONFIG_HEADER:
            icon_w = row_icon_prefix_width(line_h)
            suffix_w = font.size("*")[0] if state.config_dirty else 0
            return _fit(
                "path", fit_path_label_to_width, text, budget - icon_w - suffix_w
            )
        prefix_w = preset_row_prefix_width(font, line_h)
        return _fit("counter", fit_counter_label_to_width, text, budget - prefix_w)
    if kind == RowKind.TRACK_HEADER:
        stem = state.layout.slot(index)
        assert stem is not None
        desc = RowDescriptor(RowKind.TRACK_HEADER, slot=stem)
        return (
            _track_header_layer_prefix(state, index)
            + _fit_track_header_stem(
                font,
                state,
                index,
                max_content_width=max_content_width,
                cache=cache,
            )
            + _track_header_expand_suffix(state, desc)
        )
    if kind == RowKind.RENDER_SECTION_GAP:
        return ""
    if kind == RowKind.PANEL_NOTIFICATION:
        return _fit(
            "text", fit_text_to_width, state.notification_message or "", budget
        )
    field = ROW_FIELDS.get(kind)
    if field is not None and field.present_style == RowPresentStyle.FULL_LINE:
        if kind in {
            RowKind.LAYER_MANAGEMENT_ADD,
            RowKind.LAYER_MANAGEMENT_DELETE,
            RowKind.TRACK_USER_PRESET_ADD,
        }:
            return _row_text(state, index)
    if field is not None and field.present_style == RowPresentStyle.COMPOSITE_HEADER:
        return row_composite_header_display_text(state, state.layout.descriptor(index))
    if field is not None and field.present_style == RowPresentStyle.EXPAND_SUBHEADER:
        return row_expand_subheader_display_text(state, state.layout.descriptor(index))
    if kind in LABELED_SUB_ROW_KINDS:
        return _labeled_sub_row_prefix(state, index) + _fit_labeled_sub_row_value(
            font,
            state,
            index,
            max_content_width=max_content_width,
            cache=cache,
        )
    return _fit("text", fit_text_to_width, text, budget)


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
    return TREE_INDENT * row_tree_indent_depth(kind)


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
        RowKind.TRACK_USER_PRESET_ADD,
    }:
        if kind == RowKind.CONFIG_HEADER and state.solo_active:
            return DISABLED
        if kind == RowKind.LAYER_MANAGEMENT_DELETE and len(state.layer_z_order) == 1:
            return DISABLED
        return ACTION

    stem = state.layout.slot(index)

    if kind in RENDER_OVERLAY_SECTION_KINDS:
        if not state.render_overlay.enabled:
            return DISABLED

    if kind in RENDER_POST_FX_SECTION_KINDS:
        if not state.render_post_fx.enabled:
            return DISABLED

    if kind in {
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_MODE,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_THRESHOLD,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_CEILING,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_STRENGTH,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_SOFTNESS,
        RowKind.RENDER_POST_FX_HIGHLIGHT_ROLLOFF_DESATURATION,
    }:
        if not state.render_post_fx.highlight_rolloff.enabled:
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
        and state.tracks[stem].preset_switching == "projectm"
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


def tuning_panel_max_dimensions(
    viewport_w: int,
    viewport_h: int,
    ui_width: int,
    *,
    timeline_panel_open: bool = False,
    margin_y: int,
    padding: int,
    panel_max_width: int | None = None,
    timeline_row_count: int = 0,
) -> tuple[int, int]:
    """Maximum panel width and height for stable GPU texture capacity."""
    del viewport_w  # horizontal placement uses margin_x elsewhere
    max_w = (
        panel_max_width
        if panel_max_width is not None
        else panel_content_max_width_px(ui_width)
    )
    max_panel_w = max_w + padding * 2
    max_panel_h = viewport_h - margin_y * 2
    if timeline_panel_open and timeline_row_count > 0:
        from cleave.viz.timeline_overlay import timeline_viewport_reserve_px

        max_panel_h -= timeline_viewport_reserve_px(timeline_row_count)
    return max_panel_w, max_panel_h


@dataclass(frozen=True)
class ComposedTuningPanel:
    upload_surface: pygame.Surface
    panel_size: tuple[int, int]
    screen_rect: tuple[int, int, int, int]
    upload_plan: UploadPlan
    upload_signature: UploadSignature
    capacity: tuple[int, int]


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
    panel_max_width: int = PANEL_CONTENT_MAX_WIDTH,
) -> int:
    """Content width budget for a row; scrollable rows reserve the scrollbar column."""
    if show_scrollbar and index in scrollable_indices:
        return panel_max_width - SCROLLBAR_WIDTH
    return panel_max_width


def _transport_icons_width(line_h: int) -> int:
    icon_h = line_h + 1
    bar_w = max(2, (icon_h + 4) // 7)
    inner_gap = max(1, bar_w // 2)
    tri_w = (icon_h * 3) // 4
    slot_w = max(tri_w, 2 * bar_w + inner_gap, bar_w + inner_gap + tri_w)
    gap = max(8, line_h // 2)
    return 3 * slot_w + 2 * gap


def _glyph_icon_width(glyph: str, line_h: int) -> int:
    icon_h = line_h + 1
    return material_font(icon_h).size(glyph)[0]


def _estimate_row_content_width(
    *,
    padding: int,
    font: pygame.font.Font,
    state: TuningViewState,
    index: int,
    max_content_width: int,
    line_h: int,
) -> int:
    indent = padding + _row_indent(state, index)
    kind = state.layout.kind(index)

    if kind == RowKind.TRANSPORT:
        time_text = f" [{format_mmss(state.position_sec)}]"
        return indent + _transport_icons_width(line_h) + font.size(time_text)[0]

    if kind == RowKind.TRACK_HEADER:
        stem = state.layout.slot(index)
        block = state.tracks[stem] if stem is not None else None
        locked = block.locked if block is not None else False
        desc = RowDescriptor(RowKind.TRACK_HEADER, slot=stem)
        prefix_w = visibility_icon_slot_width(line_h)
        layer_prefix = composite_header_prefix_part(state, desc)
        stem_text = _fit_track_header_stem(
            font, state, index, max_content_width=max_content_width
        )
        expand_arrow = (
            format_composite_header_expand_value(state, desc)
            if stem is not None
            else expand_arrow_glyph(False)
        )
        label_w = (
            font.size(layer_prefix)[0]
            + font.size(stem_text)[0]
            + font.size(f" {expand_arrow}")[0]
        )
        if locked:
            label_w += track_header_lock_suffix_width(line_h)
        return indent + prefix_w + label_w

    if kind == RowKind.SETTINGS_HEADER:
        desc = state.layout.descriptor(index)
        icon_w = _glyph_icon_width(SETTINGS_GLYPH, line_h)
        prefix = composite_header_prefix_part(state, desc)
        value = format_composite_header_expand_value(state, desc)
        return indent + icon_w + font.size(prefix)[0] + font.size(value)[0]

    if kind in {
        RowKind.RENDER_OVERLAY_HEADER,
        RowKind.RENDER_POST_FX_HEADER,
        RowKind.RENDER_TIMELINE_HEADER,
    }:
        desc = state.layout.descriptor(index)
        prefix_w = visibility_icon_slot_width(line_h)
        layer_prefix = composite_header_prefix_part(state, desc)
        stem_text = composite_header_suffix_part(state, desc)
        expand_arrow = format_composite_header_expand_value(state, desc)
        label_w = (
            font.size(layer_prefix)[0]
            + font.size(stem_text)[0]
            + font.size(f" {expand_arrow}")[0]
        )
        return indent + prefix_w + label_w

    if kind == RowKind.RENDER_SECTION_GAP:
        return indent + 1

    if (
        ROW_FIELDS.get(kind) is not None
        and ROW_FIELDS[kind].present_style == RowPresentStyle.PATH_ICON
    ):
        if kind == RowKind.TRACK_PRESET_DIR:
            prefix_w = preset_row_prefix_width(font, line_h)
        elif kind in {RowKind.TRACK_PRESET, RowKind.TRACK_USER_PRESET_ITEM}:
            prefix_w = preset_row_prefix_width(font, line_h)
        else:
            prefix_w = tree_branch_prefix_width(font) + _glyph_icon_width(
                FILE_GLYPH, line_h
            )
        if kind == RowKind.CONFIG_HEADER:
            path = fit_row_text(
                font, state, index, max_content_width=max_content_width
            )
            suffix_w = font.size("*")[0] if state.config_dirty else 0
            return indent + prefix_w + font.size(path)[0] + suffix_w
        label = fit_row_text(
            font, state, index, max_content_width=max_content_width
        )
        return indent + prefix_w + font.size(label)[0]

    if (
        ROW_FIELDS.get(kind) is not None
        and ROW_FIELDS[kind].present_style == RowPresentStyle.EXPAND_SUBHEADER
    ):
        desc = state.layout.descriptor(index)
        prefix = expand_subheader_prefix(kind)
        value = format_expand_subheader_value(state, desc)
        return indent + font.size(prefix)[0] + font.size(value)[0]

    if kind in LABELED_SUB_ROW_KINDS:
        prefix = _labeled_sub_row_prefix(state, index)
        value = _fit_labeled_sub_row_value(
            font, state, index, max_content_width=max_content_width
        )
        return indent + font.size(prefix)[0] + font.size(value)[0]

    if (
        ROW_FIELDS.get(kind) is not None
        and ROW_FIELDS[kind].present_style == RowPresentStyle.FULL_LINE
        and kind
        in {
            RowKind.LAYER_MANAGEMENT_ADD,
            RowKind.LAYER_MANAGEMENT_DELETE,
            RowKind.TRACK_USER_PRESET_ADD,
        }
    ):
        label = _row_text(state, index)
        return indent + font.size(label)[0]

    text = fit_row_text(font, state, index, max_content_width=max_content_width)
    return indent + font.size(text)[0]


def _scrollable_row_in_viewport(
    *,
    row_index: int,
    scroll_y: int,
    scroll_top: int,
    scroll_bottom: int,
    row_stride: int,
    line_h: int,
) -> bool:
    local_y = row_index * row_stride
    y = scroll_top + local_y - scroll_y
    return y + line_h > scroll_top and y < scroll_bottom


def clip_rect_to_surface(
    rect: tuple[int, int, int, int],
    surface: pygame.Surface,
) -> tuple[int, int, int, int] | None:
    """Intersection of rect with surface bounds (for subsurface-safe panel_rect)."""
    return clip_rect_to_bounds(rect, surface.get_width(), surface.get_height())


def clip_rect_to_bounds(
    rect: tuple[int, int, int, int],
    bounds_w: int,
    bounds_h: int,
) -> tuple[int, int, int, int] | None:
    """Intersection of rect with a width/height viewport."""
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return None
    left = max(x, 0)
    top = max(y, 0)
    right = min(x + w, bounds_w)
    bottom = min(y + h, bounds_h)
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
        self._panel_scratch: pygame.Surface | None = None
        self._scroll_y = 0
        self._panel_cache = TuningPanelCache()

    @property
    def gpu_state(self) -> OverlayGpuState:
        return self._panel_cache.gpu

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
        self._panel_cache.clear_all()

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

    def _ensure_panel_scratch(
        self,
        panel_w: int,
        panel_h: int,
        *,
        counters: OverlayDrawCounters | None = None,
    ) -> pygame.Surface:
        if (
            self._panel_scratch is None
            or self._panel_scratch.get_size() != (panel_w, panel_h)
        ):
            self._panel_scratch = _compose_surface(
                (panel_w, panel_h), counters=counters
            )
        return self._panel_scratch

    def _blit_row(
        self,
        panel: pygame.Surface,
        *,
        state: TuningViewState,
        index: int,
        surf: pygame.Surface,
        time_surf: pygame.Surface | None,
        y: int,
        text_alpha: int,
        panel_w: int,
        line_h: int,
    ) -> None:
        row_rect = (self._padding, y, panel_w - self._padding * 2, line_h)
        panel_bg_alpha = int(BACKGROUND_ALPHA * self._visibility)
        bg = _row_bg_color(state, index)
        tint_alpha = (
            int(FOCUS_ROW_BG_ALPHA * self._visibility) if bg is not None else 0
        )
        draw_opaque_row_background(
            panel,
            row_rect,
            BACKGROUND,
            panel_bg_alpha,
            bg,
            tint_alpha=tint_alpha,
        )

        indent = self._padding + _row_indent(state, index)
        if text_alpha >= 2:
            surf.set_alpha(text_alpha)
            panel.blit(surf, (indent, y))
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

    def _build_row_at_index(
        self,
        font: pygame.font.Font,
        state: TuningViewState,
        index: int,
        *,
        max_content_width: int,
        line_h: int,
        counters: OverlayDrawCounters | None = None,
        cache: TuningPanelCache | None = None,
    ) -> tuple[pygame.Surface, pygame.Surface | None, int]:
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
            time_surf = _render_text(font, time_text, True, color, counters=counters)
            width = indent + icons_surf.get_width() + time_surf.get_width()
            return icons_surf, time_surf, width

        if kind == RowKind.TRACK_HEADER:
            stem = state.layout.slot(index)
            block = state.tracks[stem] if stem is not None else None
            enabled = block.visible if block is not None else True
            solo = stem is not None and state.solo_slot == stem
            locked = block.locked if block is not None else False
            desc = RowDescriptor(RowKind.TRACK_HEADER, slot=stem)
            prefix_surf = render_visibility_icon(
                enabled=enabled, solo=solo, line_height=line_h
            )
            layer_prefix = composite_header_prefix_part(state, desc)
            stem_text = _fit_track_header_stem(
                font,
                state,
                index,
                max_content_width=max_content_width,
                cache=cache,
            )
            expand_arrow = (
                format_composite_header_expand_value(state, desc)
                if stem is not None
                else expand_arrow_glyph(False)
            )
            label_surf = _render_track_header_label(
                font,
                layer_prefix=layer_prefix,
                stem_text=stem_text,
                value_color=color,
                expand_arrow=expand_arrow,
                locked=locked,
                line_height=line_h,
                counters=counters,
            )
            width = indent + prefix_surf.get_width() + label_surf.get_width()
            return prefix_surf, label_surf, width

        if kind == RowKind.SETTINGS_HEADER:
            desc = state.layout.descriptor(index)
            icon_surf = render_glyph(SETTINGS_GLYPH, color=VALUE, line_height=line_h)
            label_surf = _render_label_value_row(
                font,
                prefix=composite_header_prefix_part(state, desc),
                value=format_composite_header_expand_value(state, desc),
                value_color=color,
                prefix_color=LABEL,
                line_height=line_h,
                counters=counters,
            )
            width = indent + icon_surf.get_width() + label_surf.get_width()
            return icon_surf, label_surf, width

        if kind in {
            RowKind.RENDER_OVERLAY_HEADER,
            RowKind.RENDER_POST_FX_HEADER,
            RowKind.RENDER_TIMELINE_HEADER,
        }:
            desc = state.layout.descriptor(index)
            if kind == RowKind.RENDER_OVERLAY_HEADER:
                block_ro = state.render_overlay
                prefix_surf = render_visibility_icon(
                    enabled=block_ro.enabled,
                    solo=block_ro.solo,
                    line_height=line_h,
                )
            elif kind == RowKind.RENDER_POST_FX_HEADER:
                block_pp = state.render_post_fx
                prefix_surf = render_visibility_icon(
                    enabled=block_pp.enabled,
                    solo=block_pp.solo,
                    line_height=line_h,
                )
            else:
                block_tl = state.render_timeline
                prefix_surf = render_visibility_icon(
                    enabled=block_tl.enabled,
                    solo=False,
                    line_height=line_h,
                )
            label_surf = _render_track_header_label(
                font,
                layer_prefix=composite_header_prefix_part(state, desc),
                stem_text=composite_header_suffix_part(state, desc),
                value_color=color,
                expand_arrow=format_composite_header_expand_value(state, desc),
                locked=False,
                line_height=line_h,
                counters=counters,
            )
            width = indent + prefix_surf.get_width() + label_surf.get_width()
            return prefix_surf, label_surf, width

        if kind == RowKind.RENDER_SECTION_GAP:
            gap_surf = _compose_surface((1, line_h), counters=counters)
            return gap_surf, None, indent + gap_surf.get_width()

        if (
            ROW_FIELDS.get(kind) is not None
            and ROW_FIELDS[kind].present_style == RowPresentStyle.PATH_ICON
        ):
            if kind == RowKind.TRACK_PRESET_DIR:
                glyph = FOLDER_GLYPH
                icon_color = PRESET_ICON
                icon_surf = _render_preset_row_prefix(
                    font,
                    glyph=glyph,
                    icon_color=icon_color,
                    line_height=line_h,
                    counters=counters,
                )
            elif kind in {RowKind.TRACK_PRESET, RowKind.TRACK_USER_PRESET_ITEM}:
                glyph = FILE_GLYPH
                icon_color = PRESET_FILE_ICON
                icon_surf = _render_preset_row_prefix(
                    font,
                    glyph=glyph,
                    icon_color=icon_color,
                    line_height=line_h,
                    counters=counters,
                )
            else:
                icon_surf = render_glyph(
                    FILE_GLYPH, color=PRESET_FILE_ICON, line_height=line_h
                )
            if kind == RowKind.CONFIG_HEADER:
                path = fit_row_text(
                    font,
                    state,
                    index,
                    max_content_width=max_content_width,
                    cache=cache,
                )
                label_surf = _render_label_value_row(
                    font,
                    prefix=path,
                    value="*" if state.config_dirty else "",
                    value_color=CONFIG_DIRTY,
                    prefix_color=color,
                    line_height=line_h,
                    counters=counters,
                )
            else:
                label = fit_row_text(
                    font,
                    state,
                    index,
                    max_content_width=max_content_width,
                    cache=cache,
                )
                label_surf = _render_text(font, label, True, color, counters=counters)
            width = indent + icon_surf.get_width() + label_surf.get_width()
            return icon_surf, label_surf, width

        if (
            ROW_FIELDS.get(kind) is not None
            and ROW_FIELDS[kind].present_style == RowPresentStyle.EXPAND_SUBHEADER
        ):
            desc = state.layout.descriptor(index)
            surf = _render_label_value_row(
                font,
                prefix=expand_subheader_prefix(kind),
                value=format_expand_subheader_value(state, desc),
                value_color=color,
                line_height=line_h,
                counters=counters,
            )
            return surf, None, indent + surf.get_width()

        if kind in LABELED_SUB_ROW_KINDS:
            prefix = _labeled_sub_row_prefix(state, index)
            value = _fit_labeled_sub_row_value(
                font,
                state,
                index,
                max_content_width=max_content_width,
                cache=cache,
            )
            surf = _render_label_value_row(
                font,
                prefix=prefix,
                value=value,
                value_color=color,
                line_height=line_h,
                counters=counters,
            )
            return surf, None, indent + surf.get_width()

        if (
            ROW_FIELDS.get(kind) is not None
            and ROW_FIELDS[kind].present_style == RowPresentStyle.FULL_LINE
            and kind
            in {
                RowKind.LAYER_MANAGEMENT_ADD,
                RowKind.LAYER_MANAGEMENT_DELETE,
                RowKind.TRACK_USER_PRESET_ADD,
            }
        ):
            label = _row_text(state, index)
            label_color = _row_value_color(state, index)
            surf = _render_text(font, label, True, label_color, counters=counters)
            return surf, None, indent + surf.get_width()

        text = fit_row_text(
            font, state, index, max_content_width=max_content_width, cache=cache
        )
        surf = _render_text(font, text, True, color, counters=counters)
        return surf, None, indent + surf.get_width()

    def _max_content_width(
        self,
        index: int,
        *,
        scrollable_indices: frozenset[int],
        show_scrollbar: bool,
        panel_max_width: int,
    ) -> int:
        return panel_content_max_width(
            index=index,
            scrollable_indices=scrollable_indices,
            show_scrollbar=show_scrollbar,
            panel_max_width=panel_max_width,
        )

    def _ensure_cache_panel(
        self,
        panel_w: int,
        panel_h: int,
        *,
        counters: OverlayDrawCounters | None = None,
    ) -> pygame.Surface:
        cache = self._panel_cache
        if cache.panel is None or cache.panel.get_size() != (panel_w, panel_h):
            cache.panel = _compose_surface((panel_w, panel_h), counters=counters)
        return cache.panel

    def _transport_row_y(
        self,
        transport_index: int,
        *,
        metrics: PanelScrollMetrics,
        visible_indices: list[int],
        first_scrollable_visible: int | None,
    ) -> int:
        if metrics.needs_scroll:
            try:
                header_pos = metrics.header_indices.index(transport_index)
            except ValueError:
                return self._padding
            return self._padding + header_pos * metrics.row_stride
        row_y = self._padding
        for index in visible_indices:
            if index == first_scrollable_visible:
                row_y += metrics.row_stride
            if index == transport_index:
                return row_y
            row_y += metrics.row_stride
        return self._padding

    def _patch_live_panel_rows(
        self,
        panel: pygame.Surface,
        state: TuningViewState,
        *,
        font: pygame.font.Font,
        metrics: PanelScrollMetrics,
        visible_indices: list[int],
        first_scrollable_visible: int | None,
        transport_index: int,
        transport_entry: RowRenderEntry,
        panel_w: int,
        line_h: int,
        text_alpha: int,
        counters: OverlayDrawCounters | None = None,
    ) -> None:
        cache = self._panel_cache
        bg_alpha = int(BACKGROUND_ALPHA * self._visibility)
        transport_y = self._transport_row_y(
            transport_index,
            metrics=metrics,
            visible_indices=visible_indices,
            first_scrollable_visible=first_scrollable_visible,
        )
        cache.last_transport_rect = (
            BORDER_WIDTH,
            transport_y,
            panel_w - 2 * BORDER_WIDTH,
            line_h,
        )
        if bg_alpha >= 2:
            pygame.draw.rect(
                panel,
                (*BACKGROUND, bg_alpha),
                (
                    BORDER_WIDTH,
                    transport_y,
                    panel_w - 2 * BORDER_WIDTH,
                    line_h,
                ),
            )
        self._blit_row(
            panel,
            state=state,
            index=transport_index,
            surf=transport_entry.primary,
            time_surf=transport_entry.secondary,
            y=transport_y,
            text_alpha=text_alpha,
            panel_w=panel_w,
            line_h=line_h,
        )

        if state.fps is not None and text_alpha >= 2:
            if cache.last_fps_rect is not None and bg_alpha >= 2:
                pygame.draw.rect(panel, (*BACKGROUND, bg_alpha), cache.last_fps_rect)
            fps_surf = _render_text(
                font, format_fps_display(state.fps), True, VALUE, counters=counters
            )
            fps_surf.set_alpha(text_alpha)
            fps_layout = panel_fps_layout(
                panel_w=panel_w,
                padding=self._padding,
                text_width=fps_surf.get_width(),
                show_scrollbar=metrics.show_scrollbar,
            )
            panel.blit(fps_surf, (fps_layout.x, fps_layout.y))
            cache.last_fps_rect = (
                fps_layout.x,
                fps_layout.y,
                fps_surf.get_width(),
                fps_surf.get_height(),
            )

    def _composite_panel_rows(
        self,
        panel: pygame.Surface,
        state: TuningViewState,
        built_rows: dict[int, RowRenderEntry],
        *,
        metrics: PanelScrollMetrics,
        visible_indices: list[int],
        first_scrollable_visible: int | None,
        panel_w: int,
        line_h: int,
        text_alpha: int,
        header_gap: int,
    ) -> None:
        if metrics.needs_scroll:
            header_y = self._padding
            for row_index, index in enumerate(metrics.header_indices):
                y = header_y + row_index * metrics.row_stride
                entry = built_rows[index]
                self._blit_row(
                    panel,
                    state=state,
                    index=index,
                    surf=entry.primary,
                    time_surf=entry.secondary,
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
                entry = built_rows[index]
                self._blit_row(
                    panel,
                    state=state,
                    index=index,
                    surf=entry.primary,
                    time_surf=entry.secondary,
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
            for index in visible_indices:
                if index == first_scrollable_visible:
                    row_y += header_gap
                entry = built_rows[index]
                self._blit_row(
                    panel,
                    state=state,
                    index=index,
                    surf=entry.primary,
                    time_surf=entry.secondary,
                    y=row_y,
                    text_alpha=text_alpha,
                    panel_w=panel_w,
                    line_h=line_h,
                )
                row_y += line_h + self._line_gap

    def _draw_panel_chrome(
        self,
        panel: pygame.Surface,
        state: TuningViewState,
        *,
        font: pygame.font.Font,
        metrics: PanelScrollMetrics,
        panel_w: int,
        panel_h: int,
        line_h: int,
        text_alpha: int,
        counters: OverlayDrawCounters | None,
        draw_fps: bool,
    ) -> None:
        cache = self._panel_cache
        if draw_fps and state.fps is not None and text_alpha >= 2:
            fps_surf = _render_text(
                font, format_fps_display(state.fps), True, VALUE, counters=counters
            )
            fps_surf.set_alpha(text_alpha)
            fps_layout = panel_fps_layout(
                panel_w=panel_w,
                padding=self._padding,
                text_width=fps_surf.get_width(),
                show_scrollbar=metrics.show_scrollbar,
            )
            panel.blit(fps_surf, (fps_layout.x, fps_layout.y))
            cache.last_fps_rect = (
                fps_layout.x,
                fps_layout.y,
                fps_surf.get_width(),
                fps_surf.get_height(),
            )
        elif not draw_fps:
            cache.last_fps_rect = None

        if text_alpha >= 2:
            help_hint = _render_text(font, "h - help", True, LABEL, counters=counters)
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

    def compose_panel(
        self,
        state: TuningViewState,
        *,
        viewport_width: int,
        viewport_height: int,
        timeline_panel_open: bool = False,
        counters: OverlayDrawCounters | None = None,
    ) -> ComposedTuningPanel | None:
        self._panel_rect = None
        if self._visibility <= 0.01 or len(state.layout) == 0:
            return None

        font = self._font_get()
        line_h = font.get_linesize()
        frame = state.layout_frame
        if frame is not None:
            visible_indices = list(frame.visible_indices)
        else:
            visible_indices = state.layout.visible_indices(state)
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
        panel_max_width = panel_content_max_width_px(state.settings.ui_width)
        capacity = tuning_panel_max_dimensions(
            viewport_width,
            viewport_height,
            state.settings.ui_width,
            timeline_panel_open=timeline_panel_open,
            margin_y=margin_y,
            padding=self._padding,
            panel_max_width=panel_max_width,
            timeline_row_count=len(state.layer_z_order),
        )
        max_panel_h = capacity[1]
        metrics = scroll_metrics(
            visible_indices=visible_indices,
            first_scrollable_visible=first_scrollable_visible,
            line_h=line_h,
            line_gap=self._line_gap,
            padding=self._padding,
            header_gap=header_gap,
            max_panel_h=max_panel_h,
        )
        if metrics.needs_scroll:
            self._ensure_focus_visible(
                state,
                metrics.scrollable_indices,
                metrics.row_stride,
                metrics.scroll_viewport_h,
                line_h,
            )
            scroll_top = self._padding + metrics.header_block_h
            scroll_bottom = scroll_top + metrics.scroll_viewport_h
            raster_indices: set[int] = set(metrics.header_indices)
            for row_index, index in enumerate(metrics.scrollable_indices):
                if _scrollable_row_in_viewport(
                    row_index=row_index,
                    scroll_y=self._scroll_y,
                    scroll_top=scroll_top,
                    scroll_bottom=scroll_bottom,
                    row_stride=metrics.row_stride,
                    line_h=line_h,
                ):
                    raster_indices.add(index)
        else:
            raster_indices = set(visible_indices)

        scrollable_indices = frozenset(metrics.scrollable_indices)
        panel_max_width = panel_content_max_width_px(state.settings.ui_width)
        vis_tuple = tuple(visible_indices)
        cache = self._panel_cache
        if cache.row_cache_structure != vis_tuple:
            cache.clear_rows()
            cache.row_cache_structure = vis_tuple

        def max_content_width_for(index: int) -> int:
            return self._max_content_width(
                index,
                scrollable_indices=scrollable_indices,
                show_scrollbar=metrics.show_scrollbar,
                panel_max_width=panel_max_width,
            )

        static_keys = static_row_keys(
            state,
            font=font,
            cache=cache,
            visible_indices=vis_tuple,
            max_content_width_for_index=max_content_width_for,
            line_h=line_h,
        )

        panel_h = metrics.panel_h
        prev_sig = cache.panel_signature
        prev_size = cache.panel_size
        candidate_w = (
            prev_size[0]
            if prev_size is not None
            else panel_max_width + self._padding * 2
        )
        new_sig = panel_signature(
            state,
            visibility=self._visibility,
            panel_w=candidate_w,
            panel_h=panel_h,
            scroll_y=self._scroll_y,
            timeline_panel_open=timeline_panel_open,
            static_row_keys=static_keys,
        )
        can_incremental = (
            cache.panel is not None
            and prev_sig is not None
            and prev_size is not None
            and new_sig == prev_sig
            and prev_size[1] == panel_h
        )

        transport_index = next(
            (
                index
                for index in visible_indices
                if state.layout.kind(index) == RowKind.TRANSPORT
            ),
            None,
        )

        if can_incremental:
            assert cache.panel is not None
            assert transport_index is not None
            panel = cache.panel
            panel_w = prev_size[0]
            text_alpha = int(255 * self._visibility)
            transport_entry = ensure_row_surface(
                cache,
                state,
                transport_index,
                font,
                self._build_row_at_index,
                max_content_width=max_content_width_for(transport_index),
                line_h=line_h,
                counters=counters,
            )
            self._patch_live_panel_rows(
                panel,
                state,
                font=font,
                metrics=metrics,
                visible_indices=visible_indices,
                first_scrollable_visible=first_scrollable_visible,
                transport_index=transport_index,
                transport_entry=transport_entry,
                panel_w=panel_w,
                line_h=line_h,
                text_alpha=text_alpha,
                counters=counters,
            )
            self._panel_scratch = panel
            placement = self._finish_compose_panel(
                panel_w=panel_w,
                panel_h=panel_h,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
            )
            if placement is None:
                return None
            assert prev_sig is not None
            return self._build_composed_panel(
                panel,
                panel_sig=prev_sig,
                panel_size=(panel_w, panel_h),
                placement=placement,
                state=state,
                capacity=capacity,
                incremental=True,
            )

        built_rows: dict[int, RowRenderEntry] = {}
        row_widths: list[int] = []
        for index in visible_indices:
            max_content_width = max_content_width_for(index)
            if index in raster_indices:
                entry = ensure_row_surface(
                    cache,
                    state,
                    index,
                    font,
                    self._build_row_at_index,
                    max_content_width=max_content_width,
                    line_h=line_h,
                    counters=counters,
                )
                built_rows[index] = entry
                row_widths.append(entry.content_width)
            else:
                row_widths.append(
                    _estimate_row_content_width(
                        padding=self._padding,
                        font=font,
                        state=state,
                        index=index,
                        max_content_width=max_content_width,
                        line_h=line_h,
                    )
                )

        content_w = max(row_widths) if row_widths else 0
        content_w = min(content_w, panel_max_width)
        if state.settings.ui_width_mode == "fixed":
            content_w = panel_max_width
        panel_w = content_w + self._padding * 2

        alpha = int(BACKGROUND_ALPHA * self._visibility)
        if alpha < 2:
            return None

        new_sig = panel_signature(
            state,
            visibility=self._visibility,
            panel_w=panel_w,
            panel_h=panel_h,
            scroll_y=self._scroll_y,
            timeline_panel_open=timeline_panel_open,
            static_row_keys=static_keys,
        )

        panel = self._ensure_cache_panel(panel_w, panel_h, counters=counters)
        panel.fill((*BACKGROUND, alpha))

        text_alpha = int(255 * self._visibility)

        self._composite_panel_rows(
            panel,
            state,
            built_rows,
            metrics=metrics,
            visible_indices=visible_indices,
            first_scrollable_visible=first_scrollable_visible,
            panel_w=panel_w,
            line_h=line_h,
            text_alpha=text_alpha,
            header_gap=header_gap,
        )

        self._draw_panel_chrome(
            panel,
            state,
            font=font,
            metrics=metrics,
            panel_w=panel_w,
            panel_h=panel_h,
            line_h=line_h,
            text_alpha=text_alpha,
            counters=counters,
            draw_fps=True,
        )

        cache.panel_signature = new_sig
        cache.panel_size = (panel_w, panel_h)
        self._set_transport_rect_cache(
            transport_index,
            metrics=metrics,
            visible_indices=visible_indices,
            first_scrollable_visible=first_scrollable_visible,
            panel_w=panel_w,
            line_h=line_h,
        )
        self._panel_scratch = panel

        placement = self._finish_compose_panel(
            panel_w=panel_w,
            panel_h=panel_h,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
        )
        if placement is None:
            return None
        return self._build_composed_panel(
            panel,
            panel_sig=new_sig,
            panel_size=(panel_w, panel_h),
            placement=placement,
            state=state,
            capacity=capacity,
            incremental=False,
        )

    def _set_transport_rect_cache(
        self,
        transport_index: int | None,
        *,
        metrics: PanelScrollMetrics,
        visible_indices: list[int],
        first_scrollable_visible: int | None,
        panel_w: int,
        line_h: int,
    ) -> None:
        if transport_index is None:
            self._panel_cache.last_transport_rect = None
            return
        transport_y = self._transport_row_y(
            transport_index,
            metrics=metrics,
            visible_indices=visible_indices,
            first_scrollable_visible=first_scrollable_visible,
        )
        self._panel_cache.last_transport_rect = (
            BORDER_WIDTH,
            transport_y,
            panel_w - 2 * BORDER_WIDTH,
            line_h,
        )

    def _build_composed_panel(
        self,
        panel: pygame.Surface,
        *,
        panel_sig: PanelSignature,
        panel_size: tuple[int, int],
        placement: tuple[tuple[int, int, int, int], tuple[int, int]],
        state: TuningViewState,
        capacity: tuple[int, int],
        incremental: bool,
    ) -> ComposedTuningPanel:
        cache = self._panel_cache
        screen_rect, src_offset = placement
        live_sig = live_upload_signature(state)
        upload_signature = tuning_upload_signature(panel_sig, screen_rect, live_sig)
        panel_w, panel_h = panel_size
        src_x, src_y = src_offset
        active_w, active_h = screen_rect[2], screen_rect[3]

        if incremental and live_sig == cache.last_live_signature:
            upload_plan = upload_plan_for_signature(
                upload_signature,
                cache.gpu.last_signature,
            )
        elif incremental:
            dirty_rects: list[tuple[int, int, int, int]] = []
            if cache.last_transport_rect is not None:
                dirty_rects.append(cache.last_transport_rect)
            if cache.last_fps_rect is not None and state.fps is not None:
                dirty_rects.append(cache.last_fps_rect)
            upload_plan = upload_plan_for_signature(
                upload_signature,
                cache.gpu.last_signature,
                dirty_rects=clip_dirty_rects(tuple(dirty_rects), panel_w, panel_h),
            )
        else:
            cache.last_live_signature = None
            clip_rect = (
                (src_x, src_y, active_w, active_h)
                if src_x != 0 or src_y != 0 or (active_w, active_h) != (panel_w, panel_h)
                else ()
            )
            if clip_rect:
                upload_plan = upload_plan_for_signature(
                    upload_signature,
                    cache.gpu.last_signature,
                    dirty_rects=clip_dirty_rects(clip_rect, panel_w, panel_h),
                )
            else:
                upload_plan = upload_plan_for_signature(
                    upload_signature,
                    cache.gpu.last_signature,
                )

        cache.last_live_signature = live_sig
        return ComposedTuningPanel(
            upload_surface=panel,
            panel_size=panel_size,
            screen_rect=screen_rect,
            upload_plan=upload_plan,
            upload_signature=upload_signature,
            capacity=capacity,
        )

    def _finish_compose_panel(
        self,
        *,
        panel_w: int,
        panel_h: int,
        viewport_width: int,
        viewport_height: int,
    ) -> tuple[tuple[int, int, int, int], tuple[int, int]] | None:
        mx, my = self._margin
        if self._anchor == "topleft":
            pos = (mx, my)
        else:
            pos = (mx, viewport_height - panel_h - my)

        bounds = clip_rect_to_bounds(
            (pos[0], pos[1], panel_w, panel_h),
            viewport_width,
            viewport_height,
        )
        if bounds is None:
            return None
        self._panel_rect = bounds
        src_x = bounds[0] - pos[0]
        src_y = bounds[1] - pos[1]
        return bounds, (src_x, src_y)

    def draw(
        self,
        surface: pygame.Surface,
        state: TuningViewState,
        *,
        timeline_panel_open: bool = False,
        counters: OverlayDrawCounters | None = None,
    ) -> None:
        composed = self.compose_panel(
            state,
            viewport_width=surface.get_width(),
            viewport_height=surface.get_height(),
            timeline_panel_open=timeline_panel_open,
            counters=counters,
        )
        if composed is None:
            self._panel_rect = None
            return
        panel = self._panel_scratch
        assert panel is not None
        mx, my = self._margin
        if self._anchor == "topleft":
            blit_pos = (mx, my)
        else:
            blit_pos = (mx, surface.get_height() - panel.get_height() - my)
        surface.blit(panel, blit_pos)
