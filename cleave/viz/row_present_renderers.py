"""Present-style row paint, fit, and color for the live tuning panel."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame

from cleave.extract import stem_overlay_header
from cleave.viz.material_icons import (
    FILE_GLYPH,
    FOLDER_GLYPH,
    LOCK_GLYPH,
    SETTINGS_GLYPH,
    VISIBILITY_GLYPH,
    VISIBILITY_OFF_GLYPH,
    VISIBILITY_ICON_PAD_X,
    action_enter_icon_suffix_width,
    render_action_enter_icon,
    render_glyph,
    render_transport_icons,
    row_icon_prefix_width,
    track_header_lock_suffix_width,
    visibility_icon_slot_width,
)
from cleave.viz.overlay_profiler import OverlayDrawCounters
from cleave.viz.panel_notification import notification_attention
from cleave.viz.playback import format_mmss
from cleave.viz.row_kinds import RowAffordance
from cleave.viz.row_spec import (
    FitStrategy,
    ROW_SPECS,
    RowPresentStyle,
    RowSpec,
    composite_header_prefix_part,
    composite_header_suffix_part,
    editor_mode_confirm_pending,
    expand_subheader_prefix,
    format_composite_header_expand_value,
    format_expand_subheader_value,
    format_row_value,
    labeled_row_prefix,
    row_action_parameter_display_text,
    row_blocked_by_section_lock,
    row_composite_header_display_text,
    row_dynamic_labeled_display_text,
    row_dynamic_labeled_prefix,
    row_expand_subheader_display_text,
    row_full_line_display_text,
    row_labeled_display_text,
    row_spec,
    section_locked,
    tree_branch_leading_spaces,
)
from cleave.viz.row_sections import (
    RENDER_OVERLAY_SECTION_KINDS,
    RENDER_PATTERN_MASK_SECTION_KINDS,
    RENDER_POST_FX_SECTION_KINDS,
    RENDER_TIMELINE_SECTION_KINDS,
    expand_arrow_glyph,
    row_tree_indent_depth,
)
from cleave.viz.text_fit import (
    fit_counter_label_to_width,
    fit_path_label_to_width,
    fit_text_to_width,
)
from cleave.viz.theme import (
    ACTION,
    CONFIG_DIRTY,
    DISABLED,
    ERROR_NOTIFICATION,
    HIGHLIGHT,
    LABEL,
    LOCKED,
    LOCK_ICON,
    MOVE_MODE,
    NOTIFICATION_ON_FILL,
    OVERRIDE_BG,
    OVERRIDE_GLYPH,
    OVERRIDE_GLYPH_OFF,
    PANEL_CONTENT_MAX_WIDTH,
    PRESET_FILE_ICON,
    PRESET_ICON,
    SOLO_BG,
    VALUE,
    tuning_ui_metrics,
)
from cleave.viz.tuning_panel_cache import TuningPanelCache
from cleave.viz.tuning_view_state import TuningViewState

_tuning_ui = tuning_ui_metrics()
TREE_INDENT = _tuning_ui.tree_indent
TREE_BRANCH = "└"
ROW_ICON_SUFFIX_GAP = _tuning_ui.row_icon_suffix_gap


def render_text(
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


def compose_surface(
    size: tuple[int, int],
    *,
    counters: OverlayDrawCounters | None = None,
    flags: int = pygame.SRCALPHA,
) -> pygame.Surface:
    if counters is not None:
        counters.surface_builds += 1
    return pygame.Surface(size, flags)


def field_for_index(state: TuningViewState, index: int) -> RowSpec | None:
    return ROW_SPECS.get(state.layout.kind(index))


def row_has_tree_focus(state: TuningViewState, index: int) -> bool:
    if state.timeline_submenu_focused:
        return False
    return index == state.focus_index


def track_disabled(state: TuningViewState, slot: str) -> bool:
    return not state.tracks[slot].visible


def row_indent(state: TuningViewState, index: int) -> int:
    return TREE_INDENT * row_tree_indent_depth(state.layout.kind(index))


def row_shows_action_enter_hint(state: TuningViewState, index: int) -> bool:
    field = field_for_index(state, index)
    if field is None or not field.shows_enter_icon:
        return False
    if field.present_style == RowPresentStyle.ACTION_PARAMETER:
        return False
    if not row_has_tree_focus(state, index):
        return False
    return row_value_color(state, index) == HIGHLIGHT


def row_shows_enter_icon(state: TuningViewState, index: int) -> bool:
    if row_shows_action_enter_hint(state, index):
        return True
    field = field_for_index(state, index)
    if field is None or not field.shows_enter_icon:
        return False
    return (
        field.present_style == RowPresentStyle.ACTION_PARAMETER
        and editor_mode_confirm_pending(state)
    )


def append_action_enter_icon(
    surf: pygame.Surface,
    *,
    color: tuple[int, int, int],
    line_height: int,
    counters: OverlayDrawCounters | None = None,
) -> pygame.Surface:
    icon = render_action_enter_icon(color=color, line_height=line_height)
    gap = ROW_ICON_SUFFIX_GAP
    out = compose_surface(
        (surf.get_width() + gap + icon.get_width(), line_height),
        counters=counters,
    )
    out.blit(surf, (0, 0))
    out.blit(icon, (surf.get_width() + gap, 0))
    return out


def with_action_enter_hint(
    primary: pygame.Surface,
    secondary: pygame.Surface | None,
    width: int,
    *,
    state: TuningViewState,
    index: int,
    indent: int,
    line_h: int,
    counters: OverlayDrawCounters | None = None,
) -> tuple[pygame.Surface, pygame.Surface | None, int]:
    if not row_shows_action_enter_hint(state, index):
        return primary, secondary, width
    color = row_value_color(state, index)
    if secondary is not None:
        secondary = append_action_enter_icon(
            secondary, color=color, line_height=line_h, counters=counters
        )
        return primary, secondary, indent + primary.get_width() + secondary.get_width()
    primary = append_action_enter_icon(
        primary, color=color, line_height=line_h, counters=counters
    )
    return primary, None, indent + primary.get_width()


def row_text(state: TuningViewState, index: int) -> str:
    desc = state.layout.descriptor(index)
    field = field_for_index(state, index)
    if field is None:
        return ""
    style = field.present_style
    if style == RowPresentStyle.SPACER:
        return ""
    if style == RowPresentStyle.NOTIFICATION:
        return format_row_value(state, desc)
    if style == RowPresentStyle.LABELED_VALUE:
        return row_labeled_display_text(state, desc)
    if style == RowPresentStyle.ACTION_PARAMETER:
        return row_action_parameter_display_text(state, desc)
    if style == RowPresentStyle.EXPAND_SUBHEADER:
        return row_expand_subheader_display_text(state, desc)
    if style == RowPresentStyle.COMPOSITE_HEADER:
        return row_composite_header_display_text(state, desc)
    if style == RowPresentStyle.TRACK_HEADER:
        return row_composite_header_display_text(state, desc)
    if style == RowPresentStyle.PATH_ICON:
        return format_row_value(state, desc)
    if style == RowPresentStyle.FULL_LINE:
        return row_full_line_display_text(state, desc)
    if style == RowPresentStyle.DYNAMIC:
        return row_dynamic_labeled_display_text(state, desc)
    return ""


def render_label_value_row(
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
    prefix_surf = render_text(
        font,
        prefix,
        True,
        prefix_color if prefix_color is not None else LABEL,
        counters=counters,
    )
    value_surf = render_text(font, value, True, value_color, counters=counters)
    label_w = prefix_surf.get_width() + value_surf.get_width()
    if suffix_surf is not None:
        label_w += suffix_gap + suffix_surf.get_width()

    label_surf = compose_surface((label_w, line_height), counters=counters)
    x = 0
    label_surf.blit(prefix_surf, (x, 0))
    x += prefix_surf.get_width()
    label_surf.blit(value_surf, (x, 0))
    if suffix_surf is not None:
        x += value_surf.get_width() + suffix_gap
        label_surf.blit(suffix_surf, (x, 0))
    return label_surf


def row_visibility_icon_key(
    state: TuningViewState, index: int
) -> tuple[bool, bool] | None:
    """Return ``(enabled, solo)`` for rows with a visibility eye, else ``None``."""
    field = field_for_index(state, index)
    if field is None or field.visibility_icon is None:
        return None
    return field.visibility_icon(state, state.layout.descriptor(index))


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


def tree_branch_prefix_width(font: pygame.font.Font, *, depth: int = 1) -> int:
    return font.size(tree_branch_leading_spaces(depth) + TREE_BRANCH)[0]


def preset_row_prefix_width(
    font: pygame.font.Font, line_height: int, *, depth: int = 1
) -> int:
    return tree_branch_prefix_width(font, depth=depth) + row_icon_prefix_width(
        line_height
    )


def _render_preset_row_prefix(
    font: pygame.font.Font,
    *,
    glyph: str,
    icon_color: tuple[int, int, int],
    line_height: int,
    depth: int = 1,
    counters: OverlayDrawCounters | None = None,
) -> pygame.Surface:
    branch = tree_branch_leading_spaces(depth) + TREE_BRANCH
    tree_surf = render_text(font, branch, True, LABEL, counters=counters)
    icon_surf = render_glyph(glyph, color=icon_color, line_height=line_height)
    total_w = tree_surf.get_width() + icon_surf.get_width()
    surf = compose_surface((total_w, line_height), counters=counters)
    surf.blit(tree_surf, (0, 0))
    surf.blit(icon_surf, (tree_surf.get_width(), 0))
    return surf


def _track_header_layer_prefix(state: TuningViewState, index: int) -> str:
    desc = state.layout.descriptor(index)
    return composite_header_prefix_part(state, desc)


def _track_header_expand_suffix(state: TuningViewState, index: int) -> str:
    desc = state.layout.descriptor(index)
    return f" {format_composite_header_expand_value(state, desc)}"


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
    desc = state.layout.descriptor(index)
    locked = section_locked(state, desc)
    budget = max_content_width - row_indent(state, index)
    budget -= track_header_prefix_width(font)
    budget -= font.size(_track_header_layer_prefix(state, index))[0]
    budget -= font.size(_track_header_expand_suffix(state, index))[0]
    if locked:
        budget -= track_header_lock_suffix_width(font.get_linesize())
    stem_text = stem_overlay_header(block.runtime.stem)
    if cache is None:
        return fit_text_to_width(font, stem_text, budget)
    return cache.fit_text_cached("text", fit_text_to_width, font, stem_text, budget)


def render_track_header_label(
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
    prefix_surf = render_text(font, layer_prefix, True, LABEL, counters=counters)
    stem_surf = render_text(font, stem_text, True, value_color, counters=counters)
    arrow_surf = render_text(font, arrow, True, value_color, counters=counters)
    lock_surf = (
        render_glyph(LOCK_GLYPH, color=LOCK_ICON, line_height=line_height)
        if locked
        else None
    )

    label_w = prefix_surf.get_width() + stem_surf.get_width() + arrow_surf.get_width()
    if lock_surf is not None:
        label_w += ROW_ICON_SUFFIX_GAP + lock_surf.get_width()

    label_surf = compose_surface((label_w, line_height), counters=counters)
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


def _fit_value(
    font: pygame.font.Font,
    text: str,
    budget: int,
    strategy: FitStrategy,
    *,
    cache: TuningPanelCache | None = None,
) -> str:
    if strategy == FitStrategy.NONE:
        return text
    if strategy == FitStrategy.PATH:
        fitter, fit_fn = "path", fit_path_label_to_width
    elif strategy == FitStrategy.COUNTER_LABEL:
        fitter, fit_fn = "counter", fit_counter_label_to_width
    else:
        fitter, fit_fn = "text", fit_text_to_width
    if cache is None:
        return fit_fn(font, text, budget)
    return cache.fit_text_cached(fitter, fit_fn, font, text, budget)


def _labeled_sub_row_prefix(state: TuningViewState, index: int) -> str:
    kind = state.layout.kind(index)
    field = ROW_SPECS.get(kind)
    if field is None:
        return ""
    if field.present_style == RowPresentStyle.LABELED_VALUE:
        return labeled_row_prefix(kind, state.layout.descriptor(index))
    if field.present_style == RowPresentStyle.DYNAMIC:
        return row_dynamic_labeled_prefix(state.layout.descriptor(index))
    return ""


def _labeled_sub_row_value(state: TuningViewState, index: int) -> str:
    field = field_for_index(state, index)
    if field is None:
        return ""
    if field.present_style in {
        RowPresentStyle.LABELED_VALUE,
        RowPresentStyle.DYNAMIC,
    }:
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
    field = field_for_index(state, index)
    strategy = field.fit_strategy if field is not None else FitStrategy.PLAIN
    budget = max_content_width - row_indent(state, index)
    budget -= font.size(_labeled_sub_row_prefix(state, index))[0]
    value = _labeled_sub_row_value(state, index)
    return _fit_value(font, value, budget, strategy, cache=cache)


def _fit_action_parameter_row_value(
    font: pygame.font.Font,
    state: TuningViewState,
    index: int,
    *,
    max_content_width: int = PANEL_CONTENT_MAX_WIDTH,
    cache: TuningPanelCache | None = None,
) -> str:
    kind = state.layout.kind(index)
    value = format_row_value(state, state.layout.descriptor(index))
    if state.settings.ui_width_mode == "flexible":
        return value
    budget = max_content_width - row_indent(state, index)
    budget -= font.size(labeled_row_prefix(kind, state.layout.descriptor(index)))[0]
    if row_shows_enter_icon(state, index):
        budget -= action_enter_icon_suffix_width(font.get_linesize())
    return _fit_value(font, value, budget, FitStrategy.PLAIN, cache=cache)


def fit_row_text(
    font: pygame.font.Font,
    state: TuningViewState,
    index: int,
    *,
    max_content_width: int = PANEL_CONTENT_MAX_WIDTH,
    cache: TuningPanelCache | None = None,
) -> str:
    """Fit row label to the shared panel content width (pixels)."""
    kind = state.layout.kind(index)
    indent = row_indent(state, index)
    budget = max_content_width - indent
    field = ROW_SPECS.get(kind)
    if field is None:
        return ""
    if field.present_style == RowPresentStyle.SPACER:
        return ""
    if field.present_style == RowPresentStyle.TRACK_HEADER:
        return (
            _track_header_layer_prefix(state, index)
            + _fit_track_header_stem(
                font,
                state,
                index,
                max_content_width=max_content_width,
                cache=cache,
            )
            + _track_header_expand_suffix(state, index)
        )
    if field.present_style == RowPresentStyle.PATH_ICON:
        line_h = font.get_linesize()
        text = row_text(state, index)
        if field.fit_strategy == FitStrategy.PATH:
            icon_w = row_icon_prefix_width(line_h)
            suffix_w = font.size("*")[0] if state.config_dirty else 0
            enter_w = (
                action_enter_icon_suffix_width(line_h)
                if row_shows_action_enter_hint(state, index)
                else 0
            )
            return _fit_value(
                font,
                text,
                budget - icon_w - suffix_w - enter_w,
                FitStrategy.PATH,
                cache=cache,
            )
        prefix_w = preset_row_prefix_width(
            font, line_h, depth=row_tree_indent_depth(kind)
        )
        return _fit_value(
            font, text, budget - prefix_w, FitStrategy.COUNTER_LABEL, cache=cache
        )
    if field.present_style == RowPresentStyle.COMPOSITE_HEADER:
        return row_composite_header_display_text(state, state.layout.descriptor(index))
    if field.present_style == RowPresentStyle.EXPAND_SUBHEADER:
        return row_expand_subheader_display_text(state, state.layout.descriptor(index))
    if field.present_style == RowPresentStyle.ACTION_PARAMETER:
        return labeled_row_prefix(kind, state.layout.descriptor(index)) + _fit_action_parameter_row_value(
            font,
            state,
            index,
            max_content_width=max_content_width,
            cache=cache,
        )
    if field.present_style in {
        RowPresentStyle.LABELED_VALUE,
        RowPresentStyle.DYNAMIC,
    }:
        return _labeled_sub_row_prefix(state, index) + _fit_labeled_sub_row_value(
            font,
            state,
            index,
            max_content_width=max_content_width,
            cache=cache,
        )
    if field.fit_strategy == FitStrategy.NONE:
        return row_text(state, index)
    return _fit_value(
        font, row_text(state, index), budget, field.fit_strategy, cache=cache
    )


def notification_elapsed(state: TuningViewState, marker_index: int | None) -> float:
    if marker_index == 0:
        return state.persistent_notification_elapsed_sec
    return state.notification_elapsed_sec


def notification_accent(marker_index: int | None) -> tuple[int, int, int]:
    if marker_index == 0:
        return ERROR_NOTIFICATION
    return HIGHLIGHT


def row_in_move_mode(state: TuningViewState, index: int) -> bool:
    stem = state.layout.slot(index)
    if stem is not None and state.move_mode_slot == stem:
        return True
    move = state.move_mode_preset
    if move is None:
        return False
    desc = state.layout.descriptor(index)
    field = field_for_index(state, index)
    return (
        field is not None
        and field.present_style == RowPresentStyle.PATH_ICON
        and desc.preset_index is not None
        and desc.slot == move[0]
        and desc.preset_index == move[1]
    )


def row_value_color(state: TuningViewState, index: int) -> tuple[int, int, int]:
    """Return the VALUE-role color for a row (before label/value split rendering)."""
    kind = state.layout.kind(index)
    field = ROW_SPECS.get(kind)
    desc = state.layout.descriptor(index)
    if field is not None and field.present_style == RowPresentStyle.NOTIFICATION:
        accent = notification_accent(desc.marker_index)
        attention = notification_attention(
            notification_elapsed(state, desc.marker_index)
        )
        if attention.text_on_fill:
            return NOTIFICATION_ON_FILL
        return accent

    locked_blocked = section_locked(state, desc) and row_blocked_by_section_lock(kind)
    affordance = row_spec(kind).affordance

    if kind in RENDER_TIMELINE_SECTION_KINDS:
        if not state.render_timeline.enabled:
            return DISABLED

    if affordance == RowAffordance.ACTION:
        if (
            field is not None
            and field.present_style == RowPresentStyle.PATH_ICON
            and field.fit_strategy == FitStrategy.PATH
            and state.solo_active
        ):
            return DISABLED
        if field is not None and field.panel_label == "Delete Layer":
            if len(state.layer_z_order) == 1:
                return DISABLED
        if locked_blocked:
            return LOCKED
        if row_has_tree_focus(state, index):
            return HIGHLIGHT
        return ACTION

    stem = state.layout.slot(index)

    if kind in RENDER_OVERLAY_SECTION_KINDS:
        overlays = state.render_overlays
        if not (
            overlays.opening_card.runtime.enabled
            or overlays.closing_card.runtime.enabled
        ):
            return DISABLED

    if kind in RENDER_POST_FX_SECTION_KINDS:
        if not state.render_post_fx.enabled:
            return DISABLED

    if kind in RENDER_PATTERN_MASK_SECTION_KINDS:
        if not state.render_pattern_mask.enabled:
            return DISABLED

    if (
        affordance == RowAffordance.PATH_PRESET
        and desc.preset_index is None
        and stem is not None
        and state.tracks[stem].preset_empty
    ):
        return DISABLED

    if row_in_move_mode(state, index):
        return MOVE_MODE

    if row_has_tree_focus(state, index):
        return HIGHLIGHT

    if locked_blocked:
        return LOCKED

    if stem is not None and track_disabled(state, stem):
        return DISABLED

    if (
        affordance == RowAffordance.PATH_PRESET
        and stem is not None
        and desc.preset_index is not None
        and state.tracks[stem].active_preset_list_index == desc.preset_index
    ):
        return HIGHLIGHT

    return VALUE


def row_bg_color(state: TuningViewState, index: int) -> tuple[int, int, int] | None:
    if row_in_move_mode(state, index):
        return MOVE_MODE
    if row_has_tree_focus(state, index):
        return HIGHLIGHT
    return None


def action_parameter_label_color(
    state: TuningViewState, index: int
) -> tuple[int, int, int]:
    """ACTION green label prefix for action-parameter rows (e.g. editor mode)."""
    kind = state.layout.kind(index)
    desc = state.layout.descriptor(index)
    locked_blocked = section_locked(state, desc) and row_blocked_by_section_lock(kind)
    if locked_blocked:
        return LOCKED
    if row_has_tree_focus(state, index):
        return HIGHLIGHT
    return ACTION


def is_transport_row(state: TuningViewState, index: int) -> bool:
    field = field_for_index(state, index)
    if field is None or field.present_style != RowPresentStyle.FULL_LINE:
        return False
    return row_spec(state.layout.kind(index)).affordance == RowAffordance.SEEK


def is_settings_header_row(state: TuningViewState, index: int) -> bool:
    field = field_for_index(state, index)
    return (
        field is not None
        and field.present_style == RowPresentStyle.COMPOSITE_HEADER
        and field.visibility_icon is None
    )


def is_notification_row(state: TuningViewState, index: int) -> bool:
    field = field_for_index(state, index)
    return field is not None and field.present_style == RowPresentStyle.NOTIFICATION


@dataclass(frozen=True)
class RowPresentContext:
    font: pygame.font.Font
    state: TuningViewState
    index: int
    padding: int
    line_h: int
    max_content_width: int
    counters: OverlayDrawCounters | None
    cache: TuningPanelCache | None

    @property
    def kind(self):
        return self.state.layout.kind(self.index)

    @property
    def desc(self):
        return self.state.layout.descriptor(self.index)

    @property
    def field(self) -> RowSpec | None:
        return ROW_SPECS.get(self.kind)

    @property
    def indent(self) -> int:
        return self.padding + row_indent(self.state, self.index)

    @property
    def color(self) -> tuple[int, int, int]:
        return row_value_color(self.state, self.index)


RowPaint = Callable[
    [RowPresentContext], tuple[pygame.Surface, pygame.Surface | None, int]
]


def _paint_transport(
    ctx: RowPresentContext,
) -> tuple[pygame.Surface, pygame.Surface | None, int]:
    icons_surf = render_transport_icons(
        color=ctx.color,
        line_height=ctx.line_h,
        paused=ctx.state.paused,
    )
    time_text = f" [{format_mmss(ctx.state.position_sec)}]"
    time_surf = render_text(
        ctx.font, time_text, True, ctx.color, counters=ctx.counters
    )
    width = ctx.indent + icons_surf.get_width() + time_surf.get_width()
    return icons_surf, time_surf, width


def _paint_track_header(
    ctx: RowPresentContext,
) -> tuple[pygame.Surface, pygame.Surface | None, int]:
    stem = ctx.state.layout.slot(ctx.index)
    key = row_visibility_icon_key(ctx.state, ctx.index)
    enabled, solo = (True, False) if key is None else key
    locked = section_locked(ctx.state, ctx.desc)
    prefix_surf = render_visibility_icon(
        enabled=enabled, solo=solo, line_height=ctx.line_h
    )
    layer_prefix = composite_header_prefix_part(ctx.state, ctx.desc)
    stem_text = _fit_track_header_stem(
        ctx.font,
        ctx.state,
        ctx.index,
        max_content_width=ctx.max_content_width,
        cache=ctx.cache,
    )
    expand_arrow = (
        format_composite_header_expand_value(ctx.state, ctx.desc)
        if stem is not None
        else expand_arrow_glyph(False)
    )
    label_surf = render_track_header_label(
        ctx.font,
        layer_prefix=layer_prefix,
        stem_text=stem_text,
        value_color=ctx.color,
        expand_arrow=expand_arrow,
        locked=locked,
        line_height=ctx.line_h,
        counters=ctx.counters,
    )
    width = ctx.indent + prefix_surf.get_width() + label_surf.get_width()
    return prefix_surf, label_surf, width


def _paint_composite_header(
    ctx: RowPresentContext,
) -> tuple[pygame.Surface, pygame.Surface | None, int]:
    field = ctx.field
    assert field is not None
    if field.visibility_icon is None:
        icon_surf = render_glyph(SETTINGS_GLYPH, color=VALUE, line_height=ctx.line_h)
        label_surf = render_label_value_row(
            ctx.font,
            prefix=composite_header_prefix_part(ctx.state, ctx.desc),
            value=format_composite_header_expand_value(ctx.state, ctx.desc),
            value_color=ctx.color,
            prefix_color=LABEL,
            line_height=ctx.line_h,
            counters=ctx.counters,
        )
        width = ctx.indent + icon_surf.get_width() + label_surf.get_width()
        return icon_surf, label_surf, width

    key = row_visibility_icon_key(ctx.state, ctx.index)
    enabled, solo = (True, False) if key is None else key
    header_locked = section_locked(ctx.state, ctx.desc)
    prefix_surf = render_visibility_icon(
        enabled=enabled, solo=solo, line_height=ctx.line_h
    )
    label_surf = render_track_header_label(
        ctx.font,
        layer_prefix=composite_header_prefix_part(ctx.state, ctx.desc),
        stem_text=composite_header_suffix_part(ctx.state, ctx.desc),
        value_color=ctx.color,
        expand_arrow=format_composite_header_expand_value(ctx.state, ctx.desc),
        locked=header_locked,
        line_height=ctx.line_h,
        counters=ctx.counters,
    )
    width = ctx.indent + prefix_surf.get_width() + label_surf.get_width()
    return prefix_surf, label_surf, width


def _paint_spacer(
    ctx: RowPresentContext,
) -> tuple[pygame.Surface, pygame.Surface | None, int]:
    gap_surf = compose_surface((1, ctx.line_h), counters=ctx.counters)
    return gap_surf, None, ctx.indent + gap_surf.get_width()


def _paint_path_icon(
    ctx: RowPresentContext,
) -> tuple[pygame.Surface, pygame.Surface | None, int]:
    field = ctx.field
    assert field is not None
    kind = ctx.kind
    depth = row_tree_indent_depth(kind)
    affordance = row_spec(kind).affordance
    if affordance == RowAffordance.PATH_DIR:
        icon_surf = _render_preset_row_prefix(
            ctx.font,
            glyph=FOLDER_GLYPH,
            icon_color=PRESET_ICON,
            line_height=ctx.line_h,
            depth=depth,
            counters=ctx.counters,
        )
    elif affordance == RowAffordance.PATH_PRESET:
        icon_surf = _render_preset_row_prefix(
            ctx.font,
            glyph=FILE_GLYPH,
            icon_color=PRESET_FILE_ICON,
            line_height=ctx.line_h,
            depth=depth,
            counters=ctx.counters,
        )
    else:
        icon_surf = render_glyph(
            FILE_GLYPH, color=PRESET_FILE_ICON, line_height=ctx.line_h
        )
    if field.fit_strategy == FitStrategy.PATH:
        path = fit_row_text(
            ctx.font,
            ctx.state,
            ctx.index,
            max_content_width=ctx.max_content_width,
            cache=ctx.cache,
        )
        label_surf = render_label_value_row(
            ctx.font,
            prefix=path,
            value="*" if ctx.state.config_dirty else "",
            value_color=CONFIG_DIRTY,
            prefix_color=ctx.color,
            line_height=ctx.line_h,
            counters=ctx.counters,
        )
    else:
        label = fit_row_text(
            ctx.font,
            ctx.state,
            ctx.index,
            max_content_width=ctx.max_content_width,
            cache=ctx.cache,
        )
        label_surf = render_text(
            ctx.font, label, True, ctx.color, counters=ctx.counters
        )
    width = ctx.indent + icon_surf.get_width() + label_surf.get_width()
    return icon_surf, label_surf, width


def _paint_expand_subheader(
    ctx: RowPresentContext,
) -> tuple[pygame.Surface, pygame.Surface | None, int]:
    surf = render_label_value_row(
        ctx.font,
        prefix=expand_subheader_prefix(ctx.kind, ctx.desc),
        value=format_expand_subheader_value(ctx.state, ctx.desc),
        value_color=ctx.color,
        line_height=ctx.line_h,
        counters=ctx.counters,
    )
    return surf, None, ctx.indent + surf.get_width()


def _paint_action_parameter(
    ctx: RowPresentContext,
) -> tuple[pygame.Surface, pygame.Surface | None, int]:
    prefix = labeled_row_prefix(ctx.kind, ctx.desc)
    value = _fit_action_parameter_row_value(
        ctx.font,
        ctx.state,
        ctx.index,
        max_content_width=ctx.max_content_width,
        cache=ctx.cache,
    )
    value_color = ctx.color
    suffix_surf = None
    suffix_gap = 0
    if editor_mode_confirm_pending(ctx.state):
        suffix_surf = render_action_enter_icon(
            color=value_color, line_height=ctx.line_h
        )
        suffix_gap = ROW_ICON_SUFFIX_GAP
    locked_blocked = section_locked(
        ctx.state, ctx.desc
    ) and row_blocked_by_section_lock(ctx.kind)
    prefix_color = action_parameter_label_color(ctx.state, ctx.index)
    surf = render_label_value_row(
        ctx.font,
        prefix=prefix,
        value=value,
        value_color=value_color,
        prefix_color=prefix_color,
        line_height=ctx.line_h,
        suffix_surf=suffix_surf,
        suffix_gap=suffix_gap,
        counters=ctx.counters,
    )
    return surf, None, ctx.indent + surf.get_width()


def _paint_labeled_value(
    ctx: RowPresentContext,
) -> tuple[pygame.Surface, pygame.Surface | None, int]:
    prefix = _labeled_sub_row_prefix(ctx.state, ctx.index)
    value = _fit_labeled_sub_row_value(
        ctx.font,
        ctx.state,
        ctx.index,
        max_content_width=ctx.max_content_width,
        cache=ctx.cache,
    )
    surf = render_label_value_row(
        ctx.font,
        prefix=prefix,
        value=value,
        value_color=ctx.color,
        line_height=ctx.line_h,
        counters=ctx.counters,
    )
    return surf, None, ctx.indent + surf.get_width()


def _paint_full_line(
    ctx: RowPresentContext,
) -> tuple[pygame.Surface, pygame.Surface | None, int]:
    if is_transport_row(ctx.state, ctx.index):
        return _paint_transport(ctx)
    label = row_text(ctx.state, ctx.index)
    surf = render_text(ctx.font, label, True, ctx.color, counters=ctx.counters)
    return surf, None, ctx.indent + surf.get_width()


def _paint_notification(
    ctx: RowPresentContext,
) -> tuple[pygame.Surface, pygame.Surface | None, int]:
    text = fit_row_text(
        ctx.font,
        ctx.state,
        ctx.index,
        max_content_width=ctx.max_content_width,
        cache=ctx.cache,
    )
    surf = render_text(ctx.font, text, True, ctx.color, counters=ctx.counters)
    return surf, None, ctx.indent + surf.get_width()


ROW_PRESENT_RENDERERS: dict[RowPresentStyle, RowPaint] = {
    RowPresentStyle.LABELED_VALUE: _paint_labeled_value,
    RowPresentStyle.DYNAMIC: _paint_labeled_value,
    RowPresentStyle.ACTION_PARAMETER: _paint_action_parameter,
    RowPresentStyle.EXPAND_SUBHEADER: _paint_expand_subheader,
    RowPresentStyle.COMPOSITE_HEADER: _paint_composite_header,
    RowPresentStyle.PATH_ICON: _paint_path_icon,
    RowPresentStyle.FULL_LINE: _paint_full_line,
    RowPresentStyle.TRACK_HEADER: _paint_track_header,
    RowPresentStyle.NOTIFICATION: _paint_notification,
    RowPresentStyle.SPACER: _paint_spacer,
}


def render_present_row(
    ctx: RowPresentContext,
) -> tuple[pygame.Surface, pygame.Surface | None, int]:
    field = ctx.field
    style = field.present_style if field is not None else RowPresentStyle.FULL_LINE
    painter = ROW_PRESENT_RENDERERS.get(style, _paint_full_line)
    primary, secondary, width = painter(ctx)
    return with_action_enter_hint(
        primary,
        secondary,
        width,
        state=ctx.state,
        index=ctx.index,
        indent=ctx.indent,
        line_h=ctx.line_h,
        counters=ctx.counters,
    )
